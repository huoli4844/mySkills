# YAML bd 字段名 ↔ 模板变量完整对照表（v41.1 精校版）

> ⚠️ Agent 编写 YAML 时，bd 的 key 必须与模板 `{{变量}}` 完全一致，否则占位符不替换。
> 本对照表基于 `assets/templates/*.md` 实际 `{{变量}}` 提取，无无效字段。

---

## FrontMatter 公共字段（所有类型通用）

| bd key | 模板变量 | 说明 |
|:-------|:--------|:-----|
| `name` | `{{name}}` | 名称 |
| `book_id` | `{{book_id}}` | 书 ID |
| `book_name` | `{{book_name}}` | 书名 |
| `chapter_num` | `{{chapter_num}}` | 章号 |
| `confidence` | `{{confidence}}` | 置信度 (0.0-1.0) |
| `confidence_note` | `{{confidence_note}}` | 置信度说明 |
| `source_chapter` | `{{source_chapter}}` | 来源章号 |
| `source_from` | `{{source_from}}` | 来源节号 |
| `type` | `{{type}}` | 类型名 |
| `type_tag` | `{{type_tag}}` | 类型标签 |
| `aliases` | `{{aliases}}` | 别名 |
| `tags` | `{{tags}}` | 标签列表 |
| `bloom_level` | `{{bloom_level}}` | Bloom 层级（部分类型） |

---

## 概念类 (concept_template.md, quality_key=concept)

| bd key | 模板变量 | 必填 | 说明 |
|:-------|:--------|:---:|:-----|
| `solved_problem` | `{{solved_problem}}` | | **v46.1 新增** 本概念解决的核心问题（1-2句话） |
| `term_english` | `{{term_english}}` | ✅ | 英文术语 |
| `term_definition` | `{{term_definition}}` | ✅ | 术语定义 |
| `definition_sentence` | `{{definition_sentence}}` | ✅ | 精准释义（前120字可在正文逐字检索） |
| `definition_source` | `{{definition_source}}` | ✅ | 出处标注（来源：第N章 §节号） |
| `domain` | `{{domain}}` | ✅ | 学科领域 |
| `classification` | `{{classification}}` | ✅ | 分类 |
| `entity_type` | `{{entity_type}}` | | 实体类型 |
| `core_concept_map` | `{{core_concept_map}}` | ✅ | Mermaid 图谱 |
| `core_concept_map_source` | `{{core_concept_map_source}}` | | 图谱来源 |
| `core_concept_map_analysis` | `{{core_concept_map_analysis}}` | ✅ | 图谱解析（≥100字） |
| `structure` | `{{structure}}` | ✅ | 工作原理/构成要素（≥100字） |
| `mathematical_model` | `{{mathematical_model}}` | | 数学模型 |
| `tech_classification` | `{{tech_classification}}` | | 技术分类 |
| `formula_references` | `{{formula_references}}` | | 公式引用（仅 `$$...$$` LaTeX 或 `无`） |
| `figure_references` | `{{figure_references}}` | | 图引用 |
| `additional_explanations` | `{{additional_explanations}}` | | 补充说明 |
| `application_scenarios` | `{{application_scenarios}}` | ✅ | 应用场景（2-4项，每项≥50字） |
| `typical_systems` | `{{typical_systems}}` | | 典型系统 |
| `engineering_practices` | `{{engineering_practices}}` | ✅ | 工程实践（≥2条，每条≥30字） |
| `common_misconceptions` | `{{common_misconceptions}}` | ✅ | 常见误区（≥1条） |
| `related_concepts_relations` | `{{related_concepts_relations}}` | ✅ | 关联概念关系（≥2条，含wikilink） |
| `confusion_compare` | `{{confusion_compare}}` | | 相近概念辨析 |
| `evolution` | `{{evolution}}` | | 发展演进（≥50字） |
| `references` | `{{references}}` | | 参考资料 |
| `related_knowledge_elements` | `{{related_knowledge_elements}}` | ✅ | 关联KE wikilink（≥1条） |
| `learning_objectives` | `{{learning_objectives}}` | ✅ | 学习目标（Bloom 分层，≥3条） |
| `prerequisite_knowledge` | `{{prerequisite_knowledge}}` | ✅ | 前置知识 wikilink |
| `self_check_questions` | `{{self_check_questions}}` | ✅ | 自学检验思考题 |

