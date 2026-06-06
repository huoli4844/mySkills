# 技能文件清理与合并建议

> 审计时间: 2026-06-06

## 一、脚本文件（52 .py → 建议减至 47）

### 🗑️ 可删除（4 个）

| 文件 | 行数 | 理由 |
|:-----|:----:|:------|
| `validate_chapter_data.py` | 180 | 180 行中有硬编码 `REQUIRED_CONCEPT_BD_FIELDS` 列表，与 `dag_constants.REQUIRED_BD_FIELDS` 重复。功能完全被 `yaml_pre_validate.py` 覆盖。唯一引用者是 `preflight.py` 中的一次调用，可改为 `yaml_pre_validate.validate_book_chapter()`. |
| `kb_mcp.py` | ~250 | 独立 MCP 服务器（JSON-RPC stdio 协议），不属于知识库构建核心流程。应迁移到独立 MCP 技能。当前被零个脚本 import。 |
| `generate_sidebar.py` | ~150 | Obsidian _sidebar.md 生成器，未被任何脚本 import。功能单一，可并入 `dag_index.py` 或删除（索引已有生成逻辑）。 |

### 📦 可合并（6 个 → 3 个）

| 源文件 | 目标文件 | 说明 |
|:-------|:---------|:------|
| `pipeline_auto_fix.py` (39行, 1函数) | → `pipeline_auto.py` | 单函数 `_fix_solution_skeleton` 仅 39 行，直接内联到调用者。 |
| `yaml_auto_gen.py` (7函数, ~300行) | → `yaml_auto_fill.py` | 三文件 YAML 工具重叠。`yaml_auto_fill.py` 是主动维护版本，`yaml_auto_gen.py` 的 `extract_definition_sentences()` 和 `load_source_text()` 在 `yaml_auto_fill.py` 中已有重复实现。 |
| `yaml_gen.py` (12函数, ~680行) | → `yaml_auto_fill.py` | `yaml_gen.py` 的 `extract_template_vars()` / `cmd_extract()` / `cmd_match()` 与 `yaml_auto_fill.py` 的 `parse_template()` / `analyze_all_templates()` 重叠。 |

### 删除后依赖修复

| 改前 | 改后 |
|:-----|:-----|
| `preflight.py` 调用 `validate_chapter_data.validate_file()` | 改为 `yaml_pre_validate.validate_file()` |
| `validate_chapter_data.py` 中硬编码字段列表 | 统一使用 `dag_constants.REQUIRED_BD_FIELDS` |
| `pipeline_auto.py` 中 `from pipeline_auto_fix import _fix_solution_skeleton` | 函数直接移入 `pipeline_auto.py` |

---

## 二、参考文档（83 .md → 建议减至 ~35）

### 🗑️ 可删除（8 个——完全过时，无保留价值）

| 文件 | 超时原因 |
|:-----|:---------|
| `session-lessons-v434.md` | 旧会话记录，知识点已在 SKILL.md pitfalls 中固化 |
| `session-lessons-v435.md` | 同上 |
| `changelog-v43.15.md` | 旧变更日志，changelog.md 已包含后续版本 |
| `pitfalls-archive.md` | 旧陷阱归档，内容已全部移入 pitfalls.md |
| `full-automation-analysis.md` | 已被 end-to-end-pipeline.md 覆盖 |
| `engineering-audit-v50.6.md` | 已被 engineering-audit-v50.7.md 覆盖 |
| `quality-audit-v49.md` | 过时审计报告 |
| `v31-audit-findings.md` | 过时审计报告 |

### 📦 可合并到现有文档（49 个 → 合并后 ~8 个增量）

| 目标文档 | 待合并源文件 | 合并方式 |
|:---------|:-------------|:---------|
| **`pitfalls.md`** | `auto-fix-pipeline.md`, `kb-graph-directory-fix.md`, `kg-chain-connectivity-fix.md`, `mermaid-nested-fence-bug.md`, `mermaid-unicode-pitfalls.md`, `schema-alias-pitfall.md`, `v50-engineering-fixes.md` | 每条作为 pitfalls 表的新行 |
| **`yaml-structure-guide.md`** | `concept-naming-convention.md`, `confidence-levels.md`, `confidence-values.md`, `naming-convention.md`, `yaml-field-mapping.md`, `yaml-multiline-escaping.md` | 作为新节追加 |
| **`chapter-data-generation.md`** | `exercise-template-split.md`, `formula-extraction-guide.md`, `knowledge-element-content-spec.md`, `knowledge-template-v7-design.md`, `solution-template-v5-design.md` | 作为新节追加 |
| **`architecture-overview.md`** | `kg-field-flow.md`, `kg-graph-schema.md`, `kg-l3-l4-integration.md`, `kg-troubleshooting.md`, `workspace-paths.md` | 作为新节追加 |
| **`engineering-analysis.md`** | `concept-quality-audit-methodology.md`, `quality-audit-checklist.md`, `quality-audit-findings.md`, `quality-audit-patterns.md` | 作为附录追加 |
| **`obsidian-mermaid-compatibility.md`** | `mermaid-init-quality-check.md` | 后者内容追加到前者 |

### ❓ 保留待审（8 个——需人工判断是否仍有用）

| 文件 | 内容 | 判断依据 |
|:-----|:------|:---------|
| `book-overview-design.md` | L2 总揽设计文档 | 如果是当前实现的设计文档，保留；如果是过时方案，删除 |
| `builder-config-pattern.md` | Builder 配置模式说明 | 如果代码已实现，内容可归档 |
| `cleanup-after-migration.md` | 迁移后清理指南 | 如果迁移已完成，可删除 |
| `comprehensive-check-false-positives.md` | 假阳性清单 | 可合并到 pitfalls.md |
| `concept-figure-formula-audit.md` | 图/公式审计 | 可合并到 concept-formula-gate.md |
| `data-architecture.md` | 数据架构 | 可合并到 architecture-overview.md |
| `direct-assemble-pattern.md` | 直接组装模式 | 如果已标准化为 assemble_md，可删除 |
| `overview-chapter-extraction.md` | 总揽章节提取 | 可合并到 chapter-data-generation.md |

---

## 三、测试文件（22 个 → 建议减至 ~18）

| 文件 | 建议 | 理由 |
|:-----|:-----|:------|
| `test_kb_graph_new_methods.py` | 合并到 `test_kb_graph.py` | 两个测试文件测试同一模块的新旧方法，应合并 |
| `test_wikilink_resolution.py` | 合并到 `test_build_kb_files.py` | wikilink 解析是 build 的子功能 |
| `test_config_extended.py` | 合并到 `test_core_modules.py` | 配置测试是核心模块测试的子集 |
| `test_post_build_fix.py` | 保留 | 独立功能，测试修复脚本 |

---

## 四、杂物清理

| 路径 | 操作 |
|:-----|:------|
| `assets/.DS_Store` | 删除 |
| `scripts/__pycache__/` | 删除（python 自动重建） |
| `scripts/tests/__pycache__/` | 删除 |
| `references/__pycache__/` | 删除（不应在 refs 目录中） |

---

## 五、汇总效果

| 类别 | 当前 | 清理后 | 减少 |
|:-----|:----:|:------:|:----:|
| 脚本 .py | 52 | 47 | -5 |
| 参考 .md | 83 | ~35 | -48 |
| 模板 .md | 15 | 15 | 0 |
| 测试 .py | 22 | ~18 | -4 |
| 杂物文件 | 5 | 0 | -5 |
| **合计** | **177** | **~115** | **-62** |
