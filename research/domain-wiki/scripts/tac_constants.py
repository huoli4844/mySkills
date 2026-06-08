"""tac_constants.py — 模板组装核心常量与配置 (v42.0 从 template_assembler.py 拆分)

包含:
  - DEFINITION_MARKERS: 定义标记词列表
  - CONFIDENCE_LEVELS: 置信度5级表
  - REQUIRED_FRONTMATTER: Front Matter 必填字段表
  - TYPE_QUALITY_CHECKS: 类型级质量清单
  - verify_definition(): 核心概念定义验证
"""

import os
import re
import sys

from log_utils import get_logger

log = get_logger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


# ── 统一定义标记词（P21 fix: 三处验证共用此列表）──
DEFINITION_MARKERS = [
    "是指",
    "一般指",
    "简称为",
    "也称为",
    "又可称为",
    "这就是",
    "即 ",
    "指的就是",
    "定义为",
    "是指一种",
    "称为",
    "叫",
    "成为",
    "是",
    "指",
    "方程为",
    "模型为",
    "定义为",
    "可表示为",
    "表示为",
    "其中",
    "分为",
    "条件为",
    "定义为",
    "取决于",
]
# 按长度降序排列，优先匹配长词
DEFINITION_MARKERS_SORTED = sorted(DEFINITION_MARKERS, key=len, reverse=True)


# ── 定义验证 ──────────────────────────────────────────────


def verify_definition(definition: str, concept_name: str, source_file: str = "") -> bool:
    """验证核心概念定义的完整性和正确性。

    检查项：
    1. 非空（拒空字符串和纯空白）
    2. 包含至少一个定义标记词（是指/称为/即/这就是/也称为/简称为/叫/成为）
    3. 定义可在出处正文中检索到（前80字符在 source_text 中存在，去除图片标记）

    返回 True=验证通过，False=验证失败
    """
    stripped = definition.strip()
    # 1. 非空检查
    if not stripped:
        log.error(f"  ❌ {concept_name}: 定义为空！禁止生成概念文件")
        return False

    # 2. 定义标记词检查（使用统一定义标记词列表）
    markers_sorted = DEFINITION_MARKERS_SORTED
    has_marker = False
    matched_marker = ""
    for m in markers_sorted:
        if m in stripped:
            has_marker = True
            matched_marker = m
            break
    if not has_marker:
        log.error(f"  ❌ {concept_name}: 定义中无定义标记词，可能不是有效定义")
        return False
    else:
        log.success(f"  ✅ {concept_name}: 含标记词「{matched_marker}」")

    # 3. 出处可检索性检查
    if source_file and os.path.exists(source_file):
        with open(source_file, encoding="utf-8") as f:
            source_text = f.read()

        def normalize(text):
            text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # 去图片
            text = re.sub(r"\s+", " ", text).strip()  # 空白归一
            return text

        verify_text = normalize(stripped[:120])
        src_normalized = normalize(source_text)

        if verify_text in src_normalized:
            log.success(f"  ✅ {concept_name}: 精准释义可检索（含标记词）")
        else:
            verify_plain = re.sub(r'[，。、；：""\u2018\u2019！（）：？\s]', "", verify_text)
            src_plain = re.sub(r'[，。、；：""\u2018\u2019！（）：？\s]', "", src_normalized)
            if verify_plain in src_plain:
                log.warning(f"  ⚠️  {concept_name}: 去标点后匹配成功，定义基本一致")
            else:
                log.error(f"  ❌ {concept_name}: 精准释义在出处中不可检索！可尝试放宽 source_file 或手动核验")
                return False
    else:
        log.warning(f"  ⚠️  {concept_name}: 无 source_file，跳过出处检索验证")

    return True


# ── 置信度5级表（v37.0 五大类模板归并）─────────────────────
# 按模板类别定义允许的置信度值，写前校验防止错误的置信度进入文件
CONFIDENCE_LEVELS = {
    # ── 概念类（concept + knowledge-element + entity 归并）──
    "concept_template.md": {0.95},  # 核心概念：精准释义逐字匹配出处
    "concept/ke": {0.85},  # 知识要素（概念类子类型）
    "concept/entity": {0.85},  # 实体（概念类子类型）
    # ── 知识类 ──
    "knowledge_template.md": {0.85},  # 知识点：基于正文归纳
    # ── 技能类 ──
    "skill_template.md": {0.75},  # 技能点：操作步骤来自原文
    # ── 场景类 ──
    "scenario_template.md": {0.65},  # 场景：基于教材案例
    # ── 评测类（exercise + solution 归并）──
    "eval/exercise": {0.65},  # 习题
    "eval/solution": {0.65, 0.85},  # 解答：骨架0.65，Agent填充后0.85
}
# 所有模板必须注册（走 assemble_md 的必经之路，防止遗漏）
ALLOWED_TEMPLATES = set(CONFIDENCE_LEVELS.keys())

