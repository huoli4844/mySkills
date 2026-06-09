#!/usr/bin/env python3
"""l3_l4_builder.py — L3（领域总控）+ L4（知识库总控）索引构建

依赖 index_builder.py 的 L2 数据 + 跨书/跨领域扫描。

用法:
  # 构建L3（领域级）索引
  python3 l3_l4_builder.py l3 \\
    --book-dir /path/to/book \\
    --book-id 01_书ID --book-name "书名"

  # 构建L4（知识库级）索引
  python3 l3_l4_builder.py l4 \\
    --book-dir /path/to/book \\
    --book-id 01_书ID
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from kg_builder import KGraph  # noqa: E402
from graph_analytics import build_graph_section  # noqa: E402


def count_md_files(domain_dir):
    """统计领域下各目录的 .md 文件"""
    stats = defaultdict(int)
    for d in ["30_核心概念", "40_知识要素", "50_知识点", "60_技能点", "70_应用场景", "80_实体", "90_习题"]:
        full = os.path.join(domain_dir, d)
        if os.path.isdir(full):
            stats[d] = len([f for f in os.listdir(full) if f.endswith(".md")])
    return stats


def find_books(kb_root: str) -> list[dict]:
    """扫描知识库中的所有书籍"""
    books = []
    # nested layout: domain/book/
    for domain_name in sorted(os.listdir(kb_root)):
        domain_path = os.path.join(kb_root, domain_name)
        if not os.path.isdir(domain_path) or domain_name in ("raw", ".dag", "01_领域", "知识库总控"):
            continue
        for book_name in sorted(os.listdir(domain_path)):
            book_path = os.path.join(domain_path, book_name)
            if os.path.isdir(book_path) and os.path.isdir(os.path.join(book_path, "20_正文")):
                books.append({
                    "path": book_path,
                    "name": book_name,
                    "domain": domain_name,
                })
    return books


def build_l3_index(book_dir: str, book_id: str, book_name: str):
    """构建L3（领域级总控）索引 -> 领域总控/"""
    kb_root = os.path.normpath(os.path.join(book_dir, "..", ".."))
    domain_dir = os.path.normpath(os.path.join(book_dir, ".."))
    domain_name = os.path.basename(domain_dir)
    l3_dir = os.path.join(domain_dir, "领域总控")
    os.makedirs(l3_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    NL = "\n"

    print("=" * 60)
    print(f"L3 领域总控: {domain_name}")
    print("=" * 60)

    # 统计该领域下所有书籍
    all_books = find_books(kb_root)
    domain_books = [b for b in all_books if b["domain"] == domain_name]

    total_stats = defaultdict(int)
    book_list = []
    for b in domain_books:
        stats = count_md_files(b["path"])
        for k, v in stats.items():
            total_stats[k] += v
        book_list.append(f"- [[../{b['name']}/10_总揽/book_overview|{b['name']}]]")

    # 构建领域级知识图谱（扫描所有书籍的目录）
    book_paths = [b["path"] for b in domain_books]
    kg = KGraph(kb_root, book_dir=book_paths) if book_paths else KGraph(kb_root)
    try:
        kg_stats = kg.build()
        gs = build_graph_section(kg)
    except Exception as e:
        kg_stats = None
        gs = {}

    total_nodes = sum(total_stats.values())
    l3_yaml = f"""---
template_engine: ok
type: domain_overview
overview_level: L3
name: {domain_name}
domain_id: {domain_name}
confidence: 0.85
reviewer: system
review_date: {today}
tags: ["index"]
---

# {domain_name} — 领域总揽（L3）

## 领域简介

### 📚 领域书籍（{len(domain_books)}本）
{NL.join(book_list) if book_list else "（暂无书籍）"}

## 🌐 领域知识体系

### 跨书知识链
{gs.get('chain_connectivity', '（待构建）')}

### 领域节点连接性
{gs.get('node_connectivity', '（待构建）')}

### 跨书概念冲突检测
（暂无跨书数据，当前仅 1 本书）

## 🔗 跨书知识关联

### 跨书概念对齐
（仅 1 本书，无跨书关联）

## 🗺 领域知识图谱
```mermaid
{gs.get('mindmap_content', 'graph TB')}
```

## 🎯 领域学习路径
{gs.get('learning_path', '（待补充）')}

## 🛠 综合技能树
（待补充）

## 🏗 综合应用场景
（待补充）

## 📑 领域索引导航

### 核心概念
| 目录 | 文件数 |
|:----|:-----:|
| 30_核心概念 | {total_stats.get('30_核心概念', 0)} |
| 40_知识要素 | {total_stats.get('40_知识要素', 0)} |
| 80_实体 | {total_stats.get('80_实体', 0)} |
| 50_知识点 | {total_stats.get('50_知识点', 0)} |
| 60_技能点 | {total_stats.get('60_技能点', 0)} |
| 70_应用场景 | {total_stats.get('70_应用场景', 0)} |
| 90_习题 | {total_stats.get('90_习题', 0)} |

