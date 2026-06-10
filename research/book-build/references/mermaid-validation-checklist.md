# Mermaid 图质量检查清单

写作完成后，用 `quality_audit.py` 自动检查图中语法问题。以下清单供手动复核时使用。

## 通用检查

| 检查项 | 正确示例 | 错误示例 | 原因 |
|:-------|:---------|:---------|:------|
| Config 语法 | `%%{init: {"theme": "default"}}%%` | `---\nconfig:\n  theme: default\n---` | `---config---` 仅在 Mermaid v10+ 支持，多数渲染器（如 GitHub）不支持 |
| Round node 括号顺序 | `[("双低阻抗<br>R_S低 R_L低")]` | `[("双低阻抗<br>R_S低 R_L低)"]` | `)"` 使 `)` 被吞入标签字符串，圆括号 `()` 无闭合符号 |
| 引号配对 | `["标签文字"]` | 行内有奇数个 `"` | Mermaid 解析器无法确定字符串边界 |

## graph / flowchart 检查

| 检查项 | 正确 | 错误 |
|:-------|:-----|:-----|
| subgraph 标题 | `subgraph "标题名称"` | `subgraph 标题(名称)` — 括号引发 Lexical error |
| Edge label | `-->|"标签"|` | `-->|标签|` — 标签需用引号包裹 |

## timeline 检查

| 检查项 | 正确 | 错误 |
|:-------|:-----|:-----|
| 内容中的书名号 | `1864 : 麦克斯韦发表电磁场的动力学理论` | `1864 : 麦克斯韦发表《电磁场的动力学理论》` — `《》` 可能导致渲染中断 |
| 标题行 | `title 发展里程碑` | 缺失 title 行 |

## mindmap 检查

| 检查项 | 说明 |
|:-------|:-----|
| 缩进层级 | 严格用空格缩进表示层级关系，2或4空格一致即可 |
| 根节点 | `root((内容))` — 必须以 `root` 作为根节点 |

## 验证方法

```bash
# 全量审计（含Mermaid检查）
python3 scripts/quality_audit.py --project /path/to/教材

# JSON 格式查看详情
python3 scripts/quality_audit.py --project /path/to/教材 --json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"第{r['chapter']}章: {r.get('mermaid_issues',[])}\") for r in d if r.get('mermaid_issues')]"
```
