#!/usr/bin/env python3
"""index_builder.py — 扫描已渲染文件构建 L2/L3/L4 索引 YAML

扫描 30_核心概念/40_知识要素/50_知识点/60_技能点/70_应用场景/80_实体
读取 YAML frontmatter + wikilink → 生成索引 YAML → 供 template_engine.py 渲染

用法:
  python3 index_builder.py /path/to/book_dir --book-id 01_书籍ID --book-name "书籍名称"
"""

import os, re, sys
from collections import defaultdict

BOOK_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
BOOK_ID = ""
BOOK_NAME = ""

for i, a in enumerate(sys.argv):
    if a == "--book-id" and i + 1 < len(sys.argv):
        BOOK_ID = sys.argv[i + 1]
    if a == "--book-name" and i + 1 < len(sys.argv):
        BOOK_NAME = sys.argv[i + 1]

# 输出目录映射
TYPE_DIRS = [
    ("concept", "30_核心概念", "概念"),
    ("ke", "40_知识要素", "知识要素"),
    ("entity", "80_实体", "实体"),
    ("kp", "50_知识点", "知识点"),
    ("sp", "60_技能点", "技能点"),
    ("scene", "70_应用场景", "应用场景"),
    ("exercise", "90_习题", "习题"),
    ("solution", "90_习题/解答", "解答"),
]


def read_frontmatter(path):
    """读取 YAML frontmatter"""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except:
        return {}, ""
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, content


def extract_wikilinks(content):
    return [re.sub(r"^(\.\./)+", "", t.split("#")[0].strip())
            for t in re.findall(r"\[\[([^\|\]]+)", content)]


# 1. 扫描所有文件
files = {}  # {basename: {path, type, fm, links, chapter}}
by_chapter = defaultdict(list)
by_type_tag = defaultdict(list)
by_bloom = defaultdict(list)
by_difficulty = defaultdict(list)

for ttype, rel_dir, _ in TYPE_DIRS:
    full = os.path.join(BOOK_DIR, rel_dir)
    if not os.path.isdir(full):
        continue
    for fn in sorted(os.listdir(full)):
        if not fn.endswith(".md"):
            continue
        key = fn[:-3]
        path = os.path.join(full, fn)
        fm, content = read_frontmatter(path)
        links = [t for t in extract_wikilinks(content) if t != key]

        ch = fm.get("chapter_num", fm.get("source_chapter", ""))
        # 从文件名猜测章节
        if not ch or ch == "?":
            m_ch = re.search(r"(\d+)", key)
            ch = m_ch.group(1) if m_ch else "?"

        entry = {"path": path, "type": ttype, "fm": fm, "links": links, "chapter": ch}
        files[key] = entry
        by_chapter[ch].append(key)

        # type_tag 分类
        type_tag = fm.get("type_tag", fm.get("entity_type", ""))
        by_type_tag[type_tag].append(key)

        # bloom_level
        bl = fm.get("bloom_level", "")
        if bl:
            by_bloom[bl].append(key)

        # difficulty
        diff = fm.get("difficulty", "")
        if diff:
            by_difficulty[diff].append(key)


# 2. 统计连通性
incoming = defaultdict(set)
outgoing = {}
for key, entry in files.items():
    outgoing[key] = set(entry["links"])
    for t in entry["links"]:
        if t in files:
            incoming[t].add(key)

total_nodes = len(files)
orphan_nodes = sum(1 for k in files if len(incoming.get(k, set())) == 0)
linked_nodes = total_nodes - orphan_nodes
total_links = sum(len(v) for v in outgoing.values())
avg_links = round(total_links / max(total_nodes, 1), 1)


# 3. 生成各索引 YAML
def make_wikilink_list(keys, limit=50):
    items = []
    for k in keys[:limit]:
        if k in files:
            ch = files[k]["chapter"]
            items.append(f"- [[{k}]] (第{ch}章)" if ch and ch != "?" else f"- [[{k}]]")
    return "\n".join(items) if items else "（无）"


def make_table(entries, cols=3):
    """生成 markdown table"""
    if not entries:
        return "（无）"
    lines = []
    for i in range(0, len(entries), cols):
        row = " | ".join(f"[[{e}]]" for e in entries[i:i + cols])
        lines.append(f"| {row} |")
    return "\n".join(lines)


def format_tags(tag_keys):
    """按章节分组"""
    ch_groups = defaultdict(list)
    for k in tag_keys:
        if k in files:
            ch = files[k]["chapter"]
            ch_groups[ch].append(k)
    lines = []
    for ch in sorted(ch_groups.keys()):
        items = ", ".join(f"[[{k}]]" for k in ch_groups[ch])
        lines.append(f"### 第{ch}章\n{items}\n")
    return "\n".join(lines) if lines else "（无）"


