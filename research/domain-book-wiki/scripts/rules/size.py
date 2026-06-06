"""rules/size.py — 字数阈值 & "无"字段检查 & 知识密度"""
import os
import re

from dag_constants import DIR
from log_utils import get_logger

log = get_logger(__name__)

__all__ = [
    "_detect_node_type", "_extract_subsections", "_count_pure_text_chars",
    "check_field_word_counts", "check_wu_field_count", "check_knowledge_density",
    "check_kp_depth", "check_sp_depth", "check_scene_depth",
]

# 类型 → node_type 映射
_DIR_TO_NODE_TYPE = {
    DIR["CONCEPTS"]: "concept", DIR["KE"]: "knowledge-element",
    DIR["KP"]: "knowledge", DIR["SP"]: "skill", DIR["SCENE"]: "scenario",
    DIR["EXERCISES"]: "exercise", DIR["SOLUTIONS"]: "solution",
    DIR["ENTITIES"]: "entity",
}

# 各类型关键字段阈值：{ node_type: { heading_pattern_regex: min_chars } }
_FIELD_WORD_THRESHOLDS: dict = {
    "concept": {
        r"结构分析": 100,
        r"核心概念图谱解析|core_concept_map_analysis|图谱解析": 100,
        r"解决的问题|solved_problem": 30,
    },
    "skill": {r"核心操作": 200, r"技能目标|skill_objectives": 0},
    "knowledge": {
        r"理论基础|theoretical_basis": 200, r"推导说明|derivation_analysis": 200,
        r"关键细节|key_details": 100, r"典型例题|typical_examples": 200,
        r"应用方法|application_methods": 100, r"应用场景|application_scenarios": 100,
        r"工程实践|engineering_practices": 80, r"踩坑|辨析|confusion_compare": 80,
        r"知识网络解析|diagram_analysis": 200, r"图谱解析|bloom_progression_analysis": 150,
        r"解决的问题|solved_problem": 30, r"技能要求|skill_requirements": 50,
    },
    "scenario": {r"场景描述|scenario_description": 100, r"流程分析|workflow_analysis": 200},
    "solution": {r"实现流程|分步|principle_steps": 400, r"知识闭环[^图]|knowledge_loop_analysis": 200},
}

# 各类型「无」/「暂无」字段上限
_WU_FIELD_LIMITS: dict = {
    "concept": 4, "knowledge-element": 3, "knowledge": 5,
    "skill": 4, "scenario": 3, "solution": 2,
}

# 禁止为「无」的字段列表（必须由Agent生成实质内容）
_WU_FORBIDDEN_PATTERNS: dict = {
    "concept": [r"解决的问题|solved_problem"],
    "knowledge": [
        r"解决的问题|solved_problem", r"层级解读|bloom_level_description",
        r"Bloom对齐矩阵|bloom_alignment", r"技能要求|skill_requirements",
        r"技能目标|skill_objectives",
        r"理论基础|theoretical_basis", r"推导过程|derivation_diagram",
        r"关键细节|key_details", r"核心知识要素|core_knowledge_elements_table",
        r"典型例题|typical_examples", r"知识网络|knowledge_context_diagram",
    ],
    "skill": [
        r"层级解读|bloom_level_description", r"Bloom对齐矩阵|bloom_alignment",
        r"技能目标|skill_objectives", r"核心操作|core_operation",
        r"解决的问题|solved_problem",
    ],
    "scenario": [
        r"层级解读|bloom_level_description", r"Bloom对齐矩阵|bloom_alignment",
        r"场景目标|scenario_description", r"各节点工作描述|node_descriptions",
        r"知识脉络|knowledge_context",
    ],
    "knowledge-element": [r"术语定义|term_definition", r"一句话说明|definition_sentence"],
    "entity": [r"实体类型|entity_type", r"实体描述|term_definition"],
}


def _detect_node_type(filepath: str, wiki_root: str) -> str:
    """根据文件路径检测节点类型"""
    norm_path, norm_root = os.path.normpath(filepath), os.path.normpath(wiki_root)
    for dir_name, node_type in _DIR_TO_NODE_TYPE.items():
        cand = os.path.normpath(os.path.join(norm_root, dir_name))
        if norm_path.startswith(cand + os.sep) or norm_path.startswith(cand):
            return node_type
    return "unknown"


