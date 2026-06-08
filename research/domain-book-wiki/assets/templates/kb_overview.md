---
template_version: v4.0
type: kb_overview
overview_level: L4
name: {{name}}
kb_id: {{kb_id}}
confidence: 0.85
confidence_note: "基于全知识库所有领域+知识图谱汇总生成"
reviewer: {{reviewer}}
review_date: {{review_date}}
aliases: []
tags: ["knowledge-base", "{{book_id}}", "index"]
cssclass: knowledge-base
---

# {{name}} — 知识库总揽（L4）

## 知识库简介
{{description}}

## 🌍 领域总览
{{domain_index}}

## 🔬 全库知识结构

### 全库节点连接性
{{kb_connectivity}}

### 全库知识链完整性
{{kb_chain}}

## 🌉 跨领域桥接
{{cross_domain_bridges}}

## 🗺 知识库全景图谱
```mermaid
{{mindmap_content}}
```

## 🧭 全库学习路径
{{learning_path}}

## 🏛 跨领域综合技能
{{combined_skills}}

## 🏗 跨领域综合场景
{{combined_scenarios}}

## 📑 全库索引导航

### 核心概念
{{concept_index}}

### 知识点
{{knowledge_index}}

### 技能点
{{skill_index}}

### 应用场景
{{scenario_index}}

## 📈 统计信息
- 领域数: {{domain_count}}
- 总书籍数: {{total_book_count}}
- 总核心概念数: {{total_concept_count}}
- 总知识点数: {{total_knowledge_count}}
- 总技能点数: {{total_skill_count}}
- 总应用场景数: {{total_scenario_count}}

## 溯源
- 生成日期: {{review_date}}
- 置信度: 0.85
- 置信度说明: 基于全知识库所有领域+知识图谱汇总生成
- 数据来源: KGraph 知识图谱引擎 v35.0
