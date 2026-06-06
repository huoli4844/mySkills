---
name: kb-qa
description: "知识库问答+自动补齐闭环（KBQA v3.5）：纯 Markdown 输出（无 JSON 数据块），6 Phase 闭环工作流。v3.5 引用来源表新增「章节来源」列，每个召回条目须标注出处文件和详细章节号。对 emc-textbook-wiki 知识库检索、自动补齐、审阅确认、链式补齐、纠错回写、连通验证。与 professional-textbook-compilation 形成生成→KB 双向同步。"
version: 3.5.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [knowledge-base, QA, retrieval, wiki, search, auto-complete, closed-loop]
    category: research
    related_skills: [emc-textbook-wiki, professional-textbook-compilation, llm-wiki]
---

# 知识库问答技能（KBQA v3.0 — 闭环版）

对 emc-textbook-wiki 格式的结构化知识库进行问答检索，并在问答中**自动补齐**缺失的 KB 节点。

**v3.0 核心升级——从单向操作到全闭环：**

```
v2.0:  提问 → 检索 → 合成回答 → 自动补齐 → 结束
v3.0:  提问 → 检索 → 合成回答 → 审阅确认 → 链式补齐 → 连通验证 →
       纠错回写 → 教材生成回写 → log分析 → 升级管道 → ...持续积累
```

## 何时使用

- 用户问一个关于教材内容的问题
- 在教材生成工作流中，对每个模板标题检索 KB 内容作为生成素材
- 用户发现 KB 中有不准确的内容需要纠正
- 需要进行 KB 知识网络的连通性检查和总结分析

## 前置条件

- 知识库目录符合 emc-textbook-wiki 的目录结构
- 需要有 `index.md` 和 `log.md`（自动创建）
- **用户愿意参与审阅**——v3.0 不是静默操作

---

## 完整工作流（6 Phase 闭环）

> **执行顺序约束**：Phase A→B→C→D→E→F 必须按序执行。Phase E（纠错）和 Phase F（分析）可在任意 Phase 后按需触发，但 Phase C 审阅前必须已完成 Phase B 检测，Phase D 补齐前必须已完成 Phase C 确认。

```
Phase A: 检索+回答（同 v1.0）
  → 搜索七大目录，合成带出处引用的回答

Phase B: 知识空白检测（同 v2.0）
  → 检测回答中暴露的核心术语哪些 KB 缺

Phase C: 审阅确认 ← v3.0 新增
  → 向用户列出待补齐清单
  → 用户确认/修改/拒绝
  → 含链式补齐推荐

Phase D: 执行补齐 + 连通验证 ← v3.0 增强
  → 创建页面 → 双向 wikilink → 更新 index + log
  → 连通性校验：新建页面 inbound > 0？

Phase E: 纠错回写（随时触发）← v3.0 新增
  → 用户指正错误 → 更新 KB 页面 → 更新 log

Phase F: 总结分析（定期触发）← v3.0 新增
  → 分析 log.md 的高频缺失
  → 推荐升级优先级
```

---

## Phase A：检索与回答


### 检索方法

> **搜索优先级（从高到低）**：知识点/ → 概念/ → 知识要素/ → 技能点/ → 场景/ → 习题解答/

```text

```
问题: "什么是干涉仪测向的测角模糊问题？"

Step 1: 关键词提取
  → ["干涉仪", "测角模糊", "干涉仪测向"]

Step 2: 跨目录搜索（优先级由高到低）
  ① 知识点/ → 最完整（定义+推导+例题+脉络图）
  ② 概念/ → 精准定义（confidence=0.95）
  ③ 知识要素/ → 公式/方法（confidence=0.65）
  ④ 技能点/ → 操作流程
  ⑤ 场景/ → 应用案例
  ⑥ 习题解答/ → 解题思路

Step 3: 读取匹配页面完整内容

Step 4: 合成回答
  - 概念 0.95 优先引用
  - 知识要素/知识点/技能点/场景 标注 0.65
  - **每项引用必须标注出处文件**（从页面 frontmatter 的 `sources` 字段读取，如 `出处/第3章-测向与定位技术.md`）
  - **每项引用必须标注章节来源**（从出处文件搜索确定具体节号，如 `3.3 干涉仪测向技术`、`3.3.1 干涉仪的基本原理`）

Step 5: 回答格式（含覆盖度评估）
```

### 回答格式

回答时须**完整召回所有检索到的知识库页面内容**，不得省略、摘要或自行重写。

**强制规则**：每个召回的项目必须在标题下方以 `**出处**：{source_file}` 的形式标注来源（从页面 frontmatter 的 `sources` 字段或 `出处` 字段读取）。

召回时返回该页面在知识库中的完整 markdown 内容，模板框架也一并保留。格式如下：

```
## 回答

{核心回答摘要，1-3段简要概述}

## 完整召回内容

### 1. 概念：相位干涉仪

**出处**：出处/第3章-测向与定位技术.md
**章节**：第3章 测向与定位技术 / 3.3.1 干涉仪的基本原理

相位干涉仪（别名：干涉仪）：
干涉仪是一类相位法测向设备，它通过测量位于不同波前的天线接收信号的相位差，经过处理，获取来波方向。

**本质特征**：属于相位法测向设备；通过测量天线间的相位差获取来波方向；利用不同位置天线的波前相位差异。

