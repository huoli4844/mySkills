# 工程化改善路线图（v51.0 提案）

综合评级 **C→B 路线图（v50.7 已部分执行）**。扩展 v50.6 审计的 P0/P1/P2 列表，补充具体数据、依赖关系和工时估算。**P0 全部已修复，P1 部分已修复**。

## 一、dag_utils 缺失修复：精确的符号映射

`dag_utils.py` 在 v42.0 被拆分为 `dag_state.py` + `dag_constants.py` 但已删除，**10 个测试文件**仍从 `dag_utils` 导入。下列映射供创建 shim 或直接更新测试使用：

| 符号 | 源文件 | 测试中引用 |
|:-----|:------|:----------|
| `DAG_ORDER`, `DIR` | `dag_constants` | `test_dag_utils`, `test_dag_pipeline`, `test_pipeline_integration`, `test_pipeline_extras`, `test_build_kb_files` |
| `_state_path`, `_load_state`, `_save_state` | `dag_state` | `test_dag_pipeline`, `test_pipeline_integration`, `test_pipeline_extras`, `test_core_modules` |
| `_phase_dir` | `dag_state` | `test_dag_quality` |
| `PipelineLock` | `dag_state` | `test_dag_pipeline` |
| `_book_name`, `extract_chapter_num`, `validate_md_file` | `dag_state` | `test_core_modules` |
| `extract_exercises_from_text`, `verify_exercise_solution_mapping` | `dag_state` | `test_comprehensive_content_check`, `test_core_modules` |
| `PipelineError` | `dag_constants` | `test_pipeline_extras` |
| `LEVEL_QUALITY_CHECKS` | **已不存在** | `test_dag_utils` — 需要确认是否可删除或从 dag_constants 补充 |
| `DAG_DEPENDS` | **已不存在** | `test_dag_utils`, `test_pipeline_integration`, `test_dag_pipeline` — 需要确认 |

**修复方案 A（推荐）**：创建 `scripts/dag_utils.py` shim，从 dag_state + dag_constants re-export 所有符号，保留旧模块名。

**✅ v50.7 已执行**：方案 A，创建 `dag_utils.py` shim，含全部 15 个符号。

## 二、27 处 sys.exit() 分布

```text
yaml_gen.py:          3 处 (572, 576, 676)
yaml_auto_fill.py:    3 处 (561, 578, 608)
dag_controller.py:    2 处 (259, 395)
yaml_pre_validate.py: 2 处 (389, 393)
validate_mermaid_syntax.py: 2 处 (469, 472)
schema.py:            3 处 (343, 362, 388)
preflight.py:         1 处 (480)
template_assembler.py:1 处 (1353)
index_assembler.py:   1 处 (760)
validate_render.py:   1 处 (377)
kb_graph.py:          1 处 (709)
preprocess_toc.py:    1 处 (533)
post_build_fix.py:    1 处 (713)
validate_thresholds.py:1 处 (243)
verify_concepts_from_source.py: 2 处 (268, 276)
---
总计: 27 处
```

全部改为 `raise PipelineError(...)`；`dag_controller.main()` 顶层 `except PipelineError: sys.exit(1)`。

## 三、mypy 配置：13 个不存在的模块

下列模块在 `pyproject.toml` `[[tool.mypy.overrides]]` 中引用但已删除：

```
build_concepts, build_entities, build_kes, build_kps, build_scenes, build_sps,
check_dir_registry, comprehensive_content_check, template_assembler_core,
test_runner, verify_completeness, verify_concepts, kb_graph_query
```

修复：删除全部 13 行。mypy 配置从 28→15 个模块，减少死配置。

**✅ v50.7 已执行**：移除全部 14 个不存在模块（含 `build_kes`），保留 37 个有效模块。

## 四、CI 空白

当前 CI（`.github/workflows/ci.yml`）只做：
- `ruff check scripts/`
- `pytest -m "not integration"`（跳过集成测试）

