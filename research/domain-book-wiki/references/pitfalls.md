# 关键陷阱完整清单

> 简称"陷阱文档"。与 `SKILL.md` §关键陷阱速查 互为补充。
> 已修复的历史陷阱已归档至 [pitfalls-archive.md](./pitfalls-archive.md)。

## 活跃陷阱（当前版本仍需注意）

### A1. 概念质量闸门：definition_sentence 须精确匹配源文连续文本

**症状**：`pipeline done concepts` 报 `[has_source_retrieval]` 和 `[has_marker_word]`，阶段 `blocked`。

**根因**：
1. `definition_sentence` 前 120 字必须是 `20_正文/` 中**连续原文**，不能跨段落拼接
2. 前 120 字必须含定义标记词：`是指`/`称为`/`即`/`是`
3. **引号字符必须完全匹配原文**：源文用中文弯引号 `"`（U+201C）`"`（U+201D）时，YAML 中也必须用相同字符

**修复**：从正文中精确复制文本（含引号），不跨段，确保含定义标记词。

**验证**：重建并重跑 `pipeline done concepts`

### A2. 手动 build_kb_files.py 后 pipeline 状态不同步

**症状**：手动跑 `build_kb_files.py --type concept --chapter 1` 成功生成文件，但 `pipeline auto --from concepts` 再次运行 build 时报 `构建未产生输出，标记为 blocked`

**根因**：`pipeline auto` 每次运行都调用 build_kb_files.py。当文件已存在时，build 脚本报告 0 个新增文件，pipeline 判定 "构建未产生输出"。

**修复**：手动构建后用 `pipeline done <phase>` 同步状态：
```bash
python3 dag_controller.py pipeline done concepts -w $BOOK_DIR --book-id 01_xxx -c 1
```

**预防**：整书构建应优先使用 `pipeline auto`，避免混合手动+自动模式。

### A3. YAML 字段名不匹配模板（Agent 常见错误）

**症状**：Agent 写 YAML 后 build 出的 .md 有大量 `{{xxx}}` 占位符残留。

**高频错误**：
- SP: `skill_description`→`skill_objectives`, `operation_steps`→`core_operation`
- Scene: `scene_type`→`scenario_type`, `background`→`technical_environment`
- KP: `prerequisites`→`prerequisite_knowledge`

**预防**：`python3 scripts/yaml_gen.py extract <type>` 获取正确字段骨架（v41.1 新增）\n**对照表**：`references/yaml-field-mapping.md`（v41.1 精校：删 18 无效字段 + 补 113 缺失 + 新增 eval 节）

### A4. Mermaid 渲染兼容性问题

**Obsidian `flowchart` 关键字不支持**：优先使用 `graph TD` 而非 `flowchart TD`。
**节点标签 `→` 冲突**：Mermaid 节点标签 `[...]` 内用 `>` 替代 `→`。
**`\s` 正则吞换行**：Mermaid 处理中用 `[ \t]` 替代 `\s`。

## A5. preflight.py YAML 检查不递归子目录

**症状**：`preflight.py` 报 "No YAML files found" 但 YAML 文件在 `.dag/第N章/data/` 子目录中。

**根因**：`os.listdir(DATA_DIR)` 只列顶层，不进入子目录。

**修复**：改用 `os.walk(DATA_DIR)` 递归搜索。（v41.0 已修复）

## A6. verify-source 溯源验证全部 FAIL

**症状**：`pipeline done concepts` 报全部概念不可检索。

**根因**：
1. `verify_concepts_from_source.py` 用 `source_from`（节号引用如"第2章 2.1.1"）做匹配，而非 `definition`
2. `dag_pipeline_done.py` 只搜索 `r.stdout` 提取 verify 结果，但 log 输出在 `r.stderr`

**修复**：
- 始终用 `definition` 做匹配（`definition if definition else source_from`）
- 搜索 `r.stdout + r.stderr` 的合并输出（v41.0 已修复）

## A7. L2/L3 索引路径翻倍（nested 布局）

**症状**：L3 索引生成报路径错误，路径中出现重复的 book dir。

**根因**：`generate_index_data.py` 用 `args.wiki_root`（传入 book dir）又重新计算 BOOK_DIR，导致路径重复。

**修复**：使用 `get_wiki_root(os.path.abspath(args.wiki_root))` 获取真正的 wiki root。（v41.0 已修复）

## A8. index_assembler.py dict/str 拼接 TypeError

**症状**：L3 领域总控生成时报 `TypeError: can only concatenate str (not "dict") to str`。

