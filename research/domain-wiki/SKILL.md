---
name: domain-wiki
description: "从教材源文件构建结构化 Obsidian 知识库：write_yaml → pipeline_v2 phase-a → 40+文件/章。模板@prompt + dag_state状态管理 + KG索引 + 测试套件"
version: "3.0"
author: Hermes Agent
license: MIT
metadata:
  category: research
  related_skills: [source-prepare, file2md]
---

# Domain Wiki Builder (v3.0)

## Anti-Bloat Maintenance Covenant

每次修改本技能时，Agent 必须遵守以下守则，防止重蹈 domain-book-wiki 的覆辙：

### 模块容量红线
| 规则 | 阈值 | 违规处理 |
|------|------|----------|
| 单文件 ≤600行 | 超过即拆 | 提取为独立模块（见"模块分解模式"） |
| 单函数 ≤80行 | 超过即拆 | 提取内部函数或拆分逻辑 |
| 配置数据不混入引擎代码 | 发现即移 | 纯字典/列表 → 独文件（如 `review_field_depth.py`） |

### 模块分解模式
当一个文件超过 600 行时，按以下模式拆分：
```
原文件（多职责混杂）    → 拆分方向
quality_reviewer.py     → 配置数据(.py) + 格式化(.py) + 引擎+CLI(.py)
yaml_writer.py          → schema+校验(.py) + 信号词引擎(.py) + CLI入口(.py)
pipeline_v2.py          → 编排器(.py) + review-fix(.py) + 索引构建(.py)
```
每层只能单向 import：`配置数据 ← 引擎 ← 格式化输出/CLI`。禁止逆向 import。

### 死代码清理检查表
每次提交前（或至少每 3 次迭代后）执行：
```
① grep -rln "script_name" scripts/      # 检查是否被任何 py 文件 import
② grep -rn "script_name" SKILL.md      # 检查是否在技能文档中引用
③ grep -rn "script_name" references/    # 检查是否在参考文档中引用
④ 如果零引用 → git rm + 更新文档      # 确认删除
```

### 领域词审计
每次新增 `_KEYWORDS` / `_LABELS` / `_TAGS` / 分类逻辑后执行：
```
grep -rn "EMC\|dB\|MHz\|GHz\|PCB\|FDTD" scripts/ --include="*.py"
```
零匹配才算通过。领域词只能出现在 `_extract_domain_signals()` 的运行时路径中。

### 目录结构的三处事实源（需保持同步）
| 事实源文件 | 定义的目录 | 用途 |
|-----------|-----------|------|
| `scripts/split_book_to_chapters.py` BOOK_DIRS | 物理目录结构（10-90_*） | `prepare` 命令创建目录 |
| `scripts/review_field_depth.py` TYPE_YAML_MAP | 类型→输出目录映射 | 质量审查时读渲染文件 |
| `scripts/yaml_signals.py` _output_dir() | 类型→输出目录映射（重复） | self-instruct 提示 |
新增目录时必须在三处同步添加。`pipeline_v2.py` 不存目录映射，从 TYPE_YAML_MAP 动态获取。

## When to Use

用户要求从教材构建结构化 Obsidian 知识库，包含核心概念、知识要素、知识点、技能点、应用场景、实体、习题和解答。支持整书全自动流程（Phase A → 质量门 → L2/L3/L4索引 → 状态持久化）。

## v3 Pipeline 概览

```
写 YAML → yaml_writer.py validate → pipeline_v2.py phase-a
         ↓                              ↓
    pydantic 校验字段、confidence   读 schema+模板 → 填 {{xxx}} → 输出 40+ .md
         ↓
    Agent 写 YAML 前先生成自指导提示词:
    yaml_writer.py self-instruct --type concept -c N --book-dir .
```

## 核心文件（20 个脚本 + 1 验证脚本 + 1 测试套）

| 文件 | 职责 |
|------|------|
| `scripts/pipeline_v2.py` | 编排器：校验 YAML → 驱动 template_engine → 质量门 → 状态持久化。10子命令 |
| `scripts/phase_a.py` | Phase A 构建引擎（从 pipeline_v2.py 拆分）。含 phase_a()、PHASE_A_STEPS、run_script、get_chapter_dir |
| `scripts/pipeline_fix.py` | review-fix 流程：调用 quality_reviewer → 解析JSON → 输出FIX指令 → 修复后重渲染+审查 |
| `scripts/yaml_writer.py` | YAML 写入 + pydantic 校验 + @prompt 提取 + self-instruct 自指导 |
| `scripts/template_engine.py` | 模板渲染：读 schema → 填 {{xxx}} → 自动包裹 mermaid 图 → 剥离 @prompt 注释 |
| `scripts/kg_builder.py` | 知识图谱引擎。从 .md frontmatter→nodes, wikilinks→edges, SQLite 存库。支持 build/query/search/trace/quality_check。接受 str 或 list[str] book_dir（领域级跨书扫描）。构造需 wiki_root(DB存放) + book_dir(扫描目录) 两个参数 |
| `scripts/graph_analytics.py` | 图分析函数集。build_graph_section() 产出 8+ 板块：知识链连通率、节点连接性、图质量摘要、核心节点排名、Mermaid全景、章节分布、学习路径、待修复项 |
| `scripts/index_builder.py` | L2 索引构建器（知识图谱驱动）。4步流程：构建 KGraph → 图分析 → 生成索引 YAML → 渲染到 10_总揽/。`--skip-kg` 跳过KG构建回退到文件扫描。被 pipeline_v2.py build-indices 子命令触发 |
| `scripts/dag_state.py` | 状态管理器。ChapterState 支持 14 阶段追踪、依赖检查、断点续传(--resume)。phase_status_summary() 全书总览表。PipelineError 统一异常 |
| `scripts/l3_l4_builder.py` | L3(领域总控)+L4(知识库总控) 索引构建。跨书/跨领域扫描，集成 KGraph。输出 领域总控/domain_overview.md + 知识库总控/kb_overview.md |
| `scripts/quality_reviewer.py` | 质量审查引擎 v2.1（模块化）。T1结构/T2深度/T3交叉引用引擎。check-item子命令内联检查单项YAML（写一个过一件）。fix-manifest子命令生成修复清单。配置数据→review_field_depth.py，格式化→review_format.py |
| `scripts/review_field_depth.py` | 配置数据层：FIELD_DEPTH(字段深度阈值)、FM_REQUIRED/OPTIONAL、TYPE_YAML_MAP。纯字典，零运行时依赖 |
| `scripts/review_format.py` | 格式化输出层：format_report(人类报表)、build_json_output(Agent JSON+fix_manifest)、build_fix_manifest(修复清单)、print_fix_instructions(FIX_FILE指令) |
| `scripts/validate_mermaid.py` | 批量验证概念文件的 Mermaid 图语法（括号引用、单行图） |
| `scripts/wikilink_fixer.py` | 非对称链接自动补全（A→B 则 B 追加 ←A，解决 373+ 对不对称） |
| `scripts/wikilink_deep_fixer.py` | 基于章节归属的出链=0节点智能补链（同章概念→KE→实体互联） |
| `scripts/verify_domain_agnostic.sh` | 领域无关验证：扫描所有 .py 确认无硬编码领域专有词 |
| `schemas/domain_book_schema.json` | 字段定义（类型/必填/constraints） |
| `assets/templates/*.md` | 15 个模板（含 @prompt 写作指导） |
| `scripts/split_book_to_chapters.py` | 整书 MD 拆分 + content_list_v2.json 正文重建。prepare/split/reconstruct 三子命令 |
| `tests/test_core.py -v` | 12 个测试（状态管理/KG构建/pipeline CLI） |


