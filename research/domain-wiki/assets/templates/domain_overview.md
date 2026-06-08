---
template_version: v4.0
type: domain_overview
overview_level: L3
name: {{name}}
domain_id: {{domain_id}}
confidence: 0.85
confidence_note: "基于该领域下所有书籍+知识图谱汇总生成"
reviewer: {{reviewer}}
review_date: {{review_date}}
aliases: []
tags: ["knowledge-base", "{{book_id}}", "index"]
cssclass: knowledge-base
---

# {{name}} — 领域总揽（L3）

## 领域简介
{{description}}

## 📚 领域书籍
{{book_index}}

## 🌐 领域知识体系

### 跨书知识链
{{cross_book_chain}}

### 跨书概念冲突检测
{{cross_book_conflicts}}

### 领域节点连接性
{{domain_connectivity}}

## 🔗 跨书知识关联

### 跨书概念对齐
{{cross_book_alignment}}

### 知识孤岛检测
{{knowledge_islands}}

## 🗺 领域知识图谱
```mermaid
{{mindmap_content}}
```

## 🎯 领域学习路径
{{learning_path}}

## 🛠 综合技能树
{{combined_skills}}

## 🏗 综合应用场景
{{combined_scenarios}}

## 📑 领域索引导航

### 核心概念
{{concept_index}}

### 知识点
{{knowledge_index}}

### 技能点
{{skill_index}}

### 应用场景
{{scenario_index}}

## 📈 统计信息
- 书籍数: {{book_count}}
- 总核心概念数: {{total_concept_count}}
- 总知识点数: {{total_knowledge_count}}
- 总技能点数: {{total_skill_count}}
- 总应用场景数: {{total_scenario_count}}

## 溯源
- 生成日期: {{review_date}}
- 置信度: 0.85
- 置信度说明: 基于该领域下所有书籍+知识图谱汇总生成
- 数据来源: KGraph 知识图谱引擎 v35.0