**根因**：`build_domain_overview` 中 `graph_section` 可能返回 dict 而非 str。

**修复**：添加 `isinstance(graph_sec, dict)` 检查，用 `json.dumps` 序列化。（v41.0 已修复）

## A9. YAML 含冒号的定义须引号包裹

**症状**：`schema.py` 报 YAML 解析错误，冒号被误认为 mapping 分隔符。

**根因**：`definition_sentence: 电磁场边界条件为:` 中冒号后无空格但仍触发 YAML mapping 解析。

**修复**：用引号包裹：`definition_sentence: '电磁场边界条件为:'`

## A10. DEFINITION_MARKERS 缺少"条件为"

**症状**：`has_marker_word` 检查 FAIL，定义"XX边界条件为:"不含任何标记词。

**根因**：`template_assembler_core.py` 的 `DEFINITION_MARKERS` 列表不含 `条件为`。

**修复**：添加 `条件为` 到 `DEFINITION_MARKERS`。（v41.0 已修复）

## A11. pipeline done 参数顺序

**症状**：`pipeline done -w $DIR concepts` 报 `unrecognized arguments: concepts`。

**根因**：`concepts` 是 positional arg，`-w` 是 optional arg，argparse 要求 positional 在前。

**修复**：`pipeline done concepts -w $DIR --book-id 01_xxx -c 1`

## A12. yaml-field-mapping 双源不同步（v41.1 修复）

**症状**：Agent 按 yaml-field-mapping.md 写 YAML 字段，但 build 后大量 `{{xxx}}` 残留。映射表中列出的字段实际不在模板中。

**根因**：yaml-field-mapping.md 在模板归并后未同步更新，存在 18 个无效字段（模板中已移除但映射表保留）+ 113 个缺失字段（新模板字段未录入）。

**修复**（v41.1）：重写 yaml-field-mapping.md — 删 18 无效 + 补 113 缺失 + 新增 eval 完整节。你现在可以信任它。

## A14. assets/ 路径错误（SKILL.md + 参考文档）⚠️ 高频

**症状**：Phase 1 复制后 `assets/` 出现在 workspace 根目录而非 `20_正文/assets/`。preflight 检查路径为 `workspace/assets` 而非正确的 `workspace/20_正文/assets`。

**根因**：
1. SKILL.md Phase 1 代码曾写为 `cp ... "$BOOK_DIR/assets/"`（v42.1 已修复为 `20_正文/assets/`）
2. `preflight.py` `check_source_files_ready` 中 `assets_dir = os.path.join(workspace, "assets")`（v42.1 已修复为 `source_dir/assets`）

**预防**：`assets/` 永远是 `20_正文/` 的子目录，不在 workspace 根。

## A15. flat 布局下误创建容器目录

**症状**：flat 布局的 workspace 中出现了 `01_领域/`, `01_资料库/`, `00_领域总控/`, `00_知识库总控/` 四个空目录。

**根因**：flat 模式不需要这些嵌套布局的容器目录。Agent 可能按 naming-convention.md 的全量目录列表盲目创建。

**修复**（v42.1）：`preflight.py` `check_workspace_paths` 已增加布局感知 — flat 模式下跳过这四个容器目录的检查。

**预防**：flat 布局下 L3/L4 索引在 `kb_root` 级别生成（workspace 的父目录），不在 workspace 内。

## v46.1 新增陷阱 (2026-06-04)

### B1. 概念名在正文中只是提到而非讲授

**症状**：Agent 看到正文中出现一个术语，围绕它生成了 5KB+ 内容，但正文只提了它几句（<30行）。

**根因**：未严格执行三标准中的"篇幅>=50行"；Agent 有补全空白内容的倾向。

**修复**：严格三标准过滤——只将容器 span_lines>=50 的容器升级为核心概念；<30行的术语一律降级 KE。反面示例："频率管理"正文中可能只提了几句，虽然 Agent 可以生成 5KB，但源文并未长篇教授。

### B2. mathematical_model 用纯文本不用 LaTeX

**症状**：`dB=10lg(P1/P0)`、`∇×E=-jωμH` 出现在数学模型中——全部是纯文本，Obsidian 中不可渲染。

**修复**：模板 v6.1 加 HTML 注释 `<!-- 所有公式必须用 $$...$$ -->`。概念名含"方程/模型/计算/定理"且源文有公式 → mathematical_model 不得填"无"。格式：`$$\mathrm{dB}=10\lg\frac{P_1}{P_0}$$`。

