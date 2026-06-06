---
template_version: v2.0
type: knowledge_index
name: "知识点索引"
book_id: {{book_id}}
confidence: 0.90
confidence_note: "基于全书知识点汇总生成"
reviewer: {{reviewer}}
review_date: {{review_date}}
aliases: []
tags: []
---

# 知识点索引

## 按认知层级分类

### 记忆级
{{knowledge_remember}}

### 理解级
{{knowledge_understand}}

### 应用级
{{knowledge_apply}}

### 分析级
{{knowledge_analyze}}

## 按难度分类

### 易
{{knowledge_easy}}

### 中
{{knowledge_medium}}

### 难
{{knowledge_hard}}

## 按章节分类
{{by_chapter}}

## 统计
- 总知识点数: {{total_count}}
- 按认知层级分布: {{bloom_distribution}}
