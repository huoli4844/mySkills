---
template_version: v6.0
type: skill
type_tag: ["技能点"]
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
bloom_level: {{bloom_level}}
source_chapter: {{source_chapter}}
source_from: {{source_from}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

## 一、基础信息层

### 0. 解决的问题

<!-- @prompt 1-2句话。这个技能解决什么工程问题。≥30字。 -->
{{solved_problem}}

### 1. 技能点名称

- **名称**：{{name}}
- **布鲁姆认知层级**：{{bloom_level}}
- **层级解读**：<!-- @prompt ≥80字。结合该技能说明各层级含义。 -->
{{bloom_level_description}}
- **技能目标**：<!-- @prompt ≥3条。格式：'能…(场景/条件)'。 -->
{{skill_objectives}}
- **所属领域**：<!-- @prompt 学科领域。格式：'电磁兼容/子领域'。 -->
{{domain}}

### 2. 学习递进链

从理论知识到独立实操的认知递进路径：

<!-- @prompt Mermaid graph LR。理论知识到独立实操的递进路径。 -->
{{bloom_progression}}

> **认知递进解析**：<!-- @prompt ≥100字。逐层说明递进路径。 -->
{{bloom_progression_analysis}}

### 3. Bloom 对齐矩阵

操作步骤与布鲁姆六级的对应关系：

<!-- @prompt Markdown表格。操作步骤与Bloom六级对应。 -->
{{bloom_alignment}}

## 二、核心能力层

### 1. 核心操作内容

<!-- @prompt ≥5步核心操作，每步含操作+目的+注意。 -->
{{core_operation}}

### 2. 能力标准

<!-- @prompt 能力标准。达到什么水平算合格。含具体指标。 -->
{{competency_standards}}

### 3. 操作边界

<!-- @prompt 操作边界/限制条件。≥3条。 -->
{{operation_boundaries}}

## 三、实践支撑层

### 1. 核心理论支撑

<!-- @prompt ≥3个理论支撑。每个带[[wikilink]]和一句话关系。 -->
{{core_theoretical_support}}

### 2. 工具支撑

<!-- @prompt 需要的工具/设备/软件清单。 -->
{{tool_support}}

### 3. 前置技能点

<!-- @prompt 前置技能点。每个带[[wikilink]]。 -->
{{prerequisite_skills}}

### 4. 常见错误与纠正

<!-- @prompt Markdown表格。列: 常见错误|后果|正确做法。≥4行。 -->
{{common_errors_table}}

## 四、实操演练

### 1. 操作流程图

<!-- @prompt Mermaid flowchart TD。操作流程完整展示。 -->
{{operation_flowchart}}

#### 操作流程说明

<!-- @prompt ≥5步。对流程图的分步说明。 -->
{{operation_flow_analysis}}

### 2. 典型实操案例

<!-- @prompt ≥1个完整实操案例。含参数+过程+结果。 -->
{{typical_practical_cases}}

## 五、关联知识层

### 1. 支撑的理论知识

<!-- @prompt 关联概念，每个带[[wikilink]]和关系描述。 -->
{{related_concepts_knowledge}}
<!-- 关联的概念/知识点/知识要素，每个带wikilink和一句话关系说明 -->

### 2. 支撑的场景

<!-- @prompt 支撑哪些场景，每个带[[wikilink]]。 -->
{{supported_scenarios}}

### 3. 延伸技能

<!-- @prompt 延伸/进阶技能方向。≥3个。 -->
{{extended_skills}}

### 4. 易混淆技能辨析

<!-- @prompt 易混淆技能辨析。对比表。≥2组。 -->
{{confusion_skill_compare}}

## 六、知识脉络

<!-- @prompt Mermaid graph TD。知识脉络图。 -->
{{knowledge_context_diagram}}

### 知识脉络图解析

<!-- @prompt ≥5段。逐节点解析知识脉络图。 -->
{{diagram_analysis}}
