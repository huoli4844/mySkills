# 知识链接审计设计（替代 KGraph）

## 背景

原知识图谱模块 (kb_graph.py + kb_graph_builder.py + kb_graph_query.py = 1551 行) 使用 SQLite 图数据库存储节点和边，提供：

- 孤立节点检测（入度=0）
- 反向链接补全（A→B 但 B↛A）
- 跨章引用统计
- 图质量检查（路径完整性、桥接缺口等）

**问题**：该模块从未被 pipeline 自动化调用（`pipeline_full_check` 被定义但从未执行），SQLite 数据库未构建。且图结构不提供语义判断——只能做入度/连通性计数，而这通过纯文本 `[[wikilink]]` 扫描即可实现。

## 替代方案：link_audit.py

| 维度 | KGraph（废弃） | link_audit（v52.0） |
|:-----|:--------------|:-------------------|
| 行数 | 1551 | 266 |
| 存储 | SQLite | 无（纯内存） |
| 维护成本 | 增量更新、DB 一致性 | 无 |
| 速度 | 慢（SQL + 构建索引） | 快（单次文件扫描） |
| pipeline 集成 | 从未接入 | scene→l2_indices 自动运行 |

## 核心函数

- `check_orphan_nodes(wiki_root)` — 入度=0 节点检测
- `check_backlink_symmetry(wiki_root)` — A→B 但 B↛A 检测
- `check_cross_chapter_links(wiki_root)` — 跨章引用 → L2 枢纽节点
- `auto_fix_backlinks(wiki_root)` — 自动补全反向链接
- `run_link_audit(wiki_root, auto_fix=True)` — 统一入口

## 集成点

`dag_pipeline_run.py` 中 `pipeline_auto()` 的 scene 阶段验证通过后自动调用 `run_link_audit(wiki_root, auto_fix=True)`。replace KGraph 在 `pipeline_full_check()` step 13 中的调用。
