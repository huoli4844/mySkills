#!/usr/bin/env python3
"""
domain_init.py — 领域初始化管线（合并 book_toc.py + kg_builder.py + domain_injector.py）。

单入口覆盖：提取TOC → 构建知识图谱 → 注入领域信号。

用法：
  # === 全线执行（推荐）===
  python3 scripts/domain_init.py --project /path/to/教材 [--verbose] [--noise-report]

  # === 分阶段执行 ===
  python3 scripts/domain_init.py --project /path/to/教材 --phase toc     # 仅TOC提取
  python3 scripts/domain_init.py --project /path/to/教材 --phase kg      # 仅KG构建
  python3 scripts/domain_init.py --project /path/to/教材 --phase inject  # 仅领域注入

  # === 单文件TOC提取 ===
  python3 scripts/domain_init.py toc /path/to/参考书.md [--json] [--verbose] [--noise-report]

  # === KG查询/显示 ===
  python3 scripts/domain_init.py query --project /path/to/教材 --term "屏蔽"
  python3 scripts/domain_init.py show --project /path/to/教材
"""
# ============================================================
# 合并来源：book_toc.py (282行) + kg_builder.py (414行) + domain_injector.py (131行)
# 合并后 746 行。减少文件 3→1，减少导入链 2 层。
# ============================================================

import re
import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter

# ============================================================
# SECTION 1 — TOC 提取（来源：book_toc.py）
# ============================================================

# 章节头：匹配 "第1章 绪论"、"## 第1章 绪论"、"第 1 章 绪 论"
CHAPTER_PATTERN = re.compile(r'^(?:#{1,2})?\s*第\s*(\d+)\s*章\s*(.*?)$')

# 子节：匹配 "## 1.1 标题" / "### 1.1.1 标题"
SECTION_PATTERN = re.compile(r'^#{1,3}\s+(\d+(?:\.\d+)+)\s+(.*?)$')

# 目录条目（带页码）
TOC_CHAPTER_PATTERN = re.compile(r'^第\s*(\d+)\s*章\s*(.*?)\s*[…]+?\s*\d+\s*$')
TOC_SECTION_PATTERN = re.compile(r'^(\d+(?:\.\d+)+)\s+(.*?)\s*[…]+?\s*\d+\s*$')

# 篇章级分组
PART_PATTERN = re.compile(r'^#{1,2}\s*(.*?[篇卷部])\s*$')

# 噪声标题
NOISE_KEYWORDS = [
    '图书在版编目', 'CIP', '内容简介', '前言', '序',
    '目录', '封底', '参考文献', '索引', '附录',
    '作者简介', '编委会', '本书读者对象', '内容提要',
    '出版说明', '编者', '致谢', '后记', '附注',
    '编审委员会', '版权声明', '扉页',
]


def is_noise(title: str) -> bool:
    """判断标题是否为噪声（元信息/出版信息等）"""
    t = title.strip()
    if not t:
        return True
    if re.match(r'^\d+\s*$', t):  # 纯页码
        return True
    for kw in NOISE_KEYWORDS:
        if kw in t:
            return True
    return False


