#!/usr/bin/env python3
"""
book_toc.py — 从 minerU 处理过的参考书 .md 文件中提取目录结构。

借鉴 domain-wiki/split_book_to_chapters.py 的 CHAPTER_PATTERN/CONTENT_PATTERN。
不处理格式校验，不做语义分析，只做模式匹配。

用法：
  python3 scripts/book_toc.py /path/to/参考书.md
  python3 scripts/book_toc.py /path/to/参考书.md --json    # JSON 输出
  python3 scripts/book_toc.py /path/to/参考书.md --verbose  # 详细输出
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================
# 模式（从 domain-wiki split_book_to_chapters.py 借鉴）
# ============================================================

# 章节头：匹配 "第1章 绪论"、"## 第1章 绪论"、"第 1 章 绪 论"
CHAPTER_PATTERN = re.compile(
    r'^(?:#{1,2})?\s*第\s*(\d+)\s*章\s*(.*?)$'
)

# 子节：匹配 "## 1.1 标题" / "### 1.1.1 标题"
SECTION_PATTERN = re.compile(
    r'^#{1,3}\s+(\d+(?:\.\d+)+)\s+(.*?)$'
)

# 目录条目："第1章 绪论 …… 3"（带页码，"……" 或 "…" 分隔）
TOC_CHAPTER_PATTERN = re.compile(
    r'^第\s*(\d+)\s*章\s*(.*?)\s*[…]+\s*\d+\s*$'
)
TOC_SECTION_PATTERN = re.compile(
    r'^(\d+(?:\.\d+)+)\s+(.*?)\s*[…]+\s*\d+\s*$'
)

# 噪声标题（不纳入目录）
NOISE_KEYWORDS = [
    '图书在版编目', 'CIP', '内容简介', '前言', '序',
    '目录', '封底', '参考文献', '索引', '附录',
    '作者简介', '编委会', '本书读者对象', '内容提要',
    '出版说明', '编者', '致谢', '后记', '附注',
    '编审委员会', '版权声明', '扉页',
]

# 篇章级分组（如 "入门篇"、"提高篇"）
PART_PATTERN = re.compile(
    r'^#{1,2}\s*(.*?[篇卷部])\s*$'
)


def is_noise(title: str) -> bool:
    """判断标题是否为噪声（元信息/出版信息等）"""
    t = title.strip()
    if not t:
        return True
    # 纯页码
    if re.match(r'^\d+\s*$', t):
        return True
    # 噪声关键词
    for kw in NOISE_KEYWORDS:
        if kw in t:
            return True
    return False


def extract_toc(filepath: str, verbose: bool = False) -> Dict:
    """
    从 minerU .md 文件提取目录结构。

    返回：
    {
        "file": "文件名",
        "book_title": "推断的书名",
        "total_lines": N,
        "chapters": [
            {
                "num": 1,
                "title": "绪论",
                "line": 703,
                "sections": [
                    {"num": "1.1", "title": "电磁干扰问题", "line": 720},
                    ...
                ]
            },
            ...
        ],
        "toc_lines_found": 12,      # 目录区提取的条目数
        "content_lines_found": 12,   # 正文区提取的章节数
    }
    """
    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件不存在: {filepath}"}
    
    content = path.read_text(encoding='utf-8')
    lines = content.split('\n')
    total_lines = len(lines)
    
    # 推断书名（从第一行 # 标题）
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
    
    # --- 两阶段提取 ---
    # 阶段A：从目录区提取（TOC_CHAPTER_PATTERN / TOC_SECTION_PATTERN）
    # 阶段B：从正文区提取（CHAPTER_PATTERN / SECTION_PATTERN）
    # 优先用正文区，正文区找不到的用目录区补充
    
    toc_chapters = []  # 目录区的章节
    content_chapters = []  # 正文区的章节
    
    current_toc_chapter = None
    current_content_chapter = None
    
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        
        # --- 噪声过滤 ---
        if is_noise(s):
            continue
        if s.startswith('![') or s.startswith('<details>') or s.startswith('</details>'):
            continue
        
        # --- 目录条目（TOC） ---
        m = TOC_CHAPTER_PATTERN.match(s)
        if m:
            ch_num = int(m.group(1))
            ch_title = m.group(2).strip()
            # 清理标题中的特殊字符
            ch_title = re.sub(r'[《》「」『』（）\)\(\-]', '', ch_title).strip()
            current_toc_chapter = {
                'num': ch_num,
                'title': ch_title,
                'line': i + 1,
                'sections': []
            }
            toc_chapters.append(current_toc_chapter)
            continue
        
        m = TOC_SECTION_PATTERN.match(s)
        if m and current_toc_chapter:
            sec_title = m.group(2).strip()
            sec_title = re.sub(r'[《》「」『』（）\)\(\-]', '', sec_title).strip()
            current_toc_chapter['sections'].append({
                'num': m.group(1),
                'title': sec_title,
                'line': i + 1,
            })
            continue
        
        # --- 部分（篇/卷） ---
        _ = PART_PATTERN.match(s)
        
        # --- 章节头（正文） ---
        m = CHAPTER_PATTERN.match(s)
        if m:
            ch_num = int(m.group(1))
            ch_title = m.group(2).strip()
            # 跳过 TOC 中的页码条目（"绪论 …… 1"）
            if re.search(r'[…]{2,}\s*\d+$', ch_title):
                continue
            ch_title = re.sub(r'[《》「」『』（）\)\(\-]', '', ch_title).strip()
            current_content_chapter = {
                'num': ch_num,
                'title': ch_title,
                'line': i + 1,
                'sections': []
            }
            content_chapters.append(current_content_chapter)
            continue
        
        # --- 子节（正文） ---
        m = SECTION_PATTERN.match(s)
        if m and current_content_chapter:
            sec_title = m.group(2).strip()
            # 跳过 TOC 中的页码条目
            if re.search(r'[…]{2,}\s*\d+$', sec_title):
                continue
            sec_title = re.sub(r'[《》「」『』（）\)\(\-]', '', sec_title).strip()
            current_content_chapter['sections'].append({
                'num': m.group(1),
                'title': sec_title,
                'line': i + 1,
            })
    
    # --- 合并策略 ---
    # 正文区章节优先。如果正文区没找到任何章节，用目录区。
    # 正文区找到但某章缺子节，用目录区补充该章的子节。
    
    if content_chapters:
        # 对正文区每章，如果 sections 少于 2 个，从目录区对应章补充
        content_nums = {c['num']: c for c in content_chapters}
        toc_nums = {c['num']: c for c in toc_chapters}
        
        for ch_num, ch in content_nums.items():
            if len(ch['sections']) <= 1 and ch_num in toc_nums:
                # 用目录区的 sections 补充
                toc_section_nums = {s['num']: s for s in toc_nums[ch_num]['sections']}
                for s in ch['sections']:
                    toc_section_nums.pop(s['num'], None)
                ch['sections'].extend(sorted(
                    toc_section_nums.values(),
                    key=lambda x: x['num']
                ))
        
        result['chapters'] = content_chapters
        result['_source'] = 'content'
    elif toc_chapters:
        result['chapters'] = toc_chapters
        result['_source'] = 'toc'
    else:
        result['_source'] = 'none'
    
    result['toc_lines_found'] = len(toc_chapters)
    result['content_lines_found'] = len(content_chapters)
    
    if verbose:
        print(f"\n📖 {result['book_title'] or path.name}")
        print(f"   总行数: {total_lines}")
        print(f"   目录区章节: {len(toc_chapters)} 章")
        print(f"   正文区章节: {len(content_chapters)} 章")
        print(f"   合并后章节: {len(result['chapters'])} 章")
        for ch in result['chapters']:
            print(f"   ├─ 第{ch['num']}章 {ch['title']} (L{ch['line']})")
            for sec in ch['sections'][:5]:
                print(f"   │   ├─ {sec['num']} {sec['title']}")
            if len(ch['sections']) > 5:
                print(f"   │   └─ ... 共{len(ch['sections'])}节")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='从 minerU .md 提取目录结构')
    parser.add_argument('file', help='minerU 处理过的 .md 文件路径')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    args = parser.parse_args()
    
    result = extract_toc(args.file, verbose=args.verbose)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif 'error' in result:
        print(f"❌ {result['error']}")
        sys.exit(1)
    else:
        chapters = result['chapters']
        print(f"\n📚 {result['book_title'] or result['file']}")
        print(f"   共 {len(chapters)} 章 ({result['total_lines']} 行)")
        for ch in chapters:
            sec_count = len(ch['sections'])
            print(f"   第{ch['num']}章 {ch['title']} — {sec_count} 节")
            if args.verbose:
                for sec in ch['sections'][:10]:
                    print(f"       {sec['num']} {sec['title']}")
                if sec_count > 10:
                    print(f"       ... 共{sec_count}节")


if __name__ == '__main__':
    main()
