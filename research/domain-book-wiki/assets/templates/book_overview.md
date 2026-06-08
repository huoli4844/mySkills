---
template_version: v4.0
type: book_overview
overview_level: L2
name: {{name}}
book_id: {{book_id}}
domain: {{domain}}
confidence: 0.90
confidence_note: "基于全书内容+知识图谱自动汇总生成"
reviewer: {{reviewer}}
review_date: {{review_date}}
aliases: []
tags: ["knowledge-base", "{{book_id}}", "index"]
cssclass: knowledge-base
---

# {{name}}

## 简介
{{description}}

## 📊 知识体系全景

### 知识链连通率
{{chain_connectivity}}

### 节点连接性统计
{{node_connectivity}}

## 🔍 图谱质量
{{graph_quality}}

## 🏆 核心知识节点
{{top_nodes}}

## 🗺 知识图谱全景
```mermaid
{{mindmap_content}}
```

## 📋 章节分布
{{chapter_distribution}}

## 🔗 推荐学习路径
{{learning_path}}

## 🎯 动态学习路径（Bloom 认知层级 + 前置依赖）
{{learning_path_v2}}

## 📑 索引导航

### 核心概念
{{concept_index}}

### 知识点
{{knowledge_index}}

### 技能点
{{skill_index}}

### 应用场景
{{scenario_index}}

## ⚠️ 待修复项
{{todo_items}}
- 生成日期: {{review_date}}
- 置信度: 0.90
- 置信度说明: 基于全书内容+知识图谱自动汇总生成
- 数据来源: KGraph 知识图谱引擎 v35.0
