# 知识图谱故障诊断与修复指南 (kg-troubleshooting.md)

本指南覆盖 `kb_graph.py` 构建/验证全周期的常见问题根因分析和修复步骤。

## 验证流水线

```bash
# Step 1: 建图
python3 scripts/kb_graph.py <wiki_root> build

# Step 2: 验证
python3 scripts/kb_graph.py <wiki_root> validate

# 或通过 pipeline
dag_controller.py pipeline validate   # [11/11] 自动调用
```

## 死链接分类与根因

### A 类：短名 wikilink 死链（~87%）

**现象**：
```
❌ 01_电磁兼容基础/30_知识要素/传导耦合机理 → 耦合途径 (RELATED_TO) 目标不存在
```

**根因**：文件中的 `[[耦合途径]]` 无路径前缀。`kb_graph.py` 边提取逻辑遇到无 `/` 的 wikilink 时不添加 book_id 前缀。节点 ID 是 `01_电磁兼容基础/30_核心概念/耦合途径`，但边 target 是纯 `耦合途径`。

**修复**：在 `_process_file()` wikilink 归一化后增加 `name_to_id` 查表分支（见 pitfalls #26）。

**验证**：重建图谱后 `grep -c "dead_link"` 应显示 0（短名死链接全部消失）。

---

### B 类：book_overview 路径死链（~13%）

**现象**：
```
❌ 01_电磁兼容基础/30_核心概念/传导耦合 → 01_电磁兼容基础/10_总揽/book_overview_01_电磁兼容基础_0 目标不存在
```

**根因**：`10_总揽/` 目录下缺少 book_overview 等 L2 索引文件。**或** `01_资料库/` 前缀未归一化（见下方细分）。

**B1 子类：文件缺失**
- 运行 `generate_index_data.py + index-assembler.py` 生成 L2 索引
- 5 个文件：`book_overview`, `concept_index`, `knowledge_index`, `skill_index`, `scenario_index`

**B2 子类：前缀未归一化**
- `[[01_资料库/01_电磁兼容基础/10_总揽/book_overview_01_电磁兼容基础_0]]` 使用了 `01_资料库/` 而非 `01_领域/01_资料库/`
- `_full_target()` 和 `_process_file()` 中需同时处理两种前缀（见 pitfalls #27）

---

### C 类：真实断链（罕见，~0%）

**现象**：wikilink 指向确实不存在的文件名或拼写错误。

**根因**：手动编写 wikilink 时的拼写错误或文件名变更未同步。

**排查**：
```bash
sqlite3 .dag/kb_graph.db "SELECT source_id, target_id, rel_type FROM edges e
  LEFT JOIN nodes n ON e.target_id = n.id WHERE n.id IS NULL;"
```

---

## 诊断工具箱

### 1. 查看原始 edges

```python
import sqlite3
db = sqlite3.connect("<wiki_root>/.dag/kb_graph.db")
# 所有 dead_link
dead = db.execute("""
  SELECT e.source_id, e.target_id, e.rel_type FROM edges e
  LEFT JOIN nodes n ON e.target_id = n.id WHERE n.id IS NULL
""").fetchall()
# 按 target 分组统计
from collections import Counter
print(Counter(d[1] for d in dead).most_common(10))
```

### 2. 查看 name_to_id 映射覆盖范围

```bash
sqlite3 .dag/kb_graph.db "SELECT name, id FROM nodes WHERE type NOT IN ('exercise','index') ORDER BY name;"
```

### 3. 查看特定节点的所有边

```bash
sqlite3 .dag/kb_graph.db "SELECT source_id, rel_type, target_id FROM edges WHERE source_id LIKE '%耦合途径%' OR target_id LIKE '%耦合途径%';"
```

### 4. 检查 wikilink 原文

```bash
grep -o '\[\[[^]]*\]\]' 源文件.md | sort -u
```

---

## 修复后验证清单

### 快速验证（修复后立即执行）