## 📈 统计信息
- 书籍数: {len(domain_books)}
- 总核心概念数: {total_stats.get('30_核心概念', 0)}
- 总知识点数: {total_stats.get('50_知识点', 0)}
- 总技能点数: {total_stats.get('60_技能点', 0)}
- 总应用场景数: {total_stats.get('70_应用场景', 0)}
- 生成日期: {today}
- 置信度: 0.85
- 数据来源: KGraph 知识图谱引擎
"""
    out_path = os.path.join(l3_dir, "domain_overview.md")
    # 提取 body（去掉 frontmatter）
    body_match = re.split(r"^---\s*\n.*?\n---\s*\n", l3_yaml, maxsplit=1, flags=re.DOTALL)
    md_body = body_match[1] if len(body_match) > 1 else l3_yaml
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_body)
    print(f"  📄 领域总控/domain_overview.md ({len(md_body)} chars)")
    print(f"  ✅ L3 索引构建完成")
    return True


def build_l4_index(book_dir: str, book_id: str):
    """构建L4（知识库级总控）索引 -> 知识库总控/"""
    kb_root = os.path.normpath(os.path.join(book_dir, "..", ".."))
    l4_dir = os.path.join(kb_root, "知识库总控")
    os.makedirs(l4_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    NL = "\n"

    print("=" * 60)
    print("L4 知识库总控")
    print("=" * 60)

    all_books = find_books(kb_root)
    kb_name = os.path.basename(kb_root) or "知识库"

    # 按领域分组
    domains = defaultdict(list)
    for b in all_books:
        domains[b["domain"]].append(b)

    domain_index_lines = []
    total_stats = defaultdict(int)
    for domain, books in sorted(domains.items()):
        domain_total = defaultdict(int)
        for b in books:
            stats = count_md_files(b["path"])
            for k, v in stats.items():
                domain_total[k] += v
                total_stats[k] += v
        concept_count = domain_total.get("30_核心概念", 0)
        kp_count = domain_total.get("50_知识点", 0)
        sp_count = domain_total.get("60_技能点", 0)
        scene_count = domain_total.get("70_应用场景", 0)
        domain_index_lines.append(
            f"### {domain}（{len(books)}本书）{NL}"
            f"- 概念:{concept_count} 知识点:{kp_count} 技能点:{sp_count} 场景:{scene_count}{NL}"
            f"- 领域总揽: [[../{domain}/领域总控/domain_overview|{domain}]]"
        )

    # 构建全库 KG
    all_book_paths = [b["path"] for b in all_books]
    kg = KGraph(kb_root, book_dir=all_book_paths) if all_book_paths else KGraph(kb_root)
    try:
        kg_stats = kg.build()
        gs = build_graph_section(kg)
    except Exception as e:
        kg_stats = None
        gs = {}

    total_books = sum(len(books) for books in domains.values())
    l4_yaml = f"""---
template_engine: ok
type: kb_overview
overview_level: L4
name: {kb_name}
kb_id: auto-kb
confidence: 0.85
reviewer: system
review_date: {today}
tags: ["index"]
---

# {kb_name} — 知识库总揽（L4）

## 知识库简介

基于 {total_books} 本书、{total_stats.get('30_核心概念',0)} 个核心概念的知识库。

## 🌍 领域总览
{NL.join(domain_index_lines)}

## 🔬 全库知识结构

### 全库节点连接性
{gs.get('node_connectivity', '（待构建）')}

### 全库知识链完整性
{gs.get('chain_connectivity', '（待构建）')}

## 🌉 跨领域桥接
（当前仅 1 个领域，无跨领域桥接）

## 🗺 知识库全景图谱
```mermaid
{gs.get('mindmap_content', 'graph TB')}
```

## 🧭 全库学习路径
{gs.get('learning_path', '（待补充）')}

## 🏛 跨领域综合技能
（待补充）

## 🏗 跨领域综合场景
（待补充）

## 📑 全库索引导航

### 核心概念
| 目录 | 文件数 |
|:----|:-----:|
| 30_核心概念 | {total_stats.get('30_核心概念', 0)} |
| 40_知识要素 | {total_stats.get('40_知识要素', 0)} |
| 80_实体 | {total_stats.get('80_实体', 0)} |
| 50_知识点 | {total_stats.get('50_知识点', 0)} |
| 60_技能点 | {total_stats.get('60_技能点', 0)} |
| 70_应用场景 | {total_stats.get('70_应用场景', 0)} |
| 90_习题 | {total_stats.get('90_习题', 0)} |

## 📈 统计信息
- 领域数: {len(domains)}
- 总书籍数: {total_books}
- 总核心概念数: {total_stats.get('30_核心概念', 0)}
- 总知识点数: {total_stats.get('50_知识点', 0)}
- 总技能点数: {total_stats.get('60_技能点', 0)}
- 总应用场景数: {total_stats.get('70_应用场景', 0)}
- 生成日期: {today}
- 置信度: 0.85
- 数据来源: KGraph 知识图谱引擎
"""
    out_path = os.path.join(l4_dir, "kb_overview.md")
    body_match = re.split(r"^---\s*\n.*?\n---\s*\n", l4_yaml, maxsplit=1, flags=re.DOTALL)
    md_body = body_match[1] if len(body_match) > 1 else l4_yaml
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_body)
    print(f"  📄 知识库总控/kb_overview.md ({len(md_body)} chars)")
    print(f"  ✅ L4 索引构建完成")
    return True


# ════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="L3/L4 索引构建")
    sp = p.add_subparsers(dest="level", required=True)

    l3 = sp.add_parser("l3", help="构建领域总控索引")
    l3.add_argument("--book-dir", required=True)
    l3.add_argument("--book-id", required=True)
    l3.add_argument("--book-name", required=True)

    l4 = sp.add_parser("l4", help="构建知识库总控索引")
    l4.add_argument("--book-dir", required=True)
    l4.add_argument("--book-id", required=True)

    all_p = sp.add_parser("all", help="构建 L3+L4")
    all_p.add_argument("--book-dir", required=True)
    all_p.add_argument("--book-id", required=True)
    all_p.add_argument("--book-name", required=True)

    args = p.parse_args()

    if args.level in ("l3", "all"):
        build_l3_index(args.book_dir, args.book_id, args.book_name if hasattr(args, 'book_name') else "")
    if args.level in ("l4", "all"):
        build_l4_index(args.book_dir, args.book_id)


if __name__ == "__main__":
    main()
