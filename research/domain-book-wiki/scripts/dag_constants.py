"""dag_constants.py — DAG 常量、类型定义和配置注册表

从 dag_utils.py 拆分。纯常量 + 类型定义，零函数逻辑。
"""

from __future__ import annotations

from typing import Protocol


class PipelineArgs(Protocol):
    """dag_pipeline 函数参数的类型协议"""

    wiki_root: str
    book_id: str
    chapter: str | None
    input: str | None
    force: bool


class PipelineError(Exception):
    """Pipeline 操作失败

    v40.1: 统一异常类型，替代分散的 sys.exit / print + return False 模式。
    调用方可 catch 此异常做统一日志记录和状态重置。

    用法:
        PipelineError("message")
        PipelineError("phase", "message")
    """
    def __init__(self, message_or_phase: str, message: str | None = None) -> None:
        if message is None:
            # Single argument: just the message
            super().__init__(message_or_phase)
            self.phase: str | None = None
            self.message = message_or_phase
        else:
            # Two arguments: phase + message
            self.phase = message_or_phase
            super().__init__(f"[{message_or_phase}] {message}")
            self.message = message


# ── v50.0: 集中化必填字段定义 ──
# yaml_pre_validate.py 和 build_kb_files.py 从同一处读取。
# key = 内部类型名 (与 NODE_CONFIG key 一致)
# value = 对应 YAML bd 字段名列表 (与模板 {{变量}} 名一致)
REQUIRED_BD_FIELDS: dict[str, list[str]] = {
    "concept": ["solved_problem", "learning_objectives", "structure", "application_scenarios"],
    "ke": ["term_definition", "definition_sentence"],
    "entity": ["entity_type", "term_definition"],
    "kp": ["solved_problem", "bloom_level_description", "bloom_progression", "bloom_alignment", "skill_requirements", "skill_objectives", "engineering_practices", "confusion_compare", "self_check_questions"],
    "sp": ["solved_problem", "bloom_level_description", "bloom_alignment", "skill_objectives", "core_operation", "bloom_progression"],
    "scene": ["bloom_level_description", "bloom_alignment", "scenario_description", "node_descriptions", "knowledge_context", "bloom_progression"],
    "exercise": ["question"],
    "solution": ["answer"],
}


# ============================================================
# 中心化路径注册表（DIR）
# 所有目录名只在此定义，其他地方通过 DIR["KEY"] 引用
# 如需改名，只改这里，所有脚本自动生效。
# 变更后需同步：模板文件(.md) 中的硬编码路径 + 文档
# ============================================================
DIR = {
    # L1 节点
    "CONCEPTS": "30_核心概念",
    "KE": "40_知识要素",
    "KP": "50_知识点",
    "SP": "60_技能点",
    "SCENE": "70_应用场景",
    "ENTITIES": "80_实体",
    "EXERCISES": "90_习题",
    "SOLUTIONS": "90_习题/解答",
    # L2/L3/L4
    "OVERVIEW": "10_总揽",  # L2 单书索引
    "SOURCE": "20_正文",  # L1 源文件 MD
    "DOMAIN_CTRL": "领域总控",  # L3（在 domain/ 下）
    "KB_CTRL": "知识库总控",  # L4（在 wiki 根）
    # 容器目录（不存节点文件，只做层级组织）
    "FIELD": "",  # domain 文件夹直接以领域名命名
    "LIBRARY": "",  # book 文件夹直接以书籍编号+名称命名
    # v36.1: 章节 TOC 索引
    "TOC": ".dag",
    # YAML 数据存放在 .dag/第N章/data/ 下
    "DATA": ".dag",
}

# 前向兼容：从 DIR 生成 NODE_CONFIG 中使用的 dir 映射
DIR_BY_PHASE = {
    "concepts": DIR["CONCEPTS"],
    "ke": DIR["KE"],
    "kp": DIR["KP"],
    "sp": DIR["SP"],
    "scene": DIR["SCENE"],
    "entities": DIR["ENTITIES"],
    "exercises": DIR["EXERCISES"],
    "solutions": DIR["SOLUTIONS"],
}

