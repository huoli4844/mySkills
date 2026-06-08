# 技能文件清理与合并审计（v50.7 执行结果）

## 实际执行结果

| 类别 | 清理前 | 清理后 | 变化 |
|:-----|:------:|:------:|::----|
| 脚本 .py | 52 | 48 | -4（删3个死文件+合并1个小文件） |
| 测试 .py | 22 | 20 | -2（合并2对测试文件） |
| 参考 .md | 83 | 76 | -7（删8个过时文档，其中1个被v50.7覆盖后重写） |
| 杂物 | 5 | 0 | -5（.DS_Store + __pycache__） |
| **合计** | **162** | **144** | **-18** |

## 删除了什么

| 文件 | 理由 |
|:-----|:------|
| `validate_chapter_data.py` | 180行，硬编码字段列表与 dag_constants.REQUIRED_BD_FIELDS 重复，被 yaml_pre_validate 完全覆盖 |
| `kb_mcp.py` | 孤立 MCP 服务器，零 import，不属于核心构建流程 |
| `generate_sidebar.py` | 孤立，零 import，功能被 dag_index 覆盖 |
| `pipeline_auto_fix.py` | 仅39行1函数，内联到 pipeline_auto.py |
| `test_kb_graph_new_methods.py` | 合并到 test_kb_graph.py |
| `test_config_extended.py` | 合并到 test_core_modules.py |
| 8个过时参考文档 | 旧会话记录/过时审计/旧归档 |
| 5个.DS_Store + 3个__pycache__ | 杂物清理 |

## 明确不合并的

| 之前考虑合并 | 结论 | 理由 |
|:-------------|:-----|:------|
| yaml_auto_gen → yaml_auto_fill | ❌ 不合并 | 签名不同，关注点不同（交互 vs 批量），合并 → God 文件 |
| yaml_gen → yaml_auto_fill | ❌ 不合并 | 职责不同，合并 → God 文件 |

## 文件清理原则

1. **真正重复的实现**才删除（validate_chapter_data 的硬编码字段列表 vs dag_constants.REQUIRED_BD_FIELDS）
2. **完全孤立的代码**才删除（零 import 且功能被覆盖的模块）
3. **极小孤文件**才内联（≤50 行、单一函数）
4. **不要为减少文件数而合并 God 文件**（合并 yaml_auto_gen(300行)+yaml_auto_fill(800行)=1100行 → 更差）
5. **提取共享工具函数**是消除重复的正确方式（而非合并整个文件）
