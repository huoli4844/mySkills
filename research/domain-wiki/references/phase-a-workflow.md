# Phase-A Pipeline 验证流程

从已有 YAML 数据运行 `pipeline_v2.py phase-a` 的经验记录。

## 已知的 schema 校验陷阱

| 问题 | 示例 | 修复 |
|------|------|------|
| `confidence` 不在允许值内 | concept 写 0.85，允许 0.95 | `item["fm"]["confidence"] = 0.95` |
| bd 字段缺失 | 模板有 `{{solved_problem}}` 但 YAML bd 无此键 | schema 会报缺失，按模板补全字段 |
| `yaml.safe_load()` 双引号内的 `\n` 被解释为字面字符 | mermaid graph 渲染为一行 | 用 `default_flow_style=False` + `allow_unicode=True` 转储 |

## pipeline_v2.py 命令

```bash
# Phase A（完整流程）：校验 → 渲染 → 质量门 → 状态持久化
python3 scripts/pipeline_v2.py phase-a \
  --book-dir /path/to/book \
  -c CHAPTER_NUM \
  --book-id 01_书ID \
  --book-name "书名"

# 断点续传（跳过已完成阶段）
python3 scripts/pipeline_v2.py phase-a ... --resume

# 自动按序处理所有待处理阶段
python3 scripts/pipeline_v2.py run \
  --book-dir /path/to/book -c N \
  --book-id 01_书ID --book-name "书名"

# 质量门（全书批检）
python3 scripts/pipeline_v2.py quality-gate --book-dir /path/to/book
```

## YAML 数据的期望路径

```
{book_dir}/.dag/第{chapter}章/data/concepts.yaml
{book_dir}/.dag/第{chapter}章/data/kes.yaml
{book_dir}/.dag/第{chapter}章/data/entities.yaml
{book_dir}/.dag/第{chapter}章/data/kps.yaml
{book_dir}/.dag/第{chapter}章/data/sps.yaml
{book_dir}/.dag/第{chapter}章/data/scenes.yaml
{book_dir}/.dag/第{chapter}章/data/exercises.yaml
{book_dir}/.dag/第{chapter}章/data/solutions.yaml
```

## 模板字段数（concept_template.md）

domain-wiki 的 concept_template.md 有 39 个 `{{xxx}}` 占位符（frontmatter 13 个 + body 26 个）。
如果 YAML bd 缺少某些字段，渲染时模板会保留 `{{xxx}}` 原文并发出 WARNING。
