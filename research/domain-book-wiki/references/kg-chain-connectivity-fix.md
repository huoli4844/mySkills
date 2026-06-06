# v43.15 KG 知识链连通率四层修复

## 背景

book_overview 中知识链连通率显示四层链路全部有问题：
- knowledge-element→knowledge: 0%
- knowledge→skill: 26.3%
- skill→scenario: 23.1%
- concept→knowledge-element: 94.9%

## 根因分层

### 层 1：SQL 方向 bug（造成 0% 假象）
`graph_quality.py` 孤儿KE 检查 SQL:
```sql
AND e.target_id IN (SELECT id FROM nodes WHERE type='knowledge')
```
只查 `target_id`，漏了 KP→KE 边（source=KP, target=KE）。
同样 `graph_analytics.py` 链连通率 SQL 也只查 `e.target_id=nt.id`。
**修复**: 同时检查 `e.source_id` 和 `e.target_id`。

### 层 2：bd_extra_keys_from_item_bd 空数组
`dag_constants.py` KP 的 `bd_extra_keys_from_item_bd` 为空 `[]`，
`related_knowledge_elements` 永不被传入模板 → KE wikilink 不渲染 → KG 无边。
SP 的 `supported_scenarios` 同病。
**修复**: 添加 `["related_knowledge_elements", "supported_skills_scenarios"]` 到 KP，`["related_knowledge_elements", "supported_scenarios"]` 到 SP。

### 层 3：YAML wikilink 指向不存在文件（造成 空心概念）
concept YAML 的 `related_knowledge_elements: '[[SAR比吸收率]] [[HEMP核电磁脉冲]]'`
这些 wikilink 指向的文件从未创建 → KG 无边 → 空心概念。
**修复**: 替换为实际存在的 KE wikilink（如 `[[电磁环境]]`）。

### 层 4：KP→SP、SP→Scene 跨类型引用缺失
KP 的 `supported_skills_scenarios` 和 SP 的 `supported_scenarios` 字段
在 YAML 中有值但因层 2 的 bug 未传入模板，且部分 YAML 本身未填写。
**修复**: 手工匹配 14 个 KP→SP 和 3 个 SP→Scene 的 wikilink 引用。

## 修复后指标
| 链路 | 修复前 | 修复后 |
|:-----|:------|:------|
| concept→knowledge-element | 94.9% | 100% |
| knowledge-element→knowledge | 0% | 100% |
| knowledge→skill | 26.3% | 100% |
| skill→scenario | 23.1% | 100% |
| 空心概念 | 9 | 0 |
| 孤儿KE | 53 | 0 |
| 🔴 Critical | 62 | 0 |

## 验证命令
```bash
$PYTHON -c "
from kb_graph import KGraph
kg = KGraph('/path/to/wiki_root')
r = kg.check_graph_quality()
print(f'Critical: {r[\"summary\"][\"critical\"]}')  # 应为 0
hollow = [i for i in r['issues'] if i['category']=='空心概念']
orphan = [i for i in r['issues'] if i['category']=='孤儿KE']
print(f'Hollow: {len(hollow)}, Orphan: {len(orphan)}')  # 均应为 0
"
```
