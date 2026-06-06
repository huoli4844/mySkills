# 模板结构总览（Templates Overview）

> 五大类模板的结构、Bloom 层级体系、L2/L3/L4 索引概要。
> 从 SKILL.md 提取的详细模板说明。
> 版本：v44.2

## 五大类模板

| 类别 | 模板文件 | 归并来源 | 架构 | 子类型(quality_key) |
|:-----|:---------|:---------|:-----|:-------------------|
| 概念类 | concept_template.md v6.2 | concept + KE + entity | 三层 | concept / concept/ke / concept/entity |
| 知识类 | knowledge_template.md v5.2 | kp | 四层 | knowledge |
| 技能类 | skill_template.md v5.1 | sp | 五层 | skill |
| 场景类 | scenario_template.md v5.1 | scene | 四层 | scenario |
| 评测类 | eval_template.md v6.0 / exercise_template.md | exercise + solution | — | eval/exercise / eval/solution |

## 概念模板结构（concept_template.md v6.2）

```
## 学习目标              ← 学生入口（Bloom 分层 + 前置知识 wikilink + 自学检验）
## 一、基础信息          ← ### 0. 解决的问题(v46.2新增) + 术语定义 + 说明 + 分类 + 核心概念图谱
## 二、核心内容          ← 工作原理 + 数学模型 + 关键参数 + 物理含义 + 技术分类
## 三、应用与关联        ← 场景 + 典型系统 + 使用价值 + 工程要点 + 常见误区 + 辨析 + 演进
## 关联目录
```

### 历史变更
- v46.2: 新增 `### 0. 解决的问题` 节（位于 `## 一、基础信息` 与 `### 1. 术语定义` 之间），格式为1-2句话"解决{具体问题}。{价值说明}"
- v43.2: `definition_source` 替换为自动组合的 `来源：第{source_chapter}章 §{source_from} 节`

## Bloom 认知层级体系

KP/SP/Scene 三种模板强制要求结构化 Bloom 呈现：

| 模板 | Bloom 层级范围 | 说明 |
|:-----|:---------------|:-----|
| knowledge_template.md（KP）v5.2 | 知道→理解 / 知道→应用 / 理解→应用 | 学懂知识。v5.2新增: ### 0. 解决的问题 + ### 5. 技能要求 + ### 6. 技能目标，原Bloom对齐矩阵重编号为### 7 |
| skill_template.md（SP）| 应用 / 理解→应用 / 应用→分析 / 分析 | 学会操作 |
| scenario_template.md（Scene）| 分析→评价 / 分析→评价→创造 / 评价→创造 | 综合解决 |

每个模板的 Bloom 区域包含：
1. **布鲁姆认知层级** — 当前节点的 Bloom 标签
2. **学习递进链** — Mermaid 流程图
3. **Bloom 对齐矩阵** — 表格映射各节到 Bloom 层级
4. **学习目标** — 按 Bloom 六级分层编写

**代码校验**（schema.py BLOOM_RANGES）：
| 类型 | 允许值 |
|:-----|:------|
| KP | 知道→理解, 知道→应用, 理解→应用 |
| SP | 应用, 理解→应用, 应用→分析, 分析 |
| Scene | 分析→评价, 分析→评价→创造, 评价→创造 |

超出范围 → `severity: warning`。

## 习题/解答模板分离

- exercise_template.md — 纯习题模板（仅含题目 + 解答 wikilink + 关联目录）
- eval_template.md — 完整解答模板（核心解答 + 考点辨析 + 难点深入 + Mermaid 流程图 + 知识闭环图）
- 配置位置：`template_assembler.py` ASSEMBLER_CONFIG、`pipeline_auto.py` `_auto_detect_and_build_exercises`、`dag_constants.py` BUILDER_CONFIG

## L2/L3/L4 汇总层

每个层级只生成一个 overview 文件，4 类索引内嵌其中：

| 层级 | 文件 | 范围 |
|:-----|:-----|:-----|
| L2 | `book_overview_xxx.md` | 单书：知识链连通率 + 核心节点排名 + Mermaid 全景 + Bloom 学习路径 |
| L3 | `domain_overview_xxx.md` | 领域跨书：跨书知识链 + 图质量 |
| L4 | `kb_overview_xxx.md` | 全库跨领域：知识链完整性 + 盲区检测 |

索引表用相对路径（`../30_核心概念/`）避 Markdown 表格管道符冲突。

## Content Quality Standards

| 类型 | 基准大小 | 关键字段下限 |
|:-----|:-------|:-----------|
| concept | ≥8KB | definition≥80字, structure≥100字, engineering_practices≥300字, misconceptions≥200字 |
| ke | ≥2KB | definition≥100字, features≥80字 |
| entity | ≥500B | description≥100字 |
| kp | ≥8KB | knowledge_content≥300字, typical_examples≥300字 |
| sp | ≥6KB | skill_description≥200字, typical_practical_cases≥400字 |
| scene | ≥7KB | scenario_description≥200字, workflow_analysis≥300字 |
| solution | ≥5KB | principle_steps≥300字, typical_practical_cases≥400字 |
