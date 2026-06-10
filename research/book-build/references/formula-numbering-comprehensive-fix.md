# 公式编号综合修复 — 完整方案（2026-06-11 最终版）

## 问题场景

教材生成后出现以下一个或多个问题：
1. `\tag{N-M}` 在 `$$` 闭合行之后（位置错误）
2. 引用块内使用 `> $$` 而非 `$$`（格式不一致）
3. 某些 `$$` 行未闭合（奇数个 `$$`）
4. 存在空 `$$...$$` 块导致编号偏移
5. `\tag{}` 重复或缺失
6. **batch_fix 脚本错误地将 blockquote 内的 `> $$` 规范化为 `$$`，破坏引用块结构**

## 完整修复流程（按顺序执行，不可跳过）

### Step 1: 清除所有 \tag{}（不管位置是否正确）
```python
lines = [re.sub(r'\\\\tag\\{.*?\\}', '', line) for line in lines]
lines = [l for l in lines if not re.match(r'^\\s*\\\\tag\\{.*?\\}\\s*$', l.strip())]
lines = [l for l in lines if not re.match(r'^> \\\\tag\\{.*?\\}$', l.strip())]  # 也清理 blockquote 内的 tag
```
**关键**：即使 `\tag{}` 位置正确也要清除，因为修复后需要重新编号。

### Step 2: 检查 blockquote 公式 — 保留 `> $$` 结构
**不要盲目规范化 `> $$ → $$`！** Blockquote 内的公式必须保留 `> ` 前缀。

Blockquote 公式的正确结构：
```
> **柯金良观点：**
>
> $$
> 公式内容
> \tag{N-M}
> $$
>
> 后续文本
```

`> $$` 是合法的公式边界标记，状态机必须同时识别 `$$` 和 `> $$`。

### Step 3: 删除连续公式边界（空块）
```python
def is_boundary(s):
    return s == '$$' or s == '> $$'

changed = True
while changed:
    new_lines = []
    i = 0
    changed = False
    while i < len(lines):
        if i+1 < len(lines) and is_boundary(lines[i].strip()) and is_boundary(lines[i+1].strip()):
            i += 2
            changed = True
            continue
        new_lines.append(lines[i])
        i += 1
    lines = new_lines
```

### Step 4: 检测并修复未闭合边界
```python
in_f = False
for i, line in enumerate(lines):
    if line.strip() in ('$$', '> $$'):
        in_f = not in_f
if in_f:
    # 找到最后一个边界，在其前一个非空行后插入相同类型的边界
```

### Step 5: 再次删除连续边界（修复后可能产生）

### Step 6: 行级配对 + 编号（blockquote 感知版）
```python
in_formula = False
formula_is_blockquote = False
counter = 0
output = []
buf = []
for line in lines:
    stripped = line.strip()
    is_boundary = (stripped == '$$' or stripped == '> $$')
    if not in_formula:
        if is_boundary:
            in_formula = True
            formula_is_blockquote = stripped.startswith('> ')
            buf = [line]
        else:
            output.append(line)
    else:
        buf.append(line)
        if is_boundary:
            in_formula = False
            counter += 1
            has_content = any(l.strip() and l.strip() not in ('$$', '> $$') for l in buf)
            if has_content:
                tag = f'\\\\tag{{{ch}-{counter}}}'
                if formula_is_blockquote:
                    tag = '> ' + tag
                insert_pos = len(buf) - 1
                while insert_pos >= 0 and buf[insert_pos].strip() in ('$$', '> $$'):
                    insert_pos -= 1
                buf.insert(insert_pos + 1, tag)
            output.extend(buf)
            buf = []
if buf:
    output.extend(buf)
```

## 诊断决策流（先诊断，后修复）

