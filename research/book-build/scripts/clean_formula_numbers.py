#!/usr/bin/env python3
"""
Clean up formula numbering in a chapter file.
1. Remove all standalone \tag{} lines that are outside $$ blocks
2. Assign sequential numbers 6-1, 6-2, ... to each $$...$$ block
"""
import re, sys

filepath = sys.argv[1]
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

chapter = re.search(r'第\s*(\d+)\s*章', content)
ch = chapter.group(1) if chapter else '6'

lines = content.split('\n')

# Step 1: Remove ALL standalone \tag{} lines (they're outside $$ blocks)
# Don't touch tags that are inside $$ blocks
cleaned = []
in_math = False
for line in lines:
    if line.strip() == '$$':
        in_math = not in_math
    if not in_math and re.match(r'^\\tag\{\d+-\d+\}$', line.strip()):
        # Standalone tag outside $$ - remove it
        continue
    # Also remove tags that are on the line right before $$
    if not in_math and re.match(r'^\\tag\{\d+-\d+\}$', line.strip()):
        continue
    cleaned.append(line)

# Step 2: Re-number all displayed formula blocks sequentially
content2 = '\n'.join(cleaned)
lines2 = content2.split('\n')

prefix = ch + '-'
counter = 1
in_math = False
result_lines = []

for i, line in enumerate(lines2):
    stripped = line.strip()
    if stripped == '$$':
        if in_math:
            # Closing $$ - if the last line before this doesn't have a tag, add one
            # Check if any content line inside has a tag
            in_math = False
        else:
            in_math = True
        result_lines.append(line)
    elif in_math:
        # Inside formula - check if line has \tag and strip it
        if '\\tag{' in stripped:
            # Remove existing tag
            continue
        result_lines.append(line)
    else:
        result_lines.append(line)

# Now rebuild: for each $$...$$ block, add \tag before closing $$
content3 = '\n'.join(result_lines)
lines3 = content3.split('\n')

counter = 1
in_math = False
output_lines = []
block_content = []
block_start = -1

for i, line in enumerate(lines3):
    stripped = line.strip()
    if stripped == '$$':
        if in_math:
            # End of block - add tag before closing
            closing_tag = '\\tag{' + prefix + str(counter) + '}'
            counter += 1
            # Add formula content (without any existing tag line if present)
            for bc in block_content:
                if not re.match(r'^\\tag\{\d+-\d+\}$', bc.strip()):
                    output_lines.append(bc)
            output_lines.append(closing_tag)
            output_lines.append(line)
            block_content = []
            in_math = False
        else:
            block_content = []
            output_lines.append(line)
            in_math = True
    elif in_math:
        block_content.append(line)
    else:
        output_lines.append(line)

output = '\n'.join(output_lines)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(output)

# Count
tag_count = output.count('\\tag{')
formula_count = len(re.findall(r'\$\$(.+?)\$\$', output, re.DOTALL))
print("Chapter " + ch + " fix complete:")
print("  Tags: " + str(tag_count))
print("  Formula blocks: " + str(formula_count))
print("  Tags per block: " + ("OK" if tag_count == formula_count else "MISMATCH"))
