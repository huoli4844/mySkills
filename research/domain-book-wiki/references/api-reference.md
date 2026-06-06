# API Reference — 核心模块调用关系

> v45.1 新增。从新人视角描述模块间的调用链与数据流转。

## 主调用链

```
dag_controller.py (CLI入口)
  └─ dag_pipeline.py (pipeline编排)
       ├─ pipeline_auto.py (自动推进)
       │    ├─ build_kb_files.py (构建总入口)
       │    │    ├─ build_concepts.py → template_assembler.py
       │    │    ├─ build_kes.py      → template_assembler.py
       │    │    ├─ build_entities.py  → template_assembler.py
       │    │    ├─ build_kps.py      → template_assembler.py
       │    │    ├─ build_sps.py      → template_assembler.py
       │    │    ├─ build_scenes.py   → template_assembler.py
       │    │    └─ (yaml_gen.py: 数据结构提取)
       │    ├─ comprehensive_content_check.py (质量闸门)
       │    │    └─ content_check_rules.py (检查规则集合)
       │    ├─ post_build_fix.py (自动修复)
       │    ├─ generate_index_data.py
       │    │    └─ index_assembler.py (L2/L3/L4索引)
       │    └─ phase_validator.py (阶段验证)
       ├─ dag_pipeline_ops.py (单阶段操作)
       ├─ dag_pipeline_done.py (标记阶段完成)
       └─ dag_pipeline_run.py (单独运行阶段)
```

## 核心模块 API

### dag_controller.py
CLI 入口, 解析命令行参数, 路由到 dag_pipeline。

```python
# 子命令:
pipeline init   -w WORKSPACE --book-id ID -c CHAPTER  # 初始化
pipeline auto   -w WORKSPACE --book-id ID -c CHAPTER  # 全流程
pipeline done   PHASE -w WORKSPACE --book-id ID -c CHAPTER  # 标记完成
```

### dag_pipeline.py
Pipeline 编排: 读取状态 → 检查依赖 → 调用阶段函数。

### dag_state.py
状态管理和文件工具。

```python
WorkspacePaths(wr: str)         # 集中推导所有路径
detect_layout(wr: str) -> dict  # 检测 nested/flat 布局
load_workspace_config(wr)       # 加载 .dag/config.yaml
get_wiki_root(wr: str) -> str   # 从书目录计算 KB 根
PipelineLock(wiki_root)         # 文件锁并发控制
```

### dag_constants.py
纯常量 + 类型定义, 零函数逻辑。

```python
PipelineArgs(Protocol)     # 类型协议
PipelineError(Exception)   # 统一异常类型
DIR: dict                  # 中心化路径注册表
DAG_ORDER: list            # 教学链顺序
DAG_DEPENDS: dict          # 阶段依赖关系
```

### pipeline_auto.py
自动推进主循环。检查 YAML 数据 → 调用 build → 质量检查 → 索引生成。

```python
run_pipeline_auto(wr, book_id, ch) -> bool  # 主循环
verify_exercise_solution_mapping(wr)        # 习题-解答配对验证
```

### template_assembler.py
JSON 项 → MD 文件。读取模板, 填充字段, 写入文件。

```python
assemble(template, items, output_dir) -> list[str]  # 批量生成
assemble_single(template, item, output_dir) -> str  # 单文件生成
```

### template_assembler_core.py
模板引擎核心: frontmatter 生成, {{占位符}} 替换。

```python
build_frontmatter(item, template) -> str   # 构建 YAML frontmatter
fill_template(template, item) -> str       # 填充模板
load_template(name) -> str                 # 加载模板文件
```

### yaml_gen.py
YAML 数据结构的生成和验证工具。

```python
extract(type) -> dict  # 获取字段骨架 (fm/bd 嵌套)
validate(yaml_path)    # 验证 YAML 结构
```

### comprehensive_content_check.py
全量内容质量检查 (调用 content_check_rules.py 中的规则函数)。

### dag_quality.py
DAG 流程质量检查 (L2/L3/L4 索引完整度, 链式依赖, 图连通性)。

### kb_graph.py
知识图谱 — wikilink 解析, 节点/边构建, 查询, 影响分析。

```python
KGraph(wiki_root)
  .build()           # 全量/增量构建
  .query(node)       # 查询节点
  .search(pattern)   # 搜索
  .impact(node)      # 影响分析
```

### generate_index_data.py
从已有节点文件收集数据, 生成索引 JSON, 调用 index_assembler.py。

### index_assembler.py
从 JSON 数据生成 L2/L3/L4 索引 MD 文件。

```python
build_concept_index(data)    # 概念索引
build_knowledge_index(data)  # 知识点索引
build_skill_index(data)      # 技能点索引
build_scenario_index(data)   # 场景索引
build_book_overview(data)    # 书籍总揽 (L2)
build_domain_overview(data)  # 领域总揽 (L3)
build_kb_overview(data)      # 知识库总揽 (L4)
```

## 数据流转

```
docx/pdf 源文件
  ↓ file2md
20_正文/第N章.md
  ↓ preprocess_toc.py
.dag/第N章/chapter_toc.json
  ↓ Agent (手动)
.dag/第N章/data/concepts.yaml 等
  ↓ build_kb_files.py
30_核心概念/ → 40_知识要素/ → 50_知识点/ → 60_技能点/ → 70_应用场景/
  ↓ generate_index_data.py + index_assembler.py
10_总揽/ (L2) → 领域总控/ (L3) → 知识库总控/ (L4)
  ↓ kb_graph.py
知识图谱 (.dag/graph.json)
```

## 错误处理约定

| 层级 | 方式 | 示例 |
|------|------|------|
| CLI 入口 | `sys.exit(1)` | 参数错误, 无可恢复路径 |
| Pipeline 核心 | `raise PipelineError` | 阶段失败, 状态不一致 |
| 库函数 | `raise ValueError` | 输入校验失败 |
| 工具脚本 | `return False` + `log.error` | 非致命操作失败 |

> **迁移路线 (v45.1)**: 逐步将 `sys.exit` 和 `return False` 模式迁移为 `PipelineError`。
> 当前仍有 12 个脚本使用 `sys.exit`, 核心模块 `pipeline_auto.py` 使用 `return False`。
