#!/usr/bin/env python3
"""
md_to_docx.py — 教材 Markdown → Word 转换工具

依赖:
    pandoc (brew install pandoc)
    python-docx (pip install python-docx)

用法:
    # 单个文件转换
    python3 scripts/md_to_docx.py single output/第3章-耦合途径.md
                     或 -o 指定输出路径
    python3 scripts/md_to_docx.py single output/第3章-耦合途径.md -o 第3章.docx

    # 目录合并转换
    python3 scripts/md_to_docx.py dir output/
                     或 -o 指定输出路径
    python3 scripts/md_to_docx.py dir output/ -o 全书.docx

    # 从图片目录复制图片（可选，使 docx 包含插图）
    # 将图片放在 md 文件同目录下的 imgs/ 或 images/ 子目录
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile


def find_pandoc() -> str:
    """查找 pandoc 可执行路径。"""
    for candidate in ["pandoc", "/opt/homebrew/bin/pandoc", "/usr/local/bin/pandoc"]:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    print("❌ pandoc 未找到。请安装: brew install pandoc", file=sys.stderr)
    sys.exit(1)


def collect_md_files(directory: str) -> list[str]:
    """收集目录下所有 .md 文件（排除 .bak 和 README），按文件名排序返回。"""
    if not os.path.isdir(directory):
        print(f"❌ 目录不存在: {directory}", file=sys.stderr)
        sys.exit(1)
    files = []
    for f in sorted(os.listdir(directory)):
        if not f.endswith(".md"):
            continue
        if f == "README.md" or "_bak" in f or ".bak" in f:
            continue
        full = os.path.join(directory, f)
        if os.path.isfile(full):
            files.append(full)
    if not files:
        print(f"❌ 目录中没有 .md 文件: {directory}", file=sys.stderr)
        sys.exit(1)
    return files


def strip_frontmatter(content: str) -> str:
    """剥离 YAML frontmatter（--- ... ---）。"""
    return re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)


def merge_markdown(files: list[str], strip_fm: bool = True) -> str:
    """将多个 .md 文件合并为一个 Markdown 字符串。"""
    sections = []
    for i, fp in enumerate(files):
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        if strip_fm:
            content = strip_frontmatter(content)
        # 非首文件前加水平分页线
        if i > 0:
            content = "\n\n\\newpage\n\n" + content
        sections.append(content)
    return "\n\n".join(sections)


def convert_md_to_docx(
    md_content: str,
    output_path: str,
    pandoc: str,
    md_source_dir: str = None,
) -> None:
    """用 pandoc 将 Markdown 字符串转换为 docx。"""
    # 构建 pandoc 资源路径（含图片查找路径）
    cmd = [
        pandoc,
        "--from", "markdown+raw_tex-yaml_metadata_block",
        "--to", "docx",
        "--wrap", "preserve",
        "--metadata", "pagetitle=教材",
    ]
    # 添加图片资源路径
    if md_source_dir:
        cmd.extend(["--resource-path", md_source_dir])
        # 也检查 imgs/ 和 images/ 子目录
        for img_sub in ["imgs", "images"]:
            img_dir = os.path.join(md_source_dir, img_sub)
            if os.path.isdir(img_dir):
                cmd.extend(["--resource-path", img_dir])

    cmd.extend(["-o", output_path])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(md_content)
        tmp_path: str = tmp.name  # type: ignore[assignment]

    try:
        cmd.append(tmp_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"⚠️  pandoc 警告:\n{result.stderr[:500]}", file=sys.stderr)
        print(f"✅ 已生成: {output_path}")
    except subprocess.TimeoutExpired:
        print(f"❌ pandoc 超时（120s），请检查文件大小", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ 命令执行失败: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        os.unlink(tmp_path)


def cmd_single(args):
    """转换单个 .md 文件为 .docx。"""
    md_path = args.md_path
    if not os.path.isfile(md_path):
        print(f"❌ 文件不存在: {md_path}", file=sys.stderr)
        sys.exit(1)

    # 默认输出路径：同名同目录，扩展名改为 .docx
    output = args.output or os.path.splitext(md_path)[0] + ".docx"

    pandoc = find_pandoc()
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = strip_frontmatter(content)

    md_dir = os.path.dirname(os.path.abspath(md_path))
    convert_md_to_docx(content, output, pandoc, md_source_dir=md_dir)


def cmd_dir(args):
    """将目录下的所有 .md 文件合并转换为一个 .docx。"""
    directory = args.directory
    files = collect_md_files(directory)

    # 默认输出：目录名.docx
    if args.output:
        output = args.output
    else:
        dir_name = os.path.basename(os.path.normpath(directory))
        output = os.path.join(directory, f"{dir_name}.docx")

    print(f"📄 合并 {len(files)} 个 .md 文件 → {output}")
    for fp in files:
        print(f"   + {os.path.basename(fp)}")

    pandoc = find_pandoc()
    md_content = merge_markdown(files, strip_fm=True)
    convert_md_to_docx(md_content, output, pandoc, md_source_dir=directory)


def main():
    p = argparse.ArgumentParser(
        description="教材 Markdown → Word 转换工具"
    )
    sp = p.add_subparsers(dest="cmd", required=True)

    # single
    s = sp.add_parser("single", help="转换单个 .md 文件为 .docx")
    s.add_argument("md_path", help="输入的 .md 文件路径")
    s.add_argument("-o", "--output", help="输出的 .docx 文件路径（可选）")

    # dir
    d = sp.add_parser("dir", help="将目录下所有 .md 合并转换为一个 .docx")
    d.add_argument("directory", help="包含 .md 文件的目录路径")
    d.add_argument("-o", "--output", help="输出的 .docx 文件路径（可选）")

    a = p.parse_args()

    if a.cmd == "single":
        cmd_single(a)
    elif a.cmd == "dir":
        cmd_dir(a)


if __name__ == "__main__":
    main()
