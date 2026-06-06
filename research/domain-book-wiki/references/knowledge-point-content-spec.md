# Knowledge Point Content Spec (知识点内容生成指南)

知识点（KP）是结合概念和知识要素形成的综合性知识单元，回答"学了什么"。**KP 必须在已有 Concepts + KE 的基础上生成**，不可凭空创建。

---

## 两步生成流程（Two-Step KP Generation）

KP 生成采用「骨架→血肉」两步法，禁止一步到位裸写。

### Step A：骨架 — 确定 KE 清单、关联概念与 Bloom 层级

1. **精读源文章节**：`read_file(20_正文/第N章.md, offset, limit)` 定位 KP 对应的源文容器，记录节标题及其行号范围。
2. **提取 KE 清单**：遍历本章的 `30_知识要素/` 目录，锁定本 KP 将使用的 ≥3 个 KE，输出「核心 KE 候选表」（Markdown 表格：KE名称/所属节/行号/选用理由）。
3. **拉取关联概念**：遍历 `30_核心概念/` 目录，确认本 KP 依赖的 ≥3 个核心概念（含 wikilink），输出「关联概念清单」。
4. **判定 Bloom 层级**：根据源文内容深度判定 Bloom 层级（理解/应用/分析/评价），写出层级判定理由（≥80字）。
5. **综合自检**：确认 KE 与 Concepts 均已存在（文件可检索到），确认 wikilink 路径正确。不满足则 blocked，修正后重来。

### Step B：血肉 — 逐字段精写

1. 基于 Step A 的骨架，按字段填充规则表逐个字段写入，**每字段标注源文容器行号**。
2. 写 `theoretical_basis` 时，必须引用 ≥3 个概念 wikilink，且从源文中提取 ≥3 个关键数字/公式/参数。
3. 写 `application_methods` 时，必须包含具体工具名 + 判断标准（不可仅抽象描述）。
4. 写 `typical_examples` 时，例题必须含：给定参数 → 分步推导 → 结果验证。
5. 所有 `source_from` 精确到 `§节号 L起始行-结束行`，不可仅写节号。
6. 写完所有字段后，立即执行「关联一致性」验证（见下文）。

---

## 源文精读要求

生成每个 KP **之前**，Agent 必须执行以下精读流程：

```
read_file("20_正文/第N章.md", offset=<容器起始行>, limit=<容器长度>)
```

**精读输出的最低标准：**

| 维度 | 要求 |
|:-----|:-----|
| 源文定位 | 明确该 KP 对应的源文容器节号（如 §7.3.2） |
| 行级引用 | `source_from` 精确到 `§7.3.2 L120-187`，不可仅写 `§7.3` |
| 关键数据提取 | 从源文中提取 ≥3 个具体数字/公式/参数，记录原始数据和行号 |
| 定义句检索 | `definition_sentence`（若有）必须在源文中可逐字检索到 |
| 图示引用 | 若源文含图（图N-M），在 `figure_references` 中注明图号 |

**禁止行为：**
- ❌ 不读源文凭记忆写内容
- ❌ `source_from` 仅写节号不写行号
- ❌ 关键数字/公式为幻觉编造

---

## 内容深度自检（Content Depth Checklist）

每写完一个 KP，必须逐项自检以下 3 条强制标准。**任一条不满足，该 KP 不可 proceed**：

| # | 自检项 | 通过条件 | 验证方式 |
|:--|:-------|:---------|:---------|
| 1 | 具体数字/公式/参数 | 正文含 ≥3 个具体数字、公式或参数（非泛化描述） | 手动计数 `bd` 中各字段出现的数字与 LaTeX 公式 |
| 2 | 源文行号精度 | 所有 `source_from` 精确到 `§节号 L起始-结束行`，且行号范围与 `read_file` 结果一致 | 交叉对照 read_file 输出 |
| 3 | application_methods 实操性 | 含 ≥1 个具体工具名（如"频谱分析仪"、"矢量网络分析仪"）+ ≥1 个判断标准（如"当插入损耗 >3dB 时判定为超标"） | 手动检索工具名和条件判断关键词 |