## 绝对守则（用户反复纠正，牢记）

### 守则1: 只用技能文档化命令，不写自定义脚本

这个技能的每步操作都有 PL 提供的命令（`pipeline_v2.py phase-a / run / review / review-fix / build-indices`）。
任何写临时 Python 脚本的行为都是错误的——会引入不可维护的碎片、绕过质量门、且在技能迭代时被遗忘。

| 禁忌 | 替代方案 |
|:-----|:---------|
| 写一个 Python 脚本批量改 YAML | `yaml_writer.py validate / self-instruct` + Agent 逐项内联检查 |
| 写一个脚本 enrich 所有概念 | `delegate_task` + `quality_reviewer.py check-item` 内联工作流 |
| 写一个脚本检测问题 | 用 PL 的 `review / review-fix / quality-gate` 命令 |
| 全手动改文件 | 用 `pipeline_v2.py run` 自动推进 |

**检查：** 每次提交前运行 `git diff --stat`，如果有新增 `.py` 文件不在 SKILL.md 核心文件列表中，它不该存在。

### 守则2: 全自动，不问问题

这个技能的 `pipeline_v2.py run` 命令设计为一次执行完所有待处理阶段。用户期望零打断的自动管线。

- 质量门低分 → 直接运行 `review-fix --re-render --apply` 自动修复
- 概念不够 → 用 `delegate_task` 让 Agent 用 `self-instruct` 补充，不要问要不要
- 有任何问题 → 直接做，不要用「要我现在 X 吗？」「需要我处理 Y 吗？」这种句式

**用户原话：**「为什么不能全自动？为什么一直问我？质量审查体系一点作用都没有吗？」

### 守则3: 文件名不用版本号后缀

`pipeline_v2.py` 是命名反模式——暗示未来会有 `pipeline_v3.py`、`pipeline_v4.py` 的膨胀路径，和 `domain-book-wiki` 的 `dag_pipeline_run.py` / `pipeline_auto.py` 前缀过载同一类问题。

命名规则：`{模块名}.py`，无版本后缀。超 600 行时按 Anti-Bloat Covenant 拆分，保持原名。

### 守则4: 不要在备份技能上改代码

`research/domain-book-wiki/` 是 commit `8c3cd15` 标注的**历史备份**。改它 = 浪费时间。

验证方法（每次编辑前执行，非可选）：
```bash
grep -c '@prompt' ~/.hermes/skills/research/domain-wiki/assets/templates/concept_template.md
# 期望 24 — 如果得到 0，说明改错技能了
```

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

# C（推荐用于delegate_task）：从@prompt原料构建结构化Agent提示词
python3 scripts/yaml_writer.py build-prompt --type concept -c N
#    输出: 写作总则 + 逐字段要求(@prompt+字数) + 输出格式 + 质量检查
#    将此输出直接注入 delegate_task context 作为Agent的写作指引

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

### 质量审查输出必须结构化供Agent消费

质量审查的输出**不是给人看的报告**，而是供Agent解析并触发自动修复的结构化数据。

| 原则 | 说明 |
|:-----|:------|
| **JSON是默认输出** | `--json` 输出含 `scope`/`type_scores`/`fix_manifest` 的结构化JSON。每项修复含 `{file, type, score, yaml_path, fields_to_fix: [{field, action, current_len, target_len}]}`。Agent直接解析JSON即可知道*哪个文件、哪个字段、缺多少字、从哪里补* |
| **修复指令预格式化** | `review-fix` 命令输出 `FIX_FILE:`/`FIX_TYPE:`/`FIX_FIELDS:`/`FIX_SOURCE_DIR:` 行格式，Agent可以逐行解析后委托子Agent批量修复 |
| **修复阈值独立** | `--fix-threshold`（修复清单阈值，默认0.8）与 `--threshold`（exit阻断阈值，默认0.5）解耦。高质量场景可以用 0.9 作为修复目标但不阻断pipeline |
| **全局均分掩盖局部问题** | 全书评分90%时，概念类型可能只有70%。`fix_manifest` 按文件级评分检测（非类型级），避免高分掩盖局部低分 |
| **内联检查优先于事后修复** | 在生成YAML项的**当时就地检查**，问题字段当场修复后再存入聚合YAML，而非事后批量回查。使用 `check-item` 子命令逐项检测，实现"写一个过一件" |

### 内联质量检查流程（Agent生成YAML时使用）

生成YAML项目时**逐个检查、逐个通过**后再写入聚合文件，而非全部生成后再回查。

```
for each YAML item to generate:
  ① Agent 基于源文写定该项的 bd 字段内容
  ② quality_reviewer.py check-item --item '...' --type concept --threshold 0.9
     ↓
     通过 → ③ 追加到 YAML 文件 → next item
     失败 → ④ 逐字段按 fix_manifest 丰富 → 回到 ② 重检
```