### 2. 知识点：干涉仪测向技术

**出处**：出处/第3章-测向与定位技术.md
**章节**：第3章 测向与定位技术 / 3.3 干涉仪测向技术

**理论基础**：干涉仪测向（相位法测向）利用信号到达两个或多个天线阵元的波程差所引起的相位差来确定信号的到达角。

**核心原理**：当平面波以角度 $\theta$ 到达间距为 $l$ 的两天线时，波程差为 $\Delta d = l \sin\theta$，对应的相位差为：
$$\varphi = \frac{2\pi l}{\lambda} \sin\theta$$

...

### 3. 知识要素：干涉仪相位差公式

$$\varphi = \frac{2\pi l}{\lambda} \sin\theta$$

公式适用于远场平面波假设。当相位差超出 $[-\pi, \pi)$ 范围时会出现测角模糊。

...

```

**章节来源确定方法**：
1. 优先读取 KB 页面 frontmatter 的 `chapter` 字段（如 `chapter: 3`），结合目录文件确定章节号（如`第3章-测向与定位技术`）
2. 然后搜索出处文件中与该节点内容最匹配的节标题（如 `3.3`、`3.3.1`、`3.3.2`），确定具体节号
3. 若无法确定具体节，至少标注章号，格式如 `第3章-测向与定位技术 / 3.3 干涉仪测向技术`
4. 对 auto-completed 节点（无出处原文），章节来源标记为 `kbqa-自动补齐`

回答末尾附上引用来源表和知识库覆盖评估：

```
## 引用来源

| 节点 | 出处文件 | 章节来源 |
|:-----|:---------|:---------|
| 概念/相位干涉仪 | [[出处/第3章-测向与定位技术.md]] | 第3章 测向与定位技术 / 3.3.1 干涉仪的基本原理 |
| 概念/相位法测向 | [[出处/第3章-测向与定位技术.md]] | 第3章 测向与定位技术 / 3.1 测向技术概述 |
| 概念/测角模糊 | [[出处/第3章-测向与定位技术.md]] | 第3章 测向与定位技术 / 3.3.2 测角模糊问题 |
| 知识点/干涉仪测向技术 | [[出处/第3章-测向与定位技术.md]] | 第3章 测向与定位技术 / 3.3 干涉仪测向技术 |

## 知识库覆盖评估

| 维度 | 状态 | 详情 |
|:----|:----|:------|
| 核心概念 | ✅ 已覆盖 | 相位干涉仪、相位法测向、测角模糊等 |
| 知识要素 | ✅ 已覆盖 | 干涉仪相位差公式、无模糊条件、鉴相器输出公式等 |
| 知识点 | ✅ 已覆盖 | 干涉仪测向技术 |
| 技能点 | ✅ 已覆盖 | 能进行干涉仪测向配置与标定 |
| 知识空白 | 无 | — |
```

> **注意**：最终回答为纯 Markdown 格式，不包含 JSON 数据块。

---

## 内部图谱数据（不输出到回答）

以下 JSON 结构和验证代码供 Agent 在内部处理知识图谱时使用，**不在最终回答中输出**。最终输出为纯 Markdown。`nodes[]` 中每个节点直接携带 `content` 字段，无需分开两份 JSON。

```json
{
  "version": "3.1.0",
  "timestamp": "2026-05-21T00:50:00+08:00",
  "topic": "干涉仪测向技术",

  "nodes": [
    {
      "id": "概念/相位干涉仪",
      "label": "相位干涉仪",
      "type": "concept",
      "confidence": 0.95,
      "verified": true,
      "status": "existing",
      "source": "出处/第3章-测向与定位技术.md",
      "section": "第3章 测向与定位技术 / 3.3.1 干涉仪的基本原理",
      "content": "相位干涉仪（干涉仪）是一类相位法测向设备..."
    },
    {
      "id": "概念/鉴相器",
      "label": "鉴相器",
      "type": "concept",
      "confidence": 0.65,
      "verified": false,
      "source": "kbqa-v3-complete",
      "section": "kbqa-自动补齐",
      "status": "auto-completed",
      "style": "dashed",
      "content": "鉴相器是测量两路信号瞬时相位差的器件..."
    }
  ],

  "links": [
    {"source": "概念/相位干涉仪", "target": "知识点/干涉仪测向技术", "relation": "理论基础"}
  ],

  "central_topic": {"id": "知识点/干涉仪测向技术", "type": "knowledge-point"},

  "gaps": [],

  "coverage": {
    "core_concepts": "covered",
    "formulas": "covered",
    "knowledge_points": "covered",
    "missing": []
  }
}
```

### 字段说明

| 字段 | 类型 | 用途 |
|:-----|:-----|:------|
| `version` | string | 技能版本号 |
| `timestamp` | string | 回答生成时间（ISO 8601） |
| `topic` | string | 核心问题术语 |
| `nodes[]` | array | 图谱节点 + 知识内容（合一） |
| `nodes[].id` | string | 节点唯一标识（`类型/名称`） |
| `nodes[].label` | string | 显示标签 |
| `nodes[].type` | string | 节点类型 `concept` / `knowledge-element` / `knowledge-point` / `skill-point` / `scenario` / `exercise` |
| `nodes[].confidence` | number | 置信度（0.65 / 0.95） |
| `nodes[].content` | string | 知识内容本体（供渲染卡片） |
| `nodes[].status` | string | `existing` / `auto-completed` / `gap` |
| `nodes[].style` | string | 可选，`dashed` 表示虚线框（auto-completed 节点） |
| `nodes[].category` | string | 可选，知识要素专有：`公式/方程` / `规则/逻辑` / `方法` 等 |
| `nodes[].source` | string | **必填**。从页面 frontmatter 获取的出处文件路径。existing 节点如 `出处/第3章-测向与定位技术.md`；auto-completed 节点标记 `kbqa-v3-complete` |
| `nodes[].section` | string | **必填**。从出处文件搜索确定的详细章节号，如 `第3章 测向与定位技术 / 3.3.1 干涉仪的基本原理`。auto-completed 节点标记 `kbqa-自动补齐` |
| `links[]` | array | 节点间关系边 |
| `links[].source` | string | 源节点 ID |
| `links[].target` | string | 目标节点 ID |
| `links[].relation` | string | 关系描述（理论支撑 / 工具 / 约束 / 方案 / ...） |
| `central_topic` | object | 核心话题节点（供图谱居中显示） |
| `gaps[]` | array | 检测到的知识空白 |
| `coverage` | object | 覆盖度分类评估 |

### JSON 图谱自校验（生成即验证）

内部 JSON 图谱数据在写入前必须通过自校验（数据用于知识空白检测和链式补齐分析）。校验规则如下：

```python
import json
from collections import Counter

