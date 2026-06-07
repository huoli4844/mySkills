#!/usr/bin/env python3
"""JSON → MD template assembler: reads JSON items → fills template → writes .md files
v45.1-todo: 1008行，建议拆分为:
  - template_assembler.py（公共入口+类型定义，~200行）
  - template_fillers.py（字段填充逻辑，~500行）
  - template_writers.py（文件写入+验证，~308行）
"""

import json
import os
import re
import sys

from dag_constants import PipelineError
from log_utils import get_logger

log = get_logger(__name__)


sys.dont_write_bytecode = True

# ── v42.0: 核心函数（从 template_assembler.py 合并） ──

# 从 dag_controller 导入中心化路径注册表
_tac_dir = os.path.dirname(os.path.abspath(__file__))
if _tac_dir not in sys.path:
    sys.path.insert(0, _tac_dir)

# v38.0: 统一解析工具（消除重复 FM 解析/占位符检测）
from parse_utils import (  # noqa: E402
    parse_frontmatter as _parse_fm,
)
from parse_utils import (  # noqa: E402
    safe_filename,
)

# ── 从 tac_constants re-export ──
from tac_constants import (  # noqa: E402, F401
    ALLOWED_TEMPLATES,
    CONFIDENCE_LEVELS,
    DEFINITION_MARKERS,
    DEFINITION_MARKERS_SORTED,
    REQUIRED_FRONTMATTER,
    TYPE_QUALITY_CHECKS,
    verify_definition,
)

# ── 从 tac_quality re-export ──
from tac_quality import (  # noqa: E402, F401
    _CHECK_HANDLERS,
    _register_check,
    comprehensive_content_check,
    run_type_quality_checks,
    validate_frontmatter,
)

# ── 模板加载与解析 ──────────────────────────────────────────


def load_template(template_name: str) -> str:
    """从 assets/templates/ 加载模板文件（完整内容，含Front Matter）"""
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(skill_root, "assets", "templates", template_name)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    with open(template_path, encoding="utf-8") as f:
        return f.read()


def parse_template(template_content: str) -> dict:
    """解析模板，分离Front Matter和Body

    返回：
        {
            'front_matter': {...},  # 解析后的YAML（字典）
            'body_template': str,       # Body部分的模板（含占位符）
            'raw_front_matter': str     # Front Matter原始文本（用于替换）
        }
    """
    if not template_content.startswith("---"):
        raise ValueError("模板必须包含Front Matter（以---开头）")

    parts = template_content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("模板格式错误：无法分割Front Matter和Body")

    raw_fm = parts[1].strip()
    body_template = parts[2].strip()

    # v38.0: 委托 parse_utils 统一解析 frontmatter
    fm_dict = _parse_fm("---" + "\n" + raw_fm + "\n" + "---")

    return {"front_matter": fm_dict, "body_template": body_template, "raw_front_matter": raw_fm}


def fill_template(body_template: str, replacements: dict) -> str:
    """替换模板Body上的占位符（格式：{{key}}），并清理 Jinja2 条件句

    v39.1: 自动展开 YAML 多行字符串中的 \\n 字面量为实际换行符
    """
    result = body_template
    for key, value in replacements.items():
        placeholder = "{{" + key + "}}"
        # v39.1: 展开 YAML \\n 字面量为实际换行（不影响 LaTeX \\nabla 等）
        val_str = str(value)
        if "\\n" in val_str:
            # 仅替换独立的 \\n（后面不跟字母/数字，避免破坏 LaTeX 命令如 \\nabla）
            val_str = re.sub(r"\\n(?![a-zA-Z])", "\n", val_str)
        result = result.replace(placeholder, val_str)
    # Clean up Jinja2 conditionals (strip them WITHOUT evaluating — LIMITATION!)
    # WARNING: fill_template() does NOT evaluate Jinja2 conditions. {% if %} and
    # {% endif %} are simply removed and the content between them always renders.
    # Do NOT add {% if %} to templates unless you implement proper Jinja2 evaluation.
    if re.search(r"\{%[- ]+(if|endif|for|raw|end)", result):
        matches = re.findall(r"\{%[- ]+[^%]+%\}", result)
        log.warning(f"  ⚠️  WARNING: {len(matches)} Jinja2 blocks STRIPPED (not evaluated). "
            f"All conditional content will always render regardless of conditions.")
    result = re.sub(r"\{%[- ]+if[^%]+%\}", "", result)
    result = re.sub(r"\{%[- ]+endif[^%]*%\}", "", result)
    # Warn about unmatched template placeholders
    unmatched = re.findall(r"\{\{[a-z_][a-z0-9_]*\|\|[a-z_][a-z0-9_]*\}\}", result)
    unmatched += re.findall(r"\{\{[a-z_][a-z0-9_]*\}\}", result)
    if unmatched:
        uniq = sorted(set(unmatched))
        log.info(f"  WARNING: {len(uniq)} template placeholders missing from body_replacements: {', '.join(uniq[:6])}")
    # v50.0: 去除 HTML 注释（模板中的Agent提示，不输出到文件）
    result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)
    return result