### B3. delegate_task 子代理生成错误的 YAML 格式

**症状**：子代理使用嵌套 dict 格式 `{concepts: [{concept_id: ...}]}` 而非管道期望的 flat list `[{name: ..., file: ..., fm: ..., bd: ...}]`。

**修复**：发 delegate_task 时，context 中必须包含：
1. 一个完整 YAML item 样本（从正确章节复制）
2. 说明：输出必须是顶层 YAML 数组（`- name:` 开头）
3. 目标路径 `.dag/第N章/data/concepts.yaml`

不要让子代理"发明"YAML 结构——提供精确模板。

### B4. 重建前未清理 .dag 状态和旧输出

**症状**：YAML 数据更新后运行 pipeline batch，状态文件显示"已完成" → 跳过重建，概念文件内容不变。

**修复**：YAML 变更后重建前：
```bash
rm -f .dag/BOOK_ID_ch*.json .dag/BOOK_ID_ch*.json.lock .dag/BOOK_ID_ch*.json.wal
rm -f 30_核心概念/*.md
```
然后用 `ls -lt 30_核心概念/` 验证时间戳。

### B5. 大章（>1500行）子代理频繁超时

**症状**：单个 delegate_task 处理 >1500 行源文（如第4章 1606 行 53 容器），子代理在 600s 内超时，YAML 未生成。

**修复**：>1500 行章节拆分：
1. 先用审计子代理确定概念列表
2. 再按容器范围并行生成 YAML（拆成 2-3 个子代理）

## A16. 章节文件名被截断（高频）⚠️

**症状**：`20_正文/` 中文件名为 `第1章.md` 而非 `第1章 电磁兼容概述.md`。pipeline 无法识别该文件。

**根因**：Agent 错误地将 file2md 输出的完整文件名截断为简名。SKILL.md 用 `第N章.md` 作占位符导致误读。

**代码防御**：`pipeline_auto.py:43` 和 `dag_pipeline_done.py:116` 显式过滤掉 `第N章.md` 短名，只接受含完整标题的文件。

**修复**（v42.2）：SKILL.md 明确警告"保留完整文件名，禁止截断"。

## A17. 硬编码 /tmp/ 路径不跨平台

**症状**：文档和示例中大量 `/tmp/...` 路径，Windows 上 `/tmp` 不存在。

**修复**（v42.2）：全部替换为 `TMP="${TMPDIR:-/tmp}"` 变量模式。macOS/Linux 原生命名，Windows Git Bash 兼容。

## A18. except Exception 静默吞噬异常

**症状**：构建/检查/分析失败时无任何错误输出，故障完全不可见。33 处裸 `except Exception` 中 31 处不记录日志。

**影响模块**：`kb_graph_builder.py`(4), `graph_analytics.py`(6), `content_check_rules.py`(5), `build_kb_files.py`(3) 等。

**修复**（v42.2）：全部改为 `except Exception as e: log.warning/debug(...)` 记录异常。

**预防**：新代码禁止裸 `except Exception:`，至少加 `log.warning(f"xxx失败: {e}")`。

## A19. 🔥 L2/L3/L4 索引 status=done 但内容为空（v43.11 新增）

**症状**：`l2_indices` 状态为 `done`（files=5），但 `10_总揽/book_overview_*.md` 中知识链连通率全为 0%、节点统计空、Mermaid 图空白、简介显示「（待补充）」。

**根因**：`generate_index_data.py` 只检查索引文件是否写出（通过 files 计数），不验证内容质量。三重闸门（build→content-check→validate_phase_output）覆盖概念→解答全链路，但**不覆盖 L2/L3/L4 索引层**。若某些章节数据未生成（如 exercises blocked、全章 pending），索引汇总时只有部分章数据，最终呈现空壳。

**诊断**：
```bash
# 读 L2 book_overview 检查内容
cat 10_总揽/book_overview_*.md
# 检查知识链连通率是否全为 0
grep "0%" 10_总揽/book_overview_*.md
```

**修复**：补齐所有缺失章的 YAML 数据 → 重跑 `pipeline auto` 或手动 `generate_index_data.py`。

**预防**：生成 L2/L3/L4 后应抽查 book_overview 连通率，确认数字非全零再标记 done。

## A13. 内容质量检查仅覆盖格式，不覆盖深度（v41.1 新增 depth-check）

**症状**：build 和 content-check 全部 PASS，但生成的 .md 文件中 `应用场景` 只有一句话、"无"字段过多、wikilink 指向不存在的文件。