def validate_graph_json(json_str: str) -> list:
    \"\"\"验证 kb-qa JSON 图谱数据的完整性和一致性。
    返回所有问题列表，空列表 = 通过。
    \"\"\"
    issues = []
    data = json.loads(json_str)

    # 1. 必需字段存在性检查
    required = ['version', 'timestamp', 'topic', 'nodes', 'links',
                'central_topic', 'gaps', 'coverage']
    for field in required:
        if field not in data:
            issues.append(f'❌ 缺少必需字段: {field}')

    if 'nodes' not in data or 'links' not in data:
        return issues  # 无法继续检查

    node_ids = {n['id'] for n in data['nodes']}
    link_sources = {l['source'] for l in data['links']}
    link_targets = {l['target'] for l in data['links']}
    all_linked = link_sources | link_targets

    # 2. 节点字段完整性
    required_node = ['id', 'label', 'type', 'confidence', 'status', 'source', 'section']
    for n in data['nodes']:
        for field in required_node:
            if field not in n:
                issues.append(f'❌ 节点 {n.get(\"id\",\"?\")} 缺少字段: {field}')

    # 3. 断链检测
    for link in data['links']:
        if link['source'] not in node_ids:
            issues.append(f'❌ 断链: source \"{link[\"source\"]}\" 不在 nodes 中')
        if link['target'] not in node_ids:
            issues.append(f'❌ 断链: target \"{link[\"target\"]}\" 不在 nodes 中')

    # 4. 孤立节点检测（至少 1 条连线）
    conn_count = Counter()
    for link in data['links']:
        conn_count[link['source']] += 1
        conn_count[link['target']] += 1
    for n in data['nodes']:
        if conn_count.get(n['id'], 0) == 0:
            issues.append(f'⚠️ 孤立节点: {n[\"id\"]} — 无任何连线')

    # 5. central_topic 有效性
    ct = data.get('central_topic', {})
    if ct.get('id') not in node_ids:
        issues.append(f'❌ central_topic \"{ct.get(\"id\")}\" 不在 nodes 中')

    # 6. 节点类型有效性检查
    valid_types = {'concept', 'knowledge-element', 'knowledge-point', 'skill-point', 'scenario', 'exercise'}
    used_types = {n['type'] for n in data['nodes']}
    invalid_types = used_types - valid_types
    if invalid_types:
        for t in invalid_types:
            issues.append(f'⚠️ 未知节点类型: {t}')

    # 7. auto-completed 节点必须标记 style: dashed
    for n in data['nodes']:
        if n.get('status') == 'auto-completed':
            if n.get('style') != 'dashed':
                issues.append(f'⚠️ auto-completed 节点 {n["id"]} 缺少 style: "dashed"')

    # 8. auto_completed[] 与节点 status 一致性
    ac_ids = {a['id'] for a in data.get('auto_completed', [])}
    for n in data['nodes']:
        if n['status'] == 'auto-completed' and n['id'] not in ac_ids:
            issues.append(f'⚠️ 节点 {n[\"id\"]} status=auto-completed '
                          f'但不在 auto_completed[] 数组中')
        if n['id'] in ac_ids and n.get('status') != 'auto-completed':
            issues.append(f'⚠️ 节点 {n[\"id\"]} 在 auto_completed[] 中 '
                          f'但 status={n.get(\"status\")}')

    # 9. central_topic 至少有 1 条连线
    ct_id = ct.get('id', '')
    if ct_id:
        ct_links = conn_count.get(ct_id, 0)
        if ct_links == 0:
            issues.append(f'⚠️ central_topic \"{ct_id}\" 无连线')

    return issues


