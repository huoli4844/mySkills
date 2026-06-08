# Template-YAML Field Map — 所有节点类型的字段映射

## 用途

写 YAML bd 字段时，对照此文档确保覆盖全部模板字段。缺失的字段会被 builder 自动填入"无"。
每节点类型给出：总字段数、必填字段（不可为"无"）、应填字段（最多1个可为"无"）、条件字段（源文无则"无"）。

---

## 1. concept (concept_template.md) — 33 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| solved_problem | solved_problem | 🟡 应填 | 本概念解决什么问题,1-2句 |
| term_english | term_english | 🟢 必填 | 英文术语名 |
| term_definition | term_definition | 🟢 必填 | 一句话定义,可来自definition_sentence |
| definition_sentence | definition_sentence | 🟢 必填 | 逐字复制源文含"是指/称为/即/是" |
| source | source | 🟢 必填 | 出处原文引用 |
| definition_source | definition_source | 🟡 应填 | 来源:第N章 X.X |
| core_concept_map | core_concept_map | 🟡 应填 | Mermaid 概念关系图 |
| core_concept_map_analysis | core_concept_map_analysis | 🟡 应填 | 图解析,≥3句 |
| core_concept_map_source | core_concept_map_source | 🟡 应填 | 图内容来源 |
| additional_explanations | additional_explanations | 🟡 应填 | 补充说明 |
| formula_references | formula_references | 🔴 条件填 | 有公式时填LaTeX,无则"无" |
| figure_references | figure_references | 🔴 条件填 | 有图引用时填,无则"无" |
| structure | structure | 🟡 应填 | 结构说明,≥50字 |
| mathematical_model | mathematical_model | 🔴 条件填 | 有数学模型时填LaTeX,无则"无" |
| tech_classification | tech_classification | 🟡 应填 | 技术分类 |
| application_scenarios | application_scenarios | 🟡 应填 | 2-3个场景,每场景≥30字 |
| typical_systems | typical_systems | 🟡 应填 | 3-5个典型系统/设备 |
| related_concepts_relations | related_concepts_relations | 🟡 应填 | 关联概念关系说明 |
| confusion_compare | confusion_compare | 🟡 应填 | 相近概念辨析 |
| evolution | evolution | 🟡 应填 | 发展演进 |
| engineering_practices | engineering_practices | 🟡 应填 | 3条实操要点 |
| common_misconceptions | common_misconceptions | 🟡 应填 | 常见误区2-3条 |
| references | references | 🟡 应填 | 参考文献 |
| related_knowledge_elements | related_knowledge_elements | 🟡 应填 | KE列表 |
| learning_objectives | learning_objectives | 🟡 应填 | 学习目标,≥3条 |
| prerequisite_knowledge | prerequisite_knowledge | 🟡 应填 | 前置知识 |
| self_check_questions | self_check_questions | 🟡 应填 | 2-4道自检题 |
| classification | classification | 🟡 应填 | 分类信息 |
| domain | domain | 🟡 应填 | 所属领域 |
| features | features | 🟡 应填 | 特征描述,≥3点 |
| key_parameters | key_parameters | 🟡 应填 | 关键参数 |
| upstream_downstream | upstream_downstream | 🟡 应填 | 上下游关系 |
| value | value | 🟡 应填 | 工程价值,1-2句 |

**要求**: 至少 30/33 个字段为非"无"。

---

## 2. ke (ke_template.md) — 19 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| definition | definition | 🟢 必填 | 一句话定义 |
| definition_sentence | definition_sentence | 🟢 必填 | 逐字复制源文定义句 |
| source | source | 🟢 必填 | 出处原文 |
| domain | domain | 🟡 应填 | 所属领域 |
| value | value | 🟡 应填 | 工程价值 |
| classification | classification | 🟡 应填 | 分类 |
| structure | structure | 🟡 应填 | 结构说明(可含公式|块) |
| key_parameters | key_parameters | 🟡 应填 | 关键参数 |
| features | features | 🟡 应填 | 特征 |
| application_scenarios | application_scenarios | 🟡 应填 | 应用场景 |
| upstream_downstream | upstream_downstream | 🟡 应填 | 上下游 |
| related_knowledge_elements | related_knowledge_elements | 🟡 应填 | 关联KE |
| references | references | 🟡 应填 | 参考文献 |
| term_definition | term_definition | 🟡 应填 | 补充定义 |
| term_english | term_english | 🟡 应填 | 英文术语 |
| mathematical_model | mathematical_model | 🔴 条件填 | 有则填,无则无 |
| related_concepts_relations | related_concepts_relations | 🟡 应填 | 关联概念 |
| confusion_compare | confusion_compare | 🟡 应填 | 辨析 |
| evolution | evolution | 🟡 应填 | 发展 |

