---
template_version: v7.0
type: knowledge
type_tag: ["知识点"]
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
bloom_level: {{bloom_level}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
source_chapter: {{source_chapter}}
source_from: {{source_from}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

> 🎯 **{{solved_problem}}**  |  ⏱️ 约 30 分钟  |  📊 {{difficulty}}

<!-- @prompt solved_problem: 1-2句话，≥30字，直说"学完这个能干什么"。例："能独立用三要素法诊断EMC故障，不再盲目试错" -->

## 一、核心讲解

### 1. 理论基础

<!-- @prompt ≥200字。从底层原理讲起——不是罗列概念名，而是说清楚"为什么有这个知识点"。用3+个[[wikilink]]引用核心概念。 -->
{{theoretical_basis}}

### 2. 推导过程

<!-- @prompt Mermaid graph TD，≥8个节点。展示从输入→推导→结论的完整逻辑链。 -->
{{derivation_diagram}}

#### 推导说明

<!-- @prompt ≥5个Step。每Step含：①该节点干什么 ②为什么这样设计/推导 ③与其他节点关系 -->
{{derivation_analysis}}

### 3. 关键细节

<!-- @prompt ≥3条，每条≥40字。含具体数字+场景+后果。不是泛泛的"注意XX"。 -->
{{key_details}}

### 4. 核心知识要素

<!-- @prompt Markdown表格，≥3行。列: KE名称|关系|说明。每个KE用[[wikilink]]。 -->
{{core_knowledge_elements_table}}

## 二、动手实践

### 1. 典型例题 / 案例

<!-- @prompt ≥1道完整例题。结构：【题目】给定场景+参数→【分析】三要素拆解→【解法】分步操作→【验证】定量结果。 -->
{{typical_examples}}

### 2. 应用方法 / 步骤

<!-- @prompt ≥3步，每步≥30字。每步含：操作+工具+判断标准。不是"Step1 XXX"缩写。 -->
{{application_methods}}

### 3. 应用场景

<!-- @prompt ≥3个场景，每个≥40字。格式："场景名: 背景→本知识点如何应用→预期效果"。 -->
{{application_scenarios}}

### 4. 工程实践要点

<!-- @prompt ≥3条实操tips，每条≥30字。不是理论重复，是"现场干活时要注意的"。 -->
{{engineering_practices}}

### 5. ⚠️ 常见踩坑与辨析

<!-- @prompt Markdown对比表，≥2组。列：维度|方案A|方案B|选择建议。 -->
{{confusion_compare}}

## 三、知识地图

### 1. 关联知识网络

<!-- @prompt Mermaid graph TD，≥8个节点。展示KP与概念/KE/前置KP/SP/Scene的关联网络，用不同颜色区分节点类型。 -->
{{knowledge_context_diagram}}

#### 网络解析

<!-- @prompt ≥5段。对图中每类节点逐一说明：概念→KE→KP→SP→Scene。 -->
{{diagram_analysis}}

## 四、认知进阶

### 1. 布鲁姆认知层级

- **认知层级**：{{bloom_level}}
- **层级解读**：<!-- @prompt ≥100字。结合本知识点说明"理解层指什么、应用层指什么"。不是抄Bloom定义。 -->{{bloom_level_description}}

### 2. 学习递进链

<!-- @prompt Mermaid graph LR，5-6个节点。从知道→理解→应用→分析→评价→创造。 -->
{{bloom_progression}}

> **图谱解析**：<!-- @prompt ≥150字。逐层说明：①知道层(学什么,占时15%)→②理解层(核心,30%)→③应用层(关键输出,35%)→④分析层(进阶,15%)→⑤评价/创造层(专家,5%) -->
{{bloom_progression_analysis}}

### 3. 学习目标（Bloom 分层）

<!-- @prompt ≥3条，格式"层级: 具体能力描述"。每条≥30字。不是"理解XX概念"空话，而是"能用三要素法对给定超标频点完成根因定位"。 -->
{{learning_objectives}}

### 4. Bloom 对齐矩阵

<!-- @prompt Markdown表格，5-6行。列: 内容节|布鲁姆层级|认知要求。 -->
{{bloom_alignment}}

### 5. 能力要求

| 维度 | 要求 |
|:---|:---|
| 技能要求 | <!-- @prompt ≥3条，≥50字。应用本知识点需要什么前置技能（如"会使用频谱仪"）。 -->{{skill_requirements}} |
| 技能目标 | <!-- @prompt ≥3条，≥50字。学完后能做什么（如"能独立完成辐射发射超标诊断"）。 -->{{skill_objectives}} |

## 五、自学检验

<!-- @prompt 2-4道题。格式："1. 题目? (提示: ...)"。至少1道计算/操作题，至少1道概念辨析题。 -->
{{self_check_questions}}