def _strip_wu_sections(body: str) -> str:
    """C2: 删除内容恰好为'无'或'无。'的 ### / #### 子节"""
    import re as _re

    pattern = _re.compile(r"^#{3,4}\s+[^\n]+\n\s*(?:无[。]?)\s*\n?", _re.MULTILINE)
    stripped = pattern.sub("", body)
    # Also remove trailing blank lines at end
    stripped = _re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped


# ── 占位符残留检查 ───────────────────────────────────────────

# P8 fix: （暂无）是故意填写的空节标记，不是占位符（见 SKILL.md 坑 #14）
PLACEHOLDER_PATTERN = re.compile(r"\{\{[^}]+\}\}|（待补充）")


def check_placeholders(content: str, filename: str) -> int:
    """检查组装后的内容中是否存在未替换的 {{placeholder}}，返回残留数"""
    matches = PLACEHOLDER_PATTERN.findall(content)
    if matches:
        log.warning(f"  ⚠️  {filename}: {len(matches)} 个占位符残留 — {', '.join(matches[:8])}")
    return len(matches)


MERMAID_INIT = '%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}%%'


def add_mermaid_init(content: str) -> str:
    """自动为所有 ```mermaid 代码块添加 %%{init} 紧凑配置（若无）"""

    def _add_init(m):
        block = m.group(0)
        # 跳过已有 %%{ 配置的块
        if "%%{" in block:
            return block
        # 在第一行 ```mermaid 之后插入 init 配置行
        lines = block.split("\n")
        if len(lines) >= 1:
            # 插入在 ```mermaid 之后的第一行
            lines.insert(1, MERMAID_INIT)
        return "\n".join(lines)

    return re.sub(r"```mermaid\n.*?```", _add_init, content, flags=re.DOTALL)


def _wrap_mermaid_fields(content: str) -> str:
    """v43.8: 区域保护模式 — 先保护所有已包裹块，再处理裸露内容，最后统一规范化。

    杜绝 v43.7 的二次包裹 bug：_wrap_unwrapped 会把已包裹块内部的 graph
    行再次匹配，导致嵌套 ```mermaid``` fences。

    流程：
      1. 提取所有 ```mermaid...``` 块 → 替换为占位符
      2. 对非 mermaid 区域包裹裸露的 mermaid 内容
      3. 归一化所有被保护的块（strip → add init → re-wrap）
      4. 最后防线：修复块内误吞的标题
    """
    # 已知的 Mermaid 内容字段（模板中被替换后的值以这些关键词开头）
    MERMAID_KEYWORDS = (
        "flowchart ",
        "graph ",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
    )

    def _normalize_block(block: str) -> str:
        """归一化 mermaid 块：剥去旧 fences → add init → 重新包裹"""
        inner = re.sub(r"^```mermaid\s*\n", "", block)
        inner = re.sub(r"\n```\s*$", "", inner)
        inner = inner.strip()
        if inner in ("无", "无。", "", None):
            return "无"
        inner = inner.replace("→", ">")
        # v43.18: 强制替换旧 %%{init} 为正确格式（双引号 JSON + }%% 闭合）
        inner = re.sub(r'^%%\{init:.*?\n?', '', inner, flags=re.DOTALL)
        inner = MERMAID_INIT + "\n" + inner
        return "```mermaid\n" + inner + "\n```"

    def _wrap_unwrapped(match):
        inner = match.group(0).strip()
        if inner in ("无", "无。", "", None):
            return inner
        inner = inner.replace("→", ">")
        inner_with_init = MERMAID_INIT + "\n" + inner if not inner.startswith("%%{") else inner
        return "```mermaid\n" + inner_with_init + "\n```"

    # ── Step 1: 保护所有已包裹的 ```mermaid...``` 块 ──
    placeholders = {}
    ph_counter = [0]

    def _protect(m):
        key = f"__MERMAID_P{ph_counter[0]}__"
        ph_counter[0] += 1
        placeholders[key] = m.group(0)
        return "\n" + key + "\n"

    content = re.sub(r"```mermaid\n.*?\n```\s*", _protect, content, flags=re.DOTALL)

    # ── Step 2: 对非 mermaid 区域包裹裸露内容 ──
    for kw in MERMAID_KEYWORDS:
        content = re.sub(
            rf"(?<!```)\n({kw}[^\n]+(?:\n[ \t]+[^\n]+)*)",
            lambda m: "\n" + _wrap_unwrapped(m),
            content,
        )

    # ── Step 3: 归一化所有被保护的 mermaid 块 ──
    for key, block in placeholders.items():
        content = content.replace(key, _normalize_block(block))

    # ── Step 4: 最后防线 ──
    content = _fix_mermaid_block_boundaries(content)

    return content


