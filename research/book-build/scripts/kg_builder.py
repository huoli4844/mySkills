#!/usr/bin/env python3
"""
kg_builder.py — book-build 简化知识图谱引擎。

从 book_toc.py 提取的章节结构中构建 SQLite 知识图谱。
用于：
1. 跨书章节映射（书A第3章 ↔ 书B第2章）
2. 核心术语提取（章节标题词频统计）
3. 标准体系推断（从章节标题中检测标准关键词）

用法：
  python3 scripts/kg_builder.py build --project /path/to/教材
  python3 scripts/kg_builder.py query --project /path/to/教材 --term "屏蔽"
  python3 scripts/kg_builder.py show --project /path/to/教材
"""

import re
import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

# 标准体系关键词
STANDARDS_MAP = [
    ("IEC", ["iec", "国际电工委员会"]),
    ("CISPR", ["cispr", "国际无线电干扰"]),
    ("GB", ["gb/t", "gb", "国家标准", "国标"]),
    ("GJB", ["gjb", "国军标"]),
    ("ISO", ["iso", "国际标准化组织"]),
    ("ASTM", ["astm"]),
    ("IEEE", ["ieee"]),
    ("ITU", ["itu"]),
]


def get_db_path(project_root: str) -> str:
    """知识图谱数据库路径"""
    d = os.path.join(project_root, "output", "领域上下文")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "knowledge_graph.db")


def get_domain_yaml_path(project_root: str) -> str:
    return os.path.join(project_root, "output", "领域上下文", "domain-context.yaml")


