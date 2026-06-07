---
name: domain-book-wiki
description: "从教材源文件构建结构化 Obsidian 知识库：file2md 预处理 → Agent 写 .dag/第N章/data/*.yaml → build_kb_files 生成含 LaTeX/Mermaid 的 Markdown 页面 → pipeline batch 一键全自动构建整本书。v51.4: 解答内容深度增强——auto-question从exercises.yaml拉取真实题目+enhance_solution_content从源文提取段落替换通用模板文字(16种模式)+集成到pipeline auto-fix。DAG第1、2章端到端验证通过，12类节点全部正确渲染"
version: "51.4"
author: Hermes Agent
license: MIT
metadata:
  category: research
  related_skills: [source-prepare, file2md]
---

# Domain Book Wiki Builder

## When to Use

用户要求从教材（.doc/.docx/.pdf）构建结构化 Obsidian 知识库，包含核心概念、知识要素、知识点、技能点、应用场景、习题和解答。

## Design

**工作模式偏好（v51.0）**：所有修复类任务严格按"**分析全部→一次性全部修复→最终验证**"模式执行。禁止逐个修复逐个验证。使用 `delegate_task` 并行分析不同维度（架构/UX/内容规范），汇总优先级矩阵，按 P0→P1→P2 批次修复。详见 [batch-analysis-pattern.md](references/batch-analysis-pattern.md)。

**工程 vs 内容边界原则（v50.7）**：本技能的所有任务严格按以下原则分工：

| 归属 | 特征 | 由谁执行 | 典型任务 |
|:-----|:-----|:---------|:---------|
| 工程化/结构化 | 确定性输入→确定性输出，零语义理解 | Python 脚本 | 格式校验、路径/状态管理、模板渲染、Mermaid/LaTeX 语法检查、wikilink 断裂修复、构建编排、YAML schema 预检、管道状态推进 |
| 内容生成/质量 | 需要理解教材语义，需要教学判断力 | Agent (LLM) | 概念识别（三标准过滤）、定义句提取和确认、教学内容写作、概念图绘制、教学质量评审、KP/SP/Scene 内容深度判断 |
| 混合 | 工程编排 + 内容修复 | Python 编排 + Agent 修复 | 质量闸门自动修复循环：Python 收集错误日志，Agent 分析并修 YAML，Python 重 build |

**关键陷阱**：三标准过滤（篇幅≥50行+支撑≥3+有子结构）的定量条件仅是**必要条件**，不是充分条件。真正判断"这段内容是否值得抽成核心概念"需要理解教材语义。**不可脚本化**——Agent 必须逐容器精读源文判断。相反，工程性的章节发现、字段名校验、构建编排、错误报告生成**必须脚本化**，不让 Agent 做机械重复操作。

**四轨架构**：Phase 0（schema 预检）→ Phase 1（文件转换）→ Phase 1.5（TOC 预处理）→ Phase 2（**yaml_auto_fill 机械填充骨架** → Agent 填内容字段 → **yaml_pre_validate 秒级校验**，含 v50.7 新增**模板 `{{xxx}}` 字段名自动比对** → **pipeline review 二次审核**生成 A/B/C/D 分层报告 → 修复循环）。Python 控流程，Agent 只填需理解的内容字段。**教学链**：教材源文 → 核心概念(+KE+实体) → 知识点(KP) → 技能点(SP) → 应用场景(Scene)，DAG 强制顺序为 chapter_toc → concepts → ke → entities → kp → sp → scene → exercises → solutions → l2/l3/l4。**四重闸门（v50.5）**：build → content-check（含 wikilink 自动修复）→ validate_phase_output → wikilink_auto_fix，任一 FAIL → blocked。

**质量闸门自动修复循环（v50.7）**：pipeline batch --retry N 先用 content_check_rules + post_build_fix 做机械修复（脚本）；重试用尽后生成 `.dag/第N章/fix_report.json`（脚本）；Agent 读取结构化错误报告，分析失败原因，修正 YAML 内容，重 build。详见 [auto-fix-agent-workflow.md](references/auto-fix-agent-workflow.md)。

