# .md.md 双后缀问题 — 根因分析 & 修复指令

## 问题现象

渲染后 6 种非习题类型（concept/ke/entity/kp/sp/scene）的文件名出现 `.md.md` 双后缀：

```
30_核心概念/第1章 绪论.md.md     ← 应为 第1章 绪论.md
40_知识要素/第1章 绪论.md.md
50_知识点/第1章 绪论.md.md
60_技能点/第3章 屏蔽.md.md
70_应用场景/第4章 滤波.md.md
80_实体/第5章 接地及搭接.md.md
```

本次扫描发现 **24 个文件**受影响（第1/3/4/5章的 6 种类型各 4 章）。

## 根因链条（两环级联）

### 第一环：Agent 写 YAML 时 `file` 字段误含 `.md`

YAML 数据结构要求 `{name, file, fm, bd}`，其中 `file` 是输出文件名的基础（不含后缀）。但 Agent 将 `source_from`（章节源文件名，如 `第3章 屏蔽.md`）直接复制到了 `file` 字段：

```yaml
# ❌ 错误写法 — file 含 .md 后缀
- name: 屏蔽体设计方法
  file: 第3章 屏蔽.md      # ← 含 .md
  fm:
    source_from: 第3章 屏蔽.md

# ✅ 正确写法 — file 不含 .md
- name: 屏蔽体设计方法
  file: 屏蔽体设计方法      # ← 无 .md，或用节点名
```

**为什么概念类型有时没问题？** 第3章 concepts 的 Agent 将 `file` 设为概念名（`屏蔽原理`），而第1章 concepts 和所有 sp/kp/ke/entity/scene 的 Agent 将 `file` 设为章节源文件名。行为不一致原因是 **self-instruct 未指导 `file` 字段**。

### 第二环：`get_output_filename()` 无条件追加 `.md`

```python
# template_engine.py:get_output_filename()
def get_output_filename(item, type_name, chapter_num):
    if type_name in EXERCISE_FILENAME_MAP:
        return EXERCISE_FILENAME_MAP[type_name](item, chapter_num)
    file_base = item.get('file', item.get('name', 'unnamed'))
    return f"{file_base}.md"    # ← 如果 file_base 已含 .md → .md.md
```

### 第三环：quality_reviewer.py 同病

```python
# quality_reviewer.py:90
file_path = os.path.join(rendered_dir, f"{item.get('file', name)}.md")
```

导致质量审查去查 `xxx.md.md`，但实际文件是 `xxx.md`，所有双后缀文件从未被质量门检出。

## 修复指令

### Fix 1: `template_engine.py:get_output_filename()`

在 `return f"{file_base}.md"` 前增加防御性 strip：

```python
# 防御性去除已有 .md 后缀
if file_base.endswith('.md'):
    file_base = file_base[:-3]
return f"{file_base}.md"
```

### Fix 2: `quality_reviewer.py:90`

同样 strip 处理：

```python
file_base = item.get('file', name)
if file_base.endswith('.md'):
    file_base = file_base[:-3]
file_path = os.path.join(rendered_dir, f"{file_base}.md")
```

### Fix 3: `yaml_writer.py:cmd_self_instruct()`

在输出开头增加 `file` 字段说明（在 `## 一、源文章节结构` 之前）：

```python
lines.append("⚠️ 顶层 `file` 字段规则：不含 `.md` 后缀。设为该节点的名称（如概念名/技能点名/知识点名），不要设章节文件名。`source_from` 已承载源文件信息。")
```

### Fix 4: Phase A 渲染后审计

在 pipeline_v2.py 的 phase-a 渲染步骤（Step 3 或之后）增加：

```bash
# 检查是否有 .md.md 双后缀文件
find "$output_base" -name "*.md.md" -type f | tee -a "$report"
if [ -n "$(find "$output_base" -name "*.md.md" -type f)" ]; then
    echo "⚠️ 发现 .md.md 双后缀文件，需要排除"
fi
```

## 验证

修复后对受影响章节重新 Phase A 渲染，确认：

```bash
find "$BOOK_DIR" -name "*.md.md" -type f
# 预期: 0 结果
```
