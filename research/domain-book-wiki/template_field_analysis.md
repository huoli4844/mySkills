# Domain-Book-Wiki 模板字段差异分析报告

> 生成时间: 2026-06-07
> 数据来源: `assets/templates/*.md` + `scripts/dag_constants.py`
> 脚本: `scripts/template_field_analysis.md`

---

## 总览

| 节点类型 | 模板文件 | REQUIRED 个数 | ALLOWED ({{}}) 个数 | 特殊 extra 字段 |
|---------|---------|:-----------:|:-----------------:|:--------------:|
| concept | concept_template.md | 4 | 39 | 0 |
| ke | ke_template.md | 2 | 23 | 0 |
| entity | entity_template.md | 2 | 24 | 0 |
| kp | knowledge_template.md | 9 | 33+2=35 | 2 |
| sp | skill_template.md | 6 | 34+1=35 | 1 |
| scene | scenario_template.md | 6 | 26 | 0 |
| exercise | exercise_template.md | 1 | 15 | 0 |
| solution | eval_template.md | 1 | 32 | 0 |

---

## 各节点类型详情

### 1. concept (concept_template.md)

**REQUIRED 字段**（`REQUIRED_BD_FIELDS`）— 全部在模板中：
- `solved_problem`
- `learning_objectives`
- `structure`
- `application_scenarios`

**ALLOWED 字段**（模板 `{{xxx}}` + bd_extra_keys）：共 39 个

| 分类 | 字段 |
|------|------|
| 通用FM | type, type_tag, name, book_id, book_name, chapter_num, confidence, confidence_note, source_chapter, source_from, entity_type, aliases, tags |
| 核心内容 | learning_objectives★, prerequisite_knowledge, self_check_questions, solved_problem★, structure★, term_english, term_definition, definition_sentence, domain, classification, core_concept_map, core_concept_map_analysis, mathematical_model, key_parameters, features, tech_classification |
| 应用/关联 | application_scenarios★, typical_systems, value, engineering_practices, common_misconceptions, related_concepts_relations, confusion_compare, evolution, related_knowledge_elements, upstream_downstream |
| 特殊 extra | (无) |

### 2. ke (ke_template.md)

**REQUIRED 字段** — 全部在模板中：
- `term_definition`
- `definition_sentence`

**ALLOWED 字段**：共 23 个

| 分类 | 字段 |
|------|------|
| 通用FM | type_tag, name, book_id, book_name, chapter_num, confidence, confidence_note, source_chapter, source_from, aliases, tags |
| 内容 | term_english, term_definition★, definition_sentence★, domain, mathematical_model, key_parameters, features, related_concepts_relations, related_knowledge_elements, confusion_compare, application_scenarios, evolution |
| 特殊 extra | (无) |

### 3. entity (entity_template.md)

**REQUIRED 字段** — 全部在模板中：
- `entity_type`
- `term_definition`

**ALLOWED 字段**：共 24 个

| 分类 | 字段 |
|------|------|
| 通用FM | type_tag, name, book_id, book_name, chapter_num, entity_type★, confidence, confidence_note, source_chapter, source_from, aliases, tags |
| 内容 | term_definition★, definition_sentence, key_parameters, features, structure, evolution, time_milestones |
| 关联 | related_entities, related_standards, related_concepts |
| 应用 | application_scenarios, typical_products |
| 特殊 extra | (无) |

### 4. kp (knowledge_template.md)

**REQUIRED 字段** — 全部在模板中：
- `solved_problem`
- `bloom_level_description`
- `bloom_progression`
- `bloom_alignment`
- `skill_requirements`
- `skill_objectives`
- `engineering_practices`
- `confusion_compare`
- `self_check_questions`

**ALLOWED 字段**：共 35 个（模板 33 + 特殊 extra 2）

| 分类 | 字段 |
|------|------|
| 通用FM | name, book_id, book_name, chapter_num, bloom_level, confidence, confidence_note, source_chapter, source_from, aliases, tags |
| 核心讲解 | solved_problem★, difficulty, theoretical_basis, derivation_diagram, derivation_analysis, key_details, core_knowledge_elements_table |
| 动手实践 | typical_examples, application_methods, application_scenarios, engineering_practices★, confusion_compare★ |
| 知识地图 | knowledge_context_diagram, diagram_analysis |
| 认知进阶 | bloom_level_description★, bloom_progression★, bloom_progression_analysis, learning_objectives, bloom_alignment★, skill_requirements★, skill_objectives★ |
| 自学检验 | self_check_questions★ |
| **特殊 extra** | ✦ **related_knowledge_elements** — 构建系统用于关联 KE，不显示在渲染模板中 |
| | ✦ **supported_skills_scenarios** — 构建系统用于关联 SP/Scene，不显示在渲染模板中 |

### 5. sp (skill_template.md)

**REQUIRED 字段** — 全部在模板中：
- `solved_problem`
- `bloom_level_description`
- `bloom_alignment`
- `skill_objectives`
- `core_operation`
- `bloom_progression`

**ALLOWED 字段**：共 35 个（模板 34 + 特殊 extra 1）

