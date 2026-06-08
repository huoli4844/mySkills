#!/usr/bin/env python3
"""
link_audit.py — 知识链接审计工具（v52.0 替代 KGraph）

纯文本扫描，不依赖 SQLite，提供：
  1. 孤立节点检测（入度=0）
  2. 反向链接补全（A→B 但 B↛A）
  3. 跨章引用统计 → L2 索引增强数据

集成到 pipeline：scene done → l2_indices 之前自动运行。
"""

import os
import re
from collections import defaultdict, Counter
from log_utils import get_logger

log = get_logger(__name__)

# ── 节点目录映射（与 DIR_BY_PHASE 保持一致）────────────────────
TYPE_DIRS = {
    "concept": "30_核心概念",
    "ke": "40_知识要素",
    "kp": "50_知识点",
    "sp": "60_技能点",
    "scene": "70_应用场景",
    "entity": "80_实体",
    "exercise": "90_习题",
    "solution": "90_习题/解答",
}


def _collect_md_files(wiki_root: str) -> dict[str, str]:
    """扫描所有节点目录，返回 {文件名(去.md): 绝对路径}"""
    files = {}
    for _type, rel_dir in TYPE_DIRS.items():
        full_dir = os.path.join(wiki_root, rel_dir)
        if not os.path.isdir(full_dir):
            continue
        for fname in os.listdir(full_dir):
            if not fname.endswith(".md"):
                continue
            key = fname[:-3]
            files[key] = os.path.join(full_dir, fname)
    return files


