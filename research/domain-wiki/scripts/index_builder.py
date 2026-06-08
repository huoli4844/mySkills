#!/usr/bin/env python3
"""index_builder.py — 基于知识图谱的 L2/L3/L4 索引构建器

流程:
  1. 构建 KGraph（从 .md 文件扫描 frontmatter + wikilinks → SQLite）
  2. 查询图分析数据（连通率、度中心性、质量检查等）
  3. 生成索引 YAML（book_overview, concept_index, knowledge_index, skill_index, scenario_index）
  4. 渲染到 10_总揽/（通过 template_engine.py 的模板）

用法:
  python3 index_builder.py /path/to/book_dir --book-id 01_书籍ID --book-name "书籍名称"
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from kg_builder import KGraph  # noqa: E402
from graph_analytics import build_graph_section, get_enriched_nodes  # noqa: E402


# ── 类型目录映射 ──────────────────────────────────────────

TYPE_DIR_MAP = {
    "concept": "30_核心概念",
    "ke": "40_知识要素",
    "entity": "80_实体",
    "kp": "50_知识点",
    "sp": "60_技能点",
    "scene": "70_应用场景",
    "exercise": "90_习题",
    "solution": "90_习题/解答",
}

TYPE_TAG_MAP = {
    "concept": "30_核心概念",
    "ke": "40_知识要素",
    "entity": "80_实体",
    "kp": "50_知识点",
    "sp": "60_技能点",
    "scene": "70_应用场景",
}


def read_frontmatter(path):
    """读取 YAML frontmatter"""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}, ""
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, content


def scan_files_with_fm(book_dir, rel_dir):
    """扫描目录中的 .md 文件，读取 frontmatter"""
    full = os.path.join(book_dir, rel_dir)
    if not os.path.isdir(full):
        return []
    entries = []
    for fn in sorted(os.listdir(full)):
        if not fn.endswith(".md"):
            continue
        fname = fn[:-3]
        path = os.path.join(full, fn)
        fm, _ = read_frontmatter(path)
        entries.append({
            "fname": fname,
            "name": fm.get("name", fname),
            "chapter_num": str(fm.get("chapter_num", fm.get("source_chapter", "0"))),
            "type": fm.get("type", ""),
            "bloom_level": fm.get("bloom_level", ""),
        })
    return entries


def make_wikilink_table(items, prefix):
    """构建 wikilink 表格字符串"""
    if not items:
        return "暂无\n"
    lines = ["", "| # | 名称 | 链接 |", "|:--|:-----|:-----|"]
    for i, item in enumerate(items, 1):
        name = item.get("name", f"item_{i}")
        fname = item.get("fname", name)
        link = f"[[{prefix}/{fname}|{name}]]"
        lines.append(f"| {i} | {name} | {link} |")
    return "\n".join(lines)


def build_index(
    book_dir, book_id, book_name, kg_data, graph_section, enriched_nodes,
):
    """构建所有索引 YAML 并写入 .dag/index_data/"""
    DATA_DIR = os.path.join(book_dir, ".dag", "index_data")
    os.makedirs(DATA_DIR, exist_ok=True)

    NL = "\n"
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 扫描所有 .md 文件 ──
    scanned = {}
    for ttype, rel_dir in TYPE_TAG_MAP.items():
        scanned[ttype] = scan_files_with_fm(book_dir, rel_dir)

    all_concepts = scanned.get("concept", [])
    all_kes = scanned.get("ke", [])
    all_entities = scanned.get("entity", [])
    all_kps = scanned.get("kp", [])
    all_sps = scanned.get("sp", [])
    all_scenes = scanned.get("scene", [])

    # ── 统计 ──
    stats = {
        "concept_count": len(all_concepts),
        "ke_count": len(all_kes),
        "entity_count": len(all_entities),
        "knowledge_count": len(all_kps),
        "skill_count": len(all_sps),
        "scenario_count": len(all_scenes),
    }
    if kg_data and "type_counts" in kg_data:
        tc = kg_data["type_counts"]
        stats.update({
            "total_nodes": kg_data.get("nodes", 0),
            "total_edges": kg_data.get("edges", 0),
            "avg_edges": kg_data.get("avg_edges", 0),
            "concept_count": tc.get("concept", len(all_concepts)),
            "knowledge_count": tc.get("knowledge", len(all_kps)),
            "skill_count": tc.get("skill", len(all_sps)),
            "scenario_count": tc.get("scenario", len(all_scenes)),
        })

    # ── 按章节分组 ──
    ch_dist = defaultdict(list)
    for ttype, entries in scanned.items():
        for e in entries:
            ch = e.get("chapter_num", "0")
            ch_dist[ch].append((ttype, e))

    # ── 1. book_overview ──
    by_chapter_lines = []
    for ch in sorted(ch_dist.keys()):
        entries = ch_dist[ch]
        type_counts = defaultdict(int)
        items = []
        for ttype, e in entries:
            type_counts[ttype] += 1
            if len(items) < 10:
                items.append(f"[[{TYPE_TAG_MAP.get(ttype, '')}/{e['fname']}|{e['name']}]]")
        type_str = ", ".join(f"{c}个{t}" for t, c in sorted(type_counts.items()))
        link_str = ", ".join(items)
        suffix = "..." if len(entries) > 10 else ""
        by_chapter_lines.append(f"### 第{ch}章（{len(entries)}个节点, {type_str}）{NL}{link_str}{suffix}")

    # KG enriched sections
    gs = graph_section or {}
    concept_table = make_wikilink_table(all_concepts, f"../{TYPE_DIR_MAP['concept']}")
    knowledge_table = make_wikilink_table(all_kps, f"../{TYPE_DIR_MAP['kp']}")
    skill_table = make_wikilink_table(all_sps, f"../{TYPE_DIR_MAP['sp']}")
    scenario_table = make_wikilink_table(all_scenes, f"../{TYPE_DIR_MAP['scene']}")

    overview_yaml = f"""---
