#!/usr/bin/env python3
"""_sidebar.md 生成器 — Obsidian 侧边栏导航

用法:
  python3 generate_sidebar.py --book-dir /path/to/book --book-id 01_foo
"""

import argparse
import os
import sys

from log_utils import get_logger

log = get_logger(__name__)


_sd = os.path.dirname(os.path.abspath(__file__))
if _sd not in sys.path:
    sys.path.insert(0, _sd)
from dag_constants import DIR  # noqa: E402
from dag_state import get_wiki_root  # noqa: E402


def generate_sidebar(book_dir, book_name):
    """生成 Obsidian _sidebar.md"""
    lines = ["# 知识库导航", ""]

    # L2 总揽链接
    overview_dir = os.path.join(book_dir, DIR["OVERVIEW"])
    if os.path.isdir(overview_dir):
        lines.append("## 📖 本书总揽")
        for f in sorted(os.listdir(overview_dir)):
            if f.endswith(".md"):
                name = f.replace(".md", "")
                lines.append(f"- [[10_总揽/{name}|{name}]]")
        lines.append("")

    # 索引链接
    index_dirs = [
        (DIR["CONCEPTS"], "📘 核心概念"),
        (DIR["KE"], "📐 知识要素"),
        (DIR["KP"], "📗 知识点"),
        (DIR["SP"], "📙 技能点"),
        (DIR["SCENE"], "📕 应用场景"),
        (DIR["ENTITIES"], "📦 实体"),
        (DIR["EXERCISES"], "📝 习题"),
    ]

    for subdir, title in index_dirs:
        full = os.path.join(book_dir, subdir)
        if os.path.isdir(full):
            md_files = sorted([f for f in os.listdir(full) if f.endswith(".md")])
            if md_files:
                lines.append(f"## {title}")
                for f in md_files[:20]:  # max 20 per section
                    name = f.replace(".md", "")
                    lines.append(f"- [[{subdir}/{name}|{name}]]")
                if len(md_files) > 20:
                    lines.append(f"  ... 还有 {len(md_files)-20} 项")
                lines.append("")

    # L3/L4 links
    wiki_root = get_wiki_root(book_dir)
    domain_ctrl = os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"])
    if os.path.isdir(domain_ctrl):
        lines.append("## 🌐 领域总控")
        for f in sorted(os.listdir(domain_ctrl)):
            if f.endswith(".md"):
                name = f.replace(".md", "")
                lines.append(f"- [[../../{DIR['FIELD']}/{DIR['DOMAIN_CTRL']}/{name}|{name}]]")

    kb_ctrl = os.path.join(wiki_root, DIR["KB_CTRL"])
    if os.path.isdir(kb_ctrl):
        lines.append("")
        lines.append("## 🏛 知识库总控")
        for f in sorted(os.listdir(kb_ctrl)):
            if f.endswith(".md"):
                name = f.replace(".md", "")
                lines.append(f"- [[../../{DIR['KB_CTRL']}/{name}|{name}]]")

    content = "\n".join(lines) + "\n"
    out_path = os.path.join(book_dir, "_sidebar.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    log.success(f"  ✅ _sidebar.md 已生成 → {out_path}")
    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--book-dir", required=True)
    p.add_argument("--book-name", default="知识库")
    args = p.parse_args()
    generate_sidebar(args.book_dir, args.book_name)
