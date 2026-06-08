# v43.1 schema 别名陷阱：`definition` → `term_definition`

## 问题

`schema.py` 内置字段别名映射（第 131-140 行）：

```python
_FIELD_ALIASES = {
    "definition": "term_definition",  # ← 这里！
    ...
}
```

对 KE（kes.yaml）的影响：
1. 写入 `bd.definition: "..."` → schema 将其重命名为 `term_definition`
2. KE schema 要求 bd 必须有 `definition` 字段
3. 重命名后 `definition` 消失 → schema 报 `Required bd key 'definition' is missing`

## 修复

KE YAML 中 `bd` 需**同时提供**两个字段：

```yaml
bd:
  definition: "电磁兼容是指..."
  term_definition: "电磁兼容是指..."
```

这样 alias 不会触发（因为 `term_definition` 已存在），同时 schema 能找到 `definition`。

写 KE 的 `.yaml` 时务必记住这个双字段规则。
