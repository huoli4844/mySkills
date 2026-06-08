---
template_version: v7.0
type: {{type}}
type_tag: {{type_tag}}
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
source_chapter: {{source_chapter}}
source_from: {{source_from}}
entity_type: {{entity_type}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

## 学习目标

<!-- @prompt 3-5条学习目标，每条≥30字。格式："能…（应用场景）"。具体能力描述而非概念罗列。 -->
{{learning_objectives}}

### 前置知识

<!-- @prompt 2-4个前置知识点，用[[wikilink]]关联。格式："- [[概念名]]: 为什么需要这个前置知识"。 -->
{{prerequisite_knowledge}}

### 自学检验

<!-- @prompt 2-4道自测题。至少1道分析/计算题。格式："1. 题目？（提示：参考答案）"。 -->
{{self_check_questions}}

## 一、基础信息

### 0. 解决的问题

<!-- @prompt 1-2句话，≥30字。直说"这个概念解决什么问题"。 -->
{{solved_problem}}

### 1. 术语定义

<!-- @prompt term_english: 标准英文术语，首字母大写。term_definition: 从源文摘抄标准定义，≥50字。用书名号引教材。 -->
**{{name}}**（{{term_english}}）{{term_definition}}

### 2、精确释义

> <!-- @prompt definition_sentence: 从源文精确获取完整的定义。含"是指"结构。Markdown引文格式。 -->
> {{definition_sentence}}
> 来源：第{{source_chapter}}章 §{{source_from}} 

### 3. 分类与学科归属

<!-- @prompt domain: 学科领域。格式："大领域/子领域"。classification: 分类名称，用于归类同类实体。 -->
- **学科领域**：{{domain}}
- **分类**：{{classification}}

### 4. 核心概念图谱

<!-- @prompt Mermaid graph TD，≤15节点。展示该概念的子概念/关联概念的层级结构。不可用mindmap格式（Obsidian不兼容）。 -->
{{core_concept_map}}

### 图谱解析

<!-- @prompt ≥5句话。逐节点解释上图的层次结构、关联关系和重点。 -->
{{core_concept_map_analysis}}

## 二、核心内容

### 1. 工作原理/构成要素

<!-- @prompt 3-5条，按逻辑顺序列出构成要素。"① 要素名: 说明"。每条≥20字。 -->
{{structure}}

### 2. 数学模型

<!-- @prompt 必须用$$...$$块级LaTeX包裹公式。从源文提取。无公式填"无"。每公式下方标注来源："*(来源：第N章 §X.X 式(N-XX))*" -->
{{mathematical_model}}

### 3. 关键参数

<!-- @prompt ≥3个关键参数。格式："参数名(符号/单位): 说明"。 -->
{{key_parameters}}

### 4. 物理含义/特征

<!-- @prompt 3-5个核心特征，用"①…②…"格式。每条≥20字。突出该概念区别于其他概念的特征。 -->
{{features}}

### 5. 技术分类

<!-- @prompt 技术分类名称。如"分类名称"，按该领域标准术语填写。 -->
{{tech_classification}}

## 三、应用与关联

### 1. 应用场景

<!-- @prompt 2-3个应用场景，每个≥50字。格式："场景名: 背景→解决的问题→与该概念的关系"。 -->
{{application_scenarios}}

### 2. 典型系统

<!-- @prompt ≥3个典型系统/设备。每个用[[wikilink]]。 -->
{{typical_systems}}

### 3. 使用价值

<!-- @prompt ≥60字。说明该概念的重要性和工程价值。 -->
{{value}}

### 4. 工程实践要点

<!-- @prompt 2-3条工程实践要点，每条≥30字。含具体数值和参数。不是理论重复。 -->
{{engineering_practices}}

### 5. 常见误区

<!-- @prompt 3-5个常见误区。格式："误区：…"。基于真实工程经验，不能泛泛而谈。 -->
{{common_misconceptions}}

### 6. 与相关概念的关系

<!-- @prompt ≥3个关联概念。每个带[[wikilink]]和一句话关系描述。 -->
{{related_concepts_relations}}

### 7. 相近概念辨析

<!-- @prompt 对比表格式。≥2组对比。列：维度|概念A|概念B|选择建议。 -->
{{confusion_compare}}

### 8. 发展/演进

<!-- @prompt ≥50字。简述该概念的发展历程或技术演进。 -->
{{evolution}}

### 9. 关联知识要素

<!-- @prompt YAML列表格式。关联的知识要素名称，≥3个。 -->
{{related_knowledge_elements}}

### 10. 上下游关系

<!-- @prompt 格式："上游：…；下游：…"。各≥20字。 -->
{{upstream_downstream}}