template_engine: ok
type: book_overview
overview_level: L2
name: {book_name}
book_id: {book_id}
domain: 电磁兼容领域
confidence: 0.90
reviewer: system
review_date: {today}
tags: ["index"]
---

# {book_name}

## 简介

基于全书{stats.get('total_nodes', '—')}个节点（{stats.get('concept_count',0)}概念、{stats.get('knowledge_count',0)}知识点、{stats.get('skill_count',0)}技能点、{stats.get('scenario_count',0)}场景）自动构建的知识图谱分析。

## 📊 知识体系全景

### 知识链连通率
{gs.get('chain_connectivity', '（待构建）')}

### 节点连接性统计
{gs.get('node_connectivity', '（待构建）')}

## 🔍 图谱质量
{gs.get('graph_quality', '（待构建）')}

## 🏆 核心知识节点
{gs.get('top_nodes', '（待构建）')}

## 🗺 知识图谱全景
```mermaid
{gs.get('mindmap_content', 'graph TB')}
```

## 📋 章节分布
{gs.get('chapter_distribution', '（待构建）')}

## 🔗 推荐学习路径
{gs.get('learning_path', '（待补充）')}

## 🎯 动态学习路径（Bloom 认知层级 + 前置依赖）
{gs.get('learning_path_v2', '（待补充）')}

## 📑 索引导航

### 核心概念
{concept_table}

### 知识点
{knowledge_table}

### 技能点
{skill_table}

### 应用场景
{scenario_table}

## ⚠️ 待修复项
{gs.get('todo_items', '（无待修复项）')}
- 生成日期: {today}
- 置信度: 0.90
- 数据来源: KGraph 知识图谱引擎
"""
    _write_yaml(DATA_DIR, "book_overview.yaml", overview_yaml)

    # ── 2. concept_index ──
    type_tag_groups = defaultdict(list)
    for e in all_concepts:
        tag = "其他概念"
        fm = e.get("fm", {})
        # 优先使用 frontmatter 中的 type_tag
        fm_tag = fm.get("type_tag", "")
        if fm_tag:
            tag = fm_tag
        # 否则按章节号归类
        else:
            ch = fm.get("source_chapter", "")
            if ch:
                tag = f"第{ch}章概念"
            else:
                tag = "其他概念"
        type_tag_groups[tag].append(e)

    concept_ch_sections = []
    for ch in sorted(ch_dist.keys()):
        items = [f"[[{TYPE_DIR_MAP['concept']}/{e['fname']}|{e['name']}]]"
                 for ttype, e in ch_dist[ch] if ttype == "concept"]
        if items:
            concept_ch_sections.append(f"### 第{ch}章{NL}{', '.join(items)}")

    concept_tag_sections = []
    for tag in sorted(type_tag_groups.keys()):
        entries = type_tag_groups[tag]
        items = "\n".join(f"- [[{TYPE_DIR_MAP['concept']}/{e['fname']}|{e['name']}]]（第{e['chapter_num']}章）"
                         for e in entries)
        concept_tag_sections.append(f"### {tag} ({len(entries)}个){NL}{items}")

    concept_yaml = f"""---
