# Skill Point Content Spec (技能点内容生成指南)

技能点（SP）是基于理论知识的实践操作能力，回答"能做什么"。**SP 必须在已有 Concepts + KE + KP 的基础上生成**，不可凭空创建。

---

## 两步生成流程（Two-Step SP Generation）

SP 生成采用「骨架→血肉」两步法，禁止一步到位裸写。

### Step A：骨架 — 确定操作步骤、关联知识与 Bloom 层级

1. **精读源文章节**：`read_file("20_正文/第N章.md", offset, limit)` 定位 SP 对应的源文容器，记录节标题及其行号范围。
2. **提取前置依赖**：遍历 `30_核心概念/`、`30_知识要素/`、`40_知识点/` 目录，锁定本 SP 依赖的 ≥3 个概念/KE/KP，输出「前置依赖清单」（Markdown 表格：名称/类型/源文章节/选用理由）。
3. **确定技能边界**：根据源文内容和已有 KE/KP，明确本 SP 的核心操作范围（≥200字描述）、工具需求（≥3项具体工具名）和前置技能（≥1项）。
4. **判定 Bloom 层级**：SP 通常为「应用」或「分析」层级，写出层级判定理由（≥80字）。
5. **综合自检**：确认 Concepts + KE + KP 均已存在（文件可检索到），确认 wikilink 路径正确。不满足则 blocked，修正后重来。

### Step B：血肉 — 逐字段精写

1. 基于 Step A 的骨架，按字段填充规则表逐个字段写入，**每字段标注源文容器行号**。
2. 写 `core_operation` 时，必须包含 ≥3 个具体操作参数（如电压/频率/温度/尺寸等）和 ≥3 个具体工具名（如"LISN"、"矢量网络分析仪"、"近场探头"等）。
3. 写 `operation_flowchart` 时，流程图必须 ≥6 个节点，使用 Mermaid graph LR/TD 格式，展示完整的操作步骤序列。
4. 写 `typical_practical_cases` 时，至少 1 个完整案例：含给定参数 → 分步操作 → 定量验证（≥400字）。每个案例须有明确的参数值（如"超标15dB"、"Cy=4.7nF"、"150kHz-500kHz"）和定量验证结果（如"整改后裕量6dB"）。
5. 所有 `source_from` 精确到 `§节号 L起始行-结束行`，不可仅写节号。
6. 写完所有字段后，立即执行「关联一致性」验证（见下文）。

---

## 源文精读要求

生成每个 SP **之前**，Agent 必须执行以下精读流程：

```
read_file("20_正文/第N章.md", offset=<容器起始行>, limit=<容器长度>)
```

**精读输出的最低标准：**

| 维度 | 要求 |
|:-----|:-----|
| 源文定位 | 明确该 SP 对应的源文容器节号（如 §4.3） |
| 行级引用 | `source_from` 精确到 `§4.3 L120-187`，不可仅写 `§4.3` |
| 关键数据提取 | 从源文中提取 ≥3 个具体操作参数/工具名/判断标准，记录原始数据和行号 |
| 图示引用 | 若源文含图（图N-M），在操作流程中注明图号 |

**禁止行为：**
- ❌ 不读源文凭记忆写内容
- ❌ `source_from` 仅写节号不写行号
- ❌ 关键数据/工具名为幻觉编造
- ❌ 不核查依赖的 Concepts/KE/KP 是否存在就写 wikilink

---

## 内容深度自检（Content Depth Checklist）

每写完一个 SP，必须逐项自检以下 3 条强制标准。**任一条不满足，该 SP 不可 proceed**：

| # | 自检项 | 通过条件 | 验证方式 |
|:--|:-------|:---------|:---------|
| 1 | 具体操作参数/工具名 | 正文含 ≥3 个具体操作参数或工具名（非泛化描述），且每个工具名伴有具体数值或判断标准 | 手动统计：工具名（如"矢量网络分析仪"、"LISN"、"近场探头"、"EMI接收机"）+ 具体数值（如"≤4.7nF"、"≥6dB"、"150kHz-500kHz"、"10mH"） |
| 2 | 操作流程图 ≥6 节点 | `operation_flowchart` 中的 Mermaid 图 ≥6 个节点，展示完整闭环操作步骤序列 | 手动计数流程图节点数（含判断菱形节点）；节点数 = 出现 `A[`/`B[`/`C{` 等节点定义的语句数 |
| 3 | 实操案例完整性 | `typical_practical_cases` 含 ≥1 个完整案例，具备「给定参数 → 分步操作 → 定量验证」三段式结构 | 检查：① 是否有具体参数值（如"超标XdB"、"频率XXMHz"）；② 是否有分步操作描述（至少3步）；③ 是否有定量验证结果（如"整改后裕量XdB"、"降低至XXdBμV/m"） |

