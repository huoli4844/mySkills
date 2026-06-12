---
name: book-build
description: "Use when writing university textbooks. Outline-driven pipeline: domain injection → writing guide generation → delegate_task chapter writing → formula fixing → quality audit."
version: 3.9.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [textbook, outline-driven, academic-writing, domain-agnostic]
    related_skills: [github-repo-management, file2md]
---

# book-build（教材写作管线）

## Overview

**核心原则：** 借鉴手法，不照搬内容。参考教材是学写法的老师，不是抄内容的仓库。

**全自动执行：** 不改"要不要/是否继续"，直接做。做错了改比问效率高。  
**例外：** 重大结构性改动（去领域化/架构重构/技能拆分/管线变更），必须先写书面方案 → 用户确认 → 再执行。此规则优先级高于"全自动执行不询问"。

```
# 阶段0: 领域注入（新项目初始化时运行 — 一站式）
domain_init.py       01 TOC提取 + KG构建 + 领域注入（三阶段合一）

# 阶段1: 写作管线（四合一入口 → 创建 + 生成大纲 + QC + 任务清单）
init_project.py      02 项目创建 + 大纲骨架 + QC验证 + 任务清单
auto_write.py        03 任务JSON → Agent调用delegate
batch_fix_numbers    04 批量修复公式编号
quality_audit.py     05 统一质量审计
```

## 关键约束（不可违反）

### 公式格式
`\tag{N-M}` **独占一行在 `$$` 闭合前**。违反→`batch_fix_formula_numbers.py`

### 写作自查工具不写入正文
`5.1 素材清单` / `5.2 12条军规检查` / `5.3 待改进方向` 是 Agent 自查工具，不是正文。

### Mermaid 铁律
- 仅 `graph TD` / `graph LR`，换行用 `<br>` 不用 `\n`
- 禁止 emoji / `%%{init}%%` / `<-->` / `timeline` / `mindmap`
- subgraph 标题无括号无破折号，内部无 direction
- 详见 `references/mermaid-compatibility-guide.md`

### delegate_task 边界
- ✅ 分析参考教材（只读，~200s 3路并行）
- ✅ 写章节正文（已验证：单章 5 节约 400~500s，80~130 万输入 token；单章全量 delegate 实测 470s，909K 输入 token / 45K 输出 token）
- ❌ 写入大纲（≥35KB 必超时，5次实测）
- ✅ 正确模式：大纲用 `delegate 做分析 → write_file 直写`；正文用 `delegate 直接写作`
- **委托写正文时必须禁止 `\[ \]` LaTeX 语法**（子 Agent 常用 `\[ ... \]` 代替 `$$`，导致 `post_generation_check.py` 误报 tag 在 $$ 外）
- 详见 `references/chapter-writing-delegation.md`

### book-build.yaml 最小化
只放教材名 + 参考书路径。写作规范归 references/，密度底线归写作大纲。

## Design

### 四层配置

| 层 | 内容 | 位置 |
|:---|:-----|:-----|
| **技能层** | 操作流程、约束、铁律（领域无关，含 {{变量}} 占位符） | SKILL.md + references/ |
| **项目配置层** | 教材名、参考书路径 | `book-build.yaml` |
| **领域上下文层** | 领域信号 + 知识点图谱 + 渲染后的 references（初始化时自动生成） | `output/领域上下文/` |
| **章节层** | 每章结构、体量、素材 | `写作大纲/writing-guide-chX.md` |

领域上下文层是 v3.5.0 新增；Phase 0 现已由 `domain_init.py` 一站式完成。

### 脚本 vs Agent 分工
脚本管流程编排和统计检查；Agent 管内容创作和质量判断。

### 架构规则（2026-06-16 确立）

**规则1：重大改动先方案后动手**
结构性改动（去领域化/架构重构/技能拆分/管线变更），必须先写书面方案 → 用户确认 → 再执行。

**规则2：领域无关 + 领域注入**
book-build 是领域无关的工具技能。SKILL.md 和 references/ 中不应写死任何领域词。领域词在项目初始化时自动注入：

```
setup_project.py 初始化流程：
  ① 读取 book-build.yaml（教材名 + 参考书路径）
  ② 遍历 source_books[].path（minerU 处理过的 .md 文件）
  ③ extract_book_toc() → 提取每本书的章节目录结构
  ④ build_knowledge_graph() → 多本书 TOC 合并去重 → 词频统计
  ⑤ 写入 output/领域上下文/domain-context.yaml
  ⑥ 用领域信号渲染 references/ 模板 → output/领域上下文/references/

实际执行通过 domain_init.py 一站式完成：
  python3 scripts/domain_init.py --project /path/to/教材
```