```bash
# 1. 建图谱
python3 scripts/kb_graph.py <wiki_root> build

# 2. 验证图谱完整性
python3 scripts/kb_graph.py <wiki_root> validate

# 3. 内容深度检查
python3 scripts/comprehensive-content-check.py <book_root>

# 4. 全量 pipeline 验证（含所有 11 项检查）
dag_controller.py pipeline validate
```

### 验证通过标准

| 检查 | 通过条件 |
|:-----|:---------|
| `kg validate` | 0 dead_link, 0 error |
| `comprehensive-content-check` | 0 FAIL |
| `pipeline validate [04/11]` | 习题-解答 1:1（无 missing） |
| `pipeline validate [08/11]` | L1-L4 层级审核通过 |
| `pipeline done {phase}` | 不被回退为 `blocked` |

### 清单

1. ✅ `kb_graph.py <wiki_root> build` → nodes/edges 数量合理
2. ✅ `kb_graph.py <wiki_root> validate` → 0 dead_link
3. ✅ `comprehensive-content-check.py <book_root>` → 0 FAIL 0 WARN
4. ✅ L2 索引文件在 `10_总揽/` 中存在 (5 个)
5. ✅ 图谱支持 query/search/trace/impact 四方法
6. ✅ `pipeline done` 不被回退为 blocked


---

## 详细案例：228 死链分析（原 kg-deadlink-resolution.md）


# 知识图谱死链分析与修复模式

## 症状

`kb_graph.py validate` 报告大量 `dead_link`（实测 228 个）。

## 死链分类与根因

| 分类 | 数量 | 占比 | 根因 |
|:-----|:----:|:----:|:-----|
| 短名 wikilink 解析失败 | 199 | 87% | `[[耦合途径]]` → 纯名称，无路径前缀 → 边目标为 `"耦合途径"`，节点 ID 为 `"01_电磁兼容基础/30_核心概念/耦合途径"` |
| book_overview 前缀未归一化 + 文件缺失 | 29 | 13% | wikilink 用 `01_资料库/` 前缀，归一化只处理 `01_领域/01_资料库/`，且 `10_总揽/` 目录为空（L2 索引未建） |

## 根因代码分析

### kb_graph.py `_process_file()` — 边提取 (行 718-739)

```python
full_target = target  # "耦合途径" ← 纯名称，无 "/"
if full_target.startswith("01_领域/01_资料库/"):
    full_target = full_target[len("01_领域/01_资料库/"):]  # 纯名称不匹配
if book_dir and "/" in full_target and not full_target.startswith("01_"):
    # ⚠️ "耦合途径" 没有 "/" → 此分支永远不进
    bname = os.path.basename(book_dir)
    full_target = f"{bname}/{full_target}"
# 结果: target = "耦合途径" → nodes 表中不存在 → dead_link
```

**关键问题**：`"/" in full_target` 过滤了所有纯名称 wikilink。`name_to_id` 表在 `build()` 入口的 `_build_name_to_id_pre()` 已预构建并传入 `_process_file()`，但 wikilink 解析代码未使用它。

### \_full_target() (行 315-324)

```python
if t.startswith("01_领域/01_资料库/"):
    t = t[len("01_领域/01_资料库/"):]  # 只处理这个前缀
# ⚠️ 漏掉了裸 01_资料库/ 前缀（不带 01_领域/）
```

实际 wikilink 内容：`[[01_资料库/01_电磁兼容基础/10_总揽/...]]` → 此分支不匹配 → 保留为 `01_资料库/01_电磁兼容基础/...`

## 修复方案

### Fix 1: 短名 wikilink → name_to_id 查表

在 `_process_file()` 的边提取循环中，对无 `/` 的 wikilink 用 `name_to_id` 查表：

