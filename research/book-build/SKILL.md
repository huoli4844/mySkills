---
name: book-build
description: "教材写作管线：大纲驱动 → delegate_task 并行创作 → batch_fix 公式编号 → 质量审计 → git 提交"
version: 3.4.0
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

**核心原则：** 借鉴手法，不照搬内容。参考教材是学写法的老师，不是抄内容的仓库。

**全自动执行：** 不问"要不要/是否继续"，直接做。做错了改比问效率高。

```
setup_project.py      ① 创建项目
generate_outlines.py  ② 提纲docx → 写作大纲（15板块结构）
validate_outlines.py  ③ 大纲QC
generate_task_list.py ④ 生成写作任务
auto_write.py         ⑤ delegate_task 逐章创作
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

### 三层配置
| 层 | 内容 | 位置 |
|:---|:-----|:-----|
| 技能层 | 操作流程、约束、铁律 | SKILL.md + references/ |
| 项目层 | 教材名、参考书路径 | `book-build.yaml` |
| 章节层 | 每章结构、体量、素材 | `写作大纲/writing-guide-chX.md` |

### 脚本 vs Agent 分工
脚本管流程编排和统计检查；Agent 管内容创作和质量判断。

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

## Reference Index

| 需要时加载 | 内容 |
|:-----------|:------|
| `references/professor-level-writing-guide.md` | 教授级写作指南 |
| `references/outline-writing-standards.md` | 写作大纲质量标准 + 15板块 + 体量基准 |
| `references/chapter-writing-standard.md` | 章节写作军规 |
| `references/comprehensive-quality-audit.md` | 质量审计工作流 |
| `references/mermaid-compatibility-guide.md` | Mermaid 禁止语法 + 替代方案 |
| `references/mermaid-validation-checklist.md` | Mermaid 语法检查清单 |
| `references/mermaid-guide.md` | Mermaid 陷阱与正确写法 |
| `references/formula-numbering-diagnosis.md` | 公式编号诊断 |
| `references/formula-numbering-comprehensive-fix.md` | 公式编号修复流程 |
| `references/derivation-example-107.md` | 公式推导示例 |
| `references/volume-standards.md` | 体量基准与映射 |
| `references/delegate-vs-direct-write.md` | delegate 边界说明 |
| `references/parallel-section-writing.md` | 并行分节写作 |
| `references/content-expansion-workflow.md` | 内容扩充 |
| `references/audit-pitfalls.md` | 审计常见错误 |
| `references/textbook-style-guide.md` | 排版规范 |
| `references/audit-script-landscape.md` | 审计脚本全景 |