def validate_node_content(data: dict) -> list:
    \"\"\"验证统一 JSON 中 nodes[] 的 content 字段完整性。\"\"\"
    issues = []
    if 'nodes' not in data or not isinstance(data['nodes'], list):
        issues.append('❌ 缺少 nodes 字段或非数组')
        return issues
    
    for n in data['nodes']:
        if 'id' not in n:
            issues.append('❌ nodes[] 中存在缺少 id 的条目')
        if 'content' not in n:
            nid = n.get('id', '?')
            issues.append(f'❌ 节点 {nid} 缺少 content 字段（无法渲染知识卡片）')
        if 'source' not in n:
            nid = n.get('id', '?')
            issues.append(f'❌ 节点 {nid} 缺少 source 字段（必须标注出处）')
        if 'section' not in n:
            nid = n.get('id', '?')
            issues.append(f'❌ 节点 {nid} 缺少 section 字段（必须标注章节来源）')
        if n.get('status') == 'existing' and n.get('source') in (None, '', 'kbqa-v3-complete'):
            nid = n.get('id', '?')
            issues.append(f'❌ 节点 {nid} status=existing 但 source 不是有效出处路径')
    
    return issues


def auto_fix_graph_json(data: dict) -> dict:
    """自动修复常见的 JSON 图谱问题。

    修复项：
    1. auto-completed 节点补充 style: dashed
    2. 缺失 source 字段的节点补填
    """
    data = json.loads(json.dumps(data))  # deep copy
    warnings = []

    # Fix: ensure auto-completed nodes have style: dashed
    for n in data.get('nodes', []):
        if n.get('status') == 'auto-completed':
            n['style'] = 'dashed'

    # Fix: ensure all nodes have source field
    for n in data.get('nodes', []):
        if 'source' not in n or not n['source']:
            if n.get('status') == 'auto-completed':
                n['source'] = 'kbqa-v3-complete'
            else:
                n['source'] = '出处/待查证（auto-fix 补填）'
                warnings.append(f'⚠️ 节点 {n.get("id","?")} source 由 auto-fix 补填为 "出处/待查证"')

    # Fix: ensure all nodes have section field
    for n in data.get('nodes', []):
        if 'section' not in n or not n['section']:
            if n.get('status') == 'auto-completed':
                n['section'] = 'kbqa-自动补齐'
            else:
                n['section'] = '待查证章节（auto-fix 补填）'
                warnings.append(f'⚠️ 节点 {n.get("id","?")} section 由 auto-fix 补填为 "待查证章节"')

    # Fix: no schema/rule fields needed — color_scheme and rules are frontend-side

    if warnings:
        import warnings as _warnings
        for w in warnings:
            _warnings.warn(w)

    return data
```

### 自校验执行规则

| 时机 | 操作 |
|:-----|:-----|
| 每次回答生成后（自动） | 检查：每个召回条目有 `**出处**` 和 `**章节**` 标注、引用来源表含章节来源列、有覆盖评估、无 JSON 数据块 |
| 发现缺少出处或章节 | 回读 frontmatter 补填来源信息，在出处文件中搜索确认章节号 |
| 发现误混入 JSON | 移除 JSON 数据块，仅保留纯 Markdown |

### 内部图谱数据自校验检查清单

#### 图谱数据完整性（用于 Agent 内部处理，不输出）
- [ ] `nodes[]` 所有 `id` 唯一
- [ ] `links[]` 所有 `source`/`target` 在 `nodes[]` 中存在
- [ ] 所有节点有至少 1 条连线（非孤立）
- [ ] `central_topic.id` 在 `nodes[]` 中存在
- [ ] `auto-completed` 节点全部标记 `style: dashed`
- [ ] 每个节点都有 `id`、`content`、`source` 和 `section` 字段
- [ ] `status` 为 `existing` 的节点必须填写有效出处文件路径（如 `出处/第3章-测向与定位技术.md`）和章节号（如 `第3章 测向与定位技术 / 3.3.1 干涉仪的基本原理`）

#### 最终回答检查（纯 Markdown 输出）
- [ ] 回答为纯 Markdown，无 JSON 数据块
- [ ] 每个召回条目标注了 `**出处**：{source_file}` 和 `**章节**：{chaper_section}`
- [ ] 引用来源表列出所有召回节点的出处和章节
- [ ] 知识库覆盖评估完整

### 输出前校验（问答流程中自动执行）

在输出最终 Markdown 回答前执行以下检查：

```python
# Phase A Step 5 中，输出前检查：
# 1. 每个召回条目是否标注了出处和章节
for item in recalled_items:
    assert '**出处**：' in item, f'缺少出处标注: {item[:50]}'
    assert '**章节**：' in item, f'缺少章节标注: {item[:50]}'

# 2. 引用来源表和知识库覆盖评估是否存在
assert '## 引用来源' in answer, '缺少引用来源表'
assert '## 知识库覆盖评估' in answer, '缺少覆盖评估'
assert '| 节点 | 出处文件 | 章节来源 |' in answer, '引用来源表缺少章节来源列'

# 3. 检查是否误混入了 JSON 数据块（不允许）
import re
json_block = re.search(r'```json\\n', answer)
if json_block:
    log.warning('❌ 回答中不应包含 JSON 数据块，已自动移除')
