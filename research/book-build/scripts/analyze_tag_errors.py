#!/usr/bin/env python3
"""Analyze \\tag placement errors in chapter files.

Checks each \tag{X-Y} line:
1. Is it on its own line?
2. Is the next non-empty line $$?
3. If not, report the error pattern.

Usage: python3 analyze_tag_errors.py [--project PATH]

This is the primary validation tool after fixing tag placement issues.
Returns 0 errors means all tags are correctly placed.
"""

import os
import re
import glob
import sys

def analyze_tags_in_file(file_path, output_dir=None):
    """Analyze a single chapter file for tag placement errors."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    basename = os.path.basename(file_path)
    errors = []
    
    for i, line in enumerate(lines, 1):
        if '\\tag{' in line and '```' not in line and '---' not in line:
            stripped = line.strip()
            is_tag_line = bool(re.match(r'^\\tag\{[^}]+\}\s*$', stripped))
            
            if not is_tag_line:
                errors.append({
                    'line': i,
                    'type': 'tag_with_other_content',
                    'content': stripped[:100]
                })
                continue
            
            if i >= len(lines):
                errors.append({'line': i, 'type': 'tag_at_end_of_file'})
                continue
            
            next_stripped = lines[i].strip()
            if next_stripped != '$$':
                errors.append({
                    'line': i,
                    'type': 'tag_not_followed_by_dollar_dollar',
                    'content': stripped[:80],
                    'next': next_stripped[:60]
                })
    
    return errors

def main():
    output_dir = "/Users/huoli4844/Desktop/电磁兼容教材/output"
    
    if '--project' in sys.argv:
        idx = sys.argv.index('--project')
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]
    
    files = sorted(glob.glob(os.path.join(output_dir, "第*章*.md")))
    total_errors = 0
    total_tags = 0
    
    for f in files:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        tags_in_file = len(re.findall(r'\\tag\{', content))
        total_tags += tags_in_file
        
        errors = analyze_tags_in_file(f)
        total_errors += len(errors)
        
        if errors:
            print(f"  {os.path.basename(f)}: {len(errors)} 错误")
            for e in errors[:3]:
                if e['type'] == 'tag_with_other_content':
                    print(f"    L{e['line']}: 公式与tag混合: {e['content'][:80]}")
                elif e['type'] == 'tag_not_followed_by_dollar_dollar':
                    print(f"    L{e['line']}: tag后非$$: '{e['content']}' → '{e['next']}'")
    
    print(f"\n总计: {total_tags} 个tag, {total_errors} 个错误")
    if total_errors == 0:
        print("✅ 所有 \\tag 位置正确")
    
    return 1 if total_errors > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