def _fix_mermaid_block_boundaries(content: str) -> str:
    """v35.2: 最后防线 — 修复 Mermaid 块内误包含的 Markdown 标题。

    如果 ```mermaid...``` 块内出现了 ### 或 ## 标题行，说明闭合 ``` 放错了位置，
    在这些标题前插入闭合 ```，在标题后重新打开 ```mermaid...``` 块。
    """

    def _fix_one_block(match):
        block = match.group(0)
        # 提取块内容（去掉 ```mermaid 和最后的 ```）
        inner_match = re.match(r"```mermaid\n(.*?)\n```\s*$", block, re.DOTALL)
        if not inner_match:
            return block
        inner = inner_match.group(1)
        # 查找第一个 ### 或 ## 标题
        heading_match = re.search(r"\n(#{2,3}\s+[^\n]+)", inner)
        if not heading_match:
            return block  # 无标题，正常

        pos = heading_match.start()
        heading_line = heading_match.group(1)
        # 在标题前闭合 Mermaid 块
        before = inner[:pos]
        after = inner[pos:]
        return "```mermaid\n" + before.rstrip() + "\n```\n\n" + heading_line + "\n" + after[len(heading_line) :].strip()

    return re.sub(r"```mermaid\n.*?\n```\s*", _fix_one_block, content, flags=re.DOTALL)


# ── 文件名安全化 ─────────────────────────────────────────────

# safe_filename 已从 parse_utils 导入（v38.0 统一）
# 保留别名供外部引用
safe_filename = safe_filename

# =====================================================================
# v50.7: 文件写入 + 索引渲染 + CLI 已拆分到 template_writers.py
# 向后兼容的 re-export 在文件末尾（避免循环导入）


def C(*a, **kw):
    return {
        "t": a[0],
        "v": a[1],
        "p": a[2],
        "i": a[3],
        "g": a[4],
        "c": a[5],
        "n": a[6],
        "x": kw.get("x", []),
        "y": kw.get("y", []),
        "cn": kw.get("cn", ""),
    }