**要求**: 至少 16/19 个字段为非"无"。

---

## 3. entity (entity_template.md) — 17 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| entity_type | entity_type | 🟢 必填 | 实体类型(标准/组织/产品/人物) |
| term_definition | term_definition | 🟢 必填 | 定义 |
| definition_sentence | definition_sentence | 🟢 必填 | 逐字定义句 |
| definition_source | definition_source | 🟡 应填 | 来源 |
| source | source | 🟡 应填 | 出处 |
| structure | structure | 🟡 应填 | 结构说明 |
| additional_explanations | additional_explanations | 🟡 应填 | 补充说明 |
| related_concepts | related_concepts | 🟡 应填 | 关联概念 |
| references | references | 🟡 应填 | 参考文献 |
| application_scenarios | application_scenarios | 🟡 应填 | 应用场景 |
| evolution | evolution | 🟡 应填 | 发展 |
| features | features | 🟡 应填 | 特征 |
| key_parameters | key_parameters | 🟡 应填 | 关键参数 |
| related_entities | related_entities | 🟡 应填 | 关联实体 |
| related_standards | related_standards | 🟡 应填 | 关联标准 |
| time_milestones | time_milestones | 🟡 应填 | 时间里程碑 |
| typical_products | typical_products | 🟡 应填 | 典型产品 |

**要求**: 至少 14/17 个字段为非"无"。

---

## 4. kp (knowledge_template.md) — 42 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| solved_problem | solved_problem | 🟢 必填 | 解决什么问题,1-2句 |
| learning_objectives | learning_objectives | 🟢 必填 | 学习目标≥3条 |
| structure | structure | 🟡 应填 | 结构说明 |
| theoretical_basis | theoretical_basis | 🟢 必填 | 理论基础≥200字,3+wikilink |
| derivation_diagram | derivation_diagram | 🟡 应填 | Mermaid推导图≥8节点 |
| derivation_analysis | derivation_analysis | 🟡 应填 | 推导说明≥5Step |
| key_details | key_details | 🟡 应填 | 关键细节≥3条 |
| core_knowledge_elements_table | core_knowledge_elements_table | 🟡 应填 | KE表格≥3行 |
| typical_examples | typical_examples | 🟡 应填 | 典型例题≥1道 |
| application_methods | application_methods | 🟡 应填 | 应用方法≥3步 |
| application_scenarios | application_scenarios | 🟡 应填 | 场景≥3个 |
| engineering_practices | engineering_practices | 🟡 应填 | 工程要点≥3条 |
| confusion_compare | confusion_compare | 🟡 应填 | 辨析对比表≥2组 |
| knowledge_context_diagram | knowledge_context_diagram | 🟡 应填 | 知识网络Mermaid≥8节点 |
| diagram_analysis | diagram_analysis | 🟡 应填 | 网络解析≥5段 |
| bloom_level | bloom_level | 🟡 应填 | 布鲁姆层级 |
| bloom_level_description | bloom_level_description | 🟡 应填 | 层级解读≥100字 |
| bloom_progression | bloom_progression | 🟡 应填 | 递进链Mermaid |
| bloom_progression_analysis | bloom_progression_analysis | 🟡 应填 | 递进解析≥150字 |
| learning_objectives_bloom | bloom_alignment | 🟡 应填 | Bloom对齐矩阵 |
| skill_requirements | skill_requirements | 🟡 应填 | 技能要求≥3条 |
| skill_objectives | skill_objectives | 🟡 应填 | 技能目标≥3条 |
| self_check_questions | self_check_questions | 🟡 应填 | 自检题2-4道 |
| prerequisite | prerequisite | 🟡 应填 | 前置知识 |
| parallel | parallel | 🟡 应填 | 并行知识 |
| subsequent | subsequent | 🟡 应填 | 后续知识 |
| source_from | source_from | 🟡 应填 | 来源定位 |
| learning_material | learning_material | 🟡 应填 | 学习材料 |
| domain_tags | domain_tags | 🟡 应填 | 领域标签 |
| difficulty | difficulty | 🟡 应填 | 难度 |
| mathematical_model | mathematical_model | 🔴 条件填 | 有则填,无则无 |
| formula_references | formula_references | 🔴 条件填 | 有公式则填 |
| ... 共42字段 | | | |