```
Step 0: 判断 batch_fix 脚本版本
  ├── v2 或更早 → 会破坏 blockquote 公式！先升级到 v3
  └── v3 → 安全

Step 1: 检查 $$ 和 > $$ 总数
  ├── 奇数 → 存在未闭合的边界或孤立边界行
  │     ├── 超大公式块（跨越50+行）→ 未闭合 $$（陷阱 D3）
  │     └── 单个未配对 → 孤立边界行
  └── 偶数 → 跳 Step 2

Step 2: 检查 tag 位置
   ├── 纯 tag（无 >）后一行不是 $$ → tag 放错了位置
   ├── > tag（有 >）后一行不是 > $$ → tag 放错了位置
   └── 位置正确 → 跳 Step 3

Step 3: 检查 blockquote 公式完整性
   ├── > $$ + > tag + > $$ 顺序正确 → ✅
   ├── > $$ + tag（无 >）+ > $$ → blockquote 内 tag 缺少 > 前缀
   └── $$ + > 内容 + $$（无 > 前缀在边界）→ 已规范化但 blockquote 被破坏

Step 4: 检查编号连续性
   ├── 不连续（如 1,2,3,5,6，缺 4）→ 有空块被跳过（陷阱 B）
   └── 连续 → ✅ 正常
```

**常用诊断命令：**

```bash
# 检查所有公式边界（包括 blockquote 内的）
grep -c '^\$\$$' 第7章.md                  # 纯 $$ 行数
grep -c '^> \$\$$' 第7章.md               # blockquote 内 $$ 行数
# 两者之和应为偶数

# 检查 tag 位置（普通公式）
grep -n -A1 '^\\\\tag{' 第7章.md | grep -v '^--$'
# tag 行后应为 $$

# 检查 tag 位置（blockquote 公式）
grep -n -A1 '^> \\\\tag{' 第7章.md | grep -v '^--$'
# tag 行后应为 > $$

# 检查编号连续性
grep -o '\\\\tag{7-[0-9]*}' 第7章.md | sort -t- -k2 -n | cat -n
# 行号应与编号一致
```

## 验证清单

- [ ] `$$` 和 `> $$` 的总行数为偶数
- [ ] 无孤立 `\tag{}` 或 `> \tag{}`（块外）
- [ ] 编号连续：`tags == list(range(1, len(tags)+1))`
- [ ] 所有普通 `\tag{}` 后面一行是 `$$`
- [ ] 所有 `> \tag{}` 后面一行是 `> $$`
- [ ] 无空 `$$...$$` 或 `> $$...> $$` 块
- [ ] blockquote 公式的 `> ` 前缀被保留
- [ ] 无超大公式块（跨越 50+ 行，标志未闭合边界）

## 陷阱 F：blockquote 公式被 batch_fix v2 破坏（2026-06-11 新发现）

**根因**：`batch_fix_formula_numbers.py` v2 的 Step 3 盲目执行 `> $$ → $$` 规范化，破坏 blockquote 内的公式结构。

**症状**：运行 batch_fix 后，blockquote 中的公式：
- `> $$` 边界被改为 `$$`（blockquote 被破坏）
- `> \tag{}` 行被删除（编号丢失）
- 引用块文本和公式混在一起无法区分

**修复**：
1. 手动恢复 blockquote 结构：对 blockquote 内的 `$$` 行和 `\tag{}` 行重新添加 `> ` 前缀
2. 升级到 `batch_fix_formula_numbers.py` v3（不再规范化 `> $$`）

**预防**：
- **始终使用 v3 或更高版本**的 batch_fix_formula_numbers.py
- 如果文件包含 blockquote 公式（柯金良参考文献等），v2 会破坏它们
- v3 的状态机会同时识别 `$$` 和 `> $$` 作为公式边界，并自动给 blockquote 公式的 `\tag{}` 加 `> ` 前缀

## 绝对禁止的操作

1. **不要用正则 `\$\$(.*?)\$\$` 匹配公式块** — 对 `>$$` 格式无效，对嵌套内容不可靠
2. **不要盲目规范化 `> $$ → $$`** — 会破坏 blockquote 公式！状态机应直接处理 `> $$`
3. **不要 `open(f, 'w')` 后读同一文件** — 会读到空内容（已导致13章数据丢失事故）
4. **不要跳过空块检测** — 空 `$$...$$` 会吃掉一个编号
5. **不要在 v3 脚本上使用 v2 的修复顺序** — v3 不移除 `>` 空行，不规范化 `> $$`