**规则3：知识点图谱防止"写偏"**
多本参考书的组织结构不同。知识点图谱的核心作用：
- 提取每本书章节标题中的核心概念（去编号、去修饰语）
- 跨书统计：某概念出现在 4 本书中的几本
- 高频概念（3+/4 本）→ 写作大纲"必含要素" → 质量审计可检查
- 不依赖单本书的章节顺序，依赖跨书的概念共识

详见 `references/domain-agnostic-architecture.md`。

**规则4：references/ 是模板，非静态文件**
references/ 中的 .md 文件用 {{变量}} 做占位符。项目初始化时用领域信号渲染后，写入项目目录。SKILL 层的 references/ 始终保持领域无关。

**规则6：模板层改进优先 — 质量问题先查模板，不单章修补**
当某章正文质量弱于预期时，**不要直接改那一章**。根因几乎永远是该章的写作大纲（writing-guide）中每节指南不够具体。正确的排查路线：

```
章节质量弱
  └→ 查 writing-guide-chX.md 的每节指南是否足够具体
       ├→ 每节是否有"结构化要素"（概念辨析/数学/可视化/案例/教材交叉）？
       ├→ 开篇方式是否指定了引入手法？
       ├→ 案例建议是否含公司名/时间/技术参数？
       ├→ 设问过渡是否直接写出了过渡语句而不是"[过渡语句]"？
       └→ NO → 改进 templates/chapter-writing-guide-template.md → 重新生成写作大纲 → 重新写章节

       └→ YES → 检查 auto_write.py 的 delegate_task context 是否传入了完整指令
```

**核心原则**：改善永远发生在模板层（`templates/`）或流程层（`auto_write.py` 的 context 构造），从未在单章正文层。一次模板改进影响所有未来章节。

### 规则7：模板设计 — 内联示例 > 文件引用

在模板中提供指导时，**具体句子模板优于 § 文件引用**。例如：

```
❌ 旧：开篇方式（详见教授级教学法目录 §一、开篇三法）
✅ 新：开篇方式（§一 开篇三法 — 选一种展开）：
  - [ ] 日常现象引入法（≥2个生活场景）
    - 例："你是否遇到过手机靠太近音箱会发出吱吱声？"
```

**原理**：Agent 看到 § 引用时需要跳转查找另一文件（增加文件读取 + 上下文切换）。内联示例直接呈现在当前上下文中，Agent 可直接复制修改，产出质量更高。

### 规则8：6选3质量原则 — 强制所有要素导致机械写作

写作大纲模板中的结构化要素（概念辨析/公式/Mermaid/案例/脚手架/交叉引用），**不要强制全部实现**。改为 6 选 3（在 [x] 中勾选），理由：

- 不是每一节都适合放公式（例如纯概念节）
- 不是每一节都需要 Mermaid 图（例如数学推导节）
- 6 选 3 给 Agent 创作自由度，同时保持每节至少 3 个结构化要素的质量底限
- 质量审计应只检查被选中的要素是否完整实现，而非全 6 项

详见 `templates/chapter-writing-guide-template.md`。

## Workflow

### 阶段0: 领域注入（新项目初始化时运行一次）

```bash
# 全线执行（TOC提取 → KG构建 → 领域注入）
python3 scripts/domain_init.py --project /path/to/教材 [--verbose] [--noise-report]

# 分阶段执行
python3 scripts/domain_init.py --project /path/to/教材 --phase toc     # 仅TOC
python3 scripts/domain_init.py --project /path/to/教材 --phase kg      # 仅KG
python3 scripts/domain_init.py --project /path/to/教材 --phase inject  # 仅注入

# 单文件TOC提取
python3 scripts/domain_init.py toc /path/to/参考书.md [--json] [--verbose] [--noise-report]

# KG查询/查看
python3 scripts/domain_init.py query --project /path/to/教材 --term "屏蔽"
python3 scripts/domain_init.py show --project /path/to/教材
```

### 阶段1: 写作管线

```bash
python3 scripts/init_project.py /path/to/教材 --name "教材名" --outline 教材提纲.docx

# ② 自动写作（auto_write.py 输出 JSON → delegate_task）
python3 scripts/auto_write.py --project /path/to/教材

# ⑤b 修复子 Agent 常见的 `\[ \]` LaTeX 语法（如有）
python3 -c "import re; f=open('output/第*.md').read(); f=re.sub(r'\\\\\[(.*?)\\\\\\]', lambda m: '\$\$' + m.group(1) + '\n\$\$', f, flags=re.DOTALL); open('output/第*.md','w').write(f)"

# ⑥ 修复公式编号
python3 scripts/batch_fix_formula_numbers.py /path/教材/output/第*.md

# ⑦ 质量审计
python3 scripts/quality_audit.py --project /path/to/教材 [--chapter N] [--quick]

# 补充章节：差距分析
python3 scripts/outline_vs_chapter_audit.py --project /path/to/教材
```

