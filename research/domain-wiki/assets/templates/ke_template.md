---
template_version: v1.0
type: knowledge-element
type_tag: {{type_tag}}
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
source_chapter: {{source_chapter}}
source_from: {{source_from}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

## 一、术语定义

### 1. 术语名称

**{{name}}**（<!-- @prompt 标准英文术语，首字母大写。 -->
{{term_english}}）

### 2. 精确定义

<!-- @prompt 从源文摘抄标准定义。≥40字。 -->
{{term_definition}}

### 3. 一句话说明

> <!-- @prompt 一句话概括。含'是指'。Markdown引文。 -->
{{definition_sentence}}
> 来源：第{{source_chapter}}章 §{{source_from}} 节

### 4. 学科归属

- **学科领域**：<!-- @prompt 学科领域。格式：'电磁兼容/子领域'。 -->
{{domain}}

## 二、数学描述

### 1. 数学公式

<!-- 所有公式必须用 $$...$$ 块级 LaTeX 包裹。无公式时填"无"。 -->
<!-- @prompt 必须用$$…$$包裹LaTeX公式。无公式填'无'。 -->
<!-- @prompt 必须用$$…$$包裹LaTeX公式。无公式填'无'。 -->
{{mathematical_model}}

### 2. 参数说明

<!-- @prompt ≥3个关键参数，每个带单位。 -->
{{key_parameters}}

### 3. 物理含义

<!-- @prompt 3-5个特征。'①…②…'格式。 -->
{{features}}

## 三、跨概念引用

### 1. 被以下核心概念引用

<!-- @prompt 哪些核心概念引用了此KE，每个带[[wikilink]]。 -->
{{related_concepts_relations}}

### 2. 关联知识要素

<!-- @prompt YAML list格式。关联的KE名称列表。 -->
{{related_knowledge_elements}}

### 3. 相近概念辨析

<!-- @prompt 对比相近KE。Markdown对比表。 -->
{{confusion_compare}}

## 四、扩展信息

### 1. 典型应用场景

<!-- @prompt 2-3个应用场景，每个≥40字。 -->
{{application_scenarios}}

### 2. 发展/演进

<!-- @prompt ≥40字。发展历程简述。 -->
{{evolution}}