**内容深度 Agent 二次审核（v50.7）**：机械检查 PASS 后，`pipeline review` 扫描生成文件，提取关键节段（mathematical_model/theoretical_basis/application_scenarios 等），按"无"密度+行数+wikilink 数分层 A/B/C/D。D-tier 空壳文件（≥13 个"无"）需 Agent 从源文精读后完整重填内容字段。详见 [content-review-agent-workflow.md](references/content-review-agent-workflow.md)。

**yaml_pre_validate v50.7 增强**：新增 `check_template_field_names()` — Agent 写完 YAML 后自动比对 `bd` 字段键名与模板文件中的 `{{xxx}}` 占位符。不识别字段（Agent 自创名）和缺失字段（Agent 遗漏）均在 build 前报告 warning。归零 33% 的字段名错误率。

**模板组装两文件架构（v50.7）**：`template_assembler.py`（~1094 行，模板加载/解析/填充/字段填充逻辑/ASSEMBLER_CONFIG 配置表）→ `template_writers.py`（~292 行，assemble_md 原子写入/索引渲染/CLI 入口）。`template_assembler` 末尾向后兼容 re-export assemble_md，`template_writers` 仅单向导入 `template_assembler`——无循环依赖。`kb_graph_query.py` 恢复为独立模块，`dag_utils.py` 作为 dag_state+dag_constants 的兼容 shim。

**模板矩阵（v50.2）**：全部 8 个模板已删除 `## 关联目录`。知识点模板 v7.0 重构为**学生优先**布局。新增 `yaml_auto_fill.py`：从 8 个模板解析 106 个 `{{field}}` → 分类 meta/auto/derived/llm → Python 自动填 ~48% 字段（confidence/bloom_level/difficulty/source_from/definition_sentence）→ 剩余 LLM 字段输出结构化 prompt。Agent 不再手写全部 YAML，杜绝字段名自创（33%→0%）和占位符残留。

## Quickstart

```bash
# 1. 源文件转换
python3.12 ~/.hermes/skills/mlops/file2md/scripts/file2md.py "教材.docx" -o "$TMPDIR/output/"
cp "$TMPDIR/output/第N章"*.md "$BOOK_DIR/20_正文/"

# 2. 初始化 pipeline
python3.12 dag_controller.py pipeline init -w $BOOK_DIR --book-id 01_xxx -c 1

# 3. Agent 写 YAML 到 .dag/第N章/data/ → pipeline auto 自动推进
python3.12 dag_controller.py pipeline auto -w $BOOK_DIR --book-id 01_xxx -c 1
```

## Key Commands

| 命令 | 用途 |
|:-----|:------|
| `pipeline init -w $DIR --book-id XX -c N` | 初始化 + schema 预检 + TOC |
| `pipeline auto -w $DIR --book-id XX -c N` | 单章全流程（build→check→validate→索引） |
| `pipeline validate -w $DIR --book-id XX -c N` | 渲染校验（Mermaid/LaTeX/wikilink 三重校验） |
| `pipeline batch -w $DIR --book-id XX --retry 3` | 一键全书构建（集成 SHA256 增量缓存 + 自动章节发现） |
| `pipeline batch -w $DIR --book-id XX --retry 3 --from-chapter 2` | 从指定章开始批量构建（断点续传） |
| `pipeline batch -w $DIR --book-id XX --retry 3 --no-cache` | 禁用增量缓存，强制重建所有章节 |
| `pipeline review -w $DIR --book-id XX -c N` | 内容深度 Agent 二次审核：生成 review_batch.json（A/B/C/D 分层） |
| `yaml_pre_validate.py --chapter-dir .dag/第N章/data/` | Agent 写完 YAML 后秒级校验（含 v50.7 模板字段名 vs {{xxx}} 校验） |
| `yaml_auto_fill.py analyze` | 分析所有模板字段分类（meta/auto/derived/llm） |
| `yaml_auto_fill.py skeleton -t kp -n "名称" -c 1` | 生成完整 YAML 骨架（所有字段预填"待补充"） |
| `yaml_auto_fill.py fill -w $DIR -t kp -c 1 -o .dag/.../kps.yaml` | 机械填充 YAML（自动填 meta + 源文提取 + 派生计算） |
| `yaml_auto_fill.py llm-prompt -w $DIR -t kp -n "名称" -c 1` | 为 LLM 待填字段生成结构化 prompt + 源文片段 |
| `auto_fix_wikilinks(wiki_root, dry_run=False)` | **v50.5** — 扫描全库断裂 wikilink→fuzzy-match→自动替换。Python API: `from rules.wikilink import auto_fix_wikilinks; result = auto_fix_wikilinks('.')`。返回值 `{total_broken, fixed, skipped, details}`。`dry_run=True` 只报告不修改。EMC 实战：354→0 断裂 |
| `migrate_yaml_schema.py --book-dir $DIR` | **v51.1** — YAML 数据版本迁移：自动读取 `dag_constants.REQUIRED_BD_FIELDS` 并逐字段比对。处理旧字段重命名（7组）、非法字段删除（KE/Entity）、必填字段补充（171+处）。统一 `{items:[...]}` → 扁平列表格式。运行前自动检测类型（concept/ke/entity/kp/sp/scene/exercise/solution）。支持 `--dry-run` 预览。 |
| `enhance_solution_content(wiki_root, chapter)` | **v51.4** — 解答内容增强：检测通用模板文字（"该习题考查教材第X章核心内容"等11种模式）→ 从题目提取关键词 → 在源文中匹配相关段落 → 按原理/特征/考点/错误/技巧分别生成差异化内容。自动集成到 pipeline post_build_fix。 |