### ⑧ 版本标记（重大改动后执行）
```bash
git tag -a book-build-v&lt;version&gt; -m "版本说明"
git push origin book-build-v&lt;version&gt;
```
触发条件：新增测试 ≥20 / 代码重构 / 版本号修改。

禁止对小型修复或纯文档变更打 tag。

## Common Pitfalls

1. **行级状态机，不用正则** — `\$\$(.*?)\$\$` 对 `>$$` 无效
2. **先读后写** — 永远 `read()` → `write()`，绝不倒过来
3. **Mermaid 圆边节点** — `[("text")]` 对，`[("text)"]` 错
4. **Mermaid `<br>` 非 `\n`** — 节点换行用 `<br>`
5. **空 `$$...$$` 块** — 编号前先删除
6. **`> $$` 保留前缀** — 不要替换为 `$$`
7. **表格对齐行禁止前置** — 列数必须与表头匹配
8. **单行 `$$...$$` 缺编号** — 转为 `$...$`
9. **分节写作防超时** — delegate_task 单次最多 ~25KB/路，详见 `references/parallel-section-writing.md`
10. **Mermaid 白底黑字 + 横排优先** — 禁止深色主题，`graph LR` 优先
11. **批量写作后"尾巴缺失"** — 连续写多章大纲时，后期章（通常Ch8+）系统性跳过"教授级写作专项"（设问/直觉/教学/呼应）和"参考文献/深入阅读"。写完一批必须逐章扫描6项结构指标（设问引导句/工程直觉提示/教学视角句/前后呼应句/习题/参考文献）→ 只补缺失的，不盲目扩充体量。详见 `references/gap-fill-workflow.md`。
12. **重大改动先方案后动手** — 去领域化/架构重构/技能合并/管线变更必须预先写方案、确认再执行。不要直接改。此规则优先于"全自动不询问"。
13. **参考书格式是 minerU，不是 file2md** — `source_books[].path` 指向的是 minerU 处理过的 .md。特点是：`##` 用于所有层级（章节头、子节、元数据），噪声（CIP/前言/目录）混杂其中，不同书格式不一致。TOC 提取必须做噪声过滤。
14. **多本书 TOC 合并用知识点图谱** — 单本书的章节结构不代表整个领域。必须合并多本书、按概念频次排序。高频概念（出现 3+/4 本）才是必须覆盖的内容。使用 `scripts/domain_init.py --project /path/ --phase kg` 构建。详见 `references/domain-agnostic-architecture.md`。
15. **`git add -A` 污染父目录文件** — 在 `book-build/` 目录下执行 `git add -A` 会 stage `.hermes/skills/` 下其他技能的文件（如 `.archive/`、`.webui-managed-skills.json`）。必须用 `git add research/book-build/` 精确限定范围。提交前 `git diff --cached --stat` 确认只有本技能的文件。
16. **子 Agent 用 `\[ \]` 代替 `$$`** — 委托写章节正文时，子 Agent 经常使用 `\[ ... \tag{1-1} \]` LaTeX 语法而不是 `$$ ... \n\tag{1-1}\n$$` Markdown 语法。这导致 `post_generation_check.py` 报 "tag 在 $$ 块外部"。修复方法：用 Python 正则将 `\\[...\\]` 批量替换为 `$$...$$`，同时确保 `\tag{}` 在 `$$` 内部且独占一行。事后运行 `post_generation_check` 确认修复有效。
   规避方法：在委托 prompt 的 context 中明确写入"禁止使用 `\\[` 和 `\\]` 括公式，必须用 `$$` 括公式块"。

17. **写作指南的深度决定章节质量** — 章节正文质量上限由写作大纲中每节指南的深度决定。指南越具体（指定引入方式、写好过渡语句、标注公司名+技术参数），正文质量越好。如果正文字数或案例质量弱，排查路线：writing-guide → templates/ 模板 → auto_write context，**不在正文层修补**。改善永远发生在模板层。

18. **SKILL.md 膨胀检测** — 每个版本迭代后运行 `references/skill-audit-checklist.md` 中的 5 步快速检查。本技能历史上多次出现容量红线表自身膨胀（14行反膨胀=14行浪费）、25+ pitfalls、broken references 等问题。