# v33.0: 教学认知链顺序 — 概念(是什么) → KE+实体(用什么讲) → KP(学了什么) → SP(能做什么) → Scene(解决什么) → 习题
DAG_ORDER = [
    "chapter_toc",
    "concepts",
    "ke",
    "entities",
    "kp",
    "sp",
    "scene",
    "exercises",
    "solutions",
    "l2_indices",
    "l3_indices",
    "l4_indices",
]
DAG_DEPENDS = {
    "chapter_toc": [],  # v36.1: 章节 TOC 预处理，无依赖
    "concepts": ["chapter_toc"],  # 概念依赖 TOC
    "ke": ["concepts"],  # 概念完成 → 知识要素
    "entities": ["concepts"],  # 概念完成 → 实体
    "kp": ["concepts", "ke", "entities"],  # 概念+KE+实体全完成 → 知识点
    "sp": ["kp"],  # KP完成 → 技能点
    "scene": ["kp", "sp"],  # KP+SP完成 → 应用场景
    "exercises": ["scene"],  # 最后：所有教学节点完成后做习题
    "solutions": ["exercises"],
    "l2_indices": ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"],
    "l3_indices": ["l2_indices"],
    "l4_indices": ["l3_indices"],
}
DAG_ITEM_HINTS = {
    "chapter_toc": "自动提取章节 TOC",
    "concepts": "10-30 个",
    "ke": "10-30 个知识要素",
    "entities": "3-10 个实体",
    "kp": "5-15 个知识点",
    "sp": "3-8 个技能点",
    "scene": "2-5 个场景",
    "exercises": "5-20 道（可 auto-detect）",
    "solutions": "与习题数一致",
    "l2_indices": "自动生成（单书总揽: L2）",
    "l3_indices": "自动生成（领域总控: L3）",
    "l4_indices": "自动生成（知识库总控: L4）",
}
NODE_CONFIG = {
    # v37.0: 五大类模板归并 — template 字段统一使用新模板名
    "concepts": {
        "dir": DIR_BY_PHASE["concepts"],
        "template": "concept_template.md",
        "filename_style": "name_only",
        "verify_naming": "short",
    },
    "ke": {
        "dir": DIR_BY_PHASE["ke"],
        "template": "ke_template.md",
        "filename_style": None,
        "verify_naming": "short",
    },
    "kp": {
        "dir": DIR_BY_PHASE["kp"],
        "template": "knowledge_template.md",
        "filename_style": "name_only",
        "verify_naming": "short",
    },
    "sp": {
        "dir": DIR_BY_PHASE["sp"],
        "template": "skill_template.md",
        "filename_style": "name_only",
        "verify_naming": "short",
    },
    "scene": {
        "dir": DIR_BY_PHASE["scene"],
        "template": "scenario_template.md",
        "filename_style": "name_only",
        "verify_naming": "short",
    },
    "entities": {
        "dir": DIR_BY_PHASE["entities"],
        "template": "entity_template.md",
        "filename_style": None,
        "verify_naming": "short",
    },
    "exercises": {
        "dir": DIR_BY_PHASE["exercises"],
        "template": "eval_template.md",
        "filename_style": None,
        "verify_naming": "long",
    },
    "solutions": {
        "dir": DIR_BY_PHASE["solutions"],
        "template": "eval_template.md",
        "filename_style": None,
        "verify_naming": "long",
    },
    "l2_indices": {"dir": DIR["OVERVIEW"], "template": None, "filename_style": None, "verify_naming": "long"},
    "l3_indices": {"dir": None, "template": None, "filename_style": None, "verify_naming": "long"},
    "l4_indices": {"dir": None, "template": None, "filename_style": None, "verify_naming": "long"},
}

