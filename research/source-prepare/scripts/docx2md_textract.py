#!/usr/bin/env python3
"""
docx2md_textract.py — Python-docx 结构化提取（处理无标题样式的 .docx）
用于 file2md/pandoc 无法识别标题的文档。保留图片引用供后续合并。

用法:
  python3 docx2md_textract.py input.docx output_dir/ [--split]
"""
import os, re, sys, docx
from docx.oxml.ns import qn
from pathlib import Path

CHAPTER_HEADS = {
    172: (1, "电磁兼容技术概述"),
    507: (2, "电磁兼容理论基础"),
    933: (3, "干扰耦合机理"),
    1634: (4, "滤波技术"),
    2298: (5, "接地技术"),
    2832: (6, "屏蔽技术"),
    3343: (7, "印制电路板PCB的电磁兼容设计"),
    3973: (8, "计算机系统中的电磁兼容性"),
    4362: (9, "电磁兼容的预测与建模技术"),
}
CHAPTER_END = 4910

def extract(input_path, output_dir, split=False):
    if isinstance(input_path, str):
        input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = docx.Document(str(input_path))
    current_ch = 0
    ch_title = ""
    ch_data = {}  # ch_num -> [lines]
    
    for i, p in enumerate(doc.paragraphs):
        if i < 172:
            continue
        if i >= CHAPTER_END:
            break
        
        text = p.text.strip()
        
        if i in CHAPTER_HEADS:
            if current_ch > 0 and current_ch not in ch_data:
                ch_data[current_ch] = []
            current_ch, ch_title = CHAPTER_HEADS[i]
            ch_data[current_ch] = [("# " + ch_title, 1)]
            continue
        if current_ch == 0:
            continue
        
        lines = ch_data[current_ch]
        
        m = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?\s+(.+)$', text)
        if m:
            level = 4 if m.group(3) else 3
            prefix = "#" * level + " "
            lines.append((prefix + text, level))
            continue
        
        if re.match(r'^\d+\s*电[磁]{1,2}兼容', text):
            continue
        if re.match(r'^电[磁]{1,2}兼容.*\d+$', text):
            continue
        if re.match(r'^\d+$', text) and len(text) <= 4:
            continue
        if text == "习 题" or text.startswith("习 题"):
            lines.append(("## 习题", 2))
            continue
        
        drawings = p._element.findall('.//' + qn('w:drawing'))
        img_note = ""
        if drawings:
            img_note = " [公式图片%d]" % len(drawings)
        
        cleaned = re.sub(r'\s*\d+\s+电磁兼容原理与技术\s*', '', text)
        if cleaned or img_note:
            lines.append((cleaned + img_note, 0))
    
    # Write chapter files
    for ch_num in sorted(ch_data.keys()):
        lines = ch_data[ch_num]
        ch_title_text = lines[0][0].replace("# ", "")
        fn = "第%d章-%s.md" % (ch_num, re.sub(r'[\\/:*?"<>|]', '', ch_title_text)[:40])
        fp = output_dir / fn
        
        content_lines = []
        for l, level in lines:
            if level == 0:
                content_lines.append("  " + l)
            else:
                content_lines.append(l)
        
        content = "\n".join(content_lines)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        
        n_h = sum(1 for _, l in lines if l > 0)
        n_img_txt = content.count("[公式图片")
        print("  ✅ 第%d章: %s (%d行, %d标题, %d公式图片)" % (
            ch_num, fn, len(lines), n_h, n_img_txt))
    
    return list(ch_data.keys())

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("用法: python3 docx2md_textract.py input.docx output_dir/ [--split]")
        sys.exit(1)
    split = '--split' in sys.argv
    extract(sys.argv[1], sys.argv[2], split)
