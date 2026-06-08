# Mermaid 嵌套 Fence Bug — 根因分析 + 修复方案

**发现**: v43.8 (2026-06-01)
**修复**: v43.11（嵌套 fence）+ v43.11-maint（`%%` 闭合）
**影响**: YAML 数据含 Mermaid fences 的所有生成文件

## 症状

生成文件的 Mermaid 代码块出现双层包裹：

```markdown
```mermaid
%%{init: ...}

```mermaid
%%{init: ...}
graph LR
    A --> B
```
```> **解析文字**
```

- 两层 `%%{init}` 配置
- 嵌套 ` ```mermaid ` fences
- 错误闭合 ` ```> `（` ``` ` 后紧跟 markdown 内容）

## 根因

`template_assembler_core.py` `_wrap_mermaid_fields` 顺序缺陷：

1. Step 1: `re.sub` 匹配已包裹块 → `_wrap_block` 归一化（inside: strip + add init + re-wrap）
2. Step 2: `re.sub` 匹配裸露 `graph`/`flowchart` 行 → `_wrap_unwrapped` 包裹

Bug: Step 2 的 regex `(?<!```)\n(graph ...)` 用负向 lookbehind 检查 `\n` 前是否紧跟 ` ``` `。但 Step 1 已在 `graph` 前插入 `%%{init}` 行，lookbehind 通过 → `graph` 被二次包裹。

## 修复 (v43.11)

**区域保护模式** — 三阶段:

1. **保护**: 提取所有 ` ```mermaid...``` ` 块 → 替换为占位符 `__MERMAID_PN__`
2. **包裹**: 仅对非 Mermaid 区域匹配裸露 `graph`/`flowchart` 行
3. **归一化**: 恢复占位符 → strip old fences → add `%%{init}` → re-wrap

## Obsidian Mermaid 兼容：完整链条

`MERMAID_INIT` 常量配置 Mermaid 主题。Obsidian 的 Mermaid.js v10+ 比 Typora 严格得多，经三次迭代才发现完整要求：

```python
# ❌ v43.10 — 单引号 JSON，Typora OK / Obsidian 静默不渲染
MERMAID_INIT = "%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '12px'}}}"

# ❌ v43.11 — 双引号但缺 %% 闭合，Obsidian 报 "No diagram type detected matching given configuration for text:"
MERMAID_INIT = '%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}'

# ✅ v43.11-maint — 双引号 JSON + }%% 闭合（两个条件缺一不可）
MERMAID_INIT = '%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}%%'
```

**诊断口诀**：「Typora 能看、Obsidian 不能看」时：
- 先查 `%%{init` 是否双引号 JSON（`"theme"` 非 `'theme'`）
- 再查末尾是否 `}%%` 闭合（`}}}%%` 非 `}}}`）

## 质量闸门

| 层 | 文件 | 检测 |
|:---|:-----|:-----|
| 生成前 | `template_assembler_core.py` | 区域保护从源头杜绝嵌套 fence |
| 生成前 | `template_assembler_core.py` | MERMAID_INIT 常量双引号 + `%%` 闭合 |
| 生成后 | `content_check_rules.py:check_mermaid_quality` | fence 深度计数 → FAIL |
| 运行时 | `validate_mermaid_syntax.py:scan_file` | 嵌套 fence → ERROR |
