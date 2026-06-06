#!/usr/bin/env python3
"""pdf2md — PDF → Markdown（Docling 引擎）

PDF 专用解析逻辑，由 file2md.py 主入口调用。
"""

import os
import re
import sys
from pathlib import Path


def extract_pdf(pdf_path: str, output_dir: str, opts: dict,
                generate_frontmatter, split_by_chapters,
                rename_images_by_caption) -> str:
    """
    PDF → Markdown（Docling 引擎）

    Docling 优势：结构化文档理解，支持表格/图片/布局分析
    """
    from file2md import _ensure_dir, _sha256

    _ensure_dir(output_dir)
    assets_dir = os.path.join(output_dir, 'assets')
    _ensure_dir(assets_dir)

    md_content = _try_docling(pdf_path, output_dir, assets_dir, opts)
    if md_content is None:
        print("❌ Docling 引擎不可用，请安装: pip install docling")
        sys.exit(1)

    # 后处理
    md_content = _postprocess_pdf_md(md_content)

    # 用题注重命名图片文件和MD中的引用
    md_content = rename_images_by_caption(md_content, assets_dir)

    # 生成 frontmatter
    frontmatter = generate_frontmatter(pdf_path, md_content)
    md_with_fm = frontmatter + md_content

    # 输出文件名
    stem = Path(pdf_path).stem
    out_file = os.path.join(output_dir, f"{stem}.md")

    # 按章节分割（如果启用）
    split = opts.get('split', False)
    if split:
        split_files = split_by_chapters(md_content, pdf_path, output_dir)
        if split_files:
            print(f"✅ PDF 解析完成: {len(split_files)} 章")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(md_with_fm)
            return out_file

    # 写入输出
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(md_with_fm)

    n_images = len(list(Path(assets_dir).glob('*'))) if os.path.isdir(assets_dir) else 0
    n_headings = len(re.findall(r'^#{1,6}\s', md_content, re.MULTILINE))
    print(f"✅ PDF 解析完成: {out_file}")
    print(f"   📊 {n_headings} 标题, {n_images} 图片")
    return out_file


# ══════════════════════════════════════════════════════════════
# Docling 引擎
# ══════════════════════════════════════════════════════════════

def _try_docling(pdf_path: str, output_dir: str, assets_dir: str, opts: dict):
    """使用 Docling 引擎解析 PDF"""
    from file2md import _sha256

    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption
    except ImportError:
        return None

    try:
        print("🔄 使用 Docling 引擎解析 PDF...")

        pipeline_opts = PdfPipelineOptions()
        pipeline_opts.do_ocr = opts.get('ocr', True)
        pipeline_opts.do_table_structure = True
        pipeline_opts.generate_page_images = False
        pipeline_opts.generate_picture_images = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
            }
        )

        result = converter.convert(pdf_path)
        doc = result.document

        # 提取图片
        _extract_docling_images(doc, assets_dir)

        # 导出为 Markdown
        md_content = doc.export_to_markdown()

        # 修正图片路径和占位符
        md_content = _fix_docling_image_paths(md_content, assets_dir)

        print(f"   ✅ Docling 解析成功")
        return md_content

    except Exception as e:
        print(f"   ⚠️  Docling 解析失败: {e}")
        return None


def _extract_docling_images(doc, assets_dir: str):
    """从 Docling 文档中提取 PictureItem / FormulaItem 的图片"""
    from file2md import _sha256
    import io

    try:
        from PIL import Image
    except ImportError:
        return

    img_counter = 0
    saved_hashes = set()

    for item, _level in doc.iterate_items():
        if item.label not in ('picture', 'formula'):
            continue
        pil_img = item.get_image(doc)
        if pil_img is None:
            continue

        # 去重：基于像素内容 hash
        buf = io.BytesIO()
        pil_img.save(buf, format='PNG')
        data = buf.getvalue()
        hsh = _sha256(data)
        if hsh in saved_hashes:
            continue
        saved_hashes.add(hsh)

        img_counter += 1
        w, h = pil_img.size
        # 过滤小图（图标/装饰）：宽<50或高<20的图片跳过
        if w < 50 or h < 20:
            continue
        if item.label == 'formula':
            fname = f"formula-{img_counter:03d}.png"
        else:
            fname = f"image-{img_counter:03d}.png"

        fpath = os.path.join(assets_dir, fname)
        pil_img.save(fpath)

    if img_counter > 0:
        print(f"   🖼️  提取 {img_counter} 张图片")


