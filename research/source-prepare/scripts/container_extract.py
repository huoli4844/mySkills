#!/usr/bin/env python3
"""
container_extract.py — 从 .docx 的嵌入 OLE 对象中提取 MathType 公式 (MTEF → LaTeX)

用法:
  python3 container_extract.py 第2章.docx -o ./formula_output
  
输出:
  ./formula_output/eqn_bins/   (Equation Native 原始数据)
  ./formula_output/latex/      (LaTeX .tex 文件 + summary.json)
  ./formula_output/omml/       (OMML .xml 文件)
"""

import zipfile, olefile, json, os, sys, subprocess, tempfile
from pathlib import Path


def extract_from_docx(docx_path: Path, out_dir: Path):
    """从 .docx 的 word/embeddings/oleObject*.bin 中提取公式"""
    eqn_dir = out_dir / 'eqn_bins'
    eqn_dir.mkdir(parents=True, exist_ok=True)
    formulas = []
    
    with zipfile.ZipFile(str(docx_path)) as z:
        for name in z.namelist():
            if 'embeddings' in name and name.endswith('.bin'):
                data = z.read(name)
                if data[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':  # OLE2 magic
                    continue
                try:
                    tmp = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
                    tmp.write(data)
                    tmp_path = tmp.name
                    tmp.close()
                    
                    ole = olefile.OleFileIO(tmp_path)
                    streams = ole.listdir()
                    found = False
                    for s in streams:
                        if 'Equation Native' in '/'.join(s):
                            eq_data = ole.openstream(s).read()
                            fname = f"eqn_{len(formulas)}.bin"
                            (eqn_dir / fname).write_bytes(eq_data)
                            formulas.append(fname)
                            found = True
                    ole.close()
                    os.unlink(tmp_path)
                    if not found:
                        print(f"  ⚠️ {name}: 无 Equation Native 流")
                except Exception as e:
                    print(f"  ⚠️ {name}: {e}")
                    continue
    
    print(f"✅ 提取 {len(formulas)} 个 Equation Native 流")
    return formulas


def run_mtef_converter(eqn_dir: Path, out_dir: Path):
    """调用 mtef_to_latex.rb 转换为 LaTeX + OMML"""
    script_dir = Path(__file__).parent
    ruby_script = script_dir / 'mtef_to_latex.rb'
    
    if not ruby_script.exists():
        # 尝试从 formula-extract 技能加载
        alt = Path('/Users/huoli4844/.hermes/skills/mlops/formula-extract/scripts/mtef_to_latex.rb')
        if alt.exists():
            ruby_script = alt
        else:
            print("❌ 找不到 mtef_to_latex.rb")
            return False
    
    cmd = [
        'ruby', '-I', '/tmp/mathtype/lib', '-I', '/tmp/mathtype/stubs',
        str(ruby_script), str(eqn_dir), str(out_dir)
    ]
    print(f"  运行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"  {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            if 'warning' in line.lower():
                continue
            print(f"  STDERR: {line}")
    return result.returncode == 0


def build_summary(out_dir: Path, count: int):
    """构建 summary.json"""
    latex_dir = out_dir / 'latex'
    latex_dir.mkdir(parents=True, exist_ok=True)
    
    summary = {'total': count, 'success': 0, 'errors': 0, 'formulas': []}
    for i in range(count):
        tex_path = latex_dir / f'eqn_{i}.tex'
        if tex_path.exists():
            latex = tex_path.read_text(encoding='utf-8').strip()
            summary['formulas'].append({
                'name': f'eqn_{i}',
                'latex': latex,
                'version': 3
            })
            summary['success'] += 1
        else:
            summary['errors'] += 1
    
    (latex_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ summary.json: {summary['success']}/{summary['total']} 成功, {summary['errors']} 错误")
    if summary['formulas']:
        for f in summary['formulas'][:5]:
            print(f"  {f['name']}: {f['latex'][:80]}")
        if len(summary['formulas']) > 5:
            print(f"  ... 共 {len(summary['formulas'])} 个公式")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='从 .docx 的嵌入 OLE 对象提取 MathType 公式')
    parser.add_argument('input', help='输入 .docx 文件')
    parser.add_argument('-o', '--output', default='./formula_output', help='输出目录')
    args = parser.parse_args()
    
    docx_path = Path(args.input)
    out_dir = Path(args.output)
    
    if not docx_path.exists():
        print(f"❌ 文件不存在: {docx_path}")
        sys.exit(1)
    
    print(f"📄 输入: {docx_path}")
    formulas = extract_from_docx(docx_path, out_dir)
    
    if not formulas:
        print("❌ 未找到任何公式")
        sys.exit(1)
    
    if run_mtef_converter(out_dir / 'eqn_bins', out_dir):
        build_summary(out_dir, len(formulas))
        print(f"\n✅ 完成！输出目录: {out_dir}")
        print(f"   后续步骤: merge_source.py 使用 {out_dir}/latex/summary.json")
    else:
        print("❌ MTEF 转换失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
