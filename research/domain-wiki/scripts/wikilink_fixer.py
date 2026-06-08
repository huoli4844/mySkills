#!/usr/bin/env python3
"""wikilink_fixer.py — 全面修复 wikilink 双向引用

策略：
  1. 收集所有文件及其出链
  2. 对每个非叶子文件，补全缺失的反向链接（A→B 则 B 应回链 A）
  3. 对出链=0的内容节点（概念/KE/实体），尝试从被引用推测关联
"""

import os, re, sys
from collections import defaultdict

WIKI = sys.argv[1] if len(sys.argv) > 1 else "."
DRY_RUN = "--dry-run" in sys.argv

TYPE_DIRS = {
    "concept": "30_核心概念", "ke": "40_知识要素", "kp": "50_知识点",
    "sp": "60_技能点", "scene": "70_应用场景", "entity": "80_实体",
    "exercise": "90_习题", "solution": "90_习题/解答", "overview": "10_总揽",
}

# 被认为"不需要入链"的目录（叶子节点）
LEAF_DIRS = {"90_习题/解答", "90_习题", "10_总揽", "60_技能点", "70_应用场景"}


def get_dir_type(rel_dir):
    for t, d in TYPE_DIRS.items():
        if d == rel_dir:
            return t
    return "unknown"


def collect_files(wiki_root):
    files = {}
    for rel_dir in TYPE_DIRS.values():
        full = os.path.join(wiki_root, rel_dir)
        if not os.path.isdir(full):
            continue
        for fname in sorted(os.listdir(full)):
            if not fname.endswith(".md"):
                continue
            key = fname[:-3]
            files[key] = {"path": os.path.join(full, fname), "dir": rel_dir}
    return files


def extract_wikilinks(content):
    return [t.split("#")[0].strip() for t in re.findall(r"\[\[([^\]|]+)", content)]


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"  读取失败 {path}: {e}")
        return ""


def is_leaf(key, info):
    """判断是否为叶子节点（不需要入链）"""
    if info["dir"] in LEAF_DIRS:
        return True
    if key.startswith("book_overview_"):
        return True
    return False


def add_backlinks_to_file(path, missing_backlinks):
    """在文件的 关联资源 节追加缺失的反向链接"""
    content = read_file(path)
    if not content:
        return False

    # 去重，排除已存在的链接
    existing_links = extract_wikilinks(content)
    to_add = [b for b in missing_backlinks if b not in existing_links]
    if not to_add:
        return False

    # 按优先级排序：概念 > KE > 实体 > 其他
    def sort_key(b):
        if b in files:
            d = files[b]["dir"]
            if d == "30_核心概念": return 0
            if d == "40_知识要素": return 1
            if d == "80_实体": return 2
            if d == "50_知识点": return 3
        return 5
    to_add.sort(key=sort_key)

    backlink_text = "\n" + "\n".join(f"- [[{b}]]" for b in to_add)

    if "## 关联资源" in content:
        # 在 关联资源 节末尾追加
        content = content.replace("## 关联资源", "## 关联资源" + backlink_text, 1)
    else:
        content += f"\n## 关联资源\n{backlink_text}\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


# ── 主流程 ──
files = collect_files(WIKI)
incoming = defaultdict(set)
outgoing = {}
content_map = {}

for key, info in files.items():
    content_map[key] = read_file(info["path"])
    outgoing[key] = set()

for key, content in content_map.items():
    for target in extract_wikilinks(content):
        t_clean = re.sub(r"^(\.\./)+", "", target)
        if t_clean in files:
            outgoing[key].add(t_clean)
            incoming[t_clean].add(key)

stats = {"fixed": 0, "files": 0, "asymmetric_fixed": 0, "orphan_fixed": 0}

# Phase 1: 补全非对称链接（A→B 但 B↛A）
print("=" * 60)
print("Phase 1: 非对称链接修复")
print("=" * 60)

asymmetric = defaultdict(list)
for src, targets in outgoing.items():
    for tgt in targets:
        if tgt not in outgoing or src not in outgoing[tgt]:
            if not is_leaf(tgt, files.get(tgt, {})):
                asymmetric[tgt].append(src)

print(f"发现 {sum(len(v) for v in asymmetric.values())} 对非对称链接"
      f"（涉及 {len(asymmetric)} 个目标文件）")

batch = 0
for tgt, sources in sorted(asymmetric.items()):
    if tgt not in files:
        continue
    info = files[tgt]
    path = info["path"]
    added = add_backlinks_to_file(path, sources)
    if added:
        stats["asymmetric_fixed"] += len(sources)
        stats["files"] += 1

if DRY_RUN:
    print(f"🟡 DRY-RUN: 将修复 {stats['files']} 个文件, {stats['asymmetric_fixed']} 对链接")
    sys.exit(0)

# Phase 2: 补全出链=0的内容节点的基础关联
print("\n" + "=" * 60)
print("Phase 2: 0出链内容节点修复")
print("=" * 60)

zero_out_link_content = []
for key, info in files.items():
    if info["dir"] in LEAF_DIRS:
        continue
    if len(outgoing.get(key, set())) == 0:
        # 被谁引用了？用引用者作为关联源
        refs = incoming.get(key, set())
        zero_out_link_content.append((key, info, refs))

print(f"发现 {len(zero_out_link_content)} 个内容节点出链为 0")

for key, info, refs in sorted(zero_out_link_content):
    path = info["path"]
    # 如果被别人引用了，反向链接回去
    if refs:
        add_backlinks_to_file(path, list(refs))
        stats["orphan_fixed"] += 1

# 统计
print("\n" + "=" * 60)
print("修复报告")
print("=" * 60)
print(f"  Phase 1 修复: {stats['files']} 个文件")
print(f"    新增反向链接: {stats['asymmetric_fixed']} 条")
print(f"  Phase 2 修复: {stats['orphan_fixed']} 个内容节点")

# 最终状态
incoming2 = defaultdict(set)
outgoing2 = {}
for key, content in content_map.items():
    content2 = read_file(files[key]["path"])
    outgoing2[key] = set()
    for target in extract_wikilinks(content2):
        t_clean = re.sub(r"^(\.\./)+", "", target)
        if t_clean in files:
            outgoing2[key].add(t_clean)
            incoming2[t_clean].add(key)

total = len(files)
orphans = sum(1 for k in files if len(incoming2.get(k, set())) == 0 and not is_leaf(k, files[k]))
asym = sum(1 for s in files for t in outgoing2.get(s, set())
           if t not in outgoing2 or s not in outgoing2[t])
print(f"\n最终状态:")
print(f"  总文件: {total}")
print(f"  非叶子孤立节点: {orphans} 个")
print(f"  非对称链接: {asym} 对")
print(f"  孤立节点(含叶子): {sum(1 for k in files if len(incoming2.get(k, set()))==0)} 个")