**修复**：`comprehensive_content_check.py --depth-check <wiki_root>` 新增：
- `check_field_word_counts` — 逐字段字数阈值检查（解答 2.1 ≥ 400字、概念 structure ≥ 100字 等）
- `check_wu_field_count` — "无"字段数上限检查（概念 ≤5、KP ≤8、解答 ≤2）
- `check_wikilink_validity` — wikilink 真实存在性验证
- `check_cross_concept_pollution` — 图/公式跨概念重复检测

---

## v52.4 新增 (2026-06-08)

### B6. Confidence 值必须精确匹配 CONFIDENCE_LEVELS

**症状**：`phase_validator.py` 输出 `confidence=0.90 不符合 concept_template.md 的允许值 {0.95}`，阶段 blocked。

**根因**：`tac_constants.CONFIDENCE_LEVELS` 对每种节点类型定义了严格允许值：
- concept: `{0.95}` — 使用 0.90 或 0.85 都阻断
- sp: `{0.75}` — 使用 0.80 阻断
- entity/ke: `{0.85}`
- scene/exercise: `{0.65}`

**修复**：YAML 的 `fm.confidence` 使用精确允许值。

**预防**：用 `pipeline preflight` 一次性发现所有置信度问题。

### B7. 缺失字段阻断 build，多余字段不阻断

**症状**：build 后 .md 文件存在但含 `{{xxx}}` 占位符。

**根因**：模板 `{{xxx}}` 对应的字段在 YAML `bd:` 中不存在 → `assemble_md` 不替换 → `{{xxx}}` 原样留在输出中。

**区分规则**：
- **缺失字段**（模板有但 YAML 无）→ **阻断级** → 必须补
- **多余字段**（YAML 有但模板无）→ **非阻断级** → 模板不消耗这些字段

**修复**：`schema_loader.py extract concept --yaml` → 用正确骨架替换整个 `bd:` 区块。

### B8. 自动填充字段无需也不应在 bd 中出现

**症状**：`name`、`source_chapter`、`source_from` 被报告为 bd 中"多余"字段。

**根因**：这些字段出现在模板正文中，但由 `build_kb_files.py` 自动从 YAML 的 `fm:` 中读取填充。不需要在 `bd:` 中写。

**完整列表**：
```
name, source_chapter, source_from, type_tag, type, confidence,
confidence_note, chapter_num, bloom_level, entity_type, aliases, tags,
book_id, book_name, exercise_link, exercise_name, bloom_progression_analysis
```

**预防**：用 `schema_loader.py extract concept` 输出的字段列表只包含 `bd:` 字段。

## 历史归档索引


# v43.6 新增 (2026-06-01)

### P5. 🔥 rollback 删光所有章节文件

**症状**：构建第 N 章后 `pipeline rollback concepts` 重置状态，前 N-1 章的所有 .md 文件全部消失。

**根因**：`pipeline_extras.py:89-91` 的 `pipeline_rollback` 函数在回滚时 `os.listdir` 阶段目录 → `os.remove` 所有 .md 文件，完全不区分章节归属。构建多章时，任何一章的 rollback 都会删光全部输出。

**修复**（v43.6）：删除文件清除代码块。rollback 仅重置 pipeline 状态为 `pending`，不触碰输出文件。增量构建下不同章节文件名天然不同（如 `电磁兼容三要素.md` vs `多导体传输线理论.md`），无需 rollback 删文件。`build_kb_files.py` 在重建同一章节时会覆盖同名文件。

**受影响**：所有 `pipeline rollback` 操作。修复后 rollback 安全用于多章增量构建。

---

## v44.2-maint 新增 (2026-06-03)

### P10. dag_quality.py L2/L3/L4 索引检查仍期望 5 分离文件
**症状**：`pipeline validate` 报 missing concept_index, knowledge_index, scenario_index, skill_index，但 v43.15 已融合为单文件。
**修复**（v44.2-maint）：`dag_quality.py` l2/l3/l4_indices_exist 的 `expected` 改为只检查单文件 (book_overview/domain_overview/kb_overview)。

### P11. L3 all_books_l2_done 在嵌套布局下多计数
**症状**：L3 报 "7/5 本书 L2 完成"，domain 目录下 8 个章状态文件各计数为独立"书"。
**修复**（v44.2-maint）：(a) 嵌套布局下 library_dir = parent(wr) (b) 按书目录计数而非 JSON 文件数 (c) 过滤隐藏目录/非书目录 (d) v43.12 下只需 ANY 章 l2=done/accepted。

