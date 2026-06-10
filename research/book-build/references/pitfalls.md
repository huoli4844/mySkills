# Pitfalls 完整陷阱列表

| # | 陷阱 | 预防 |
|:-:|:-----|:-----|
| 1 | **添加大纲不存在的章节** | 大纲之外一律不写 |
| 2 | **遗漏大纲存在的章节** | 写作后逐项对照大纲检查 |
| 3 | **直接复制KB模板结构** | KB是原料，教材是成品，必须二次加工 |
| 4 | **公式与$$同行** | `\tag{5-1}$$` 导致渲染失败 → tag必须独占一行，$$另起一行 |
| 5 | **直接覆写原文件** | 改技能或章节文件前先 `cp` 备份到 `.bak` 或 `.backups/`，确认无误再替换正式文件 |
| 6 | **公式用Unicode非LaTeX** | md 用 `$$`，docx 用 OMML XML |
| 7 | **使用显性教学步骤标记** | 用第三人称学术叙事替代 |
| 8 | **第二人称"你"用于正文叙事** | 正文用第三人称（"读者""人们"） |
| 9 | **刻意拆短段落** | 真实教材使用100-300字信息密集型长段落 |
| 10 | **每个案例末尾用显性「EMC启示：」标记** | 案例的分析和启示应自然融入叙事 |
| 11 | **等长段落** | 核心段10+行，辅助段3-5行，结论单句段 |
| 12 | **过渡词单一** | 交替使用设问/类比/递进/转折/因果 |
| 13 | **每节同一结构** | 先判断内容类型（6种模式之一）再选结构 |
| 14 | **习题只有概念题** | 每章必须包含概念/简答/计算/分析各一 |
| 15 | **docx公式不可编辑** | 用 `python-docx + latex_to_omml` 而非 pandoc。验证：`assert '<m:oMath' in open('f.docx','rb').read()`. 详见 `references/md-to-docx-guide.md` |
| 16 | **KB零结果时留空** | 即使零素材也要基于通用知识写出来 |
| 17 | **verify_chapter 的 summary 计数** | 脚本用 `^\d+\.` 匹配总结条目 |
| 18 | **大纲是.docx格式未先提取** | 用 `file2md` 或 `parse_outline.py` 预处理 |
| 19 | **Obsidian Mermaid 图太小** | 加 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` |
| 20 | **本章总结只有文字没有图** | 必须图文并茂——Mermaid图+要点表格 |
| 21 | **忽视各教材共同盲区分析** | 系统分析各书没写透的内容是独创价值所在 |
| 22 | **某本书主题不匹配却硬套** | 只借鉴写作手法，内容从其他来源补充 |
| 23 | **文字型决策树未转Mermaid图** | 所有决策树/时间线/因果链须转为Mermaid图 |
| 24 | **图号冲突** | 添加Mermaid图后用 `grep -n '图N-'` 验证 |
| 25 | **临时文件未清理** | 章组装完成后 `rm -f` 清理 section-*.md |
| 26 | **本章总结标题数字与实际条数不一致** | `grep -n '核心要点'` 检查标题数字 |
| 27 | **公式章号前缀写错（跨章素材污染）** | 从第N+1章素材复制公式时，`\tag{8-X}`易遗漏不改。写完后必须扫描`\tag{`批量核对章号前缀 |
| 28 | **在已有示例之间插入新例导致后续编号偏移** | 插入新例后必须五步闭环：重排例题编号→更新文本引用→更新总览Mermaid→更新要点列表→更新习题引用 |
| 29 | **章末总览Mermaid图引用滞后** | 任何编号重排后必须检查总览Mermaid图中的每一处引用的例号/公式号是否与实际一致 |
| 30 | **Mermaid图中emoji破坏Obsidian渲染** | `✅❌⚠️🔽➡️`等emoji出现在Mermaid节点标签中会导致整图不渲染。用纯文本替代（"达标/不达标/注意/下降"），不得使用任何Unicode emoji |
| 31 | **单行`$$...$$`混淆状态机审计脚本** | 单行`$$\\boxed{...}$$`导致行状态机`$$`计数漏掉该块。审计必须用`re.finditer(r'\\$\\$', text)`按位置而非按行计数 |
| 32 | **xychart-beta 非法关键字导致全图空白** | `bar-group-group` 不存在于任何Mermaid版本，`xychart-beta` 仅支持 `title/x-axis/y-axis/bar/line` 五个关键字。写入非法关键字后整图渲染失败，无错误提示 | 使用 `post_generation_check.py --fix` 自动检测并移除非法关键字 |

## 硬件相关 Pitfalls

| # | 陷阱 | 说明 | 正确做法 |
|:-:|:-----|:-----|:---------|
| 44 | **Mermaid mindmap 崩溃** | >100节点或含emoji导致Obsidian渲染崩溃 | ≤30节点，不用emoji |
| 45 | **``{init}` JSON 语法** | 单引号或缺失闭合 `%%` 导致Error | 双引号JSON+闭合`%%` |
| 46 | **YAML 多行 Mermaid** | `\n`转义在yaml.safe_load中不识别 | 用 `|` block scalar |
| 35 | **公式 \\left/\\right 不匹配** | `\\left(` 无 `\\right)` → 渲染失败 | 每个 `\\left` 必须配对 `\\right` |
| 36 | **`\\rightarrow` 含 `\\right` 子串导致误报** | 检查器用 `count('\\\\right')` 在 `\\rightarrow` 中匹配到 `\\right` → 误报 \"\\left(0)与\\right(1)不匹配\" | 检查器必须用正则 `r'\\\\right(?![a-zA-Z])'` 而非 `count()` |
| 37 | **`%%{init}` 被误识别为图表类型** | Mermaid第一行为 `%%{init:...}%%` 时检查器报\"未知图表类型\" | 检查器必须跳过 `%%{init}` 行再判定类型 |
| 38 | **`clean_formula_numbers.py` 跳过 inline $$** | 该脚本只处理 `$$...$$` 块（开闭在不同行），不处理单行 `$$inline$$` 和裸公式 | 运行前先用 `re.sub(r'\\$\\$(.+?)\\$\\$', r'\\n$$\\n\\1\\n$$\\n', text)` 转 inline 为 block 格式 |
| 39 | **子代理写公式缺 `$$` 包裹** | `delegate_task` 子代理常把公式写成纯文本或无 `$$` 的 `\\tag{}` | context 必须显式约束"每个独立行公式用 $$...$$ 包裹，\\tag{} 在 $$ 内部"；写完后 `--fix` + `renumber.py` 两步修复 |
| 40 | **参考教材数量写死** | 文档/表格/测试中假设恰好3本（书A/书B/书C），但 config 可配置任意数量 | 所有遍历用 `c.source_books` 动态迭代；表格行数 = `len(c.source_books)`；避免"书A/书B/书C"或"三书"字眼 |
| 41 | **测试断言具体配置值** | 测试中断言 `"查老师教材" in output` 或 `get_book_by_author("路宏敏")`，结果 config 换领域后测试炸了 | 测试只断言结构（`isinstance`/`endswith`/`is not None`），不断言 config.yaml 中定义的具体文本/路径/数字 |
| 42 | **忽略项目目录初始化** | 客户给了项目路径，Agent 直接去读 `book-build.yaml`，但该文件还不存在 | 收到项目路径后先检查 `{path}/book-build.yaml` 是否存在。不存在则自动调用 `Config.setup(path)` 创建目录结构和模板 |
| 43 | **Phase 重编号的链路风暴** | 修改 Phase 编号后漏更新工作流概览块、各节标题、Design 中 fast mode 引用、闸门表、闸门Mermaid图、项目目录注释等 | Phase 重编号后必须全局搜索 `Phase` 逐处核对 |
| 44 | **公式链无推导文字（AI写作特征）** | 连续3+个显示公式间无推导叙述（"由…得"、"代入…"），第4-14章实战共发现86处 | `fix_common_issues.py` 检测报告，`delegate_task` + LLM 逐处插入推导文字 |
| 45 | **Mermaid图后无图注** | 每个```mermaid块后必须有 `*图N-X：描述*` 图注 | `check_mermaid_has_caption()` 检测，`fix_common_issues.py` 自动补全 |
| 46 | **processed_dir 与 raw_dir 混淆** | 用户无独立处理后目录时，将两者指向同一路径 | 省略 `processed_dir`，book_config.py 会处理 `None` |
| 47 | **柯金良章节目录与实际内容标题格式不同** | TOC 用双井号带页码，实际内容用单井号 | 用 `grep -n "^# 第"` 而非 `"^## 第"` 定位真实内容 |
| 48 | **blockquote 中 --fix 产生孤立 tag** | `> $$` 块运行 `--fix` 时可能在 `$$` 外部插入 `\tag{}` | `grep -n '^> *\\\\tag{'` 找到后手动删除，再运行 `renumber.py` |
| 49 | **`\\tag{0-X}` 错误章号前缀** | 自动修复提取章号失败时生成 `\\tag{0-X}` | `grep -n 'tag{0-'` 找到后替换为正确章号，运行 `renumber.py` |
| 50 | **MD→DOCX 时 \\tag/\\text/\\xrightarrow 等 LaTeX 命令不转换** | pandoc 和 `latex_to_omml` 都不识别教材用的 `\\xrightarrow{文字}`、`\\tag{N-M}`、`\\displaystyle` 等命令 | `md_to_docx.py` 的 `clean_latex()` 自动预处理：移除 `\\tag` 行、`\\xrightarrow{a}`→`a \\to`、移除 `\\left`/`\\right`。如果手动转换，必须执行相同的清理步骤 |
| 51 | **`latex_to_omml.py` 跨技能依赖不同步** | `book-build/scripts/latex_to_omml.py` 复制自 `docx-format` 技能，docx-format 更新后 book-build 的副本会过时 | 定期从 `docx-format` 技能同步，或运行 `diff -q` 检查差异 |