def _extract_subsections(body: str) -> list[tuple[str, str]]:
    """从 body 中提取所有 ### 子节，返回 [(标题, 纯文本内容), ...]"""
    subs = []
    sec_pattern = re.compile(r"^(#{3,4})\s+(.+)$", re.MULTILINE)
    matches = list(sec_pattern.finditer(body))
    if not matches:
        return subs
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        raw = re.sub(r"```.*?```", "", body[start:end], flags=re.DOTALL)
        cleaned = "\n".join(line for line in raw.split("\n") if line.strip())
        subs.append((heading, cleaned))
    return subs


def _count_pure_text_chars(text: str) -> int:
    """计算纯文本字数（去除 Markdown 标记、代码、多余空白）"""
    t = text
    for pat, repl in [
        (r"```.*?```", ""), (r"`[^`]+`", ""), (r"\[\[([^\]]+)\]\]", r"\1"),
        (r"!\[.*?\]\(.*?\)", ""), (r"\[([^\]]*)\]\([^)]*\)", r"\1"),
        (r"<[^>]+>", ""), (r"\*{1,3}", ""), (r"_{1,3}", ""),
    ]:
        t = re.sub(pat, repl, t, flags=re.DOTALL if "```" in pat else 0)
    t = re.sub(r"^>\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^#{1,4}\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"\s+", "", t)
    return len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9]", t))


def check_field_word_counts(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """按字段粒度（### 子节）检查文字密度"""
    results = []
    node_type = _detect_node_type(filepath, wiki_root)
    if node_type == "unknown" or node_type not in _FIELD_WORD_THRESHOLDS:
        return results
    thresholds = _FIELD_WORD_THRESHOLDS[node_type]
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"文件读取失败 ({filepath}): {e}")
        return results
    parts = content.split("---", 2)
    body = parts[2] if len(parts) >= 3 else content
    name = os.path.basename(filepath).replace(".md", "")
    label = f"{node_type}/{name}"
    subsections = _extract_subsections(body)

    if node_type == "skill":
        for heading, text in subsections:
            if re.search(r"技能目标|skill_objectives", heading):
                items = re.findall(r"^\s*[-*\d.]\s+\S", text, re.MULTILINE)
                if len(items) < 3:
                    results.append(("WARN", "FieldWordCount",
                        f"[{label}] 字段「{heading}」条目数 {len(items)} < 3（技能目标至少 3 条）"))
                continue

    for heading, text in subsections:
        for pattern, min_chars in thresholds.items():
            if min_chars == 0:
                continue
            if re.search(pattern, heading):
                char_count = _count_pure_text_chars(text)
                if char_count < min_chars:
                    results.append(("WARN", "FieldWordCount",
                        f"[{label}] 字段「{heading}」字数 {char_count} < {min_chars}（阈值）"))

    if node_type == "solution":
        for heading, text in subsections:
            if re.search(r"常见错误|common_mistakes|易错", heading):
                items = re.split(r"\n(?=#{3,4}\s|\*\*[^*]+\*\*\s*\n|[-*\d.]\s)", text)
                for item in items:
                    item_text = item.strip()
                    if not item_text or len(item_text) < 10:
                        continue
                    char_count = _count_pure_text_chars(item_text)
                    if char_count < 50:
                        results.append(("WARN", "FieldWordCount",
                            f"[{label}] 常见错误条目字数 {char_count} < 50（「{item_text[:30]}...」）"))
    return results


def check_wu_field_count(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """统计文件中「无」/「暂无」/「无。」字段数"""
    results = []
    node_type = _detect_node_type(filepath, wiki_root)
    limit = _WU_FIELD_LIMITS.get(node_type)
    if limit is None:
        return results
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"文件读取失败 ({filepath}): {e}")
        return results
    parts = content.split("---", 2)
    body = parts[2] if len(parts) >= 3 else content
    name = os.path.basename(filepath).replace(".md", "")
    label = f"{node_type}/{name}"
    subsections = _extract_subsections(body)
    wu_fields: list[str] = []

    for heading, text in subsections:
        stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        stripped = re.sub(r"\s+", "", stripped)
        if stripped in ("无", "暂无", "无。", "暂无。", ""):
            wu_fields.append(heading)

    if len(wu_fields) > limit:
        results.append(("WARN", "WuFieldCount",
            f"[{label}] 「无」字段数 {len(wu_fields)} > {limit}（上限）: {', '.join(wu_fields)}"))

    forbidden = _WU_FORBIDDEN_PATTERNS.get(node_type, [])
    for heading in wu_fields:
        for pattern in forbidden:
            if re.search(pattern, heading):
                results.append(("FAIL", "ForbiddenWuField",
                    f"[{label}] 字段「{heading}」禁止为「无」——必须由Agent生成实质内容"))
    return results