**Agent 在 delegate_task 中的具体做法：**
```python
# 生成单项YAML内容后
import subprocess, json

item = {"name": "...", "fm": {...}, "bd": {...}}  # Agent写的内容

# 内联质量检查
r = subprocess.run([
    "python3", "scripts/quality_reviewer.py", "check-item",
    "--type", "concept",
    "--item", json.dumps(item, ensure_ascii=False),
], capture_output=True, text=True)

result = json.loads(r.stdout)

if result["pass"]:
    write_to_yaml(item)  # 通过 → 写入
else:
    for issue in result["issues"]:
        if issue["action"] == "enrich":
            # 从源文补充内容
            item["bd"][issue["field"]] = enrich_from_source(
                item["bd"][issue["field"]],
                source_text,
                issue["target_len"]
            )
        elif issue["action"] == "fill":
            item["bd"][issue["field"]] = fill_from_source(...)
    # 重新检
    r2 = subprocess.run([...], ...)
    assert json.loads(r2.stdout)["pass"]
    write_to_yaml(item)
```

**命令行用法：**
```bash
# 检查单个YAML项（概念）
python3 scripts/quality_reviewer.py check-item \
  --type concept --threshold 0.9 \
  --item '{"name":"电场耦合","fm":{"source_chapter":"3","confidence":0.95},"bd":{"term_definition":"定义内容...","learning_objectives":"目标..."}}'

# 返回JSON: {score, pass, issues: [{field, severity, current_len, target_len, action}]}
```

### 工程 vs 内容边界原则

| 归属 | 特征 | 由谁执行 |
|:-----|:-----|:---------|
| 工程化 | 确定性输入→输出 | Python 脚本：模板渲染、格式校验、YAML schema 校验 |
| 内容 | 需语义理解 | Agent (LLM)：概念抽取、内容写作、教学质量 |

### 跨章一致性检查（v3.0+）

`quality_reviewer.py` 中的 `check_cross_references()` 在 book 级审查时自动执行三遍扫描：
1. 收集所有节点名称→文件映射
2. 检测同名概念跨类型/跨文件冲突（`cross_chapter_conflict`）
3. 验证 wikilink 目标是否存在（`wikilink_broken`）

```bash
# 触发方式：在 book 级审查中自动执行
python3 scripts/pipeline_v2.py review --book-dir /path --book-id 01_ID
```

## Quickstart

**优先级：内联检查（写一个过一件） > 事后批量审查（安全网）**

### 第一步：生成 YAML 时做内联质量检查（推荐）

在 delegate_task 中逐项生成时，每写完一个 YAML 项立即内联检查：

```bash
# 在子Agent中每生成一个YAML项后：
python3 scripts/quality_reviewer.py check-item \
  --type concept --threshold 0.9 \
  --item '{"name":"概念名","fm":{"source_chapter":"N","confidence":0.95},"bd":{...}}'
```

子Agent流程：
```
for each_item:
  ① 基于源文写 bd 字段
  ② check-item --type concept --threshold 0.9
     ├─ pass → 追加到 YAML → next
     └─ fail → 按 issues[{field, target_len, action}] 丰富 → 回到 ②
```

不通过当场丰富重检，通过后才追加到 `concepts.yaml`。详见 [inline-quality-workflow.md](references/inline-quality-workflow.md)

### 第二步：全量校验 + Phase A 渲染（自动质量门 + Preflight）

所有 YAML 写完后，全量校验 + 渲染 + 自动质量门：

```bash
# 0. Preflight（可选，v3.0+ 集成在 phase-a 中）
#    写入 YAML 后/渲染前的完整性闸门：
#    ├─ 8种YAML文件存在性+语法+字段缺失/多余
#    ├─ confidence范围、LaTeX公式格式
#    ├─ 概念覆盖度、习题-解答配对
#    自动作为 Phase A Step 0 执行，发现问题只报告不阻断。
#    也可独立运行检查：
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book -c N --book-id 01_书ID --book-name "书名"
# 其 Step 0 会自动完成 preflight

# 1. 全量校验
python3 scripts/yaml_writer.py validate-dir --dir .dag/第N章/data/

# 2. 渲染 + 自动质量门（Step 0→3 自动完成以下检查）：
#    ├─ Step 0: Preflight — YAML完整性闸门
#    ├─ Step 1: YAML schema校验
#    ├─ Step 2: 模板渲染
#    ├─ Step 3a: Mermaid语法验证
#    ├─ Step 3b: 章节关联wikilink修复（出链=0 → 同章关联）
#    ├─ Step 3c: 反向链接补全（A→B则B也→A）
#    └─ Step 4: 质量审查
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book \
  -c N \
  --book-id 01_书ID \
  --book-name "书名"
**全书质量门**（可选，批量检查所有已渲染章节）：
```bash
python3 scripts/pipeline_v2.py quality-gate --book-dir /path/to/book
```

**质量审查**（支持Agent可消费JSON输出 + 自动修复指令）：

```bash
# 全书审查（人类可读）
python3 scripts/pipeline_v2.py review \
  --book-dir /path/to/book --book-id 01_书ID

# 单章审查（含具体问题列表）
python3 scripts/pipeline_v2.py review \
  --book-dir /path/to/book --book-id 01_书ID -c 3 -v

# 输出JSON供Agent消费（含fix_manifest修复清单）
python3 scripts/pipeline_v2.py review \
  --book-dir /path/to/book --book-id 01_书ID -c 3 --json

# 设定阈值（低于则exit 1，可用作CI门禁）
python3 scripts/pipeline_v2.py review \
  --book-dir /path/to/book --book-id 01_书ID -c 3 --threshold 0.3

# 审查+生成Agent可消费的修复指令（文件级精确字段修复）
python3 scripts/pipeline_v2.py review-fix \
  --book-dir /path/to/book --book-id 01_书ID -c 3 --threshold 0.9

# 保存修复清单到JSON文件，供Agent批量处理
python3 scripts/pipeline_v2.py review-fix \
  --book-dir /path/to/book --book-id 01_书ID -c 3 --threshold 0.9 --output fix.json

# Agent修复YAML后重新渲染+审查
python3 scripts/pipeline_v2.py review-fix \
  --book-dir /path/to/book --book-id 01_书ID -c 3 --re-render --apply

