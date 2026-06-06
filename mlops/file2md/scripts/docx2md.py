#!/usr/bin/env python3
"""docx2md — DOCX → Markdown（pandoc 引擎）

DOCX 专用解析逻辑，由 file2md.py 主入口调用。
"""

import os
import re
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_docx(docx_path: str, output_dir: str, opts: dict,
                 find_pandoc, generate_frontmatter, split_by_chapters,
                 fix_image_paths_to_assets, rename_images_by_caption) -> str:
    """
    DOCX → Markdown（pandoc 引擎）

    pandoc 优势：
    - OMML 公式 → LaTeX ($..$ / $$..$$)
    - 表格完整保留
    - 图片自动提取到 media/
    - 标题层级完整
    - 列表、引用、脚注等结构
    """
    from file2md import _ensure_dir, _resolve_name

    pandoc_cmd = find_pandoc()
    if not pandoc_cmd:
        print("❌ pandoc 未安装。请执行: brew install pandoc (macOS) 或 apt install pandoc (Linux)")
        sys.exit(1)

    _ensure_dir(output_dir)
    assets_dir = os.path.join(output_dir, 'assets')
    _ensure_dir(assets_dir)

    # 使用临时目录提取 media
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = os.path.join(tmpdir, 'media')

        # pandoc 核心转换命令
        cmd = [
            pandoc_cmd,
            docx_path,
            '-t', 'gfm+tex_math_dollars+pipe_tables+raw_html',
            '--wrap=none',                    # 不折行，保留原始段落
            '--extract-media', tmpdir,        # 提取图片到临时目录
            '--markdown-headings=atx',        # 使用 # 风格标题
            '--columns=10000',                # 防止宽表格被截断
        ]

        # 可选：保留原始 HTML 表格（复杂表格）
        if opts.get('raw_html_tables'):
            cmd.extend(['-t', 'gfm+tex_math_dollars+raw_html'])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"❌ pandoc 转换失败:\n{result.stderr}")
            sys.exit(1)

        md_content = result.stdout

        # 处理图片：将 media/ 中的图片移动到 assets/ 并修正路径
        img_path_map = {}  # old_basename → new_assets_path
        used_names = set()
        if os.path.isdir(media_dir):
            img_counter = 0
            for root, _, files in os.walk(media_dir):
                for fname in sorted(files):
                    img_counter += 1
                    src = os.path.join(root, fname)
                    ext = os.path.splitext(fname)[1].lower() or '.png'

                    new_name = f"image-{img_counter:03d}{ext}"
                    new_name = _resolve_name(new_name, used_names)

                    dst = os.path.join(assets_dir, new_name)
                    shutil.copy2(src, dst)

                    # 记录映射：原始文件名 → assets/新名
                    img_path_map[fname] = f"assets/{new_name}"

        # 修正 markdown 中的图片路径（支持相对路径和绝对路径）
        for old_fname, new_path in img_path_map.items():
            # 替换相对路径（media/image1.jpeg）
            md_content = md_content.replace(f"media/{old_fname}", new_path)
            # 替换绝对路径中包含的文件名
            md_content = re.sub(
                r'[\w/.-]+/media/' + re.escape(old_fname),
                new_path,
                md_content
            )

        # 也处理可能的反斜杠路径（Windows 兼容）
        md_content = md_content.replace('\\', '/')

    # 后处理：清理 pandoc 输出的常见问题
    md_content = _postprocess_docx_md(md_content)

    # 统一修正图片路径
    md_content = fix_image_paths_to_assets(md_content, assets_dir)

    # 用题注重命名图片文件和MD中的引用（6层截断策略）
    md_content = rename_images_by_caption(md_content, assets_dir)

    # 生成 frontmatter
    frontmatter = generate_frontmatter(docx_path, md_content)
    md_with_fm = frontmatter + md_content

    # 输出文件名
    stem = Path(docx_path).stem
    out_file = os.path.join(output_dir, f"{stem}.md")

    # 按章节分割（如果启用）
    split = opts.get('split', False)
    if split:
        split_files = split_by_chapters(md_content, docx_path, output_dir)
        if split_files:
            print(f"✅ DOCX 解析完成: {len(split_files)} 章")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(md_with_fm)
            return out_file

    # 写入输出文件
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(md_with_fm)

    # 统计
    n_images = len(list(Path(assets_dir).glob('*'))) if os.path.isdir(assets_dir) else 0
    n_tables = md_content.count('\n|')
    n_formulas = md_content.count('$$') // 2 + md_content.count('$') // 2
    n_headings = len(re.findall(r'^#{1,6}\s', md_content, re.MULTILINE))

    print(f"✅ DOCX 解析完成: {out_file}")
    print(f"   📊 {n_headings} 标题, {n_images} 图片, ~{n_tables} 表格行, ~{n_formulas} 公式")
    return out_file


