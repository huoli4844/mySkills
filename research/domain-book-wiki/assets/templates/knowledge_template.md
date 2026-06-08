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

<!-- solved_problem: 1-2句话，≥30字，直说"学完这个能干什么"。例："能独立用三要素法诊断EMC故障，不再盲目试错" -->

## 一、核心讲解

### 1. 理论基础

{{theoretical_basis}}

<!-- theoretical_basis: ≥200字。从底层原理讲起——不是罗列概念名，而是说清楚"为什么有这个知识点"。
用 3+ 个 [[wikilink]] 引用核心概念。例: 三要素理论→缺一不可原理→为什么是EMC所有方法论的根基 -->

### 2. 推导过程

{{derivation_diagram}}

<!-- derivation_diagram: Mermaid graph TD，≥8个节点。展示从输入→推导→结论的完整逻辑链 -->

#### 推导说明

{{derivation_analysis}}

<!-- derivation_analysis: 对图中每个关键节点逐一解释。≥5个Step，每Step含:
- 该节点干什么(1句)
- 为什么这样设计/推导(1句)
- 与其他节点的关系(1句)
例: Step1"频率维度分析"→为什么频率排第一? 因为频率直接决定耦合方式(>30MHz辐射/<30MHz传导) -->

### 3. 关键细节

{{key_details}}

<!-- key_details: ≥3条，每条≥40字。不是泛泛的"注意XX"，而是具体数字+场景+后果。
例: "125MHz窄带尖峰→时钟源辐射(不是开关电源); 150kHz-30MHz宽带底噪→开关电源传导干扰" -->

### 4. 核心知识要素

{{core_knowledge_elements_table}}

<!-- core_knowledge_elements_table: Markdown表格，≥3行。列: KE名称|关系|说明。每个KE用[[wikilink]] -->

## 二、动手实践

### 1. 典型例题 / 案例

{{typical_examples}}

<!-- typical_examples: ≥1道完整例题，结构:
【题目】给定场景+参数→【分析】三要素拆解(源/路径/敏感)→【解法】分步操作→【验证】定量结果。
例: "125MHz超标10-15dB→诊断为时钟辐射→加RC滤波+地平面优化→降18dB通过" -->

### 2. 应用方法 / 步骤

{{application_methods}}

<!-- application_methods: ≥3步，每步≥30字。不是"Step1 XXX"的缩写，而是每步包含: 操作+工具+判断标准。
例: "Step1频谱分析: 设置RBW=9kHz(传导)/120kHz(辐射)，扫描150kHz-1GHz，标记所有超标6dB以上的频点" -->

### 3. 应用场景

{{application_scenarios}}

<!-- application_scenarios: ≥3个场景，每个≥40字。格式: "场景名: 背景→本知识点如何应用→预期效果" -->

### 4. 工程实践要点

{{engineering_practices}}

<!-- engineering_practices: ≥3条实操tips，每条≥30字。不是理论重复，是"现场干活时要注意的" -->

### 5. ⚠️ 常见踩坑与辨析

{{confusion_compare}}

<!-- confusion_compare: Markdown对比表，≥2组对比。列: 对比维度|方案A|方案B|选择建议。
例: "辐射超标→加屏蔽罩||辐射超标→改PCB布局 →频率<200MHz改布局成本低,>1GHz屏蔽罩更快" -->

## 三、知识地图

### 1. 关联知识网络

{{knowledge_context_diagram}}

<!-- knowledge_context_diagram: Mermaid graph TD，≥8个节点。展示KP与概念/KE/前置KP/SP/场景的关联网络，用不同颜色区分节点类型 -->

#### 网络解析

{{diagram_analysis}}

<!-- diagram_analysis: ≥5段。对图中每类节点逐一说明——概念层(理论来源)→KE层(知识要素)→KP层(前置/后续知识点)→SP层(支撑的技能)→Scene层(应用场景) -->

## 四、认知进阶

### 1. 布鲁姆认知层级

- **认知层级**：{{bloom_level}}
- **层级解读**：{{bloom_level_description}}

<!-- bloom_level_description: ≥100字。不是抄Bloom定义，是结合本知识点具体说明"在这个知识点里，理解层指什么，应用层指什么" -->

### 2. 学习递进链

{{bloom_progression}}

<!-- bloom_progression: Mermaid graph LR，5-6个节点，从知道→理解→应用→分析→评价→创造 -->

> **图谱解析**：{{bloom_progression_analysis}}

<!-- bloom_progression_analysis: ≥150字。逐层说明: ①知道层(学什么,占时15%)→②理解层(核心,30%)→③应用层(关键输出,35%)→④分析层(进阶,15%)→⑤评价/创造层(专家,5%) -->

### 3. 学习目标（Bloom 分层）

{{learning_objectives}}

<!-- learning_objectives: ≥3条，格式"层级: 具体能力描述"。每条≥30字。不是"理解XX概念"这种空话，而是"能用三要素法对给定的超标频点完成根因定位" -->

### 4. Bloom 对齐矩阵

{{bloom_alignment}}

<!-- bloom_alignment: Markdown表格，5-6行。列: 内容节|布鲁姆层级|认知要求 -->

### 5. 能力要求

| 维度 | 要求 |
|:---|:---|
| 技能要求 | {{skill_requirements}} |
| 技能目标 | {{skill_objectives}} |

<!-- skill_requirements: ≥3条，≥50字。应用本知识点需要什么前置技能(如"会使用频谱仪") -->
<!-- skill_objectives: ≥3条，≥50字。学完后能做什么(如"能独立完成辐射发射超标诊断") -->

## 五、自学检验

{{self_check_questions}}

<!-- self_check_questions: 2-4道题。格式: "1. 题目? (提示: ...)"。至少1道计算/操作题，至少1道概念辨析题 -->
