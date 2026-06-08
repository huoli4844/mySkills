---
name: domain-wiki
description: "从教材源文件构建结构化 Obsidian 知识库：write_yaml → pipeline_v2 phase-a → 40+文件/章。模板自携带@prompt写作指导，yaml_writer.py pydantic校验，零对照表"
version: "2.7"
author: Hermes Agent
license: MIT
metadata:
  category: research
  related_skills: [source-prepare, file2md]
---

# Domain Wiki Builder (v2)

## When to Use

用户要求从教材构建结构化 Obsidian 知识库，包含核心概念、知识要素、知识点、技能点、应用场景、实体、习题和解答。

## v2 Pipeline 概览

```
写 YAML → yaml_writer.py validate → pipeline_v2.py phase-a
         ↓                              ↓
    pydantic 校验字段、confidence   读 schema+模板 → 填 {{xxx}} → 输出 40+ .md
         ↓
    Agent 写 YAML 前先生成自指导提示词:
    yaml_writer.py self-instruct --type concept -c N --book-dir .
```

**核心文件**（仅 7 个脚本，已全面清洗）：

| 文件 | 职责 |
|------|------|
| `scripts/pipeline_v2.py` | 编排器：校验 YAML → 驱动 template_engine |
| `scripts/yaml_writer.py` | YAML 写入 + pydantic 校验 + @prompt 提取 + self-instruct 自指导 |
| `scripts/template_engine.py` | 模板渲染：读 schema → 填 {{xxx}} → 自动包裹 mermaid 图 → 剥离 @prompt 注释 |
| `scripts/validate_mermaid.py` | 批量验证概念文件的 Mermaid 图语法（括号引用、单行图） |
| `schemas/domain_book_schema.json` | 字段定义（类型/必填/constraints） |
| `assets/templates/*.md` | 15 个模板（含 @prompt 写作指导） |
| `scripts/split_book_to_chapters.py` | 整书 MD 拆分 |
| `scripts/link_audit.py` | wikilink 审核 |

## 核心设计原则

### 模板是字段的单一权威源（用户核心要求）

每个模板 `.md` 文件同时包含一切信息，**不需要任何外部对照表**：

1. **`{{xxx}}` 占位符** — template_engine.py 输出格式
2. **`<!-- @prompt ... -->` 注释** — Agent 写作指导（写什么、多长、什么格式）

改了模板就等于改了所有。新增一个字段只需在模板中写 `{{new_field}}` 加一行 `<!-- @prompt ... -->`。不需要改 schema.json、不需要维护 template-yaml-field-map.md、不需要单独写提示词文档。

**Agent 写 YAML 的正确工作流（三选一）：**
```bash
# A（推荐）：生成自指导提示词 — @prompt + schema约束 + 源文上下文
python3 scripts/yaml_writer.py self-instruct --type concept -c N --book-dir /path

# B：只看模板中的 @prompt 写作指导
python3 scripts/yaml_writer.py prompt --type concept
python3 scripts/yaml_writer.py prompt --type kp --field theoretical_basis

# C：生成YAML骨架，只写值不写字段名
python3 scripts/yaml_writer.py skeleton --type concept
```

**`self-instruct` 输出结构（字段工作台模式 v2.7+）：**
| 节 | 内容 |
|---|------|
| 章节源文 | 自动加载 20_正文/第N章.md，解析为按 `##`/`###` 标题分段的字典（50+节） |
| 源文公式检测 | 自动扫描 `$$..$$` 公式块，提取行号和内容，注入到 mathematical_model 字段提示 |
| 必填字段(字段工作台) | 每字段：进度编号(idx/总数) + 🔴必填/🟡可选 + 模板节标题 + schema约束 + @prompt + 源文片段（最多2条最匹配段） |
| 可选字段 | 同上，注明"有内容写否则填无" |
| 常见错误提醒 | confidence范围、字段位置、mermaid格式、列表格式 |

**关键设计——字段工作台（v2.5+）：** 每字段并行展示三列信息——模板位置+@prompt（格式规格）、源文片段（内容原料）、schema约束（校验条件）。Agent 不需要自己翻源文找对应的字段内容——系统已经把源文按**语义级信号词匹配**到每个字段，Agent 只需逐字段填空。@prompt 解决"格式怎么控制"，源文片段解决"内容从哪里来"，schema约束解决"校验什么条件"。

