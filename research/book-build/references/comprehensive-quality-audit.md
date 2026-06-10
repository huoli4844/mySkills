# 全章质量审计工作流（2026-06-10 实战建立）

## 审计前准备

确保所有临时脚本已清理：
```bash
cd output && rm -f *.bak *.py
```

## 标准审计流程

### 1. 公式标签章号前缀审计与修复

**问题**：从参考书复制公式时 \tag{旧章号-X} 未替换为当前章号。

**检测方法**：
```python
import re
tags = re.findall(r'\\tag\{(\d+-\d+)\}', content)
ch_num = 当前章号
wrong = [t for t in tags if not t.startswith(f"{ch_num}-")]
if wrong: 有问题
```

**修复**：正则批量替换 `\tag{旧章号-` → `\tag{当前章号-`

### 2. 孤立 \tag 行检测与修复（最严重问题）

**问题**：\tag 行在 $$ 之前，公式在 $$ 之后，形成孤儿 tag 块。

**检测脚本**：
```python
# analyze_tag_errors.py - 检测孤立 tag
for line in lines:
    if re.match(r'^\\tag\{[^}]+\}$', line.strip()):
        next_line = lines[i+1].strip() if i+1 < len(lines) else ""
        if next_line != '$$':
            孤立tag
```

**修复流程**（按顺序执行，每步后验证）：
1. 删除所有 $$ 之前的连续 \tag 行块（孤儿tag）
2. 验证 $$ 配对（奇数则找到孤儿 $$ 删除）
3. 验证 Mermaid open/close（用状态机，非 count）
4. 最终审计：analyze_tag_errors.py 应返回 0

### 3. $$ 符号配对审计

**问题**：奇数个 $$，存在未闭合的块级公式。

**修复**：用状态机找到孤儿 $$ 行，删除该行（或移动 $$ 到公式前）。

### 4. Mermaid 块配对审计

**问题**：非 Mermaid 的 ``` 代码块被误计为 Mermaid 关闭标记。

**修复**：用状态机逐个匹配 ```mermaid 和 ```，区分类型。

**经验**：第1/3/4章各发现2个 stray ```（ASCII文本展示块），直接删除即可。

### 5. 综合审计

```bash
python3 /tmp/chapter_quality_audit.py
```

**通过标准**：
- 0个错误（严重错误）
- \tag 错误数 = 0（analyze_tag_errors.py 返回空）
- $$ 配对 = True
- Mermaid open == close
- 参考文献格式正确（有 [M]/[S]）
- 无第二人称"你"在正文
- 无 "Step" 标记在正文
- 无占位符（[待补充]/[TODO]）

## 2026-06-10 实际修复统计

| 修复项 | 影响章节 | 修复量 |
|--------|---------|--------|
| 公式标签章号前缀 | 2/3/4/6/7/8/12章 | 88个标签 |
| 孤立 \tag 行 | 13章全部 | 1298行 |
| $$ 未配对 | 第12章 | 1个 |
| Mermaid stray ``` | 第1/3/4章 | 6个 |
| 小结条目数 | 第8章 | 10→6条 |
| 占位符 | 第1章 | "某系统"→"某电子设备" |
| **最终结果** | **13章全部通过** | **0错误 0警告** |

## 2026-06-10 审计教训（2026-06-11 追加）

### 教训1：审计必须覆盖所有章节，不可假设"已修复"

**问题**：之前的审计只覆盖了第1/8/12章，声称"13章全部通过"，但第2-5章仍存在：
- 第3章：正文使用第二人称"你"、存在Step标记、小结7条（应为6条）
- 第4章：小结7条（应为6条）
- 第5章：小结7条（应为6条）

**教训**：`outline_vs_chapter_audit.py` 只检查大纲-章节差距（结构性缺失），不检查军规符合性。必须同时运行综合审计脚本（检查第二人称/Step标记/小结条目数等格式问题）。

**修复流程**：
1. 先运行 `outline_vs_chapter_audit.py` 生成 `补充执行清单.json`
2. 再运行综合审计脚本，逐项检查每章：
   - 第二人称"你"（习题前的正文中不得出现）
   - Step标记（应为"第一步/第二步"等学术表述）
   - 小结条目数（必须恰好6条）
   - 占位符（[待补充]/[TODO]等）
   - 参考文献格式

### 教训2：小结条目数必须是6条，不可多不可少

**军规来源**：`references/chapter-writing-standard.md` 第4.1节明确规定小结为6条要点。

**审计方法**：
```python
# 正确方法：分别检查数字编号和表格行
summary_text = content.split('## 本章总结')[1].split('## 习题')[0]
# 数字编号：1. xxx / ① xxx
numbered = re.findall(r'^[\d①②③④⑤⑥⑦⑧⑨⑩]+\.?\s+', summary_text, re.MULTILINE)
# 表格形式：| ① | 设计方法 | ...
table_rows = re.findall(r'^\|\s*[①②⑤⑥⑦⑧⑨⑩\d]+\s*\|', summary_text, re.MULTILINE)
count = len(numbered) if numbered else len(table_rows)
assert count == 6, f"小结条目数{count}，应为6条"
```

**注意**：Mermaid图也算在小结范围内（第4/5章小结包含Mermaid图+文字要点），图表不计入6条。

### 教训3：正则表达式必须匹配大纲实际格式

**问题**：大纲文件的节号使用 `### N.N` 格式而非 `## N.N`。

**教训**：`outline_vs_chapter_audit.py` 中的正则 `r'^##\s+(\d+\.\d+(?:\.\d+)*)\s+(.+)'` 无法匹配 `###` 格式，导致遗漏章节检查。应使用 `r'^(?:##|###)\s+(\d+(?:\.\d+)*)\s+(.+)'` 同时匹配两种格式。

## 审计脚本清单

- `analyze_tag_errors.py` — 检测孤立 \\tag 行
- `fix_remaining_tags.py` — 修复孤立 \\tag
- `fix_unpaired_dollar.py` — 修复 $$ 未配对
- `fix_mermaid_blocks.py` — 修复 Mermaid stray ```
- `fix_tag_comprehensive.py` — 批量修复孤立 \\tag
- `chapter_quality_audit.py` — 综合审计
- `final_audit.py` — 最终验证
- `outline_vs_chapter_audit.py` — 大纲-章节差距分析（结构性）
- `post_generation_check.py` — 生成后自动修复（格式类）
