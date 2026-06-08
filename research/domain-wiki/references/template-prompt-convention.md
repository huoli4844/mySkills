# @prompt 写作指导约定

## 格式

模板中每个 `{{field}}` 前面或附近必须加一行：

```markdown
<!-- @prompt 写作要求。多长、什么格式、写什么内容、示例。 -->
{{field}}
```

## 原则

1. **模板自己就是完整的指南**，不需要任何外部对照表、schema 映射文档、提示词文档。改模板就等于改了所有。
2. **`@prompt` 只写内容指导**（写什么、多长、什么格式），不写机械校验（类型/必填/confidence 等由 schema.json + yaml_writer.py 处理）。
3. **`template_engine.py` 渲染时自动剥离 `<!-- ... -->`**，零泄漏到最终输出。
4. 如果某个字段跟另一类型的同名字段要求不同（如 concept 的 `mathematical_model` 和 ke 的 `mathematical_model`），各自写各自的 `@prompt`。

## 示例

```markdown
### 2. 数学模型

<!-- @prompt 必须用$$...$$块级LaTeX包裹公式。从源文提取。无公式填"无"。每公式下方标注来源。 -->
{{mathematical_model}}

### 3. 关键参数

<!-- @prompt ≥3个关键参数。格式："参数名(符号/单位): 说明"。 -->
{{key_parameters}}
```

## Agent 使用方式

```bash
# 看某类型全部字段要求
python3 scripts/yaml_writer.py prompt --type concept

# 只看一个字段
python3 scripts/yaml_writer.py prompt --type kp --field theoretical_basis

# 输出示例：
# 📌 theoretical_basis [必填/string]
# ≥200字。从底层原理讲起。用3+个[[wikilink]]引用核心概念。
```

## 重要性排序

| 信息来源 | 优先级 | 说明 |
|----------|--------|------|
| 模板 `{{xxx}}` + `@prompt` | 最高 | 字段名和写作要求全部在这里 |
| `schema.json` | 协助 | 辅助校验（类型/必填/constraints），不参与字段名映射 |
| 其他 references | 参考 | 历史文档，不参与工具流程 |
