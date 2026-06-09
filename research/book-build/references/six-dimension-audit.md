# 六维编号审计 — 每章完成后运行

本审计脚本在目标python3环境下运行，无需额外依赖。

```bash
# 替换第N章的文件名后直接执行
python3 -c "
import re
with open('output/第N章-*.md','r') as f:
    text = f.read()
lines = text.split('\n')
N = 8  # ← 替换为当前章号

print('=== 六维编号审计 第{N}章 ===')

# 1) 公式tags
tags = re.findall(r'\\\\tag\{(\d+-\d+)\}', text)
print(f'1) 公式: {len(tags)}个')
for i,t in enumerate(tags):
    ch,num = t.split('-')
    exp = f'{N}-{i+1}'
    if t != exp:
        print(f'   ❌ #{i+1}: {t} (应{exp})')
print(f'   章号无误: {\"✅\" if all(t.split(\"-\")[0]==str(N) for t in tags) else \"❌\"}')

# 2) 图注
figs = re.findall(r'\*图(\d+-\d+)', text)
print(f'2) 图: {len(figs)}个')
for i,f in enumerate(figs):
    exp = f'{N}-{i+1}'
    if f != exp: print(f'   ❌ #{i+1}: 图{f} (应{exp})')

# 3) 例题
exs = re.findall(r'\*\*例(\d+-\d+)', text)
print(f'3) 例: {len(exs)}个')
for i,e in enumerate(exs):
    exp = f'{N}-{i+1}'
    if e != exp: print(f'   ❌ #{i+1}: 例{e} (应{exp})')

# 4) 引用一致性
refs = set(re.findall(r'式\((\d+-\d+)\)', text))
tag_set = set(tags)
miss = refs - tag_set
print(f'4) 引用: {len(refs)}个 {\"✅\" if not miss else \"❌ 缺失: \"+str(miss)}')

# 5) 语法平衡
opens = text.count('\$\$')
mermaid_c = text.count('\`\`\`mermaid')
closes = text.count('\`\`\`') - mermaid_c
print(f'5) 平衡: \$\$={\"✅\" if opens%2==0 else \"❌\"} Mermaid={\"✅\" if mermaid_c==closes else \"❌\"}')

# 6) Mermaid emoji
in_m=False; em=0
for i,line in enumerate(lines,1):
    if line.strip()=='\`\`\`mermaid': in_m=True
    elif in_m and line.strip()=='\`\`\`': in_m=False
    elif in_m:
        if re.findall(r'[\U0001F300-\U0001F9FF\u2600-\u27BF\u2705\u274C]', line): em+=1
print(f'6) Mermaid emoji: {em}处 {\"✅\" if em==0 else \"❌\"}')

print(f'\n体量: {len(lines)}行 / {len(text.encode())}字节 / {len(tags)}公式 / {len(figs)}图 / {len(exs)}例')
"
```

## 常见失败场景与修复

| # | 检查项 | 失败表现 | 修复方法 |
|:-:|:-------|:---------|:---------|
| 1 | 公式章号前缀 | 从第N+1章复制素材导致tag写为`{8-X}`而非`{7-X}` | `sed 's/\\\\tag{8-/\\\\tag{7-/g'` 然后重排 |
| 2 | 图编号重复 | 新Mermaid图插在已有图之间导致重复号 | 全部提取 `*图N-X：` 按位置序重排 |
| 3 | 例编号重复 | 在例7-1和例7-2之间插入新例7-2，原7-2~7-8偏移 | 全部提取`**例N-X**`按位置序重排 |
| 4 | 总览Mermaid引用滞后 | 例题/公式重排后总览图中的例号/公式号未同步 | 手动检查Mermaid块中所有`例N-X`和`式N-X`引用 |
| 5 | 单行$$混淆状态机 | `$$\boxed{xxx}$$`在同一行开闭，导致后续tag被判为"在$$外" | 使用`re.finditer(r'\$\$', text)`位置法而非行状态机 |

## 修复后的链路风暴

任何编号重排都会导致以下引用失效，必须全部同步更新：

1. 文本中的`式(N-X)`、`图N-X`、`见例N-X`等引用
2. 章末总览Mermaid图中的引用
3. 章末要点列表中的引用
4. 习题中的引用（如"用式N-X计算"）
