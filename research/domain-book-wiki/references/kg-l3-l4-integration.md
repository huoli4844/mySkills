# L3/L4 知识图谱集成（v25.3 已实现）

## 当前状态

| 层级 | 图谱集成 | 说明 |
|:----:|:--------:|:------|
| **L1** (概念/KE/KP/SP/Scene) | ✅ 完整 | 4项图谱检查（hollow/connectivity/integrity/orphan） |
| **L2** (book_overview) | ✅ 完整 | `build_book_overview()` 接 `graph_section`+`kg_stats`；LEVEL_QUALITY_CHECKS 含 graph_l2_connectivity + graph_l2_coverage |
| **L3** (domain_overview) | ✅ 完整 | `build_domain_overview()` 接 `graph_section`+`kg_stats`；LEVEL_QUALITY_CHECKS 含 graph_l3_cross_book |
| **L4** (kb_overview) | ✅ 完整 | `build_kb_overview()` 接 `graph_section`+`kg_stats`；LEVEL_QUALITY_CHECKS 含 graph_l4_complete |

## 实现架构

### 核心改动

`_build_graph_section(kg, book_id, kg_stats, like_pattern=None)` 新增 `like_pattern` 参数：

```python
# 默认（L2 单书）：like_pattern = f"{book_id}/"
# L3 跨书：like_pattern = "%"  → 全库节点
# L4 全库：like_pattern = "%"  → 全库节点
```

SQL 查询中所有 `f"{book_id}/%"` 替换为 `f"{like_pattern}%"`，L3/L4 调用时传 `like_pattern="%"`。

### 数据流

```
L3: _build_graph_section(like_pattern="%") → graph_section
    → make_index_json(..., graph_section=graph_section_l3)
    → index-assembler build_domain_overview() 填充 {{graph_section}}

L4: _build_graph_section(like_pattern="%") → graph_section
    → make_index_json(..., graph_section=graph_section_l4)
    → index-assembler build_kb_overview() 填充 {{graph_section}}
```

### 模板改动

`domain_overview.md` 和 `kb_overview.md` 各新增：
```markdown
## 知识图谱分析
{{graph_section}}
```

### L3 标题适配

L3 的 graph_section 做了 `replace()` 标题重写以适配领域语境：
- `## 📊 图连接性全景` → `## 📊 跨书图连接性全景`
- `## 🔍 图质量摘要` → `## 🔍 领域图质量摘要`
- `## 🗺 知识图谱全景` → `## 🗺 跨书知识图谱全景`

L4 同理 → 前缀改为「全库」。

### L3/L4 Builder 的 kg_stats 接入

`build_domain_overview()` / `build_kb_overview()` 从 `data` 解析：
- `data.get('kg_stats', {})` → 统计表（总节点数/平均边数/孤立节点/按章节分布/置信度分布）
- `data.get('graph_section', '')` → 完整的图分析内容块

## 质量检查

### LEVEL_QUALITY_CHECKS 新增 4 项

| check_id | 层级 | 级别 | 实现 |
|:---------|:----:|:----:|:------|
| `graph_l2_connectivity` | L2 | 🟡 warning | 扫描 L2 索引 wikilink 在图谱中是否可查 |
| `graph_l2_coverage` | L2 | 🟡 warning | L2 索引唯一点 / 全书 L1 节点 ≥ 80% |
| `graph_l3_cross_book` | L3 | 🟡 warning | 查询数据库中 edge 的 source/target 是否来自不同 book_id |
| `graph_l4_complete` | L4 | 🟡 warning | 全量 check_graph_quality() 检测空心概念 |

### dag_controller.py check_level_quality() 新增句柄

每个句柄的通用模式：

```python
elif check_id == "graph_lN_xxx":
    try:
        from kb_graph import KGraph
        wiki_root = os.path.normpath(os.path.join(wr, "..", "..", ".."))
        kg = KGraph(wiki_root)
        if os.path.exists(kg.db_path):
            kg.build()  # 确保最新
            # ... 具体检查逻辑 ...
        else:
            msg = "图谱未构建，跳过"
            result = "pass"
    except Exception as e:
        msg = f"检查异常: {e}"
        result = "pass"  # 异常不阻断
```

## 生成的 graph_section 内容板块

`_build_graph_section()` 产出 6 个板块，对 L3/L4 同样适用：

1. **图连接性全景** — 类型统计表（节点类型/数量/平均出度/平均入度）
2. **图质量摘要** — Critical/Warning/Info 计数 + 空心概念/孤儿KE/路径断裂/过载节点详情
3. **核心知识节点排名** — Top 10 按度中心性排序
4. **知识图谱全景** — Mermaid graph TB 代码块
5. **按章节图分布** — 每章概念/KE/KP/SP/Scene 矩阵表
6. **推荐学习路径** — 从 Top 3 节点出发的 trace 路径

## 边界情况

- **单书领域**: L3 `graph_l3_cross_book` 检查自动跳过（仅 1 本书，无跨书引用）
- **图谱未构建**: 所有检查 pass（不阻断）
- **kg_data 为 None**: 回退到文件扫描模式，graph_section 为空
- **Empty graph**: `_build_graph_section` 的 Mermaid 块跳过（total <= 0）
