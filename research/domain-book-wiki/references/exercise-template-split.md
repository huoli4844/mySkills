# v43.5 习题/解答模板分离

## 问题

v43.4 之前，习题和解答共用 `eval_template.md` 模板。习题文件中包含了完整的解答骨架（核心解答、考点辨析、难点深入等节），内容全是"参见教材相关章节"和"无"，极度单薄。

## 解决方案

将模板拆分为两个独立文件：

### `exercise_template.md` — 纯习题模板

```markdown
---
template_version: v5.1
...
---
## 题目内容
{{question}}
## 关联习题解答
{{related_answer}}
## 关联目录
{{related_directory}}
```

只含题目 + 解答 wikilink + 关联目录，不含任何解答内容。

### `eval_template.md` — 完整解答模板

保留原模板的完整解答结构：
- 核心解答（实现原理 + 主要特点）
- 考点与易错点解析（核心考点 + 常见错误 + 解题技巧）
- 难点深度解析（3 个可命名的难点节）
- 可视化解题逻辑（Mermaid 流程图 + 知识闭环图）
- 关联资源（关联概念 + 引用出处 + 关联目录）

## 需修改的三处硬编码

| 文件 | 位置 | 改动 |
|:-----|:-----|:-----|
| `template_assembler.py` | ASSEMBLER_CONFIG exercise 条目第 423 行 | `"eval_template.md"` → `"exercise_template.md"` |
| `pipeline_auto.py` | `_auto_detect_and_build_exercises` 第 66 行 | `"template": "eval_template.md"` → `"exercise_template.md"` |
| `dag_constants.py` | BUILDER_CONFIG exercise 条目 | 同上 |

⚠️ 三处必须全部修改，只改一处习题仍使用旧模板。