**补充自检（推荐）：**

- [ ] `theoretical_basis` 中 ≥3 个概念 wikilink 可点击跳转
- [ ] `typical_examples` 例题可独立复现（走完参数→推导→验证全流程）
- [ ] Mermaid 图未使用不被 Obsidian 支持的语法特性（参考 `obsidian-mermaid-compatibility.md`）
- [ ] 每张 Mermaid 图的解析文字 ≥500 字符

---

## 关联一致性（Association Consistency）

写完全部 KP 字段后，**立即**跑 wikilink 验证：

### 验证流程

1. **概念 wikilink 校验**：遍历 `related_concepts` 中每个 wikilink，用 `search_files` 验证目标 `.md` 文件存在于 `30_核心概念/`。
2. **KE wikilink 校验**：遍历 `related_knowledge_elements` 中每个 wikilink，验证目标文件存在于 `30_知识要素/`。
3. **前置知识校验**：若 `prerequisite_knowledge` 不为"无"，验证其 wikilink 目标文件存在于 `40_知识点/`。
4. **支撑关系校验**：验证 `supported_skills_scenarios` 中每个 wikilink 目标存在。

### 阻断规则

```
if any wikilink is 断链 (broken link):
    → BLOCKED: 不可 proceed
    → 修正 wikilink 路径 或 删除该引用
    → 重新验证直到全部通过
```

### 验证结果记录

每完成一个 KP 的验证，在生成日志中记录：

```
[wikilink 验证] KP: 电磁兼容三要素分析法
  related_concepts (3/3): ✅ 电磁干扰源 ✅ 耦合途径 ✅ 敏感设备
  related_knowledge_elements (3/3): ✅ 传导耦合 ✅ 辐射耦合 ✅ 共模干扰
  prerequisite_knowledge (1/1): ✅ 电磁兼容基本概念
  supported_skills_scenarios (2/2): ✅ 电磁干扰三要素识别 ✅ 电磁兼容设计评审
  → 全部通过，可 proceed
```

---

## 字段填充规则

