"""review_field_depth.py — 字段深度阈值配置

质量审查引擎的配置数据层。纯字典定义，零运行时依赖。
供 quality_reviewer.py 和 pipeline_fix.py 等模块导入。
"""

# ── 类型映射 ──
TYPE_YAML_MAP: dict[str, dict[str, str]] = {
    "concept":     {"yaml": "concepts.yaml",    "dir": "30_核心概念", "tpl": "concept_template.md"},
    "ke":          {"yaml": "kes.yaml",         "dir": "40_知识要素", "tpl": "ke_template.md"},
    "entity":      {"yaml": "entities.yaml",    "dir": "80_实体",    "tpl": "entity_template.md"},
    "kp":          {"yaml": "kps.yaml",         "dir": "50_知识点",   "tpl": "knowledge_template.md"},
    "sp":          {"yaml": "sps.yaml",         "dir": "60_技能点",   "tpl": "skill_template.md"},
    "scene":       {"yaml": "scenes.yaml",      "dir": "70_应用场景", "tpl": "scenario_template.md"},
    "exercise":    {"yaml": "exercises.yaml",   "dir": "90_习题",     "tpl": "exercise_template.md"},
    "solution":    {"yaml": "solutions.yaml",   "dir": "90_习题/解答","tpl": "eval_template.md"},
}

# ── FM 必填/可选字段 ──
FM_REQUIRED = ["source_chapter", "confidence"]
FM_OPTIONAL = ["source_from", "type_tag", "entity_type", "aliases", "tags",
               "book_id", "book_name", "confidence_note", "bloom_level", "difficulty"]

# ── 类型特定的 bd 字段深度阈值（字数下限） ──
FIELD_DEPTH: dict[str, dict[str, int]] = {
    "concept": {
        "learning_objectives": 80,
        "prerequisite_knowledge": 30,
        "term_definition": 80,
        "mathematical_model": 30,
        "classification": 30,
        "core_concept_map": 30,
        "working_principle": 80,
        "key_parameters": 30,
        "physical_meaning": 50,
        "technical_classification": 20,
        "engineering_practices": 50,
        "application_scenarios": 50,
        "typical_values": 20,
        "common_misconceptions": 30,
        "practical_tips": 30,
        "related_concepts": 30,
    },
    "ke": {
        "term_definition": 60,
        "definition_sentence": 30,
        "classification": 20,
        "structure": 40,
        "features": 30,
        "mathematical_model": 30,
        "key_parameters": 30,
        "application_scenarios": 40,
        "value": 20,
        "upstream_downstream": 20,
    },
    "kp": {
        "learning_objectives": 80,
        "theoretical_basis": 150,
        "practical_skills": 80,
        "typical_values": 20,
        "application_scenarios": 50,
        "analysis_method": 50,
        "common_misconceptions": 30,
        "advanced_topics": 30,
    },
    "sp": {
        "learning_objectives": 60,
        "operation_flow": 100,
        "tools_and_equipment": 50,
        "standards_and_specs": 30,
        "precautions": 30,
        "quality_criteria": 30,
        "typical_scenarios": 50,
    },
    "scene": {
        "scenario_description": 80,
        "requirements_analysis": 50,
        "implementation_steps": 100,
        "key_technologies": 50,
        "expected_outcome": 30,
    },
    "entity": {
        "term_definition": 60,
        "features": 40,
        "classification": 20,
        "typical_values": 30,
    },
    "solution": {
        "question": 30,
        "principle_steps": 100,
        "key_points": 50,
        "common_pitfalls": 30,
        "exam_points": 30,
    },
}