def init_db(db_path: str):
    """初始化 SQLite 表结构"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.executescript("""
        CREATE TABLE IF NOT EXISTS source_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            chapter_num INTEGER NOT NULL,
            chapter_title TEXT NOT NULL,
            section_count INTEGER DEFAULT 0,
            full_path TEXT,
            start_line INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_chapter_book ON source_chapters(book_id, chapter_num);
        
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            chapter_num INTEGER NOT NULL,
            section_num TEXT NOT NULL,
            section_title TEXT NOT NULL,
            start_line INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_section_book ON sections(book_id, chapter_num);
        
        CREATE TABLE IF NOT EXISTS concept_frequency (
            concept TEXT NOT NULL,
            book_id TEXT NOT NULL,
            chapter_num INTEGER NOT NULL,
            frequency INTEGER DEFAULT 1,
            PRIMARY KEY (concept, book_id, chapter_num)
        );
        
        CREATE TABLE IF NOT EXISTS cross_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_book_id TEXT NOT NULL,
            source_chapter_num INTEGER NOT NULL,
            target_book_id TEXT NOT NULL,
            target_chapter_num INTEGER NOT NULL,
            similarity REAL DEFAULT 0.5
        );
        
        CREATE TABLE IF NOT EXISTS book_meta (
            book_id TEXT PRIMARY KEY,
            book_title TEXT,
            total_lines INTEGER,
            standards_family TEXT
        );
    """)
    
    conn.commit()
    return conn


def extract_terms_from_title(title: str) -> List[str]:
    """从章节标题中提取术语（2~8字中文名词）"""
    # 移除编号前缀和分隔符
    clean = re.sub(r'^[\d.]+', '', title).strip()
    clean = re.sub(r'[（(][^)）]*[)）]', '', clean)  # 去掉括号内容
    clean = re.sub(r'[《》「」『』【】、，。：；？！·]', ' ', clean)
    
    terms = []
    # 提取 2-8 字中文词
    for word in re.findall(r'[\u4e00-\u9fff]{2,8}', clean):
        word = word.strip()
        if len(word) >= 2 and word not in _STOP_WORDS:
            terms.append(word)
    return terms


_STOP_WORDS = {
    '一个', '及其', '主要', '基本', '一般', '常见', '常用',
    '相关', '不同', '其他', '各种', '之间', '以上', '以下',
    '介绍', '概述', '方法', '技术', '应用', '设计', '分析',
    '研究', '发展', '特点', '原理', '方式', '过程', '内容',
    '方面', '情况', '部分', '问题', '关系', '影响', '作用',
    '意义', '性质', '领域', '系统',
}


def _detect_standards(chapters: List[Dict]) -> List[str]:
    """从章节标题中检测标准体系"""
    all_text = ' '.join(c['title'] for c in chapters)
    all_text += ' '.join(
        s['title'] for c in chapters for s in c.get('sections', [])
    )
    all_text = all_text.lower()
    
    detected = []
    for name, keywords in STANDARDS_MAP:
        if any(kw in all_text for kw in keywords):
            detected.append(name)
    return detected


def build_graph(project_root: str, verbose: bool = False):
    """
    构建知识图谱：
    1. 读取项目配置
    2. 对每本参考书调用 book_toc 提取章节
    3. 写入 SQLite
    4. 跨书映射 + 词频统计
    5. 输出 domain-context.yaml
    """
    from book_toc import extract_toc
    
    # 读取 book-build.yaml
    cfg_path = os.path.join(project_root, "book-build.yaml")
    if not os.path.exists(cfg_path):
        print(f"❌ 未找到项目配置: {cfg_path}")
        sys.exit(1)
    
    import yaml
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    
    textbook_name = cfg.get('textbook', {}).get('name', '未知教材')
    source_books = cfg.get('source_books', [])
    
    if not source_books:
        print("❌ book-build.yaml 中没有 source_books")
        sys.exit(1)
    
    db_path = get_db_path(project_root)
    conn = init_db(db_path)
    
    print(f"\n{'='*50}")
    print(f"📚 构建知识图谱")
    print(f"   教材: {textbook_name}")
    print(f"   参考书: {len(source_books)} 本")
    print(f"{'='*50}")
    
    all_chapters = []  # 用于词频统计
    all_terms_counter = Counter()
    book_ids = []
    
    for book in source_books:
        display_name = book.get('display_name', '?')
        author = book.get('author', '?')
        md_path = book.get('path', '')
        
        if not md_path or not os.path.exists(md_path):
            print(f"   ⚠️  跳过 {display_name}（文件不存在: {md_path}）")
            continue
        
        # 提取目录
        toc = extract_toc(md_path)
        if 'error' in toc:
            print(f"   ⚠️  跳过 {display_name}: {toc['error']}")
            continue
        
        chapters = toc.get('chapters', [])
        print(f"\n   📖 {display_name}（{author}）")
        print(f"      {len(chapters)} 章")
        
        book_id = f"{author}-{display_name}"[:60]
        book_ids.append(book_id)
        
        # 写 book_meta
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO book_meta VALUES (?, ?, ?, ?)",
            (book_id, toc.get('book_title', ''), toc.get('total_lines', 0), '')
        )
        
        for ch in chapters:
            ch_num = ch['num']
            ch_title = ch['title']
            sections = ch.get('sections', [])
            
            # 写 source_chapters
            cursor.execute(
                "INSERT INTO source_chapters (book_id, chapter_num, chapter_title, section_count, full_path, start_line) VALUES (?, ?, ?, ?, ?, ?)",
                (book_id, ch_num, ch_title, len(sections), md_path, ch.get('line', 0))
            )
            
            # 写 sections
            for sec in sections:
                cursor.execute(
                    "INSERT INTO sections (book_id, chapter_num, section_num, section_title, start_line) VALUES (?, ?, ?, ?, ?)",
                    (book_id, ch_num, sec['num'], sec['title'], sec.get('line', 0))
                )
            
            # 提取术语
            all_text = ch_title + ' ' + ' '.join(s['title'] for s in sections)
            terms = extract_terms_from_title(all_text)
            term_counts = Counter(terms)
            for term, freq in term_counts.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO concept_frequency (concept, book_id, chapter_num, frequency) VALUES (?, ?, ?, ?)",
                    (term, book_id, ch_num, freq)
                )
                all_terms_counter[term] += freq
            
            all_chapters.append(ch)
        
        conn.commit()
        
        if verbose:
            for ch in chapters[:5]:
                print(f"      ├─ 第{ch['num']}章 {ch['title']} ({len(ch['sections'])}节)")
            if len(chapters) > 5:
                print(f"      └─ ... 共{len(chapters)}章")
    
    # --- 跨书章节映射 ---
    print(f"\n   🔗 跨书映射...")
    if len(book_ids) >= 2:
        _build_cross_mappings(conn, book_ids)
    
    # --- 检测标准体系 ---
    standards = _detect_standards(all_chapters)
    print(f"   📋 检测到标准体系: {', '.join(standards) if standards else '通用'}")
    
    # --- 输出 domain-context.yaml ---
    top_terms = all_terms_counter.most_common(30)
    domain_name = textbook_name.replace('-', '').strip()
    
    domain_ctx = {
        "domain_name": domain_name,
        "textbook_name": textbook_name,
        "source_books": len(source_books),
        "book_ids": book_ids,
        "standards_family": standards,
        "top_terms": [{"term": t, "frequency": f} for t, f in top_terms[:20]],
        "chapter_count": len(all_chapters),
    }
    
    yaml_path = get_domain_yaml_path(project_root)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(domain_ctx, f, allow_unicode=True, default_flow_style=False)
    
    print(f"\n   ✅ 写入: {yaml_path}")
    print(f"      db:   {db_path}")
    print(f"      核心术语: {', '.join(t for t, _ in top_terms[:10])}")
    
    conn.close()
    return domain_ctx


def _build_cross_mappings(conn, book_ids):
    """构建跨书章节相似映射（基于章节标题关键词重叠）"""
    cursor = conn.cursor()
    
    for i in range(len(book_ids)):
        for j in range(i + 1, len(book_ids)):
            b1 = book_ids[i]
            b2 = book_ids[j]
            
            # 获取两本书的所有章节
            cursor.execute(
                "SELECT chapter_num, chapter_title FROM source_chapters WHERE book_id = ?",
                (b1,)
            )
            ch1_list = cursor.fetchall()
            
            cursor.execute(
                "SELECT chapter_num, chapter_title FROM source_chapters WHERE book_id = ?",
                (b2,)
            )
            ch2_list = cursor.fetchall()
            
            for ch1_num, ch1_title in ch1_list:
                terms1 = set(extract_terms_from_title(ch1_title))
                if not terms1:
                    continue
                
                for ch2_num, ch2_title in ch2_list:
                    terms2 = set(extract_terms_from_title(ch2_title))
                    if not terms2:
                        continue
                    
                    overlap = terms1 & terms2
                    if overlap:
                        similarity = len(overlap) / max(len(terms1), len(terms2))
                        if similarity >= 0.3:
                            cursor.execute(
                                "INSERT OR IGNORE INTO cross_mappings (source_book_id, source_chapter_num, target_book_id, target_chapter_num, similarity) VALUES (?, ?, ?, ?, ?)",
                                (b1, ch1_num, b2, ch2_num, round(similarity, 2))
                            )
    
    conn.commit()


def query_graph(project_root: str, term: str, verbose: bool = False):
    """查询某个术语在知识图谱中的出现位置"""
    db_path = get_db_path(project_root)
    if not os.path.exists(db_path):
        print(f"❌ 知识图谱不存在: {db_path}")
        print("   请先运行: python3 scripts/kg_builder.py build --project ...")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT cf.book_id, cf.chapter_num, sc.chapter_title, cf.frequency
        FROM concept_frequency cf
        LEFT JOIN source_chapters sc ON cf.book_id = sc.book_id AND cf.chapter_num = sc.chapter_num
        WHERE cf.concept LIKE ?
        ORDER BY cf.frequency DESC
        LIMIT 30
    """, (f"%{term}%",))
    
    rows = cursor.fetchall()
    if not rows:
        print(f"未找到包含 \"{term}\" 的章节")
        return
    
    print(f"\n🔍 \"{term}\" 在知识图谱中出现 {len(rows)} 处:")
    by_book = {}
    for book_id, ch_num, ch_title, freq in rows:
        by_book.setdefault(book_id, []).append((ch_num, ch_title, freq))
    
    for book_id, chapters in by_book.items():
        print(f"\n  📖 {book_id}")
        for ch_num, ch_title, freq in chapters[:10]:
            print(f"     第{ch_num}章 {ch_title} (频次: {freq})")
    
    conn.close()


def show_domain(project_root: str):
    """显示领域上下文"""
    yaml_path = get_domain_yaml_path(project_root)
    if not os.path.exists(yaml_path):
        print(f"❌ 领域上下文不存在: {yaml_path}")
        print("   请先运行: python3 scripts/kg_builder.py build --project ...")
        return
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        print(f.read())


def main():
    parser = argparse.ArgumentParser(description='知识图谱构建引擎')
    sub = parser.add_subparsers(dest='command')
    
    p_build = sub.add_parser('build', help='构建知识图谱')
    p_build.add_argument('--project', required=True)
    p_build.add_argument('--verbose', '-v', action='store_true')
    
    p_query = sub.add_parser('query', help='查询术语')
    p_query.add_argument('--project', required=True)
    p_query.add_argument('--term', required=True)
    
    p_show = sub.add_parser('show', help='显示领域上下文')
    p_show.add_argument('--project', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'build':
        build_graph(args.project, verbose=args.verbose)
    elif args.command == 'query':
        query_graph(args.project, args.term)
    elif args.command == 'show':
        show_domain(args.project)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