---

## 知识要素 (concept_template.md, quality_key=concept/ke)

> 复用概念模板，质量检查降低（confidence=0.85）

| bd key | 模板变量 | 说明 |
|:-------|:--------|:-----|
| `term_definition` | `{{term_definition}}` | 定义内容 |
| `term_english` | `{{term_english}}` | 英文术语 |
| `classification` | `{{classification}}` | 分类 |
| `structure` | `{{structure}}` | 构成 |
| `key_parameters` | `{{key_parameters}}` | 关键参数 |
| `features` | `{{features}}` | 特征（≥100字） |
| `application_scenarios` | `{{application_scenarios}}` | 应用场景（≥3项） |
| `value` | `{{value}}` | 价值意义 |
| `upstream_downstream` | `{{upstream_downstream}}` | 上下游关系 |
| `related_knowledge_elements` | `{{related_knowledge_elements}}` | 关联KE |
| `references` | `{{references}}` | 参考资料 |
| `domain` | `{{domain}}` | 学科领域 |

---

## 实体 (concept_template.md, quality_key=concept/entity)

> 复用概念模板，entity_type 区分实体类型

| bd key | 模板变量 | 说明 |
|:-------|:--------|:-----|
| `entity_type` | `{{entity_type}}` | 实体类型标签 |
| `term_definition` | `{{term_definition}}` | 实体描述 |
| `structure` | `{{structure}}` | 构成/参数 |
| `application_scenarios` | `{{application_scenarios}}` | 应用上下文 |
| `features` | `{{features}}` | 关键特征 |
| `related_knowledge_elements` | `{{related_knowledge_elements}}` | 关联KE |

---

## 知识点 (knowledge_template.md v6.0, quality_key=knowledge)

| bd key | 模板变量 | 必填 | 说明 |
|:-------|:--------|:---:|:-----|
| `solved_problem` | `{{solved_problem}}` | ✅ | 本知识点解决的核心问题 |
| `prerequisite_concepts` | `{{prerequisite_concepts}}` | | **v48.0**: 前置概念清单(本KP整合的核心概念) |
| `learning_objectives` | `{{learning_objectives}}` | ✅ | 学习目标 |
| `domain` | `{{domain}}` | ✅ | 领域标签 |
| `bloom_level_description` | `{{bloom_level_description}}` | ✅ | Bloom 层级解读 |
| `bloom_progression` | `{{bloom_progression}}` | ✅ | 学习递进链 Mermaid |
| `bloom_progression_analysis` | `{{bloom_progression_analysis}}` | ✅ | 递进链图谱解析 |
| `bloom_alignment` | `{{bloom_alignment}}` | ✅ | Bloom 对齐矩阵表格 |
| `skill_requirements` | `{{skill_requirements}}` | | **v46.1 新增** 应用本知识点需要的前置技能 |
| `skill_objectives` | `{{skill_objectives}}` | | **v46.1 新增** 学完后可达到的技能目标 |
| `theoretical_basis` | `{{theoretical_basis}}` | ✅ | 理论基础（≥200字，≥3 wikilink） |
| `key_details` | `{{key_details}}` | ✅ | 关键细节（≥3条） |
| `derivation_diagram` | `{{derivation_diagram}}` | ✅ | 推导图 Mermaid（≥8节点） |
| `derivation_analysis` | `{{derivation_analysis}}` | ✅ | 推导说明（≥5 Step，不可填"无"） |
| `core_knowledge_elements_table` | `{{core_knowledge_elements_table}}` | ✅ | KE 清单表格（≥3条） |
| `application_scenarios` | `{{application_scenarios}}` | ✅ | 应用场景（≥3项） |
| `application_methods` | `{{application_methods}}` | ✅ | 应用方法（≥3步） |
| `typical_examples` | `{{typical_examples}}` | ✅ | 典型例题（≥1，参数→推导→验证） |
| `exam_and_misconceptions` | `{{exam_and_misconceptions}}` | ✅ | **v48.0 合并**: 考点+考试例题+考点解析+常见误解辨析 |
| `related_concepts` | `{{related_concepts}}` | ✅ | 关联概念 wikilink（≥3） |
| `related_knowledge_elements` | `{{related_knowledge_elements}}` | ✅ | 关联KE wikilink（≥2） |
| `supported_skills_scenarios` | `{{supported_skills_scenarios}}` | ✅ | 支撑技能/场景（≥1） |
| `prerequisite_knowledge` | `{{prerequisite_knowledge}}` | ✅ | 前置知识（⚠ 非 `prerequisites`） |
| `confusion_compare_table` | `{{confusion_compare_table}}` | ✅ | 易混淆对比表（≥1组） |
| `knowledge_context_diagram` | `{{knowledge_context_diagram}}` | ✅ | 知识脉络图 Mermaid（≥8节点） |
| `diagram_analysis` | `{{diagram_analysis}}` | ✅ | 脉络图解析（≥5段，≥500字） |
| `aliases` | `{{aliases}}` | | 别名 |

