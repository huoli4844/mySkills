# Mermaid 兼容性指南

## 核心原则

教材中的 Mermaid 图需在尽可能多的渲染器中正常显示。以下规则基于实战验证总结。

**最可靠的图类型：`graph LR` / `graph TD`**，节点数 ≤10/块。

## ✅ 可用语法

| 语法 | 说明 | 示例 |
|:-----|:-----|:-----|
| `graph TD` / `graph LR` | 最稳定，所有渲染器支持 | `graph TD\nA[节点] --> B[节点]` |
| `A["标签文字"]` | 节点标签用方括号+双引号 | `A["频率响应分析"]` |
| `A[("标签")]` | 圆边节点，引号先闭括号后闭 | `A[("关键节点")]` |
| `A -.-> B` | 虚线箭头 | `A -.-> B` |
| `A -->|"标签"| B` | 带标签箭头 | `A -->|"大于3GHz"| B` |
| `subgraph "标题"` / `end` | 子图分组 | subgraph 标题无括号/破折号 |

## ❌ 禁止语法

| 语法 | 风险 | 替代方案 |
|:-----|:-----|:---------|
| `timeline` | Mermaid v10.2+ 才支持 | `graph LR` 横向时间线 |
| `mindmap` | 部分渲染器不支持 | `graph TD` 树形结构 |
| `%%{init: ...}%%` | 部分渲染器不支持 | 不使用，接受默认主题（白底黑字） |
| `<-->` 双向箭头 | 部分渲染器不支持 | 两条单向箭头 `A --> B; B --> A` |
| subgraph 内 **`direction`** | 已知渲染 bug | 移除 direction，或用多个独立 graph 块 |
| `---config---` 语法 | 仅在 Mermaid v10+ 支持 | 改用 `%%{init}` 或直接不用 |
| `xychart-beta` 多系列 | Obsidian 中不渲染 | 多个独立的 `graph LR` 块 |

## 致命规则（不遵守 = 图不渲染）

### 1. 禁止 emoji
永远不要在节点标签中使用 Unicode emoji：`✅❌⚠️🔽⭐🔄🚫📋` → 改为纯文字"达标/不达标/注意/下降"。

### 2. 圆边节点括号顺序
`[("标签")]` ✅ — `"` 先闭，`)` 后闭  
`[("标签)"]` ❌ — `)` 被吞入标签字符串，圆括号缺闭合

### 3. subgraph 标题
标题中不要含括号 `()`、破折号 `—`、逗号 `,` → 引发 Lexical error。拆为多个 `graph LR` 块代替。

### 4. 标签含括号/逗号必须加引号
`A["label(text, with comma)"]` ✅  
`A[label(text, with comma)]` ❌

### 5. 节点数 ≤30
超过 30 节点导致白屏。超过 10 节点建议拆分。

## 快速排查表

| 现象 | 根因 | 修复 |
|:-----|:-----|:-----|
| 白屏/空白 | emoji 或 xychart-beta | 删 emoji，换 graph LR |
| `Lexical error` | subgraph 标题含括号 | 移除特殊字符 |
| `undefined class` | `:::classname` 无 `classDef` | 添加 `classDef` |
| 渲染不全/太小 | 无 `useMaxWidth` | 加 `%%{init: {"flowchart": {"useMaxWidth": false}}}%%` |
| 乱码/位移 | 引号不配对 | 检查 `"` 数量为偶数 |
| 节点标签缺失 | `("text)"]` 括号顺序 | 改为 `("text")]` |

## 验证命令

```bash
# 自动检查
python3 scripts/quality_audit.py --project /path/to/教材

# 手动查 emoji
grep -n '🔄\|⚠️\|🚫\|📋\|⭐' output/第*.md
```