**运行测试套件**（12个测试覆盖核心模块）：
```bash
python3 tests/test_core.py -v
# 预期: 12/12 tests passed
# 覆盖: dag_state(6) + KGraph(4) + pipeline CLI(2)
```

**自动按序处理**（从当前状态自动识别下一个待处理阶段并执行，支持断点续传）：
```bash
# 自动处理所有待处理阶段
python3 scripts/pipeline_v2.py run \
  --book-dir /path/to/book -c N \
  --book-id 01_书ID --book-name "书名"

# 查看全书状态总览
python3 scripts/pipeline_v2.py overview \
  --book-dir /path/to/book --book-id 01_书ID
```

**状态管理**：每章自动创建状态文件 `.dag/书籍ID_chN.json`，14 阶段追踪（chapter_toc→concepts→ke→entities→kp→sp→scene→exercises→solutions→quality_review→auto_fix→l2_indices→l3_indices→l4_indices），支持断点续传：`phase-a --resume` 跳过已完成阶段。`run` 命令自动识别下一个待处理阶段。

**整书预处理**（已有整书 MD 时，带已有 `content_list_v2.json` 的自动重建正文）：
```bash
python3 scripts/split_book_to_chapters.py prepare \
  --raw-dir /path/to/raw/书籍名/ \
  -w $BOOK_DIR --split

# 若章节文件仅含标题无正文（源文件缺失），从 content_list_v2.json 重建：
python3 scripts/split_book_to_chapters.py reconstruct \
  -w $BOOK_DIR \
  --v2-path /path/to/raw/书籍名/书籍名_content_list_v2.json
# reconstruct 命令利用每页的 page_header（如"第3章"）确定章节边界，
# 提取标题+正文段落重建章节文件。零硬编码，通用中文教材。
```
**构建 L2/L3/L4 索引**（全量Phase A完成后执行）：

```bash
# 一键L2索引（KG驱动）
python3 scripts/pipeline_v2.py build-indices \
  --book-dir /path/to/book \
  --book-id 01_书ID \
  --book-name "书名"

# L3 领域总控
python3 scripts/l3_l4_builder.py l3 \
  --book-dir /path/to/book \
  --book-id 01_书ID --book-name "书名"

# L4 知识库总控  
python3 scripts/l3_l4_builder.py l4 \
  --book-dir /path/to/book --book-id 01_书ID

# 跳过KG（仅文件扫描）
python3 scripts/index_builder.py /path/to/book \
  --book-id 01_书ID --book-name "书名" --skip-kg
```

**索引产出**：`10_总揽/` 目录下 5 个索引文件：
| 文件 | 内容 | 数据源 |
|------|------|--------|
| `book_overview.md` | 总览（连通率、Mermaid、Top10、章节分布、学习路径、4类索引表、质量项） | KG + 文件扫描 |
| `concept_index.md` | 概念索引（按分类+章节） | 文件扫描 |
| `knowledge_index.md` | 知识点索引（按Bloom层级+章节） | 文件扫描 |
| `skill_index.md` | 技能点索引（按章节） | 文件扫描 |
| `scenario_index.md` | 应用场景索引（按章节） | 文件扫描 |

**知识图谱引擎注意事项**：
- `KGraph(wiki_root, book_dir)` — wiki_root 为知识库根目录（存 DB 用），book_dir 为书籍工作目录（扫 .md 用）
- book_dir 接受 str（单书）或 list[str]（多书/领域级/全库级扫描）
- KG 按 book_dir 范围构建，所有节点自动从该书籍的 30_核心概念/ 等目录扫描
- 空 confidence 值会被解析为 0.0，不会导致构建失败
- L3/L4 构建时 KGraph 传入所有书籍目录列表实现跨书分析

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

## ⚠️ CRITICAL: VERIFY SKILL IDENTITY BEFORE ANY ACTION

**This skill has a DEADLY LOOKALIKE: `research/domain-book-wiki/` (a v52.x backup).**
Every edit, every command, every `cd` MUST verify you're in the right directory.

### Automated Identity Check (MANDATORY before any edit)

```bash
# === IDENTITY CHECK (run this BEFORE any edit) ===
grep -c '@prompt' ~/.hermes/skills/research/domain-wiki/assets/templates/concept_template.md
# Expected: 24 — if 0, you are in domain-book-wiki (the BACKUP).
# STOP IMMEDIATELY. Switch to domain-wiki.
```

### The "No Ad-Hoc Scripts" Rule

This skill is designed to be fully automatic through its documented commands. **DO NOT write temporary Python scripts** to work around pipeline steps. The documented commands are:
- `pipeline_v2.py phase-a` — validate + render
- `pipeline_v2.py run` — fully automatic pipeline (14 phases)
- `pipeline_v2.py quality-gate` — Mermaid + wikilink
- `pipeline_v2.py review / review-fix` — quality
- `pipeline_v2.py build-indices` — L2/L3/L4
- `yaml_writer.py validate / self-instruct / prompt / build-prompt` — YAML tools
- `split_book_to_chapters.py prepare / split` — book prep

If you need to do something and no skill command exists, fix the SKILL or use the existing commands — do not write a one-off script.

### Run Fully Automatically, Do Not Ask

The `pipeline_v2.py run` command processes ALL pending phases automatically. When the user asks to process a book:
1. Prepare: `split_book_to_chapters.py prepare --raw-dir RAW -w BOOK --split`
2. Write YAML (Agents via `yaml_writer.py`)
3. Run: `pipeline_v2.py run --book-dir BOOK -c N --book-id ID --book-name NAME`
4. Quality: `pipeline_v2.py quality-gate --book-dir BOOK`
5. Review: `pipeline_v2.py review --book-dir BOOK --book-id ID`
6. Indices: `pipeline_v2.py build-indices --book-dir BOOK --book-id ID --book-name NAME`

**Do NOT ask the user "should I proceed?" or "what next?" — just do the next step.**

**Why this matters:** There are TWO near-identically-named skills:
- `research/domain-wiki/` — **ACTIVE** (v3.0, `pipeline_v2.py`, 24 `@prompt`) ← USE THIS
- `research/domain-book-wiki/` — **HISTORICAL BACKUP** (v52.x, `dag_controller.py`, 0 `@prompt`) ← DO NOT TOUCH

