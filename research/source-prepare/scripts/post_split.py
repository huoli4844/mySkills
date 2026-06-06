#!/usr/bin/env python3
"""
post_split.py — 从 file2md 的完整 MD 中，用 ## N.1 节号正确分割章节
用法: python3 post_split.py <full_md> <output_dir>
"""
import re, sys, os

def split_by_sections(md_content, source_name, output_dir):
    lines = md_content.split('\n')
    
    # 找出每个章节的第一个 ## N.1 节号
    ch_starts = {}  # ch_num -> (line_idx, title)
    for i, line in enumerate(lines):
        m = re.match(r'^##\s+(\d+)\.(\d+)\s+(.+)$', line)
        if m:
            ch_num = int(m.group(1))
            sec_num = int(m.group(2))
            if sec_num == 1:  # N.1 表示新章节开始
                if '](#bookmark' not in line:
                    if ch_num not in ch_starts:
                        ch_starts[ch_num] = (i, m.group(3).strip())
    
    if not ch_starts:
        print("❌ 未检测到章节边界")
        return []
    
    sorted_chs = sorted(ch_starts.keys())
    print(f"🔍 检测到 {len(sorted_chs)} 章: {sorted_chs}")
    
    os.makedirs(output_dir, exist_ok=True)
    output_files = []
    
    for idx, ch_num in enumerate(sorted_chs):
        start, ch_title = ch_starts[ch_num]
        end = ch_starts[sorted_chs[idx+1]][0] if idx+1 < len(sorted_chs) else len(lines)
        
        # Extract chapter body
        ch_body_lines = lines[start:end]
        if not ch_body_lines:
            continue
        
        # Find chapter display title (from # 第N章 if present)
        display_title = f"第{ch_num}章 {ch_title}"
        for line in ch_body_lines:
            m2 = re.match(r'^#\s+第\s*{}\s*章\s+(.+)$'.format(ch_num), line)
            if m2:
                t = re.sub(r'!\[.*?\]\(.*?\)', '', m2.group(1)).strip()
                t = re.sub(r'\*\*', '', t).strip()
                t = re.sub(r'\s+', ' ', t).strip()
                if t and "图片" not in t:
                    display_title = f"第{ch_num}章 {t}"
                    break
        
        body = '\n'.join(ch_body_lines).strip()
        if not body:
            continue
        
        safe_title = re.sub(r'[\\/:*?"<>|]', '', ch_title)[:40]
        fn = f"第{ch_num}章-{safe_title}.md"
        fp = os.path.join(output_dir, fn)
        
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(body + '\n')
        output_files.append(fp)
        
        n_h = len(re.findall(r'^#{1,6}\s', body, re.MULTILINE))
        n_img = body.count('![')
        print(f"  ✅ 第{ch_num}章: {fn} ({len(body)} bytes, {n_h}标题, {n_img}图片)")
    
    return output_files

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python3 post_split.py <full_md> <output_dir>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        content = f.read()
    
    split_by_sections(content, sys.argv[1], sys.argv[2])
