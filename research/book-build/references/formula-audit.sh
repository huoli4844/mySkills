#!/bin/bash
# formula-audit.sh — 教材章节公式与图号全编审计
# 用法: bash formula-audit.sh output/第N章.md
# 检查项: 公式编号连续性 / 花括号平衡 / \left\right匹配 / Mermaid闭合 / 图号唯一性

FILE="$1"
if [ -z "$FILE" ]; then
  echo "用法: bash $0 output/第N章.md"
  exit 1
fi
if [ ! -f "$FILE" ]; then
  echo "❌ 文件不存在: $FILE"
  exit 1
fi

echo "═══════════════════════════════════════════"
echo "  公式全编审计 — $(basename $FILE)"
echo "═══════════════════════════════════════════"

# 1. 公式计数
TAG_COUNT=$(grep -c 'tag{' "$FILE" 2>/dev/null || echo 0)
echo ""
echo "① 公式编号数: $TAG_COUNT"

# 2. 编号连续性
echo "② 编号连续性检查:"
TAG_NUMS=$(grep -o 'tag{[0-9]-[0-9]*}' "$FILE" | sed 's/tag{//;s/}//' | sort -t- -k2 -n)
CHAPTER=$(echo "$TAG_NUMS" | head -1 | cut -d- -f1)
NUMS=$(echo "$TAG_NUMS" | cut -d- -f2 | sort -n)
EXPECTED=$(seq $(echo "$NUMS" | head -1) $(echo "$NUMS" | tail -1))
MISSING=$(comm -23 <(echo "$EXPECTED" | tr ' ' '\n') <(echo "$NUMS" | sort -u) 2>/dev/null)
DUPES=$(echo "$NUMS" | sort | uniq -d)
if [ -z "$MISSING" ]; then
  echo "  ✅ 编号连续 (${CHAPTER}-$(echo "$NUMS" | head -1) ~ ${CHAPTER}-$(echo "$NUMS" | tail -1))"
else
  echo "  ❌ 缺失编号: $MISSING"
fi
if [ -z "$DUPES" ]; then
  echo "  ✅ 编号无重复"
else
  echo "  ❌ 重复编号: $DUPES"
fi

# 3. 花括号平衡
echo "③ LaTeX 语法检查:"
python3 -c "
import re, sys
c = open('$FILE').read()
blocks = re.findall(r'\$\$(.*?)\$\$', c, re.DOTALL)
errors = []
for i, b in enumerate(blocks):
    braces = b.count('{') - b.count('}')
    lr = b.count('\\\left') - b.count('\\\right')
    empty_frac = '\\frac{' in b and ('\\frac{}{}' in b or '\\frac{}{' in b or '\\frac{ }{}' in b)
    if braces != 0: errors.append(f'  块{i+1}: 花括号差{braces}')
    if lr != 0: errors.append(f'  块{i+1}: \\\\left/\\\\right差{lr}')
    if empty_frac: errors.append(f'  块{i+1}: 空\\frac')
if errors:
    for e in errors: print(e)
else:
    print('  ✅ 花括号平衡 / \\\\left\\\\right对称 / 无空\\frac')
"

# 4. 公式块数 vs tag数
echo "④ 公式块完整性:"
python3 -c "
import re
c = open('$FILE').read()
blocks = len(re.findall(r'\$\$[^$]+\$\$', c))
tags = c.count('\\\\tag{')
if blocks == tags:
    print(f'  ✅ {blocks}个公式块 = {tags}个编号')
else:
    print(f'  ⚠️  {blocks}个公式块, 仅{tags}个编号 (差{blocks-tags}个)')
    # 找出无编号块
    parts = c.split('\$\$')
    for i in range(1, len(parts), 2):
        if '\\\\tag{' not in parts[i]:
            # 找到原文位置
            idx = c.find('\$\$' + parts[i][:30], c.find('\$\$' + parts[i][:30]) if i<5 else 0)
            line = c[:idx].count(chr(10)) + 1
            print(f'  → 无编号公式在行{line}: {parts[i][:60].strip()}...')
"

# 5. Mermaid 图检查
echo "⑤ Mermaid图:"
python3 -c "
c = open('$FILE').read()
for i, b in enumerate(c.split('\`\`\`mermaid')[1:], 1):
    end = b.find('\`\`\`')
    print(f'  图{i}: {\"✅\" if end>0 else \"❌ 缺闭合\"}')"

# 6. 图号唯一性
echo "⑥ 图号唯一性:"
FIGURE_NUMS=$(grep -oP '图\d+-\d+' "$FILE" 2>/dev/null || python3 -c "
import re
c = open('$FILE').read()
for m in re.findall(r'图\d+-\d+', c): print(m)
" | sort | uniq -c)
DUP_FIGS=$(echo "$FIGURE_NUMS" | awk '$1>1{print $2}')
if [ -z "$DUP_FIGS" ]; then
  echo "  ✅ 图号无重复"
else
  echo "  ❌ 图号重复: $DUP_FIGS"
fi

# 7. 汇总
echo ""
echo "═══════════════════════════════════════════"
echo "  审计完成"
echo "═══════════════════════════════════════════"