ASSEMBLER_CONFIG = {
    # fields: (tmpl, ver, type_val, id, tags, conf, (ns,nl,ni), extra_fm, extra_bd)
    "concept": C(
        "concept_template.md",
        "v6.1",
        ("override_type", "concept"),
        "concept_id",
        ["概念"],
        0.95,
        (1, 1, 1),
        cn="定义可从原文逐字匹配，经人工复核",
        x=[
            "concept_type::定义",
            "concept_level::核心",
            "bloom_level::理解",
            "definition_source",
            "additional_explanations",
            "formula_references",
            "figure_references",
            "core_concept_map_source",
            "features::无",
            "structure::无",
            "prerequisites::无",
            "factors::无",
            "related_knowledge::无",
            "confusion_compare::无",
            "domain::无",
            "classification::无",
            "boundary::无",
            "application_scenarios::无",
            "value::无",
            "upstream_downstream::无",
            "evolution::无",
            "key_parameters::无",
            "common_misconceptions::无",
            "references::无",
            "related_knowledge_elements::无",
            "related_toc::无",
            "source::无",
            "term_definition::无",
            "core_concept_map::无",
            "core_concept_map_analysis::无",
            "mathematical_model::无",
            "tech_classification::无",
            "typical_systems::无",
            "related_concepts_relations::无",
            "engineering_practices::无",
            "confidence_note::精准释义逐字匹配出处原文",
        ],
        y=[
            "definition_sentence:definition",
            "term_english",
            "term_definition",
            "definition_source",
            "additional_explanations",
            "formula_references",
            "figure_references",
            "core_concept_map",
            "core_concept_map_source",
            "core_concept_map_analysis",
            "structure",
            "mathematical_model",
            "tech_classification",
            "application_scenarios",
            "typical_systems",
            "related_concepts_relations",
            "confusion_compare",
            "evolution",
            "engineering_practices",
            "common_misconceptions",
            "references",
            "related_knowledge_elements",
            "source",
            "concept_type",
            "concept_level",
            "bloom_level",
            "features",
            "prerequisites",
            "factors",
            "related_knowledge",
            "domain",
            "classification",
            "boundary",
            "value",
            "upstream_downstream",
            "key_parameters",
            "related_toc",
        ],
    ),
    "knowledge": C(
        "knowledge_template.md",
        "v5.0",
        ("_S", "knowledge"),
        "knowledge_id",
        ["知识点"],
        0.85,
        (1, 1, 1),
        cn="内容基于正文归纳，关键结论可溯源",
        x=[
            "knowledge_level::核心",
            "bloom_level::理解",
            "difficulty::中",
            "content_core",
            "content_significance::无",
            "content_difficulties::无",
            "prerequisites::无",
            "follow_ups::无",
            "examples::无",
            "referenced_concepts::无",
            "learning_objectives::无",
            "domain::无",
            "theoretical_basis::无",
            "key_details::无",
            "application_scenarios::无",
            "application_methods::无",
            "typical_examples::无",
            "common_exam_points::无",
            "exam_questions::无",
            "exam_point_analysis::无",
            "related_concepts::无",
            "related_knowledge_elements::无",
            "prerequisite_knowledge::无",
            "supported_skills_scenarios::无",
            "confusion_compare_table::无",
            "derivation_diagram::无",
            "derivation_analysis::无",
            "core_knowledge_elements_table::无",
            "knowledge_context_diagram::无",
            "diagram_analysis::无",
        ],
        y=[
            "content_core",
            "learning_objectives::无",
            "domain::无",
            "theoretical_basis::无",
            "key_details::无",
            "derivation_diagram::无",
            "derivation_analysis::无",
            "core_knowledge_elements_table::无",
            "application_scenarios::无",
            "application_methods::无",
            "typical_examples::无",
            "common_exam_points::无",
            "exam_questions::无",
            "exam_point_analysis::无",
            "related_concepts::无",
            "related_knowledge_elements::无",
            "prerequisite_knowledge::无",
            "supported_skills_scenarios::无",
            "confusion_compare_table::无",
            "knowledge_context_diagram::无",
            "diagram_analysis::无",
        ],
    ),
    "skill": C(
        "skill_template.md",
        "v5.0",
        ("_S", "skill"),
        "skill_id",
        ["技能点"],
        0.75,
        (1, 1, 1),
        cn="操作步骤来自原文或教材标准流程",
        x=[
            "skill_level::L1",
            "bloom_level::应用",
            "difficulty::中",
            "skill_description",
            "skill_steps::无",
            "standard_pass::无",
            "capability_standard::无",
            "key_techniques::无",
            "common_tools::无",
            "precautions::无",
            "related_concepts::无",
            "related_knowledge::无",
            "application_scenarios::无",
            "typical_cases::无",
            "confusion_compare_table::无",
            "operation_diagram::无",
            "operation_analysis::无",
            "knowledge_elements::无",
            "evolution",
            "references::无",
            "skill_objectives::通过本技能学习达到以下能力",
            "domain::（待指定）",
            "core_operation::无",
            "competency_standards::无",
            "operation_boundaries::无",
            "core_theoretical_support::无",
            "tool_support::无",
            "prerequisite_skills::无",
            "applicable_scenarios::无",
            "operation_flowchart::无",
            "operation_flow_analysis::无",
            "typical_practical_cases::无",
            "related_concepts_knowledge::无",
            "supported_scenarios::无",
            "extended_skills::无",
            "confusion_skill_compare::无",
            "knowledge_context_diagram::无",
            "diagram_analysis::无",
        ],
        y=[
            "skill_description",
            "skill_steps::无",
            "standard_pass::无",
            "capability_standard::无",
            "key_techniques::无",
            "common_tools::无",
            "precautions::无",
            "related_concepts::无",
            "related_knowledge::无",
            "application_scenarios::无",
            "typical_cases::无",
            "confusion_compare_table::无",
            "operation_diagram::无",
            "operation_analysis::无",
            "knowledge_elements::无",
            "evolution::无",
            "references::无",
            "skill_objectives::通过本技能学习达到以下能力",
            "domain::（待指定）",
            "core_operation::无",
            "competency_standards::无",
            "operation_boundaries::无",
            "core_theoretical_support::无",
            "tool_support::无",
            "prerequisite_skills::无",
            "applicable_scenarios::无",
            "operation_flowchart::无",
            "operation_flow_analysis::无",
            "typical_practical_cases::无",
            "related_concepts_knowledge::无",
            "supported_scenarios::无",
            "extended_skills::无",
            "confusion_skill_compare::无",
            "knowledge_context_diagram::无",
            "diagram_analysis::无",
        ],
    ),
    "scenario": C(
        "scenario_template.md",
        "v5.0",
        ("_S", "scenario"),
        "scenario_id",
        ["应用场景"],
        0.65,
        (1, 1, 1),
        cn="场景基于教材案例或实际工程经验构建",
        x=[
            "scenario_level::L1",
            "bloom_level::应用",
            "difficulty::中",
            "scenario_description",
            "typical_workflow::无",
            "workflow_diagram::无",
            "diagram_analysis::无",
            "context_diagram::无",
            "context_analysis::无",
            "boundary_conditions::无",
            "prerequisites::无",
            "key_techniques::无",
            "common_tools::无",
            "success_criteria::无",
            "common_pitfalls::无",
            "related_concepts::无",
            "related_knowledge::无",
            "related_skills::无",
            "references::无",
            "scenario_type::产品认证",
            "domain::（待指定）",
            "scene_elements::无",
            "constraints::无",
            "technical_environment::无",
            "core_knowledge_support::无",
            "core_skill_support::无",
            "confusion_scenario_compare::无",
            "evolution::无",
        ],
        y=[
            "scenario_description",
            "typical_workflow::无",
            "workflow_diagram::无",
            "diagram_analysis::无",
            "context_diagram::无",
            "context_analysis::无",
            "boundary_conditions::无",
            "prerequisites::无",
            "key_techniques::无",
            "common_tools::无",
            "success_criteria::无",
            "common_pitfalls::无",
            "related_concepts::无",
            "related_knowledge::无",
            "related_skills::无",
            "references::无",
            "scenario_type::产品认证",
            "domain::（待指定）",
            "scene_elements::无",
            "constraints::无",
            "technical_environment::无",
            "core_knowledge_support::无",
            "core_skill_support::无",
            "confusion_scenario_compare::无",
            "evolution::无",
            "scene_concept_support::无",
            "scene_ke_support::无",
            "workflow_analysis::无",
            "typical_application_cases::无",
            "related_scenes::无",
            "knowledge_context_diagram::无",
        ],
    ),
    "entity": C(
        "concept_template.md",
        "v6.1",
        ("_S", "entity"),
        "entity_id",
        ["实体"],
        0.85,
        (1, 0, 1),
        cn="事实信息可溯源",
        x=[
            "entity_type::设备",
            "category::无",
            "specifications::无",
            "features::无",
            "application_scenarios::无",
            "references::无",
        ],
        y=[
            "entity_type::设备",
            "category::无",
            "specifications::无",
            "features::无",
            "application_scenarios::无",
            "references::无",
            "description::无",
            "related_concepts::无",
        ],
    ),
    "knowledge-element": C(
        "concept_template.md",
        "v6.1",
        ("_S", "knowledge-element"),
        "ke_id",
        ["知识要素"],
        0.85,
        (1, 0, 1),
        cn="基于正文内容归纳生成",
        x=[
            "domain::无",
            "classification::无",
            "structure::无",
            "key_parameters::无",
            "features::无",
            "application_scenarios::无",
            "value::无",
            "upstream_downstream::无",
            "related_knowledge_elements::无",
            "references::无",
            "source::无",
        ],
        y=[
            "definition::无",
            "domain::无",
            "classification::无",
            "structure::无",
            "key_parameters::无",
            "features::无",
            "application_scenarios::无",
            "value::无",
            "upstream_downstream::无",
            "related_knowledge_elements::无",
            "references::无",
            "source::无",
        ],
    ),
    "exercise": C(
        "exercise_template.md",
        "v6.1",
        ("_S", "exercise"),
        "exercise_id",
        ["习题"],
        0.65,
        (1, 0, 1),
        cn="自动检测+解答wikilink",
        x=[
            "exercise_type::问答题",
            "difficulty::中",
            "source_file",
            "related_concepts",
            "related_knowledge_elements::无",
            "answer::无",
        ],
        y=[
            "exercise_type::问答题",
            "difficulty::中",
            "source_file::无",
            "related_concepts::无",
            "related_knowledge_elements::无",
            "related_answer::无",
        ],
    ),
    "solution": C(
        "eval_template.md",
        "v6.1",
        ("_S", "solution"),
        "solution_id",
        ["习题解答"],
        0.65,
        (1, 0, 1),
        cn="自动检测+解答wikilink",
        x=[
            "question::无",
            "exam_point_analysis::无",
            "difficulty_analysis::无",
            "problem_solving_flowchart::无",
            "problem_solving_analysis::无",
            "knowledge_closed_loop::无",
            "closed_loop_analysis::无",
            "references::无",
            "exercise_link::无",
            "exercise_name::无",
        ],
        y=[
            "question::无",
            "answer::无",
            "exam_point_analysis::无",
            "difficulty_analysis::无",
            "problem_solving_flowchart::无",
            "problem_solving_analysis::无",
            "knowledge_closed_loop::无",
            "closed_loop_analysis::无",
            "references::无",
            "exercise_link::无",
            "exercise_name::无",
        ],
    ),
    # v43.14: 索引类型 — 生成 L2/L3/L4 索引文件。每个 item 用 wikilink 渲染为列表项
    "index": C(
        "concept_index.md",
        "v3.0",
        ("override_type", "index"),
        "id",
        ["索引"],
        0.95,
        (1, 0, 0),  # name_only, not long, not id_based
        cn="自动索引",
        x=[
            "total_count",
            "index_type",
        ],
        y=[
            "items_table",
        ],
    ),
    # v43.14: 书总揽类型 — 生成 L2 book_overview 文件
    "book_overview": C(
        "book_overview.md",
        "v3.0",
        ("override_type", "book_overview"),
        "book_id",
        ["总揽"],
        0.95,
        (1, 0, 0),
        cn="自动总揽",
        x=[
            "book_name",
            "domain",
            "stats",
            "chain_connectivity",
            "graph_quality",
            "top_nodes",
            "mindmap_content",
            "chapter_distribution",
            "learning_path",
        ],
        y=[
            "book_name",
            "stats",
            "chain_connectivity",
            "node_connectivity",
            "graph_quality",
            "top_nodes",
            "mindmap_content",
            "chapter_distribution",
            "learning_path",
        ],
    ),
}