**源文匹配引擎（v2.7 重构：双层信号词体系，零领域绑定）：** 使用**双层信号词体系**——语言层 + 领域动态提取——实现语义级匹配。**不依赖任何 embedding 模型**（非必需），纯静态规则运行时自适应。

**语言层（`_LANG_SIGNALS`，硬编码，领域无关）：** 中文技术写作的通用模式。9 类信号词（definition/formula/structure/negation/evolution/cause_effect/application），不含任何领域专有词。含"是指/指的是"（定义标记）、"不能/不要/误区"（否定标记）、"①步②骤③流程"（结构标记）、"导致/由于/为了"（因果标记）等。

**领域层（`_extract_domain_signals()`，运行时从源文自动提取，零配置）：** 每次 self-instruct 调用时自动执行，通过三个路径提取：

1. **单位词提取**：`\d+\s*[a-zA-Z/°μΩ...]+` 正则匹配数字后的字母组合（如 dBm、GHz、dBi、V/m、pF、nH、μs、ns）。不依赖任何硬编码列表——换本书自动提取该书的计量单位。
2. **节标题术语提取**：从 `##`/`###` 标题提取 3 字以上核心名词，过滤通用词后作为 application 信号词。
3. **高频技术词提取**：全文中文词频统计（>3 次，3-8 字），过滤停用词后作为 technical 信号词。

**合并规则：** 语言层 + 领域层在 `_match_field_to_source()` 中合并，领域层同名类目覆盖语言层。每字段通过 `_FIELD_SIGNAL_PROFILES` 配置主/次信号类型（如 `engineering_practices→number(主)+example(次)`），评分时主信号 x1.5 + 次信号 x0.75 + 数字密度 + 公式行加分 + 长度惩罚。

**关键教训：规则够细就不需要 embedding——语言层 9 类通用信号 + 领域层运行时自适应 + 主次信号画像，在 EMC 教材上实测匹配准确率足够（application_scenarios 从匹配"13.4 接口诊断法"改善为匹配"车内线缆串扰分析"）。换本机械/生物/金融教材，零配置即可自适应。**

**设计意图：** 模板 @prompt 是通用写作指导（人工可控，改一次跨所有章节生效）。Agent 把 @prompt 当"原料"而非"指令"，结合当前章节源文自行形成一次性自指导提示词。这样 @prompt 成为人工控制输出质量的持久手段。

**实战验证（第13章）：** 使用本流程处理第13章（1148行，10道习题）——全线零阻断、44文件全量生成。概念文件164行/篇含12-13节点Mermaid图，零@prompt泄漏，零{{xxx}}残留，所有Mermaid标签正确引用`()`。对比旧章节30/49概念缺图、27文件标签括号未引用、3个单行图——全部归零。

**改进方向：** 当前Agent写YAML的待填字段清单由Agent自身记忆决定，非模板驱动。P0目标：在pipeline_v2.py增加模板字段覆盖率校验，实现"填空式写作"。详见[dag-flow-optimization.md](references/dag-flow-optimization.md)。

**template_engine.py 渲染时**自动剥离 `<!-- @prompt ... -->`，零泄漏到输出。

### 两阶段构建

- **Phase A（纯代码）**：校验 YAML → 渲染模板输出。所有 8 种类型（concept/ke/entity/kp/sp/scene/exercise/solution）一次完成
- **Phase B（可选，Agent 分析）**：`pipeline_v2.py phase-b` 输出当前章节的数据概况，供 Agent 判断是否需要调整 YAML 内容

### 工程 vs 内容边界原则

| 归属 | 特征 | 由谁执行 |
|:-----|:-----|:---------|
| 工程化 | 确定性输入→输出 | Python 脚本：模板渲染、格式校验、YAML schema 校验 |
| 内容 | 需语义理解 | Agent (LLM)：概念抽取、内容写作、教学质量 |

## Quickstart

**写 YAML → 自指导 → 校验 → 渲染 → 验证图**（五步完成一章）：

```bash\n# 1. Agent 生成自指导提示词（模板@prompt + schema约束 + 源文上下文）\npython3 scripts/yaml_writer.py self-instruct --type concept -c N --book-dir /path\n\n# 1b. Agent 基于自指导提示词写 YAML\npython3 scripts/yaml_writer.py write --type concept \\\n  --yaml-path .dag/第N章/data/concepts.yaml \\\n  --items '[...]'

# 2. 全量校验
python3 scripts/yaml_writer.py validate-dir --dir .dag/第N章/data/

# 3. 渲染
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book \
  -c N \
  --book-id 01_书ID \
  --book-name "书名"

# 4. 验证输出的 Mermaid 图语法
python3 scripts/validate_mermaid.py --book-dir /path/to/book
```