def _fix_docling_image_paths(md_content: str, assets_dir: str) -> str:
    """修正 Docling 输出中的图片引用路径，处理占位符"""
    img_files = sorted(Path(assets_dir).glob('*')) if os.path.isdir(assets_dir) else []
    if not img_files:
        md_content = re.sub(r'<!--\s*image\s*-->', '', md_content)
        md_content = re.sub(r'<!--\s*formula-not-decoded\s*-->', '', md_content)
        return md_content

    img_idx = [0]

    # 1. 替换 ![caption](path) 格式的图片引用
    def _replace_img(m):
        caption = m.group(1)
        if img_idx[0] < len(img_files):
            new_path = f"assets/{img_files[img_idx[0]].name}"
            img_idx[0] += 1
            return f"![{caption}]({new_path})"
        return m.group(0)

    md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replace_img, md_content)

    # 2. 替换 <!-- image --> 占位符
    def _replace_placeholder(m):
        if img_idx[0] < len(img_files):
            new_path = f"assets/{img_files[img_idx[0]].name}"
            name = img_files[img_idx[0]].stem
            img_idx[0] += 1
            return f"![{name}]({new_path})"
        return ''

    md_content = re.sub(r'<!--\s*image\s*-->', _replace_placeholder, md_content)

    # 3. 替换 <!-- formula-not-decoded --> 占位符
    formula_idx = [0]
    formula_files = []
    for f in img_files:
        try:
            from PIL import Image
            with Image.open(str(f)) as im:
                w, h = im.size
                if 50 < w < 1000 and h < 200 and w / h > 1.5:
                    formula_files.append((f, w, h))
        except Exception:
            pass

    if formula_files:
        def _replace_formula(m):
            if formula_idx[0] < len(formula_files):
                f, w, h = formula_files[formula_idx[0]]
                new_path = f"assets/{f.name}"
                formula_idx[0] += 1
                return f"![公式]({new_path})"
            return ''
        md_content = re.sub(r'<!--\s*formula-not-decoded\s*-->', _replace_formula, md_content)
    else:
        md_content = re.sub(r'<!--\s*formula-not-decoded\s*-->', '', md_content)

    return md_content


# ══════════════════════════════════════════════════════════════
# PDF 后处理
# ══════════════════════════════════════════════════════════════