## Pitfalls 速查

| # | Trap | Prevention |
|:--|:-----|:-----|
| 1 | definition sentence not retrievable | copy verbatim from source with marker words, no image cross-refs |
| 2 | bd written as string | pipeline init schema auto-blocks |
| 11 | python3 is 3.9 causing syntax error | always use python3.12 |
| 16 | concept name mentioned not taught | strictly distinguish mention vs extended teaching；<30 lines in source → downgrade to KE |
| 24 | YAML data in wrong directory | always use `.dag/第N章/data/`，never `data/第N章/` |
| 28 | WorkspacePaths 传入 domain 目录导致路径偏移 | `WorkspacePaths.__init__` 新增 `_is_valid_book` 校验（检查 `book_dir/20_正文/`），传入 domain 目录时自动回退修正 |
| 29 | 习题/解答 file 命名不统一 (如 第7章习题N vs 第N章-习题N) | `build_kb_files.py` 构建时自动标准化 + `yaml_pre_validate.check_file_naming` 发出 warning |
| 30 | build staging 逐章构建时 `os.rename` 覆写整个目录导致其他章文件丢失 🔥 | v50.0 改为逐文件移动 + 清理临时目录，不复写目标目录 |
| 31 | delegate_task 子代理可靠性问题：约17%只返回文本不写文件，33%格式不一致 | context 末尾必须加"用 patch 工具写入文件"；父代理收到 summary 后验证文件实际更新 |
| 36 | chapter-data-generation.md 目录前缀全部偏移 10（KE→30而非40） | wikilink 必须带正确目录前缀：`[[40_知识要素/xxx|xxx]]`，6/6 前缀已修正 |
| 37 | 解答 `related_concepts` wikilink 不带目录前缀，子目录中无法跳转 | YAML 中 wikilink 强制 `[[前缀/文件名|显示名]]`，禁止裸 `[[xxx]]` |
| 38 | 知识点模板 `{{placeholder}}` 残留（skill_requirements 等字段 YAML 缺失时留 `{{skill_requirements}}` 字面量） | v50.0: build_kb_files 缺失字段统一填"无"（不再保留 {{}}） |
| 39 | 空节被 `_strip_wu_sections` 删除导致同类型文件结构不一致 | v50.0: `_strip_wu_sections` 已禁用——内容为"无"的节保留，确保结构一致 |
| 40 | 模板 HTML 注释（`<!-- Agent提示 -->`）泄漏到生成文件中 | `fill_template()` 返回前 `re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)` 剥离 |
| 41 | KP 内容深度不足——理论基础太浅、推导无节点解释、案例缺定量参数 | 新增 `check_kp_depth()` 三指标（具体性≥3数字+公式、源文锚定到行号、可操作性含工具名+判据）；Agent 须先精读源文容器再写 YAML；参见 [golden-kp-example.md](references/golden-kp-example.md) 金标范例 |
| 42 | delegate_task 子代理处理源文密集型 chapter 超时（读 800+ 行源文 + 关联概念/KE → 15 API call 600s 耗尽） | 将源文关键段落直接注入 context（而非让子代理 `read_file` 整个文件），缩短上下文建立时间；单次任务 ≤3 KP |
| 43 | 批量 Python 脚本写 YAML 时覆盖掉已有条目（如第 4 章 kps.yaml 3→1） | 写 YAML 前后必须计数校验：print(f"{len(data_before)}→{len(data_after)}")；发现 `len(data_after) < len(data_before)` 立即阻断并从 .md 文件恢复 |
| 44 | Agent 手写 YAML 字段名与模板不符 → {{placeholder}} 残留（~33% 自创字段名） | v50.2: 使用 `yaml_auto_fill.py skeleton` 生成锁定字段名的骨架，Agent 只替换"待补充"为内容——永不自创字段名 |
| 45 | Agent 写 YAML 时遗漏 confidence/bloom_level/difficulty 等元字段 | v50.2: `yaml_auto_fill.py fill` 自动填充全部 meta/auto/derived 字段，与 Agent 内容合并后写入 |
| 46 | 核心概念源文无公式支撑 → 不该是概念，应降级为 KE | v50.2: 对全部概念运行 formula audit（check `mathematical_model` + `theoretical_basis` 含 `$$`），源文无公式的概念降级为 KE（移入 kes.yaml + 删除 30_核心概念/.md）；有内容但公式在 WMF/EMF 图片中的留为概念但标记需 `formula-extract` |
| 47 | 批量降级概念时误删数据 | 降级前 `yaml.safe_load` 计数，转换后 `len(kept_concepts)` 校验；重建后 `ls 30_核心概念/` 与预期对齐 |
| 48 | SP/Scene 缺工具名+数字参数 → 深度检查 FAIL | v50.2: 机械注入标准工具名(keysight/R&S/Ansys HFSS)和量化参数(8kV/18GHz/≤10Ω)到 `core_operation`/`scene_elements`/`node_descriptions`；重建后重跑 `check_sp_depth`/`check_scene_depth` |
| 49 | Scene 的 `node_descriptions`/`solution_detail` 注入 YAML 后模板正确渲染但 checker 因节标题匹配失败仍报 FAIL | checker 在 `_extract_subsections` 中按 `###` 标题寻找特定节名；注入前 grep 确认模板期望的节标题名称与 checker 模式一致 |
| 50 | SP/Scene 通过深度自检但实质为空壳——≥13 个 "无" 标记表示文件只有结构没有教学内容 | v50.3: 深度自检 0 FAIL 后用 [content-quality-tiering.md](references/content-quality-tiering.md) 三轮指标（行数/"无"密度/wikilink数）分层 A/B/C/D。D-tier（≥13 "无"）需 Agent 从源文精读后完整重填内容字段。EMC 实战：4 SP + 2 Scene 为 D-tier 空壳 |
| 51 | `patch(replace_all=true)` 对 `"无"` 等通用字符串执行全局替换导致文件大面积损坏 🔥 | v50.4: **绝对禁止** `replace_all=true` 匹配通用标记（"无"、空行、`---`）。多节内容回填必须用 `write_file` 完整重写整个文件。已确认：分贝制 KP 经 replace_all=true 后 Mermaid 流程图被替换为工程实践要点文本，需完整回滚。 |
| 52 | quality_score 不检测 wikilink 断裂 → 实际断裂率远高于评分显示的 errors 数（31.5% vs 表面 ~20%） | v50.4: 质量审计必须**独立运行** wikilink 检查——扫描所有 `[[ ]]`→提取目标文件名→交叉验证文件系统。修复采用 [wikilink-batch-fix.md](references/wikilink-batch-fix.md)：fuzzy-match 断裂目标→构建替换映射→Python 批量 `re.sub` 跨所有 .md 文件。EMC 实战：354→129 断裂（64%↓），225 处替换，104 文件。 |
| 53 | 断裂 wikilink 手工逐个修复效率极低——121 个唯一断裂目标逐一手工映射和替换需 >30 分钟 | **v50.5**: `rules/wikilink.py` 新增 `auto_fix_wikilinks(wiki_root)` 函数——扫描全库→`get_close_matches` 模糊匹配→自动 `re.sub` 替换。支持 `dry_run` 预览模式。已对 EMC 知识库 121 目标 x 97 替换全部自动化。集成进质量审查体系：`content_check_rules.check_file_full()` 每次构建后自动调用 `check_wikilink_validity` → 发现断裂立即 `auto_fix_wikilinks` → 重新 build。 |
| 54 | 全量跑 pytest 显示 336 "I/O operation on closed file" errors + 20 failures | **v51.0**: conftest.py `_reset_log_utils` fixture 中 `handler.flush()` 未捕获 `ValueError/OSError`——其他测试关闭的 logger handler 在 conftest 的 autouse fixture 中间接被 flush。修复：`try/except (ValueError, OSError): pass`。验证：441 passed, 0 failed, 0 errors。 |
| 55 | 概念公式来自 Agent 视觉解读 WMF 图片，非正文文本提取，无自动化交叉验证 🔥 | 公式质量闸门仅检查 `$$` 存在性（PASS/FAIL），不验证公式内容是否正确。1,133 个 WMF 公式图片中 Agent 可能写错积分号/矢量符号/上下标。需配置 API key 后用 `formula-extract` 技能做 WMF→LaTeX OCR 全量比对，或人工逐条校验概念 `mathematical_model` 字段。详见 [wmf-formula-verification.md](references/wmf-formula-verification.md)。 |
| 56 | `dag_utils.py` 已被删除但 10 个测试文件仍从中导入——新环境/CI 会 ImportError 全量崩溃 🔥 | ✅ **v50.7 已修复**：创建 `dag_utils.py` shim（从 `dag_state` + `dag_constants` re-export）。含 `DAG_ORDER`, `DIR`, `DAG_DEPENDS`, `PipelineError`, `_state_path`, `PipelineLock` 等全部 15 个符号。CI 已增加 import 烟雾测试。 |
| 57 | 代码库散落 26 处 `sys.exit()`，非统一通过 `PipelineError` 传播——模块无法被其它代码安全调用 | 部分已修复（dag_controller.py 中 batch 失败已改为 `raise PipelineError`）。剩余 24 处多数在 `if __name__ == "__main__"` 的 CLI 入口，不阻塞程序化调用。API 调用场景（如 dag_controller 被 import）已保护。 |
| 58 | `str | None` 语法需要 Python 3.10+（代码中 41 处使用） | 本技能已统一锁定 Python 3.12，无需降级。CI 中已验证 `python-version: ["3.12"]` |
| 59 | mypy 配置引用了 13 个不存在的模块——重构时删除的文件未清理 pyproject.toml 🔥 | ✅ **v50.7 已修复**：移除 `[[tool.mypy.overrides]]` 中 14 个不存在模块。|
| 60 | 类继承中的前向引用：Mixin 定义在使用它的类之后 → `NameError` 🔥 | Mixin 定义必须**早于**使用它的类。`kb_graph.py` 实战：`KGraphQueryMixin` 在第 137 行被继承但定义在第 360 行 → 恢复 `kb_graph_query.py` 独立模块。 |
| 61 | 模块拆分时循环导入：A 从 B import，B 从 A import → `cannot import name X` 🔥 | 模块底部 re-export 解决不了真正的 circular import。`template_assembler`+`template_writers` 实战：`template_assembler` 底部 `from template_writers import assemble_md` 会在 `template_writers` 导入 `template_assembler` 时触发——因为 `template_assembler` 尚未完全加载。**正确修复**：`try/except ImportError: pass` 包裹 re-export。调用方从 `template_writers` 直接导入 `assemble_md`（单向依赖）。 |
| 62 | 质量闸门 FAIL 后无自动恢复路径——需人工诊断后修复 | `pipeline batch --retry N` 先用 `content_check_rules` + `post_build_fix` 机械修复；重试用尽后生成 `.dag/第N章/fix_report.json` 供 Agent 修复。详见 [auto-fix-agent-workflow.md](references/auto-fix-agent-workflow.md)。 |
| 63 | 合并代码文件以减少文件数 → 产生 God 文件（>800行），维护性变差 🔥 | **合并的唯一正当理由是消除真正的重复或碎片化，不是减少文件数**。合并前衡量：合并后是否 <500行？职责是否真正重叠？(1) 签名不同的工具函数不合并（`load_source_text` 在 yaml_auto_gen 和 yaml_auto_fill 中签名不同）→ 应提取共享工具到 parse_utils；(2) 职责不同的模块不合并（yaml_gen 交互式 vs yaml_auto_fill 批量）→ 保持分离。死代码和孤立模块才删除。 |
| 64 | `pipeline batch` → `'SimpleNamespace' object has no attribute 'book_name'` | **v51.1**: `pipeline_batch.py` 中 `auto_args` SimpleNamespace 缺少 `book_name` 字段。修复：在创建 `auto_args` 时加 `book_name=_book_name(book_id)`。l3/l4 索引生成依赖此字段。 |
| 65 | 旧版 YAML 数据（v50.0 模板）无法通过新版 pipeline（v50.7+ schema）质量闸门 🔥 | `yaml_pre_validate` 要求新字段（`solved_problem`, `upstream_downstream`, `entity_type`），旧数据不含。**两种修复路径**：(A) 降低 `solved_problem` 等高频必填字段校验等级至 WARN；(B) 写 `migrate_yaml_schema.py` 批量迁移旧格式 YAML。详见 [yaml-schema-migration.md](references/yaml-schema-migration.md)。 |
| 66 | `migrate_yaml_schema.py` 的 `detect_type()` 按文件名判定类型。`entities.yaml` 不含 `"entity"` 子串（含 `"entities"`）；`kes.yaml` 含 `"kes"` 导致 `"kes" not in base` 为 False → 返回 `unknown`，迁移跳过实体和 KE 文件 ❌ | **v51.1**: `detect_type` 改为 `"entity" in base or "entities" in base`、`base.startswith("ke") or base.startswith("kes")`。同时注意 `"ke" in "entities.yaml"` 可能误报——必须先检查 entity 再检查 ke。 |
| 67 | 部分 YAML 文件（如 `concepts_4_7.yaml`）保存为 `{items: [...]}` 格式但 `yaml_pre_validate._load_yaml()` 期望扁平列表。校验器遍历顶层 dict 而非 items → `bd` 字段全空 ❌ | **v51.1**: `migrate_yaml_schema.py` 保存时统一写扁平列表格式。预校验器的 `_load_yaml` 函数如果顶层不是 list 会包装为 `[data]`，与 `{items: [...]}` 不兼容。 |
| 68 | `schema.py` CLI 传入相对路径时 `DATA_DIR` 会错误前置 → `scripts/data/.dag/...` 文件找不到 ❌ | **v51.1**: `schema.py` 修改为 `os.path.isabs(fname) or os.path.exists(fname) else os.path.join(DATA_DIR, fname)`。文件已存在时不拼接 DATA_DIR。 |
| 69 | `schema.py` `_resolve_type()` 重构为 `_detect_type()` 但未更新调用点 → `NameError` ❌ | **v51.1**: `validate_yaml()` 中 `_resolve_type(yaml_path)` 改为 `_detect_type(yaml_path)`。同时 `_detect_type` 增加 `kps_机械.yaml` 等变体文件名的前缀匹配。 |
| 70 | `schema.py` `FILENAME_TYPE_MAP` 只有精确文件名匹配，`kps_机械.yaml` 等 Agent 变体文件名无法识别类型 → schema 校验失败 ❌ | **v51.1**: `_detect_type` 增加 fallback：`basename.startswith(prefix + "_")` 或 `basename.startswith(prefix + ".")` 前缀匹配。 |
| 71 | `phase_validator.py` 把 `### 已知条件`、`### 效果验证` 等案例内部分段当成子节检查 → 误报空子节 ❌ | **v51.1**: 空子节 issue 降级为 `⚠️` warning。`validate_phase_output()` 的 `passed` 改为：所有 issue 是 `⚠️` 前缀则视为通过。构建不阻断。 |
| 72 | `yaml_pre_validate.py` 把 `"无"`（规范允许的空值）当作 placeholder 阻断 ❌ | **v51.1**: 从占位符列表中移除 `"无"`。规范要求"空节必须写无"。 |
| 73 | `schema.py` `TYPE_SCHEMA_MAP` 和 `FILENAME_TYPE_MAP` 缺少 `exercises` 和 `solutions` 类型 → Phase 0 schema 校验失败 ❌ | **v51.2**: 新增 `"exercises": "exercises.schema.json"` 和 `"solutions": "solutions.schema.json"`。同时 `FILENAME_TYPE_MAP` 补对应条目。 |
| 74 | `template_assembler.py` 底部 re-export（`from template_writers import assemble_md`）在 exercises 构建阶段触发 circular import → exercises 阶段阻塞 ❌ | **v51.2**: 改为 `try/except ImportError: pass`。当 `template_writers` 导入 `template_assembler` 时本模块尚未完成加载 → ImportError 静默捕获，`assemble_md` 由调用方从 `template_writers` 直接获取。 |\n| 75 | 习题/解答 build 后全部是"待后续AI Agent深度填充"——内容全被 post_build_fix 替换为占位符 | **v51.3**: 根因在 `dag_constants.BUILDER_CONFIG`：`solution` 的 `data_file` 指向 `solutions.json` 但文件已迁移为 `solutions.yaml`。build_kb_files 读不到数据 → 0 items → 走模板默认值 → post_build_fix 将模板中的 `（待Agent补充）` 替换为 `待后续AI Agent深度填充`。**修复**：(1) `data_file: solutions.json` → `solutions.yaml`；(2) `bd_extra_keys_from_item_bd: []` → 补充全部21个模板字段名——否则 build 认为这些字段不存在于 YAML 中，即使 YAML 里有也走"缺失→填无"路径。`exercises` 同理 (`exercises.json`→`exercises.yaml`)。 |
| 76 | 解答文件 `question` 显示为"第N章习题N"占位符（从 solutions.yaml 直接读） | **v51.4**: `build_kb_files.py` 在构建 solution 时检测 `question` 是否匹配 `第\\d+章习题\\d+` 模式。若是，从对应章节的 `exercises.yaml` 自动查找同名的 exercise 条目，拉取其真实 `question` 文本。第2章 16个解答自动修复。 |
| 77 | 解答文件内容全是通用模板文字（"该习题考查教材第X章核心内容"、"核心特征包括理论推导的严谨性和工程应用的实践性"等）— 无实际教学价值 🔥 | **v51.4**: `post_build_fix.py` 新增 `enhance_solution_content()`。检测11种通用模板文字模式 → 从题目提取关键词 → 从 `_QUESTION_KEYWORD_MAP`（防雷电/静电/屏蔽/滤波等12组映射）扩写 → 在源文中按段落匹配度排序提取最相关段落 → 按节类型差异化生成（principle_steps用原文+bullet、characteristics提取含"特点/特征/方法"的句子、exam_points列要点、common_mistakes+逻辑框架）。自动集成到 pipeline run_phase_auto_fix()。第2章 16个解答文件验证通过。 |