def _read_content(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _extract_wikilinks(content: str) -> list[str]:
    """从内容中提取所有 [[target]] 目标名（去掉 #片段和 |显示名）"""
    links = re.findall(r"\[\[([^\]|]+)", content)
    return [link.split("#")[0].strip() for link in links]


# ── 公开 API ────────────────────────────────────────────────


def check_orphan_nodes(wiki_root: str, min_nodes: int = 3) -> dict:
    """查找入度 = 0 的孤立节点。

    Returns:
        {"orphans": [文件名], "total_nodes": N, "orphan_pct": float}
    """
    files = _collect_md_files(wiki_root)
    if len(files) < min_nodes:
        return {"orphans": [], "total_nodes": 0, "orphan_pct": 0.0}

    incoming = defaultdict(int)
    for fname, fpath in files.items():
        content = _read_content(fpath)
        for target in _extract_wikilinks(content):
            incoming[target] += 1

    orphans = [f for f in files if incoming.get(f, 0) == 0]
    pct = round(len(orphans) / len(files) * 100, 1) if files else 0.0

    if orphans:
        log.warning(f"[link_audit] 发现 {len(orphans)} 个孤立节点 ({pct}%): {orphans[:8]}...")

    return {"orphans": sorted(orphans), "total_nodes": len(files), "orphan_pct": pct}


def check_backlink_symmetry(wiki_root: str, min_nodes: int = 3) -> dict:
    """查找 A→B 但 B↛A 的非对称链接。

    Returns:
        {"asymmetric": [(A, B), ...], "total_pairs": N}
    """
    files = _collect_md_files(wiki_root)
    if len(files) < min_nodes:
        return {"asymmetric": [], "total_pairs": 0}

    links = {}  # {source: [targets]}
    for fname, fpath in files.items():
        content = _read_content(fpath)
        targets = [t for t in _extract_wikilinks(content) if t in files]
        links[fname] = set(targets)

    asymmetric = []
    for src, targets in links.items():
        for tgt in targets:
            if tgt in links and src not in links[tgt]:
                asymmetric.append((src, tgt))

    if asymmetric:
        log.info(f"[link_audit] 发现 {len(asymmetric)} 对非对称链接（A→B 但 B↛A）")

    return {"asymmetric": asymmetric[:50], "total_pairs": len(asymmetric)}


def check_cross_chapter_links(wiki_root: str) -> dict:
    """统计跨章引用数据，用于 L2 索引增强。

    Returns:
        {
            "cross_refs": {源章节: {目标章节: count}},
            "hub_nodes": [(入度, 文件名), ...],  # 按引用数降序
            "chapters": {"1": "第1章 概述", ...}
        }
    """
    # 首先解析章节
    chapter_map = {}
    src_dir = os.path.join(wiki_root, "20_正文")
    if os.path.isdir(src_dir):
        for fname in sorted(os.listdir(src_dir)):
            m = re.match(r"第(\d+)章\s+(.+)\.md$", fname)
            if m:
                chapter_map[m.group(1)] = f"第{m.group(1)}章 {m.group(2)}"

    files = _collect_md_files(wiki_root)
    if not files:
        return {"cross_refs": {}, "hub_nodes": [], "chapters": chapter_map}

    # 获取每个文件的章节号（从 frontmatter 或文件名前缀）
    incoming = Counter()
    cross_refs = defaultdict(lambda: defaultdict(int))

    for fname, fpath in files.items():
        content = _read_content(fpath)
        ch = "?"
        # 尝试从文件名前缀提取章节（第N章-xxx → N）
        m_ch = re.match(r"第(\d+)章", fname)
        if m_ch:
            ch = m_ch.group(1)

        for target in _extract_wikilinks(content):
            incoming[target] += 1
            # 跨章判断
            m_tgt = re.match(r"第(\d+)章", target)
            if m_tgt and m_tgt.group(1) != ch:
                cross_refs[ch][m_tgt.group(1)] += 1

    top_hubs = [(cnt, name) for name, cnt in incoming.most_common(20) if name in files]

    return {
        "cross_refs": {k: dict(v) for k, v in cross_refs.items()},
        "hub_nodes": [(cnt, name) for cnt, name in top_hubs],
        "chapters": chapter_map,
    }


def auto_fix_backlinks(wiki_root: str, dry_run: bool = True) -> dict:
    """自动补全非对称链接（A→B 但 B↛A 时，在 B 尾部追加 [[A]]）。

    Returns:
        {"fixed": int, "files_modified": [文件名]}
    """
    result = check_backlink_symmetry(wiki_root)
    if result["total_pairs"] == 0:
        return {"fixed": 0, "files_modified": []}

    files = _collect_md_files(wiki_root)
    modified = set()

    for src, tgt in result["asymmetric"]:
        tgt_path = files.get(tgt)
        if not tgt_path or tgt in modified:
            continue
        if dry_run:
            continue
        content = _read_content(tgt_path)
        if f"[[{src}]]" in content:
            continue
        # 在文件末尾追加反向链接（在"关联资源"节中）
        backlink = f"\n- [[{src}]]\n"
        if "## 关联资源" in content:
            content = content.replace("## 关联资源", f"## 关联资源\n\n- [[{src}]]\n", 1)
        else:
            content += f"\n## 关联资源\n\n- [[{src}]]\n"
        with open(tgt_path, "w", encoding="utf-8") as f:
            f.write(content)
        modified.add(tgt)

    if not dry_run:
        log.info(f"[link_audit] 自动补全 {len(modified)} 个文件的反向链接")

    return {"fixed": len(modified), "files_modified": sorted(modified)}


def run_link_audit(wiki_root: str, chapter: str | None = None, auto_fix: bool = False) -> dict:
    """统一运行入口，集成到 pipeline auto 中。

    Args:
        wiki_root: 知识库根目录
        chapter: 章节号（可选，用于限定范围）
        auto_fix: 是否自动补全反向链接

    Returns:
        {
            "orphans": {...},
            "backlinks": {...},
            "cross_refs": {...},
            "auto_fixed": int,
        }
    """
    result = {
        "orphans": check_orphan_nodes(wiki_root),
        "backlinks": check_backlink_symmetry(wiki_root),
        "cross_refs": check_cross_chapter_links(wiki_root),
        "auto_fixed": 0,
    }

    if auto_fix:
        fix = auto_fix_backlinks(wiki_root, dry_run=False)
        result["auto_fixed"] = fix["fixed"]

    # 汇总日志
    o = result["orphans"]
    if o["orphans"]:
        log.warning(f"[link_audit] 孤立节点: {o['orphan_pct']}% ({len(o['orphans'])} 个)")
    b = result["backlinks"]
    if b["asymmetric"]:
        log.info(f"[link_audit] 非对称链接: {b['total_pairs']} 对")
    c = result["cross_refs"]
    if c["hub_nodes"]:
        top = c["hub_nodes"][:5]
        log.info(f"[link_audit] 枢纽节点: {', '.join(f'{n}({c})' for c, n in top)}")

    return result


if __name__ == "__main__":
    import sys
    wiki_root = sys.argv[1] if len(sys.argv) > 1 else "."
    dry = "--dry-run" in sys.argv
    if dry:
        sys.argv.remove("--dry-run")

    result = run_link_audit(wiki_root, auto_fix=not dry)

    print(f"\n孤立节点: {result['orphans']['orphan_pct']}% ({len(result['orphans']['orphans'])} 个)")
    if result["orphans"]["orphans"]:
        for f in result["orphans"]["orphans"][:10]:
            print(f"  ⚠️  {f}")
    print(f"\n非对称链接: {result['backlinks']['total_pairs']} 对")
    print(f"枢纽节点: {len(result['cross_refs']['hub_nodes'])} 个")
    if result["auto_fixed"]:
        print(f"自动补全: {result['auto_fixed']} 个文件")