def _postprocess_pdf_md(md: str) -> str:
    """PDF 输出后处理：修正 Docling 输出的各种问题"""
    # 1. 过滤页眉页脚残留
    md = re.sub(r'^#{0,6}\s*第\s*\d+\s*章[^\n]*[·•]\s*\d+\s*[·•][^\n]*$', '', md, flags=re.MULTILINE)
    # 2. 过滤纯页码行
    md = re.sub(r'^\s*[·•]\s*\d+\s*[·•]\s*$', '', md, flags=re.MULTILINE)

    lines = md.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # ── 3. 合并 Docling 分割标题 ──
        if re.match(r'^#{1,6}\s+\d+\s*$', line) or re.match(r'^#{1,6}\s+[（(]\s*$', line):
            merged = re.sub(r'^#{1,6}\s+', '', line)
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                next_line = lines[j]
                if re.match(r'^#{1,6}\s+', next_line):
                    next_text = re.sub(r'^#{1,6}\s+', '', next_line)
                    merged = merged + next_text
                    fixed_lines.append(merged)
                    i = j + 1
                    continue
                elif re.match(r'^\s*[.．、]\s*\S', next_line) or re.match(r'^\d+\s*[）)]\s*\S', next_line):
                    merged = merged + next_line
                    fixed_lines.append(merged)
                    i = j + 1
                    continue
            fixed_lines.append(merged)
            i += 1
            continue

        # ── 4. 修正错误标题级别 ──
        if re.match(r'^#{1,6}\s+[（(]\s*\d+\s*[）)]\s*\S', line):
            text = re.sub(r'^#{1,6}\s+', '', line)
            fixed_lines.append(text)
            i += 1
            continue
        elif re.match(r'^#{1,6}\s+[①②③④⑤⑥⑦⑧⑨⑩]', line):
            text = re.sub(r'^#{1,6}\s+', '', line)
            fixed_lines.append(text)
            i += 1
            continue
        elif re.match(r'^#{1,6}\s+\d+\s*[.．、]\s*\S', line) and not re.match(r'^#{1,6}\s+\d+(?:\.\d+)+\s', line):
            text = re.sub(r'^#{1,6}\s+', '', line)
            fixed_lines.append('#### ' + text)
            i += 1
            continue

        # ── 5. 过滤误判标题 ──
        if re.match(r'^#{1,6}\s+', line):
            title_text = re.sub(r'^#{1,6}\s+', '', line)
            is_real_heading = bool(
                re.match(r'第\s*\d+\s*[章节]', title_text) or
                re.match(r'\d+(?:\.\d+){0,2}\s+', title_text) or
                re.match(r'习\s*题', title_text) or
                re.match(r'附\s*录', title_text) or
                re.match(r'参\s*考\s*文\s*献', title_text) or
                re.match(r'目\s*录', title_text)
            )
            if not is_real_heading and len(title_text) < 4:
                fixed_lines.append(title_text)
                i += 1
                continue
            if not is_real_heading and len(title_text) < 15 and not re.search(r'[章节节]', title_text):
                if re.search(r'[，。；：、]', title_text) or title_text.startswith(('可', '解', '将', '由', '若', '假', '设', '对', '为', '则', '从', '令', '因')):
                    fixed_lines.append(title_text)
                    i += 1
                    continue

        fixed_lines.append(line)
        i += 1

    md = '\n'.join(fixed_lines)

    # 3b. 反向合并
    lines2 = md.split('\n')
    merged_lines = []
    i = 0
    while i < len(lines2):
        line = lines2[i]
        if re.match(r'^#{1,6}\s+[.．、）)]\s*\S', line):
            text = re.sub(r'^#{1,6}\s+', '', line)
            j = i + 1
            while j < len(lines2) and lines2[j].strip() == '':
                j += 1
            if j < len(lines2):
                next_line = lines2[j]
                if re.match(r'^#{0,6}\s*\d+\s*[）)]?\s*$', next_line):
                    num_text = re.sub(r'^#{1,6}\s+', '', next_line)
                    merged_text = num_text + text
                    if merged_lines and merged_lines[-1].strip():
                        merged_lines[-1] = merged_lines[-1] + '\n' + merged_text
                    else:
                        merged_lines.append(merged_text)
                    i = j + 1
                    continue
            if merged_lines:
                for k in range(len(merged_lines) - 1, -1, -1):
                    if merged_lines[k].strip():
                        merged_lines[k] = merged_lines[k] + text
                        break
            else:
                merged_lines.append(text)
            i += 1
            continue
        merged_lines.append(line)
        i += 1
    md = '\n'.join(merged_lines)

    # ── 6. 修正标题层级 ──
    md = re.sub(r'^(#{1,6})\s+(第\s*\d+\s*章\s+\S)',
                lambda m: '# ' + re.sub(r'^#{1,6}\s+', '', m.group(0)), md, flags=re.MULTILINE)
    md = re.sub(r'^#{1,6}\s+(\d+\.\d+\.\d+\s+\S)',
                lambda m: '### ' + m.group(1), md, flags=re.MULTILINE)
    md = re.sub(r'^#{1,6}\s+(\d+\.\d+\s+\S[^.])',
                lambda m: '## ' + m.group(1), md, flags=re.MULTILINE)
    md = re.sub(r'^#{1,6}\s+(习\s*题[^\n]*)',
                lambda m: '## ' + m.group(1), md, flags=re.MULTILINE)

    # 7. 多余空行压缩
    md = re.sub(r'\n{4,}', '\n\n\n', md)

    # 7b. 修复表格格式
    from file2md import _fix_table_blank_lines
    md = _fix_table_blank_lines(md)

    # 8. 清理残留 HTML 注释占位符
    md = re.sub(r'<!--\s*image\s*-->', '', md)
    md = re.sub(r'<!--\s*formula-not-decoded\s*-->', '', md)
    md = re.sub(r'<!--\s*公式\d+\s*-->', '', md)
    md = re.sub(r'<!--\s*图片\d+\s*-->', '', md)
    md = re.sub(r'<!--\s*表格\d+\s*-->', '', md)

    return md.strip() + '\n'
