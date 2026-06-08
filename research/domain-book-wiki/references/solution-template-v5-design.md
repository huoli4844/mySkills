# 解答模板 v5.0 设计规范

> 版本：v35.8 | 从 v4.0 扁平结构升级为六段式结构化格式

## 模板结构（6 个 ## 主段 + 13 个 ### 子节）

```
## 一、题目原文              {{question}}
## 二、核心解答
  ### 2.1 实现原理（流程化拆解）    {{principle_steps}}
  ### 2.2 主要特点（维度化归纳）    {{characteristics}}
## 三、考点与易错点解析
  ### 3.1 核心考点                 {{exam_points}}
  ### 3.2 常见错误（避坑指南）      {{common_mistakes}}
  ### 3.3 解题技巧                 {{solving_tips}}
## 四、难点深度解析
  ### 4.1 {{difficulty_1_title}}    {{difficulty_1_content}}
  ### 4.2 {{difficulty_2_title}}    {{difficulty_2_content}}
  ### 4.3 {{difficulty_3_title}}    {{difficulty_3_content}}
## 五、可视化解题逻辑
  ### 5.1 实现流程思维导图 *(必填)*  {{flowchart_diagram}} (Mermaid graph TD/LR)
       **实现流程分步说明**         {{flowchart_steps}}
  ### 5.2 知识闭环体系 *(必填)*      {{knowledge_loop_diagram}} (Mermaid，仅限图)
       ### 知识闭环图解析           {{knowledge_loop_analysis}}
## 六、关联资源
  ### 6.1 核心知识点 / 概念         {{related_concepts}} (wikilink 列表)
  ### 6.2 引用与关联目录            {{source_reference}} + wikilink
```

## v4.0 → v5.0 字段名映射

| v4.0 字段 | v5.0 字段 | 说明 |
|---|---|---|
| `answer` | `principle_steps` | 核心解答的实现原理 |
| — | `characteristics` | 新增：特点维度归纳 |
| `exam_point_analysis` | `exam_points` | 考点分析 |
| — | `common_mistakes` | 新增：常见错误 |
| — | `solving_tips` | 新增：解题技巧 |
| `difficulty_analysis` | `difficulty_1/2/3_content` | 拆分为 3 个独立难点 |
| `problem_solving_flowchart` | `flowchart_diagram` | 解题流程图 |
| `problem_solving_analysis` | `flowchart_steps` | 流程分步说明 |
| `knowledge_closed_loop` | `knowledge_loop_diagram` | 知识闭环图 |
| `closed_loop_analysis` | `knowledge_loop_analysis` | 闭环图解析 |
| `references` | `source_reference` | 引用来源 |
| — | `related_concepts` | 新增：关联知识点 wikilink |

## 必填图检查规则

`check_solution_mandatory_diagrams` 在 comprehensive-content-check 中以 FAIL 级阻断：

1. `flowchart_diagram` 不能为空 / `"无"` / 含中文占位符
2. `knowledge_loop_diagram` 同上，且必须包含有效 Mermaid 语法（`graph`/`flowchart`/`sequenceDiagram` 等声明）

## 骨架生成器默认图

当 solutions.yaml 缺失时，`_auto_build_solutions` 自动生成：

```
flowchart_diagram (graph TD):          knowledge_loop_diagram (graph LR):
  审题 → 回顾概念 → 建立模型            核心概念 → 分析模型
    → 推导结论 → 验证 → 总结              → 解决方案 → 工程应用
                                            ← 反馈闭环 (虚线)
```

## 置信度

- 骨架：0.65（`CONFIDENCE_LEVELS["eval/solution"]` 允许）
- Agent 填充后：0.85（v35.8 新增允许值）
