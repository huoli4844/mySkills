# Agent YAML bd 字段名校验清单

> 每次 delegate_task 写 YAML 前，先 grep 模板文件提取 `{{xxx}}` 字段名，不要凭记忆写。
> v52.3 新增 pipeline 自动校验：运行 pipeline auto 时会打印 `[字段校验/类型/名称]` warning。

## 提取命令

```bash
grep -o '{{[^}]*}}' assets/templates/<type>.md | sort -u
```

## 各类型字段名速查

### concept_template.md → concepts.yaml
term_english, term_definition, definition_sentence, core_concept_map, core_concept_map_analysis,
structure, mathematical_model, tech_classification, application_scenarios, typical_systems,
engineering_practices, common_misconceptions, related_concepts_relations, confusion_compare,
evolution, references, related_knowledge_elements, learning_objectives, prerequisite_knowledge,
self_check_questions, solved_problem, classification, domain, features, key_parameters,
upstream_downstream, value, entity_type, additional_explanations, figure_references, formula_references

### ke_template.md → kes.yaml
term_definition, term_english, classification, structure, key_parameters, features,
application_scenarios, value, upstream_downstream, related_knowledge_elements, references, domain,
definition_sentence, confusion_compare, evolution, mathematical_model, related_concepts_relations

### entity_template.md → entities.yaml
entity_type, term_definition, definition_sentence, structure, application_scenarios, features,
key_parameters, related_entities, related_standards, time_milestones, typical_products,
related_concepts, evolution

### knowledge_template.md → kps.yaml
solved_problem, learning_objectives, theoretical_basis, application_scenarios,
engineering_practices, confusion_compare, self_check_questions, prerequisite, difficulty,
core_knowledge_elements_table, bloom_level_description, bloom_progression, bloom_alignment,
skill_requirements, skill_objectives, structure, mathematical_model, related_scenes,
application_methods, derivation_analysis, derivation_diagram, diagram_analysis, key_details,
knowledge_context_diagram, typical_examples

### skill_template.md → sps.yaml
skill_objectives, prerequisite_skills, core_operation, typical_tools, performance_criteria,
common_mistakes, application_domain, engineering_case, solved_problem, bloom_level_description,
bloom_progression, bloom_alignment, competency_standards, operation_boundaries,
core_theoretical_support, tool_support, extended_skills, typical_practical_cases,
confusion_skill_compare, supported_scenarios, operation_flowchart, operation_flow_analysis,
common_errors_table, knowledge_context_diagram, diagram_analysis, related_concepts_knowledge,
domain, applicable_scenarios

### scenario_template.md → scenes.yaml
scenario_type, scenario_description, scene_elements, node_descriptions,
typical_application_cases, knowledge_context_diagram, workflow_diagram, diagram_analysis,
confusion_scenario_compare, core_knowledge_support, core_skill_support, scene_concept_support,
scene_ke_support, related_scenes, evolution, domain

### exercise_template.md → exercises.yaml
question, related_answer

### eval_template.md → solutions.yaml
principle_steps, characteristics, exam_points, common_mistakes, solving_tips,
difficulty_1_title, difficulty_1_content, difficulty_2_title, difficulty_2_content,
difficulty_3_title, difficulty_3_content, flowchart_diagram, flowchart_steps,
knowledge_loop_diagram, knowledge_loop_analysis, related_concepts, source_reference, question

## 常见错误模式

| 错误 | 正确写法 | 影响 |
|:-----|:---------|:-----|
| `answer_text` | `principle_steps` + `characteristics` + `exam_points` + ...(模板的19个字段) | solution 模板不识别 → 回退骨架 |
| `key_formulas` | 放入 `principle_steps` 中用 $$ 嵌入 | eval_template 无此字段 |
| `skill_description` | `skill_objectives` | skill_template 不显示 |
| `scene_type` | `scenario_type` | scenario_template 不显示 |
| `node_descriptions`/`solution_detail` | `scene_elements` + `typical_application_cases` | scene 字段不对应 |
| `source_from`/`source` | facts from fm fields | bd 中不需要，fm 自动填充 |