**整书预处理**（已有整书 MD 时）：
```bash
python3 scripts/split_book_to_chapters.py prepare \
  --raw-dir /path/to/raw/书籍名/ \
  -w $BOOK_DIR --split
```

## YAML 数据规范

所有 YAML 文件必须遵循 `{name, file, fm, bd}` 四字段结构：

```yaml
- name: 概念名
  file: 概念名          # 输出 .md 文件名（不含后缀）
  fm:                   # frontmatter（元数据）
    source_chapter: "N"
    confidence: 0.95
    name: 概念名
    tags: [tag1, tag2]
  bd:                   # body（内容字段）
    term_definition: "..."
    mathematical_model: "$$...$$"
```

- `fm` 字段：约 11-13 个，大部分可自动填充
- `bd` 字段：每类型不同（concept 有 26 个，exercise 只有 2 个）
- 字段名必须与 schema.json 一致（`yaml_writer.py write` 会 pydantic 校验，写错当场报错）
- 每个节点类型一个文件：`concepts.yaml`, `kes.yaml`, `entities.yaml`, `kps.yaml`, `sps.yaml`, `scenes.yaml`, `exercises.yaml`, `solutions.yaml`

## 8 种节点类型

| 类型 | 模板 | 置信度 | bd 字段数 | 内容来源 |
|------|------|--------|-----------|----------|
| concept | concept_template.md | 0.95 | 26 | 核心概念定义、公式、结构、关联 |
| ke | ke_template.md | 0.85 | 12 | 知识要素（公式/参数/学科基础） |
| entity | entity_template.md | 0.85 | 12 | 实体（标准/设备/组织/人物） |
| kp | knowledge_template.md | 0.85 | 22 | 知识点（理论+实践+认知进阶） |
| sp | skill_template.md | 0.75 | 23 | 技能点（操作流程+工具+标准） |
| scene | scenario_template.md | 0.65 | 15 | 应用场景（工程案例+实施流程） |
| exercise | exercise_template.md | 0.65 | 2 | 习题原文 |
| solution | eval_template.md | 0.65/0.85 | 19 | 解答（步骤+考点+难点+闭环） |

## Pitfalls

