#!/usr/bin/env python3
"""
大纲解析工具 — 从 .docx / .md / 纯文本中提取章节分层树。

用法：
  python3 parse_outline.py 大纲.docx -o /tmp/outline.json
  python3 parse_outline.py 大纲.md -o /tmp/outline.json
  cat 大纲.txt | python3 parse_outline.py /dev/stdin -o /tmp/outline.json
  python3 parse_outline.py /dev/stdin -o /tmp/outline.json   # 粘贴后 Ctrl+D

输出 JSON 结构：
{
  "title": "书名",
  "chapters": [
    {"number": "1", "title": "第1章 绪论", "sections": [
      {"number": "1.1", "title": "1.1 研究背景", "subsections": []},
      ...
    ]}
  ]
}
"""
import argparse, json, re, sys
from pathlib import Path


CHAPTER_PATTERN = re.compile(r'^(?:#{1,2}\s*)?第\s*([一二三四五六七八九十\d]+)\s*章\s*(.*?)$', re.MULTILINE)
SECTION_PATTERN = re.compile(r'^#{2,3}\s*(\d+\.\d+)\s*(.*?)$', re.MULTILINE)
SUBSECTION_PATTERN = re.compile(r'^#{3,4}\s*(\d+\.\d+\.\d+)\s*(.*?)$', re.MULTILINE)

CHINESE_NUM = {'一':'1','二':'2','三':'3','四':'4','五':'5',
               '六':'6','七':'7','八':'8','九':'9','十':'10'}


def chn_to_arabic(cn: str) -> str:
    if cn.isdigit():
        return cn
    if cn in CHINESE_NUM:
        return CHINESE_NUM[cn]
    if '十' in cn:
        if cn == '十': return '10'
        if cn.startswith('十'): return f'1{CHINESE_NUM.get(cn[1],"0")}'
        if cn.endswith('十'): return f'{CHINESE_NUM.get(cn[0],"1")}0'
        return f'{CHINESE_NUM.get(cn[0],"1")}{CHINESE_NUM.get(cn[1],"0")}'
    return cn


def parse_text(text: str) -> dict:
    lines = text.strip().split('\n')
    title = ""
    for line in lines:
        s = line.strip().lstrip('#').strip()
        if s and not re.search(r'第.*章', s) and len(s) > 2:
            title = s
            break

    chapters = []
    for ch_match in CHAPTER_PATTERN.finditer(text):
        ch_num = ch_match.group(1).strip()
        ch_title_raw = ch_match.group(2).strip()
        ch_pos = ch_match.start()

        ch_arabic = chn_to_arabic(ch_num)
        ch_title = f"第{ch_arabic}章 {ch_title_raw}" if ch_title_raw else f"第{ch_arabic}章"

        next_ch = CHAPTER_PATTERN.search(text, ch_match.end())
        ch_end = next_ch.start() if next_ch else len(text)
        ch_text = text[ch_pos:ch_end]

        sections = []
        for sec_match in SECTION_PATTERN.finditer(ch_text):
            sec_num = sec_match.group(1)
            sec_title = sec_match.group(2).strip()
            sec_title = f"{sec_num} {sec_title}" if sec_title else sec_num

            sec_pos = sec_match.start()
            next_sec = SECTION_PATTERN.search(ch_text, sec_match.end())
            sec_end = next_sec.start() if next_sec else len(ch_text)
            sec_text = ch_text[sec_pos:sec_end]

            subsections = []
            for sub_match in SUBSECTION_PATTERN.finditer(sec_text):
                sub_num = sub_match.group(1)
                sub_title = sub_match.group(2).strip()
                sub_title = f"{sub_num} {sub_title}" if sub_title else sub_num
                subsections.append({"number": sub_num, "title": sub_title})

            sections.append({
                "number": sec_num,
                "title": sec_title,
                "subsections": subsections,
            })

        chapters.append({
            "number": ch_arabic,
            "title": ch_title,
            "sections": sections,
        })

    return {"title": title, "chapters": chapters}


def print_tasks(outline: dict):
    total_leaves = sum(len(c.get("sections", [])) for c in outline["chapters"])
    print(f"📋 写作任务清单（共计 {total_leaves} 个节）")
    for c in outline["chapters"]:
        secs = c.get("sections", [])
        print(f"  ├── {c['title']} ({len(secs)}节)")
        for s in secs:
            if s.get("subsections"):
                print(f"  │   ├── {s['title']} ({len(s['subsections'])}子节)")
                for sub in s["subsections"]:
                    print(f"  │   │   └── {sub['title']}")
            else:
                print(f"  │   └── {s['title']}")


def main():
    parser = argparse.ArgumentParser(description='大纲解析：提取章节分层树')
    parser.add_argument('input', help='输入文件路径（.docx / .md / /dev/stdin）')
    parser.add_argument('-o', '--output', required=True, help='输出 JSON 文件路径')
    parser.add_argument('--print-tasks', action='store_true', help='同时打印任务清单')
    args = parser.parse_args()

    input_path = Path(args.input)

    if args.input.endswith('.docx'):
        try:
            from docx import Document
        except ImportError:
            print("❌ 需要 python-docx: pip install python-docx", file=sys.stderr)
            sys.exit(1)
        doc = Document(str(input_path))
        text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        text = input_path.read_text('utf-8', errors='replace') if input_path.exists() else sys.stdin.read()

    outline = parse_text(text)

    ch_nums = [int(c["number"]) for c in outline["chapters"] if c["number"].isdigit()]
    if ch_nums:
        expected = list(range(ch_nums[0], ch_nums[-1] + 1))
        missing = set(expected) - set(ch_nums)
        if missing:
            print(f"⚠️ 章节编号可能不连续，缺失: {missing}", file=sys.stderr)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)

    print(f"✅ 已输出: {args.output}（{len(outline['chapters'])}章，{sum(len(c.get('sections',[])) for c in outline['chapters'])}节）")

    if args.print_tasks:
        print()
        print_tasks(outline)


if __name__ == '__main__':
    main()
