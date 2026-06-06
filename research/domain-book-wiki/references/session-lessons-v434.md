# v43.4 会话教训 — 知识库构建过程中的关键发现

## 1. YAML 数据在 `.dag/` 内的风险

**问题**：6 个 YAML 数据文件（concepts.yaml, kes.yaml, entities.yaml, kps.yaml, sps.yaml, scenes.yaml）存放在 `.dag/第N章/data/` 下。`pipeline init` 和 `rollback` 操作会清空 `.dag/` 目录，导致 Agent 辛苦撰写的 YAML 数据全部丢失。

**Workaround**：每次 `pipeline init` 或 `rollback` 后，必须重新检查 `.dag/第N章/data/` 下的 YAML 文件是否存在。如果丢失，需要重新写入。

**长期方向**：YAML 数据应与 pipeline 状态分离——数据是用户资产，状态是 pipeline 内部管理数据。

## 2. `definition_sentence` 必须是源文精确子串

**问题**：`verify-source` 检查要求 `definition_sentence` 的前 80 字符必须在 `20_正文/` 源文件中作为**连续子串**存在。标点符号、空格、逗号周期都不能有偏差。

**典型错误**：
- 源文：`两大类，分别列于表1-1和表1-2。`
- 错误写法：`两大类。`（把逗号改成了句号）

**修复**：用 `read_file(offset=line, limit=N)` 读取源文的精确文本，逐字复制到 `definition_sentence` 中。

## 3. Agent 对 KP/SP/Scene 的判断失误

**问题**：Agent 在第 1 章构建时自行判断"概述章内容较浅"而跳过了 KP/SP/Scene YAML 的创建。用户明确指出这是 pipeline 不该中断的流程——**Agent 必须为每一章创建全部 6 个 YAML 文件**，是否产生实际 MD 文件由 `build_kb_files.py` 根据数据内容决定，不由 Agent 预判。

**规则**：每章必须创建 concepts.yaml + kes.yaml + entities.yaml + kps.yaml + sps.yaml + scenes.yaml，无一例外。

## 4. pipeline auto 不可中断

**问题**：pipeline auto 运行时 Agent 停下来问"要继续推进 KP/SP/Scene 吗？"。用户明确要求全自动。

**规则**：一次写完所有 YAML → 直接 `pipeline auto` → 允许跑到尾。如果 exercises 检测不到（概述章无习题），在 auto 结束后用 `pipeline done exercises/solutions` 跳过。不要在 auto 中间中断。

## 5. 各类型 confidence 值速记

| 类型 | confidence | 说明 |
|:-----|:---------:|:-----|
| concept | **0.95** | 核心概念 |
| ke | **0.85** | 知识要素 |
| entity | **0.85** | 实体 |
| kp | **0.85** | 知识点 |
| sp | **0.75** | 技能点 |
| scene | **0.65** | 应用场景 |

写错 confidence 值 → FM 校验阻断，build 输出 0 文件。

## 6. `file` 字段不加 `.md` 后缀

builder 自动追加 `.md`。如果在 YAML 中写 `file: "电磁兼容三要素.md"`，最终生成 `电磁兼容三要素.md.md`。

## 7. KE 的 `definition` 双字段要求

schema.py 有别名映射 `"definition" → "term_definition"`。写 KE YAML 时，bd 必须**同时包含** `definition` 和 `term_definition` 两个字段（值相同），否则 schema 校验报 `Required bd key 'definition' is missing`。

## 8. Bloom 字段必须存在于 YAML 中

KP/SP/Scene YAML 必须包含：`bloom_level`（在 fm 中）、`bloom_level_description`、`bloom_progression`、`bloom_progression_analysis`、`bloom_alignment`（在 bd 中）。`bloom_level` 通过 `bd_extra_keys_from_item_fm` 从 fm 注入 bd。模板中的 `{{bloom_level}}` 变量从 bd 读取。
