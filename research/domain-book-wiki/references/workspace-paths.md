# 集中化路径管理（v43.1）

## 问题

L2/L3/L4 索引文件的目标路径原先由 `generate_index_data.py`、`build_kb_files.py`、`dag_index.py` 等多个文件独立拼接，路径推导逻辑分散且不一致。当用户自定义领域名和书籍名后，旧的 `DIR["FIELD"]`/`DIR["LIBRARY"]` 硬编码路径无法适配。

## 解决方案：`WorkspacePaths` 类

所有路径由 `dag_state.WorkspacePaths` 统一推导。给定 book 目录（wr），自动计算：

| 属性 | 推导公式 | 示例 |
|:-----|:---------|:-----|
| `kb_root` | `wr/../..` | KB 根 |
| `domain_dir` | `wr/..` | 领域目录 |
| `domain_name` | `basename(domain_dir)` | "电磁兼容领域" |
| `book_name` | `basename(wr)` | "0001_电磁兼容基础教材" |
| `l2_dir` | `book_dir/DIR["OVERVIEW"]` | 书籍 10_总揽 |
| `l3_dir` | `domain_dir/DIR["DOMAIN_CTRL"]` | 领域 领域总控 |
| `l4_dir` | `kb_root/DIR["KB_CTRL"]` | KB 知识库总控 |
| `content_dir(phase)` | `book_dir/DIR_BY_PHASE[phase]` | 30_核心概念 等 |

## 使用方

| 文件 | 用法 |
|:-----|:-----|
| `dag_pipeline_ops.py::pipeline_init` | `wp.ensure_all()` 统一建目录 |
| `generate_index_data.py` | 推导 L2/L3/L4 输出路径 |
| `build_kb_files.py` | 推导 `related_directory` wikilink |
| 任意需要路径的地方 | `wp = WorkspacePaths(wr)` → `wp.l3_dir` 等 |