def extract_toc(filepath: str, verbose: bool = False, noise_report: bool = False) -> Dict:
    """
    从 minerU .md 文件提取目录结构。

    返回：
    {"file", "book_title", "total_lines", "chapters": [{num, title, line, sections}],
     "toc_lines_found", "content_lines_found", "noise_filtered" (含noise_report时)}
    """
    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件不存在: {filepath}"}

    content = path.read_text(encoding='utf-8')
    lines = content.split('\n')
    total_lines = len(lines)

    # 推断书名
    book_title = ""
    for line in lines[:50]:
        s = line.strip()
        if s.startswith('# ') and not is_noise(s[2:]):
            book_title = s[2:].strip()
            break

    result = {
        "file": path.name,
        "book_title": book_title,
        "total_lines": total_lines,
        "chapters": [],
    }

    toc_chapters = []
    content_chapters = []
    noise_filtered = []  # 仅 noise_report 时使用

    current_toc_chapter = None
    current_content_chapter = None

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue

        # --- 噪声过滤 ---
        if is_noise(s):
            if noise_report:
                noise_filtered.append({"line": i + 1, "text": s[:80], "reason": "noise_keyword"})
            continue
        if s.startswith('![') or s.startswith('<details>') or s.startswith('</details>'):
            if noise_report:
                noise_filtered.append({"line": i + 1, "text": s[:80], "reason": "markdown"})
            continue

        # --- 目录条目（TOC）---
        m = TOC_CHAPTER_PATTERN.match(s)
        if m:
            ch_num = int(m.group(1))
            ch_title = re.sub(r'[《》「」『』（）\)\(-]', '', m.group(2)).strip()
            current_toc_chapter = {'num': ch_num, 'title': ch_title, 'line': i + 1, 'sections': []}
            toc_chapters.append(current_toc_chapter)
            continue

        m = TOC_SECTION_PATTERN.match(s)
        if m and current_toc_chapter:
            sec = re.sub(r'[《》「」『』（）\)\(-]', '', m.group(2)).strip()
            current_toc_chapter['sections'].append({'num': m.group(1), 'title': sec, 'line': i + 1})
            continue

        # --- 章节头（正文）---
        m = CHAPTER_PATTERN.match(s)
        if m:
            ch_num = int(m.group(1))
            ch_title = m.group(2).strip()
            if re.search(r'[…]{2,}\s*\d+$', ch_title):
                continue  # 跳 TOC 页码
            ch_title = re.sub(r'[《》「」『』（）\)\(-]', '', ch_title).strip()
            current_content_chapter = {'num': ch_num, 'title': ch_title, 'line': i + 1, 'sections': []}
            content_chapters.append(current_content_chapter)
            continue

        # --- 子节（正文）---
        m = SECTION_PATTERN.match(s)
        if m and current_content_chapter:
            sec_title = m.group(2).strip()
            if re.search(r'[…]{2,}\s*\d+$', sec_title):
                continue
            sec_title = re.sub(r'[《》「」『』（）\)\(-]', '', sec_title).strip()
            current_content_chapter['sections'].append({'num': m.group(1), 'title': sec_title, 'line': i + 1})

    # --- 合并策略 ---
    if content_chapters:
        content_nums = {c['num']: c for c in content_chapters}
        toc_nums = {c['num']: c for c in toc_chapters}
        for ch_num, ch in content_nums.items():
            if len(ch['sections']) <= 1 and ch_num in toc_nums:
                existing = {s['num'] for s in ch['sections']}
                for ts in toc_nums[ch_num]['sections']:
                    if ts['num'] not in existing:
                        ch['sections'].append(ts)
                ch['sections'].sort(key=lambda x: x['num'])
        result['chapters'] = content_chapters
        result['_source'] = 'content'
    elif toc_chapters:
        result['chapters'] = toc_chapters
        result['_source'] = 'toc'
    else:
        result['_source'] = 'none'

    result['toc_lines_found'] = len(toc_chapters)
    result['content_lines_found'] = len(content_chapters)

    if noise_report:
        result['noise_filtered'] = noise_filtered

    if verbose:
        print(f"\n  {result.get('book_title') or path.name}")
        print(f"    总行数: {total_lines}  |  目录: {len(toc_chapters)}章  |  正文: {len(content_chapters)}章")
        if noise_report and noise_filtered:
            print(f"    噪声过滤: {len(noise_filtered)} 处")
        for ch in result['chapters']:
            print(f"    ├─ 第{ch['num']}章 {ch['title']} (L{ch['line']})")
            for sec in ch['sections'][:5]:
                print(f"    │  ├─ {sec['num']} {sec['title']}")
            if len(ch['sections']) > 5:
                print(f"    │  └─ ... 共{len(ch['sections'])}节")

    return result


# ============================================================
# SECTION 2 — 知识图谱（来源：kg_builder.py）
# ============================================================

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

_STOP_WORDS = {
    '一个', '及其', '主要', '基本', '一般', '常见', '常用',
    '相关', '不同', '其他', '各种', '之间', '以上', '以下',
    '介绍', '概述', '方法', '技术', '应用', '设计', '分析',
    '研究', '发展', '特点', '原理', '方式', '过程', '内容',
    '方面', '情况', '部分', '问题', '关系', '影响', '作用',
    '意义', '性质', '领域', '系统', '概念',
    # 章节结构噪声词
    '小结', '概述', '引言', '引言概述',
    '标准简介', '绪论',
}


def extract_terms_from_title(title: str) -> List[str]:
    """从章节标题中提取术语（2~8字中文名词）"""
    clean = re.sub(r'^[\d.]+', '', title).strip()
    clean = re.sub(r'[（(][^)）]*[)）]', '', clean)
    clean = re.sub(r'[《》「」『』【】、，。：；？！·]', ' ', clean)
    terms = []
    for word in re.findall(r'[\u4e00-\u9fff]{2,8}', clean):
        word = word.strip()
        if len(word) >= 2 and word not in _STOP_WORDS:
            terms.append(word)
    return terms