template_engine: ok
type: concept_index
name: 核心概念索引 - {book_name}
book_id: {book_id}
confidence: 0.90
reviewer: system
review_date: {today}
tags: ["index"]
---

# 核心概念索引 - {book_name}

## 按分类

{NL.join(concept_tag_sections)}

## 按章节分类

{NL.join(concept_ch_sections)}

## 统计

- 总概念数: {kg_data.get('type_counts', {}).get('concept', len(all_concepts)) if kg_data else len(all_concepts)}
"""
    _write_yaml(DATA_DIR, "concept_index.yaml", concept_yaml)

    # ── 3. knowledge_index ──
    bloom_groups = defaultdict(list)
    ch_kp_groups = defaultdict(list)
    for e in all_kps:
        bl = e.get("bloom_level", "")
        if bl:
            bloom_groups[bl].append(e)
        ch = e.get("chapter_num", "?")
        ch_kp_groups[ch].append(e)

    bloom_sections = []
    for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]:
        items = bloom_groups.get(bl, [])
        if items:
            item_lines = "\n".join(f"- [[{TYPE_DIR_MAP['kp']}/{e['fname']}|{e['name']}]]"
                                  for e in items)
            bloom_sections.append(f"### {bl} ({len(items)}个){NL}{item_lines}")

    kp_ch_sections = []
    for ch in sorted(ch_kp_groups.keys()):
        items = ch_kp_groups[ch]
        item_lines = ", ".join(f"[[{TYPE_DIR_MAP['kp']}/{e['fname']}|{e['name']}]]" for e in items)
        kp_ch_sections.append(f"### 第{ch}章{NL}{item_lines}")

    bloom_dist = ", ".join(f"{bl}:{len(items)}" for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]
                          if (items := bloom_groups.get(bl, [])))

    knowledge_yaml = f"""---
template_engine: ok
type: knowledge_index
name: 知识点索引 - {book_name}
book_id: {book_id}
confidence: 0.90
reviewer: system
review_date: {today}
tags: ["index"]
---

# 知识点索引 - {book_name}

## 按认知层级分类

{NL.join(bloom_sections) if bloom_sections else "（暂无按Bloom层级分类的知识点）"}

## 按章节分类

{NL.join(kp_ch_sections)}

## 统计

- 总知识点数: {len(all_kps)}
- 按认知层级分布: {bloom_dist}
"""
    _write_yaml(DATA_DIR, "knowledge_index.yaml", knowledge_yaml)

    # ── 4. skill_index ──
    sp_ch_sections = []
    for ch in sorted(ch_dist.keys()):
        items = [f"[[{TYPE_DIR_MAP['sp']}/{e['fname']}|{e['name']}]]"
                 for ttype, e in ch_dist[ch] if ttype == "sp"]
        if items:
            sp_ch_sections.append(f"### 第{ch}章{NL}{', '.join(items)}")

    skill_yaml = f"""---
template_engine: ok
type: skill_index
name: 技能点索引 - {book_name}
book_id: {book_id}
confidence: 0.90
reviewer: system
review_date: {today}
tags: ["index"]
---

# 技能点索引 - {book_name}

## 按章节分类

{NL.join(sp_ch_sections) if sp_ch_sections else "（暂无技能点数据）"}

## 统计

- 总技能点数: {len(all_sps)}
"""
    _write_yaml(DATA_DIR, "skill_index.yaml", skill_yaml)

    # ── 5. scenario_index ──
    scene_ch_sections = []
    for ch in sorted(ch_dist.keys()):
        items = [f"[[{TYPE_DIR_MAP['scene']}/{e['fname']}|{e['name']}]]"
                 for ttype, e in ch_dist[ch] if ttype == "scene"]
        if items:
            scene_ch_sections.append(f"### 第{ch}章{NL}{', '.join(items)}")

    scenario_yaml = f"""---
template_engine: ok
type: scenario_index
name: 应用场景索引 - {book_name}
book_id: {book_id}
confidence: 0.90
reviewer: system
review_date: {today}
tags: ["index"]
---

# 应用场景索引 - {book_name}

## 按章节分类

{NL.join(scene_ch_sections) if scene_ch_sections else "（暂无应用场景数据）"}

## 统计

