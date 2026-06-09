# 批量章节处理工作流（20章全自动）

> 适用于 10-20 章的整书全自动管线处理。
> 核心模式：`delegate_task (写YAML) → pipeline_v2.py run (全自动14阶段)` 逐章循环。

## 流程

```
for each chapter (1..20):
  ① yaml_writer.py build-prompt --type TYPE -c N  → 获取含@prompt的Agent提示词
  ② delegate_task: 提示词+源文 → 写8YAML → validate → 通过
       ↓
  ③ pipeline_v2.py run: 14阶段全自动
       ↓
  完成后: quality-gate → build-indices → review
```

## 关键：使用 @prompt 原料构建 Agent 提示词

模板中的 `<!-- @prompt ... -->` 是写作指导的**原料**，不是可以直接给 Agent 的指令。
写 YAML 前必须先加工成结构化提示词：

```bash
# Step A: 获取逐字段写作要求
yaml_writer.py build-prompt --type concept -c N
# 输出:
#   ## 写作总则 — LaTeX/Mermaid/wikilink格式约束
#   ## 逐字段写作要求 — @prompt + FIELD_DEPTH字数阈值
#   ## 输出格式 — YAML模板
#   ## 质量检查 — validate命令

# Step B: 将 build-prompt 的输出直接注入 delegate_task context
#         作为 Agent 的写作指引

# 备选（更详细的源文上下文）:
yaml_writer.py self-instruct --type concept -c N --book-dir /path
```

**不要**只给子代理 `yaml_writer.py skeleton` 的输出——skeleton 只展示字段名，不含任何写作指导、字数约束、格式要求。

**正确做法**：`build-prompt` 的输出直接放在 delegate_task context 的 `写作指引` 章节。

## delegate_task 写入YAML的关键约束

| 约束 | 说明 |
|:-----|:------|
| fm 必填字段 | `source_chapter`, `source_from`, `confidence_note` |
| confidence 值 | concept=0.95, ke/entity/kp=0.85, sp=0.75, scene/exercise/solution=0.65 |
| 校验方法 | 每文件写完 `yaml_writer.py validate --yaml-path $FILE --type TYPE` |
| 最低数量 | concept≥3, ke≥2, entity≥1, kp≥1, sp≥1, scene≥1, exercise≥2, solution≥2 |
| exercise 文件名 | `name` 字段别含 `/` → `sanitize_filename` 转 `-` |
| 写作指引 | 必须先用 `build-prompt` 获取 @prompt 约束，注入 delegate context |

## 已知问题

- 大章 delegate_task 可能超时(600s) → 重试
- 子代理可能不验证就返回 → context 末尾写明"验证→修复→通过后返回"
- 失败重跑前清状态：`rm -f .dag/BOOK_ID_chN.json`
- **子代理写 YAML 时必须拿到 @prompt 指引，否则内容质量差** → context 中必须包含 `build-prompt` 的输出
