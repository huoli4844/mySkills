#!/usr/bin/env python3
"""
file2md — 高保真文档解析工具 v3.2.0

将 PDF/DOCX 文件最大限度还原为 Markdown，保留：
- 目录结构（标题层级）
- 正文段落与格式
- 数学公式（LaTeX，Docling/pandoc引擎提取）
- 表格（Markdown table）
- 图片（提取到 assets/ 目录）
- 列表、引用等结构

引擎策略：
- DOCX → pandoc（原生 OMML 公式转 LaTeX，表格/图片全量提取）
- PDF  → Docling（结构化文档理解引擎）

模块结构：
- file2md.py   — 主入口 + 共享工具函数
- docx2md.py   — DOCX 专用逻辑（pandoc 转换 + LaTeX 修复 + 后处理）
- pdf2md.py    — PDF 专用逻辑（Docling 解析 + 图片提取 + 后处理）
"""

import os
import re
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import date

__version__ = "3.2.0"


# ══════════════════════════════════════════════════════════════
# 共享工具函数
# ══════════════════════════════════════════════════════════════

def _safe_filename(name: str, max_len: int = 80) -> str:
    """生成安全文件名"""
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '', name)
    safe = re.sub(r'\s+', ' ', safe).strip()
    return safe[:max_len].rstrip('. ') or 'unnamed'


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _find_pandoc() -> str:
    """搜索 pandoc 可执行文件路径（多路径搜索 + pypandoc_binary 缓存）"""
    candidates = [
        'pandoc',
        os.path.expanduser('~/bin/pandoc'),
        '/opt/homebrew/bin/pandoc',
        '/usr/local/bin/pandoc',
        '/usr/bin/pandoc',
    ]
    # 尝试 pypandoc_binary 的缓存路径
    try:
        import pypandoc
        pp = pypandoc.get_pandoc_path()
        if pp and os.access(pp, os.X_OK):
            return pp
    except Exception:
        pass
    for c in candidates:
        if os.sep in c:
            if os.access(c, os.X_OK):
                return c
        else:
            try:
                r = subprocess.run(['which', c], capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    return r.stdout.strip()
            except Exception:
                pass
    return None


def _resolve_name(fname: str, used: set) -> str:
    """文件名去重：重名时追加 -2, -3 ... 后缀"""
    if fname not in used:
        used.add(fname)
        return fname
    base, ext = os.path.splitext(fname)
    n = 2
    while f"{base}-{n}{ext}" in used:
        n += 1
    fname = f"{base}-{n}{ext}"
    used.add(fname)
    return fname


def _caption_to_filename(caption: str, ext: str) -> str:
    """图片题注转文件名（6层截断策略，≤80字符）

    截断层（优先级从高到低）：
    1. 全角标点截断：[。！？，,] 取前段
    2. 说明性词语前截断：根据/由/当/若/设/其中/式中...
    3. 希腊字母后接等号/数字前截断
    4. 后续图号前截断（防双题注粘连）
    5. 括号数学公式剥离（≤30字符的括号内容）
    6. 前导分隔符清除
    """
    if not caption:
        return f"图.{ext}"
    fig = re.match(r'^(图\s*\d+(?:[-._]\d+){1,2})', caption)
    fig_num = fig.group(1).replace(' ', '') if fig else ''
    body = caption[fig.end():].strip() if fig else caption
    body = re.split(r'[。！？，,]', body)[0].strip()
    body = re.split(r'(?:根据|由|当|若|设|其中|式中|这里|因此|所以|则[\s\d]|即[\s\d]|可[\s\d]|在[\s\d])', body)[0].strip()
    body = re.split(r'(?:\s[α-ω]\s*[=＝]\s*[\d°]|\s[α-ω]\s+角)', body)[0].strip()
    body = re.split(r'(?:\s+图\s*\d+(?:[-._]\d+){0,2})', body)[0].strip()
    body = re.sub(r'[（(][^）)]{1,30}[）)]', '', body).strip()
    body = re.sub(r'^[-\s\-—_]+', '', body).strip()
    body = body[:40].rstrip()
    raw = f"{fig_num}-{body}".strip('-') or caption
    safe = re.sub(r'[\\/:*?"<>|]', '', raw)
    safe = re.sub(r'\s+', ' ', safe).strip()[:80].rstrip('. ')
    return f"{safe}.{ext}"


def _generate_frontmatter(source_file: str, md_content: str, **extra) -> str:
    """生成 YAML frontmatter"""
    sha = hashlib.sha256(md_content.encode()).hexdigest()
    fm = {
        "title": Path(source_file).stem,
        "source": os.path.basename(source_file),
        "parser": "file2md",
        "version": __version__,
        "sha256": sha,
        "ingested": str(date.today()),
    }
    fm.update(extra)
    return f"---\n{json.dumps(fm, ensure_ascii=False, indent=2)}\n---\n\n"


# 章节检测正则（供外部引用）
RE_CHAPTER = re.compile(r'第\s*(\d+)\s*章\s+(.+)')

def _fix_table_blank_lines(md: str) -> str:
    """修复 GFM 表格格式：行间空行删除，表格前后必须有空行"""
    md = re.sub(r'(\|[^\n]+)\n\n+(\|)', r'\1\n\2', md)
    md = re.sub(r'([^|\n])\n(\|)', r'\1\n\n\2', md)
    return md


def _fix_image_paths_to_assets(md_content: str, assets_dir: str) -> str:
    """将 MD 中所有图片引用路径统一修正为 assets/ 相对路径"""
    if not os.path.isdir(assets_dir):
        return md_content
    actual_files = {f.name for f in Path(assets_dir).iterdir() if f.is_file()}
    if not actual_files:
        return md_content

    def _fix_path(m):
        alt = m.group(1)
        raw_path = m.group(2)
        fname = os.path.basename(raw_path)
        if fname in actual_files:
            return f'![{alt}](assets/{fname})'
        return m.group(0)

    md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _fix_path, md_content)
    return md_content


