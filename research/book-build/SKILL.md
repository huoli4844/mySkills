---
name: book-build
description: "教材写作管线：大纲驱动 → delegate_task 并行创作 → batch_fix 公式编号 → 质量审计 → git 提交"
version: 3.4.0
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
setup_project.py      ① 创建项目
generate_outlines.py  ② 提纲docx → 写作大纲（15板块结构）
validate_outlines.py  ③ 大纲QC
generate_task_list.py ④ 生成写作任务
auto_write.py         ⑤ 任务JSON → Agent调用delegate_task
batch_fix_numbers     ⑥ 批量修复公式编号
quality_audit.py      ⑦ 统一质量审计
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
- ❌ 写入大纲/章节（≥35KB 必超时，5次实测）
- ✅ 正确模式：delegate 做分析 → 主 Agent 用 `write_file` 直写

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

领域上下文层是 v3.5.0 新增：`setup_project.py` 在初始化时从参考书 .md 提取章节标题 → 词频统计 → 生成。

### SKILL.md 设计原则（被纠正的错误不要重犯）

SKILL.md **只放 Agent 加载时需要知道的东西**。以下内容不应出现在 SKILL.md：
- ❌ 维护契约/自检清单（自身就是膨胀）
- ❌ 与其他技能的对照表（对当前任务无关）
- ❌ 重复 references/ 已有的详细内容
- ❌ 历史记录、实战教训、版本对比数据

以上内容应放入 `references/`，通过 Reference Index 按需加载。
判断标准：这条内容 Agent 每次加载技能时都必须看到吗？如果不需要 → 放 references/。

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

## Workflow

```bash
# ① 创建项目
python3 scripts/setup_project.py /path/to/教材 --name "教材名" --outline 教材提纲.docx

# ② 生成写作大纲（两阶段：脚本骨架 → Agent 填充15板块）
python3 scripts/generate_outlines.py --project /path/to/教材

# ③ 大纲QC
python3 scripts/validate_outlines.py --project /path/to/教材

# ④ 生成任务列表
python3 scripts/generate_task_list.py --project /path/to/教材 --force-init

# ⑤ 自动写作（auto_write.py 输出 JSON → delegate_task）
python3 scripts/auto_write.py --project /path/to/教材

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
触发条件：测试新增≥20个 / 代码重构 / 版本号修改。

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
14. **多本书 TOC 合并用知识点图谱** — 单本书的章节结构不代表整个领域。必须合并多本书、按概念频次排序。高频概念（出现 3+/4 本）才是必须覆盖的内容。详见 `references/domain-agnostic-architecture.md`。

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/professor-level-writing-guide.md` | 教授级写作指南 |
| `references/outline-writing-standards.md` | 写作大纲质量标准 + 15板块 + 体量基准 |
| `references/chapter-writing-standard.md` | 章节写作军规 |
| `references/comprehensive-quality-audit.md` | 质量审计工作流 |
| `references/mermaid-compatibility-guide.md` | Mermaid 兼容性指南（含语法、禁止项、排查表、验证命令） |
| `references/formula-numbering-diagnosis.md` | 公式编号诊断 |
| `references/formula-numbering-comprehensive-fix.md` | 公式编号修复流程 |
| `references/derivation-example-107.md` | 公式推导示例 |
| `references/volume-standards.md` | 体量基准与映射 |
| `references/gap-fill-workflow.md` | 写作大纲查疑补漏工作流（6项结构检查+补漏原则） |
| `references/delegate-vs-direct-write.md` | delegate 边界说明 |
| `references/parallel-section-writing.md` | 并行分节写作 |
| `references/content-supplementation-workflow.md` | 内容补充工作流（P0/P1/P2） |
| `references/domain-agnostic-architecture.md` | 领域无关架构设计（变量+注入策略） |
| `references/domain-agnostic-audit.md` | 领域无关审计命令 |
| `scripts/book_toc.py` | 从 minerU .md 提取目录结构 |
| `scripts/kg_builder.py` | 知识图谱引擎（build/query/show） |
| `scripts/domain_injector.py` | 领域信号注入（填充 reference 变量） |
| `references/textbook-style-guide.md` | 排版规范 |
| `references/audit-script-landscape.md` | 审计脚本全景 |
