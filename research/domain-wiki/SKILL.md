---
name: domain-wiki
description: "从教材源文件构建结构化 Obsidian 知识库：write_yaml → pipeline_v2 phase-a → 40+文件/章。模板自携带@prompt写作指导，yaml_writer.py pydantic校验，零对照表"
version: "2.3"
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
    Agent 写 YAML 前先看 @prompt:
    yaml_writer.py prompt --type concept
```

**核心文件**（仅 7 个脚本，已全面清洗）：

| 文件 | 职责 |
|------|------|
| `scripts/pipeline_v2.py` | 编排器：校验 YAML → 驱动 template_engine |
| `scripts/yaml_writer.py` | YAML 写入 + pydantic 校验 + @prompt 提取 |
| `scripts/template_engine.py` | 模板渲染：读 schema → 填 {{xxx}} → 自动包裹 mermaid 图 → 剥离 @prompt 注释 |
| `schemas/domain_book_schema.json` | 字段定义（类型/必填/constraints） |
| `assets/templates/*.md` | 15 个模板（含 @prompt 写作指导） |
| `scripts/split_book_to_chapters.py` | 整书 MD 拆分 |
| `scripts/link_audit.py` | wikilink 审核 |
| `scripts/validate_mermaid.py` | 批量验证概念文件的 Mermaid 图语法 |

## 核心设计原则

### 模板是字段的单一权威源（用户核心要求）

每个模板 `.md` 文件同时包含一切信息，**不需要任何外部对照表**：

1. **`{{xxx}}` 占位符** — template_engine.py 输出格式
2. **`<!-- @prompt ... -->` 注释** — Agent 写作指导（写什么、多长、什么格式）

改了模板就等于改了所有。新增一个字段只需在模板中写 `{{new_field}}` 加一行 `<!-- @prompt ... -->`。不需要改 schema.json、不需要维护 template-yaml-field-map.md、不需要单独写提示词文档。

**Agent 写 YAML 的正确工作流：**
```bash
yaml_writer.py prompt --type concept           # 看全部字段要求
yaml_writer.py prompt --type kp --field theoretical_basis  # 只看一个字段
```

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

**写 YAML → 校验 → 渲染**（三步完成一章）：

```bash
# 1. Agent 写 YAML（先用 prompt 看写作要求）
python3 scripts/yaml_writer.py prompt --type concept
python3 scripts/yaml_writer.py write --type concept --yaml-path .dag/第N章/data/concepts.yaml --items '[...]'

# 2. 全量校验
python3 scripts/yaml_writer.py validate-dir --dir .dag/第N章/data/

# 3. 渲染
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book \
  -c N \
  --book-id 01_书ID \
  --book-name 书名

# 4. 验证输出的Mermaid图语法（排查括号未引用、单行图等）
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
| 10 | YAML 中存在 `\n`（字面反斜杠+n）而非真正的换行 → mermaid graph 渲染为一行 `graph TD\n  A-->B` | YAML 中多行 graph 必须用 `|` block scalar：`core_concept_map: |-\n  graph TD\n    A[label] --> B[label2]`。不能用双引号 + `\n` 转义——会被 yaml.safe_load 解析为字面 `\n` 字符串而非换行。 |

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| [template-prompt-convention.md](references/template-prompt-convention.md) | **v2.2** — `@prompt` 写作指导约定：格式/原则/Agent 使用方式/重要性排序 |
| [template-yaml-field-map.md](references/template-yaml-field-map.md) | 模板-YAML 字段映射表（8种类型的 bd 字段详细说明） |
| [golden-kp-example.md](references/golden-kp-example.md) | KP YAML 金标范例 |
| [golden-sp-example.md](references/golden-sp-example.md) | SP YAML 金标范例 |
| [golden-scene-example.md](references/golden-scene-example.md) | Scene YAML 金标范例 |
| [chapter-data-generation.md](references/chapter-data-generation.md) | Agent 写 YAML 指南 |
| [yaml-generation-guide.md](references/yaml-generation-guide.md) | YAML 数据格式规范 |
| [quality-gate-architecture.md](references/quality-gate-architecture.md) | 质量门架构 |
| [batch-analysis-pattern.md](references/batch-analysis-pattern.md) | 批量分析→修复→验证工作模式 |
| [link-audit-design.md](references/link-audit-design.md) | wikilink 审计设计 |
| [mermaid-graph-troubleshooting.md](references/mermaid-graph-troubleshooting.md) | Mermaid核心概念图语法问题调试指南（括号引用/单行图/YAML块标量） |
