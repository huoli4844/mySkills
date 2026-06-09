# Mermaid 图在教材中的使用规范

## 可读性铁律

### 禁止自动缩放
在 Mermaid 代码块第一行加初始化块：
```mermaid
%%{init: {"flowchart": {"useMaxWidth": false, "htmlLabels": true}, "theme": "neutral"}}%%
graph LR
```
`useMaxWidth: false` 阻止 Obsidian 自动缩放到不可读的尺寸。

### 布局方向
- 优先 `graph LR`（横向）而非 `graph TB`（纵向）
- 复杂图用 `flowchart` 替代 `graph`

### 节点数量与文字
| 图类型 | 最大节点数 | 每节点最多字数 |
|:-------|:---------:|:--------------:|
| 时间线 | 15 | 8 字 |
| 知识总览 | 10 | 6 字 |
| 特点图 | 8 | 12 字（2-3 行） |

### 禁止 emoji
绝对禁止在节点标签中使用 emoji。部分 Mermaid 版本渲染含 emoji 会导致节点空白或渲染失败。

### 有图必有说明
每个 Mermaid 图后紧跟 `*图 X-X：标题*`。