缺失（按优先级）：
1. **Import 烟雾测试**：`python3.12 -c "from dag_state import *; from dag_constants import *; from build_kb_files import *"` — 防止 import 退化
2. **mypy 渐进严格化**：`mypy --show-error-codes scripts/`（逐步收紧 override）
3. **覆盖率红线**：`coverage run -m pytest -m "not integration" && coverage report --fail-under=30`
4. **集成测试**：pip install pyyaml 后跑全部测试

**✅ v50.7 已执行**：CI 已增加 import 烟雾测试、mypy 类型检查、coverage（fail-under=30）。第 4 项集成测试仍跳过（依赖 pyyaml）。

## 五、批次化改善路线图（含工时估算）

### 批次一：P0 — 恢复可运行（2-4 小时） ✅ v50.7 已全部完成

| # | 动作 | 状态 |
|:-:|:-----|:----:|
| 1 | 创建 `dag_utils.py` shim | ✅ `from dag_utils import DAG_ORDER` 成功 |
| 2 | 清理 mypy 中 13 个不存在模块 | ✅ 14 个模块已移除 |
| 3 | CI 增加 import 烟雾测试 + mypy + coverage | ✅ 已在 CI 中 |
| 4 | 验证所有 21 个测试通过 | ✅ 261/261 通过 |
| 5 | 另：KGraphQueryMixin 前向引用修复 | ✅ 恢复 kb_graph_query.py 独立模块 |
| 6 | 另：12 个文件死模块 import 重定向 | ✅ template_assembler_core/dag_pipeline/comprehensive_content_check |

### 批次二：P1 — 工程加固（4-8 小时） ⚠️ v50.7 部分完成

| # | 动作 | 状态 |
|:-:|:-----|:----:|
| 5 | 27 处 `sys.exit()` → `PipelineError` | ⚠️ 部分：dag_controller 核心调用路径已修，其余 24 处在 CLI `__main__` 内 |
| 6 | `template_assembler.py` 拆为 3 文件 | ❌ 待 P2 |
| 7 | CI 启用 `mypy --strict` 渐进化 | ✅ 已添加 mypy 步骤 |
| 8 | CI 启用覆盖率报告 | ✅ coverage --fail-under=30 已启用 |

### 批次三：P2 — 架构自动化（16-24 小时）

| # | 动作 | 验收标准 |
|:-:|:-----|:---------|
| 9 | 可配置常量外移至 `configs/defaults.yaml` | DIR/NODE_CONFIG 仍为代码常量，内容阈值外移 |
| 10 | 状态文件增加 `schema_version` | `.dag/*.json` 含 `schema_version: 1` |
| 11 | `--auto-discover` 自动扫描 `20_正文/` | `pipeline batch --auto-discover` 发现全部 N 章 |
| 12 | 质量闸门自动修复循环 | `auto_fix → retry → max 3` 循环 |
| 13 | WAL 自动清理 >7 天 / >1000 条 | WAL 文件 <100KB |

### 批次四：长期优化

| # | 动作 | 依赖 |
|:-:|:-----|:-----|
| 14 | `fix-retry` 闭环 → LLM 管道自动修正 YAML | 批次三质量闸门循环稳定后 |
| 15 | WMF 公式 OCR 全量比对 | formula-extract API key 配置后 |
| 16 | 批量章并行化（`concurrent.futures`） | 批次三批次化完成 |
| 17 | WorkspacePaths 审计：消除所有手拼路径 | — |

## 六、关键依赖可视化

```text
dag_utils缺失  ─┬→ test_pipeline_integration (10 files failed)
                ├→ preflight.py (fallback 回退)
                └→ test_dag_utils.py (import 自测文件本身)

mypy死配置     → 13 个模块名无对应 .py 文件

27处sys.exit   → 异常无法被 try/except 捕获
                   └→ 模块无法被 Python 代码安全调用

CI 空白         → import 退化 / mypy 退化 / 覆盖退化 均不报警
```
