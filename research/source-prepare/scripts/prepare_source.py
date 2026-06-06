#!/usr/bin/env python3
"""
source-prepare: 教材源文件预处理管线
将 .doc/.docx/.pdf → emc-textbook-wiki 可用的 MD + 公式素材

用法:
  python3 prepare_source.py input.doc -o /path/to/wiki/出处 --split
  python3 prepare_source.py input.docx -o /path/to/wiki/出处
  python3 prepare_source.py input.pdf -o /path/to/wiki/出处 --no-ocr
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ── 各 skill 脚本路径（按 skills 目录结构自动解析） ────────────────────
_THIS_DIR = Path(__file__).parent.resolve()
_SKILL_ROOT = _THIS_DIR.parent.parent.parent  # skills root
# 如果 source-prepare 在 research/ 下，则向上三级
if _SKILL_ROOT.name in ("research", "mlops", "devops", "data-science"):
    _SKILL_ROOT = _SKILL_ROOT.parent

FORMULA_EXTRACT = _SKILL_ROOT / "mlops" / "formula-extract" / "scripts" / "convert_all.py"
FORMULA_RECOGNIZE = _SKILL_ROOT / "mlops" / "formula-extract" / "scripts" / "extract_formula.py"
MERGE_SOURCE = _SKILL_ROOT / "research" / "source-prepare" / "scripts" / "merge_source.py"
DOCX_FORMAT = _SKILL_ROOT / "docx-format" / "scripts" / "format_docx.py"
FILE2MD = _SKILL_ROOT / "mlops" / "file2md" / "scripts" / "file2md.py"

# formula-extract 的 Ruby 依赖路径
RUBY_LIB = Path("/tmp/mathtype/lib")
RUBY_STUBS = Path("/tmp/mathtype/stubs")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run(cmd: list, desc: str = "", timeout: int = 300) -> bool:
    """运行命令，返回是否成功"""
    eprint(f"[{desc}] {' '.join(str(c) for c in cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.stdout:
            for line in result.stdout.splitlines():
                if "warning:" not in line.lower() and line.strip():
                    eprint(f"  {line}")
        if result.returncode != 0:
            eprint(f"  ❌ 返回码 {result.returncode}")
            if result.stderr:
                eprint(f"  STDERR: {result.stderr[:500]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        eprint(f"  ❌ 超时 ({timeout}s)")
        return False
    except FileNotFoundError as e:
        eprint(f"  ❌ 找不到命令: {e}")
        return False


def detect_file_type(path) -> str:
    """检测文件类型: doc / docx / pdf"""
    if isinstance(path, str):
        path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    ext = path.suffix.lower()
    if ext == ".docx":
        return "docx"
    if ext == ".pdf":
        return "pdf"

    # .doc 是 OLE2 CFB 格式，读前 8 字节检测
    with open(path, "rb") as f:
        header = f.read(8)
    if header[:2] == b"\xD0\xCF":  # OLE2 magic: D0CF11E0
        return "doc"
    if header[:4] == b"%PDF":
        return "pdf"
    # 后缀 .doc 但非 OLE2
    if ext == ".doc":
        return "doc"

    raise ValueError(f"不支持的文件格式: {path.suffix} (header={header.hex()})")


def step_formula_extract(doc_path: Path, formulas_dir: Path) -> bool:
    """
    从 .doc 提取公式 (formula-extract/convert_all.py)
    输出: latex/*.tex, latex/summary.json, omml/*.omml.xml
    """
    if not FORMULA_EXTRACT.exists():
        eprint("  ❌ formula-extract 脚本不存在，跳过")
        return False

    if not RUBY_LIB.exists():
        eprint("  ⚠️  Ruby mathtype lib 不存在（/tmp/mathtype/lib），公式提取将失败")
        eprint("     请先安装: git clone https://github.com/siefkenj/mathtype /tmp/mathtype")
        eprint("     并: gem build mathtype.gemspec && gem install --user-install bindata")
        eprint("     并创建 stubs: mkdir -p /tmp/mathtype/stubs/ole ...")

    return run(
        ["python3", str(FORMULA_EXTRACT), str(doc_path), str(formulas_dir)],
        desc="公式提取",
        timeout=120,
    )


def step_textutil_to_docx(doc_path: Path, docx_path: Path) -> bool:
    """用 macOS textutil 将 .doc → .docx"""
    return run(
        ["textutil", "-convert", "docx", str(doc_path), "-output", str(docx_path)],
        desc=".doc → .docx",
        timeout=60,
    )


def step_docx_format(input_docx: Path, output_docx: Path, ocr: bool = False) -> bool:
    """docx-format: 格式化标题/题注 + 图片公式 OCR（可选）"""
    if not DOCX_FORMAT.exists():
        eprint("  ❌ docx-format 脚本不存在，跳过格式化")
        return False

    cmd = ["python3", str(DOCX_FORMAT), str(input_docx), str(output_docx)]
    if not ocr:
        cmd.append("--no-ocr")

    return run(cmd, desc="docx-format", timeout=300)


def step_file2md(input_path: Path, output_dir: Path, split: bool, no_ocr: bool) -> bool:
    """file2md: 转 MD"""
    if not FILE2MD.exists():
        eprint("  ❌ file2md 脚本不存在")
        return False

    cmd = ["python3", str(FILE2MD), str(input_path), "-o", str(output_dir)]
    if split:
        cmd.append("--split")
    if no_ocr:
        cmd.append("--no-ocr")

    return run(cmd, desc="file2md", timeout=300)


def step_formula_recognition(input_docx: Path, output_dir: Path, work_dir: Path,
                              assets_dir: Path, split: bool) -> bool:
    """图片公式 LLM 识别：检测 assets/ 中的小图片（公式），调用 extract_formula.py 转为 LaTeX"""
    if not FORMULA_RECOGNIZE.exists():
        eprint("  ❌ extract_formula.py 不存在，跳过公式识别")
        return False

    # 1. 从原始 docx 检测图片高度，选出公式候选（小尺寸图片）
    from zipfile import ZipFile
    from lxml import etree

    W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    WP_NS = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
    A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

    formula_images = set()
    try:
        with ZipFile(input_docx) as z:
            with z.open('word/document.xml') as f:
                tree = etree.parse(f)
            # 找所有 inline drawing 并检查高度
            for draw in tree.iter(f'{WP_NS}inline'):
                ext = draw.find(f'.//{A_NS}ext')
                if ext is not None:
                    try:
                        cy = int(ext.get('cy', '0'))
                        h_emus = cy / 914400  # EMU → inch
                        h_pt = h_emus * 72     # inch → pt
                        # 公式通常 3~30pt 高
                        if 3 <= h_pt <= 30:
                            # 找图片引用
                            blip = draw.find(f'.//{A_NS}blip')
                            if blip is not None:
                                embed = blip.get(f'{W_NS}embed') or blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                                if embed:
                                    formula_images.add(embed)
                    except (ValueError, AttributeError):
                        pass
        eprint(f"  🔍 检测到 {len(formula_images)} 个公式候选图片")
    except Exception as e:
        eprint(f"  ⚠️  docx 图片高度检测失败: {e}")
        return False

    if not formula_images:
        eprint("  ℹ️  未检测到公式图片，跳过识别")
        return False

    # 2. 找出 assets/ 中对应的图片文件
    formula_files = []
    if assets_dir.exists():
        # 从 docx 的 media/ 映射到 assets/ 文件
        for f in sorted(assets_dir.iterdir()):
            if f.suffix.lower() in ('.png', '.jpeg', '.jpg') and f.is_file():
                # 检查图片尺寸是否为公式大小
                try:
                    from PIL import Image
                    with Image.open(f) as img:
                        w, h = img.size
                        # 公式通常较小：宽<300px 或 高<100px
                        if w < 300 or h < 100:
                            formula_files.append(f)
                except Exception:
                    pass

    if not formula_files:
        eprint("  ℹ️  assets 中无公式候选图片")
        return False

    eprint(f"  📸 待识别公式图片: {len(formula_files)} 个")

    # 3. 运行 extract_formula.py --batch
    formulas_output = work_dir / "_formula_recognition"
    formulas_output.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3", str(FORMULA_RECOGNIZE),
        str(assets_dir),
        "--batch", "-o", str(formulas_output),
        "--no-convert",
    ]
    ok = run(cmd, desc="公式LLM识别", timeout=600)
    if not ok:
        eprint("  ⚠️  公式识别部分失败")

    # 4. 收集识别结果 → summary.json
    summary_items = []
    for f in sorted(formulas_output.iterdir()):
        if f.suffix == '.md' and f.name.endswith('.latex.md'):
            latex_content = f.read_text(encoding='utf-8').strip()
            # 文件名: image-001.png.latex.md → image-001
            stem = f.name.replace('.latex.md', '')
            summary_items.append({
                "name": stem,
                "latex": latex_content
            })

    if summary_items:
        summary = {"total": len(summary_items), "success": len(summary_items),
                   "errors": 0, "formulas": summary_items}
        summary_path = formulas_output / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        eprint(f"  📐 已识别 {len(summary_items)} 个公式")

        # 5. 替换 MD 中的图片引用为 LaTeX
        if MERGE_SOURCE.exists():
            for md_file in output_dir.glob("*.md"):
                if md_file.name == 'formatted.md':
                    continue
                merged_md = work_dir / f"merged_{md_file.name}"
                cmd = [
                    "python3", str(MERGE_SOURCE),
                    "--md", str(md_file),
                    "--formulas", str(summary_path),
                    "-o", str(merged_md),
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if merged_md.exists():
                    shutil.copy2(merged_md, md_file)
                    eprint(f"  ✅ 公式替换: {md_file.name}")
    else:
        eprint("  ⚠️  公式识别未返回结果")

    return True


def process_doc(input_path: Path, output_dir: Path, split: bool, no_ocr: bool,
                formulas_dir: Path, ocr: bool = False) -> bool:
    """处理 .doc 文件"""
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 线 A: 出处 MD
    docx_path = work_dir / "converted.docx"
    if not step_textutil_to_docx(input_path, docx_path):
        return False

    formatted_docx = work_dir / "formatted.docx"
    step_docx_format(docx_path, formatted_docx, ocr=ocr)

    step_file2md(formatted_docx, output_dir, split, no_ocr)

    # 线 B: 公式素材（可选）
    if not formulas_dir:
        formulas_dir = output_dir / "_formulas"
    step_formula_extract(input_path, formulas_dir)

    # 输出公式统计
    summary_path = formulas_dir / "latex" / "summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            d = json.load(f)
        eprint(f"\n📊 公式提取: {d['success']}/{d['total']} 成功, {d['errors']} 错误")

    return True


def process_docx(input_path: Path, output_dir: Path, split: bool, no_ocr: bool,
                 ocr: bool = False, formula_recognize: bool = False) -> bool:
    """处理 .docx 文件"""
    work_dir = output_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    formatted_docx = work_dir / "formatted.docx"
    step_docx_format(input_path, formatted_docx, ocr=ocr)

    step_file2md(formatted_docx, output_dir, split, no_ocr)

    # 图片公式 LLM 识别（可选）
    if formula_recognize:
        assets_dir = output_dir / "assets"
        step_formula_recognition(formatted_docx, output_dir, work_dir, assets_dir, split)

    return True


def process_pdf(input_path: Path, output_dir: Path, split: bool, no_ocr: bool) -> bool:
    """处理 .pdf 文件"""
    step_file2md(input_path, output_dir, split, no_ocr)
    return True


def summarize_output(output_dir: Path):
    """输出汇总信息"""
    eprint("\n" + "=" * 60)
    eprint("📋 处理汇总")
    eprint("=" * 60)

    md_files = list(output_dir.glob("*.md"))
    if md_files:
        for f in sorted(md_files):
            size = f.stat().st_size
            lines = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            eprint(f"  ✅ MD: {f.name} ({size/1024:.0f} KB, {lines} 行)")

    assets_dir = output_dir / "assets"
    if assets_dir.exists():
        images = list(assets_dir.glob("*"))
        eprint(f"  🖼️  图片: {len(images)} 个")

    formulas_dir = output_dir / "_formulas"
    if formulas_dir.exists():
        summary = formulas_dir / "latex" / "summary.json"
        if summary.exists():
            with open(summary) as f:
                d = json.load(f)
            eprint(f"  📐 公式: {d['success']} 个 (LaTeX + OMML)")

    eprint("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="教材源文件预处理管线: .doc/.docx/.pdf → MD (供 emc-textbook-wiki 使用)"
    )
    parser.add_argument("input", help="输入文件 (.doc / .docx / .pdf)")
    parser.add_argument("-o", "--output", help="输出目录（默认: 输入文件所在目录）")
    parser.add_argument("--split", action="store_true", help="按章节分割输出")
    parser.add_argument("--no-ocr", action="store_true", help="禁用 PDF OCR")
    parser.add_argument("--ocr", action="store_true",
                        help="启用图片公式OCR（pix2tex），将.docx中的图片公式转为可编辑LaTeX。需先 pip install pix2tex")
    parser.add_argument("--formula-recognize", action="store_true",
                        help="启用图片公式LLM识别（formula-extract），将.docx中的图片公式通过多模态LLM转为LaTeX。需配置MOONSHOT_API_KEY或OPENAI_API_KEY")
    parser.add_argument("--formulas-dir", help="公式提取输出目录（默认: {output}/_formulas/）")
    parser.add_argument("--skip-formulas", action="store_true", help="跳过公式提取（仅 .doc）")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    # 确定输出目录
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = input_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    # 公式目录
    formulas_dir = None
    if args.formulas_dir:
        formulas_dir = Path(args.formulas_dir).resolve()
    elif args.skip_formulas:
        formulas_dir = None
    else:
        formulas_dir = output_dir / "_formulas"

    # 检测文件类型
    try:
        file_type = detect_file_type(input_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"\n📄 输入: {input_path.name}")
    print(f"🔍 类型: {file_type}")
    print(f"📁 输出: {output_dir}")

    # ── 按类型处理 ──
    success = False
    try:
        if file_type == "doc":
            success = process_doc(input_path, output_dir, args.split, args.no_ocr,
                                  formulas_dir, ocr=args.ocr)
        elif file_type == "docx":
            if args.skip_formulas:
                pass  # docx 不需要 formula-extract
            success = process_docx(input_path, output_dir, args.split, args.no_ocr,
                                   ocr=args.ocr, formula_recognize=args.formula_recognize)
        elif file_type == "pdf":
            if not args.skip_formulas:
                eprint("  ℹ️  PDF 格式不支持公式提取，跳过")
            success = process_pdf(input_path, output_dir, args.split, args.no_ocr)
    except Exception as e:
        print(f"\n❌ 管线处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if success:
        # 清理中间目录（公式识别完成后保留 _work 供 merge 使用后的清理）
        if not args.formula_recognize:
            work_dir = output_dir / "_work"
            if work_dir.exists():
                import shutil
                shutil.rmtree(work_dir)
                eprint("  🧹 已清理中间文件 (_work/)")

        summarize_output(output_dir)

        # 针对 .doc 输出的特殊提示
        if file_type == "doc":
            print(f"\n⚠️  .doc 源文件提示:")
            print(f"   - MD 中公式显示为 EMBED Equation.3 占位符（textutil 转换限制）")
            print(f"   - 标题显示为 **粗体** 而非 ## 标题（需 emc-textbook-wiki 时手动调整）")
            print(f"   - 公式 LaTeX 已提取到 _formulas/，Step 5 创建知识要素时使用")
            print(f"   - 建议：如有 .docx 源文件，公式和标题保真度最高")

        if args.ocr:
            print(f"\n🔍 OCR 模式已启用：")
            print(f"   - docx-format 会尝试将图片公式转为可编辑 OMML/LaTeX")
            print(f"   - 需要 pix2tex 模型：pip install pix2tex")
            print(f"   - 转换成功的图片公式将出现在 MD 中为 LaTeX $...$ 格式")

        print(f"\n✅ 处理完成！输出目录: {output_dir}")
        print(f"   下一步: 将 MD 文件移入 wiki 的 出处/ 目录作为 emc-textbook-wiki Step 3 输入")
        print(f"   公式素材: 在 Step 5 创建知识要素时从 _formulas/latex/summary.json 中检索 LaTeX")
    else:
        print("\n❌ 管线处理未完全成功，请检查上方的错误日志")
        sys.exit(1)


if __name__ == "__main__":
    main()
