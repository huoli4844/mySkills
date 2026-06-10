# 公式编号综合修复 — 完整方案（2026-06-11 最终版）

## 问题场景

教材生成后出现以下一个或多个问题：
1. `\tag{N-M}` 在 `$$` 闭合行之后（位置错误）
2. 引用块内使用 `> $$` 而非 `$$`（格式不一致）
3. 某些 `$$` 行未闭合（奇数个 `$$`）
4. 存在空 `$$...$$` 块导致编号偏移
5. `\tag{}` 重复或缺失

## 完整修复流程（按顺序执行，不可跳过）

### Step 1: 清除所有 \tag{}（不管位置是否正确）
```python
lines = [re.sub(r'\\tag\{.*?\}', '', line) for line in lines]
lines = [l for l in lines if not re.match(r'^\s*\\tag\{.*?\}\s*$', l.strip())]
```
**关键**：即使 `\tag{}` 位置正确也要清除，因为修复后需要重新编号。

### Step 2: 规范化 `> $$` → `$$`
```python
lines = [re.sub(r'^>\s*\$\$', '$$', line) for line in lines]
lines = [l for l in lines if l.strip() != '>']  # 删除空引用行
```

### Step 3: 删除连续 `$$`（空块）
```python
# 循环删除直到无变化
while changed:
    new_lines = []
    i = 0
    changed = False
    while i < len(lines):
        if i+1 < len(lines) and lines[i].strip() == '$$' and lines[i+1].strip() == '$$':
            i += 2
            changed = True
            continue
        new_lines.append(lines[i])
        i += 1
    lines = new_lines
```

### Step 4: 检测并修复未闭合 `$$`
```python
in_f = False
for i, line in enumerate(lines):
    if line.strip() == '$$':
        in_f = not in_f
if in_f:
    # 找到最后一个 $$，在其前一个非空行后插入 $$
```

### Step 5: 再次删除连续 `$$`（修复后可能产生）

### Step 6: 行级配对 + 编号
```python
in_formula = False
counter = 0
output = []
buf = []
for line in lines:
    stripped = line.strip()
    is_boundary = (stripped == '$$')
    if not in_formula:
        if is_boundary:
            in_formula = True
            buf = [line]
        else:
            output.append(line)
    else:
        buf.append(line)
        if is_boundary:
            in_formula = False
            counter += 1
            has_content = any(l.strip() and l.strip() != '$$' for l in buf)
            if has_content:
                tag = f'\\tag{{{ch}-{counter}}}'
                insert_pos = len(buf) - 1
                while insert_pos >= 0 and buf[insert_pos].strip() == '$$':
                    insert_pos -= 1
                buf.insert(insert_pos + 1, tag)
            output.extend(buf)
            buf = []
if buf:
    output.extend(buf)
```

## 诊断决策流（先诊断，后修复）

遇到公式编号问题，按以下决策树诊断：

```
Step 1: 检查 $$ 总数
  ├── 奇数 → 存在未闭合的 $$ 或孤立 $$ 行
  │     ├── 大公式块（跨越50+行）→ 未闭合 $$（陷阱 D3）
  │     └── 单个未配对 → 孤立 $$ 行
  └── 偶数 → 跳 Step 2

Step 2: 检查 tag 位置
   ├── tag 在 $$ 之前（tag 行后一行是 $$）→ 所有 tag 放错了位置
   │     └── 这是格式错误：tag 在公式闭合时被放在 $$ 之外
   └── tag 位置正确 → 跳 Step 3

Step 3: 检查引用块内容
   ├── 存在 `> $$` 或 `>$$` → 引用块格式未规范化（陷阱 D2）
   │     └── 规范化后可能导致 Step 1 的 $$ 总数问题
   └── 无 → 跳 Step 4

Step 4: 检查编号连续性
   ├── 不连续（如 1,2,3,5,6，缺 4）→ 有空块被跳过（陷阱 B）
   └── 连续 → ✅ 正常
```

**常用诊断命令**（直接在终端运行）：

```bash
# 检查 $$ 总数
grep -c '^\$\$$' 第7章-滤波技术.md
# 应为偶数

# 检查是否存在 >$$
grep -n '^> *\$\$$' 第7章-滤波技术.md
# 应无输出（已规范化）

# 检查 tag 位置
grep -n -A1 '^\\\\tag{' 第7章-滤波技术.md | grep -v '^--$'
# tag 行后一行应为 $$

# 检查编号连续性
grep -o '\\\\tag{7-[0-9]*}' 第7章-滤波技术.md | sort -t- -k2 -n | cat -n
# 行号应与编号一致（1-1, 2-2, 3-3, ...）
```

## 验证清单

- [ ] `$$` 总数为偶数
- [ ] 无孤立 `\tag{}`（块外）
- [ ] 编号连续：`tags == list(range(1, len(tags)+1))`
- [ ] 所有 `\tag{}` 后面一行是 `$$`
- [ ] 所有 `\tag{}` 前面一行不是 `$$`
- [ ] 无空 `$$...$$` 块
- [ ] 无 `> $$` 未规范化（引用块内也应使用 `$$` 或已规范化）
- [ ] 无超大公式块（跨越 50+ 行，标志未闭合 `$$`）

## 绝对禁止的操作

1. **不要用正则 `\$\$(.*?)\$\$` 匹配公式块** — 对 `>$$` 格式无效，对嵌套内容不可靠
2. **不要用补丁式修复**（先修 `>$$` 再修 tag 位置）— 行号变化导致后续修复失效
3. **不要 `open(f, 'w')` 后读同一文件** — 会读到空内容（已导致13章数据丢失事故）
4. **不要跳过空块检测** — 空 `$$...$$` 会吃掉一个编号