```

JSON 内部图谱数据仅在 Agent 内部用于知识空白检测和链式补齐分析，**不在最终回答中输出**。

---

## Phase B：知识空白检测

> **前置 Phase**: Phase A（检索+回答）必须已完成，否则无空白可检测

对回答问题过程中暴露的每个核心术语，检查 KB 中是否存在对应页面。

### 检测范围

| 节点类型 | 检查条件 | 缺失则标记 |
|:---------|:---------|:-----------|
| 概念 | 回答中核心技术术语 → `概念/{term}.md` 是否存在 | concept_gap |
| 知识要素 | 回答中涉及公式/方法 → `知识要素/{term}.md` 是否存在 | ke_gap |
| 知识点 | 回答中完整专题 → `知识点/{term}.md` 是否存在 | kp_gap |

### 检测步骤

```python
def detect_gaps(wiki_dir, question, answer, existing_refs):
    """检测回答中暴露的知识空白"""
    gaps = []
    
    # 1. 从 question + answer 中提取核心术语
    core_terms = extract_core_terms(question, answer)
    
    # 2. 排除已引用的页面（existing_refs）
    # 3. 检查每个术语在各目录是否存在
    for term in core_terms:
        if term in existing_refs:
            continue  # 已引用 → 不缺
        
        if os.path.exists(f"{wiki_dir}/概念/{term}.md"):
            continue  # 已有概念
        
        gaps.append({
            'term': term,
            'type': 'concept',        # 最可能的类型
            'priority': 'core',       # 'core' 或 'edge'
            'reason': f'回答中核心术语"{term}"无概念页',
        })
    
    # 4. 链式检测：概念缺 → 检查配套KE/KP是否也缺
    chain_gaps = detect_chain_gaps(wiki_dir, gaps, existing_refs)
    
    return gaps + chain_gaps
```

---

## Phase C：审阅确认（v3.0 新增核心）

> **前置 Phase**: Phase B（知识空白检测）必须已完成，审阅清单来自 B 的输出

### 补齐清单展示

检测到知识空白后，**不直接创建**，先向用户展示：

```
═══════════════════════════════════════════════
📋 检测到以下知识空白，请审阅：

核心空白（待补齐）：
  [ ] 概念/鉴相器
      原因：回答中核心术语，KB 无对应概念页
      链式关联：将同时检查以下是否存在 →
        └─ 知识要素/鉴相器输出公式
        └─ 知识点/鉴相技术

  [ ] 知识要素/相位测量公式
      原因：回答涉及相位差计算，无对应知识要素

建议跳过（边缘提及）：
  [ ] 概念/相位比较器
      原因：仅在背景介绍中提及

─────────────────────────────────────────────
操作选项：
  Y) 确认补齐所有勾选条目
  N) 全部跳过
  修改建议：概念/鉴相器的释义应为“XXX”
  取消某项：/skip 鉴相器
═══════════════════════════════════════════════
```

### 用户交互方式

| 用户输入 | 行为 |
|:---------|:-----|
| `Y` 或 `继续` | 确认补齐所有勾选条目 |
| `N` 或 `跳过` | 本次不补齐 |
| `概念/鉴相器的释义应为XXX` | 修改释义后补齐 |
| `/skip 鉴相器` | 跳过该条 |
| `/add 概念/XXX` | 额外添加某条 |
| 沉默无回复 | 只补齐 `priority='core'` 的条目 |

### 核心原则

> **知识的第一次写入方向，决定了质量基线。** 用户确认过的自动补齐内容进入 KB 后就是正式内容，会出现在以后的问答中。所以补齐前的审阅不可跳过。

---

### 链式补齐（Phase C→D 的递归检测）

#### 什么是链式补齐

创建概念 `A` 时，自动检查与 `A` 配套的其他节点类型是否也存在：

```
补齐 概念/鉴相器
  → 链检查 1: 知识要素/中有"鉴相器输出公式"吗？→ 缺 → 列入链式清单
  → 链检查 2: 知识点/中有"鉴相技术"吗？→ 缺 → 列入链式清单
  → 一并展示给用户确认
```

### 链式补齐决策表

| 当前补齐类型 | 触发检查 | 链缺失类型 | 说明 |
|:------------|:---------|:-----------|:-----|
| 概念/A | 是不是有配套的公式/方法 | 知识要素/A公式 | 概念常用公式 |
| 概念/A | 是不是有完整的技术专题 | 知识点/A技术 | 概念常属于某技术领域 |
| 知识要素/A公式 | 是不是有对应的概念 | 概念/A | 公式基于哪个概念 |
| 知识点/A | 是不是缺核心概念 | 概念/A | 知识点必有核心概念 |

### 链式检查实现

```python
def detect_chain_gaps(wiki_dir, primary_gaps, existing_refs):
    """从主要缺失出发，检查链式缺失"""
    chain_gaps = []
    
    # 链规则：概念类型 → 检查 KE/KP
    CONCEPT_KE_RULES = {
        '鉴相器': ['鉴相器输出公式'],
        '干涉仪': ['干涉仪相位差公式', '干涉仪无模糊条件'],
        '测向': ['测向系统灵敏度指标'],
    }
    
    CONCEPT_KP_RULES = {
        '鉴相器': ['鉴相技术'],
    }
    
    for gap in primary_gaps:
        if gap['type'] == 'concept':
            term = gap['term']
            
            # 检查配套 KE
            for ke_term in CONCEPT_KE_RULES.get(term, []):
                ke_path = f"{wiki_dir}/知识要素/{ke_term}.md"
                if not os.path.exists(ke_path) and ke_term not in existing_refs:
                    chain_gaps.append({
                        'term': ke_term,
                        'type': 'knowledge-element',
                        'priority': 'core',
                        'reason': f'概念"{term}"的配套公式/规则',
                        'chain_from': term,
                    })
            
            # 检查配套 KP
            for kp_term in CONCEPT_KP_RULES.get(term, []):
                kp_path = f"{wiki_dir}/知识点/{kp_term}.md"
                if not os.path.exists(kp_path) and kp_term not in existing_refs:
                    chain_gaps.append({
                        'term': kp_term,
                        'type': 'knowledge-point',
                        'priority': 'core',
                        'reason': f'概念"{term}"的完整技术专题',
                        'chain_from': term,
                    })
    
    return chain_gaps