**补充自检（推荐）：**

- [ ] `core_operation` 中 ≥3 个具体工具名+≥3 个具体操作参数
- [ ] `operation_flow_analysis` 每 Step 含关键参数+操作要点（≥5 个 Step）
- [ ] `competency_standards` 含入门/熟练/精通三级量化标准
- [ ] Mermaid 图未使用不被 Obsidian 支持的语法特性（参考 `obsidian-mermaid-compatibility.md`）
- [ ] 每张 Mermaid 图的解析文字 ≥150 字符

---

## 关联一致性（Association Consistency）

写完全部 SP 字段后，**立即**跑 wikilink 验证：

### 验证流程

1. **概念/KP wikilink 校验**：遍历 `core_theoretical_support` 中每个 wikilink，用 `search_files` 验证目标 `.md` 文件存在于 `30_核心概念/` 或 `40_知识点/`。
2. **KE wikilink 校验**：遍历 `related_concepts_knowledge` 中每个 wikilink，验证目标文件存在于 `30_知识要素/`。
3. **前置技能校验**：若 `prerequisite_skills` 不为"无"，验证其 wikilink 目标文件存在于 `60_技能点/`。
4. **场景关联校验**：验证 `applicable_scenarios` 中每个 wikilink 目标文件存在于 `50_场景/` 或 `60_技能点/`。
5. **延伸技能校验**：若 `extended_skills` 不为"无"，验证其 wikilink 目标文件存在。

### 阻断规则

```
if any wikilink is 断链 (broken link):
    → BLOCKED: 不可 proceed
    → 修正 wikilink 路径 或 删除该引用
    → 重新验证直到全部通过
```

### 验证结果记录

每完成一个 SP 的验证，在生成日志中记录：

```
[wikilink 验证] SP: 电源端口EMI滤波器选型与整改
  core_theoretical_support (3/3): ✅ 反射滤波器 ✅ 电源线滤波器 ✅ 共模干扰和差模干扰
  related_concepts_knowledge (4/4): ✅ 反射滤波器 ✅ 电源线滤波器 ✅ 共模干扰和差模干扰 ✅ 吸收式滤波器
  prerequisite_skills (1/1): ✅ 电磁兼容测试基础
  applicable_scenarios (1/1): ✅ 产品EMC认证整改
  extended_skills (1/1): ✅ EMC设计审查
  → 全部通过，可 proceed
```

---

## 字段填充规则