### P12. L3 indices_exist ctrl_dir 在嵌套布局路径缺失
**症状**：`wiki_root/FIELD/DOMAIN_CTRL` 在 FIELD="" 时丢失领域目录名。
**修复**（v44.2-maint）：嵌套布局下 ctrl_dir = parent(wr)/DOMAIN_CTRL。

### P13. quality_graph_checks.py KeyError 'total_nodes'
**症状**：L4 健康检查报 `'total_nodes'` KeyError。
**修复**（v44.2-maint）：`degree_centrality()` 返回 `total` 不是 `total_nodes`，键名修正。

### P14. L4 all_domains_l3_done 阈值 ≥3 与 v43.15 不兼容
**症状**：v43.15 融合后 domain_overview 仅 1 个 .md 文件，旧阈值 ≥3 永远不满足 → 所有领域标记为 pending。
**修复**（v44.2-maint）：阈值改为 ≥1。


## v52.4 新增 (2026-06-08)

### B6. Confidence 值必须精确匹配 CONFIDENCE_LEVELS

**症状**：`phase_validator.py` 输出 `confidence=0.90 不符合 concept_template.md 的允许值 {0.95}`，阶段 blocked。

**根因**：`tac_constants.CONFIDENCE_LEVELS` 对每种节点类型定义了严格允许值：
- concept: `{0.95}` — 使用 0.90 或 0.85 都阻断
- sp: `{0.75}` — 使用 0.80 阻断
- entity/ke: `{0.85}`
- scene/exercise: `{0.65}`

**修复**：YAML 的 `fm.confidence` 使用精确允许值。

**预防**：用 `pipeline preflight` 一次性发现所有置信度问题。

### B7. 缺失字段阻断 build，多余字段不阻断

**症状**：build 后 .md 文件存在但含 `{{xxx}}` 占位符。

**根因**：模板 `{{xxx}}` 对应的字段在 YAML `bd:` 中不存在 → `assemble_md` 不替换 → `{{xxx}}` 原样留在输出中。

**区分规则**：
- **缺失字段**（模板有但 YAML 无）→ **阻断级** → 必须补
- **多余字段**（YAML 有但模板无）→ **非阻断级** → 模板不消耗这些字段

**修复**：`schema_loader.py extract concept --yaml` → 用正确骨架替换整个 `bd:` 区块。

### B8. 自动填充字段无需也不应在 bd 中出现

**症状**：`name`、`source_chapter`、`source_from` 被报告为 bd 中"多余"字段。

**根因**：这些字段出现在模板正文中，但由 `build_kb_files.py` 自动从 YAML 的 `fm:` 中读取填充。不需要在 `bd:` 中写。

**完整列表**：
```
name, source_chapter, source_from, type_tag, type, confidence,
confidence_note, chapter_num, bloom_level, entity_type, aliases, tags,
book_id, book_name, exercise_link, exercise_name, bloom_progression_analysis
```

**预防**：用 `schema_loader.py extract concept` 输出的字段列表只包含 `bd:` 字段。

### B9. [已知] Solutions 回退骨架生成（eval_template 格式不匹配）

**症状**: `pipeline auto` solutions 阶段输出 `⚠️ build_kb_files.py 返回非零（可能 solutions.yaml 缺失）` → 回退到骨架解答。生成的 .md 含 `{{type_tag}}`, `{{bloom_level}}` 占位符残留。

**根因**: `build_kb_files.py --type solution` 预期的 bd 字段结构与 `eval_template.md` 的 `{{xxx}}` 不完全对齐。Template 引擎找不到匹配字段 → 返回非零 → pipeline 回退到从 exercises 文件生成骨架。

**影响范围**: 所有章节解答文件（ch1~ch7 106个）均含2个占位符。

**临时修复**: 占位符不影响阅读（位于 frontmatter 中）。完整修复需统一 `build_kb_files.py` 中 solution 字段映射为 `eval_template.md` 的精确 {{xxx}} 集合。

### B11. [v52.5] YAML 完整性闸门 — 6个L1文件必须全部存在

**症状**: `pipeline auto` 拒绝执行，输出 `❌ YAML 数据文件不完整` 并列出缺失文件。

**根因**: 只写了部分YAML（如仅 concepts.yaml）就运行 pipeline auto → 缺文件的阶段被blocked → 输出残缺（只有概念+自动检测的习题）。