---

## 技能点 (skill_template.md v6.0, quality_key=skill)

| bd key | 模板变量 | ⚠ 错误写法 |
|:-------|:--------|:----------|
| `solved_problem` | `{{solved_problem}}` | **v48.0**: 本技能解决的工程问题 |
| `skill_objectives` | `{{skill_objectives}}` | ❌ `skill_description` |
| `core_operation` | `{{core_operation}}` | ❌ `operation_steps` |
| `competency_standards` | `{{competency_standards}}` | ❌ `assessment_criteria` |
| `operation_boundaries` | `{{operation_boundaries}}` | ❌ `common_errors` |
| `core_theoretical_support` | `{{core_theoretical_support}}` | ❌ `supported_by_knowledge` |
| `tool_support` | `{{tool_support}}` | ❌ `tools_required` |
| `applicable_scenarios` | `{{applicable_scenarios}}` | |
| `prerequisite_skills` | `{{prerequisite_skills}}` | ❌ `prerequisite_knowledge` |
| `extended_skills` | `{{extended_skills}}` | ❌ `related_skills` |
| `typical_practical_cases` | `{{typical_practical_cases}}` | ❌ `typical_cases` |
| `confusion_skill_compare` | `{{confusion_skill_compare}}` | |
| `supported_scenarios` | `{{supported_scenarios}}` | ❌ `outputs_to_scenario` |
| `evolution` | `{{evolution}}` | |
| `operation_flowchart` | `{{operation_flowchart}}` | Mermaid 或说明 |
| `operation_flow_analysis` | `{{operation_flow_analysis}}` | |
| `common_errors_table` | `{{common_errors_table}}` | 常见错误表 |
| `knowledge_context_diagram` | `{{knowledge_context_diagram}}` | Mermaid 或说明 |
| `diagram_analysis` | `{{diagram_analysis}}` | |
| `related_concepts_knowledge` | `{{related_concepts_knowledge}}` | |
| `domain` | `{{domain}}` | |

---

## 应用场景 (scenario_template.md v6.0, quality_key=scenario)

| bd key | 模板变量 | ⚠ 错误写法 |
|:-------|:--------|:----------|
| `scenario_type` | `{{scenario_type}}` | ❌ `scene_type` |
| `scenario_description` | `{{scenario_description}}` | ❌ `scene_description` |
| `node_descriptions` | `{{node_descriptions}}` | **v48.0**: 每流程节点一句话描述 |
| `overall_solution` | `{{overall_solution}}` | **v48.0**: 完整解题闭环 |
| `scene_elements` | `{{scene_elements}}` | ❌ `objectives` |
| `constraints` | `{{constraints}}` | |
| `technical_environment` | `{{technical_environment}}` | ❌ `background` |
| `boundary_conditions` | `{{boundary_conditions}}` | ❌ `constraints`（已用） |
| `core_knowledge_support` | `{{core_knowledge_support}}` | |
| `core_skill_support` | `{{core_skill_support}}` | |
| `scene_concept_support` | `{{scene_concept_support}}` | |
| `scene_ke_support` | `{{scene_ke_support}}` | |
| `related_scenes` | `{{related_scenes}}` | |
| `confusion_scenario_compare` | `{{confusion_scenario_compare}}` | |
| `evolution` | `{{evolution}}` | |
| `knowledge_context_diagram` | `{{knowledge_context_diagram}}` | Mermaid 或说明 |
| `workflow_diagram` | `{{workflow_diagram}}` | Mermaid 或说明 |
| `workflow_analysis` | `{{workflow_analysis}}` | |
| `diagram_analysis` | `{{diagram_analysis}}` | |
| `typical_application_cases` | `{{typical_application_cases}}` | |
| `domain` | `{{domain}}` | |