# ══════════════════════════════════════════════════════════════
# DOCX 后处理
# ══════════════════════════════════════════════════════════════

def _postprocess_docx_md(md: str) -> str:
    """pandoc 输出后处理"""
    # 1. 将 HTML <img> 标签转换为 Markdown 图片引用
    def _html_img_to_md(m):
        src = m.group(1)
        alt = m.group(2) or 'image'
        fname = os.path.basename(src)
        if alt == 'image':
            alt = os.path.splitext(fname)[0]
        return f'![{alt}]({src})'
    md = re.sub(r'<img\s+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?\s*>', _html_img_to_md, md)
    md = re.sub(r'<img\s+src="([^"]+)"[^>]*/?\s*>', lambda m: f'![image]({m.group(1)})', md)

    # 2. 将 <figcaption><p>...</p></figcaption> 转为纯文本行
    md = re.sub(r'<figcaption><p>(.*?)</p></figcaption>', lambda m: m.group(1).strip(), md)
    md = re.sub(r'<figcaption[^>]*>(.*?)</figcaption>', lambda m: m.group(1).strip(), md)

    # 3. 修复 pandoc DOCX 输出中的 LaTeX 反斜杠问题
    latex_commands = [
        'circ', 'theta', 'varphi', 'phi', 'psi', 'omega', 'alpha', 'beta', 'gamma',
        'delta', 'epsilon', 'lambda', 'mu', 'sigma', 'rho', 'tau', 'pi',
        'frac', 'sqrt', 'left', 'right', 'overline', 'underline', 'hat', 'bar',
        'dot', 'ddot', 'tilde', 'vec', 'sum', 'prod', 'int', 'oint',
        'triangleq', 'text', 'mathrm', 'mathbf', 'mathcal', 'mathbb',
        'cdot', 'ldots', 'cdots', 'ddots', 'vdots',
        'Delta', 'Omega', 'Sigma', 'Theta', 'Phi', 'Psi', 'Gamma', 'Lambda',
        'approx', 'equiv', 'neq', 'leq', 'geq', 'll', 'gg', 'sim', 'simeq',
        'propto', 'infty', 'partial', 'nabla',
        'lbrack', 'rbrack', 'lg', 'ln', 'log', 'sin', 'cos', 'tan', 'exp',
        'arcsin', 'arccos', 'arctan', 'min', 'max', 'lim',
        'pm', 'mp', 'ne', 'to', 'ld', 'Leftrightarrow',
        'leftarrow', 'rightarrow', 'Leftarrow', 'Rightarrow',
        'begin', 'end', 'quad', 'qquad', 'hspace', 'vspace',
        'bmatrix', 'pmatrix', 'vmatrix', 'Bmatrix', 'cases', 'array', 'aligned', 'eqnarray',
    ]
    cmd_pattern = '|'.join(latex_commands)

    def _fix_pandoc_latex(content: str) -> str:
        """修复 pandoc DOCX 输出中 / 替代反斜杠的 LaTeX 问题"""
        fixed = re.sub(r'/(?=[{])', r'\\', content)
        fixed = re.sub(r'/(?=[}])', r'\\', fixed)
        fixed = fixed.replace('//', '\\\\')
        fixed = re.sub(r'(?<!\\)/(' + cmd_pattern + r')\b', r'\\\1', fixed)
        fixed = re.sub(r'(?<!\\)/(?=[a-zA-Z]{2,})', r'\\', fixed)
        fixed = re.sub(r'/_\s*\{', '_{', fixed)
        fixed = re.sub(r'/\^\s*\{', '^{', fixed)
        fixed = re.sub(r'\\right\./', r'\\right.', fixed)
        fixed = fixed.replace('/%', '\\%')
        return fixed

    # 3a. 修复 $`...`$ 行内公式
    md = re.sub(r'\$`(.*?)`\$', lambda m: f'${_fix_pandoc_latex(m.group(1))}$', md, flags=re.DOTALL)

    # 3b. 将 ``` math ... ``` 转为 $$...$$ 并修复 LaTeX
    md = re.sub(r'``` math\n(.*?)\n```', lambda m: f'$$\n{_fix_pandoc_latex(m.group(1))}\n$$', md, flags=re.DOTALL)

    # 3c. 修复 /$/$ ... /$/$ 格式的块级公式
    md = re.sub(r'/\$/\$\s*(.*?)\s*/\$/\$', lambda m: f'$${_fix_pandoc_latex(m.group(1))}$$', md, flags=re.DOTALL)

    # 3d. 修复行内 /$ ... /$ 格式公式
    md = re.sub(r'/\$\s*(.*?)\s*/\$', lambda m: f'${_fix_pandoc_latex(m.group(1))}$', md)

    # 4. 删除多余的空行
    md = re.sub(r'\n{4,}', '\n\n\n', md)

    # 5. 修复表格格式
    from file2md import _fix_table_blank_lines
    md = _fix_table_blank_lines(md)

    # 6. 清理 {width=...} 图片属性
    md = re.sub(r'\{[^}]*width=[^}]*\}', '', md)
    md = re.sub(r'\{[^}]*height=[^}]*\}', '', md)

    # 7. 确保公式块前后有空行
    md = re.sub(r'([^\n])\n(\$\$)', r'\1\n\n\2', md)
    md = re.sub(r'(\$\$)\n([^\n])', r'\1\n\n\2', md)

    # 8. 清理残留 HTML 标签
    md = re.sub(r'</?figure[^>]*>', '', md)

    # 9. 标题检测与修复：处理 pandoc 将标题包裹在 blockquote/span 中的情况
    
    def _clean_line_for_heading(line):
        """去除 blockquote > 前缀和 HTML 标签，提取纯文本"""
        import re
        cleaned = re.sub(r'^>\s*', '', line)  # 去掉 blockquote
        cleaned = re.sub(r'<span[^>]*>', '', cleaned)
        cleaned = re.sub(r'</span>', '', cleaned)
        cleaned = re.sub(r'<a[^>]*>', '', cleaned)
        cleaned = re.sub(r'</a>', '', cleaned)
        cleaned = re.sub(r'\*\*', '', cleaned)  # 去掉加粗
        cleaned = re.sub(r'\#\#\#+\s*', '', cleaned)  # 去掉已有 #
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # 去链接
        return cleaned.strip()
    
    lines = md.split('\n')
    fixed_lines = []
    for line in lines:
        stripped = line.strip()
        cleaned = _clean_line_for_heading(stripped)
        
        # 第N章 标题 → #
        m = re.match(r'^(第\s*\d+\s*章\s+)(.+)$', cleaned)
        if m:
            title = m.group(2).strip()
            # 跳过页眉（含页码的）
            if re.search(r'\d+$', title) and not re.match(r'^\d+', title):
                title = re.sub(r'\s+\d+$', '', title)  # 去掉末尾页码
            fixed_lines.append('# ' + title)
            continue
        
        # 2.1 / 2.1.1 节号 → ### / ####
        m = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?\s+(.+)$', cleaned)
        if m:
            sub = m.group(3)
            prefix = '####' if sub else '###'
            title = m.group(4).strip()
            section_num = m.group(1) + '.' + m.group(2)
            if sub:
                section_num += '.' + sub
            fixed_lines.append(prefix + ' ' + section_num + ' ' + title)
            continue
        
        fixed_lines.append(line)
    md = '\n'.join(fixed_lines)

    # 10. 重新运行章节分割
    md = re.sub(r'# (第\s*\d+\s*章\s+)', r'# \1', md)

    return md