**检查范围**: 6个L1文件 — `concepts.yaml`, `kes.yaml`, `entities.yaml`, `kps.yaml`, `sps.yaml`, `scenes.yaml`。`exercises.yaml` 和 `solutions.yaml` 明确排除在外（自动检测/骨架回退不需要YAML）。

**修复**: 补全缺失的YAML文件后重跑 pipeline auto。

**预防**: pipeline init 阶段即检查 L1 完整性（Phase 0.25 告警，非阻断）。

### B12. [v52.5] YAML item 的 `file:` 字段必须唯一

**症状**: 多个 items 使用相同 `file:` 值 → build 将它们全部合并到同一个 .md 文件。

**根因**: `build_kb_files.py` 按 `file:` 分组，同名的 items 输出到同一文件。

**修复**: 每个 item 应有唯一 `file:`，格式为 `短名称-第N章`。

**预防**: 写 YAML 时检查所有 `file:` 值是否唯一。

### B13. [v52.5] YAML `file:` 值禁止含 `/` 字符

**症状**: `file: 多设备DC/DC隔离供电场景-第4章` → OS将 `/` 解释为路径分隔符 → 文件写入错误路径。

**根因**: `file` 值直接用作文件名。`/` 在所有 OS 中均为路径分隔符。

**修复**: 替换 `/` 为 `_` 或 `-`：`多设备DC_DC隔离供电场景-第4章`。

