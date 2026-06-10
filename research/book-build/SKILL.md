---
name: book-build
description: "教材写作管线：大纲驱动 → delegate_task 并行创作 → batch_fix 公式编号 → 质量审计 → git 提交。提供写作大纲解析、内容差距分析、P0/P1 分阶段补充、公式编号批量修复、全章质量审计等工具。适用场景：基于多本参考书进行的中文专业教材（特别是电磁兼容/EMC领域）的结构化编写。"
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [textbook, emc, outline-driven, academic-writing]
    related_skills: [github-repo-management, file2md]
---

# book-build（教材写作管线）

## Overview

**大纲驱动，写作大纲供料，严格遵循结构，专业级学术写作。** 写作大纲是原料，教材是成品——不能把大纲结构复制到教材正文，必须重新组织为自然叙述的学术散文。

**专业教材 = 权威定义 + 直观引入 + 编号公式 + "式中"变量解释 + 含数字实例 + 层次化习题。**

**全自动执行（核心偏好）**：执行时不问"要不要/是否继续"，直接做。做错了再改也比停下来问效率高。

## When to Use

- 用户要求**编写或补充**中文专业教材（特别是EMC/电磁兼容领域）
- 需要**检查已有章节**与写作大纲的差距（`outline_vs_chapter_audit.py`）
- 需要**批量修复**公式编号、$$ 配对、blockquote 公式格式问题（`batch_fix_formula_numbers.py`）
- 需要**扩充**某章体量以达到大纲目标（内容扩充工作流）

**不适用**：英文教材、非结构化写作（无写作大纲的项目）、纯翻译任务。

## Design

教材写作由三层配置驱动，职责分离：

| 层 | 内容 | 存放位置 |
|:---|:-----|:---------|
| **技能层** | 操作流程、陷阱清单、公式格式铁律（怎么写） | 本 SKILL.md + references/ |
| **项目层** | 教材名、参考书路径（项目信息） | `book-build.yaml` |
| **章节层** | 每章内容结构、建议体量、素材来源（写什么） | `写作大纲/writing-guide-chX.md` |

各章内容由 `delegate_task` 并行创作，创作完成后统一用 `batch_fix_formula_numbers.py` 修复公式编号。质量检查通过 `outline_vs_chapter_audit.py` + 综合审计完成。

## Workflow

### A. 检查章节与大纲的差距

```bash
python3 scripts/outline_vs_chapter_audit.py \
  --project /path/to/教材 --output /path/to/教材/output
```
输出：`output/补充与完善分析报告.md` + `output/补充执行清单.json`（不要提交到 git）

### B. 补充缺失内容

按 P0 → P1 顺序执行：

**P0（结构性缺失）**：缺失内容节、缺失本章总结 → 直接 `patch` 或 `delegate_task` 创作，每章增加 10-50 行

**P1（内容质量提升）**：真实案例、计算例题、参考书盲区深度补充 → 必须 `delegate_task` + 参考书源文提取，每章 50-200 行

### C. 批量修复公式编号

```bash
# v3 blockquote 安全版：保留 > $$ 结构，同时识别 $$ 和 > $$ 为公式边界
python3 scripts/batch_fix_formula_numbers.py /path/to/教材/output/第*.md
```

### D. 内容扩充（当某章体量显著不足时）

```bash
# 1. 读取写作大纲得知目标体量（如 8.1.1 建议 25KB）
# 2. 用 delegate_task 扩充（每章独立任务，max_concurrent_children=3）
# 3. 最后运行 batch_fix_formula_numbers.py
```

### E. git 提交

```bash
cd /path/to/教材
git add -A
git commit -m "feat: 说明改动内容"
git push
```

## 章节格式标准（2026-06-12 统一）

每章开头：

```markdown
# 第X章 章节名称

## 内容提要

本章概述段落。

通过本章学习，读者应达成以下学习目标：

1. 能......（不要加 Bloom 标签）
2. 能......
```

**禁止**：`**记忆层**`/`**理解层**` 等 Bloom 标签、`## 学习目标`（统一为 `## 内容提要`）

## ⚠️ 关键澄清：以下内容不是教材正文

写作说明、军规检查、核心公式总结是**写作过程中的质量检查工具**，**不得写入教材成品**。教材正文只包含：叙述性内容、编号公式、表格/Mermaid图、例题与习题、参考文献。

- ❌ `## X.Y 本章写作说明`
- ❌ `## X.Y.Z 12条军规落实检查`
- ❌ `## ★ 全章核心公式总结`（公式已在正文中用 `\tag{}` 编号）

## 公式格式铁律

- `\tag{N-M}` **独占一行**，在公式内容之后、**闭合 `$$` 之前**
- 正确：`$$\n公式\n\tag{N-M}\n$$`
- 错误：`$$\n公式\n$$\n\tag{N-M}`
- 引用块内公式：`> $$\n> 公式\n> \tag{N-M}\n> $$`
- 行内公式用 `$...$`
- 违反上述规则 → 运行 `batch_fix_formula_numbers.py`（v3+）

## Common Pitfalls

1. **正则 `\$\$(.*?)\$\$` 不可靠** — 对 `>$$` 格式无效，对嵌套内容不可靠。必须用行级状态机
2. **空 `$$...$$` 块导致编号偏移** — 编号前先扫描删除空块
3. **孤立 `$$` 或 `> $$` 行破坏配对计数** — 用状态机配对后删除未配对的边界行
4. **`>$$` 引用块格式** — 保留 `> $$` 不变（v3），不要替换为 `$$`（v2 做法会破坏 blockquote 结构）
5. **先写后读** — 永远先 `open(f, 'r').read()` 再 `open(f, 'w').write()`，绝不先写后读
6. **Mermaid 圆边节点括号顺序** — `[("text\")]"`（错）→ `[("text\")]"` 应为 `[("text")]`（对），`)"` 顺序使 `)` 被吞入标签字符串

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/formula-numbering-diagnosis.md` | 公式编号缺失根因诊断 + 陷阱 A-E |
| `references/formula-numbering-comprehensive-fix.md` | 综合修复流程 + 诊断决策树 |
| `references/comprehensive-quality-audit.md` | 全章质量审计工作流 |
| `references/audit-pitfalls.md` | 审计陷阱（覆盖不全/小结条目数/正则匹配） |
| `references/content-expansion-workflow.md` | 内容扩充工作流详细步骤 |
| `references/mermaid-guide.md` | Mermaid 陷阱与正确写法 |
| `references/content-supplementation-workflow.md` | P0/P1 补充工作流 |
| `references/derivation-example-107.md` | 公式推导示例 |
| `references/gap-analysis-checklist.md` | 差距分析检查清单 |
| `references/chapter-writing-standard.md` | 章节写作标准 |
