# Mermaid %%{init} 质量检查 (v43.18)

## 问题

Obsidian 的 Mermaid.js v10+ 对 `%%{init}` 格式严格，Typora 宽松。常见错误：

| 错误 | Obsidian 报错 | 示例 |
|:-----|:-----|:-----|
| 单引号 JSON | `No diagram type` | `%%{init: {'theme': 'base'}}` |
| 缺 `}%%` 闭合 | `No diagram type` | `%%{init: {"theme": "base"}}}` |

正确格式：
```
%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}%%
```

## 检测 (content_check_rules.py)

`check_mermaid_quality()` 新增 FAIL 级检查：
1. 单引号 JSON → FAIL: "Mermaid %%{init} 使用单引号JSON"
2. 缺 `}%%` 闭合 → FAIL: "Mermaid %%{init} 缺末尾 }}%% 闭合"

## 自动修复 (validate_mermaid_syntax.py)

`scan_file()` 自动替换：
1. 单引号 `{'theme': 'base'...}` → `{"theme": "base"...}`
2. 双引号但缺 `}%%` → 追加 `}%%`

## 预防 (template_assembler_core.py)

`_normalize_block()` 强制替换旧 `%%{init}` 为 `MERMAID_INIT` 常量，确保所有生成文件使用正确格式。

## 三层联动

```
生成时: _normalize_block → 强制正确 init
检查时: content_check → FAIL 如有残留
运行: validate_mermaid_syntax → auto-fix
```