**预防**: `file:` 值仅含字母、数字、中文、`-`、`_`、`.`，禁止 `/`、`\`、`:`、`*`、`?`。

## 历史归档索引（重复删除 — 上一个完全相同）

---

**文档版本**: v42.3
**最后更新**: 2026-05-31
**维护者**: Hermes Agent (domain-book-wiki)

## v42.3 新增 (2026-05-31)

### P1. 章节文件名截断
Agent 复制 file2md 输出时手动将 `第1章 电磁兼容概述.md` 重命名为 `第1章.md`。pipeline_auto 显式过滤短名文件。
**修复**: `cp /tmp/output/第N章*.md "$BOOK_DIR/20_正文/"` — 通配符保留原名。

### P2. assets 路径错误
assets 复制到 `$BOOK_DIR/assets/` 而非 `$BOOK_DIR/20_正文/assets/`，MD 中相对路径 `assets/xxx.png` 无法解析。
**修复**: `cp -n /tmp/output/assets/* "$BOOK_DIR/20_正文/assets/"`。

### P3. flat 布局误建容器目录

## v50.1 新增 (2026-06-05)

### 42. delegate_task 子代理源文密集型 chapter 超时

**症状**: 子代理处理含 800+ 行源文的章节时超时（15 API call / 600s 耗尽），
任务未完成即退出。第 2-8 章全部超时，第 1 章（2 KP）成功。

**根因**: 子代理在 context 外自行 read_file 读取整个源文件，每读一个文件消耗一次 API call，
建立上下文的开销超出时间预算。

**预防**:
1. 单次 delegate_task ≤ 3 KP
2. 将源文关键段落直接注入 context，而非让子代理 read_file
3. 子代理 context 中提前提供关联概念/KE 的文件名列表，减少 search_files 调用

### 43. 批量 Python 脚本写 YAML 覆盖数据

**症状**: kps.yaml 原有 3 条记录，批量填充后只剩 1 条。第 4 章丢失 2 个 KP。

**根因**: yaml.load + 遍历 item + yaml.dump 串行流程中，某些 YAML 条目结构异常
导致遍历跳过条目，最终 dump 时只写出最后一个遍历到的条目。

**预防**:
1. 写 YAML 前后必须计数校验: print(f"{len(before)}→{len(after)}")
2. 发现 len(after) < len(before) 立即中断并从备份恢复
3. 写前 shutil.copy2(src, src + ".bak")
4. 恢复方案: 从已构建的 .md 文件 frontmatter 反向生成 YAML 条目
Agent 在 flat 工作区创建 `01_领域/`, `01_资料库/`, `00_知识库总控/`。preflight 现已布局感知（v42.3 修复），flat 模式自动跳过这些目录。

### P4. except Exception 静默吞噬（已修复）
build_kb_files.py, content_check_rules.py, kb_graph_builder.py, graph_analytics.py 中 16 处裸 `except Exception:` 改为 `except Exception as e: log.warning(...)`。

---

## v44.2 新增 (2026-06-03)

### P6. schema.py definition→term_definition 单向移动别名
**症状**：Agent 写 `definition` 到 KE YAML，schema 将其重命名为 `term_definition`（`bd.pop(alias)`），但下游代码（template_assembler/dag_pipeline_done/verify_concepts）仍读取 `definition` → 找不到字段 → 空值。
**修复**（v44.2）：改为**双向复制**：同时保留 `definition` 和 `term_definition` 两个字段，无论 Agent 写哪个。
**预防**：Agent 现在只需写 `definition`（或 `term_definition`）一个字段即可，代码会自动补齐另一个。无需再写双字段。

### P7. verify-source 跨章假阳性阻断
**症状**：`pipeline done concepts` 扫描所有章的 .md 文件检查定义句可检索性，当前章 100% 通过仍因其他章的历史问题被 blocked。
**修复**（v44.2）：在 `dag_pipeline_done.py` 中按 `source_chapter` 过滤，只验证当前章的概念/KE。同时 KE 阶段也做了相同过滤。
**验证**：重新执行 `pipeline done concepts -w $BOOK_DIR --book-id XX -c N`。

### P8. L2/L3/L4 索引空壳无检测
**症状**：`l2_indices` 状态为 `done` 但 book_overview 中知识链连通率全 0%、简介「（待补充）」、Mermaid 空图。
**修复**（v44.2）：新增 `l2_content_not_empty` 检查（dag_quality.py + dag_constants.py LEVEL_QUALITY_CHECKS L2 层）：读取 book_overview 文件，检测连通率 0%、「待补充」、文件过小（<200 字符）等空壳信号，标记 warning。
**验证**：运行 `pipeline validate -w $BOOK_DIR --book-id XX -c N` 确认 L2 检查 `l2_content_not_empty` 结果为 pass。

### P9. yaml_gen.py extract 输出扁平字段（Agent 长期痛点）
**症状**：Agent 用 `yaml_gen.py extract concept` 得到扁平字段列表（`field: ""`），但 build 期望 `{name, file, fm, bd}` 容器结构，Agent 需手动补容器的过程反复出错。
**修复**（v44.2）：`cmd_extract` 重写，直接输出含 `name/file/fm/bd` 的完整容器结构，含正确 confidence 值（按类型自动匹配）、字段对齐注释。sync with `yaml-structure-guide.md`。
**预防**：直接使用 `yaml_gen.py extract <type>` 输出作为 YAML 骨架。写 YAML 前仍然建议参考已有章的 `.dag/第N章/data/*.yaml` 确认格式。


## v49.0 数据路径统一 (2026-06-04)

### P24. 数据写入路径错误：`data/第N章/` vs `.dag/第N章/data/`
**症状**：pipeline 报告"数据文件不存在"但 YAML 文件已写。  
**根因**：v49.0 将数据存储统一为 `.dag/第N章/data/`，`_load_items()` 不再读取 `data/`。Agent 按旧习惯写入 `data/第N章/` 后 build 找不到数据。  
**修复**：`mv data/第N章/*.yaml .dag/第N章/data/ && rm -rf data/`  
**永久预防**：preflight.py 已新增 `check_data_dir_convention` 检测，发现 `data/` 下存在 YAML 即 FAIL 阻断 pipeline。

### P27. 回退链变更：`.dag/第N章/data/` → 技能 `scripts/data/`
**症状**：技能目录 `scripts/data/` 中的 YAML 被用作 fallback 但数据已过期。  
**根因**：v49.0 回退链从 `data/ → .dag/ → scripts/data/` 简化为 `.dag/ → scripts/data/`。  
**修复**：确保 `.dag/第N章/data/` 中包含正确的 YAML，技能 `scripts/data/` 仅用作模板参考。  
**预防**：`preflight.py` 的 `check_data_dir_convention` 会自动检测。

### P28. 禁止手拼 YAML 数据路径 — 必须用 `WorkspacePaths.data_dir()`
**症状**：修改 data 目录约定后多个文件各自手拼 `os.path.join(wr, ".dag", ...)`，漏改一处就出 bug。  
**根因**：v49.0 前 YAML 数据路径在 3 个文件中各自手拼，无集中入口。  
**修复**：`dag_state.py` 新增 `WorkspacePaths.data_dir(chapter)`，所有调用方统一使用。  
**预防**：新增代码中如果见到 `os.path.join(..., ".dag", ..., "data")` 且与 YAML 数据相关，必须改用 `WorkspacePaths(wr).data_dir(ch)`。preflight `check_data_dir_convention` 会在 pipeline init 时检测 `data/` 违规。

---

## v50.0 新增 (2026-06-05)

### P29. yaml_pre_validate.py 字段 schema 与实际 YAML 脱节 ⚠️ 高频假阳性 (v50.0 已修复)

**症状**：`yaml_pre_validate` 报 255+ 错误、`quality_score` 显示 400+ 错误，但实际 YAML 内容质量合格。
**根因**：`yaml_pre_validate` 和 `build_kb_files._REQUIRED_BD_FIELDS` 各自维护一套字段名，不同步。
**修复** (v50.0)：`dag_constants.py` 新增集中化 `REQUIRED_BD_FIELDS`，3 文件消费同一来源。`_TYPE_TO_BD_KEY` 映射 yaml_pre_validate 类型名→dag_constants key。255→57 真实错误。

### P30. delegate_task 子代理生成内容但未写文件

**症状**：子代理返回 summary 含完整文本但目标文件未修改。6 子代理中 1 个(17%)只返文本不写。
**修复**：子代理 context 末尾加 `完成后必须用 patch 工具将内容写入目标文件。`。父代理收到后 `grep -l` 验证。

### P31. 子代理方案详解格式不一致

**症状**：部分使用 `##### 一、`（h5）而非 `一、`（纯文本）。2/6(33%)格式不同。
**修复**：context 中指明 `分项标题使用纯文本"一、xxx"，不使用 markdown 标题标记（#）。`

### P32. WorkspacePaths 传入 domain 目录导致路径偏移 (v50.0)

**症状**：知识库出现嵌套重复 `domain/domain/book/10_总揽/`。
**根因**：`WorkspacePaths.__init__` 未验证 `wr` 是否为合法 book 目录。
**修复** (v50.0)：新增 `_is_valid_book` 校验（检查 `20_正文/`）。传入 domain 目录时自动回退修正。

### P33. 习题/解答 file 命名不统一 (v50.0)

**症状**：`第7章习题1-描述.md` vs 标准 `第N章-习题N.md`。
**修复** (v50.0)：① `build_kb_files.py` 构建时自动标准化 ② `yaml_pre_validate.check_file_naming()` 发出 warning ③ `chapter-data-generation.md` 第10条约束。

### P34. build staging 逐章构建时 `os.rename` 覆写整个目录 (v50.0) 🔥

**症状**：依次为多章构建 exercise/solution 时，第N章的 `.build_tmp/90_习题/` 通过 `os.rename` **替换**整个 `90_习题/`，导致前N-1章的习题文件全部丢失。只有最后一章的习题存活。
**根因**：v49.0 的 staging 机制用 `os.rename(out_dir, real_dir)` 以整个临时目录替换目标目录。逐章构建时每章只含自己的文件，rename 会删光其他章已有内容。
**修复** (v50.0)：改为逐文件移动 + 清理临时目录，不复写整个目标目录：
```python
os.makedirs(real_dir, exist_ok=True)
for fname in os.listdir(out_dir):
    src = os.path.join(out_dir, fname)
    dst = os.path.join(real_dir, fname)
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(src, dst)
shutil.rmtree(out_dir)
```
**预防**：所有 staging commit 必须用逐文件移动模式，禁止目录级 `os.rename`。

### P35. quality_score wikilink 计数遗漏 L2/L3/L4 索引文件

**症状**：每章 398 wikilink 断链，其中 164 条指向 `book_overview_*.md`。
**根因**：`all_files` 只扫 6 个节点目录，漏 `10_总揽/` 和 `90_习题/`。
**修复** (v50.0)：扩展 `all_scan_dirs` + `os.walk()` 递归子目录。398→234 断链。

### P36. chapter-data-generation.md 目录前缀全部偏移 10 (v50.0)

**症状**：Agent 按文档写 wikilink `[[30_知识要素/xxx]]` → 实际目录是 `40_知识要素/`，所有链接不可跳转。
**根因**：KE/KP/SP/Scene/实体 五个目录前缀比实际少 10。仅 `30_核心概念/` 正确。
**修复** (v50.0)：全部修正 + 新增习题/解答前缀 + 强调禁止裸 wikilink。

### P37. 解答 `related_concepts` wikilink 不带目录前缀 (v50.0)

**症状**：解答中 `[[近场与远场]]` 裸 wikilink 在 `解答/` 子目录中无法跳转到 `40_知识要素/`。
**修复** (v50.0)：YAML 数据中 wikilink 强制 `[[前缀/文件名|显示名]]` 格式。Agent 必须查实际文件名+目录前缀后写入。