def check_knowledge_density(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """知识密度评分 — 实质内容字符数 / 总字符数。阈值: <60%→WARN, <45%→FAIL"""
    results = []
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"知识密度评分文件读取失败 ({filepath}): {e}")
        return results
    name = os.path.basename(filepath).replace(".md", "")
    node_type = _detect_node_type(filepath, wiki_root)
    label = f"{node_type}/{name}"

    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content

    # 排除代码块、HTML注释、模板指令
    cleaned = body
    cleaned = re.sub(r"```mermaid.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\{%[-]?[^%]*%\}?", "", cleaned)

    total_chars = len(re.sub(r"\s", "", cleaned))
    if total_chars == 0:
        return results

    # 计算实质内容字符数（去除Markdown格式标记）
    substantive = cleaned
    substantive = re.sub(r"^#{1,6}\s+", "", substantive, flags=re.MULTILINE)
    substantive = re.sub(r"^\s*[-*+]\s+", "", substantive, flags=re.MULTILINE)
    substantive = re.sub(r"^\s*\d+\.\s+", "", substantive, flags=re.MULTILINE)
    substantive = re.sub(r"\[\[([^\]]+)\]\]", r"\1", substantive)
    substantive = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", substantive)
    substantive = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", substantive)
    substantive = re.sub(r"\*{1,3}", "", substantive)
    substantive = re.sub(r"_{1,3}", "", substantive)
    substantive = re.sub(r"`[^`]+`", "", substantive)
    substantive_chars = len(re.sub(r"\s", "", substantive))

    density = substantive_chars / total_chars if total_chars > 0 else 0
    if density < 0.45:
        results.append(("FAIL", "KnowledgeDensity",
            f"[{label}] 知识密度极低: {density:.1%} < 45%（实质 {substantive_chars} / 总 {total_chars} 字符）"))
    elif density < 0.60:
        results.append(("WARN", "KnowledgeDensity",
            f"[{label}] 知识密度偏低: {density:.1%} < 60%（实质 {substantive_chars} / 总 {total_chars} 字符）"))
    return results