18. **KG 噪声词污染 top_terms** — 中文教材章节标题中的"小结""概述""引言"等结构词会占据词频榜首，淹没真正的领域术语。当 top_terms 中出现这些词时，说明 `domain_init.py` 的 `_STOP_WORDS` 需要补充。验证方法：运行 `domain_init.py show --project /path/` 查看 top_terms，如果前 5 项出现"小结""概述""标准简介"等噪声，立即补充到 `_STOP_WORDS` 后重建 KG。常见的噪声模式：
    - 章末结构词："小结""本章小结""思考题""习题"
    - 章首结构词："概述""引言""绪论""标准简介"
    - 无效片段："基于""磁兼容"（电磁兼容的截断）"的"

19. **骨架大纲"太简单"陷阱** — `init_project.py --chapter N` 只生成模板骨架（~15KB），所有 [占位符] 未填充。如果直接展示给用户，会被认为"太简单"。正确流程：
    a. 运行 `init_project.py` 生成骨架
    b. 立即用 delegate_task→write_file 模式填充 15 板块
    不要只运行骨架生成就汇报结果。填充后目标体量 68KB+。

20. **提纲 docx 的章末板块需独立 ## 标题** — 当 `教材提纲.docx` 中某章明确写了「总结；习题；参考文献；深入阅读」等章末板块时，写作指南的"章末必含板块"表只是第一步。

21. **骨架中 {j} 节号未替换** — `init_project.py` 生成骨架时只传入了 `ch` 和 `title`，模板中 `### 第{ch}.{j}节 [标题]` 的 `{j}` 不会被替换，骨架中显示 `### 第1.{j}节 [标题]`。正常现象，`{j}` 由后续填充时逐节替换为实际节号 1~5。填充后务必确认所有 `{j}` 已替换。

22. **质量审计对中间推导公式编号的误报** — `quality_audit.py` 统计 `$$` 块总数对比 `\\tag` 数量，五步推导的中间步骤（Step 3-4，无 `\\tag`）被报"缺 N 个编号"。这是规范的——"辅助公式直接给出，不自创编号"。规避：中间推导用 `$...$` 行内公式而非 `$$...$$` 块级，消除误报。

23. **写作大纲生成质量 — 新版Ch1对比提炼的7条增强规则**（2026-06-12）：写作指南必须包含：①概念建构四步法（现象→定义→辨析→深化，每步写出可直接用的正文句子）；②开篇三法选择（日常现象/历史事件/工程矛盾，[x]标注选中）；③必备结构化要素6选3（[x]勾选+逐项完整实现）；④公式推导五步法；⑤案例参数量化表；⑥教材匹配度分析总结。详见 `references/outline-writing-standards.md`。

24. **验证管线必须端到端** — 当用户要求"验证第1章大纲"时，完整流程是：
    a. 运行 `domain_init.py --project /path/`（Phase 0）
    b. 运行 `init_project.py --project /path/ --chapter 1`（生成骨架）
    c. delegate_task 填充 15 板块（写完整大纲到 68KB+）
    d. 运行 `quality_audit.py` + `post_generation_check.py` 验证
    只跑骨架就展示结果 = 被用户问"写作大纲怎么这么简单？"。填充前和填充后是完全不同的产物。

25. **`init_project.py` 依赖 `python-docx`** — 解析提纲 .docx 需要 `python-docx` 包。如果环境未安装，`init_project.py` 返回空章节列表（静默失败）。安装命令：`uv pip install python-docx`。如果解析仍失败，检查提纲文件是否存在于 `input/教材提纲.docx` 路径。

## Reference Index

### L1 必备（每次加载）

| 文件 | 内容 |
|:-----|:------|
| `references/professor-level-writing-guide.md` | 9大教授级教学法（域无关） |
| `references/outline-writing-standards.md` | 写作大纲质量标准 + 体量基准 |
| `references/mermaid-compatibility-guide.md` | Mermaid 语法约束 |
| `references/chapter-writing-delegation.md` | 章节写作委托指南 |
| `references/domain-agnostic-architecture.md` | 领域无关架构设计 |

### L2 按需（按场景选择）

见 `references/ref-quickref.md`（场景速查表）和 `references/INDEX.md`（完整分层目录）。

### 脚本索引

| 脚本 | 用途 |
|:-----|:------|
| `scripts/domain_init.py` | 领域初始化（TOC→KG→注入，合三为一） |
| `scripts/init_project.py` | 项目初始化（创建+大纲+QC+任务，四合一） |
| `scripts/auto_write.py` | 自动写作（delegate_task） |
| `scripts/batch_fix_formula_numbers.py` | 批量修复公式编号 |
| `scripts/quality_audit.py` | 质量审计 |
| `scripts/outline_vs_chapter_audit.py` | 差距分析 |
| `scripts/post_generation_check.py` | 生成后检查 |
|