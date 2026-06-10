# Mermaid Validation Coverage

## Checks Currently Implemented (validate_mermaid.py)

| Check | Detection | Fix |
|-------|-----------|-----|
| `flowchart` keyword | ⚠️ 报警 | 改为 `graph TD` |
| `graph X X` double keyword | ❌ 报警 | 去掉重复: `graph TD TD`→`graph TD` |
| Diamond node `<>` chars | ❌ 报警 | 用中文"小于"/"大于"替代 `<`/`>` |
| Single-line graph | ⚠️ 报警 | 每个节点/边换成独立行 |
| Special chars in labels | ⚠️ 报警 | 用 `"双引号"` 包裹标签 |
| Missing mermaid block | ⚠️ 报警 | 概念图节必须有 ````mermaid` 块 |

## Shell Tricks for Quick Checks

```bash
# Count triple-backtick balance (must be even)
grep -c '```' *.md | awk -F: '$2%2==1'

# Find diamond nodes with < or > inside mermaid blocks
grep -A5 '```mermaid' *.md | grep '{.*<.*}'

# Find flowchart keyword (non-mermaid context OK)
grep -rn 'flowchart' --include='*.md' .

# Find graph TD TD (double keyword)
grep -rn 'graph TD TD\|graph LR LR\|graph BT BT' --include='*.md' .
```

## History of Mermaid Rendering Issues Found in This KB

| Date | Found In | Root Cause | Fix |
|------|----------|------------|-----|
| 2026-06-09 | `电磁兼容概论_柯金良` 概念/技能点/场景 (46 files) | `flowchart` 关键字不兼容 Obsidian | `flowchart TD`→`graph TD` (精确替换，非字符串替换) |
| 2026-06-09 | Same 46 files | `sed 's/flowchart/graph TD/g'` 产生 `graph TD TD` | `sed 's/^flowchart TD/graph TD/'` → `validate_mermaid` 新增检测 |
| 2026-06-09 | `电磁骚扰接收机测量方法.md` | `{峰值<限值?}` → Mermaid 把 `<` 当方向符 | 用中文"小于"替代 `<` |
| 2026-06-09 | Same file | `re.sub` 吃掉第1个 Mermaid 块的闭口 ``` | `grep -c '```'` 验证偶数，补回闭口 |
| 2026-06-09 | `电磁兼容原理` 4个概念文件 | 单行 Mermaid 图 (graph TD A-->B 挤一行) | 分解为多行排版 |
