"""Formula checks for post_generation_check — $$ block validation, tag numbering, format.""" 
import re

def extract_chapter_number(text: str) -> int:
    """从文件中提取章号"""
    m = re.search(r'第\s*(\d+)\s*章', text)
    return int(m.group(1)) if m else 0


def fix_chapter_prefix(n: int) -> str:
    """返回章号前缀如 '5-'"""
    return f'{n}-'


def check_formulas(text: str, chapter_n: int, verbose: bool = False) -> list:
    """
    检查所有公式块，返回问题列表。
    每个问题: (行号, 严重级别, 描述, 可自动修复, 修复方法)
    """
    issues = []
    lines = text.split('\n')
    tag_prefix = f'{chapter_n}-'

    # Step 1: 定位所有 $$ 公式块
    in_formula = False
    formula_blocks = []  # [(start_line, end_line, content_lines)]
    start = 0
    current = []
    for i, line in enumerate(lines):
        if line.strip() == '$$':
            if in_formula:
                formula_blocks.append((start, i, current))
                current = []
                in_formula = False
            else:
                start = i
                in_formula = True
        elif in_formula:
            current.append((i, line))

    # Step 2: 检查每个公式块
    for start_line, end_line, content in formula_blocks:
        content_text = '\n'.join([l for _, l in content])
        block_lines = [l for _, l in content]
        full_text = '\n'.join(block_lines)

        # 2a. 花括号平衡
        braces = 0
        for ch in full_text:
            if ch == '{': braces += 1
            if ch == '}': braces -= 1
        if braces != 0:
            issues.append((start_line + 1, 'ERROR', f'花括号不平衡(差{braces}个"}}")', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2b. \\left/\\right 匹配（使用正则防误报：\\rightarrow→\\right 子串问题）
        lefts = len(re.findall(r'\\\\left(?![a-zA-Z])', full_text))
        rights = len(re.findall(r'\\\\right(?![a-zA-Z])', full_text))
        if lefts != rights:
            issues.append((start_line + 1, 'ERROR', f'\\left({lefts})与\\right({rights})不匹配', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2c. 空\frac
        if re.search(r'\\frac\s*\{\s*\}\s*\{[^}]*\}', full_text) or \
           re.search(r'\\frac\s*\{[^}]*\}\s*\{\s*\}', full_text):
            issues.append((start_line + 1, 'WARN', '存在空\\frac', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2d. \begin/\end不匹配
        if full_text.count('\\begin') != full_text.count('\\end'):
            issues.append((start_line + 1, 'ERROR', '\\begin/\\end不匹配', True,
                          lambda t, s=start_line, e=end_line: t))

        # 2e. 检查\tag是否存在
        has_tag = '\\tag{' in full_text
        if not has_tag:
            issues.append((start_line + 1, 'ERROR', f'缺\\tag编号', True,
                          lambda t, s=start_line: _fix_missing_tag(t, s, chapter_n)))

    # Step 3: 提取所有\tag编号，检查连续性和重复
    tags = re.findall(r'\\tag\{' + tag_prefix + r'(\d+)\}', text)
    if tags:
        nums = [int(x) for x in tags]
        nums_sorted = sorted(nums)

        # 重复检查
        seen = set()
        dups = set()
        for n in nums:
            if n in seen:
                dups.add(n)
            seen.add(n)
        for d in sorted(dups):
            issues.append((0, 'ERROR', f'公式编号重复: {tag_prefix}{d}', True,
                          lambda t: _fix_duplicate_tags(t, chapter_n)))

        # 跳跃检查
        expected = list(range(min(nums_sorted), max(nums_sorted) + 1))
        missing = sorted(set(expected) - set(nums_sorted))
        if missing:
            issues.append((0, 'WARN', f'公式编号缺失: {", ".join(tag_prefix + str(m) for m in missing)}', True,
                          lambda t: _fix_numbering_gap(t, chapter_n)))

        # 编号超过+1检查（大跳跃）
        for i in range(1, len(nums_sorted)):
            if nums_sorted[i] - nums_sorted[i - 1] > 1:
                issues.append((0, 'INFO', f'编号跳跃: {tag_prefix}{nums_sorted[i-1]}→{tag_prefix}{nums_sorted[i]}', True,
                              lambda t: _fix_numbering_gap(t, chapter_n)))

    return issues


def _fix_missing_tag(text: str, line_idx: int, chapter_n: int) -> str:
    """给指定的公式块补上下一个可用编号。\tag必须放在$$...$$内部。"""
    lines = text.split('\n')
    tag_prefix = f'{chapter_n}-'

    # 找到当前最大的编号
    existing = re.findall(r'\\tag\{' + tag_prefix + r'(\d+)\}', text)
    next_num = max([int(x) for x in existing]) + 1 if existing else 1

    # 找到该公式块的闭合 $$
    for i in range(line_idx, len(lines)):
        if lines[i].strip() == '$$':
            # 在闭合 $$ 之前插入 \tag（保证在$$...$$内部）
            lines.insert(i, f'\\tag{{{tag_prefix}{next_num}}}')
            break

    return '\n'.join(lines)


def _fix_duplicate_tags(text: str, chapter_n: int) -> str:
    """修复重复编号：重新从1开始连续编号"""
    tag_prefix = f'{chapter_n}-'
    lines = text.split('\n')
    new_lines = []
    tag_counter = 1
    for line in lines:
        if re.match(r'^\\tag\{' + tag_prefix + r'\d+\}$', line.strip()):
            new_lines.append(f'\\tag{{{tag_prefix}{tag_counter}}}')
            tag_counter += 1
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)


def _fix_numbering_gap(text: str, chapter_n: int) -> str:
    """修复编号跳跃：重新从1开始连续编号"""
    return _fix_duplicate_tags(text, chapter_n)


# ── 合法Mermaid图表类型（首行关键字） ──
VALID_MERMAID_TYPES = {
    'flowchart', 'graph', 'sequenceDiagram', 'classDiagram',
    'stateDiagram-v2', 'erDiagram', 'gantt', 'pie', 'mindmap',
    'timeline', 'journey', 'xychart-beta', 'quadrantChart',
    'sankey-beta', 'gitgraph', 'requirementDiagram', 'block-beta',
}

def check_formula_format(text: str, verbose: bool = False) -> list:
    """检查公式格式规范"""
    issues = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        line_num = i + 1
        
        # tag与公式同行
        if re.search(r'\$\$.*\\\\?tag\{', stripped) or re.search(r'\\\\?tag\{[^}]+\}.*\$\$', stripped):
            issues.append((line_num, 'ERROR', 'tag与公式同行，应分开为两行', True, '_fix_tag_same_line'))
        
        # 空$$块
        if stripped == '$$' and i+1 < len(lines) and lines[i+1].strip() == '$$':
            issues.append((line_num, 'WARN', '空$$块（无内容）', True, None))
        
        # tag在$$之后
        if stripped == '$$' and i+1 < len(lines) and re.match(r'\\\\?tag\{', lines[i+1].strip()):
            issues.append((line_num, 'ERROR', 'tag在$$之后，应移至$$之前', True, '_fix_tag_after_dollar'))
    
    return issues


def _fix_formula_format(text: str) -> str:
    """修复公式格式问题"""
    lines = text.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 处理tag与公式同行:  $$ \tag{1-1} formula
        m = re.match(r'^(\s*)\$\$(.*?)(\\\\?tag\{[^}]+\})(.*)$', line)
        if m:
            indent = m.group(1)
            tag = m.group(3)
            after_tag = m.group(4).strip()
            new_lines.append(f'{indent}{tag}')
            new_lines.append(f'{indent}$$ {after_tag}' if after_tag else f'{indent}$$')
            i += 1
            continue
        
        # 处理tag在$$之后
        if stripped == '$$' and i+1 < len(lines) and re.match(r'\\\\?tag\{', lines[i+1].strip()):
            new_lines.append(lines[i+1])  # move tag before $$
            new_lines.append('$$')
            i += 2
            continue
        
        new_lines.append(line)
        i += 1
    
    return '\n'.join(new_lines)