**要求**: 至少 36/42 个字段为非"无"。

---

## 5. sp (skill_template.md) — 32 个内容字段

完整字段: solved_problem, bloom_level, bloom_level_description, skill_objectives, domain, bloom_progression, bloom_progression_analysis, bloom_alignment, core_operation, competency_standards, operation_boundaries, core_theoretical_support, tool_support, prerequisite_skills, common_errors_table, operation_flowchart, operation_flow_analysis, typical_practical_cases, related_concepts_knowledge, supported_scenarios, extended_skills, confusion_skill_compare, knowledge_context_diagram, diagram_analysis, ...

**要求**: 至少 26/32 个字段为非"无"。

---

## 6. scene (scenario_template.md) — 28 个内容字段

完整字段: scenario_type, bloom_level, domain, scenario_description, scene_elements, scene_concept_support, core_knowledge_support, core_skill_support, scene_ke_support, workflow_diagram, node_descriptions, typical_application_cases, related_scenes, confusion_scenario_compare, knowledge_context_diagram, diagram_analysis, ...

**要求**: 至少 22/28 个字段为非"无"。

---

## 7. exercise (exercise_template.md) — 5 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| question | question | 🟢 必填 | 完整习题原文 |
| related_answer | related_answer | 🟡 应填 | wikilink到对应解答 |

**要求**: 至少 4/5 个字段为非"无"。

---

## 8. solution (eval_template.md) — 18 个内容字段

| 模板字段 | YAML bd 键 | 等级 | 说明 |
|----------|------------|:----:|------|
| question | question | 🟢 必填 | 题目原文 |
| principle_steps | principle_steps | 🟢 必填 | 解题原理流程化拆解 |
| characteristics | characteristics | 🟢 必填 | 技术特点归纳 |
| exam_points | exam_points | 🟢 必填 | 核心考点分析 |
| common_mistakes | common_mistakes | 🟢 必填 | 常见错误 |
| solving_tips | solving_tips | 🟢 必填 | 解题技巧 |
| difficulty_1_title | difficulty_1_title | 🟢 必填 | 难点1标题 |
| difficulty_1_content | difficulty_1_content | 🟢 必填 | 难点1内容 |
| difficulty_2_title | difficulty_2_title | 🟢 必填 | 难点2标题 |
| difficulty_2_content | difficulty_2_content | 🟢 必填 | 难点2内容 |
| difficulty_3_title | difficulty_3_title | 🟡 应填 | 难点3标题 |
| difficulty_3_content | difficulty_3_content | 🟡 应填 | 难点3内容 |
| flowchart_diagram | flowchart_diagram | 🔴 条件填 | 流程图(有则填) |
| flowchart_steps | flowchart_steps | 🔴 条件填 | 流程说明(有则填) |
| knowledge_loop_diagram | knowledge_loop_diagram | 🔴 条件填 | 知识闭环图 |
| knowledge_loop_analysis | knowledge_loop_analysis | 🔴 条件填 | 闭环解析 |
| related_concepts | related_concepts | 🟡 应填 | 关联知识点wikilink |
| related_answer | related_answer | 🟡 应填 | 关联习题链接 |

**要求**: 至少 14/18 个字段为非"无"。

---

## 快速检查命令

```bash
# 对指定 YAML 检查模板字段覆盖
python3 -c "
import yaml, re, sys

data_dir = sys.argv[1]
tpl_dir = sys.argv[2]
yaml_name = sys.argv[3]
tpl_name = sys.argv[4]

with open(f'{tpl_dir}/{tpl_name}') as f:
    tpl = f.read()
tpl_fields = set(re.findall(r'\{\{(\w+)\}\}', tpl))
skip = {'name','book_id','book_name','chapter_num','confidence','confidence_note',
        'source_chapter','source_from','entity_type','aliases','tags','type','type_tag'}
content_fields = tpl_fields - skip

with open(f'{data_dir}/{yaml_name}') as f:
    data = yaml.safe_load(f)
if data:
    for item in data:
        bd = item.get('bd', {})
        missing = content_fields - set(bd.keys())
        wu = sum(1 for v in bd.values() if v == '无' or v is None)
        print(f\"{item.get('name','?'):30s} bd={len(bd):2d}  gap={len(missing):2d}  无_in_bd={wu}\")
        if missing:
            print(f\"  missing: {sorted(missing)}\")
" .dag/第1章/data/ assets/templates/ concepts.yaml concept_template.md
```