# ── 层级质量清单 ────────────────────────────────────────
# 每个 DAG 层级完成后应通过的审核项
LEVEL_QUALITY_CHECKS = {
    "L1": {
        "label": "单文件层（L1）",
        "checks": [
            ("critical", "all_phases_done", "所有 L1 阶段必须标记 done"),
            ("critical", "exercise_solution_1to1", "习题-解答 1:1 对应关系通过"),
            ("critical", "no_broken_links", "L1 范围内无断链"),
            ("critical", "no_placeholder", "L1 文件无 {{placeholder}} 残留"),
            ("critical", "no_shared_figures", "无共享图：每个图号只属于一个概念"),
            ("warning", "concept_definitions_valid", "概念定义的标记词检查通过"),
            ("warning", "mermaid_no_errors", "Mermaid 无 🔴 级别错误"),
            # ── 图质量检查 ──
            ("critical", "graph_hollow_concepts", "空心概念：所有概念必须有KE引用"),
            ("critical", "graph_orphan_ke", "孤儿KE：所有KE必须有KP引用"),
            ("warning", "graph_overloaded", "过载节点：入度≥10的节点需考虑拆分"),
            ("warning", "graph_similar_names", "相似节点名：同类型近似名称需检查合并"),
            ("warning", "graph_connectivity", "图连通性：概念→KE→KP→SP→Scene 引用完整"),
            ("warning", "graph_path_integrity", "路径完整性：概念链各环节连通"),
            ("warning", "graph_orphan_nodes", "孤立节点：无游离的知识节点"),
        ],
    },
    "L2": {
        "label": "单书总揽层（L2）",
        "checks": [
            ("critical", "all_l1_done", "该书的全部 L1 阶段必须标记 done"),
            ("critical", "l2_indices_exist", "book_overview 索引文件存在（v43.15: 融合为单文件）"),
            ("critical", "l2_indices_done", "l2_indices 阶段必须标记 done"),
            ("warning", "l2_content_not_empty", "L2 book_overview 有实质性内容（非全 0% 空壳）"),
            ("critical", "no_broken_links", "L2 索引中无断链"),
            ("warning", "graph_l2_connectivity", "L2 索引节点在图谱中可追溯"),
            ("warning", "graph_l2_coverage", "L2 索引覆盖≥80%的L1节点"),
            # ── v35.0: 图深度分析 ──
            ("warning", "graph_book_chain", "全书知识链完整性：概念→Scene 路径无断裂"),
            ("warning", "graph_book_centrality", "全书核心概念识别：度中心性分析"),
            ("warning", "graph_book_similar", "跨章概念一致性：同名概念跨章定义一致"),
        ],
    },
    "L3": {
        "label": "领域总控层（L3）",
        "checks": [
            ("critical", "all_books_l2_done", "领域内所有书的 L2 阶段必须 done"),
            ("critical", "l3_indices_exist", "domain_overview 索引文件存在（v43.15: 融合为单文件）"),
            ("critical", "l3_indices_done", "l3_indices 阶段必须标记 done"),
            ("critical", "no_broken_links_l3", "L3 索引中无断链"),
            # ── v35.0: 跨书图分析 ──
            ("warning", "graph_cross_book_align", "跨书概念对齐：同名概念跨书定义一致性"),
            ("warning", "graph_knowledge_islands", "知识孤岛检测：高重叠概念但跨书引用少的书对"),
            ("warning", "graph_domain_chain", "领域教学链覆盖：聚合各书路径完整性"),
            ("warning", "graph_l3_cross_book", "跨书引用计数：领域内跨书边统计"),
        ],
    },
    "L4": {
        "label": "知识库总控层（L4）",
        "checks": [
            ("critical", "all_domains_l3_done", "所有领域的 L3 阶段必须 done"),
            ("critical", "l4_indices_exist", "kb_overview 索引文件存在（v43.15: 融合为单文件）"),
            ("critical", "l4_indices_done", "l4_indices 阶段必须标记 done"),
            ("critical", "no_broken_links_l4", "L4 索引中无断链"),
            # ── v35.0: 全库图分析 ──
            ("warning", "graph_full_health", "全库结构健康度：节点/边/孤立/过载汇总"),
            ("warning", "graph_cross_domain", "跨领域桥接：不同领域间概念关联分析"),
            ("warning", "graph_full_blindspots", "全库知识盲区：所有书中概念→Scene 无完整路径"),
            ("warning", "graph_l4_complete", "全库空心概念：无概念缺失KE引用"),
        ],
    },
}


# ============================================================
# BUILDER_CONFIG — 类型驱动的构建配置字典（v36.5 抽取）
# 每个条目定义一种知识库节点类型的构建参数。
# 由 build_kb_files.py 的 build_type() 统一执行。
# v42.0: 从 dag_utils.py 迁入
# ============================================================

_COMMON_FM = {"aliases": [], "tags": ["knowledge-base", "{{book_id}}"]}

