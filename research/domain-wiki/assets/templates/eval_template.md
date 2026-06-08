---
template_version: v6.1
type: {{type}}
type_tag: {{type_tag}}
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

## 一、题目原文

<!-- @prompt 习题原文。从源文直接抄录。 -->
{{question}}

## 二、核心解答

### 2.1 实现原理（流程化拆解）

<!-- @prompt ≥5步解题步骤。流程化拆解。每步含公式/操作+说明。 -->
{{principle_steps}}

### 2.2 主要特点（维度化归纳）

<!-- @prompt ≥3个特点归纳。用维度归纳法（维度一…维度二…）。 -->
{{characteristics}}

## 三、考点与易错点解析

### 3.1 核心考点

<!-- @prompt ≥3个核心考点。明确写出考查的知识点。 -->
{{exam_points}}

### 3.2 常见错误（避坑指南）

<!-- @prompt ≥3个常见错误。格式：'① 错误: 说明→正确做法'。 -->
{{common_mistakes}}

### 3.3 解题技巧

<!-- @prompt ≥3条解题技巧。含速算、验算、记忆口诀等。 -->
{{solving_tips}}

## 四、难点深度解析

### 4.1 <!-- @prompt 难点1标题。直接描述技术难点。 -->
{{difficulty_1_title}}

<!-- @prompt ≥60字。难点1的详细解析。 -->
{{difficulty_1_content}}

### 4.2 <!-- @prompt 难点2标题。 -->
{{difficulty_2_title}}

<!-- @prompt ≥60字。难点2的详细解析。 -->
{{difficulty_2_content}}

### 4.3 <!-- @prompt 难点3标题。 -->
{{difficulty_3_title}}

<!-- @prompt ≥60字。难点3的详细解析。 -->
{{difficulty_3_content}}

## 五、可视化解题逻辑

### 5.1 实现流程思维导图

<!-- @prompt Mermaid graph TD。解题流程思维导图。 -->
{{flowchart_diagram}}

**实现流程分步说明：**

<!-- @prompt ≥5步。流程图的分步文字说明。 -->
{{flowchart_steps}}

### 5.2 知识闭环体系

<!-- @prompt Mermaid graph TD。知识闭环图。本题与全章知识点关系。 -->
{{knowledge_loop_diagram}}

### 知识闭环图解析

<!-- @prompt ≥100字。知识闭环图文分析。 -->
{{knowledge_loop_analysis}}

## 六、关联资源

### 6.1 核心知识点 / 概念

<!-- @prompt 关联的核心概念/知识点。每个带[[wikilink]]。≥3个。 -->
{{related_concepts}}

### 6.2 关联习题

- [[<!-- @prompt 自动填充。关联的习题wikilink。 -->
{{exercise_link}}|<!-- @prompt 自动填充。关联的习题名称。 -->
{{exercise_name}}]]
