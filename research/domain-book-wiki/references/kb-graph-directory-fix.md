# kb_graph 目录结构硬编码修正 (v43.13)

## 问题

`kb_graph.py` 的 `build()` 方法始终返回 0 nodes，导致 `generate_index_data.py` 回退到文件扫描模式，L2 索引 JSON 只有 2 个条目（chapter_num=0），book_overview 全为零。

## 根因（3 处硬编码不匹配）

### 1. `_book_dirs()` — 书籍目录发现

**原代码**：
```python
lib = os.path.join(self.wiki_root, "01_领域", "01_资料库")
return sorted(os.path.join(lib, d) for d in os.listdir(lib) ...)
```

**实际目录结构**：
```
电磁领域知识库/
├── .dag/kb_graph.db
└── 电磁兼容领域/
    ├── 领域总控/
    └── 0001_电磁兼容基础教材/
        ├── 10_总揽/
        ├── 30_核心概念/
        └── ...
```

没有 `01_领域/01_资料库/` 中间层 → `_book_dirs()` 返回 `[]` → 无书籍目录 → build() 无节点。

**修复**：自适应扫描 wiki_root 下所有非隐藏子目录，在每个领域目录下找书籍子目录。

### 2. `_type_dir_map()` — 目录号错位

| 原代码期望 | 真实目录 |
|:-----------|:--------|
| `30_知识要素` | **40_知识要素** |
| `40_知识点` | **50_知识点** |
| `50_技能点` | **60_技能点** |
| `60_应用场景` | **70_应用场景** |
| `70_实体` | **80_实体** |

六处全错，导致所有 KE/KP/SP/Scene/Entity 节点都被映射到错误的类型。

### 3. `_get_kg_data()` — 节点 ID 前缀不匹配

**原因**：`KGraph.build()` 构建的节点 ID 格式为 `{domain}/{book_id}/{dir}/{name}`：
```
电磁兼容领域/0001_电磁兼容基础教材/30_核心概念/电磁兼容三要素
```

**原查询**：
```sql
WHERE n.id LIKE '0001_电磁兼容基础教材/%'
```
前缀不含领域名 → 匹配 0 条。

**修复**：
```sql
WHERE n.id LIKE '%/' || '0001_电磁兼容基础教材' || '/%'
```

## 补丁文件（5 个）

| 文件 | 修改 |
|:-----|:-----|
| `kb_graph.py:159-175` | `_book_dirs()` 自适应扫描 |
| `kb_graph.py:166-180` | `_type_dir_map()` 编号对齐 |
| `graph_analytics.py:554-562` | `_get_kg_data()` LIKE 模式 |
| `pipeline_auto.py:56-68` | 无习题自动 done/0 |
| `dag_state.py:304-319` | `_save_state` 阶段一致性检查 |

## 验证

```bash
python3 -c "
from kb_graph import KGraph
kg = KGraph('/path/to/wiki_root')
kg.build()
import sqlite3
conn = sqlite3.connect(kg.db_path)
conn.row_factory = sqlite3.Row
print(conn.execute('SELECT COUNT(*) as n FROM nodes').fetchone()['n'])
"
# 应输出 > 0（本库 347 nodes, 1814 edges）
```