def _split_by_chapters(md_content: str, source_file: str, output_dir: str) -> list:
    """按章节标题分割 MD 内容为多个文件

    检测 `第N章 标题` 模式的标题行作为分割点，
    每章生成独立 MD 文件（带 frontmatter），assets/ 目录共用。

    Returns:
        list: 输出文件路径列表；如果未检测到章节则返回空列表
    """
    lines = md_content.split('\n')

    chapter_lines = []  # [(line_idx, ch_num, ch_title)]
    for i, line in enumerate(lines):
        # 跳过目录条目（含 ](# 链接标记）
        if '](#bookmark' in line or '](#电' in line:
            continue
        m = re.match(r'^#{0,6}\s*第\s*(\d+)\s*章\s+(.+)', line)
        if m:
            ch_num = int(m.group(1))
            ch_title = m.group(2).strip()
            
            # 清理页眉污染：去掉图片引用、HTML标签、页码、加粗标记
            ch_title_clean = re.sub(r'!\[.*?\]\(.*?\)', '', ch_title)
            ch_title_clean = re.sub(r'</?u>', '', ch_title_clean)
            ch_title_clean = re.sub(r'\*\*', '', ch_title_clean)
            ch_title_clean = re.sub(r'\s*\d+$', '', ch_title_clean)  # 去掉末尾页码
            ch_title_clean = re.sub(r'\s+', ' ', ch_title_clean).strip()  # 空白归一
            
            if re.search(r'[·•]\s*\d+\s*[·•]', ch_title_clean):
                continue
            # 跳过非中文标题（目录项如 "CHAPTER 2"）
            if not re.search(r'[\u4e00-\u9fff]', ch_title_clean):
                continue
            if 1 <= ch_num <= 99 and len(ch_title_clean) < 80:
                # 跳过含图片的行（页眉）
                if '![' in ch_title:
                    continue
                chapter_lines.append((i, ch_num, ch_title_clean))

    # 去重：保留每个章节第一次出现（目录项已在上方过滤）
    seen_ch = set()
    deduped = []
    for item in chapter_lines:
        if item[1] not in seen_ch:
            seen_ch.add(item[1])
            deduped.append(item)
    chapter_lines = deduped

    if not chapter_lines:
        return []

    print(f"🔍 检测到 {len(chapter_lines)} 章: {[(c, t) for _, c, t in chapter_lines]}")

    output_files = []
    for idx, (line_idx, ch_num, ch_title) in enumerate(chapter_lines):
        end_idx = chapter_lines[idx + 1][0] if idx + 1 < len(chapter_lines) else len(lines)

        if idx == 0 and line_idx > 0:
            ch_body = '\n'.join(lines[:end_idx])
        else:
            ch_body = '\n'.join(lines[line_idx:end_idx])

        ch_body = ch_body.strip()
        if not ch_body:
            continue

        fm = _generate_frontmatter(
            source_file, ch_body,
            title=f"第{ch_num}章 {ch_title}",
            chapter=ch_num
        )

        safe_title = _safe_filename(ch_title, max_len=40)
        out_name = f"第{ch_num}章-{safe_title}.md"
        out_path = os.path.join(output_dir, out_name)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(fm + ch_body + '\n')

        output_files.append(out_path)

        n_h = len(re.findall(r'^#{1,6}\s', ch_body, re.MULTILINE))
        n_img = ch_body.count('![')
        n_tbl = ch_body.count('\n|')
        print(f"   📄 第{ch_num}章 {ch_title}: {n_h}标题, {n_img}图, ~{n_tbl}表格行")

    return output_files


