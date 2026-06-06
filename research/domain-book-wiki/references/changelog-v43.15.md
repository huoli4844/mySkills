# v43.15 (2026-06-02)

**类型**: 架构简化 — L2/L3/L4 三索引入 overview 单文件

### 前情
v43.15 初始只对 L2 做了融合（book_overview 含 4 类索引），L3/L4 仍生成独立的 concept_index/knowledge_index/skill_index/scenario_index 文件。用户要求三层层级统一。

### 变更

| 文件 | 变更 |
|:-----|:-----|
| `assets/templates/domain_overview.md` | 新增 `## 📑 领域索引导航` 节（4 个 {{index}} 占位符） |
| `assets/templates/kb_overview.md` | 新增 `## 📑 全库索引导航` 节（4 个 {{index}} 占位符） |
| `scripts/index_assembler.py` | `build_domain_overview` / `build_kb_overview` 填充 4 个索引变量；修复 `graph_sec` dict→str 类型错误 |
| `scripts/generate_index_data.py` | `concept_items_f` 等提升到 L2/L3/L4 共享作用域；L3/L4 的 `make_index_json` 传入 4 个索引表格字符串 |
| `scripts/dag_index.py` | L3/L4 前缀改为 `["domain_overview"]` / `["kb_overview"]`；清理逻辑扩展到三层 |
| `scripts/dag_constants.py` | L3 "5 个 L3 索引文件" → "domain_overview 单文件"；L4 同理 |

### 结果
- L2 `10_总揽/`: 5 文件 → 1 文件 (`book_overview_xxx.md`)
- L3 `领域总控/`: 5 文件 → 1 文件 (`domain_overview_xxx.md`)  
- L4 `知识库总控/`: 5 文件 → 1 文件 (`kb_overview_xxx.md`)
