---
template_version: v1.0
type: entity
type_tag: {{type_tag}}
name: {{name}}
book_id: {{book_id}}
book_name: {{book_name}}
chapter_num: {{chapter_num}}
entity_type: {{entity_type}}
confidence: {{confidence}}
confidence_note: "{{confidence_note}}"
source_chapter: {{source_chapter}}
source_from: {{source_from}}
aliases: {{aliases}}
tags: {{tags}}
---

# {{name}}

## 一、实体信息

### 1. 实体名称

**{{name}}**

### 2. 实体类型

- **类型**：{{entity_type}}
  <!-- 类型枚举: person(人物)/device(设备)/standard(标准)/event(事件)/organization(机构)/location(地点)/other(其他) -->

### 3. 实体描述

<!-- @prompt 实体描述≥40字。设备写功能，标准写适用范围，人物写贡献。 -->
{{term_definition}}

### 4. 一句话说明

> <!-- @prompt 一句话概括。Markdown引文。 -->
{{definition_sentence}}
> 来源：第{{source_chapter}}章 §{{source_from}} 节

## 二、核心属性

### 1. 规格/参数

<!-- @prompt 设备:技术规格；标准:编号版本；人物:生卒年份。≥3条。 -->
{{key_parameters}}
<!-- 设备:技术规格/性能参数/工作频段; 标准:编号/版本/适用范围; 人物:生卒/国籍/贡献领域 -->

### 2. 功能/特征

<!-- @prompt 功能/特征描述。3-5条。 -->
{{features}}

### 3. 构成/组成

<!-- @prompt 设备:模块组成；组织:部门架构；标准:章节结构。 -->
{{structure}}
<!-- 设备:模块组成; 组织:部门架构; 标准:章节结构 -->

## 三、历史与发展

### 1. 发展/演进

<!-- @prompt ≥40字。发展演进描述。 -->
{{evolution}}

### 2. 重要时间节点

<!-- @prompt 格式：'YYYY: 事件描述'。≥2条。 -->
{{time_milestones}}
<!-- 格式: YYYY-MM-DD: 事件描述或YYYY: 事件描述 -->

## 四、关联网络

### 1. 关联实体

<!-- @prompt 格式：'- [[实体名]]: 关系描述'。≥2条。 -->
{{related_entities}}
<!-- 格式: - [[实体名]]: 关系描述 -->

### 2. 关联标准/规范

<!-- @prompt 关联标准，每个带[[wikilink]]。 -->
{{related_standards}}
<!-- 格式: - [[标准名]]: 关系描述 -->

### 3. 关联核心概念

<!-- @prompt 哪些概念引用了此实体，每个带[[wikilink]]。 -->
{{related_concepts}}
<!-- 哪些概念中引用了此实体 -->

## 五、应用场景

### 1. 典型应用

<!-- @prompt ≥40字。应用场景描述。 -->
{{application_scenarios}}

### 2. 典型产品/型号

<!-- @prompt 典型产品/型号列表。仅device类型填写。 -->
{{typical_products}}
<!-- 仅 device 类型填写 -->