Commit `8c3cd15` explicitly states: *"当前活跃技能为 research/domain-wiki/ (v2.x)。此目录仅作历史参考。"*

**History:** The previous agent session wasted 2 full commits modifying the backup, had to `git revert`, and received user frustration. All because they skipped the verification grep.

**Quick reference:**
| Skill | Pipeline | Prompt system | Agent YAML tool |
|-------|----------|---------------|-----------------|
| `domain-wiki` (ACTIVE) | `pipeline_v2.py phase-a / run` | `yaml_writer.py prompt --type concept` (24 `@prompt`) | `yaml_writer.py self-instruct` |
| `domain-book-wiki` (BACKUP) | `dag_controller.py pipeline auto` | None (0 `@prompt` in templates) | `yaml_auto_fill.py llm-prompt` |

## Pitfalls

| # | Trap | Prevention |
|:--|:-----|:-----------|
| 1 | 模板 `{{xxx}}` 与 schema BD 字段不一致（schema 缺字段或有多余字段） | 模板是字段的唯一权威源。写模板时加 `<!-- @prompt ... -->`，必要时才更新 schema.json |
| 2 | `@prompt` 注释泄漏到渲染输出 | template_engine.py 的 `render_item()` 必须在替换完所有 `{{xxx}}` 后执行 `re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)` |
| 3 | 习题文件名双前缀（"第11章-第11章-习题1.md"） | `EXERCISE_FILENAME_MAP` 和 `_gen_exercise_content` 中先检查 `name` 是否已含 `第N章-` 前缀，避免重复 |
| 4 | 解答 `question` 太短（<20字）被 schema 拦截 | solution 的 `question` 字段有 `min_chars: 20` 约束。直接从习题 YAML 复制原文 |
| 5 | Agent 写的 `theoretical_basis` 太短（<150字）被拦截 | schema 中有 `min_chars` 约束。写之前用 `yaml_writer.py prompt --type kp --field theoretical_basis` 看要求 |
| 6 | 内容质量的根因不是 prompt 不够细，而是源文不在上下文。prompt 只能解决"格式"，解决不了"深度" | Agent 写 YAML 前必须精读源文对应段落。prompt 命令只是锦上添花，不是雪中送炭。 |
| 7 | **子代理写 YAML 时未拿到 @prompt 指引**（仅用了 `skeleton` 看字段名）→ 内容质量差：字数不足、无LaTeX公式、Mermaid格式错误、字段内容空洞 | delegate_task context 中必须包含 `yaml_writer.py build-prompt --type TYPE -c N` 的输出。模板 `<!-- @prompt ... -->` 是**原料**，需用 `build-prompt` 加工成结构化提示词（写作总则+逐字段要求+字数约束+格式规范+输出模板+校验指令）后注入 context。不要只给子代理 `skeleton` 输出（字段名清单不含任何写作指导）。 |
| 7 | `confidence` 值超出允许范围（如 exercise 写 0.85 但只允许 0.65） | schema.json 每类型有 `confidence.allowed` 枚举。`yaml_writer.py write` 在校验阶段直接 reject |
| 8 | 换书：章节文件名、关键词、教材描述全硬编码 | 所有领域信息已在 `_extract_domain_signals()` 中运行时自动提取。章节文件名通过 `get_source_path()` 自动发现（`f.startswith(f"第{chapter}章")`）。不再需要外部配置。详见 `scripts/verify_domain_agnostic.sh`。 |
| 9 | 核心概念图的 `core_concept_map` 不含 ` ```mermaid ` fence → Obsidian 把 graph TD 当普通文字渲染，不显示图 | **引擎层防护**：`template_engine.py._auto_wrap_mermaid()` 自动检测 raw `graph TD/LR/flowchart/sequenceDiagram` 等 mermaid 语法并包裹代码块。**Agent 写 YAML 时的预防**：`core_concept_map` 只需写 `graph TD\n  A[label] --> B[label2]` 内容本身，不需要加 `` ```mermaid `` fence（引擎会加）。纯文字描述（如"接地是EMC四大技术之一"）不会被引擎转换，需重写为 graph 格式。 |
| 10 | YAML 中存在 `\n`（字面反斜杠+n）而非真正的换行 → mermaid graph 渲染为一行 | YAML 中多行 graph 必须用 `|` block scalar：`core_concept_map: |-\n  graph TD\n    A[label] --> B[label2]`。`yaml.dump(..., default_flow_style=False)` 自动用块标量。 |
| 11 | Mermaid 标签中的 `()` `,` 等特殊字符未用引号包裹 `A[label(内容)]` → 渲染报错 `Syntax error in graph` | 标签必须用 `A["label(内容)"]` 包裹。`scripts/validate_mermaid.py` 可批量检测。 |
| 12 | Agent 把 graph 写在一行 `graph TD A-->B A-->C` 内 → 某些渲染器失败 | 必须用多行：每个节点/边一行。`scripts/validate_mermaid.py` 可检测。 |
| 13 | 把领域专有词硬编码到信号词列表（signals 含 dBm/FDTD/PCB 等 EMC 术语）→换本机械/生物教材匹配全失效 | **两阶段信号词体系：** `_LANG_SIGNALS`（中文技术写作通用模式，领域无关）+ `_extract_domain_signals()`（运行时从源文自动提取单位词、节标题术语、高频技术词）。零硬编码领域词。详见 `yaml_writer.py` 中的 `_extract_domain_signals()`。 |
| 14 | 只在 `_LANG_SIGNALS` 做了领域净化，但漏了 `_TEMPLATE_SECTION_KEYWORDS`、`_FIELD_KEYWORDS` 等其他静态关键字映射——这些也把 `dB`、`电平`、`限值` 等 EMC 术语硬编码了进去，产生相同的领域偏置 | **全面审计所有静态列表：** 任何以 `_KEYWORDS`、`_LABELS`、`_TAGS` 命名的模块级常量都可能泄漏领域词。修改后运行 `scripts/verify_domain_agnostic.sh` 验证零匹配。领域词只能出现在 `_extract_domain_signals()` 的运行时提取路径中。每次在 scripts/ 中新增字符串列表必须审计是否含领域专有词。 |
| 15 | 模板 `<!-- @prompt ... -->` 中的示例文本含领域专有词（如 `"电磁兼容/子领域"`、`"诊断EMC故障"`）→ 换本机械/化学教材这些示例词即成为误导 | **模板 @prompt 的示例必须用通用占位描述：** `"大领域/子领域"` 替代 `"电磁兼容/子领域"`，`"诊断故障"` 替代 `"诊断EMC故障"`。写示例时问自己"这句话放生物/金融/机械教材里会不会显得奇怪"。 |
| 16 | `.py` 文件 docstring 中的示例命令行含领域特定值（如 `--book-name "工程电磁兼容第3版_路宏敏"`）→ 读者复制粘贴跑不通他自己的书 | **docstring 示例用占位符：** `--book-id 01_书籍ID --book-name "书籍名称" -c N`。全书搜 `工程电磁兼容`、`电磁兼容`、`EMC` 等词确认零出现在代码/docstring 中。 |
| 17 | Phase A 渲染完成后不跑 wikilink 修复 → 概念/KE/实体之间约 60-80% 只有出链无人链，知识图谱呈单向森林状 | Phase A 渲染后必须顺序执行：`wikilink_deep_fixer.py`（同章关联）→ `wikilink_fixer.py`（反向补全）。实测可将孤立率从 84% 降至 13%，非对称链接 399→0。 |
| 18 | 质量检查（Mermaid验证、wikilink修复）作为事后人工步骤 → 被遗忘，用户反馈后才补救 | **质量门必须集成到 pipeline 中，不能作为可选的手动步骤。** `pipeline_v2.py phase-a` 的 Step 3 自动完成：Mermaid验证 → 同章wikilink关联 → 反向链接补全。新增 `quality-gate` 子命令用于全书批检。任何新 Agent 在修改 pipeline 时不得移除 Step 3。 |
| 19 | 多次修改后技能目录积累死脚本、过时配置文件和 reference 文档 → 技能膨胀、后续 Agent 困惑、用户需要额外清理 | **每次提交前执行清理：** ① `grep -rl "dead_script_name" scripts/` 确认无引用后删除 ② 删除后运行 `grep -rn "dead_name" skill_dir/` 确保无断裂引用 ③ 清理不再被 pipeline 读取的 config/ 目录和 references/ 中引用已删除脚本的过时文档 ④ 更新 SKILL.md 的 Reference Index 避免断裂链接 ⑤ `scripts/verify_domain_agnostic.sh` 确保仍在维护。参考 patterns: dead-code-cleanup。 |
| 20 | **构建索引时不使用知识图谱** → book_overview.md 只有简单的列表和统计，无连通率、图质量、核心节点排名、Mermaid全景、学习路径等关键数据 | **索引构建必须集成知识图谱。** `index_builder.py` 的默认流程：构建 KGraph（从所有 .md 文件）→ `graph_analytics.build_graph_section()` 获取 8+ 图分析板块 → 生成含 KG 数据的索引 YAML → 渲染到 `10_总揽/`。`--skip-kg` 仅作为调试回退，不应在生成环境中使用。`pipeline_v2.py build-indices` 子命令自动执行全部流程。 |
| 21 | `KGraph(wiki_root)` **只传 wiki_root 不传 book_dir** → `_scan_all_md_files()` 在 wiki_root 下找 `30_核心概念/` 等目录，但在嵌套布局中这些目录在 `domain/book/` 下，结果为 0 节点 | **KGraph 必须同时接收 wiki_root 和 book_dir 两个参数：** `KGraph(wiki_root, book_dir=book_dir)`。wiki_root = 知识库根目录（存 SQLite DB 用，`{wiki_root}/.dag/knowledge_graph.db`），book_dir = 书籍工作目录（扫 .md 文件用）。 |
| 22 | **Mermaid 图中同名节点在不同类型下重复定义**（如概念和实体都有名称为 "IEC 61000系列标准" 的节点，但 mermaid_safe() 映射为相同标识符）→ Mermaid 渲染报 duplicate node ID 错误 | `graph_analytics.py` 中 `all_nodes` 字典初始化后，每类节点渲染前必须检查 `name not in all_nodes`，只对未出现的名称添加行。在 `build_graph_section()` 中添加 `and name not in all_nodes` 条件。 |
| 23 | **Mermaid 边中源节点和目标节点名称相同但ID不同**（不同概念节点同名但在不同目录下创建了不同文件，通过 wikilink 相互连接）→ Mermaid 渲染出 `A -.-> A` 自环 | `graph_analytics.py` 中输出 Mermaid edge 时跳过 `src == tgt` 的情况。在 `build_graph_section()` 的输出循环中添加 `and src != tgt` 条件。 |
| 24 | **`confidence` 字段在 frontmatter 中为空字符串**（如 `confidence: ""`）→ `float()` 抛出 `could not convert string to float: ''`，KG 构建失败 | `kg_builder.py` 中的 `_process_file()` 在调用 `float(fm.get("confidence", 0))` 前先校验：`float(fm.get("confidence", 0) or 0)` + `try/except (ValueError, TypeError)` 兜底。 |
| 25 | **构建中途中止（如网络中断）→ 所有已完成的阶段信息丢失，需重头再来** → 浪费时间 | **使用状态管理 dag_state.py。** `pipeline_v2.py phase-a --resume` 跳过已完成阶段。`pipeline_v2.py run` 自动检测下一个待处理阶段。状态文件存储在 `.dag/书籍ID_chN.json`。每次成功完成阶段后自动 `state.save()`。 |
| 26 | **只构建了 L2 索引（book_overview/concept_index 等），未构建 L3/L4（领域总控/知识库总控）** → 索引体系不完整 | Phase A 全部完成后，调用 `l3_l4_builder.py all`（L3+L4一次完成）或 `pipeline_v2.py run` 自动推进。L3 产出 `领域总控/domain_overview.md`（跨书），L4 产出 `知识库总控/kb_overview.md`（跨领域）。 |
| 27 | **模板自身有重复节标题**（如 `## 学习目标` 和 `### 学习目标`）→ 渲染后出现视觉冗余 | 新增或修改模板后，先肉眼审查：每个 `##` 和 `###` 节标题是否在同一层级内唯一。`## 学习目标` 下不应再有 `### 学习目标`。通过第3章实测发现并修复。 |
| 28 | **fix_manifest硬编码0.8阈值** → 审查脚本的exit阈值 0.5 和修复清单阈值 0.8 混用同一个参数。当exit阈值设为 0.9 时，fix_manifest用到同样的 0.9，修复强度不足 | **`--threshold` vs `--fix-threshold` 严格分离。** `quality_reviewer.py chapter --threshold 0.3 --fix-threshold 0.9` exit阻断用 0.3（低，不阻断），修复清单用 0.9（高，抓更多补内容）。`pipeline_v2.py` 的 `review-fix` 命令内部用 `--threshold 0.01 --fix-threshold 0.9` 确保不因exit code阻断，同时fix_manifest用高阈值。 |
| 29 | **type级均分掩盖文件级低分** → `build_fix_manifest()` 原设计检查类型级评分（如concept=0.85≥0.8就跳过整个类型），忽略了类型内某些文件只有 0.70 的实际情况 | **fix_manifest必须按文件级评分检测。** 去掉类型级的 `if ts.get("score", 1.0) >= 0.8: continue` 过滤，全部由文件级 `fs.get("score", 1.0) >= threshold` 决定。|
| 30 | **review-fix 命令认为 exit code 0=质量达标** → 整体评分 0.95 但概念分 0.85 低于修复阈值 0.9，修复指令有13个文件需要修复但被"质量达标"挡住 | **review_and_fix() 始终解析JSON的fix_manifest**，不以exit code判断。用极低 `--threshold 0.01` 运行 quality_reviewer 确保不exit 1，独立用 `--fix-threshold` 控制修复清单。|
| | **生成YAML时不做内联质量检查** → 全部写完后再跑review-fix，发现13个文件有问题，需要额外一轮回查修复 | **写一个过一件**：每生成一个YAML项，立即 `quality_reviewer.py check-item --item ... --type ... --threshold 0.9` 检查，不通过当场丰富重检再写入聚合YAML。见"内联质量检查流程"章节。|
| | **`load_yaml_list()` 使用 bare except** → 当 `pyyaml` 未安装时 `import yaml` 抛出 `ModuleNotFoundError`，被 bare `except Exception` 吞掉，静默返回 `[]`，导致全书审查显示 0 项、所有类型评分为 0 | **所有文件 I/O / 导入操作用显式 except 而非 bare except。** `load_yaml_list()` 应先检查 `os.path.isfile(path)`，然后独立 try/except `import yaml` 的 `ImportError`，再用 `except (yaml.YAMLError, OSError):` 处理加载错误。新增文件 I/O 函数必须经过此模式审计。参见 `quality_reviewer.py:load_yaml_list()` 的最终实现。 |
| | **Agent 将 `file` 字段设为源章节文件名（含 `.md`）** → `get_output_filename()` 追加 `.md` 后得到 `.md.md` 双后缀文件。影响所有非习题类型（concept/ke/entity/kp/sp/scene）的 24 个文件 | **双线防御：** ① `template_engine.py:get_output_filename()` 和 `quality_reviewer.py` 中 strip 掉 `file_base` 已有的 `.md` 后缀 ② `yaml_writer.py:cmd_self_instruct()` 在字段工作台开头明确说明 `file` 字段不含 `.md` |
| | **`.venv` 缺少关键依赖（pyyaml/pytest）** → 质量审查和测试静默失败、返回空结果。日常开发依赖变化不会自动传播到已有的 .venv | **初始 setup 和每次新增依赖后运行：** `python3 -m pip install pyyaml pytest`。pyproject.toml 的 `dependencies` 和 `[project.optional-dependencies] test` 必须反映实际运行时依赖。`python3 -m pip list` 验证。 |
| | **SKILL.md 因多次 AI 编辑累积重复章节** → 两个"第一步：内联质量检查"、两个"第二步：全量校验"等，造成文档混乱 | 每次编辑 SKILL.md 后运行 `grep -c "^#" SKILL.md | sort | uniq -d` 检查关键标题唯一性。用 `git diff --stat SKILL.md` 观察新增量远大于删除量时要警觉。 |
| | **pyproject.toml 遗留旧模块引用** | 每次重命名/删除脚本后同步清理 pyproject.toml。搜索 pyproject.toml 中是否还有对已删除模块的引用。git rm 后运行 grep -rn deleted_name pyproject.toml 确认零残留。 |
| | **run 无限循环: PHASE_A_STEPS 吞噬 quality_review** | PHASE_A_STEPS 字典含 quality_review/auto_fix → cmd_run 的 if next_phase in PHASE_A_STEPS 先于 elif quality_review 匹配，调用 phase_a 但不保存这两阶段状态。从 PHASE_A_STEPS 中移除，让独立 elif 分支处理。 |
| | **set_status 静默忽略不存在 phase** | 旧状态文件缺某些 phase 时 set_status 检查 if phase in self._data[phases] 为 False → 什么都不做。save 写出不含该 phase 的状态 → next_pending 永远返回该 phase → 无限循环。set_status 遇到缺失 phase 时自动创建默认条目。 |
| | **run 无限循环: auto_fix/l4_indices 未设 status=done** | auto_fix 原本设 status=pending（等 Agent）→ 循环。l4_indices 缺 state.set_status+state.save → 索引完成但不推进。auto_fix 设 done（不阻断），l4_indices 补上状态保存。 |
| | **run state 对象在 phase_a 后不刷新** | cmd_run 的 state 实例在 phase_a（内部创建独立 ChapterState 存盘）后仍持有旧内存数据 → next_pending 读脏数据。phase_a 返回后执行 state = ChapterState(...) 从磁盘重新加载。 |
| | **YAML `file` 字段含 `.md` 后缀 → 6 种非习题类型输出 `.md.md` 双后缀文件**（`第3章 屏蔽.md.md`），质量审查也查不到这些文件因为同样用了 `{file}.md` 拼接 | **三层防线：**（①防御性 strip）`template_engine.py:get_output_filename()` 中 `file_base.endswith('.md')` 时 strip 掉再追加。`quality_reviewer.py:90` 同样处理。（②Agent 指导）`yaml_writer.py:self-instruct` 输出开头必须提示 `file` 字段不含 `.md` 后缀，设为节点名而非源文件名。（③渲染后审计）Phase A 完成后 grep 全书 `*.md.md` 文件报告。详见 [md-double-extension-fix.md](references/md-double-extension-fix.md)。 |
| | **`split_book_to_chapters.py` 正则 `.+?` 不匹配无标题章节** → `# 第2章`（只有章节号无标题文本）未被 `CHAPTER_PATTERN` 捕获，内容章节丢失。（2026-06-09 处理 `21K行` 新书时发现） | CHAPTER_PATTERN 的 `.+?`（至少1字符）改为 `.*?`（0字符也可）：`r"^(?:#{1,2})?\s*(第\s*\d+\s*章\s*.*?)(?:\s*)$"`。同时新增 `CHAPTER_BARE_PATTERN` 匹配无 `#` 前缀的章节（`第6章 电缆...`）。|

