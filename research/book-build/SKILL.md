---
name: book-build
description: "教材写作管线：大纲驱动 → delegate_task 并行创作 → batch_fix 公式编号 → 质量审计 → git 提交。提供写作大纲解析、内容差距分析、P0/P1 分阶段补充、公式编号批量修复、全章质量审计等工具。适用场景：基于多本参考书进行的中文专业教材（特别是电磁兼容/EMC领域）的结构化编写。"
version: 3.1.0
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

**大纲驱动，写作大纲供料，严格遵循结构，专业级学术写作。** 管线由脚本控制流程、Agent 负责创作判断。脚本不做创造，Agent 不做机械重复。

```
setup_project.py      ① 创建项目目录 + 配置
       ↓
generate_outlines.py  ② 提纲docx → Agent 生成写作大纲（可人工调整）
       ↓
validate_outlines.py  ③ 大纲 QC
       ↓
generate_task_list.py ④ 从大纲生成写作任务列表
       ↓
auto_write.py         ⑤ 按任务列表自动 → delegate_task 逐章创作
       ↓
batch_fix_numbers     ⑥ 批量修复公式编号
       ↓
quality_audit.py      ⑦ 统一质量审计 + 修复
```

**全自动执行（核心偏好）**：执行时不问"要不要/是否继续"，直接做。

## When to Use

- 用户要求**新建**教材项目 → `setup_project.py`
- 需要从提纲+参考书**生成写作大纲** → `generate_outlines.py` + Agent
- 需要**检查写作大纲**完整性 → `validate_outlines.py`
- 需要从大纲**编排写作任务** → `generate_task_list.py`
- 需要**自动逐章写作** → `auto_write.py`
- 需要**补充/扩充**已有章节内容 → delegate_task
- 需要**批量修复**公式编号 → `batch_fix_formula_numbers.py`
- 需要**质量审计** → `quality_audit.py`

## Design

三层配置驱动，职责分离：

| 层 | 内容 | 存放位置 |
|:---|:-----|:---------|
| **技能层** | 操作流程、陷阱清单、公式格式铁律 | SKILL.md + references/ |
| **项目层** | 教材名、参考书路径 | `book-build.yaml` |
| **章节层** | 每章内容结构、建议体量、素材来源 | `写作大纲/writing-guide-chX.md` |

脚本与 Agent 分工：
- **脚本**管流程编排、文件操作、统计检查
- **Agent**管内容创作、质量判断、调整决策

## Workflow

### ① 创建项目

```bash
python3 scripts/setup_project.py /path/to/教材 \
  --name "电磁兼容教材" --outline 教材提纲.docx
```

完成后编辑 `book-build.yaml`，填入参考教材路径。

### ② 生成写作大纲

```bash
# 从提纲 docx 解析章节结构，生成骨架
python3 scripts/generate_outlines.py --project /path/to/教材
```

输出 `output/outline_tasks.json`，每个任务包含：

```json
{"type": "complete_writing_guide",
 "chapter": 3,
 "guide_path": "output/写作大纲/writing-guide-ch3.md",
 "source_books": [...],
 "status": "pending"}
```

Agent 读取后对每个 `pending` 任务执行 `delegate_task`：
- goal: "为第X章完善写作大纲（分析参考书内容，确定写作手法/体量目标/素材来源）"
- context: 从 outline_tasks.json 中提取 guide_path + source_books
- 完成后标记 status 为 completed

### ③ 大纲 QC

```bash
python3 scripts/validate_outlines.py --project /path/to/教材
```

### ④ 生成任务列表

```bash
python3 scripts/generate_task_list.py --project /path/to/教材 --force-init
python3 scripts/generate_task_list.py --project /path/to/教材 --status
python3 scripts/generate_task_list.py --project /path/to/教材 --mark-done 3
```

### ⑤ 自动写作