# ── NODE_CONFIG: 类型名 → ASSEMBLER_CONFIG 映射（取代逐个薄函数） ──
# 调用方直接使用: assemble_by_config(NODE_CONFIG['knowledge'], **kwargs)
NODE_CONFIG = {
    "concept": ASSEMBLER_CONFIG["concept"],
    "knowledge": ASSEMBLER_CONFIG["knowledge"],
    "skill": ASSEMBLER_CONFIG["skill"],
    "scenario": ASSEMBLER_CONFIG["scenario"],
    "ke": ASSEMBLER_CONFIG["knowledge-element"],
    "entity": ASSEMBLER_CONFIG["entity"],
    "exercise": ASSEMBLER_CONFIG["exercise"],
    "solution": ASSEMBLER_CONFIG["solution"],
    "index": ASSEMBLER_CONFIG["index"],
    "book_overview": ASSEMBLER_CONFIG["book_overview"],
}

# Standard frontmatter fields
_STD_FM = [
    "template_version",
    "type",
    "type_tags",
    "name",
    "book_id",
    "book_name",
    "chapter_num",
    "id_field",
    "confidence",
    "confidence_note",
    "source_chapter",
    "source_page",
    "source_from",
    "reviewer",
    "review_date",
    "aliases",
    "tags",
]

