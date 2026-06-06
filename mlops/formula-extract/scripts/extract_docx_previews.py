#!/usr/bin/env python3
"""
从 docx 中提取 EMF/WMF 对应的 PNG/JPEG 预览图
=============================================
Word 保存 EMF/WMF 时，通常会在 media/ 中同时存一份位图预览。
本脚本批量提取这些预览图，避免手动转换 EMF/WMF。

用法:
  # 单文件
  python3 extract_docx_previews.py 第3章.docx -o ./assets/

  # 批量处理（如 8 个章节）
  python3 extract_docx_previews.py /path/to/chapters/ --batch -o ./all_previews/

输出:
  - 仅提取 PNG/JPEG 预览（跳过纯矢量 EMF/WMF）
  - 按章节分子目录存放
  - 生成映射表: emf → png 对应关系
"""

import os
import zipfile
import argparse
from pathlib import Path
from collections import defaultdict


def extract_previews(docx_path: str, output_dir: str) -> dict:
    """从单个 docx 中提取 PNG/JPEG 预览，返回 EMF→PNG 映射"""
    docx_path = Path(docx_path).resolve()
    chapter_name = docx_path.stem
    out_dir = Path(output_dir) / chapter_name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[处理] {docx_path.name}")

    with zipfile.ZipFile(docx_path, 'r') as zf:
        media_files = [n for n in zf.namelist() if n.startswith('word/media/')]

        # 分类
        vectors = [n for n in media_files if n.lower().endswith(('.emf', '.wmf'))]
        bitmaps = [n for n in media_files if n.lower().endswith(('.png', '.jpg', '.jpeg'))]

        # 建立 stem → 路径 映射
        bitmap_stems = {}
        for b in bitmaps:
            stem = Path(b).stem.lower()
            bitmap_stems[stem] = b

        # 查找每个矢量图是否有位图预览
        mapping = {}
        extracted = 0
        for v in vectors:
            v_stem = Path(v).stem.lower()
            v_name = Path(v).name

            if v_stem in bitmap_stems:
                bmp_path = bitmap_stems[v_stem]
                bmp_name = Path(bmp_path).name

                # 读取并保存
                data = zf.read(bmp_path)
                out_path = out_dir / bmp_name
                out_path.write_bytes(data)

                mapping[v_name] = bmp_name
                extracted += 1
            else:
                mapping[v_name] = None

    print(f"  矢量图: {len(vectors)} 个")
    print(f"  位图预览: {len(bitmaps)} 个")
    print(f"  成功匹配提取: {extracted} 个")
    print(f"  输出目录: {out_dir}")

    return {
        'chapter': chapter_name,
        'mapping': mapping,
        'output_dir': str(out_dir),
        'extracted': extracted,
        'total_vectors': len(vectors),
    }


def main():
    ap = argparse.ArgumentParser(description='从 docx 中提取 EMF/WMF 的 PNG/JPEG 预览')
    ap.add_argument('input', help='输入 docx 文件或目录')
    ap.add_argument('-o', '--output', default='./docx_previews',
                    help='输出目录 (默认: ./docx_previews)')
    ap.add_argument('--batch', action='store_true',
                    help='批量处理目录中的所有 docx')
    ap.add_argument('--report', action='store_true',
                    help='生成汇总报告 (mapping.json)')

    args = ap.parse_args()
    input_path = Path(args.input).resolve()

    results = []

    if args.batch or input_path.is_dir():
        docx_files = sorted(input_path.glob('*.docx'))
        if not docx_files:
            print(f"未找到 docx 文件: {input_path}")
            return

        print(f"批量处理: 发现 {len(docx_files)} 个 docx")
        for f in docx_files:
            results.append(extract_previews(str(f), args.output))
    else:
        results.append(extract_previews(str(input_path), args.output))

    # 汇总
    total_extracted = sum(r['extracted'] for r in results)
    total_vectors = sum(r['total_vectors'] for r in results)

    print(f"\n{'='*60}")
    print(f"汇总: {total_extracted}/{total_vectors} 个矢量图找到位图预览")
    print(f"输出根目录: {Path(args.output).resolve()}")
    print(f"{'='*60}")

    # 生成映射报告
    if args.report:
        report_path = Path(args.output) / 'mapping.json'
        import json
        report_data = {
            'summary': {
                'total_chapters': len(results),
                'total_vectors': total_vectors,
                'total_extracted': total_extracted,
            },
            'chapters': [
                {
                    'chapter': r['chapter'],
                    'output_dir': r['output_dir'],
                    'mapping': r['mapping'],
                }
                for r in results
            ],
        }
        report_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[报告] 映射表已保存: {report_path}")

    # 打印缺失清单
    missing = []
    for r in results:
        for vec, bmp in r['mapping'].items():
            if bmp is None:
                missing.append(f"  {r['chapter']}/{vec}")

    if missing:
        print(f"\n[警告] 以下 {len(missing)} 个矢量图未找到位图预览，需要手动转换:")
        for m in missing[:20]:
            print(m)
        if len(missing) > 20:
            print(f"  ... 还有 {len(missing)-20} 个")


if __name__ == '__main__':
    main()