```bash
# 生成下一条写作任务
python3 scripts/auto_write.py --project /path/to/教材

# 遍历全部待写
python3 scripts/auto_write.py --project /path/to/教材 --all

# 覆盖已有章节
python3 scripts/auto_write.py --project /path/to/教材 --chapter 3 --force
```

`auto_write.py` 输出结构化 JSON 到 `.hermes/tasks/write_chX.json`，格式：

```json
{"goal": "为教材项目创作第X章完整内容",
 "context": "...写作大纲+参考书路径+写作规范...",
 "chapter": X,
 "guide_path": "output/写作大纲/writing-guide-chX.md",
 "output_path": "output/第X章-标题.md"}
```

Agent 读取该 JSON 后直接提交给 `delegate_task`：

```
delegate_task(
  goal=task.goal,
  context=task.context,
  toolsets=["terminal", "file"]
)
```

创作完成后运行 `batch_fix_formula_numbers.py` 修复编号。

### ⑥ 统一修复公式编号

```bash
python3 scripts/batch_fix_formula_numbers.py /path/教材/output/第*.md
```

### ⑦ 质量审计

```bash
# 全量
python3 scripts/quality_audit.py --project /path/to/教材

# 单章
python3 scripts/quality_audit.py --project /path/to/教材 --chapter 7

# 快速（仅检查公式和$$）
python3 scripts/quality_audit.py --project /path/to/教材 --quick
```

### 补充已有章节

```bash
# P0（结构性缺失）：patch 少量框架
# P1（内容质量提升）：delegate_task 深度补充

# 差距分析
python3 scripts/outline_vs_chapter_audit.py \
  --project /path/to/教材 --output /path/to/教材/output
```

## 章节格式标准

```markdown
# 第X章 章节名称
## 内容提要
...段落...
通过本章学习，读者应达成以下学习目标：
1. 能......（不要加 Bloom 标签）
2. 能......
```

**禁止**：`**记忆层**` Bloom 标签、`## 学习目标`（统一为 `## 内容提要`）

## ⚠️ 关键澄清：以下内容不是教材正文

- ❌ `## X.Y 本章写作说明`（含素材来源清单）
- ❌ `## X.Y.Z 12条军规落实检查`
- ❌ `## ★ 全章核心公式总结`

## 公式格式铁律

- `\tag{N-M}` **独占一行**，在公式内容之后、**闭合 `$$` 之前**
- 正确：`$$\n公式\n\tag{N-M}\n$$`
- 错误：`$$\n公式\n$$\n\tag{N-M}`
- 引用块内公式：`> $$\n> 公式\n> \tag{N-M}\n> $$`
- 违反 → 运行 `batch_fix_formula_numbers.py`

## Common Pitfalls

1. **行级状态机，不用正则** — `\$\$(.*?)\$\$` 对 `>$$` 格式无效
2. **空 `$$...$$` 块** — 编号前先删除
3. **`>$$` 保留 `>` 前缀** — v3 做法，不要替换为 `$$`
4. **先读后写** — 永远 `read()` 再 `write()`，绝不先写后读
5. **Mermaid 圆边节点** — `[("text")]`（对）而非 `[("text)"]`（错）
6. **写作说明不写入正文** — 军规检查/核心公式总结是内部工具
7. **book-build.yaml 最小化** — 只放教材名和参考书路径，写作规范在其他地方

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/formula-numbering-diagnosis.md` | 公式编号根因诊断 + 陷阱 A-E |
| `references/formula-numbering-comprehensive-fix.md` | 综合修复流程 + 诊断决策树 |
| `references/comprehensive-quality-audit.md` | 全章质量审计工作流 |
| `references/content-expansion-workflow.md` | 内容扩充工作流 |
| `references/mermaid-guide.md` | Mermaid 陷阱与正确写法 |
| `references/derivation-example-107.md` | 公式推导示例 |
| `references/chapter-writing-standard.md` | 章节写作标准 |