# Standard body fields
_STD_BD = [
    "name",
    "id_field",
    "source_chapter",
    "source_page",
    "source_from",
    "book_id",
    "book_name",
    "chapter_num",
    "reviewer",
    "review_date",
]


def _f(s):
    """Parse field spec: 'key'→(k,k,'') or 'key:src'→(k,src,'') or 'key::default'→(k,k,default)"""
    if "::" in s:
        k, d = s.split("::", 1)
        return (k, k, d)
    if ":" in s:
        k, src = s.split(":", 1)
        return (k, src, "")
    return (s, s, "")


def _v(cfg, k, kwargs):
    """Get value from kwargs or config default"""
    return kwargs.get(k, cfg.get(k, ""))


def _fn(v):
    """Safe filename from concept/entity name"""
    safe = re.sub(r"[\\\\/:*?\"<>|]", "_", str(v))
    safe = safe.replace(" ", "_")
    return safe[:128]


# ---------------------------------------------------------------------------
# 组装入口
# ---------------------------------------------------------------------------
def assemble_by_config(config, **kwargs):
    """通用组装函数：读取JSON数据 → 组装所有items → 写入文件"""

    c = config["t"]  # template name
    tmpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "templates", c)
    if not os.path.exists(tmpl_path):
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "templates", c)
        if os.path.exists(alt):
            tmpl_path = alt

    with open(tmpl_path, encoding="utf-8") as f:
        template = f.read()

    items = kwargs.get("items", [])
    res = []
    for idx, item in enumerate(items):
        try:
            out = _assemble_one(config, template, item, kwargs, idx)
            res.append(out)
        except Exception as e:
            log.error(f"  ❌ {item.get('name','?')}: 生成失败 — {e}")
    return res