```

### 默认链规则表（可扩展）

| 概念 | 配套 KE | 配套 KP |
|:-----|:--------|:--------|
| 鉴相器 | 鉴相器输出公式 | 鉴相技术 |
| 干涉仪 | 干涉仪相位差公式, 干涉仪无模糊条件 | 干涉仪测向技术 |
| 时差定位 | 时差定位双曲线方程 | 时差定位技术 |
| 测向交叉定位 | 测向交叉定位矩阵公式 | 测向交叉定位技术 |
| 虚拟基线 | 虚拟基线公式 | — |
| 圆概率误差 | 圆概率误差(CEP)公式 | — |
| 几何稀释精度 | 几何稀释精度(GDOP)公式 | — |

> ⚠️ 链规则表需要随 KB 内容扩展。当知识库中检测到新的概念→KE→KP 关系时，应自动记录到 `references/chain-rules.md`。

---

## Phase D：执行补齐 + 连通验证

> **前置 Phase**: Phase C（审阅确认）必须已完成，补齐清单已确认

### 执行补齐

按用户确认的清单创建页面，遵循 emc-textbook-wiki 模板规范：

- 概念 → `概念/{term}.md`（5层模板，无内容填"无"）
- 知识要素 → `知识要素/{term}.md`（3层模板）
- 知识点 → `知识点/{term}.md`（4层模板，简版）
- 全部 frontmatter 标记 `confidence: 0.65`, `source: "kbqa-v3-complete"`, `verified: false`
- 不含 `sources` 字段（无出处原文）

#### 实践验证 Pitfalls（2026-05-20 会话实测）

| # | Pitfall | 说明 | 正确做法 |
|:-:|:--------|:-----|:---------|
| 1 | **index.md 计数格式** | index.md 使用 `## 概念（N个）` 格式，追加时必须更新 N | `patch` 替换 `概念（X个）` → `概念（X+1个）`，而非简单追加行末 |
| 2 | **双向 wikilink 卫生** | 创建概念/A 后，已有概念/B 的关联层不会自动追加 `[[概念/A]]` | 手动 patch 已有相关概念的关联层（上下游/关联）追加 wikilink |
| 3 | **KE 置信度不一致** | KB 中已有的 KE（如鉴相器输出公式）可能标记 0.75/0.85，与用户规则 0.65 不符 | 不修改已有 KE 的置信度——这是 KB 构建早期的遗留问题。仅确保**新建**页面使用正确的 0.65 |
| 4 | **log.md 首次创建** | 若 KB 无 log.md，直接创建即可，无需等用户确认 | `write_file(log_path, "# 知识库操作日志\n\n")`，然后追加条目 |
| 5 | **概念名 ≠ 搜索词** | 用户问题中的术语可能与 KB 文件名不完全一致 | 先用 `ls 概念/ | grep -i {term}` 做模糊匹配，再用精确路径读取 |
| 6 | **行号污染陷阱** | `read_file` 输出含 `   NNN|` 行号前缀，若直接将其内容传给 `write_file` 会写入带前缀的脏数据 | 通过 `terminal` 用 `head`/`sed` 读取原始内容，或写文件时用 Python 脚本 `re.sub(r'^\s*\d+\|', '', line)` 清洗 |
| 7 | **代码块配对断裂** | 连续出现 ` ``` ` 时可能因语言标记（````text````）被误判为开闭配对 | 用 `grep -n '^```'` 检查配对：偶数个=正确。相邻的三个 ``` 往往是开-关-开模式，中间第二个可能是多余的 |
| 8 | **配置表误当代码块** | YAML 配置如被包裹在 ` ```yaml` 中，后续编辑时前后 ``` 可能不对称 | 配置项用 Markdown 表格而非 YAML 代码块，避免 ``` 配对问题 |
| 9 | **技能审计后遗漏修复** | 审计列出 N 个问题，修复时只做了 M < N 个 | 修复后运行 `python3 -c "检查各项是否通过"` 逐项确认，不允许留任何未修复项 |

### 连通性验证

每次补齐后自动运行：

```python
def verify_connectivity(wiki_dir, created_pages):
    """验证新创建页面的 wikilink 连通性"""
    issues = []
    
    for page_path in created_pages:
        with open(page_path, 'r') as f:
            content = f.read()
        
        # 1. 检查是否有 outbound wikilink
        outbound = re.findall(r'\[\[([^\]]+)\]\]', content)
        if len(outbound) < 1:
            issues.append(f'{page_path}: 0 条出站 wikilink（至少需 1 条）')
        
        # 2. 检查 inbound wikilink
        page_name = os.path.basename(page_path).replace('.md', '')
        inbound_count = 0
        for d in ['概念', '知识要素', '知识点']:
            d_path = os.path.join(wiki_dir, d)
            if not os.path.isdir(d_path):
                continue
            for fname in os.listdir(d_path):
                if fname.endswith('.md') and fname != os.path.basename(page_path):
                    with open(os.path.join(d_path, fname), 'r') as f:
                        if f'[[{d}/{page_name}]]' in f.read():
                            inbound_count += 1
        if inbound_count < 1:
            issues.append(f'{page_path}: 0 条入站 wikilink')
        
        # 3. 检查 index.md 中是否有该页面
        index_path = os.path.join(wiki_dir, 'index.md')
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                if page_name not in f.read():
                    issues.append(f'{page_path}: 未在 index.md 中列出')
    
    return issues
