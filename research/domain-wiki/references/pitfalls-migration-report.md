# 陷阱迁移报告：domain-book-wiki → domain-wiki

## 已从 domain-book-wiki 迁移的陷阱修复

| 旧技能陷阱 | domain-wiki 修复 | 提交 |
|:----------|:-----------------|:----|
| A17: bare `except Exception:` 33处 | 精确异常类型 + print 错误 (11处) | 5bceed3 |
| A17: `except:` 裸捕获 | 0处 ✅ | — |
| A17: `/tmp/` 硬编码路径 | 0处 ✅ | — |
| A14: assets 路径错位 | 0处 ✅ | — |
| P29: 字段列表多源 | 模板单一权威, 0硬编码字段列表 ✅ | — |
| A19/P35: 索引空壳无检测 | graph_analytics 18项检测 ✅ | — |
| B1: 无三标准过滤 | yaml_writer.py self-instruct ✅ | — |
| B2: 公式纯文本 | 模板 @prompt 强制 $$...$$ ✅ | — |

## 从 domain-book-wiki 吸纳的设计

| 功能 | 状态 | 提交 |
|:-----|:----|:----|
| 管线预验证 (preflight) | `phase_a.py step_0_preflight()` | f305690 |
| 跨章一致性检查 | `quality_reviewer.check_cross_references()` 同名冲突+断裂wikilink | 1c52c7f |
| 概念覆盖度门 | preflight 中检查概念数 vs 源文段落数 | f305690 |

## 不吸纳的旧设计

- ❌ `dag_` 前缀过载 (9文件) — 命名混乱
- ❌ 手动 batch 模式 — 已被 `pipeline_v2.py run` 替代
- ❌ `yaml_pre_validate` 自维护字段列表 — 违反模板单一权威
- ❌ 多个 YAML 工具 — 已被 `yaml_writer` 统一
- ❌ 14个文件超600行 — 违反模块化红线
- ❌ 54个脚本 + 87 reference — 膨胀失控

## 管线修复 (2026-06-09)

| Bug | 根因 | 修复 |
|:----|:----|:-----|
| `run` 循环 | PHASE_A_STEPS 含 quality_review/auto_fix → phase_a()吃掉不保存状态 | 移出PHASE_A_STEPS |
| `set_status` 静默忽略 | 旧状态文件缺 quality_review 字段 | 自动创建缺失phase |
| `auto_fix` / `l4_indices` 死循环 | 设成 pending 而非 done | 设 done + state.save |
| state 跨 phase_a 变脏 | cmd_run 对象不刷新 | 重载 ChapterState |
| `split_book_to_chapters.py` 丢章节 | 正则 `.` 不匹配 `#第N章`(无标题) | `.*` + CHAPTER_BARE_PATTERN |

## 命名红线检查

| 文件 | 改前行数 | 当前行数 | 状态 |
|:-----|:-------:|:--------:|:----|
| kg_builder.py | 677 | 526 ✅ | 删5个未用方法 |
| pipeline_v2.py | 661 | 512 ✅ | phase_a()拆出到phase_a.py |
| 其余17个脚本 | <500 | <500 ✅ | — |
