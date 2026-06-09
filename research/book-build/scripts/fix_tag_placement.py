#!/usr/bin/env python3
"""Fix tag placement: move \tag{...} from outside $$ to inside $$"""
import re, sys

filepath = sys.argv[1]
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: \tag{N-M} on its own line, followed by $$
# Fix: remove the standalone \tag line, add \tag inside the $$ block
# before the closing $$

lines = content.split('\n')
new_lines = []
i = 0
pending_tag = None

while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Check if this line is a standalone \tag before a $$
    if re.match(r'^\\tag\{\d+-\d+\}$', stripped):
        # Look ahead to see if next non-empty line is $$
        next_non_empty = None
        for j in range(i+1, min(i+5, len(lines))):
            if lines[j].strip():
                next_non_empty = lines[j].strip()
                break
        if next_non_empty == '$$':
            # Store this tag, don't output it yet
            pending_tag = stripped
            i += 1
            continue
    
    if stripped == '$$' and pending_tag:
        # Output $$, then formula content as-is, then tag, then closing $$
        new_lines.append(line)
        # Find the closing $$
        closing_idx = None
        for j in range(i+1, len(lines)):
            if lines[j].strip() == '$$':
                closing_idx = j
                break
        if closing_idx:
            # Output content between $$ and $$, then tag before closing $$
            for k in range(i+1, closing_idx):
                new_lines.append(lines[k])
            new_lines.append(pending_tag)
            new_lines.append('$$')
            i = closing_idx + 1
            pending_tag = None
            continue
        else:
            # No closing $$ found, just output the tag now
            new_lines.append(pending_tag)
            pending_tag = None
    
    new_lines.append(line)
    i += 1

result = '\n'.join(new_lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(result)

# Verify
before = content.count('\\tag{')
after = result.count('\\tag{')
fixed = before - after
print("Tags moved inside $$: " + str(abs(fixed)))
print("Before: " + str(before) + " tags, After: " + str(after) + " tags")
print("Done")