```

### 更新 index.md 和 log.md

```python
def update_nav(wiki_dir, created_pages):
    """追加 index.md 和 log.md"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # index.md：追加到对应 section
    index_path = f"{wiki_dir}/index.md"
    if os.path.exists(index_path):
        with open(index_path, 'a') as f:
            for page in created_pages:
                f.write(f"\n[[{page}]]")
    
    # log.md
    log_path = f"{wiki_dir}/log.md"
    if not os.path.exists(log_path):
        with open(log_path, 'w') as f:
            f.write(f"# 知识库操作日志\n\n")
    
    with open(log_path, 'a') as f:
        f.write(f"\n## [{today}] kbqa | 审阅补齐\n")
        for page in created_pages:
            f.write(f"- 创建 [[{page}]] (0.65, kbqa-v3-complete)\n")
```

---

## Phase E：纠错回写（用户触发）

> **触发条件**: 用户明确指正 KB 内容错误，不依赖 Phase 顺序。可在任何 Phase 后触发

### 触发条件

用户在问答或教材生成审阅中说：
- "这个定义不对"
- "这个概念说错了"
- "这个公式不完整"
- "这个分类漏了XXX"

### 纠错流程

```
用户: "概念/鉴相器的定义不对，它是用来测相位差的，不是测频率的"

Step 1: 读取 概念/鉴相器.md
Step 2: 定位错误内容（精准释义）
Step 3: 用户提供正确版本
Step 4: patch 更新文件
Step 5: 在文件末尾追加纠错注释：
        <!-- [2026-05-20] kbqa: 用户纠正释义——原为"测频", 改为"测相位差" -->
Step 6: 更新 log.md
Step 7: 告知用户修正已完成
```

### 纠错记录规范

```markdown
## [YYYY-MM-DD] kbqa | 用户纠错：概念/鉴相器

### 错误位置
- 文件：概念/鉴相器.md
- 字段：精准释义
- 原内容：「鉴相器是一种用于测量信号频率的设备」
- 正确内容：「鉴相器是一种用于测量两路信号之间相位差的设备」

### 后续建议
如需验证正确性并升级到 0.95，请提供出处原文。
```

### 纠错后的连通更新

如果用户对概念的修改涉及与其他页面的关系变化，自动检查并更新：

```python
def update_after_correction(wiki_dir, corrected_page, changed_terms):
    """概念修正后，更新引用该概念的所有页面中的相关表述"""
    # 搜索所有引用该概念的页面
    # 如果这些页面中的描述与修正后的概念不一致，标记为待更新
    affected_pages = []  # 需要手动审阅的页面列表
    # 不自动修改——只汇报
    return affected_pages
```

---

## Phase F：总结分析（定期/按需触发）

> **最佳时机**: 一轮完整 A→B→C→D→E 流程结束后（或用户要求时）

### 触发时机

| 场景 | 触发方式 | 分析范围 |
|:-----|:---------|:---------|
| 问答会话结束时 | 自动 | 本次会话的补齐 + 纠错 |
| 用户要求"分析KB状态" | 手动 | 全部 log.md |
| 教材一章生成完后 | 自动 | 该章相关的补齐 |
| 每周/每月健康检查 | 定期 | 全部 KB + log.md |

### 分析报告结构

```
═══════════════════════════════════════════════
📊 KB 状态分析报告

一、自动补齐概况
  ─ 总计已自动补齐：概念 N 个，KE M 个，KP K 个
  ─ 其中已审阅确认：N 个（由用户确认过）
  ─ 其中静默补齐：M 个（v2.0 遗留）

二、高频缺失 TOP 5
  ─ 鉴相器系列：出现在 3 次问答中
  ─ 测向精度公式：出现在 2 次问答中
  ─ 建议优先用出处原文升级

三、用户纠错统计
  ─ 总计纠错：N 次
  ─ 待验证：M 次（纠错后未验证出处）

四、连通性检查
  ─ 孤立页面（无入站链接）：N 个
  ─ 断链：N 处 wikilink 指向不存在页面

五、升级建议（0.65 → 0.95）
  优先级列表：
    1. 概念/鉴相器（高频缺失 + 可提供出处原文）
    2. 知识要素/时差定位公式（教材生成必需）
═══════════════════════════════════════════════
```

### 分析实现

```python
def analyze_log(wiki_dir):
    """分析 log.md 生成总结报告"""
    log_path = f"{wiki_dir}/log.md"
    if not os.path.exists(log_path):
        return "log.md 不存在"
    
    with open(log_path, 'r') as f:
        content = f.read()
    
    # 统计补齐条目
    creates = re.findall(r'创建 \[\[([^\]]+)\]\]', content)
    corrections = re.findall(r'用户纠错：([^\n]+)', content)
    
    # 统计高频术语
    term_freq = defaultdict(int)
    for create in creates:
        term = create.split('/')[-1] if '/' in create else create
        term_freq[term] += 1
    
    top_missing = sorted(term_freq.items(), key=lambda x: -x[1])[:5]
    
    # 连通性检查
    isolated = []
    for d in ['概念', '知识要素', '知识点']:
        d_path = f"{wiki_dir}/{d}"
        if not os.path.isdir(d_path):
            continue
        for fname in os.listdir(d_path):
            if not fname.endswith('.md'):
                continue
            # 扫描全库入站链接数
            inbound = 0
            page_name = fname.replace('.md', '')
            for scan_d in ['概念', '知识要素', '知识点', '技能点', '场景']:
                scan_path = os.path.join(wiki_dir, scan_d)
                if not os.path.isdir(scan_path):
                    continue
                for scan_f in os.listdir(scan_path):
                    if scan_f == fname or not scan_f.endswith('.md'):
                        continue
                    with open(os.path.join(scan_path, scan_f), 'r') as sf:
                        if f'[[{d}/{page_name}]]' in sf.read():
                            inbound += 1
            if inbound == 0:
                isolated.append(f"{d}/{page_name}")
    
    return {
        'total_creates': len(creates),
        'top_missing': top_missing,
        'corrections': corrections,
        'isolated_pages': isolated,
        'total_auto_complete': len([c for c in creates if '(0.65' in content]),
    }
```

---

## 教材生成闭环（与 professional-textbook-compilation 协同）

### 生成→KB 回写

教材生成时，每节的处理：

```
模板标题 "3.3.2 测角模糊问题"
  ↓
1. 执行 kb-qa 检索（走 Phase A）
  ↓
2. 检测到 KB 缺失（走 Phase B）
  ↓
3. 询问用户："教材生成中检测到缺失，是否补齐？"
  ↓
4. 用户确认后执行补齐（走 Phase C→D）
  ↓
5. 继续生成该节（KB 现在更完整了）
  ↓
6. 章生成完成 → 执行 Phase F 总结分析
```

### 生成过程中的用户纠错

```
用户审阅3.2.1节："这里干涉仪的组成写错了，
应该是两天线+两接收通道+鉴相器，不是三通道"

  ↓
1. kb-qa 检索 KB → 发现 概念/相位干涉仪 的构成要素描述也错了
2. 问用户："KB 中 概念/相位干涉仪.md 也需要同步修正吗？"
3. 用户确认 → 执行 Phase E 纠错回写
4. 该节重写 → 使用更新后的 KB 内容

---

## 升级管道（0.65 → 0.95）

### 升级流程

```
现有自动补齐页面（0.65, verified: false）
  ↓
用户提供出处 PDF/DOCX
  ↓
emc-textbook-wiki Step 4-5 重新提取
  ↓
verify-concept-definitions.py 验证
  ↓
✅ 通过 → confidence 升级到 0.95, verified: true
|❌ 失败 → 保持 0.65，标记 verified: false
```

### Phase F 分析报告中含升级建议

```text
升级建议（0.65 → 0.95）：
  1. 概念/鉴相器 — 高频缺失 + 有出处PDF可提取
  2. 知识要素/时差定位公式 — 教材生成必需
```

---

## 配置项

以下为 kb-qa 技能的可调参数，Agent 在每次问答开始时读取这些配置：

| 参数路径 | 类型 | 默认值 | 说明 |
|:---------|:-----|:-------|:-----|
| `kbqa.auto_complete.skip_user_confirmation` | bool | `false` | 设为 `true` 则跳过用户审阅（Phase C），静默补齐 |
| `kbqa.auto_complete.chain_completion` | bool | `true` | 补齐概念时自动检查配套 KE/KP |
| `kbqa.auto_complete.only_core_gaps` | bool | `true` | 只补核心术语，边缘提及的跳过 |
| `kbqa.connectivity.verify_after_complete` | bool | `true` | 补齐后自动验证 wikilink 连通性 |
| `kbqa.connectivity.auto_fix_orphans` | bool | `false` | 是否自动修复孤立页面（须用户确认） |
| `kbqa.analysis.auto_report` | bool | `true` | 每章生成完后自动输出 KB 状态分析报告（Phase F） |
| `kbqa.upgrade.suggest_on_analysis` | bool | `true` | 在分析报告中包含 0.65→0.95 升级建议 |

---

## 相关技能

- `emc-textbook-wiki` — 将 0.65 的自动补齐页面升级为 0.95 的出处原文验证
- `professional-textbook-compilation` — 教材生成消费方，实现生成→KB 双向同步
- `llm-wiki` — 自动补齐策略的参考来源
- `file2md` — PDF/DOCX → Markdown，用于升级管道

## 参考文件

- `references/chain-rules.md` — 链式补齐的规则表（概念→KE→KP 映射）
- `scripts/validate-graph-json.py` — JSON 图谱自校验脚本