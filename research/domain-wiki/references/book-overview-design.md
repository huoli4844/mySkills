# book_overview 设计演进 (v43.15 → v43.17)

## v43.15: 三层索引融合

L2/L3/L4 各层级从 5 个独立文件（book_overview + 4 个 index）合并为单文件，4 类索引表内嵌。

## v43.17: Book Overview 模板精简与增强

### 模板变更

| 变更 | 旧 | 新 |
|:-----|:---|:---|
| 标题 | `# {{name}} — 资料总揽（L2）` | `# {{name}}` |
| 错题归因 | `## 📝 错题归因分析` | ❌ 删除 |
| 统计信息 | `## 📈 统计信息`（数字列表） | ❌ 删除 |
| 简介 | 空或数字罗列 | 自动生成 1000 字描述 |

### 简介自动生成逻辑

`index_assembler.py:build_book_overview()` 按以下步骤生成：

1. 扫描 `20_正文/` 获取章节文件名 → 提取章节标题
2. 从 `top_nodes` 提取核心概念排名
3. 构建结构化描述：
   - 第1段：教材概述 + 章节结构
   - 第2段：各章内容摘要（硬编码，基于教材已知章节主题）
   - 第3段：知识节点统计 + Bloom 学习链路
   - 第4段：目标读者 + 功能特点
4. 最终 ≥1000 字

### 图谱全景优化

| 问题 | 修复 |
|:-----|:-----|
| 169 节点过载 | 只画有边节点 → 26 节点 |
| Emoji 不兼容 | 去 Emoji，纯文本标签 |
| 80 条边全指向 book_overview | 过滤 index/solution/exercise 类型 |
| 特殊字符崩溃 | `_mermaid_safe()` 清洗 |

### 索引导航 wikilink 修复

| 版本 | 格式 | 问题 |
|:-----|:-----|:-----|
| v1 | `[[30_核心概念/xxx]]` | 平铺路径 Obsidian 解析失败 |
| v2 | `[[领域/书/30_核心概念/xxx]]` | 绝对嵌套路径 + 表格管道符冲突 |
| v3 | `[[../30_核心概念/xxx]]` | ✅ 相对路径，无管道符 |

### Bloom 思维导图

`mindmap` 要求单根 → 加 `📚 全书知识体系` 为根，8 章为子节点，19 个知识点为孙节点。

### 学习轨道图

新增 Mermaid `graph LR` 流程图：基础夯实 → 应用实践 → 深度学习 → 创造创新。

### 涉及文件

- `assets/templates/book_overview.md`
- `scripts/index_assembler.py` (build_book_overview)
- `scripts/generate_index_data.py` (_build_wikilink_table, _make_items)
- `scripts/graph_analytics.py` (mindmap, learning_path_v2)
- `scripts/graph_quality.py` (hollow_concept check)
- `scripts/dag_constants.py` (bd_extra_keys)