| | **`split_book_to_chapters.py` TOC 块过滤过严 → 章节编号不连续** | 保留所有章节，仅跳过 <15行的TOC片段。TOC条目是章节存在形式。详见 [toc-detection-design.md](references/toc-detection-design.md)。 |
| | **`split_book_to_chapters.py` 不报告各章内容质量 → 源文件缺失正文的章节静默生成瘦文件** | `split_book()` 中按文件大小分级输出 `✅有正文(>20KB)／⚠️少量(2-20KB)／❌仅标题(<2KB)`，让用户明确知道哪些章节有实质内容、哪些仅为标题大纲。对于 `❌` 级别的章节，根因通常是源文件本身缺失正文（OCR/MinerU提取遗漏），不是拆分工具的问题。 |
| | **源文件部分章节缺失正文（MinerU/OCR提取遗漏）** → 拆分后部分章节只有标题大纲(<2KB)，无段落文字。根因不是拆分工具而是源文件本身。 | 检查源文件目录是否有 `_content_list_v2.json`（MinerU/常规提取器的按页内容清单）。用 `split_book_to_chapters.py reconstruct -w BOOK --v2-path RAW/xxx_content_list_v2.json` 按页眉章节边界重建正文。reconstruct 命令提取每页的 `page_header`（如"第3章"）确定章节归属，然后提取 `title(标题)+paragraph(正文)` 内容重组章节文件。实测7章从0-4KB恢复至11-84KB。无 page_header 的 PDF 提取文件不适用此方法。 |

