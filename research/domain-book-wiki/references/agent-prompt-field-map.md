# Agent Prompt bd 字段名 → 模板变量对应表

> ⚠️ 写作前必须读此表。字段名写错 = 模板 `{{xxx}}` 不替换 = 内容全空。
> pipeline auto v52.3 新增 `[字段校验/...]` warning 会自动检测字段名不匹配，但最佳实践是写作时就写对。

## 提取命令（通用方法）

```bash
grep -o '{{[^}]*}}' assets/templates/<type>.md | sort -u
```

## 各类型 bd 字段名速查

### 概念 (concept_template.md → concepts.yaml)

```
term_english, term_definition, definition_sentence,
core_concept_map, core_concept_map_analysis, structure,
mathematical_model, tech_classification, application_scenarios,
typical_systems, engineering_practices, common_misconceptions,
related_concepts_relations, confusion_compare, evolution,
references, related_knowledge_elements, learning_objectives,
prerequisite_knowledge, self_check_questions, solved_problem,
classification, domain, features, key_parameters,
upstream_downstream, value, entity_type,
additional_explanations, figure_references, formula_references
```

### 知识要素 (ke_template.md → kes.yaml)

```
term_definition, term_english, classification, structure,
key_parameters, features, application_scenarios, value,
upstream_downstream, related_knowledge_elements, references, domain,
definition_sentence, confusion_compare, evolution,
mathematical_model, related_concepts_relations
```

### 实体 (entity_template.md → entities.yaml)

```
entity_type, term_definition, definition_sentence, structure,
application_scenarios, features, key_parameters,
related_entities, related_standards, time_milestones,
typical_products, related_concepts, evolution
```

### 知识点 (knowledge_template.md → kps.yaml)

```
solved_problem, learning_objectives, theoretical_basis,
application_scenarios, engineering_practices, confusion_compare,
self_check_questions, prerequisite, difficulty,
core_knowledge_elements_table, bloom_level_description,
bloom_progression, bloom_alignment, skill_requirements,
skill_objectives, structure, mathematical_model, related_scenes,
application_methods, derivation_analysis, derivation_diagram,
diagram_analysis, key_details, knowledge_context_diagram,
typical_examples
```

### 技能点 (skill_template.md → sps.yaml)

```
skill_objectives, prerequisite_skills, core_operation,
typical_tools, performance_criteria, common_mistakes,
application_domain, engineering_case, solved_problem,
bloom_level_description, bloom_progression, bloom_alignment,
competency_standards, operation_boundaries,
core_theoretical_support, tool_support, extended_skills,
typical_practical_cases, confusion_skill_compare,
supported_scenarios, operation_flowchart, operation_flow_analysis,
common_errors_table, knowledge_context_diagram, diagram_analysis,
related_concepts_knowledge, domain, applicable_scenarios
```

### 应用场景 (scenario_template.md → scenes.yaml)

```
scenario_type, scenario_description, scene_elements,
node_descriptions, typical_application_cases,
knowledge_context_diagram, workflow_diagram, diagram_analysis,
confusion_scenario_compare, core_knowledge_support,
core_skill_support, scene_concept_support, scene_ke_support,
related_scenes, evolution, domain
```

### 习题 (exercise_template.md → exercises.yaml)

```
question, related_answer
```

### 解答 (eval_template.md → solutions.yaml)

```
principle_steps, characteristics, exam_points, common_mistakes,
solving_tips, difficulty_1_title, difficulty_1_content,
difficulty_2_title, difficulty_2_content,
difficulty_3_title, difficulty_3_content,
flowchart_diagram, flowchart_steps,
knowledge_loop_diagram, knowledge_loop_analysis,
related_concepts, source_reference, question
```

## 常见错误对照

| 错误字段 | 模板期望 | 后果 |
|:---------|:---------|:-----|
| `answer_text` | `principle_steps` + `characteristics` + `exam_points` + ...(19个) | eval_template 不显示 → 骨架回退 |
| `key_formulas` | 用 `$$...$$` 嵌入 `principle_steps` | eval_template 无此字段 |
| `skill_description` | `skill_objectives` | skill_template 不显示 |
| `scene_type` | `scenario_type` | scenario_template 不显示 |
| `typical_values` | 量化参数嵌入 `principle_steps` 或 `characteristics` | eval_template 无此字段 |
| `engineering_insight` | 知识点放入 `exam_points` 或 `solving_tips` | eval_template 无此字段 |
| `solution_detail` | 拆解到 `scene_elements` + `typical_application_cases` | scenario_template 无此字段 |