def _detect_standards(chapters: List[Dict]) -> List[str]:
    """从章节标题中检测标准体系"""
    all_text = ' '.join(c['title'] for c in chapters)
    all_text += ' '.join(s['title'] for c in chapters for s in c.get('sections', []))
    all_text = all_text.lower()
    detected = []
    for name, keywords in STANDARDS_MAP:
        if any(kw in all_text for kw in keywords):
            detected.append(name)
    return detected


def _kg_get_db_path(project_root: str) -> str:
    d = os.path.join(project_root, "output", "领域上下文")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "knowledge_graph.db")


def _kg_get_yaml_path(project_root: str) -> str:
    return os.path.join(project_root, "output", "领域上下文", "domain-context.yaml")


def _kg_init_db(db_path: str):
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


def _kg_build_cross_mappings(conn, book_ids: List[str]):
    cursor = conn.cursor()
    for i in range(len(book_ids)):
        for j in range(i + 1, len(book_ids)):
            b1, b2 = book_ids[i], book_ids[j]
            cursor.execute("SELECT chapter_num, chapter_title FROM source_chapters WHERE book_id = ?", (b1,))
            ch1_list = cursor.fetchall()
            cursor.execute("SELECT chapter_num, chapter_title FROM source_chapters WHERE book_id = ?", (b2,))
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
                        sim = len(overlap) / max(len(terms1), len(terms2))
                        if sim >= 0.3:
                            cursor.execute(
                                "INSERT OR IGNORE INTO cross_mappings VALUES (NULL, ?, ?, ?, ?, ?)",
                                (b1, ch1_num, b2, ch2_num, round(sim, 2))
                            )
    conn.commit()