def check_kp_depth(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """KP 内容深度自检 — 3 项指标：具体性、源文锚定、可操作性"""
    results = []
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"KP内容深度检查文件读取失败 ({filepath}): {e}")
        return results

    name = os.path.basename(filepath).replace(".md", "")
    label = f"KP/{name}"

    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content

    # ── 1. 具体性 ──
    # 统计 ≥3 个数字+单位组合（如 125MHz, 10dB, 100μV/m）和 $$ 公式数
    num_unit_pattern = re.compile(
        r"\d+(?:\.\d+)?\s*(?:MHz|GHz|kHz|Hz|dB|dBm|dBμV|μV/m|V/m|A/m|"
        r"μV|mV|V|μA|mA|A|Ω|kΩ|MΩ|μF|nF|pF|μH|nH|mH|H|"
        r"W|kW|mW|dBμA|dBμV/m|m/s|km/h|rpm|°C|°F|K|"
        r"s|ms|μs|ns|ps|bit|bps|Mbps|Gbps|%|ppm)",
    )
    num_unit_count = len(num_unit_pattern.findall(body))
    formula_count = len(re.findall(r"\$\$", body))

    if num_unit_count < 3 and formula_count == 0:
        results.append((
            "FAIL", "KpDepthSpecificity",
            f"[{label}] 具体性不足：数字+单位组合 {num_unit_count} 个（需 ≥3），"
            f"$$ 公式 {formula_count} 个（需 ≥1）。请补充量化数据和公式",
        ))
    elif num_unit_count < 3:
        results.append((
            "FAIL", "KpDepthSpecificity",
            f"[{label}] 具体性不足：数字+单位组合 {num_unit_count} 个（需 ≥3）。"
            f"请补充量化数据",
        ))
    elif formula_count == 0:
        results.append((
            "WARN", "KpDepthSpecificity",
            f"[{label}] 建议补充：$$ 公式 {formula_count} 个。"
            f"数字+单位组合 {num_unit_count} 个（已满足 ≥3）",
        ))

    # ── 2. 源文锚定 ──
    # 检查 source_from 是否含 Lxx-xx / Lxx–xx 行号
    src_anchor_pattern = re.compile(r"L\d+[-\u2013]\d+")
    if not src_anchor_pattern.search(content):
        results.append((
            "WARN", "KpDepthSourceAnchor",
            f"[{label}] 源文锚定缺失：source_from 中未找到 Lxx-xx 行号引用",
        ))

    # ── 3. 可操作性 ──
    tools_list = [
        "频谱仪", "示波器", "近场探头", "电流探头", "LISN",
        "R&S", "Keysight", "Rohde",
    ]
    standards_list = ["大于", "小于", "超过", "判据", "标准限值"]

    tools_found = [t for t in tools_list if t.lower() in content.lower()]
    standards_found = [s for s in standards_list if s in content]

    if not tools_found and not standards_found:
        results.append((
            "WARN", "KpDepthOperability",
            f"[{label}] 可操作性不足：未找到工具名（{', '.join(tools_list)} 等）"
            f"和判断标准关键词（{', '.join(standards_list)} 等）。请补充实操指引",
        ))
    elif not tools_found:
        results.append((
            "WARN", "KpDepthOperability",
            f"[{label}] 可操作性不足：未找到工具名（{', '.join(tools_list)} 等）。"
            f"检测到标准关键词: {', '.join(standards_found)}",
        ))
    elif not standards_found:
        results.append((
            "WARN", "KpDepthOperability",
            f"[{label}] 可操作性不足：未找到判断标准关键词（{', '.join(standards_list)} 等）。"
            f"检测到工具名: {', '.join(tools_found)}",
        ))

    return results


