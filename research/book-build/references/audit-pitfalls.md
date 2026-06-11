# 审计陷阱专项（2026-06-11 新增）

## Pitfall 1: 审计必须覆盖所有章节

**问题**：之前的审计只覆盖了部分章节（第1/8/12章），声称"13章全部通过0错误0警告"，但第2-5章仍存在：
- 第3章：正文使用第二人称"你"、存在Step标记、小结7条（应为6条）
- 第4章：小结7条（应为6条）
- 第5章：小结7条（应为6条）

**教训**：`outline_vs_chapter_audit.py` 只检查大纲-章节差距（结构性缺失），不检查军规符合性。必须同时运行综合审计脚本。

**修复流程**：
1. 先运行 `outline_vs_chapter_audit.py` 生成 `补充执行清单.json`
2. 再运行综合审计脚本，逐项检查每章：
   - 第二人称"你"（习题前的正文中不得出现）
   - Step标记（应为"第一步/第二步"等学术表述）
   - 小结条目数（必须恰好6条）
   - 占位符（[待补充]/[TODO]等）
   - 参考文献格式

## Pitfall 2: 小结条目数必须是6条

**军规来源**：`references/chapter-writing-rules.md` 第4.1节明确规定小结为6条要点。

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

## Pitfall 3: 正则表达式必须匹配大纲实际格式

**问题**：大纲文件的节号使用 `### N.N` 格式而非 `## N.N`。

**教训**：`outline_vs_chapter_audit.py` 中的正则 `r'^##\s+(\d+\.\d+(?:\.\d+)*)\s+(.+)'` 无法匹配 `###` 格式。应使用 `r'^(?:##|###)\s+(\d+(?:\.\d+)*)\s+(.+)'` 同时匹配两种格式。
