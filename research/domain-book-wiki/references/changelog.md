# Changelog

## v50.0 (2026-06-05) — 驾驭工程全面修复

### P0: Schema 统一
- `dag_constants.py` 新增 `REQUIRED_BD_FIELDS` 集中化必填字段定义（8 类型）
- `build_kb_files.py` 删除本地 `_REQUIRED_BD_FIELDS`，改为从 `dag_constants` 导入
- `yaml_pre_validate.py.check_required_fields()` 通过 `_TYPE_TO_BD_KEY` 映射消费同一 schema
- **效果**: 第 6 章从 255 假阳性降至 57 真实内容缺口；第 4 章 459→61；全部章节错误可追踪到具体 `bd.field`

### P1-1: 错误处理统一
- 26 处裸 `except Exception:` 全部改为 `except Exception as e: log.warning/debug(...)`（16 个文件）
- 零残留裸 except

### P1-2: content_check_rules.py 拆分
- 1327 行 → 291 行入口 + `rules/`（`bloom.py` 121 / `wikilink.py` 69 / `formula.py` 105 / `size.py` 252 / `diagram.py` 296）
- 所有函数签名不变，外部调用方无需修改

### P1-3: SKILL.md 精简
- 470 行 → 69 行；移除全部 v45-v49 版本历史块
- 保留：When to Use → Design → Quickstart → Key Commands(5) → Pitfalls(5+链接) → Reference Index(8)

### P2: 删除死代码
- 删除 6 个 `build_*.py` 薄包装器（`build_concepts/kes/kps/sps/entities/scenes.py`，各 31 行）
- 0 处外部引用，纯死代码

### 新增陷阱
- P30: delegate_task 子代理未写文件
- P31: 子代理格式不一致

## v49.1 (2026-06-05)
- yaml_pre_validate: check_required_fields 兼容新旧格式
- build_kb_files: 新增 _format_list_to_numbered() 修复学习目标渲染
- entity_type/domain/classification 仅 entity 类型填写
- BOOK_NAME 自动从 book_overview 读取
- 知识库 129 个 .md 清理无意义 frontmatter 字段
- 第 6 章假阳性从 255→0（当时 schema 未统一，仅做兼容处理）

## v49.0 (2026-06-04)
- 驾驭工程四件套: yaml_pre_validate / build staging / quality_score / WorkspacePaths
- preflight.py data/ 目录检测
- YAML 统一存储于 .dag/第N章/data/

## Prior versions
See git history for v48.x and earlier.
