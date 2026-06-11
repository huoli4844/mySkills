# 大章并行分节创作 + 组装工作流

## 问题

单次 `delegate_task` 创作完整章节（60~80KB）时，子代理会在 600s 超时（实测两次：第2章大纲填充和正文创作均超时）。600s 内仅能完成 7~11 次 API 调用，不足以完成阅读参考教材 + 写出完整章节。

## 方案：并行分节 + 组装

### 第1步：分析参考教材（可选，做一次）

如果需要从参考教材提取内容，先用一个 delegate_task 做分析（只分析不写入）：

```
delegate_task(goal="分析4本参考教材中第X章相关内容，给出内容摘要/写作手法/盲区",
              toolsets=["terminal","file"])
```

### 第2步：并行分节创作

将章节按节号分组，3路并行 delegate_task：

| 路 | 内容 | 目标大小 |
|:--|:-----|:--------|
| Part1 | §X.1 + §X.2 | 15~25KB |
| Part2 | §X.3 + §X.4 | 15~20KB |
| Part3 | §X.5 | 15~25KB |

每路 context 必须包含：
- 写作大纲中对应节的完整写作指南（必含要素/设问过渡/案例建议）
- 参考教材路径（子代理会自己读取）
- 格式规范（公式/Mermaid/表格写法）
- 输出路径（如 `第X章_part1.md`）
- **不要带章首导读和章末总结** — 这些由组装脚本统一处理

关键：Part1 输出要包含 `# 第X章 标题` + `## 内容导读` + 学习目标。Part2/Part3 只需从 `## X.3` 或 `## X.5` 开始。

```
delegate_task(tasks=[
  {goal: "创作第X章§X.1+§X.2的正文", context: "...", toolsets: [...]},
  {goal: "创作第X章§X.3+§X.4的正文", context: "...", toolsets: [...]},
  {goal: "创作第X章§X.5的正文",      context: "...", toolsets: [...]},
])
```

### 第3步：组装

用 Python 脚本组装三部分：

```python
import os

base = '/path/to/project/output'

# 1. 读取三部分 — 注意：必须用原生 open()，不能用 execute_code 中的 read_file
#    （read_file 从 hermes_tools 返回 '123|content' 格式，会污染行内容）
with open(f'{base}/第X章_part1.md', 'r') as f:
    p1 = f.readlines()
with open(f'{base}/第X章_part2.md', 'r') as f:
    p2 = f.readlines()
with open(f'{base}/第X章_part3.md', 'r') as f:
    p3 = f.readlines()

# 2. 找到 Part2 正文起始行（跳过 "# 第X章 ...（续）" 等多余标题）
p2_start = 0
for i, line in enumerate(p2):
    if line.strip().startswith('## X.3'):  # 该部分第一个 ## 节标题
        p2_start = i
        break
# Part3 同理（如果以 ## X.5 直接开始则 p3_start = 0）
p3_start = 0
for i, line in enumerate(p3):
    if line.strip().startswith('## X.5'):
        p3_start = i
        break

# 3. 拼接（Part1 完整保留，Part2/Part3 从节标题开始）
combined = p1 + ['\n'] + p2[p2_start:] + ['\n'] + p3[p3_start:]

# 4. 写入临时文件
with open(f'{base}/第X章_combined.md', 'w') as f:
    f.writelines(combined)

size = os.path.getsize(f'{base}/第X章_combined.md')
print(f"组合后: {size:,} bytes, {len(combined)} 行")
```

### 第4步：追加章末板块

在组装文件末尾追加：
- `## 本章总结` — Mermaid 知识结构图 + 核心要点表（8~12条）
- `## 习题` — 基础题 + 进阶题 + 思考题（8~12题）
- `## 参考文献` — ≥12篇
- `## 深入阅读` — 3~6本

```python
with open('第X章_combined.md', 'r') as f:
    content = f.read()

ending = """
---

## 本章总结
...（从写作大纲章末板块复制）...
"""

with open('第X章-标题.md', 'w') as f:
    f.write(content + ending)
```

### 第5步：修复公式编号 + 质量审计

```bash
python3 scripts/batch_fix_formula_numbers.py output/第X章-标题.md
python3 scripts/quality_audit.py --project . --chapter X
```

### 第6步：清理临时文件

```bash
rm output/第X章_part*.md output/第X章_combined.md
```

## 常见问题

### Part2 带多余标题

Part2 子代理可能输出 `# 第X章 电磁兼容概述（续）` 等多余标题。组装时需通过搜索第一个 `## X.Y` 标记跳过。

### 公式编号冲突

三路并行各自独立编号，必然冲突。`batch_fix_formula_numbers.py` 会在组装后统一按顺序重编号。

### 单行 `$$...$$` 缺少 \tag

Part 中常见行内 `$$10\lg(4/3)=1.25\mathrm{dB}$$` 被 `quality_audit.py` 计为公式但无 \tag。修复：转为行内 `$10\lg(4/3)\approx1.25\,\mathrm{dB}$`——这类小计算不需要独立编号。

### 章内交叉引用脱节

三路并行时 Part2 不知道 Part3 的表号/图号。解决办法：组装后运行一次全文搜索，检查 "表X-X" / "图X-X" 引用一致性。如有冲突，用 patch 修复。