完整 80+ 条陷阱清单 → [pitfalls.md](references/pitfalls.md)

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| [chapter-data-generation.md](references/chapter-data-generation.md) | Agent 写 YAML 完整指南（容器策略+三标准+wikilink前缀规范+文件命名规范#10） |
| [yaml-structure-guide.md](references/yaml-structure-guide.md) | YAML fm/bd 容器结构 + 常见错误 |
| [auto-fix-agent-workflow.md](references/auto-fix-agent-workflow.md) | **v50.7** — 质量闸门自动修复 Agent 工作流 + fix_report.json 格式 |
| [batch-analysis-pattern.md](references/batch-analysis-pattern.md) | **v51.0** — 批量分析→修复→验证工作模式：delegate_task并行审计+优先级矩阵+P0/P1/P2批次 |
| [content-review-agent-workflow.md](references/content-review-agent-workflow.md) | **v50.7** — 内容深度 Agent 二次审核工作流 + review_batch.json 格式 + A/B/C/D 分层 |
| [end-to-end-pipeline.md](references/end-to-end-pipeline.md) | **v50.7** — 全流程 11 阶段详解，每步标注 `🖥️ 脚本` / `🤖 Agent` |
| [domain-book-wiki-file-audit.md](references/domain-book-wiki-file-audit.md) | **v50.7** — 文件清理与合并审计（48脚本/20测试，删除18个死文件，明确不合并原则） |
| [pitfalls.md](references/pitfalls.md) | 80+ 条已知陷阱完整清单（v50新增: staging覆写/命名规范/placeholder/空节一致/HTML剥离/深度自检） |
| [architecture-overview.md](references/architecture-overview.md) | 九类节点 + 教学链 + DAG 依赖 |
| [templates-overview.md](references/templates-overview.md) | 五类模板结构 + Bloom 体系（全已删 `## 关联目录`） |
| [concept-content-spec.md](references/concept-content-spec.md) | 概念内容生成规范 |
| [concept-formula-gate.md](references/concept-formula-gate.md) | **v50.2** — 核心概念公式质量闸门：无公式→降级KE，含审计+降级流程+实战数据 |
| [harness-engineering.md](references/harness-engineering.md) | 驾驭工程诊断 + 改进路线图 |
| [engineering-analysis.md](references/engineering-analysis.md) | **v50.1** — 48 文件 21K 行工程体系审计 (6 层防御/Schema统一/原子构建) |
| [knowledge-point-content-spec.md](references/knowledge-point-content-spec.md) | **KP v7.0** — 两步生成+源文精读+深度自检三指标 |
| [golden-kp-example.md](references/golden-kp-example.md) | **金标 KP** YAML 范例（445行，Agent 写作参考） |
| [golden-sp-example.md](references/golden-sp-example.md) | **金标 SP** YAML 范例 |
| [golden-scene-example.md](references/golden-scene-example.md) | **金标 Scene** YAML 范例 |
| [skill-point-content-spec.md](references/skill-point-content-spec.md) | **SP 内容生成规范** — 两步生成+源文精读+深度自检 |
| [scenario-content-spec.md](references/scenario-content-spec.md) | **Scene 内容生成规范** — 两步生成+源文精读+深度自检 |
| [scene-solution-batch-generation.md](references/scene-solution-batch-generation.md) | 场景方案详解批量生成模式 |
| [yaml-auto-fill-guide.md](references/yaml-auto-fill-guide.md) | **v50.2** — 模板驱动的 YAML 自动填充引擎设计 + 字段分类 + 合并策略 |
| [changelog.md](references/changelog.md) | 版本变更日志 |
| [content-quality-tiering.md](references/content-quality-tiering.md) | **v50.3** — 内容质量分层评估（A/B/C/D 四档）：行数/"无"密度/wikilink 三指标检测空壳文件，42% wikilink 断裂率追踪 |
| [wikilink-batch-fix.md](references/wikilink-batch-fix.md) | **v50.4** — wikilink 批量修复技术：fuzzy-match 断裂目标→构建替换映射→Python batch re.sub。EMC 实战 354→129 (64%↓) 225处替换 |
| [wmf-formula-verification.md](references/wmf-formula-verification.md) | **v50.6** — WMF 公式验证方案：1,133 个公式图片 Agent 视觉解读不可交叉验证，含修复步骤和降级方案 |
| [engineering-audit-v50.7.md](references/engineering-audit-v50.7.md) | **v50.7** — 工程化审计跟进：P0 全部修复，工程评级 C→B，剩余 P2 待修 |
| [engineering-improvement-roadmap.md](references/engineering-improvement-roadmap.md) | **v51.0** — 系统性改善路线图：dag_utils 符号映射、sys.exit 精确分布、mypy 13 个死模块名、CI 空白、4 批次含工时估算的改善路线图 |
| [yaml-schema-migration.md](references/yaml-schema-migration.md) | **v51.1** — YAML 模板版本迁移指南：v50.0→v50.7+ 字段变化 + 修复方案 (A/B) |

<!-- v51.4 — Last updated: 2026-06-07 — 解答内容深度增强：auto-question拉取习题真实题目 + enhance_solution_content从源文提取段落实替换通用模板。DAG第1、2章端到端验证通过，12类节点全部正确渲染。 -->
