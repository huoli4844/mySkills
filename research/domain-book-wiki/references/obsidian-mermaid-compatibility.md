# Obsidian Mermaid 渲染兼容性规则

## 核心原则

**永远以 Obsidian 的 Mermaid.js v10+ 为最低兼容目标。** Typora 渲染正常的图不一定在 Obsidian 中正常。

## 兼容性检查清单

### 1. `%%{init}` 格式（双层要求）
```
✅ 正确：%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}%%
❌ 错误：%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '12px'}}}   (单引号 JSON)
❌ 错误：%%{init: {"theme": "base", "themeVariables": {"fontSize": "12px"}}}    (缺 }%% 闭合)
```
- JSON 必须双引号（`"` 非 `'`）
- 末尾必须有 `}%%` 闭合指令

### 2. 图规模限制
| 指标 | 安全上限 | 风险边界 |
|:-----|:------|:------|
| 节点数 | <50 | 50-100 可能卡顿，>100 大概率崩溃 |
| 边数 | <40 | 40-80 可能渲染慢 |
| 总行数 | <100 | >150 行开始不稳定 |
| Emoji | 0（禁止） | 1-2 个可能 OK，大量必然崩溃 |

### 3. 节点名/标签安全规则
- 节点 ID：使用 `_mermaid_safe()` 清洗，只保留字母/数字/CJK/下划线
- 标签内：`"` 替换为 `'`，Emoji 全部移除
- 禁止字符：`()[]{}|:;#<>` 以及任何 Emoji

```python
def _mermaid_safe(name):
    """将名称转为 Mermaid 安全标识符，非字母/数字/CJK → _"""
    safe = ""
    for c in name:
        if c.isalnum() or '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' or c == '_':
            safe += c
        elif c in ' \t-':
            safe += '_'
    return safe or "node"
```

### 3b. 连通节点策略（避免 169 节点过载）
画全量节点会导致 Obsidian 渲染崩溃。采用「只画有边节点」策略：
1. 先查 TOP N 高连接度边 → 收集有边节点名
2. 只为这些节点渲染 → 大幅减少图规模
3. 边数控制在 40-50 条，节点数控制在 30-50 个

### 4. mindmap 类型特殊限制
`mindmap` 图类型要求**严格单根**——所有节点必须是唯一根节点的子孙。多根（如多个 `第N章` 平级）会导致 `There can be only one root` 错误。

```mermaid
✅ 正确：mindmap\n  根节点\n    子节点1\n    子节点2
❌ 错误：mindmap\n  节点A\n  节点B      (两个根)
```

### 5. Markdown 表格内 wikilink 转义
Markdown 表格中 `|` 被解析为列分隔符。两种解决方案：

**方案 A（推荐）：去掉 `|display` 部分**，只用路径：
```markdown
| 链接 |
|:-----|
| [[../30_核心概念/PCB电磁兼容设计方法]] |   ← ✅ 无管道符，无转义问题
```

**方案 B：转义管道符**（Obsidian 部分版本不支持）：
```markdown
| [[路径/文件\|显示名]] |   ← ⚠️ 转义可能不生效
```

**相对路径优先**：book_overview 在 `10_总揽/`，用 `../30_核心概念/` 等相对路径。避免嵌套全路径中的额外斜杠/管道符。

### 6. 边查询防污染
边查询必须排除 `index`/`solution`/`exercise` 类型节点，否则 `资料总揽` 等节点会吸走所有 TOP N 边名额：
```sql
AND n1.type NOT IN ('index', 'solution', 'exercise')
AND n2.type NOT IN ('index', 'solution', 'exercise')
ORDER BY degree DESC LIMIT 50
```

## 实战案例

### 案例 1：169 节点 / 60 边 / 169 Emoji → 崩溃
- 症状：Obsidian 渲染空白或 "Parse error"
- 根因：节点过多 + Emoji 过多
- 修复：去 Emoji → 只画有边节点 → 缩减到 26 节点 / 30 边 → 正常

### 案例 2：`No diagram type detected matching given configuration`
- 症状：Obsidian 报此错误但 Typora 正常
- 根因：`%%{init}` 末尾缺 `}%%` 或 单引号 JSON
- 修复：检查 `}%%` 闭合 + 双引号 JSON

### 案例 3：空 Mermaid 块
- 症状：Obsidian 显示 "No diagram type detected" 且块内无内容
- 根因：模板 ` ```mermaid\n{{empty_field}}\n``` ` + 值空
- 修复：`build_book_overview` 后处理检测并替换为占位文本

## 验证方法

```python
# 检查 Emoji
emoji_count = sum(1 for c in mermaid_block if ord(c) > 127 and not (0x4e00 <= ord(c) <= 0x9fff))
assert emoji_count == 0, f"Found {emoji_count} emoji characters"

# 检查 %%{init} 格式
assert '\\'theme\\': \\' not in block, "Single quotes in init JSON"
assert block.count('}}}%%') == block.count('%%{init'), "Missing }%% closing"

# 检查图规模
nodes = block.count('["')
assert nodes < 100, f"Too many nodes: {nodes}"
lines = len(block.split('\n'))
assert lines < 200, f"Too many lines: {lines}"
```