def check_scene_depth(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """Scene 内容深度自检 — 3 项指标：具体性（工程参数）、源文锚定、完整性（流程图+方案详解）

    指标：
    - 具体性: ≥3 个工程参数（成本/尺寸/频率/限值等具体数值）
    - 源文锚定: source_from 含 Lxx-xx 行号
    - 完整性: 工作流程图≥8节点 + 方案详解≥4分项 + 每节点有工作描述
    """
    results = []
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"Scene内容深度检查文件读取失败 ({filepath}): {e}")
        return results

    name = os.path.basename(filepath).replace(".md", "")
    label = f"Scene/{name}"

    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content

    # ── 1. 具体性：工程约束参数 ──
    # 统计 ≥3 个工程参数组合（成本/尺寸/频率/限值/裕量/温度/效率等具体数值）
    eng_param_patterns = [
        # 成本类
        re.compile(r"BOM\s*(?:增加|成本)?\s*[<＜]\s*(?:\$|¥)?\d+(?:\.\d+)?%?"),
        re.compile(r"(?:成本|价格)\s*[<＜]\s*(?:\$|¥)?\d+(?:\.\d+)?"),
        # 尺寸类
        re.compile(r"\d+(?:\.\d+)?\s*×\s*\d+(?:\.\d+)?(?:\s*×\s*\d+(?:\.\d+)?)?\s*(?:mm|cm|m)"),
        re.compile(r"(?:尺寸|体积)\s*(?:[<＜]|限制|约束)\s*\d+"),
        # 频率类
        re.compile(r"\d+(?:\.\d+)?\s*(?:MHz|GHz|kHz|Hz)\b"),
        # 标准限值类
        re.compile(r"\d+(?:\.\d+)?\s*dB(?:μV/m|μV|m)?\s*(?:@|at|限值|Class|限)"),
        re.compile(r"CISPR\s*\d+"),
        # 裕量类
        re.compile(r"(?:裕量|margin)\s*[>＞≥]\s*\d+(?:\.\d+)?\s*dB"),
        # 温升/效率类
        re.compile(r"(?:温升|效率)\s*[<＜>＞]\s*\d+(?:\.\d+)?\s*(?:°C|%)"),
        # 防护/开口率
        re.compile(r"IP\d{2}"),
        re.compile(r"(?:开口率|通风)\s*[>＞≥]?\s*\d+(?:\.\d+)?\s*%"),
    ]
    eng_param_matches = []
    for pat in eng_param_patterns:
        eng_param_matches.extend(pat.findall(body))
    eng_param_count = len(eng_param_matches)

    if eng_param_count < 3:
        results.append((
            "FAIL", "SceneDepthSpecificity",
            f"[{label}] 具体性不足：工程约束参数 {eng_param_count} 个（需 ≥3）。"
            f"请补充成本/尺寸/频率/限值/裕量等具体数值。"
            f"检测到的参数: {eng_param_matches}",
        ))

    # ── 2. 源文锚定 ──
    src_anchor_pattern = re.compile(r"L\d+[-–]\d+")
    if not src_anchor_pattern.search(content):
        results.append((
            "WARN", "SceneDepthSourceAnchor",
            f"[{label}] 源文锚定缺失：source_from 中未找到 Lxx-xx 行号引用",
        ))

    # ── 3a. 完整性 — 工作流程图节点数 ──
    # 提取 mermaid 代码块中的节点定义
    mermaid_blocks = re.findall(r"```mermaid\s*\n(.*?)```", body, re.DOTALL)
    workflow_nodes_found = 0
    has_branch = False

    # 定位工作流程区域的 mermaid 图
    for mb in mermaid_blocks:
        # 只检查 graph 类型的 mermaid
        if re.search(r"graph\s+(TD|LR|BT|RL)", mb):
            # 统计节点：匹配形如 A[、A(、A{ 的节点定义
            nodes = re.findall(r"\b([A-Za-z0-9_]+)\s*[\[\(\{]", mb)
            unique_nodes = len(set(nodes))
            if unique_nodes > workflow_nodes_found:
                workflow_nodes_found = unique_nodes
                # 检查是否有分支判断（菱形节点 {}）
                has_branch = bool(re.search(r"\{[^}]*\}", mb))

    if workflow_nodes_found < 8:
        results.append((
            "FAIL", "SceneDepthWorkflowNodes",
            f"[{label}] 工作流程图节点数不足：{workflow_nodes_found} 个（需 ≥8）。"
            f"请扩展流程图，增加更多实施步骤",
        ))
    elif not has_branch:
        results.append((
            "WARN", "SceneDepthWorkflowBranch",
            f"[{label}] 工作流程图缺少分支判断：{workflow_nodes_found} 个节点，"
            f"但无菱形判断节点 {{条件?}}。请添加至少 1 个分支判断",
        ))

    # ── 3b. 完整性 — 节点工作描述不为"无" ──
    node_desc_patterns = [
        r"各节点工作描述|node_descriptions|节点描述",
    ]
    node_desc_is_wu = False
    node_desc_found = False

    subsections = _extract_subsections(body)
    for heading, text in subsections:
        for pat in node_desc_patterns:
            if re.search(pat, heading):
                node_desc_found = True
                # 移除代码块、HTML注释和后续 ##/### 标题
                stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
                stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)
                stripped = re.split(r"\n##\s", stripped)[0]
                stripped = re.sub(r"\s+", "", stripped)
                if not stripped or stripped in ("无", "暂无", "无。", "暂无。"):
                    node_desc_is_wu = True
                break
        if node_desc_found:
            break

    if not node_desc_found:
        # 也检查 workflow_analysis 是否存在且不为"无"
        for heading, text in subsections:
            if re.search(r"workflow_analysis|流程分析|操作流程说明", heading):
                stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
                stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.DOTALL)
                stripped = re.split(r"\n##\s", stripped)[0]
                stripped = re.sub(r"\s+", "", stripped)
                if stripped in ("无", "暂无", "无。", "暂无。", ""):
                    node_desc_is_wu = True
                node_desc_found = True
                break

    if node_desc_is_wu or not node_desc_found:
        results.append((
            "FAIL", "SceneDepthNodeDescriptions",
            f"[{label}] 节点工作描述缺失：node_descriptions 或 workflow_analysis 为'无'或缺失。"
            f"每个工作流节点必须有一句话工作描述",
        ))

    # ── 3c. 完整性 — 方案详解分项数 ──
    solution_section = ""
    for heading, text in subsections:
        if re.search(
            r"typical_application_cases|方案详解|案例详述|详细方案",
            heading,
        ):
            solution_section = text
            break

    solution_subitems = 0
    if solution_section:
        # 匹配 "一、xxx" "二、xxx" ... "N、" 格式
        solution_subitems = len(re.findall(
            r"(?:^|\n)\s*(?:[一二三四五六七八九十]、|[1-9]\d*[.、])",
            solution_section,
        ))
        # 也匹配 "一." 或 "1." 格式
        if solution_subitems == 0:
            solution_subitems = len(re.findall(
                r"(?:^|\n)\s*(?:[一二三四五六七八九十][.、])",
                solution_section,
            ))

    if solution_subitems < 4:
        results.append((
            "FAIL", "SceneDepthSolutionSubitems",
            f"[{label}] 方案详解分项数不足：{solution_subitems} 个（需 ≥4）。"
            f"请按 一、二、三、... 格式补充分项设计内容",
        ))

    # ── 3d. 完整性 — 方案详解含定量预期结果 ──
    if solution_section:
        has_quantitative_result = bool(re.search(
            r"(?:预期|预计|预期结果|效果验证).*?(?:\d+(?:\.\d+)?\s*(?:dB|%|位|bit|ENOB|°C|mm|MHz|V|A|W|\$|¥))",
            solution_section,
        ))
        if not has_quantitative_result:
            # 更宽松：方案末尾是否有数值指标
            has_quantitative_result = bool(re.search(
                r"(?:裕量|margin|ENOB|有效位|BOM|成本)\s*[>＞≥<＜≈=]?\s*\d+(?:\.\d+)?",
                solution_section,
            ))
        if not has_quantitative_result:
            results.append((
                "WARN", "SceneDepthQuantitativeResult",
                f"[{label}] 方案详解缺少定量预期结果。"
                f"请在末尾补充预期裕量/性能指标/成本等数值",
            ))

    return results


