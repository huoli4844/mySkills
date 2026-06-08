#!/usr/bin/env python3
"""wikilink_deep_fixer.py — 基于章节归属自动关联内容节点

策略：
  1. 读取所有文件 YAML frontmatter，提取 chapter_num 和 tags
  2. 对出链=0的内容节点，自动关联同章节的相关节点
  3. 关联规则（按优先级）：
     a) 概念 → 同章节的 KE、实体
     b) KE → 同章节的概念、实体、KP
     c) 实体 → 同章节的概念、KE
     d) 知识点 → 同章节的 KE、概念
"""

import os, re, sys, json
from collections import defaultdict

WIKI = sys.argv[1] if len(sys.argv) > 1 else "."

TYPE_DIRS = [
    ("concept", "30_核心概念"),
    ("ke", "40_知识要素"),
    ("entity", "80_实体"),
    ("kp", "50_知识点"),
    ("sp", "60_技能点"),
    ("scene", "70_应用场景"),
    ("exercise", "90_习题"),
    ("solution", "90_习题/解答"),
]

LEAF_DIRS = {"90_习题/解答", "90_习题"}


def read_frontmatter(path):
    """读取 YAML frontmatter 返回 dict"""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return {}, ""
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, content


def extract_wikilinks(content):
    """提取所有 [[target]] 目标"""
    return [re.sub(r"^(\.\./)+", "", t.split("#")[0].strip())
            for t in re.findall(r"\[\[([^\|\]]+)", content)]


# 收集所有文件信息
files = {}
fm_cache = {}
content_cache = {}

for ttype, rel_dir in TYPE_DIRS:
    full = os.path.join(WIKI, rel_dir)
    if not os.path.isdir(full):
        continue
    for fn in sorted(os.listdir(full)):
        if not fn.endswith(".md"):
            continue
        key = fn[:-3]
        path = os.path.join(full, fn)
        fm, content = read_frontmatter(path)
        files[key] = {"type": ttype, "dir": rel_dir, "path": path}
        fm_cache[key] = fm
        content_cache[key] = content

# 按章节建立索引
by_chapter = defaultdict(lambda: defaultdict(list))
for key, info in files.items():
    ch = fm_cache[key].get("chapter_num", "?")
    by_chapter[ch][info["type"]].append(key)

# 关联规则: {源类型: [(目标类型, 优先级权重, 说明)]}
LINK_RULES = {
    "concept": [("ke", 3, "同章KE"), ("entity", 2, "同章实体"), ("kp", 1, "同章KP")],
    "ke": [("concept", 3, "同章概念"), ("entity", 2, "同章实体"), ("kp", 1, "同章KP")],
    "entity": [("concept", 3, "同章概念"), ("ke", 2, "同章KE")],
    "kp": [("ke", 3, "同章KE"), ("concept", 2, "同章概念"), ("entity", 1, "同章实体")],
}

# 计算出入链
incoming = defaultdict(set)
outgoing = {}
for key in files:
    links = [t for t in extract_wikilinks(content_cache[key]) if t in files]
    outgoing[key] = set(links)
    for t in links:
        incoming[t].add(key)

# 找出需要修复的节点
to_fix = [(key, info) for key, info in sorted(files.items())
          if len(outgoing.get(key, set())) == 0
          and info["dir"] not in LEAF_DIRS
          and not key.startswith("book_overview_")]

print(f"需要修复: {len(to_fix)} 个内容节点\n")

fixed = 0
for key, info in to_fix:
    ch = fm_cache[key].get("chapter_num", "")
    path = info["path"]
    content = content_cache[key]

    # 确定关联目标
    link_targets = []
    rules = LINK_RULES.get(info["type"], [])
    for tgt_type, priority, desc in rules:
        candidates = by_chapter.get(ch, {}).get(tgt_type, [])
        for c in candidates:
            if c != key and c not in outgoing.get(key, set()):
                # 检查是否已存在于内容中
                if f"[[{c}]]" not in content and f"[[{c}|" not in content:
                    link_targets.append((c, priority, desc))

    if not link_targets:
        continue

    # 按优先级排序，最多取8个
    link_targets.sort(key=lambda x: -x[1])
    top_targets = link_targets[:8]

    wikilinks = "\n".join(f"- [[{t[0]}]]" for t in top_targets)
    link_note = f"\n<!-- 关联: {'同章' + ch + '章' if ch else '同领域'} -->\n{wikilinks}"

    if "## 关联资源" in content:
        # 在 关联资源 末尾追加（在最后一个 wikilink 之后或节尾）
        lines = content.split("\n")
        insert_pos = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("## ") and "关联资源" in lines[i]:
                insert_pos = i + 1
                break
        for i in range(insert_pos, len(lines)):
            if lines[i].strip().startswith("## "):
                insert_pos = i
                break
        lines.insert(insert_pos, wikilinks)
        lines.insert(insert_pos, f"<!-- 关联: 同章{ch}章 -->")
        new_content = "\n".join(lines)
    else:
        new_content = content.rstrip() + f"\n\n## 关联资源\n{link_note}\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    fixed += 1

    if fixed <= 5:
        print(f"  ✅ {key} ({info['type']}): +{len(top_targets)} 链接 → {[t[0] for t in top_targets]}")

print(f"\n修复统计:")
print(f"  修改文件: {fixed}/{len(to_fix)}")
print(f"  总计新增 wikilink: {sum(len([t for t in LINK_RULES.get(files[k]['type'], []) if by_chapter.get(fm_cache[k].get('chapter_num',''), {}).get(t[0], [])]) for k,_ in to_fix if k)} (约数)")

# 最终验证
print("\n" + "=" * 60)
print("最终验证")
print("=" * 60)

incoming2, outgoing2 = defaultdict(set), {}
for key in files:
    with open(files[key]["path"], encoding="utf-8") as f:
        content = f.read()
    links = [t for t in extract_wikilinks(content) if t in files]
    outgoing2[key] = set(links)
    for t in links:
        incoming2[t].add(key)

non_leaf = {k for k, v in files.items() if v["dir"] not in LEAF_DIRS and not k.startswith("book_overview_")}
orphans = sum(1 for k in non_leaf if len(incoming2.get(k, set())) == 0)
zero_out = sum(1 for k in non_leaf if len(outgoing2.get(k, set())) == 0)
total_non_leaf = len(non_leaf)
print(f"  非叶子节点: {total_non_leaf}")
print(f"  孤立(无入链): {orphans} ({orphans*100//total_non_leaf}%)")
print(f"  出链为0: {zero_out} ({zero_out*100//total_non_leaf}%)")
print(f"  非对称链接: {sum(1 for s in files for t in outgoing2.get(s,set()) if t not in outgoing2 or s not in outgoing2[t])} 对")