| 模板变量 | 内容要求 | 必须填？ | 来源 |
|---------|---------|:-------:|:----:|
| `name` | 知识点名称 | **必需** | — |
| `solved_problem` | 解决的问题——本知识点解决的核心工程/理论问题（1-2句话，≥30字） | **必需** | 推理 |
| `learning_objectives` | 学习目标——学完本知识点后应掌握的能力描述（至少3条，用列表） | **必需** | 推理 |
| `domain` | 所属领域 | **必需** | 正文 |
| `bloom_level_description` | 层级解读——Bloom层级含义的详细解释（≥150字） | **必需** | 推理 |
| `bloom_progression` | 学习递进链——Mermaid graph LR 5节点图(知道→理解→应用→分析→评价) | **必需** | 自主生成 |
| `bloom_progression_analysis` | 认知图谱解析——5层递进解析（≥150字，每层含百分比占比） | **必需** | 自主生成 |
| `bloom_alignment` | Bloom对齐矩阵——5行Markdown表格(内容节|布鲁姆层级|认知要求) | **必需** | 自主生成 |
| `skill_requirements` | 技能要求——应用本知识点需要的具体前置技能（≥3条，≥50字） | **必需** | 推理 |
| `skill_objectives` | 技能目标——学完后可达到的具体能力（≥3条，≥50字） | **必需** | 推理 |
| `theoretical_basis` | 理论基础——该知识点的理论来源和依据（至少200字，含 3+ 个核心概念 wikilink） | **必需** | 概念+正文 |
| `derivation_diagram` | 核心推导过程——Mermaid graph LR 推导流程图（展示从输入→推导→结论的完整逻辑链，≥8个节点） | **必需** | 自主生成 |
| `derivation_analysis` | 推导流程说明——逐Step说明推导过程，每Step含公式+物理意义（≥5个Step） | **必需** | 自主生成 |
| `key_details` | 关键细节/注意事项——易错点、边界条件（至少3条） | **必需** | 推理 |
| `core_knowledge_elements_table` | 核心知识要素清单——本KP使用的KE清单表格（至少3条，Markdown表格格式） | **必需** | KE |
| `application_scenarios` | 应用场景——该KP适用的场景（至少3项，每项含 wikilink） | **必需** | 推理 |
| `application_methods` | 应用方法/步骤——实际应用中的操作流程（至少3步，每步含工具名+判断标准） | **必需** | 推理 |
| `typical_examples` | 典型例题/案例——至少1道完整例题（含参数→分步推导→验证） | **必需** | 正文+推理 |
| `exam_and_misconceptions` | 考点+考试例题+考点解析+常见误解辨析（v48.0 合并字段） | **必需** | 推理 |
| `related_concepts` | 关联概念——该KP引用的核心概念 wikilink（至少3条） | **必需** | 概念 |
| `related_knowledge_elements` | 关联知识要素——该KP使用的KE wikilink（至少2条） | **必需** | KE |
| `prerequisite_knowledge` | 前置知识点——学习本KP前需要掌握的知识点 wikilink，无则填"无" | 推荐 | 推理 |
| `supported_skills_scenarios` | 支撑的技能点/场景——本KP可以支撑的SP/场景 wikilink（至少1条） | **必需** | 推理 |
| `confusion_compare_table` | 易混淆知识点辨析——与其他KP的对比表格（≥1组，Markdown表格） | **必需** | 推理 |
| `knowledge_context_diagram` | 知识脉络图——Mermaid graph TD 图，展示KP与概念/KE/前置KP/SP/场景的关联（≥8个节点，含 classDef 颜色编码） | **必需** | 自主生成 |
| `diagram_analysis` | 知识脉络图解析——逐节点解析图中含义（≥5段，每类节点逐一说明） | **必需** | 自主生成 |

## 内容质量标准

| 标准 | 通过条件 |
|:-----|:---------|
| Bloom字段完整性 | bloom_level_description/递进链/对齐矩阵/认知解析均不可为"无"或空 |
| 新增字段完整性 | solved_problem≥30字, skill_requirements≥50字(≥3条), skill_objectives≥50字(≥3条) |
| 非空子节数 | 至少16个 `###` 子节有实质内容（代码强制阈值；理想目标≥18） |
| 总字数 | ≥ 1600 字符（代码强制阈值；理想目标≥4000） |
| 文件大小 | ≥ 8KB |
| Mermaid图 | 3张（推导图+脉络图+递进链图） |
| 图解析字数 | ≥ 500 字符（每张图） |
| 表格 | ≥ 3（KE清单+易混淆辨析+Bloom对齐矩阵） |
| 例题 | ≥ 1（含参数+分步推导+验证） |
| 考点 | ≥ 2个 |
| **深度自检** | **含 ≥3 个具体数字/公式/参数；source_from 精确到容器行号；application_methods 含工具名+判断标准** |
| **wikilink 验证** | **全部 wikilink 可解析到真实存在的文件，断链则 blocked** |

## 依赖关系

生成前必须确认：
- [ ] 该KP涉及的概念文件已存在（`30_核心概念/` 中）
- [ ] 该KP使用的KE文件已存在（`30_知识要素/` 中）
- [ ] `related_concepts` 中的 wikilink 指向真实存在的概念文件
- [ ] `related_knowledge_elements` 中的 wikilink 指向真实存在的KE文件
- [ ] Step A 骨架分析已完成并留存记录
- [ ] 源文章节已通过 `read_file` 精读并记录行号范围

---

**版本**: v49.0
**最后更新**: 2026-06-05
**v49.0 变更**: 新增两步生成流程（Step A 骨架 + Step B 血肉）、源文精读要求（read_file + 行级 source_from）、内容深度自检（3 条强制标准）、关联一致性验证（wikilink 断链 blocked 机制）。保留原字段填充规则表与内容质量标准，增量补充。
