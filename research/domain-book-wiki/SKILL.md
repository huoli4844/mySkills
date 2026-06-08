---
name: domain-book-wiki
template_version: v2.0
domain: research
description: 知识库构建编排系统 — 正文→Agent写YAML(受pydantic保护)→schema校验→模板渲染输出。领域无关、书籍无关。
version: v2.0
triggers:
  - "生成知识库"
  - "domain-wiki"
  - "知识库构建"
  - "YAML完整性"
  - "pipeline_v2"
  - "yaml_writer"
  - "template_engine"
---

# domain-book-wiki v2.0 — 知识库构建编排系统

## 架构三域隔离

```
正文（唯一可信数据源）
    ↓ Agent 提取
YAML 数据（yaml_writer.py 写入，pydantic 校验字段名/类型/confidence）
    ↓
schemas/domain_book_schema.json（唯一字段权威源，领域无关）
    ↓
template_engine.py（纯代码渲染，从 schema 读字段映射，从模板 .md 读格式）
    ↓
.md 输出（严格按模板 .md 结构）
```

### 核心文件

| 文件 | 职责 |
|:-----|:------|
| `schemas/domain_book_schema.json` | **唯一真相源** — 8节点类型×字段名/类型/required/confidence/template映射 |
| `scripts/yaml_writer.py` | Agent写YAML工具 — 动态pydantic模型，字段名/confidence写错当场报错 |
| `scripts/template_engine.py` | 纯代码渲染引擎 — YAML→.md，从schema读映射，不硬编码字段名 |
| `scripts/pipeline_v2.py` | 两阶段编排 — Phase A(纯代码) + Phase B(Agent评估) |

### 层级结构

```
L1（逐章）: concept → ke → entity [可选: kp → sp → scene] → exercise → solution
L2（单书）: 书籍总揽（最后一章统一生成）
L3（领域）: 领域总控（最后一章统一生成）
L4（全库）: 知识库总控（最后一章统一生成）
```

## 核心工作流

### Phase A（纯代码，零Agent）

```bash
# 一步完成：校验YAML → 模板渲染
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book \
  -c 4 \
  --book-id 01_工程电磁兼容 \
  --book-name "工程电磁兼容第3版_路宏敏"
```

内部流程：
1. 检查 6 个 L1 YAML 文件是否存在（concepts.yaml / kes.yaml / entities.yaml / kps.yaml / sps.yaml / scenes.yaml）
2. 用 schema.json 校验每个YAML的字段名、类型、confidence值
3. 按 DAG 顺序逐个渲染（concept → ke → entity → kp → sp → scene）
4. exercises 自动从源文.md检测；solutions 自动生成骨架

### Phase B（Agent评估）

```bash
python3 scripts/pipeline_v2.py phase-b --book-dir /path/to/book -c 4
# 输出已有数据概况 + 建议Agent判断是否需要补充KP/SP/Scene
```

Agent 读取 Phase A 输出 → 基于已渲染的概念/KE/实体内容 → 决定是否写KP/SP/Scene的YAML → 用 `yaml_writer.py` 写入（pydantic保护字段）

## Agent 写 YAML 的正确方式

### 1. 先看骨架（不创建文件）

```bash
python3 scripts/yaml_writer.py skeleton --type concept
```

输出所有正确字段名，自动填充字段标 `# （自动填充）`。

### 2. 写 YAML（带全量校验）

```bash
python3 scripts/yaml_writer.py write \
  --type concept \
  --yaml-path .dag/第4章/data/concepts.yaml \
  --items '[
    {
      "name": "概念名",
      "file": "概念名-第4章",
      "fm": {
        "source_chapter": "4",
        "source_from": "4.1.3",
        "confidence": 0.95,
        "confidence_note": "精准释义逐字匹配出处原文"
      },
      "bd": {
        "term_english": "English Name",
        "term_definition": "定义文本...",
        ...
      }
    }
  ]'
```

**字段名写错 / confidence 超范围 / 必填字段缺失 → pydantic 当场报错，不写入。**

### 3. 校验已有 YAML