def count_by(values, key_fn):
    counter = defaultdict(int)
    for v in values:
        counter[key_fn(v)] += 1
    return dict(counter)


# 章节分布
chapter_dist = defaultdict(list)
for key, entry in files.items():
    chapter_dist[entry["chapter"]].append(key)


# === Concept Index ===
concept_keys = [k for k, v in files.items() if v["type"] == "concept"]
ke_keys = [k for k, v in files.items() if v["type"] == "ke"]
entity_keys = [k for k, v in files.items() if v["type"] == "entity"]
kp_keys = [k for k, v in files.items() if v["type"] == "kp"]
sp_keys = [k for k, v in files.items() if v["type"] == "sp"]
scene_keys = [k for k, v in files.items() if v["type"] == "scene"]
exercise_keys = [k for k, v in files.items() if v["type"] == "exercise"]
solution_keys = [k for k, v in files.items() if v["type"] == "solution"]

print("=" * 60)
print(f"书籍: {BOOK_NAME} (ID: {BOOK_ID})")
print("=" * 60)

print(f"\n## 统计总览")
print(f"- 总节点数: {total_nodes}")
print(f"- 总链接数: {total_links} ({avg_links}/节点)")
print(f"- 有入链节点: {linked_nodes} ({linked_nodes * 100 // max(total_nodes, 1)}%)")
print(f"- 孤立节点: {orphan_nodes} ({orphan_nodes * 100 // max(total_nodes, 1)}%)")

print(f"\n## 章节分布")
for ch in sorted(chapter_dist.keys()):
    keys = chapter_dist[ch]
    types = defaultdict(int)
    for k in keys:
        types[files[k]["type"]] += 1
    type_str = ", ".join(f"{t}:{c}" for t, c in sorted(types.items()))
    print(f"- 第{ch}章: {len(keys)} 个 ({type_str})")

print(f"\n## 核心概念 ({len(concept_keys)}个)")
by_type_tag_clean = defaultdict(list)
for k in concept_keys:
    ttag = files[k]["fm"].get("type_tag", files[k]["fm"].get("entity_type", "未分类"))
    by_type_tag_clean[ttag].append(k)
for tag in sorted(by_type_tag_clean.keys()):
    ks = by_type_tag_clean[tag]
    print(f"- {tag}: {len(ks)} 个")
    for k in ks[:5]:
        ch = files[k]["chapter"]
        n_links = len(outgoing.get(k, set()))
        n_refs = len(incoming.get(k, set()))
        print(f"  - [[{k}]] (第{ch}章, 出链{n_links}, 入链{n_refs})")
    if len(ks) > 5:
        print(f"  ... 还有 {len(ks)-5} 个")

if kp_keys:
    print(f"\n## 知识点 ({len(kp_keys)}个) — Bloom层级分布")
    for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]:
        ks = [k for k in kp_keys if files[k]["fm"].get("bloom_level", "") == bl]
        if ks:
            print(f"- {bl}: {len(ks)} 个")
            for k in ks[:3]:
                print(f"  - [[{k}]]")
            if len(ks) > 3:
                print(f"  ... 还有 {len(ks)-3} 个")

# 输出 YAML 数据文件
DATA_DIR = os.path.join(BOOK_DIR, ".dag", "index_data")
os.makedirs(DATA_DIR, exist_ok=True)


def write_index_yaml(name, data):
    """将索引数据写入 YAML 文件"""
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    size = os.path.getsize(path)
    print(f"  📄 {name} ({size} bytes)")


NL = "\n"

# Book Overview YAML
by_chapter_lines = []
for ch in sorted(chapter_dist.keys()):
    ks = chapter_dist[ch]
    types = defaultdict(int)
    for k in ks:
        types[files[k]["type"]] += 1
    type_str = ", ".join(f"{c}个{t}" for t, c in sorted(types.items()))
    link_list = ", ".join(f"[[{k}]]" for k in ks[:10])
    suffix = "..." if len(ks) > 10 else ""
    by_chapter_lines.append(f"### 第{ch}章（{len(ks)}个节点, {type_str}）{NL}{link_list}{suffix}")

linked_pct = linked_nodes * 100 // max(total_nodes, 1)
orphan_pct = orphan_nodes * 100 // max(total_nodes, 1)

# Bloom distribution lines
bloom_lines = []
for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]:
    ks = [k for k in kp_keys if files[k]["fm"].get("bloom_level", "") == bl]
    if ks:
        bl_s = ", ".join(f"[[{k}]]" for k in ks[:5])
        bl_s += "..." if len(ks) > 5 else ""
        bloom_lines.append(f"- **{bl}** ({len(ks)}个): {bl_s}")

# Hub nodes
hub_lines = []
for k in sorted(files.keys(), key=lambda k: -len(incoming.get(k, set())))[:15]:
    hub_lines.append(f"- [[{k}]]: 入链{len(incoming.get(k, set()))}个")

