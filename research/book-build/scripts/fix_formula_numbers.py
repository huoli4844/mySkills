#!/usr/bin/env python3
"""Fix formula numbering in a chapter file.
Usage: python3 fix_formula_numbers.py output/第N章.md

Scans all $$...$$ blocks, ensures each has exactly one \tag{N-M},
and renumbers all tags sequentially. Detects and removes duplicate tags,
and handles both \tag and \\tag variants.

Backup: automatically creates a .bak file before modifying.
"""
import re, sys, os

def fix_formula_numbers(path):
    # Backup
    bak_path = path + '.bak'
    if not os.path.exists(bak_path):
        import shutil
        shutil.copy2(path, bak_path)
        print(f'Backup: {bak_path}')

    c = open(path).read()
    
    # Auto-detect chapter number from filename or first existing tag
    chapter = None
    # Try from filename: 第N章  or  ChN
    fn_match = re.search(r'第(\d+)章|Ch(\d+)', os.path.basename(path))
    if fn_match:
        chapter = fn_match.group(1) or fn_match.group(2)
    # Try from existing tags
    if not chapter:
        existing = re.findall(r'tag\{(\d+)-\d+\}', c)
        if existing:
            chapter = existing[0]
        else:
            chapter = '1'  # fallback
    
    # Find all $$ blocks
    eq_pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    parts = []
    pos = 0
    counter = 0
    
    for m in eq_pattern.finditer(c):
        parts.append(c[pos:m.start()])
        eq_text = m.group(1)
        counter += 1
        
        # Remove ALL tag variants
        for pattern in [r'\\\\tag\{' + chapter + r'-\d+\}', r'\\tag\{' + chapter + r'-\d+\}',
                        r'\\\\tag\{\d+-\d+\}', r'\\tag\{\d+-\d+\}', r'\tag\{\d+-\d+\}']:
            eq_text = re.sub(pattern, '', eq_text)
        
        # Clean blank lines
        content_lines = [l for l in eq_text.split('\n') if l.strip()]
        clean = '\n'.join(content_lines)
        
        # Add single tag with detected chapter number
        clean += f'\n\\tag{{{chapter}-{counter}}}'
        parts.append('$$\n' + clean + '\n$$')
        pos = m.end()
    
    parts.append(c[pos:])
    result = ''.join(parts)
    open(path, 'w').write(result)
    
    # Verify
    c2 = open(path).read()
    all_tags_digit = re.findall(r'tag\{(\d+-\d+)\}', c2)
    from collections import Counter
    dup = {k: v for k, v in Counter(all_tags_digit).items() if v > 1}
    if dup:
        print(f'WARNING: Duplicate tags: {dup}')
        return False
    
    total = len(re.findall(r'tag\{\d+-\d+\}', c2))
    blocks = len(list(eq_pattern.finditer(c2)))
    print(f'OK: {total} tags across {blocks} equation blocks')
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    success = fix_formula_numbers(sys.argv[1])
    sys.exit(0 if success else 1)