```bash
# 单文件（自动识别类型）
python3 scripts/yaml_writer.py validate --yaml-path concepts.yaml
# 显式指定类型
python3 scripts/yaml_writer.py validate --yaml-path test.yaml --type concept
# 批量校验整个章
python3 scripts/yaml_writer.py validate-dir --dir .dag/第4章/data/
```

## Confidence 速查表

所有值定义在 `schemas/domain_book_schema.json`，Agent不可修改默认值：

| 类型 | 允许值 | 含义 |
|:-----|:-------|:-----|
| concept | `[0.95]` | 精准释义逐字匹配出处 |
| ke / entity | `[0.85]` | 基于正文归纳 |
| kp | `[0.85]` | 基于正文归纳 |
| sp | `[0.75]` | 操作步骤来自原文 |
| scene / exercise | `[0.65]` | 基于教材案例 |
| solution | `[0.65, 0.85]` | 骨架0.65 / Agent填充0.85 |

## 字段管理（与旧版对比）

| 维度 | 旧版(v52.5-) | 新版(v2.0) |
|:-----|:------------|:-----------|
| 字段权威源 | schema_loader + schema.py + config.py + tac_constants.py (4处) | `schemas/domain_book_schema.json`（唯一） |
| confidence定义 | 10个文件 | 同上一处 |
| Agent写YAML | 文字提示"按以下字段写" | pydantic模型，写错0%通过 |
| 模板渲染 | build_kb_files.py（含字段校验） | template_engine.py（纯渲染，无校验） |
| 校验 | 15个validator文件(~5108行) | yaml_writer内置校验（从schema驱动） |
| 编排 | dag_controller.py（12阶段） | pipeline_v2.py（两阶段） |

## 已知陷阱

### P1. YAML `file:` 值禁止含 `/` 字符

`file: 多设备DC/DC隔离供电场景-第4章` → `/` 被OS解释为路径分隔符。
**正确**: `多设备DC_DC隔离供电场景-第4章`

### P2. 6个L1 YAML文件缺一不可

`pipeline_v2 phase-a` 执行前检查 concepts.yaml / kes.yaml / entities.yaml / kps.yaml / sps.yaml / scenes.yaml。
缺少任何一个立即拒绝。exercises.yaml 和 solutions.yaml 不在此列（自动检测/骨架回退）。

### P3. 多余字段不阻断但应清理

schema校验中"多余字段"是警告而非错误——渲染引擎只取schema中定义的字段。但遗留字段（如旧版的 `additional_explanations`、`definition_source` 等）建议清理。

## 快速调试

```bash
# 查看所有类型
python3 scripts/yaml_writer.py list

# 查看章节构建状态
python3 scripts/pipeline_v2.py status --book-dir /path/to/book -c 4

# 只渲染单个类型（不经过pipeline）
python3 scripts/template_engine.py render \
  --type concept \
  --data .dag/第4章/data/concepts.yaml \
  --output 30_核心概念 \
  --book-id 01_工程电磁兼容 \
  --book-name "工程电磁兼容第3版_路宏敏" -c 4

# 批量校验整个章的YAML
python3 scripts/yaml_writer.py validate-dir --dir .dag/第4章/data/
```

## 遗留（旧版 dag_controller.py 已弃用）

`dag_controller.py` / `dag_pipeline_run.py` / `build_kb_files.py` / `schema_loader.py` 等旧版pipeline文件保留在`scripts/`目录中供参考，但不再用于新章节构建。新构建请使用 `pipeline_v2.py` + `yaml_writer.py` + `template_engine.py`。

## 版本历史

v2.0 (2026-06-08) — 数据层重构
- `schemas/domain_book_schema.json`: 唯一字段权威源，全类型定义
- `scripts/yaml_writer.py`: Agent写YAML工具，pydantic模型动态生成
- `scripts/template_engine.py`: schema驱动的模板渲染引擎，重写
- `scripts/pipeline_v2.py`: Phase A纯代码 + Phase B Agent评估
- 废弃 dag_controller.py / build_kb_files.py / schema_loader.py 等15个validator
- 领域无关、书籍无关：换模板只需更新schema.json

v52.5 (2026-06-08) — YAML完整性闸门（历史版本，标记tag）
v52.4a — schema_loader + preflight质量门
v52.3 — 字段校验warning
v52.2 — 数据变更自动检测