| 模板变量 | 内容要求 | 必须填？ | 来源 |
|---------|---------|:-------:|:----:|
| `name` | 技能点名称 | **必需** | — |
| `solved_problem` | 解决的问题——本技能解决的核心工程/操作问题（1-2句话，≥30字） | **必需** | 推理 |
| `bloom_level_description` | 层级解读——Bloom层级含义的详细解释（≥150字） | **必需** | 推理 |
| `bloom_progression` | 学习递进链——Mermaid graph LR 5节点图(知道→理解→应用→分析→评价) | **必需** | 自主生成 |
| `bloom_progression_analysis` | 认知跃迁解析——5层递进解析，每层含百分比占比说明（≥150字） | **必需** | 自主生成 |
| `bloom_alignment` | Bloom对齐矩阵——5行Markdown表格(操作步骤\|布鲁姆层级\|认知要求) | **必需** | 自主生成 |
| `skill_objectives` | 技能目标——掌握本技能后能完成的任务（至少3条，用列表，≥50字） | **必需** | 推理 |
| `domain` | 所属领域 | **必需** | — |
| `core_operation` | 核心操作内容——该技能的核心操作描述（≥200字，含工具名+具体操作参数+判断标准） | **必需** | 源文+推理 |
| `competency_standards` | 能力标准——评判技能掌握程度的标准（分入门/熟练/精通三级，每级含具体标准） | **必需** | 推理 |
| `operation_boundaries` | 操作边界——该技能的适用范围和限制条件（至少3条） | **必需** | 推理 |
| `core_theoretical_support` | 核心理论支撑——支撑该技能的理论知识 wikilink（至少3条概念/KP引用） | **必需** | 概念+KP |
| `tool_support` | 工具支撑——执行该技能所需的工具/设备/软件（至少3项，含说明） | **必需** | 推理 |
| `prerequisite_skills` | 前置技能——掌握本技能前应具备的其他SP（至少1条），无则填"无" | 推荐 | 推理 |
| `applicable_scenarios` | 适配场景——该技能可应用的场景 wikilink（至少2条） | **必需** | 推理 |
| `operation_flowchart` | 操作流程图——Mermaid graph LR/TD 流程图，展示操作步骤序列（≥6个节点） | **必需** | 自主生成 |
| `operation_flow_analysis` | 操作流程说明——逐Step说明操作过程，每Step含关键参数+操作要点+理论依据（≥5个Step） | **必需** | 自主生成 |
| `typical_practical_cases` | 典型实操案例——至少1个完整案例（三段式：给定参数→分步操作→定量验证，≥400字） | **必需** | 源文+推理 |
| `related_concepts_knowledge` | 关联概念/知识点/知识要素——引用的概念/KP/KE wikilink（至少5条） | **必需** | 概念+KP+KE |
| `supported_scenarios` | 支撑的场景——该技能支持的场景 wikilink，无则填"无" | 推荐 | 推理 |
| `extended_skills` | 延伸技能——学完本技能后可学习的进阶技能 wikilink，无则填"无" | 推荐 | 推理 |
| `confusion_skill_compare` | 易混淆技能辨析——与其他SP的对比表（≥1组，Markdown表格） | **必需** | 推理 |
| `evolution` | 发展演进——该技能的技术发展趋势，无则填"无" | 推荐 | 推理 |
| `knowledge_context_diagram` | 知识脉络图——Mermaid graph TD 图，展示SP与概念/KP/前置SP/场景的关联（≥8个节点，含 classDef 颜色编码） | **必需** | 自主生成 |
| `diagram_analysis` | 知识脉络图解析——逐节点解析图中含义（≥5段） | **必需** | 自主生成 |

---

## 内容质量标准

| 标准 | 通过条件 |
|:-----|:---------|
| Bloom字段完整性 | bloom_level_description≥150字、bloom_progression(5节点)、bloom_alignment(5行表格)、bloom_progression_analysis≥150字(5层) |
| 技能目标完整性 | skill_objectives ≥ 3条独立条目，≥50字 |
| 核心操作完整性 | core_operation ≥ 200字，含≥3个工具名+≥3个具体操作参数，不可为"无" |
| 能力标准完整性 | competency_standards 分入门/熟练/精通三级，每级含具体量化标准 |
| 文件大小 | ≥ 8KB（代码强制阈值） |
| Mermaid图 | 2张（操作流程图≥6节点 + 知识脉络图≥8节点含classDef） |
| 实操案例 | ≥ 1（三段式：给定参数→分步操作→定量验证，≥400字） |
| 易混淆对比 | ≥ 1组（Markdown表格） |
| wikilink引用 | ≥ 8条 |
| **深度自检** | **含 ≥3 个具体操作参数/工具名；operation_flowchart ≥6 节点；typical_practical_cases 含定量验证；source_from 精确到容器行号** |
| **wikilink 验证** | **全部 wikilink 可解析到真实存在的文件，断链则 blocked** |

---

## 依赖关系

生成前必须确认：
- [ ] 该SP涉及的概念文件已存在（`30_核心概念/` 中）
- [ ] 该SP使用的KE文件已存在（`30_知识要素/` 中）
- [ ] 该SP依赖的KP文件已存在（`40_知识点/` 中）
- [ ] `core_theoretical_support` 中的 wikilink 指向真实存在的概念/KP文件
- [ ] `related_concepts_knowledge` 中的 wikilink 指向真实存在的概念/KE/KP文件
- [ ] Step A 骨架分析已完成并留存记录
- [ ] 源文章节已通过 `read_file` 精读并记录行号范围

---

**版本**: v2.0
**最后更新**: 2026-06-05
**v2.0 变更**: 新增两步生成流程（Step A 骨架 + Step B 血肉）、源文精读要求（read_file + 行级 source_from）、内容深度自检（3 条强制标准：具体操作参数/工具名 ≥3、操作流程图 ≥6 节点、实操案例三段式定量验证）、关联一致性验证（wikilink 断链 blocked 机制）。保留原字段填充规则表与内容质量标准，增量补充深度要求。与 KP v49.0 规范对齐生成流程和验证体系。