def check_sp_depth(filepath: str, wiki_root: str = "") -> list[tuple[str, str, str]]:
    """SP 内容深度自检 — 3 项指标：具体性（≥3 工具/材料/参数名+具体数值）、源文锚定（Lxx-xx）、可操作性（流程图≥6节点+实操案例含分步操作）"""
    results = []
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"SP内容深度检查文件读取失败 ({filepath}): {e}")
        return results

    name = os.path.basename(filepath).replace(".md", "")
    label = f"SP/{name}"

    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else content

    # ── 1. 具体性：≥3 个工具/材料/参数名 + 具体数值 ──
    sp_tools_list = [
        "频谱仪", "频谱分析仪", "示波器", "矢量网络分析仪", "网络分析仪",
        "EMI接收机", "信号发生器", "功率计", "微欧表",
        "LISN", "线路阻抗稳定网络", "近场探头", "电流探头", "电场探头",
        "磁场探头", "天线", "耦合钳", "CDN", "耦合去耦网络",
        "R&S", "Keysight", "Tektronix", "Rohde", "Langer",
        "TDK", "Murata", "Schurter",
        "HFSS", "CST", "Ansys", "ADS", "SPICE", "FilterSolutions",
        "Nuhertz",
        "铜编织带", "导电衬垫", "导电漆", "emi屏蔽", "滤波连接器",
        "共模扼流圈", "铁氧体磁珠", "铁氧体", "锰锌", "镍锌",
        "snubber", "阻尼电阻", "屏蔽电缆", "铜箔",
    ]
    sp_num_unit_pattern = re.compile(
        r"\d+(?:\.\d+)?\s*(?:MHz|GHz|kHz|Hz|dB|dBm|dBμV|dBμV/m|μV/m|V/m|A/m|"
        r"μV|mV|V|μA|mA|A|Ω|kΩ|MΩ|μF|nF|pF|μH|nH|mH|H|"
        r"W|kW|mW|dBμA|m/s|km/h|rpm|°C|°F|K|"
        r"s|ms|μs|ns|ps|bit|bps|Mbps|Gbps|%|ppm|"
        r"mm|cm|m|km|mil|inch|"
        r"V/ns|A/μs|S/m|N·m|g|kg)",
    )

    tools_found = [t for t in sp_tools_list if t.lower() in content.lower()]
    num_unit_count = len(sp_num_unit_pattern.findall(body))

    if len(tools_found) < 3 and num_unit_count < 3:
        results.append((
            "FAIL", "SpDepthSpecificity",
            f"[{label}] 具体性严重不足：工具/材料名 {len(tools_found)} 个（需 ≥3），"
            f"数字+单位组合 {num_unit_count} 个（需 ≥3）。请补充具体工具名和量化数据",
        ))
    elif len(tools_found) < 3:
        results.append((
            "FAIL", "SpDepthSpecificity",
            f"[{label}] 具体性不足：工具/材料名 {len(tools_found)} 个（需 ≥3）。"
            f"数字+单位组合 {num_unit_count} 个（已满足 ≥3）。请补充具体工具名",
        ))
    elif num_unit_count < 3:
        results.append((
            "FAIL", "SpDepthSpecificity",
            f"[{label}] 具体性不足：数字+单位组合 {num_unit_count} 个（需 ≥3）。"
            f"检测到工具名: {', '.join(tools_found[:5])}",
        ))

    # ── 2. 源文锚定：source_from 含 Lxx-xx ──
    src_anchor_pattern_sp2 = re.compile(r"L\d+[-–]\d+")
    if not src_anchor_pattern_sp2.search(content):
        results.append((
            "WARN", "SpDepthSourceAnchor",
            f"[{label}] 源文锚定缺失：source_from 中未找到 Lxx-xx 行号引用。"
            f"请 read_file 精读源文容器后标注精确行号范围",
        ))

    # ── 3. 可操作性：操作流程图 ≥6 节点 + 实操案例含分步操作 ──
    mermaid_blocks_sp2 = re.findall(r"```mermaid\s*\n(.*?)```", body, re.DOTALL)
    node_count_total = 0
    for block in mermaid_blocks_sp2:
        nodes = re.findall(r"^\s+([A-Za-z0-9_]+)[\[\(\{]", block, re.MULTILINE)
        node_count_total = max(node_count_total, len(set(nodes)) if nodes else 0)

    if node_count_total < 6:
        results.append((
            "WARN", "SpDepthFlowchartNodes",
            f"[{label}] 操作流程图节点数不足：最大 Mermaid 图 {node_count_total} 个节点（需 ≥6）。"
            f"请在 operation_flowchart 中扩展操作步骤序列",
        ))

    # 3b. 检查实操案例是否含分步操作
    case_section_pattern = re.compile(
        r"(?:典型实操案例|typical_practical_cases|实操演练|实操案例).*?(?=\n## |\n# |\Z)",
        re.DOTALL,
    )
    case_section = case_section_pattern.search(body)
    step_markers_found = 0

    if case_section:
        case_text = case_section.group(0)
        step_pattern = re.compile(
            r"(?:Step\s*[A-Za-z0-9]|步骤\s*[一二三四五六七八九十\d]|第[一二三四五六七八九十\d]+步|"
            r"\*\*Step\s|[①-⑩]|【\d+】)",
        )
        step_markers_found = len(step_pattern.findall(case_text))
        has_verification = bool(re.search(
            r"(?:整改后|验证|复测|测量结果|裕量|通过|合格|✅)",
            case_text,
        ))
        if not has_verification:
            results.append((
                "WARN", "SpDepthCasesIncomplete",
                f"[{label}] 实操案例缺少定量验证：未找到整改后/验证/复测/裕量等验证关键词。"
                f"请补充「给定参数→分步操作→定量验证」三段式完整案例",
            ))
    else:
        results.append((
            "WARN", "SpDepthCasesMissing",
            f"[{label}] 未找到实操案例章节：缺少 typical_practical_cases 内容。"
            f"请补充至少1个完整实操案例（含参数+分步操作+定量验证）",
        ))

    if case_section and step_markers_found < 3:
        results.append((
            "WARN", "SpDepthCasesSteps",
            f"[{label}] 实操案例分步操作不足：检测到 {step_markers_found} 个分步标记（建议 ≥3 步）。"
            f"请扩充案例的操作步骤细节",
        ))

    return results