BUILDER_CONFIG = {
    "ke": {
        "data_file": "kes.json",
        "dir_key": "KE",
        "template": "ke_template.md",  # v47.0: 知识要素专用模板
        "quality_key": "ke",  # v47.0: 独立质量检查键
        "type_tags": ["知识要素"],
        "fm_type": "knowledge-element",
        "template_version": "v1.0",
        "graph_type": "ke",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": [],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["source_chapter", "source_from"],
        "bd_extra_keys_from_item_bd": ["definition_sentence"],
        "print_label": "KE:",
    },
    "kp": {
        "data_file": "kps.json",
        "dir_key": "KP",
        "template": "knowledge_template.md",  # v37.0: 知识类模板
        "type_tags": ["知识点"],
        "fm_type": "knowledge-point",
        "template_version": "v7.0",
        "graph_type": "kp",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": ["bloom_level"],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["bloom_level"],
        "bd_extra_keys_from_item_bd": ["related_knowledge_elements", "supported_skills_scenarios"],
        "print_label": "KP:",
    },
    "sp": {
        "data_file": "sps.json",
        "dir_key": "SP",
        "template": "skill_template.md",  # v37.0: 技能类模板
        "type_tags": ["技能点"],
        "fm_type": "skill",
        "template_version": "v7.0",
        "graph_type": "sp",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": ["bloom_level"],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["bloom_level"],
        "bd_extra_keys_from_item_bd": ["related_knowledge_elements", "supported_scenarios"],
        "print_label": "SP:",
    },
    "entity": {
        "data_file": "entities.json",
        "dir_key": "ENTITIES",
        "template": "entity_template.md",  # v47.0: 实体专用模板
        "quality_key": "entity",  # v47.0: 独立质量检查键
        "type_tags": ["实体"],
        "fm_type": "entity",
        "template_version": "v1.0",
        "graph_type": "entity",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": [],
        "fm_extra_keys_from_item_bd": ["entity_type"],
        "bd_extra_keys_from_item_fm": ["source_chapter"],
        "bd_extra_keys_from_item_bd": ["entity_type"],
        "print_label": "Entity:",
    },
    "scene": {
        "data_file": "scenes.json",
        "dir_key": "SCENE",
        "template": "scenario_template.md",  # v37.0: 场景类模板
        "type_tags": ["应用场景"],
        "fm_type": "scenario",
        "template_version": "v7.0",
        "graph_type": "scene",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": ["bloom_level"],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["bloom_level"],
        "bd_extra_keys_from_item_bd": [],
        "print_label": "Scene:",
    },
    "concept": {
        "data_file": "concepts.json",
        "dir_key": "CONCEPTS",
        "template": "concept_template.md",
        "type_tags": ["概念"],
        "fm_type": "concept",
        "template_version": "v7.0",
        "graph_type": "concept",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": [],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["source_chapter", "source_from"],
        "bd_extra_keys_from_item_bd": [],
        "print_label": "Concept:",
    },
    "solution": {
        "data_file": "solutions.json",
        "dir_key": "SOLUTIONS",
        "template": "eval_template.md",  # v37.0: 归并到评测类模板
        "quality_key": "eval/solution",  # v37.0: 质量检查子类型键
        "type_tags": ["习题解答"],
        "fm_type": "solution",
        "template_version": "v7.0",
        "graph_type": "solution",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": ["bloom_level"],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["source_chapter"],
        "bd_extra_keys_from_item_bd": [],
        "print_label": "Solution:",
    },
    "exercise": {
        "data_file": "exercises.json",
        "dir_key": "EXERCISES",
        "template": "exercise_template.md",  # v43.5: 习题只含题目
        "quality_key": "eval/exercise",  # v37.0: 质量检查子类型键
        "type_tags": ["习题"],
        "fm_type": "exercise",
        "template_version": "v7.0",
        "graph_type": "exercise",
        "static_fm_extra": dict(_COMMON_FM),
        "cssclass": "knowledge-base",
        "fm_extra_keys_from_item_fm": ["bloom_level"],
        "fm_extra_keys_from_item_bd": [],
        "bd_extra_keys_from_item_fm": ["source_chapter"],
        "bd_extra_keys_from_item_bd": [],
        "print_label": "Exercise:",
    },
}
