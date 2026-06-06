#!/usr/bin/env python3
"""
validate-graph-json.py — 验证 kb-qa 回答中的 JSON 图谱数据和 returned_pages 数据。

支持两种 JSON 块的验证：
  1. 图谱 JSON（nodes + links + color_scheme + rules）
  2. returned_pages JSON（按类型组织的召回内容）

用法：
    python3 validate-graph-json.py <json_file>       # 验证单个 JSON 文件
    python3 validate-graph-json.py --stdin            # 从 stdin 读取
"""
import json
import sys
from collections import Counter

VALID_TYPES = {'concept', 'knowledge-element', 'knowledge-point', 'skill-point', 'scenario', 'exercise'}
VALID_STATUS = {'existing', 'auto-completed', 'gap'}
REQUIRED_GRAPH_FIELDS = ['version', 'timestamp', 'topic', 'nodes', 'links', 'central_topic', 'gaps', 'auto_completed', 'coverage', 'color_scheme']
REQUIRED_NODE_FIELDS = ['id', 'label', 'type', 'confidence', 'status']


def validate_graph_json(data: dict) -> list:
    """验证图谱 JSON 的完整性和一致性。返回问题列表，空列表=通过。"""
    issues = []

    for field in REQUIRED_GRAPH_FIELDS:
        if field not in data:
            issues.append(f'❌ 缺少必需字段: {field}')

    if 'nodes' not in data or 'links' not in data:
        return issues

    node_ids = {n['id'] for n in data['nodes']}

    # 节点字段完整性
    for n in data['nodes']:
        for field in REQUIRED_NODE_FIELDS:
            if field not in n:
                issues.append(f'❌ 节点 {n.get("id","?")} 缺少字段: {field}')

    # 断链检测
    for link in data['links']:
        if link['source'] not in node_ids:
            issues.append(f'❌ 断链: source "{link["source"]}" 不在 nodes 中')
        if link['target'] not in node_ids:
            issues.append(f'❌ 断链: target "{link["target"]}" 不在 nodes 中')

    # 孤立节点
    conn_count = Counter()
    for link in data['links']:
        conn_count[link['source']] += 1
        conn_count[link['target']] += 1
    for n in data['nodes']:
        if conn_count.get(n['id'], 0) == 0:
            issues.append(f'⚠️ 孤立节点: {n["id"]} — 无任何连线')

    # 节点 ID 唯一性
    if len(node_ids) != len(data['nodes']):
        issues.append('❌ nodes[] 中存在重复 id')

    # central_topic 有效性
    ct = data.get('central_topic', {})
    if ct.get('id') not in node_ids:
        issues.append(f'❌ central_topic "{ct.get("id")}" 不在 nodes 中')

    # color_scheme 覆盖
    used_types = {n['type'] for n in data['nodes']}
    scheme_types = set(data.get('color_scheme', {}).keys())
    missing_scheme = used_types - scheme_types
    if missing_scheme:
        for t in missing_scheme:
            issues.append(f'⚠️ color_scheme 缺少类型: {t}')

    # auto-completed 节点标记
    for n in data['nodes']:
        if n.get('status') == 'auto-completed' and n.get('style') != 'dashed':
            issues.append(f'⚠️ auto-completed 节点 {n["id"]} 缺少 style: "dashed"')

    # auto_completed[] 一致性
    ac_ids = {a['id'] for a in data.get('auto_completed', [])}
    for n in data['nodes']:
        if n['status'] == 'auto-completed' and n['id'] not in ac_ids:
            issues.append(f'⚠️ 节点 {n["id"]} status=auto-completed 但不在 auto_completed[] 中')
        if n['id'] in ac_ids and n.get('status') != 'auto-completed':
            issues.append(f'⚠️ 节点 {n["id"]} 在 auto_completed[] 中但 status={n.get("status")}')

    # rules 段完整性
    rules = data.get('rules', {})
    required_rules = ['node_color_by', 'node_border_style', 'node_size_by']
    for r in required_rules:
        if r not in rules:
            issues.append(f'⚠️ rules 缺少字段: {r}')

    # gap 有连线
    ct_id = ct.get('id', '')
    if ct_id:
        ct_links = conn_count.get(ct_id, 0)
        if ct_links == 0:
            issues.append(f'⚠️ central_topic "{ct_id}" 无连线')

    return issues


def validate_returned_pages(data: dict) -> list:
    """验证 returned_pages JSON。返回问题列表，空列表=通过。"""
    issues = []

    if 'returned_pages' not in data:
        issues.append('❌ 缺少 returned_pages 字段')
        return issues

    rp = data['returned_pages']

    for node_type, pages in rp.items():
        if node_type not in VALID_TYPES:
            issues.append(f'⚠️ returned_pages 中未知类型: {node_type}')
        if not isinstance(pages, list):
            issues.append(f'❌ returned_pages.{node_type} 应为数组')
            continue
        for i, p in enumerate(pages):
            if 'id' not in p:
                issues.append(f'❌ returned_pages.{node_type}[{i}] 缺少 id')
            if 'content' not in p:
                issues.append(f'❌ returned_pages.{node_type}[{i}] 缺少 content')
            if p.get('status') == 'auto-completed' and p.get('style') != 'dashed':
                issues.append(f'⚠️ returned_pages.{node_type}[{i}] auto-completed 但缺少 style: dashed')

    return issues


def auto_fix_graph_json(data: dict) -> dict:
    """自动修复常见的 JSON 图谱问题。"""
    import copy
    data = copy.deepcopy(data)

    for n in data.get('nodes', []):
        if n.get('status') == 'auto-completed':
            n['style'] = 'dashed'

    data['rules'] = {
        'node_color_by': "color_scheme[node.type].fill",
        'node_node_color_by_autocompleted': "color_scheme[node.type].fill",
        'node_border_style': "status === 'auto-completed' ? dashed : solid",
        'node_border_style_gap': "dashed",
        'node_size_by': "confidence (0.95=large, 0.65=small)",
        'edge_color_by': "source.type",
        'central_fixed': True,
    }

    return data


def main():
    if len(sys.argv) < 2:
        print("用法: python3 validate-graph-json.py <json_file>")
        print("      python3 validate-graph-json.py --stdin")
        sys.exit(1)

    if sys.argv[1] == '--stdin':
        data = json.load(sys.stdin)
    else:
        with open(sys.argv[1], 'r') as f:
            data = json.load(f)

    graph_issues = validate_graph_json(data)
    rp_issues = validate_returned_pages(data)

    total = len(graph_issues) + len(rp_issues)

    if graph_issues:
        print(f"🔴 图谱 JSON 问题 ({len(graph_issues)}):")
        for i in graph_issues:
            print(f"  {i}")

    if rp_issues:
        print(f"🔴 returned_pages 问题 ({len(rp_issues)}):")
        for i in rp_issues:
            print(f"  {i}")

    if total == 0:
        print("✅ 全部校验通过")
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
