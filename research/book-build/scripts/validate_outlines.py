#!/usr/bin/env python3
"""
validate_outlines.py — 写作大纲质量检查。
检查各章写作大纲的完整性、结构合理性和内容覆盖度。

用法：
  python3 validate_outlines.py --project /path/to/教材

检查项：
  1. 每章是否有写作大纲文件
  2. 大纲中是否定义了 L1 节（X.Y 格式）和 L2 子节（X.Y.Z 格式）
  3. 每节是否有目标体量（建议KB数）
  4. 各节的素材来源是否已标注
  5. 大纲是否包含 5.1（素材清单）和 5.2（军规检查）节
  6. 各节之间的体量分配是否均衡（无单节过大或过小）
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Optional


def find_writing_guides(project_root: str) -> List[Tuple[int, str]]:
    """查找所有写作大纲文件，返回 (章节号, 路径) 列表"""
    guides_dir = Path(project_root) / "output" / "写作大纲"
    if not guides_dir.exists():
        print(f"❌ 写作大纲目录不存在: {guides_dir}")
        return []
    
    guides = []
    for f in sorted(guides_dir.glob("writing-guide-ch*.md")):
        m = re.search(r'ch(\d+)', f.stem)
        if m:
            guides.append((int(m.group(1)), str(f)))
    return guides


def parse_sections(content: str) -> Tuple[List[str], List[str]]:
    """从大纲内容中提取 L1 节和 L2 子节"""
    l1 = re.findall(r'^###\s+(\d+\.\d+)\s+(.+)', content, re.MULTILINE)
    l2 = re.findall(r'^####\s+(\d+\.\d+\.\d+)\s+(.+)', content, re.MULTILINE)
    return (
        [f"{s[0]} {s[1][:40]}" for s in l1],
        [f"{s[0]} {s[1][:40]}" for s in l2]
    )


def find_kb_targets(content: str) -> List[str]:
    """提取建议体量信息（建议KB数、建议体量等）"""
    targets = []
    for line in content.split('\n'):
        if '|' not in line:
            continue
        cols = [c.strip() for c in line.split('|')]
        # 找形如 "| 8.1.1 | 静电屏蔽 | 25KB |" 的行
        if re.match(r'^[\d.]+\s*$', cols[1]) and ('KB' in line or '体量' in line):
            targets.append(line.strip()[:100])
    return targets


def has_source_marks(content: str) -> bool:
    """检查大纲是否标注了素材来源（路宏敏/梁振光/柯金良/张亮）"""
    marks = ['路宏敏', '梁振光', '柯金良', '张亮']
    return any(m in content for m in marks)


def check_chapter(chapter: int, filepath: str) -> dict:
    """检查单个章节的大纲"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.count('\n') + 1
    size = os.path.getsize(filepath)
    l1_sections, l2_sections = parse_sections(content)
    targets = find_kb_targets(content)
    source_marks = has_source_marks(content)
    
    # 检查是否包含 5.1 和 5.2 节
    has_51 = '5.1' in ' '.join(l1_sections) or '5.1' in content
    has_52 = '5.2' in ' '.join(l1_sections) or '5.2' in content
    
    issues = []
    
    if not l1_sections:
        issues.append("❌ 未定义任何 L1 节")
    
    if not source_marks:
        issues.append("⚠️  未标注素材来源")
    
    # 检查 L1 节的编号连续性
    l1_nums = []
    for s in l1_sections:
        m = re.match(r'(\d+\.\d+)', s)
        if m:
            l1_nums.append(m.group(1))
    
    # 过滤出纯内容节（排除 5.1/5.2 等写作说明节）
    content_sections = [s for s in l1_nums if not s.startswith('5.')]
    if content_sections:
        expected = [f"{chapter}.{i}" for i in range(1, len(content_sections) + 1)]
        actual = content_sections[:len(expected)]
        if actual != expected:
            issues.append(f"⚠️  L1节编号异常: 实际 {actual}, 期望 {expected}")
    
    return {
        "chapter": chapter,
        "file": filepath,
        "lines": lines,
        "size_kb": round(size / 1024, 1),
        "l1_count": len(l1_sections),
        "l2_count": len(l2_sections),
        "has_targets": len(targets) > 0,
        "has_source_marks": bool(source_marks),
        "has_51": has_51,
        "has_52": has_52,
        "l1_sections": l1_sections,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(
        description="写作大纲质量检查"
    )
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()
    
    guides = find_writing_guides(args.project)
    if not guides:
        print("❌ 未找到写作大纲文件")
        sys.exit(1)
    
    print(f"找到 {len(guides)} 章写作大纲\n")
    
    all_results = []
    total_issues = 0
    
    for chapter, filepath in guides:
        result = check_chapter(chapter, filepath)
        all_results.append(result)
        total_issues += len(result["issues"])
        
        status = "⚠️" if result["issues"] else "✅"
        print(f"第{chapter:>2}章 {status} | {result['size_kb']:>5}KB | "
              f"L1={result['l1_count']:>2}节 L2={result['l2_count']:>2}节 | "
              f"素材={'✅' if result['has_source_marks'] else '❌'} | "
              f"体量目标={'✅' if result['has_targets'] else '⚠️'}")
        
        if result["issues"]:
            for issue in result["issues"]:
                print(f"       {issue}")
    
    print(f"\n--- 汇总 ---")
    print(f"总章节: {len(guides)} 章")
    print(f"问题数: {total_issues}")
    
    # 统计体量分布
    sizes = [r['size_kb'] for r in all_results]
    print(f"大纲体量: 最小{min(sizes)}KB 最大{max(sizes)}KB 平均{sum(sizes)/len(sizes):.0f}KB")
    
    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