def _rename_images_by_caption(md_content: str, assets_dir: str) -> str:
    """扫描 MD 内容中的图片题注，用题注重命名图片文件和引用路径。

    命名规则：
    - 有题注：图3.1.1-比幅单脉冲测向原理.png（6层截断策略）
    - 无题注：保持原名 image-001.png
    """
    if not os.path.isdir(assets_dir):
        return md_content

    lines = md_content.split('\n')
    img_refs = []  # [(line_idx, old_path, caption_in_md)]
    img_pattern = re.compile(r'!\[([^\]]*)\]\(assets/([^)]+)\)')

    for i, line in enumerate(lines):
        m = img_pattern.search(line)
        if m:
            img_refs.append((i, m.group(2), m.group(1)))

    if not img_refs:
        return md_content

    caption_re = re.compile(r'^[\s*]*图\s*(\d+(?:[.\-]\d+)*)\s*(.*)')
    en_caption_re = re.compile(r'^[\s*]*(?:Figure|Fig\.?)\s*(\d+(?:[.\-]\d+)*)\s*(.*)')

    rename_map = {}
    used_names = set()

    for line_idx, old_fname, md_caption in img_refs:
        caption_text = None
        fig_num = None

        # 策略1：图片引用下方2行内查找题注
        for delta in (1, 2):
            target = line_idx + delta
            if target >= len(lines):
                break
            target_line = lines[target].strip()
            clean = re.sub(r'^[*]+\s*', '', target_line)
            clean = re.sub(r'\s*[*]+$', '', clean)
            cm = caption_re.match(clean)
            if not cm:
                cm = en_caption_re.match(clean)
            if cm:
                fig_num = cm.group(1)
                caption_text = cm.group(2).strip()
                break

        # 策略2：图片引用上方2行内查找题注
        if caption_text is None:
            for delta in (1, 2):
                target = line_idx - delta
                if target < 0:
                    break
                target_line = lines[target].strip()
                clean = re.sub(r'^[*]+\s*', '', target_line)
                clean = re.sub(r'\s*[*]+$', '', clean)
                cm = caption_re.match(clean)
                if not cm:
                    cm = en_caption_re.match(clean)
                if cm:
                    fig_num = cm.group(1)
                    caption_text = cm.group(2).strip()
                    break

        # 策略3：从 MD 引用的 alt text 提取题注
        if caption_text is None and md_caption:
            clean = md_caption.strip()
            cm = caption_re.match(clean)
            if not cm:
                cm = en_caption_re.match(clean)
            if cm:
                fig_num = cm.group(1)
                caption_text = cm.group(2).strip()

        # 构造新文件名（6层截断策略）
        if caption_text is not None and fig_num is not None:
            full_caption = f"图{fig_num} {caption_text}"
            ext = os.path.splitext(old_fname)[1]
            new_name = _caption_to_filename(full_caption, ext.lstrip('.'))
        else:
            continue

        new_name = _resolve_name(new_name, used_names)
        rename_map[old_fname] = new_name

    # 执行重命名
    for old_fname, new_fname in rename_map.items():
        old_path = os.path.join(assets_dir, old_fname)
        new_path = os.path.join(assets_dir, new_fname)
        if os.path.exists(old_path) and old_fname != new_fname:
            os.rename(old_path, new_path)

    # 替换 MD 中的引用
    for old_fname, new_fname in rename_map.items():
        md_content = md_content.replace(f'assets/{old_fname}', f'assets/{new_fname}')
        new_stem = os.path.splitext(new_fname)[0]
        md_content = re.sub(
            rf'!\[[^\]]*\]\(assets/{re.escape(new_fname)}\)',
            f'![{new_stem}](assets/{new_fname})',
            md_content
        )

    renamed_count = len(rename_map)
    if renamed_count:
        print(f"   📷 {renamed_count} 张图片已用题注命名")

    return md_content


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f'file2md v{__version__} — 高保真文档转 Markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 file2md.py input.docx -o output/
  python3 file2md.py input.pdf -o output/ --engine docling
  python3 file2md.py input.docx --split     # 按章节分割
        """
    )
    parser.add_argument('input', help='输入文件路径 (PDF 或 DOCX)')
    parser.add_argument('-o', '--output', default=None,
                        help='输出目录（默认：输入文件同目录）')
    parser.add_argument('--engine', choices=['docling'],
                        default='docling', help='PDF 解析引擎 (默认: docling)')
    parser.add_argument('--ocr', action='store_true', default=True,
                        help='启用 OCR（PDF 扫描件，默认开启）')
    parser.add_argument('--no-ocr', action='store_true',
                        help='禁用 OCR')
    parser.add_argument('--split', action='store_true',
                        help='按章节分割输出多文件（检测"第N章"标题边界）')

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    # 确定输出目录
    if args.output:
        output_dir = os.path.abspath(args.output)
    else:
        output_dir = os.path.dirname(input_path)
    _ensure_dir(output_dir)

    # 选项
    opts = {
        'pdf_engine': args.engine,
        'ocr': not args.no_ocr,
        'split': args.split,
    }

    # 按需导入对应模块
    ext = os.path.splitext(input_path)[1].lower()
    if ext == '.docx':
        print(f"📄 DOCX 模式: {os.path.basename(input_path)}")
        from docx2md import extract_docx
        extract_docx(
            input_path, output_dir, opts,
            find_pandoc=_find_pandoc,
            generate_frontmatter=_generate_frontmatter,
            split_by_chapters=_split_by_chapters,
            fix_image_paths_to_assets=_fix_image_paths_to_assets,
            rename_images_by_caption=_rename_images_by_caption,
        )
    elif ext == '.pdf':
        print(f"📄 PDF 模式: {os.path.basename(input_path)}")
        from pdf2md import extract_pdf
        extract_pdf(
            input_path, output_dir, opts,
            generate_frontmatter=_generate_frontmatter,
            split_by_chapters=_split_by_chapters,
            rename_images_by_caption=_rename_images_by_caption,
        )
    else:
        print(f"❌ 不支持的文件格式: {ext}（仅支持 .pdf / .docx）")
        sys.exit(1)


if __name__ == '__main__':
    main()
