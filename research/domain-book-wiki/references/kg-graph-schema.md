# 知识图谱 Schema 设计 (kb_graph.py)

## 三表结构

### nodes — 节点表

只存 frontmatter 元数据，不存 .md 文件全文。

| 列 | 类型 | 说明 |
|:---|:-----|:------|
| id | TEXT PK | 节点标识（如 `01_电磁兼容基础/30_核心概念/传导耦合`） |
| type | TEXT | concept / knowledge-element / knowledge / skill / scenario / entity / exercise / solution / index |
| name | TEXT | frontmatter 的 name |
| book_id | TEXT | 01_电磁兼容基础 |
| chapter_num | TEXT | 章节号 |
| confidence | REAL | 0.65 ~ 0.95 |
| source_chapter | TEXT | frontmatter 的 source_chapter |
| summary | TEXT | body 前 200 字摘要 |
| mtime | REAL | 文件修改时间（增量更新用） |
| file_path | TEXT | 磁盘路径 |

### edges — 边表

| 列 | 类型 | 说明 |
|:---|:-----|:------|
| source_id | TEXT | 源节点 ID (FK → nodes.id) |
| target_id | TEXT | 目标节点 ID (FK → nodes.id) |
| rel_type | TEXT | 关系类型 |
| section | TEXT | 来源节标题 |

索引：idx_edges_source, idx_edges_target

### nodes_fts — FTS5 全文搜索虚拟表

搜索使用 LIKE 匹配（对中文分词更可靠），FTS5 保留作为备选。

## 12 类关系推断规则

| 节标题（子串匹配） | rel_type |
|:-----------------|:---------|
| 核心概念图谱 / 工作原理/构成要素 | **PART_OF** |
| 技术分类 | **PART_OF** |
| 应用场景 / 应用方法/步骤 | **APPLIES_TO** |
| 适配场景 / 支撑的场景 | **APPLIES_TO** |
| 支撑知识点 / 支撑技能点 | **APPLIES_TO** |
| 前置知识点 / 前置技能 | **PREREQUISITE_OF** |
| 相近概念辨析 / 易混淆辨析 | **CONTRASTS_WITH** |
| 发展/演进 / 发展演进 | **EVOLVED_FROM** |
| 常见误区 / 操作边界 / 边界条件 | **LIMITED_BY** |
| 使用到的知识要素 | **RELATED_TO** |
| 关联概念 / 关联知识要素 / 关联知识点 | **RELATED_TO** |
| 关联习题 / 关联习题解答 | **ANSWERS** |

## 节点 ID 格式

```
书籍内文件：    {book_id}/{dir}/{name}
索引文件：      {wiki_root_relative_path}
习题/解答：     {book_id}/{dir}/{name}
```

## 路径标准化

三种格式统一处理：
- `30_核心概念/传导耦合`（短路径 → 补书籍前缀）
- `01_电磁兼容基础/30_核心概念/传导耦合`（直接匹配）
- `01_领域/01_资料库/01_电磁兼容基础/30_核心概念/传导耦合`（裁剪前缀）

## 全量重建成本

294 文件, ~2MB: real 0.57s, user 0.18s, sys 0.27s
