---
template_version: v7.0
type: scenario
type_tag: ["应用场景"]
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

## 一、场景概览

### 1. 场景名称

- **名称**：{{name}}
- **场景类型**：{{scenario_type}}
- **布鲁姆认知层级**：{{bloom_level}}
- **所属领域**：{{domain}}

### 2. 场景背景与目标

{{scenario_description}}
<!-- 这个场景是什么工程背景、要达成什么工程目标 -->

### 3. 场景要素

{{scene_elements}}
<!-- 干扰源/敏感设备/耦合路径/约束条件等 -->

## 二、知识与技能应用

### 1. 涉及的核心概念

{{scene_concept_support}}
<!-- 哪些核心概念支撑本场景 -->

### 2. 应用的知识点

{{core_knowledge_support}}
<!-- 本场景调用了哪些知识点，每个一句话说明用途 -->

### 3. 调用的技能点

{{core_skill_support}}
<!-- 本场景需要哪些技能点，每个一句话说明用途 -->

### 4. 需要的知识要素

{{scene_ke_support}}

## 三、工程实施流程

### 1. 工作流程图

{{workflow_diagram}}
<!-- Mermaid 流程图，展示工程实施的完整流程 -->

### 2. 各节点工作描述

{{node_descriptions}}
<!-- 每流程节点一句话描述其工作内容 -->

## 四、典型工程案例

### 1. 案例详述

{{typical_application_cases}}
<!-- 完整的工程案例：背景→实施过程→结果验证 -->

### 2. 关联场景

{{related_scenes}}
<!-- 同类/上下游工程场景 -->

### 3. 易混淆场景辨析

{{confusion_scenario_compare}}

## 五、知识脉络

{{knowledge_context_diagram}}

### 知识脉络图解析

{{diagram_analysis}}