```python
for target in wikilinks:
    full_target = target
    if "/" not in full_target:
        # 短名 wikilink（如 [[耦合途径]]）→ 查 name_to_id 预扫表
        resolved = name_to_id.get(full_target)
        if resolved:
            full_target = resolved
            # 已正确解析，跳过后续归一化
        else:
            # 查不到则保留原值，validate 会报告为真 dead_link
            continue
    else:
        # 有路径的 wikilink → 原有归一化逻辑
        if full_target.startswith("01_领域/01_资料库/"):
            full_target = full_target[len("01_领域/01_资料库/"):]
        elif full_target.startswith("01_资料库/"):
            full_target = full_target[len("01_资料库/"):]
        if book_dir and not full_target.startswith("01_"):
            bname = os.path.basename(book_dir)
            full_target = f"{bname}/{full_target}"
```

**前提**：`name_to_id` 参数已在 `_process_file(fpath, node_type, book_dir, nodes, edges, name_to_id)` 传入（行 349）。
**数据来源**：`_build_name_to_id_pre()` 在 `build()` 行 337 预扫所有 `.md` 文件的 frontmatter → `{name: node_id}`。

### Fix 2: `01_资料库/` 前缀归一化

在 `_full_target()` 中增加分支：

```python
if t.startswith("01_领域/01_资料库/"):
    t = t[len("01_领域/01_资料库/"):]
elif t.startswith("01_资料库/"):
    t = t[len("01_资料库/"):]  # ← 新增：裸前缀归一化
```

## 验证步骤

```bash
python3 scripts/kb_graph.py <wiki_root> build
python3 scripts/kb_graph.py <wiki_root> validate
```

修复后预期：
- 短名死链：199 → **0** ✅（所有短名通过 name_to_id 查表成功解析）
- book_overview 死链：29 → 29（仍需 L2 索引文件，这是真正的 dead_link）

## 实际修复结果

### Phase 1 修复后（仅代码修复 + rename，不含 L2 索引）
```bash
$ python3 kb_graph.py <wiki_root> validate
❌ [dead_link] ... book_overview_01_电磁兼容基础_0 目标不存在
# 短名死链：199 → 0 ✅ 全部消失
# book_overview 死链：29（索引文件不存在）
# 总计: 100 个问题（全部为 book_overview 死链 + 非 error 级别的 info/warn）
```

### Phase 2 修复后（生成 L2 索引 + 重建图谱）
```bash
$ python3 kb_graph.py <wiki_root> build   # nodes: 100, edges: 380
$ python3 kb_graph.py <wiki_root> validate
# 0 dead_link ✅ 从 228 降至 0
# 剩余: 8 个 confidence_gap (warn) + 5 个 overloaded (info) — 非 error，正常
# 总计: 13 个问题（全部为 info/warn 级别）
```

## 可复用经验

1. **短名 wikilink 必须查 name_to_id 表**：
   - `[[概念名]]` 是无路径前缀的纯名称
   - 图构建时必须通过 `name_to_id` 预扫描映射表解析
   - 这是 87% 死链的根因（199/228）

2. **路径前缀归一化要覆盖所有变体**：
   - wikilink 中可能使用 `01_资料库/`（无 `01_领域/` 前缀）
   - 归一化必须同时处理 `01_领域/01_资料库/` 和 `01_资料库/`

3. **name_to_id 预扫描必须在 build() 入口处**：
   - `_build_name_to_id_pre()` 在主循环前扫描所有 .md
   - 结果传入 `_process_file()` → 同时服务于 COMPOSED_OF、TESTS、wikilink 三种解析

4. **book_overview 死链有两重原因**：
   - 一是路径前缀归一化缺失（可修复）
   - 二是 L2 索引文件本身不存在（需 `index-assembler.py` 生成）
   - 先做归一化修复，等索引文件生成后重建图谱即可清除

5. **pipeline validate [11/11] 已集成 graph validate**：
   - `dag_controller.py` 行 1250-1269 自动调用 `kg.validate()`
   - 计数 `severity == 'error'` 级别问题
   - 非误报 — 无需额外集成