## 领域自适应设计原则

| 原则 | 说明 |
|------|------|
| **所有静态字符串列表不分领域硬编码** | 不仅 `_LANG_SIGNALS`，`_TEMPLATE_SECTION_KEYWORDS`、`_FIELD_KEYWORDS`、`_FIELD_TO_KEYWORDS` 等所有模块级关键字映射也不含领域专有词（如 dB/电平/限值/PCB/FDTD）。此类词只通过 `_extract_domain_signals()` 在运行时从源文自动提取。新增任何 `_*KEYWORDS` 或 `_*LABELS` 常量后必须 grep 验证零领域词。 |
| **领域词从源文自动提取** | `_extract_domain_signals()` 通过 `\d+[unit]` 模式提取单位、节标题提取领域术语、高频词统计提取技术词 —— 换书零配置 |
| **不需要 embedding** | 规则足够细 + 运行时自适应 = 语义级匹配。embedding 增加几百 MB 依赖和 10 倍+延迟，非必需 |
| **`@prompt` 是原料不是指令** | Agent 把模板 `<!-- @prompt ... -->` 当作写作指导原料，结合当前章节源文自行形成一次性自指导提示词。人工改 @prompt 文字即可控制输出质量 |
| **领域词检查面覆盖全部文本载体** | 不仅是代码中的常量列表，以下位置也必须审计领域专有词：① docstring 示例命令行 (`--book-id 01_工程电磁兼容`) ② 模板 @prompt 示例 (`"电磁兼容/子领域"`) ③ 源文匹配引擎注释 (`如 dB, MHz, GHz`)。替换为 `01_书籍ID`、`大领域/子领域`、`如 Hz, V/m` 等通用占位。 |

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
|| [wikilink-fix-patterns.md](references/wikilink-fix-patterns.md) | wikilink 孤立节点和非对称链接批量修复指南 |
|| [mermaid-graph-troubleshooting.md](references/mermaid-graph-troubleshooting.md) | Mermaid核心概念图语法问题调试指南（括号引用/单行图/YAML块标量） |
|| [template-prompt-convention.md](references/template-prompt-convention.md) | @prompt 写作指导约定：格式/原则/Agent 使用方式 |
|| [template-yaml-field-map.md](references/template-yaml-field-map.md) | 模板-YAML 字段映射表（8种类型的 bd 字段详细说明） |
|| [golden-kp-example.md](references/golden-kp-example.md) | KP YAML 金标范例 |
|| [golden-sp-example.md](references/golden-sp-example.md) | SP YAML 金标范例 |
|| [golden-scene-example.md](references/golden-scene-example.md) | Scene YAML 金标范例 |
|| [toc-detection-design.md](references/toc-detection-design.md) | 整书拆分时 TOC 块自动检测逻辑（三层过滤：目录块边界+章节过滤+行数阈值） |
|| [quality-review-metrics.md](references/quality-review-metrics.md) | 质量审查评分体系：T1/T2/T3检查项、评分公式、CLI用法 |
|| [review-fix-workflow.md](references/review-fix-workflow.md) | Agent驱动修复流程：审查→结构化JSON→文件级修复指令→委托→重渲染→重审查 |
|| [inline-quality-workflow.md](references/inline-quality-workflow.md) | 内联质量检查工作流（inline-before-batch）：生成时就地检查，写一个过一件，不留给事后 |
|| [domain-book-wiki-pitfalls-migration.md](references/domain-book-wiki-pitfalls-migration.md) | 从旧技能迁移时发现的陷阱和修复记录（bare except/循环bug/文件红线/吸纳功能） |
|| [book-split-workflow.md](references/book-split-workflow.md) | 整书按章节拆分工作流：TOC检测、内容优先、章节名补全、逐行扫描、页码清理 |
|| [batch-chapter-workflow.md](references/batch-chapter-workflow.md) | 批量章节处理工作流：delegate_task写YAML → pipeline_v2.py run 逐章全自动 |
|| [delegate-yaml-writing.md](references/delegate-yaml-writing.md) | delegate_task 写YAML标准工作流：build-prompt注入→validate→pipeline run |