- 总应用场景数: {len(all_scenes)}
"""
    _write_yaml(DATA_DIR, "scenario_index.yaml", scenario_yaml)

    total = len(overview_yaml) + len(concept_yaml) + len(knowledge_yaml) + len(skill_yaml) + len(scenario_yaml)
    print(f"  ✅ 索引YAML生成完成: 5 个文件, {total} bytes")

    return True


def _write_yaml(dir_path, filename, content):
    """写入 YAML 文件"""
    path = os.path.join(dir_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  📄 {filename} ({len(content)} bytes)")


def render_indices(book_dir):
    """渲染索引 YAML → 10_总揽/ .md 文件"""
    idx_dir = os.path.join(book_dir, ".dag", "index_data")
    if not os.path.isdir(idx_dir):
        print(f"  ❌ 索引数据目录不存在: {idx_dir}")
        return False

    output_dir = os.path.join(book_dir, "10_总揽")
    os.makedirs(output_dir, exist_ok=True)

    index_map = {
        "book_overview.yaml": "book_overview.md",
        "concept_index.yaml": "concept_index.md",
        "knowledge_index.yaml": "knowledge_index.md",
        "skill_index.yaml": "skill_index.md",
        "scenario_index.yaml": "scenario_index.md",
    }

    rendered = 0
    for yf, out_md in index_map.items():
        yp = os.path.join(idx_dir, yf)
        if not os.path.isfile(yp):
            print(f"  ⏳ 跳过 {yf}（不存在）")
            continue
        with open(yp, encoding="utf-8") as f:
            raw = f.read()
        # 提取 body（frontmatter 之后的部分）
        body_match = re.split(r"^---\s*\n.*?\n---\s*\n", raw, maxsplit=1, flags=re.DOTALL)
        md_body = body_match[1] if len(body_match) > 1 else raw
        out_path = os.path.join(output_dir, out_md)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_body)
        rendered += 1
        print(f"  📄 → 10_总揽/{out_md} ({len(md_body)} chars)")

    print(f"  ✅ 已渲染 {rendered} 个索引文件到 10_总揽/")
    return True


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="索引构建器（知识图谱驱动）")
    p.add_argument("book_dir", help="书籍工作目录")
    p.add_argument("--book-id", required=True, help="书籍ID")
    p.add_argument("--book-name", required=True, help="书籍名称")
    p.add_argument("--skip-kg", action="store_true", help="跳过知识图谱构建（仅扫描文件）")
    args = p.parse_args()

    book_dir = os.path.abspath(args.book_dir)
    book_id = args.book_id
    book_name = args.book_name

    print("=" * 60)
    print(f"索引构建: {book_name} (ID: {book_id})")
    print("=" * 60)

    kg_data = None
    graph_section = None
    enriched_nodes = None

    if not args.skip_kg:
        # Step 1: 构建知识图谱
        print("\n📊 Step 1: 构建知识图谱...")
        wiki_root = os.path.normpath(os.path.join(book_dir, "..", ".."))
        if not os.path.isdir(wiki_root):
            # 回退到 book_dir 的父目录的父目录
            wiki_root = os.path.normpath(os.path.join(book_dir, ".."))
        print(f"  Wiki根目录: {wiki_root}")
        print(f"  Book目录: {book_dir}")
        kg = KGraph(wiki_root, book_dir=book_dir)
        try:
            kg_data = kg.build()
            print(f"  ✅ 知识图谱构建完成")

            # Step 2: 图分析
            print("\n🔍 Step 2: 进行图分析...")
            graph_section = build_graph_section(kg)
            enriched_nodes = get_enriched_nodes(kg)
            print(f"  ✅ 图分析完成")

            # 输出摘要
            s = kg.check_graph_quality()["summary"]
            print(f"  图质量: 🔴C:{s['critical']} ⚠️W:{s['warning']} ℹ️I:{s['info']}")
            top10 = kg.get_top_nodes(5)
            if top10:
                top_strs = [f"{r['name']}({r['in_degree']+r['out_degree']})" for r in top10]
                print(f"  Top5: {' | '.join(top_strs)}")
        except Exception as e:
            print(f"  ⚠️ 知识图谱异常: {e}")
            kg_data = None
    else:
        print("\n⏩ 跳过知识图谱构建")

    # Step 3: 构建索引 YAML
    print("\n📝 Step 3: 构建索引 YAML...")
    build_index(book_dir, book_id, book_name, kg_data, graph_section, enriched_nodes)

    # Step 4: 渲染到 10_总揽/
    print("\n🖨  Step 4: 渲染索引到 10_总揽/...")
    render_indices(book_dir)

    print(f"\n✅ 索引构建完成")


if __name__ == "__main__":
    main()