def _assemble_one(config, template, item, kwargs, idx):
    """Assemble a single item"""
    import datetime

    ver = config["v"]
    type_val = config["p"]
    id_field = config["i"]
    tag_list = config["g"]
    conf_default = config["c"]
    (name_only, is_long, is_id_based) = config["n"]
    extra_fm = config.get("x", [])
    extra_bd = config.get("y", [])
    cn = config.get("cn", "")

    # Build frontmatter
    fm = {}
    for s in _STD_FM:
        if s == "template_version":
            fm[s] = ver
        elif s == "type":
            if (isinstance(type_val, tuple) and type_val[0] == "override_type") or (isinstance(type_val, tuple) and type_val[0] == "_S"):
                fm[s] = type_val[1]
            else:
                fm[s] = type_val
        elif s == "type_tags":
            fm[s] = json.dumps(tag_list, ensure_ascii=False)
        elif s == "name":
            fm[s] = item.get("name", "")
        elif s == "book_id":
            fm[s] = kwargs.get("book_id", "")
        elif s == "book_name":
            fm[s] = kwargs.get("book_name", "")
        elif s == "chapter_num":
            fm[s] = str(kwargs.get("chapter_num", ""))
        elif s == "id_field":
            if is_id_based:
                fm[s] = item.get(id_field, f"{id_field}_{idx:03d}")
            else:
                fm[s] = f"{id_field}_{idx:03d}"
        elif s == "confidence":
            fm[s] = float(item.get("confidence", conf_default))
        elif s == "confidence_note":
            fm[s] = item.get("confidence_note", cn)
        elif s == "source_chapter":
            fm[s] = item.get("source_chapter", "")
        elif s == "source_page":
            fm[s] = item.get("source_page", "")
        elif s == "source_from":
            fm[s] = item.get("source_from", "")
        elif s == "reviewer":
            fm[s] = item.get("reviewer", "系统自动")
        elif s == "review_date":
            fm[s] = item.get("review_date", datetime.date.today().isoformat())
        elif s == "aliases":
            fm[s] = json.dumps(item.get("aliases", []), ensure_ascii=False)
        elif s == "tags":
            fm[s] = json.dumps(item.get("tags", []), ensure_ascii=False)

    # Extra frontmatter fields
    for s in extra_fm:
        if isinstance(s, tuple):
            if s[0] == "_S":
                fm[s[1]] = s[2]
            elif s[0] == "_D":
                fm[s[1]] = datetime.datetime.now().strftime(s[2])
            continue
        k, src, d = _f(s)
        v = item.get(src, d)
        if v == "" and d != "":
            v = d
        fm[k] = v

    # Build body data
    bd = {}
    for s in _STD_BD:
        if s == "name":
            bd["name"] = item.get("name", "")
        elif s == "id_field":
            bd["id_field"] = item.get(id_field, f"{id_field}_{idx:03d}")
        elif s == "book_id":
            bd["book_id"] = kwargs.get("book_id", "")
        elif s == "book_name":
            bd["book_name"] = kwargs.get("book_name", "")
        elif s == "chapter_num":
            bd["chapter_num"] = str(kwargs.get("chapter_num", ""))
        elif s == "source_chapter":
            bd["source_chapter"] = item.get("source_chapter", "")
        elif s == "source_page":
            bd["source_page"] = item.get("source_page", "")
        elif s == "source_from":
            bd["source_from"] = item.get("source_from", "")
        elif s == "reviewer":
            bd["reviewer"] = item.get("reviewer", "系统自动")
        elif s == "review_date":
            bd["review_date"] = item.get("review_date", datetime.date.today().isoformat())

    for s in extra_bd:
        if isinstance(s, tuple):
            if s[0] == "_S":
                bd[s[1]] = s[2]
            elif s[0] == "_D":
                bd[s[1]] = datetime.datetime.now().strftime(s[2])
            continue
        k, src, d = _f(s)
        v = item.get(src, d)
        if v == "" and d != "":
            v = d
        bd[k] = v

    # Verify definition if applicable
    name = item.get("name", "")
    definition = item.get("definition", "")
    source_file = item.get("source_file", "")

    if definition:
        if re.search(r"是指|称为|即|就是|指", definition):
            log.success(f"  ✅ {name}: 含标记词「是指」")
        else:
            log.info(f"  ⛔ {name}: 定义中无定义标记词，可能不是有效定义")

        # Source verification
        if source_file and os.path.exists(source_file):
            with open(source_file, encoding="utf-8") as sf:
                src_text = sf.read()
            check_text = definition.replace("\n", "")[:80]
            if check_text in src_text:
                log.success(f"  ✅ {name}: 精准释义可检索（含标记词）")
            else:
                # Try without punctuation
                def strip_punct(t):
                    return re.sub(r'[，。、；：""\u2018\u2019！？（）【】《》\s]', "", t)

                stripped = strip_punct(check_text)
                if any(stripped in s for s in [src_text, strip_punct(src_text[:500])]):
                    log.warning(f"  ⚠️  {name}: 去标点后匹配成功，定义基本一致")
                else:
                    log.error(f"  ❌ {name}: 精准释义在出处中不可检索！可尝试放宽 source_file 或手动核验")
                    log.info(f"  ⛔ {name}: 定义验证失败，跳过")
                    return None
        elif source_file:
            log.warning(f"  ⚠️  {name}: source_file不存在: {source_file}")
        else:
            log.warning(f"  ⚠️  {name}: 无 source_file，跳过出处检索验证")

    # Render template
    bd["definition_sentence"] = bd.get("definition_sentence", "")
    all_vars = dict(kwargs)
    all_vars.update(fm)
    all_vars.update(bd)
    all_vars.update(item)

    output = fill_template(template, all_vars)

    # Determine output path
    safe_name = _fn(name) if name_only else f"{_fn(name)}_{kwargs.get('book_id','')}_{kwargs.get('chapter_num','')}"
    if is_long and not name_only:
        safe_name = f"{_fn(name)}_{kwargs.get('book_id','')}_{kwargs.get('chapter_num','')}"
    output_file = os.path.join(kwargs.get("output_dir", "."), f"{safe_name}.md")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    # P0-1: 原子写入
    import tempfile as _tmp

    fd, tmpname = _tmp.mkstemp(dir=os.path.dirname(output_file), prefix="." + safe_name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(output)
        os.replace(tmpname, output_file)
    except OSError:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
        raise
    log.success(f"  ✅ {name}.md")
    return output_file


# ── 文件名安全化 ─────────────────────────────────────────────

# safe_filename 已从 parse_utils 导入（v38.0 统一）
# 保留别名供外部引用
safe_filename = safe_filename


# =====================================================================
# v50.7: 文件写入 + 索引渲染 + CLI 已拆分到 template_writers.py
# 向后兼容的 re-export（用 try/except 解决 circular import）
# =====================================================================
try:
    from template_writers import (  # noqa: E402, F401
        _assemble_index,
        assemble_book_overview_md,
        assemble_concept_md,
        assemble_md,
    )
except ImportError:
    # 在 template_writers 导入本模块时，本模块尚未完全加载
    # assemble_md 由调用方从 template_writers 直接导入
    pass
