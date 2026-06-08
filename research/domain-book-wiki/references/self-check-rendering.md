# self_check_questions 渲染格式 (v46.1)

## YAML 存储格式

`concepts.yaml` 的 `bd.self_check_questions` 支持两种格式：

### 格式1：结构化列表（推荐）

```yaml
self_check_questions:
  - question: "电磁干扰源按来源分为哪两大类？"
    answer: "内部干扰源和外部干扰源"
  - question: "宽带干扰源和窄带干扰源的区分标准？"
    answer: "干扰信号带宽与敏感器带宽的比较"
```

### 格式2：纯文本字符串

```yaml
self_check_questions: "1. 电磁干扰源按来源分为哪两大类？（提示：...）\n2. 宽带干扰源..."
```

## 渲染规则

`build_kb_files.py` 的 `_format_self_check_questions()` 自动处理：

| YAML 输入 | MD 输出 |
|-----------|---------|
| `[{question, answer}]` | `1. question（提示：answer）` |
| `[{question, hint}]` | `1. question（提示：hint）` |
| `[{q, a}]` | `1. q（提示：a）` |
| `"1. xxx\n2. xxx"` | 原样透传 |
| Python repr 字符串 | yaml.safe_load 解析后按 list 处理 |
| `"无"` | `无` |

## 代码位置

- 格式化函数：`build_kb_files.py` `_format_self_check_questions()`（L253-285）
- 调用位置：`build_type()` L409-411（bd 组装完成后、fm 构建前）
- 模板占位符：`concept_template.md` `{{self_check_questions}}`

## 常见问题

**Q: 渲染出来是 `[{'question': '...', 'answer': '...'}]` Python repr？**  
A: 说明 `_format_self_check_questions` 未生效。检查 build_kb_files.py L409-411 是否包含调用。

**Q: 想让学生先思考再看答案，如何隐藏提示？**  
A: 当前渲染为 `（提示：答案）` 内联格式。如需可折叠答案，需要模板层支持 `<details>` 标签——暂未实现。