---

## 评测类 (eval_template.md, quality_key=eval/exercise 或 eval/solution)

> ⚠️ v41.1 新增，此前完全缺失

### 习题 (quality_key=eval/exercise, confidence=0.65)

| bd key | 模板变量 | 说明 |
|:-------|:--------|:-----|
| `question` | `{{question}}` | 习题内容 |
| `related_answer` | `{{related_answer}}` | 关联解答 wikilink |
| `exercise_link` | `{{exercise_link}}` | 习题链接 |
| `exercise_name` | `{{exercise_name}}` | 习题名称 |

### 解答 (quality_key=eval/solution, confidence=0.85)

| bd key | 模板变量 | 必填 | 说明 |
|:-------|:--------|:---:|:-----|
| `principle_steps` | `{{principle_steps}}` | ✅ | 实现原理（≥400字） |
| `characteristics` | `{{characteristics}}` | ✅ | 主要特点（≥4维 + 表格） |
| `exam_points` | `{{exam_points}}` | ✅ | 核心考点（≥4个） |
| `common_mistakes` | `{{common_mistakes}}` | ✅ | 常见错误（≥3条×50-80字） |
| `solving_tips` | `{{solving_tips}}` | ✅ | 解题技巧（≥3条） |
| `difficulty_1_title` | `{{difficulty_1_title}}` | ✅ | 难点1标题 |
| `difficulty_1_content` | `{{difficulty_1_content}}` | ✅ | 难点1深度解析（≥200字） |
| `difficulty_2_title` | `{{difficulty_2_title}}` | ✅ | 难点2标题 |
| `difficulty_2_content` | `{{difficulty_2_content}}` | ✅ | 难点2深度解析（≥200字） |
| `difficulty_3_title` | `{{difficulty_3_title}}` | ✅ | 难点3标题 |
| `difficulty_3_content` | `{{difficulty_3_content}}` | ✅ | 难点3深度解析（≥200字） |
| `flowchart_diagram` | `{{flowchart_diagram}}` | ✅ | 解题流程图 Mermaid ⚠ 必填 |
| `flowchart_steps` | `{{flowchart_steps}}` | ✅ | 流程分步说明 |
| `knowledge_loop_diagram` | `{{knowledge_loop_diagram}}` | ✅ | 知识闭环图 Mermaid ⚠ 必填 |
| `knowledge_loop_analysis` | `{{knowledge_loop_analysis}}` | ✅ | 闭环图解析（≥200字） |
| `related_concepts` | `{{related_concepts}}` | ✅ | 核心知识点 wikilink（≥3） |
| `source_reference` | `{{source_reference}}` | ✅ | 引用出处 |

---

## 索引/总揽类（不通过 Agent 生成，脚本自动填充）

| 模板 | 模板变量数 | 说明 |
|:-----|:--------:|:-----|
| `book_overview.md` | 26 | L2 单书总揽 |
| `domain_overview.md` | 21 | L3 领域总控 |
| `kb_overview.md` | 20 | L4 知识库总控 |
| `concept_index.md` | 18 | 概念索引 |
| `knowledge_index.md` | 13 | 知识点索引 |
| `skill_index.md` | 11 | 技能点索引 |
| `scenario_index.md` | 11 | 场景索引 |

---

## 验证命令

生成 YAML 前确认模板字段：
```bash
grep -o '{{[^}]*}}' assets/templates/<type>.md | sort -u
```

生成 YAML 后验证：
```bash
python3 scripts/schema.py .dag/第N章/data/<type>.yaml
python3 scripts/validate_chapter_data.py --chapter N --fix
```

---

**版本**: v41.1  
**变更**: 精校全部模板字段，删除 18 个无效字段，新增 eval_template 节，补全 KE/实体字段  
**最后更新**: 2026-05-30