# ── Front Matter 必填字段表 ──────────────────────────────────
# 每类节点写前必须包含的字段（模板各自的特有字段由 template 定义，这里只保证最低要求）
REQUIRED_FRONTMATTER = {
    "concept_template.md": {"name", "type", "confidence"},
    "concept/ke": {"name", "type", "confidence"},
    "concept/entity": {"name", "type", "confidence"},
    "knowledge_template.md": {"name", "type", "confidence"},
    "skill_template.md": {"name", "type", "confidence"},
    "scenario_template.md": {"name", "type", "confidence"},
    "eval/exercise": {"name", "type", "confidence"},
    "eval/solution": {"name", "type", "confidence"},
}


# ── 类型级质量清单（v37.0 五大类模板归并）─────────────────
# 每种节点文件生成后应通过的质量检查项
# "critical"=必须通过才能标记 done；"warning"=告警但可继续
TYPE_QUALITY_CHECKS = {
    # ── 概念类：核心概念 ──
    "concept_template.md": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在且完整（--- ... ---）"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_concept", "type 必须为 concept"),
        ("critical", "has_confidence_095", "confidence 必须为 0.95"),
        ("critical", "has_definition", "必须有 > 开头的精准释义"),
        ("critical", "has_marker_word", "精准释义必须含定义标记词（是指/称为/即/是）"),
        (
            "critical",
            "has_source_retrieval",
            "【根源要求】定义前120字必须在正文(20_正文/)中可检索到！否则 confidence=0.95 无效",
        ),
        ("critical", "has_source_citation", "精准释义必须标注来源（> 来源：第X章 §X.X）"),
        ("critical", "has_formula_citation", "如有公式引用，下方必须标注 > 来源：..."),
        ("critical", "has_figure_citation", "如有图引用，下方必须标注 > 来源：..."),
        ("warning", "additional_explanations", "建议从正文提取更多解释性段落（含来源标注）"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
        ("warning", "mermaid_valid", "Mermaid 代码块语法正确"),
    ],
    # ── 概念类：知识要素（concept/ke 子类型）──
    "concept/ke": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_ke", "type 必须为 knowledge-element"),
        ("critical", "has_confidence_085", "confidence 必须为 0.85"),
        ("warning", "has_content", "正文内容非空"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 概念类：实体（concept/entity 子类型）──
    "concept/entity": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_entity", "type 必须为 entity"),
        ("critical", "has_confidence_085", "confidence 必须为 0.85"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 知识类 ──
    "knowledge_template.md": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_knowledge", "type 必须为 knowledge"),
        ("critical", "has_confidence_085", "confidence 必须为 0.85"),
        ("critical", "has_mermaid_flow", "必须有 Mermaid 推导流程图"),
        ("critical", "has_analysis_text", "必须有文字解析段"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 技能类 ──
    "skill_template.md": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_skill", "type 必须为 skill"),
        ("critical", "has_confidence_075", "confidence 必须为 0.75"),
        ("critical", "has_mermaid_flow", "必须有 Mermaid 操作流程图"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 场景类 ──
    "scenario_template.md": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_scenario", "type 必须为 scenario"),
        ("critical", "has_confidence_065", "confidence 必须为 0.65"),
        ("critical", "has_boundary", "必须有边界条件"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 评测类：习题 ──
    "eval/exercise": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_exercise", "type 必须为 exercise"),
        ("critical", "has_confidence_065", "confidence 必须为 0.65"),
        ("critical", "has_question", "必须有题目内容"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
    # ── 评测类：解答 ──
    "eval/solution": [
        ("critical", "has_frontmatter", "FrontMatter 必须存在"),
        ("critical", "has_name", "必须有 name 字段"),
        ("critical", "has_type_solution", "type 必须为 solution"),
        ("critical", "has_confidence_065", "confidence 必须为 0.65"),
        ("critical", "has_answer", "必须有参考答案"),
        ("critical", "has_mermaid", "必须有 Mermaid 解题流程或知识闭环图"),
        ("critical", "has_analysis", "必须有文字解析段"),
        ("warning", "no_placeholder", "无 {{placeholder}} 残留"),
    ],
}