# Type tag groups for concept index
type_tag_groups = defaultdict(list)
for k in concept_keys:
    ttag = files[k]["fm"].get("type_tag", files[k]["fm"].get("entity_type", "未分类"))
    type_tag_groups[ttag].append(k)

concept_by_chapter_text = format_tags(concept_keys)
kp_by_chapter_text = format_tags(kp_keys)
sp_by_chapter_text = format_tags(sp_keys)
scene_by_chapter_text = format_tags(scene_keys)

overview_yaml = f"""---
template_engine: ok
type: book_overview
overview_level: L2
name: {BOOK_NAME}
book_id: {BOOK_ID}
domain: 待填写
confidence: 0.90
reviewer: system
review_date: auto
tags: ["index"]
---

# {BOOK_NAME}

## 总览

**总节点数**: {total_nodes} | **总链接数**: {total_links} | **平均链接**: {avg_links}/节点
**有入链节点**: {linked_nodes}/{total_nodes} ({linked_pct}%)
**孤立节点**: {orphan_nodes}/{total_nodes} ({orphan_pct}%)

## 章节分布

{NL.join(by_chapter_lines)}

## 核心概念索引

{make_wikilink_list(concept_keys, 100)}

## 知识要素索引

{make_wikilink_list(ke_keys, 100)}

## 实体索引

{make_wikilink_list(entity_keys, 100)}

## 知识点索引 (按Bloom层级)

{NL.join(bloom_lines)}

## 技能点索引

{make_wikilink_list(sp_keys, 50)}

## 应用场景索引

{make_wikilink_list(scene_keys, 50)}

## 枢纽节点 (入链最多)

{NL.join(hub_lines)}
"""

write_index_yaml("book_overview.yaml", overview_yaml)

# Concept Index YAML
concept_index_yaml = f"""---
template_engine: ok
type: concept_index
name: 核心概念索引 - {BOOK_NAME}
book_id: {BOOK_ID}
confidence: 0.90
reviewer: system
review_date: auto
tags: ["index"]
---

# 核心概念索引 - {BOOK_NAME}

## 按 Type Tag 分类

{NL.join(f"### {tag}{NL}{make_wikilink_list(ks)}" for tag, ks in sorted(type_tag_groups.items()))}

## 按章节分类

{concept_by_chapter_text}

## 统计

- 总概念数: {len(concept_keys)}
"""
write_index_yaml("concept_index.yaml", concept_index_yaml)

# Knowledge Index YAML
bloom_groups = {bl: [k for k in kp_keys if files[k]["fm"].get("bloom_level", "") == bl]
                for bl in ["记忆", "理解", "应用", "分析", "评价", "创造"]}

bloom_sections = []
for bl, ks in bloom_groups.items():
    if ks:
        bloom_sections.append(f"### {bl}{NL}{make_wikilink_list(ks)}")

bloom_dist = ", ".join(f"{bl}:{len(ks)}" for bl, ks in bloom_groups.items() if ks)

knowledge_index_yaml = f"""---
template_engine: ok
type: knowledge_index
name: 知识点索引 - {BOOK_NAME}
book_id: {BOOK_ID}
confidence: 0.90
reviewer: system
review_date: auto
tags: ["index"]
---

# 知识点索引 - {BOOK_NAME}

## 按认知层级分类

{NL.join(bloom_sections)}

## 按章节分类

{kp_by_chapter_text}

## 统计

- 总知识点数: {len(kp_keys)}
- 按认知层级分布: {bloom_dist}
"""
write_index_yaml("knowledge_index.yaml", knowledge_index_yaml)

# Skill Index YAML
skill_index_yaml = f"""---
template_engine: ok
type: skill_index
name: 技能点索引 - {BOOK_NAME}
book_id: {BOOK_ID}
confidence: 0.90
reviewer: system
review_date: auto
tags: ["index"]
---

# 技能点索引 - {BOOK_NAME}

## 按章节分类

{sp_by_chapter_text}

## 统计

- 总技能点数: {len(sp_keys)}
"""
write_index_yaml("skill_index.yaml", skill_index_yaml)

# Scene Index YAML
scenario_index_yaml = f"""---
template_engine: ok
type: scenario_index
name: 应用场景索引 - {BOOK_NAME}
book_id: {BOOK_ID}
confidence: 0.90
reviewer: system
review_date: auto
tags: ["index"]
---

# 应用场景索引 - {BOOK_NAME}

## 按章节分类

{scene_by_chapter_text}

## 统计

- 总应用场景数: {len(scene_keys)}
"""
write_index_yaml("scenario_index.yaml", scenario_index_yaml)

print(f"\n✅ 指数数据已写入: {DATA_DIR}")