| # | Trap | Prevention |
|:--|:-----|:-----------|
| 1 | 模板 `{{xxx}}` 与 schema BD 字段不一致（schema 缺字段或有多余字段） | 模板是字段的唯一权威源。写模板时加 `<!-- @prompt ... -->`，必要时才更新 schema.json |
| 2 | `@prompt` 注释泄漏到渲染输出 | template_engine.py 的 `render_item()` 必须在替换完所有 `{{xxx}}` 后执行 `re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)` |
| 3 | 习题文件名双前缀（"第11章-第11章-习题1.md"） | `EXERCISE_FILENAME_MAP` 和 `_gen_exercise_content` 中先检查 `name` 是否已含 `第N章-` 前缀，避免重复 |
| 4 | 解答 `question` 太短（<20字）被 schema 拦截 | solution 的 `question` 字段有 `min_chars: 20` 约束。直接从习题 YAML 复制原文 |
| 5 | Agent 写的 `theoretical_basis` 太短（<150字）被拦截 | schema 中有 `min_chars` 约束。写之前用 `yaml_writer.py prompt --type kp --field theoretical_basis` 看要求 |
| 6 | 内容质量的根因不是 prompt 不够细，而是源文不在上下文。prompt 只能解决"格式"，解决不了"深度" | Agent 写 YAML 前必须精读源文对应段落。prompt 命令只是锦上添花，不是雪中送炭。 |
| 7 | `confidence` 值超出允许范围（如 exercise 写 0.85 但只允许 0.65） | schema.json 每类型有 `confidence.allowed` 枚举。`yaml_writer.py write` 在校验阶段直接 reject |
| 8 | 换书：章节文件名、关键词、教材描述全硬编码 | `config/book_info.yaml` 和 `config/knowledge_keywords.yaml` 外置配置。 |
| 9 | 核心概念图的 `core_concept_map` 不含 ` ```mermaid ` fence → Obsidian 把 graph TD 当普通文字渲染，不显示图 | **引擎层防护**：`template_engine.py._auto_wrap_mermaid()` 自动检测 raw `graph TD/LR/flowchart/sequenceDiagram` 等 mermaid 语法并包裹代码块。**Agent 写 YAML 时的预防**：`core_concept_map` 只需写 `graph TD\n  A[label] --> B[label2]` 内容本身，不需要加 `` ```mermaid `` fence（引擎会加）。纯文字描述（如"接地是EMC四大技术之一"）不会被引擎转换，需重写为 graph 格式。 |
| 10 | YAML 中存在 `\n`（字面反斜杠+n）而非真正的换行 → mermaid graph 渲染为一行 | YAML 中多行 graph 必须用 `|` block scalar：`core_concept_map: |-\n  graph TD\n    A[label] --> B[label2]`。`yaml.dump(..., default_flow_style=False)` 自动用块标量。 |
| 11 | Mermaid 标签中的 `()` `,` 等特殊字符未用引号包裹 `A[label(内容)]` → 渲染报错 `Syntax error in graph` | 标签必须用 `A["label(内容)"]` 包裹。`scripts/validate_mermaid.py` 可批量检测。 |
| 12 | Agent 把 graph 写在一行 `graph TD A-->B A-->C` 内 → 某些渲染器失败 | 必须用多行：每个节点/边一行。`scripts/validate_mermaid.py` 可检测。 |
| 13 | 把领域专有词硬编码到信号词列表（signals 含 dBm/FDTD/PCB 等 EMC 术语）→换本机械/生物教材匹配全失效 | **两阶段信号词体系：** `_LANG_SIGNALS`（中文技术写作通用模式，领域无关）+ `_extract_domain_signals()`（运行时从源文自动提取单位词、节标题术语、高频技术词）。零硬编码领域词。详见 `yaml_writer.py` 中的 `_extract_domain_signals()`。 |

## 领域自适应设计原则

| 原则 | 说明 |
|------|------|
| **信号词不分领域硬编码** | `_LANG_SIGNALS` 只含中文技术写作通用模式（"是指/称为/导致/注意/①"），不含任何领域的专有词 |
| **领域词从源文自动提取** | `_extract_domain_signals()` 通过 `\d+[unit]` 模式提取单位、节标题提取领域术语、高频词统计提取技术词 —— 换书零配置 |
| **不需要 embedding** | 规则足够细 + 运行时自适应 = 语义级匹配。embedding 增加几百 MB 依赖和 10 倍+延迟，非必需 |
| **`@prompt` 是原料不是指令** | Agent 把模板 `<!-- @prompt ... -->` 当作写作指导原料，结合当前章节源文自行形成一次性自指导提示词。人工改 @prompt 文字即可控制输出质量 |

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| [mermaid-graph-troubleshooting.md](references/mermaid-graph-troubleshooting.md) | Mermaid核心概念图语法问题调试指南（括号引用/单行图/YAML块标量） |
| [yaml-multiline-escaping.md](references/yaml-multiline-escaping.md) | YAML 多行转义问题：`\n` 字面量污染排查方案 |
| [template-prompt-convention.md](references/template-prompt-convention.md) | @prompt 写作指导约定：格式/原则/Agent 使用方式 |
| [template-yaml-field-map.md](references/template-yaml-field-map.md) | 模板-YAML 字段映射表（8种类型的 bd 字段详细说明） |
| [golden-kp-example.md](references/golden-kp-example.md) | KP YAML 金标范例 |
| [golden-sp-example.md](references/golden-sp-example.md) | SP YAML 金标范例 |
| [golden-scene-example.md](references/golden-scene-example.md) | Scene YAML 金标范例 |
| [chapter-data-generation.md](references/chapter-data-generation.md) | Agent 写 YAML 指南 |
| [yaml-generation-guide.md](references/yaml-generation-guide.md) | YAML 数据格式规范 |
| [quality-gate-architecture.md](references/quality-gate-architecture.md) | 质量门架构 |\n| [link-audit-design.md](references/link-audit-design.md) | wikilink 审计设计 |\n| [dag-flow-optimization.md](references/dag-flow-optimization.md) | DAG流程分析与改进方案（P0/P1/P2优化路线图） |