| 分类 | 字段 |
|------|------|
| 通用FM | name, book_id, book_name, chapter_num, confidence, confidence_note, bloom_level, source_chapter, source_from, aliases, tags |
| 基础信息 | solved_problem★, bloom_level_description★, skill_objectives★, domain, bloom_progression★, bloom_progression_analysis, bloom_alignment★ |
| 核心能力 | core_operation★, competency_standards, operation_boundaries |
| 实践支撑 | core_theoretical_support, tool_support, prerequisite_skills, common_errors_table |
| 实操演练 | operation_flowchart, operation_flow_analysis, typical_practical_cases |
| 关联知识 | related_concepts_knowledge, supported_scenarios, extended_skills, confusion_skill_compare |
| 知识脉络 | knowledge_context_diagram, diagram_analysis |
| **特殊 extra** | ✦ **related_knowledge_elements** — 构建系统用于关联 KE，不显示在渲染模板中 |

### 6. scene (scenario_template.md)

**⚠️ REQUIRED 字段中 4/6 不在模板 `{{xxx}}` 中！**

**REQUIRED 字段**：
- 在模板中: `scenario_description`, `node_descriptions`
- **不在模板中**: `bloom_level_description`, `bloom_alignment`, `bloom_progression`, `knowledge_context`

**ALLOWED 字段**：共 26 个

| 分类 | 字段 |
|------|------|
| 通用FM | name, book_id, book_name, chapter_num, bloom_level, confidence, confidence_note, source_chapter, source_from, aliases, tags |
| 场景概览 | scenario_type, domain, scenario_description★, scene_elements |
| 知识技能应用 | scene_concept_support, core_knowledge_support, core_skill_support, scene_ke_support |
| 工程实施 | workflow_diagram, node_descriptions★ |
| 典型案例 | typical_application_cases, related_scenes, confusion_scenario_compare |
| 知识脉络 | knowledge_context_diagram, diagram_analysis |
| 特殊 extra | (无) |

### 7. exercise (exercise_template.md)

**REQUIRED 字段** — 在模板中：
- `question`

**ALLOWED 字段**：共 15 个

| 分类 | 字段 |
|------|------|
| 通用FM | type, type_tag, name, book_id, book_name, chapter_num, confidence, confidence_note, bloom_level, source_chapter, source_from, aliases, tags |
| 内容 | question★, related_answer |
| 特殊 extra | (无) |

### 8. solution (eval_template.md)

**⚠️ REQUIRED 字段 `answer` 不在模板 `{{xxx}}` 中！**

**REQUIRED 字段**：
- `answer` — **不在模板 eval_template.md 的任何 `{{xxx}}` 占位符中**

**ALLOWED 字段**：共 32 个

| 分类 | 字段 |
|------|------|
| 通用FM | type, type_tag, name, book_id, book_name, chapter_num, bloom_level, confidence, confidence_note, source_chapter, source_from, aliases, tags |
| 题目原文 | question |
| 核心解答 | principle_steps, characteristics |
| 考点解析 | exam_points, common_mistakes, solving_tips |
| 难点深度 | difficulty_1_title, difficulty_1_content, difficulty_2_title, difficulty_2_content, difficulty_3_title, difficulty_3_content |
| 可视化 | flowchart_diagram, flowchart_steps, knowledge_loop_diagram, knowledge_loop_analysis |
| 关联资源 | related_concepts, exercise_link, exercise_name |
| 特殊 extra | (无) |

---

## 关键差异与发现

### 🔴 严重: REQUIRED 字段不在模板中

| 节点类型 | 字段 | 问题 |
|---------|------|------|
| **scene** | `bloom_level_description` | REQUIRED 但不在模板 `{{xxx}}` 中 |
| **scene** | `bloom_alignment` | REQUIRED 但不在模板 `{{xxx}}` 中 |
| **scene** | `bloom_progression` | REQUIRED 但不在模板 `{{xxx}}` 中 |
| **scene** | `knowledge_context` | REQUIRED 但不在模板 `{{xxx}}` 中（模板中有 `knowledge_context_diagram`，不完全等同） |
| **solution** | `answer` | REQUIRED 但 eval_template.md 中无 `{{answer}}`（模板中用 `{{question}}` 作为内容字段） |

### 🟡 中等: bd_extra_keys 特殊字段（构建系统内部使用）

| 节点类型 | 字段 | 用途推测 |
|---------|------|---------|
| **kp** | `related_knowledge_elements` | 构建系统自动注入的关联 KE 列表，用于知识图谱 |
| **kp** | `supported_skills_scenarios` | 构建系统自动注入的关联 SP/Scene 列表，用于知识图谱 |
| **sp** | `related_knowledge_elements` | 构建系统自动注入的关联 KE 列表，用于知识图谱 |

这些字段由构建系统 (`build_kb_files.py`) 自动填充，不在最终渲染的模板中显示。

### 🟢 其他发现

- 所有类型共享 `COMMON_FM` 标准前注字段：`type/type_tag/name/book_id/book_name/chapter_num/confidence/confidence_note/source_chapter/source_from/aliases/tags`
- concept/entity 额外有 `entity_type` 字段
- kp/sp/scene/exercise/solution 额外有 `bloom_level` 字段
- scene 的 `knowledge_context` 在 REQUIRED 中使用，但模板中使用的是 `knowledge_context_diagram` — 这两个字段名不完全一致
