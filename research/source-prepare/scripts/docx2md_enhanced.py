#!/usr/bin/env python3
"""
docx2md_enhanced.py — 增强版 DOCX→MD 转换器
使用 python-docx 检测标题（字体大小+节号），file2md 提取图片，
合并为结构完整的 MD 文件。

用法:
  python3 docx2md_enhanced.py input.docx output_dir/ [--split]
"""
import os, re, sys, json, shutil, subprocess, tempfile
from pathlib import Path
import docx
from docx.oxml.ns import qn

# 章节标题段落索引（font_size >= 20pt 且含中文）
CHAPTER_HEADS = {
    172: ("1", "电磁兼容技术概述"),
    507: ("2", "电磁兼容理论基础"),
    933: ("3", "干扰耦合机理"),
    1634: ("4", "滤波技术"),
    2298: ("5", "接地技术"),
    2832: ("6", "屏蔽技术"),
    3343: ("7", "印制电路板PCB的电磁兼容设计"),
    3973: ("8", "计算机系统中的电磁兼容性"),
    4362: ("9", "电磁兼容的预测与建模技术"),
}
CHAPTER_END = 4910  # Appendix start

def extract_structured_md(docx_path, output_dir, assets_dir, split=False):
    """提取结构化 MD（标题+正文+图片引用）"""
    doc = docx.Document(docx_path)
    
    # 先用 file2md 提取图片到 assets/
    file2md_script = Path(__file__).parent / "file2md.py"
    if file2md_script.exists():
        cmd = ["python3", str(file2md_script), str(docx_path), "-o", str(output_dir)]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    file2md_md = os.path.join(output_dir, f"{Path(docx_path).stem}.md")
    full_md_content = ""
    if os.path.exists(file2md_md):
        with open(file2md_md, "r", encoding="utf-8") as f:
            full_md_content = f.read()
    
    current_ch = 0
    ch_title = ""
    ch_sections = {}  # ch_num -> [(line_text, is_heading_level)]
    
    for i, p in enumerate(doc.paragraphs):
        if i < 172:  # Skip metadata
            continue
        if i >= CHAPTER_END:
            break
        
        text = p.text.strip()
        
        # Detect chapter heading
        if i in CHAPTER_HEADS:
            if current_ch > 0 and current_ch in ch_sections:
                pass  # Save previous chapter
            current_ch, ch_title = CHAPTER_HEADS[i]
            ch_sections[current_ch] = [("# " + ch_title, 1)]
            continue
        
        if current_ch == 0:
            continue
        
        lines = ch_sections[current_ch]
        
        # Detect section headings by section number pattern
        sec_m = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?\s+(.+)$', text)
        if sec_m:
            level = 4 if sec_m.group(3) else 3
            prefix = "#" * level + " "
            lines.append((prefix + text, level))
            continue
        
        # Skip page headers and page numbers
        if re.match(r'^\d+\s*电[磁]{1,2}兼容', text) or re.match(r'^电[磁]{1,2}兼容.*\d+$', text):
            continue
        if re.match(r'^\d+$', text) and len(text) <= 4:
            continue
        if text == "习 题" or text.startswith("习 题"):
            lines.append(("## 习题", 2))
            continue
        
        # Check for formula images in this paragraph
        drawings = p._element.findall('.//' + qn('w:drawing'))
        img_note = ""
        if drawings:
            img_note = f" [公式图片{len(drawings)}]"
        
        # Regular text
        cleaned = re.sub(r'\s*\d+\s+电磁兼容原理与技术\s*', '', text)
        if cleaned or img_note:
            lines.append((cleaned + img_note, 0))
    
    # Write chapter files
    chapter_files = {}
    for ch_num in sorted(ch_sections.keys()):
        lines = ch_sections[ch_num]
        ch_title_text = lines[0][0].replace("# ", "")
        fn = f"第{ch_num}章-{ch_title_text}.md"
        fp = os.path.join(output_dir, fn)
        
        content = "\n".join(f"  {l[0]}" if l[1]==0 else l[0] for l in lines)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        chapter_files[ch_num] = fp
        print(f"  ✅ 第{ch_num}章: {fn} ({len(lines)} lines)")
    
    return chapter_files
