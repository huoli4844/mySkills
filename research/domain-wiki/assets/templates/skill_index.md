---
template_version: v2.0
type: skill_index
name: "技能点索引"
book_id: {{book_id}}
confidence: 0.90
confidence_note: "基于全书技能点汇总生成"
reviewer: {{reviewer}}
review_date: {{review_date}}
aliases: []
tags: []
---

# 技能点索引

## 按技能层级分类

### L1 操作技能
{{skills_l1}}

### L2 任务技能
{{skills_l2}}

## 按难度分类

### 易
{{skills_easy}}

### 中
{{skills_medium}}

### 难
{{skills_hard}}

## 按章节分类
{{by_chapter}}

## 统计
- 总技能点数: {{total_count}}
- 按层级分布: {{level_distribution}}
