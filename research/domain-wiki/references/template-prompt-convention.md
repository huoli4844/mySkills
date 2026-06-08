# 模板 @prompt 写作指导约定

## 格式

每个模板 `.md` 文件中的每个 `{{field}}` 附近，放置一条 `<!-- @prompt ... -->` 注释：

```markdown
### 数学模型

<!-- @prompt 必须用$$...$$块级LaTeX包裹公式。从源文提取。无公式填"无"。 -->
{{mathematical_model}}
```

`@prompt` 注释必须在 `{{field}}` 的 200 字符范围内（可以跨行）。注释中的内容是给 Agent 的写作指导，不是给最终用户的。

## 原则

1. **模板是字段的单一权威源**。模板有什么 `{{xxx}}`，YAML 就该有什么字段。不再维护分离的字段映射表。
2. **@prompt 只写"怎么写"，不写"是什么"**。字段名本身已经告诉 Agent 这是什么（如 `mathematical_model`）。@prompt 告诉 Agent 格式要求、字数、风格。
3. **每个必填字段至少有一个 @prompt**。可选字段可以没有。
4. **@prompt 自动剥离**。template_engine.py 的 `render_item()` 会在填充完所有 `{{xxx}}` 后执行 `re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)`，@prompt 注释不会泄露到输出文件。

## 工具

```bash
# 列出某类型全部字段的 @prompt
yaml_writer.py prompt --type concept

# 只看单个字段
yaml_writer.py prompt --type kp --field theoretical_basis
```

## 模板与字段覆盖

| 模板 | 字段数 | @prompt 数 | 覆盖率 |
|------|--------|-----------|--------|
| concept_template.md | 24 | 24 | 100% |
| ke_template.md | 12 | 13 | 100% (含自动字段) |
| entity_template.md | 12 | 12 | 100% |
| knowledge_template.md | 21 | 21 | 100% |
| skill_template.md | 23 | 23 | 100% |
| scenario_template.md | 15 | 15 | 100% |
| eval_template.md | 19 | 19 | 100% |
| exercise_template.md | 2 | 2 | 100% |
