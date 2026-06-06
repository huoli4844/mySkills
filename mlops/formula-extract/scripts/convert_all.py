#!/usr/bin/env python3
"""
批量转换 .doc 中的 MathType 公式 → LaTeX + OMML
流程：
  1. 用 olefile 提取 Equation Native 流
  2. 用 Ruby mathtype gem 解析 MTEF → snapshot → LaTeX
  3. 用 latex_to_omml.py 将 LaTeX → OMML
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add docx-format scripts to path for latex_to_omml
# Resolve: formula-extract is under mlops/, docx-format is in skills root
_script_dir = Path(__file__).parent
_skills_root = _script_dir.parent.parent.parent  # goes to mlops/
if _skills_root.name == "mlops":
    _skills_root = _skills_root.parent  # go up one more: to skills root
sys.path.insert(0, str(_skills_root / "docx-format" / "scripts"))
from latex_to_omml import latex_to_omml
from lxml import etree


def extract_equation_native(doc_path: Path, out_dir: Path):
    """Step 1: Extract all Equation Native streams from .doc"""
    import olefile
    out_dir.mkdir(parents=True, exist_ok=True)
    ole = olefile.OleFileIO(str(doc_path))
    eq_count = 0
    for stream in ole.listdir():
        path = '/'.join(stream)
        if 'Equation Native' in path:
            data = ole.openstream(stream).read()
            out_path = out_dir / f'eqn_{eq_count}.bin'
            out_path.write_bytes(data)
            eq_count += 1
    ole.close()
    print(f"Extracted {eq_count} Equation Native streams to {out_dir}")
    return eq_count


def mtef_to_latex(eqn_dir: Path, output_dir: Path):
    """Step 2: Run Ruby MTEF→LaTeX converter"""
    script_path = Path(__file__).parent / "mtef_to_latex.rb"
    ruby_lib = "/tmp/mathtype/lib"
    ruby_stubs = "/tmp/mathtype/stubs"
    cmd = ["ruby", "-I", ruby_lib, "-I", ruby_stubs, str(script_path), str(eqn_dir), str(output_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Filter out warnings
    lines = [l for l in result.stdout.split('\n') if 'warning:' not in l and l.strip()]
    for line in lines:
        print(line)
    if result.returncode != 0:
        print("STDERR:", result.stderr[:500])
    return result.returncode == 0


def latex_to_omml_batch(latex_dir: Path, omml_dir: Path):
    """Step 3: Convert LaTeX files to OMML XML"""
    omml_dir.mkdir(parents=True, exist_ok=True)
    summary_path = latex_dir / "summary.json"
    if not summary_path.exists():
        print("summary.json not found")
        return 0

    with open(summary_path) as f:
        data = json.load(f)

    success = 0
    errors = []
    for item in data.get("formulas", []):
        name = item["name"]
        latex = item["latex"]
        try:
            omml = latex_to_omml(latex)
            xml_str = etree.tostring(omml, pretty_print=True, encoding='unicode')
            out_path = omml_dir / f"{name}.omml.xml"
            out_path.write_text(xml_str, encoding='utf-8')
            success += 1
        except Exception as e:
            errors.append({"name": name, "latex": latex, "error": str(e)})

    print(f"\nOMML conversion: {success} success, {len(errors)} errors")
    if errors:
        print("Errors:")
        for e in errors[:10]:
            print(f"  {e['name']}: {e['error']}")

    # Write OMML summary
    omml_summary = {
        "total": success + len(errors),
        "success": success,
        "errors": len(errors),
        "error_details": errors
    }
    with open(omml_dir / "summary.json", "w") as f:
        json.dump(omml_summary, f, indent=2, ensure_ascii=False)

    return success


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_all.py <input.doc> [output_dir]")
        sys.exit(1)

    doc_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("formula_output")

    # Create working directories
    work_dir = output_dir / "_work"
    eqn_dir = work_dir / "eqn_native"
    latex_dir = work_dir / "latex"
    omml_dir = output_dir / "omml"

    # Step 1: Extract
    count = extract_equation_native(doc_path, eqn_dir)
    if count == 0:
        print("No equations found!")
        return

    # Step 2: MTEF → LaTeX
    ok = mtef_to_latex(eqn_dir, latex_dir)
    if not ok:
        print("LaTeX conversion failed")
        return

    # Step 3: LaTeX → OMML
    latex_to_omml_batch(latex_dir, omml_dir)

    # Step 4: Copy final LaTeX outputs
    final_latex_dir = output_dir / "latex"
    final_latex_dir.mkdir(parents=True, exist_ok=True)
    for f in latex_dir.glob("*.tex"):
        (final_latex_dir / f.name).write_text(f.read_text())
    (final_latex_dir / "summary.json").write_text(
        (latex_dir / "summary.json").read_text()
    )

    print(f"\nDone! Output in {output_dir}")
    print(f"  LaTeX: {final_latex_dir}")
    print(f"  OMML:  {omml_dir}")


if __name__ == "__main__":
    main()