def build_graph(project_root: str, verbose: bool = False) -> Dict:
    """
    构建知识图谱：读取配置 → 每本参考书提取TOC → 写入SQLite → 跨书映射 → 输出yaml。
    """
    import yaml

    cfg_path = os.path.join(project_root, "book-build.yaml")
    if not os.path.exists(cfg_path):
        print(f"   ❌ 未找到项目配置: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}

    textbook_name = cfg.get('textbook', {}).get('name', '未知教材')
    source_books = cfg.get('source_books', [])
    if not source_books:
        print("   ❌ book-build.yaml 中没有 source_books")
        sys.exit(1)

    db_path = _kg_get_db_path(project_root)
    conn = _kg_init_db(db_path)

    print(f"\n   📚 构建知识图谱: {textbook_name} ({len(source_books)} 本参考书)")

    all_chapters = []
    all_terms_counter = Counter()
    book_ids = []

    for book in source_books:
        display_name = book.get('display_name', '?')
        author = book.get('author', '?')
        md_path = book.get('path', '')

        if not md_path or not os.path.exists(md_path):
            print(f"      ⚠️  跳过 {display_name}（文件不存在）")
            continue

        toc = extract_toc(md_path)
        if 'error' in toc:
            print(f"      ⚠️  跳过 {display_name}: {toc['error']}")
            continue

        chapters = toc.get('chapters', [])
        print(f"      📖 {display_name}（{author}）— {len(chapters)} 章")

        book_id = f"{author}-{display_name}"[:60]
        book_ids.append(book_id)
        cursor = conn.cursor()

        cursor.execute("INSERT OR REPLACE INTO book_meta VALUES (?, ?, ?, ?)",
                       (book_id, toc.get('book_title', ''), toc.get('total_lines', 0), ''))

        for ch in chapters:
            ch_num = ch['num']
            sections = ch.get('sections', [])
            cursor.execute("INSERT INTO source_chapters VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                           (book_id, ch_num, ch['title'], len(sections), md_path, ch.get('line', 0)))
            for sec in sections:
                cursor.execute("INSERT INTO sections VALUES (NULL, ?, ?, ?, ?, ?)",
                               (book_id, ch_num, sec['num'], sec['title'], sec.get('line', 0)))

            all_text = ch['title'] + ' ' + ' '.join(s['title'] for s in sections)
            terms = extract_terms_from_title(all_text)
            term_counts = Counter(terms)
            for term, freq in term_counts.items():
                cursor.execute("INSERT OR REPLACE INTO concept_frequency VALUES (?, ?, ?, ?)",
                               (term, book_id, ch_num, freq))
                all_terms_counter[term] += freq
            all_chapters.append(ch)

        conn.commit()

    if len(book_ids) >= 2:
        _kg_build_cross_mappings(conn, book_ids)

    standards = _detect_standards(all_chapters)
    top_terms = all_terms_counter.most_common(30)

    domain_ctx = {
        "domain_name": textbook_name.replace('-', '').strip(),
        "textbook_name": textbook_name,
        "source_books": len(source_books),
        "book_ids": book_ids,
        "standards_family": standards,
        "top_terms": [{"term": t, "frequency": f} for t, f in top_terms[:20]],
        "chapter_count": len(all_chapters),
    }

    yaml_path = _kg_get_yaml_path(project_root)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(domain_ctx, f, allow_unicode=True, default_flow_style=False)

    print(f"      ✅ 写入: {yaml_path}")
    print(f"         核心术语: {', '.join(t for t, _ in top_terms[:10])}")
    conn.close()
    return domain_ctx


def query_graph(project_root: str, term: str):
    """查询某个术语在知识图谱中的出现位置"""
    db_path = _kg_get_db_path(project_root)
    if not os.path.exists(db_path):
        print(f"   ❌ 知识图谱不存在，请先运行 domain_init.py --project ... --phase kg")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cf.book_id, cf.chapter_num, sc.chapter_title, cf.frequency
        FROM concept_frequency cf
        LEFT JOIN source_chapters sc ON cf.book_id = sc.book_id AND cf.chapter_num = sc.chapter_num
        WHERE cf.concept LIKE ?
        ORDER BY cf.frequency DESC LIMIT 30
    """, (f"%{term}%",))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"   ❓ 未找到 \"{term}\"")
        return

    print(f"\n   🔍 \"{term}\" — {len(rows)} 处:")
    by_book = {}
    for book_id, ch_num, ch_title, freq in rows:
        by_book.setdefault(book_id, []).append((ch_num, ch_title, freq))
    for book_id, chapters in by_book.items():
        print(f"      📖 {book_id}")
        for ch_num, ch_title, freq in chapters[:10]:
            print(f"         第{ch_num}章 {ch_title} (频次: {freq})")


def show_domain(project_root: str):
    """显示领域上下文"""
    yaml_path = _kg_get_yaml_path(project_root)
    if not os.path.exists(yaml_path):
        print(f"   ❌ 领域上下文不存在，请先运行 domain_init.py --project ... --phase kg")
        return
    with open(yaml_path, 'r', encoding='utf-8') as f:
        print(f.read())


# ============================================================
# SECTION 3 — 领域注入（来源：domain_injector.py）
# ============================================================

SKILL_DIR = Path(__file__).resolve().parent.parent
REFERENCES_DIR = SKILL_DIR / "references"


def _inj_load_context(project_root: str) -> Dict:
    """读取已构建的领域上下文"""
    yaml_path = os.path.join(project_root, "output", "领域上下文", "domain-context.yaml")
    if not os.path.exists(yaml_path):
        print(f"   ⚠️  领域上下文不存在，请先运行 --phase kg")
        print(f"      {yaml_path}")
        return {}
    import yaml
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def build_variable_map(ctx: Dict) -> Dict[str, str]:
    """从领域上下文构建 {{var}} → 实际值的映射表"""
    domain_name = ctx.get("domain_name", "本领域")
    standards = ctx.get("standards_family", [])
    top_terms = [t["term"] for t in ctx.get("top_terms", [])[:5]]
    standards_str = "、".join(standards) if standards else "行业"

    return {
        "domain_name": domain_name,
        "domain_standards": f"{standards_str}标准",
        "domain_standards_family": standards_str,
        "domain_key_terms": "、".join(top_terms[:3]) if top_terms else f"{domain_name}核心概念",
        "example_cases": f"真实{domain_name}工程案例",
        "standard_refs": f"参考教材、{standards_str}标准、公开报告",
    }


def inject_variables(text: str, var_map: Dict[str, str]) -> str:
    """替换所有 {{var}} 为实际值，未定义的变量保留原样"""
    def replacer(m):
        var_name = m.group(1).strip()
        if var_name in var_map:
            return var_map[var_name]
        for key, val in var_map.items():
            if key in var_name:
                return val
        return m.group(0)
    return re.sub(r'\{\{(\w+)\}\}', replacer, text)


def inject_references(project_root: str, var_map: Dict[str, str], verbose: bool = False) -> int:
    """填充 references/ 中的模板，写入项目 output/ 目录"""
    refs_dir = os.path.join(project_root, "output", "领域上下文", "references")
    os.makedirs(refs_dir, exist_ok=True)

    count = 0
    for fpath in sorted(REFERENCES_DIR.glob("*.md")):
        content = fpath.read_text(encoding='utf-8')
        if '{{' not in content:
            continue
        injected = inject_variables(content, var_map)
        out_path = os.path.join(refs_dir, fpath.name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(injected)
        count += 1
        if verbose:
            vars_found = re.findall(r'\{\{(\w+)\}\}', content)
            print(f"      {fpath.name}: {len(vars_found)} 个变量")
    return count


def inject_domain(project_root: str, verbose: bool = False):
    """执行领域信号注入"""
    ctx = _inj_load_context(project_root)
    if not ctx:
        sys.exit(1)
    var_map = build_variable_map(ctx)

    print(f"\n   🔧 领域信号注入")
    print(f"      领域: {var_map['domain_name']}")
    print(f"      标准: {var_map['domain_standards']}")

    ref_count = inject_references(project_root, var_map, verbose=verbose)
    print(f"      ✅ 已注入 {ref_count} 个 reference 文件")
    print(f"         到 {project_root}/output/领域上下文/references/")


# ============================================================
# CLI — 统一入口
# ============================================================

def cmd_toc(args):
    """单文件TOC提取"""
    result = extract_toc(args.file, verbose=args.verbose, noise_report=args.noise_report)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif 'error' in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    else:
        chapters = result['chapters']
        print(f"\n📚 {result.get('book_title') or result['file']}")
        print(f"   共 {len(chapters)} 章 ({result['total_lines']} 行)")
        for ch in chapters:
            sec_count = len(ch['sections'])
            print(f"   第{ch['num']}章 {ch['title']} — {sec_count} 节")
            if args.verbose:
                for sec in ch['sections'][:10]:
                    print(f"      {sec['num']} {sec['title']}")
                if sec_count > 10:
                    print(f"      ... 共{sec_count}节")


def cmd_query(args):
    query_graph(args.project, args.term)


def cmd_show(args):
    show_domain(args.project)


def cmd_project(args):
    """项目初始化全线或分阶段"""
    if args.phase in (None, 'toc'):
        print(f"\n{'='*50}")
        print(f"📖 Phase: TOC 提取")
        print(f"{'='*50}")
        # TOC提取在各参考书上运行（由 build_graph 内部调用）
        pass  # build_graph 内部会调用 extract_toc

    if args.phase in (None, 'kg'):
        print(f"\n{'='*50}")
        print(f"📊 Phase: 知识图谱构建")
        print(f"{'='*50}")
        build_graph(args.project, verbose=args.verbose)

    if args.phase in (None, 'inject'):
        print(f"\n{'='*50}")
        print(f"🔧 Phase: 领域信号注入")
        print(f"{'='*50}")
        inject_domain(args.project, verbose=args.verbose)


def main():
    parser = argparse.ArgumentParser(description='领域初始化管线')
    sub = parser.add_subparsers(dest='command', help='子命令')

    # toc 子命令：单文件TOC提取
    p_toc = sub.add_parser('toc', help='从 minerU .md 提取目录结构')
    p_toc.add_argument('file', help='minerU .md 文件路径')
    p_toc.add_argument('--json', action='store_true', help='JSON 输出')
    p_toc.add_argument('--verbose', '-v', action='store_true')
    p_toc.add_argument('--noise-report', action='store_true', help='输出噪声过滤明细')

    # query 子命令
    p_query = sub.add_parser('query', help='查询术语在KG中的位置')
    p_query.add_argument('--project', required=True)
    p_query.add_argument('--term', required=True)

    # show 子命令
    p_show = sub.add_parser('show', help='显示领域上下文')
    p_show.add_argument('--project', required=True)

    # project 子命令（默认可省略）
    p_proj = sub.add_parser('project', help='项目初始化（全线或分阶段）')
    p_proj.add_argument('--project', required=True)
    p_proj.add_argument('--phase', choices=['toc', 'kg', 'inject'], help='指定阶段，省略则全执行')
    p_proj.add_argument('--verbose', '-v', action='store_true')
    p_proj.add_argument('--noise-report', action='store_true')

    # 兼容：直接 --project 调用
    parser.add_argument('--project', help='项目根目录（完整管线）')
    parser.add_argument('--phase', choices=['toc', 'kg', 'inject'], help='指定阶段')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--noise-report', action='store_true')

    args = parser.parse_args()

    if args.command == 'toc':
        cmd_toc(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'show':
        cmd_show(args)
    elif args.command == 'project':
        cmd_project(args)
    elif args.project:
        cmd_project(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
