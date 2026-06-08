# L2 学习路径数据流

从"Bloom 层级标注"到"L2 总揽的可视化学习路径"的完整数据链。

## 数据流总览

```
Agent 写 KP/SP YAML  →   build_kb_files.py  →   KG 数据库  →   generate_index_data.py  →   index-assembler.py  →   book_overview.md
  bloom_level: 应用         FM 写入 .md         nodes 表      §9 算法读取                 {{learning_path_v2}}      渲染
```

## 关键链路节点

### 1. 数据源：KP/SP YAML 中的 `bloom_level`

每个 KP/SP YAML 的 `fm` 段必须有：

```yaml
- name: 某知识点
  bd:
    bloom_level: "应用"
    # ...
```

LM 值域（`generate_index_data.py` 第 308 行）：
- `记忆` → score 0
- `理解` → score 1 (默认值，空值也落在此)
- `应用` → score 2
- `分析` → score 3
- `评价` → score 4
- `创造` → score 5

**注意**：concepts.yaml 没有 bloom_level，不能触发学习路径算法。

### 2. KG 数据库

`build_kb_files.py` 构建 `.md` 文件时，`kb_graph.py` 会在其 `_process_file()` 中提取 FM 的 `bloom_level` 字段写入 `nodes` 表。

**数据库列必须存在**。v36.0 新增，旧数据库需重建：

```bash
python3 scripts/kb_graph.py <wiki_root> build
```

重建后验证：

```bash
sqlite3 .dag/kg_graph.db "SELECT name, bloom_level, type FROM nodes WHERE type IN ('knowledge','skill') AND bloom_level != '' LIMIT 10;"
```

如果返回为空 → 问题出在数据源（YAML 没填 bloom_level）或数据库 schema（列不存在）。

### 3. `generate_index_data.py` 的 §9 算法

文件位置：`scripts/generate_index_data.py` 第 279-457 行

算法步骤：
1. 查 KG nodes 表：`SELECT name, chapter_num, bloom_level, difficulty FROM nodes WHERE type='knowledge' ORDER BY chapter_num`
2. 查 edges 表的 `PREREQUISITE_OF` 关系
3. 如果 `kps` 不为空 → 生成四段内容：
   - §9a: Bloom 层级分布表（各 Bloom 层级知识点数 + 占比 + 条形图）
   - §9b: 按章推荐路径（章内按 Bloom 层级排序的知识点 wikilink 列表）
   - §9c: 前置依赖链分析（PREREQUISITE_OF 关系图谱）
   - §9d: 推荐学习轨道（基础夯实 → 应用实践 → 深度学习 → 技能导向）
4. 如果 `kps` 为空 → `result["learning_path_v2"]` 保持默认值 `"（待补充）"`

**这是最常见的失败模式**：第 N 章还没有任何 KP 节点被 build 进 KG 数据库。

### 4. `index-assembler.py` 的模板填充

文件位置：`scripts/index-assembler.py` 第 389 行

```python
"learning_path_v2": data.get('learning_path_v2', '（待补充）'),
```

直接透传 `generate_index_data.py` 的 result 值。

### 5. 模板渲染

模板 `assets/templates/book_overview.md` 第 52 行：

```markdown
## 🎯 动态学习路径（Bloom 认知层级 + 前置依赖）
{{learning_path_v2}}
```

## 故障排查矩阵

| 症状 | 可能原因 | 排查命令 / 步骤 |
|:-----|:----------|:----------------|
| `（待补充）` | 该章无 KP 数据 | `pipeline status --chapter N` 查看 kp phase |
| `（待补充）` | KG 数据库未重建 | `sqlite3 .dag/kg_graph.db "PRAGMA table_info(nodes)"` 检查有无 `bloom_level` 列 |
| `（异常）` 含 traceback | §9 算法抛异常 | 查看 `generate_index_data.py` 第 455-457 行的 except 捕获 |
| Bloom 分布表全为 0 | bloom_level 全是空字符串 | `grep "bloom_level: " 40_知识点/第N章*.md \| sort \| uniq -c` |
| 只有分布表无推荐路径 | PREREQUISITE_OF 边为空 | `sqlite3 .dag/kg_graph.db "SELECT COUNT(*) FROM edges WHERE rel_type='PREREQUISITE_OF'"` |

## 快速修复命令

```bash
# 1. 重建 KG 数据库
python3 scripts/kb_graph.py /Users/huoli4844/Desktop/测试-全书/电磁兼容基础 build

# 2. 重新生成索引数据
python3 scripts/generate_index_data.py --book-dir /Users/huoli4844/Desktop/测试-全书/电磁兼容基础

# 3. 重建 L2 总揽
python3 scripts/build_kb_files.py --type concept --book-id 电磁兼容基础

# 4. 验证
grep "动态学习路径" 10_总揽/book_overview_电磁兼容基础_0.md
```
