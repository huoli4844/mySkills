"""Mermaid checks for post_generation_check — syntax validation, caption detection.""" 
import re

VALID_MERMAID_TYPES = {
    'graph', 'flowchart', 'sequenceDiagram', 'classDiagram',
    'stateDiagram', 'stateDiagram-v2', 'erDiagram',
    'gantt', 'pie', 'pie showData', 'quadrantChart',
    'requirementDiagram', 'gitgraph', 'mindmap', 'timeline',
    'xychart-beta', 'block', 'sankey-beta',
}

def check_mermaid(text: str, verbose: bool = False) -> list:
    """检查Mermaid图语法——全面校验，修复之前只查闭合的漏洞"""
    issues = []
    lines = text.split('\n')
    in_mermaid = False
    mermaid_content = []
    mermaid_start_line = 0
    mermaid_idx = 0  # 图序号

    # 变量跟踪所有 mermaid 块的起止行号
    mermaid_blocks = []
    for i, line in enumerate(lines):
        if line.strip() == '```mermaid':
            in_mermaid = True
            mermaid_start_line = i
            mermaid_content = []
            mermaid_idx += 1
        elif in_mermaid and line.strip() == '```':
            in_mermaid = False
            mermaid_blocks.append((mermaid_idx, mermaid_start_line, i, mermaid_content))
        elif in_mermaid:
            mermaid_content.append((i, line))

    # 检查未闭合的
    if in_mermaid:
        issues.append((mermaid_start_line + 1, 'ERROR',
                       f'Mermaid图{mermaid_idx}缺闭合```', True,
                       lambda t: t))

    for idx, start_line, end_line, content in mermaid_blocks:
        block_lines = [l for _, l in content]
        if not block_lines or all(not l.strip() for l in block_lines):
            issues.append((start_line + 1, 'WARN',
                           f'Mermaid图{idx}内容为空', False, None))
            continue

        first_line = block_lines[0].strip()
        # 跳过 %%{init} 配置行，找第一个非init行为图表类型
        init_skipped = 0
        for bl in block_lines:
            if bl.strip().startswith('%%{init'):
                init_skipped += 1
                continue
            first_line = bl.strip()
            break
        chart_type = first_line.split()[0] if first_line else ''

        # ── 检查1：图表类型是否合法 ──
        if chart_type not in VALID_MERMAID_TYPES:
            issues.append((start_line + 1, 'WARN',
                           f'Mermaid图{idx}: 未知图表类型"{chart_type}"'
                           f'（合法: {", ".join(sorted(VALID_MERMAID_TYPES)[:10])}...）',
                           False, None))

        # ── 检查2：xychart-beta 语法 ──
        if chart_type == 'xychart-beta':
            valid_kw = {'title', 'x-axis', 'y-axis', 'bar', 'line'}
            found_kw = set()
            invalid_kw = set()
            for bline in block_lines[init_skipped + 1:]:  # 跳过图表类型行（xychart-beta本身不是关键字）
                kw = bline.strip().split()[0] if bline.strip() else ''
                if kw and kw not in valid_kw:
                    invalid_kw.add(kw)
                elif kw in valid_kw:
                    found_kw.add(kw)
            for bad in invalid_kw:
                issues.append((start_line + 1, 'ERROR',
                               f'Mermaid图{idx} xychart-beta含非法关键字"{bad}"'
                               f'（仅支持: {", ".join(sorted(valid_kw))}）',
                               False, None))
            if 'y-axis' not in found_kw:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} xychart-beta缺y-axis定义',
                               False, None))
            bar_or_line = found_kw & {'bar', 'line'}
            if not bar_or_line:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} xychart-beta缺bar/line数据',
                               False, None))

        # ── 检查3：flowchart/graph 节点标签引号 ──
        if chart_type in ('flowchart', 'graph'):
            for bline in block_lines:
                stripped = bline.strip()
                # 检测节点标签 [] 内含逗号或括号但未用引号包裹
                for m in re.finditer(r'([A-Za-z0-9_]+)\[([^\\"]*?)\]', stripped):
                    label = m.group(2)
                    if (',' in label or '(' in label or ')' in label) and \
                       '"' not in label:
                        issues.append((start_line + 1, 'WARN',
                                       f'Mermaid图{idx} 节点"{m.group(1)}"标签含'
                                       f'逗号/括号但未用引号: [{label}] → '
                                       f'["{label}"]',
                                       False, None))

        # ── 检查4：subgraph 标题特殊字符（Obsidian词法崩溃根因） ──
        for bline in block_lines:
            stripped = bline.strip()
            # subgraph 标题含括号/破折号/逗号等特殊字符
            if stripped.startswith('subgraph '):
                title = stripped[len('subgraph '):].strip()
                if re.search(r'[（）()—–,，]', title):
                    issues.append((start_line + 1, 'ERROR',
                                   f'Mermaid图{idx} subgraph标题含特殊字符: '
                                   f'"{title[:50]}"'
                                   f' → Obsidian词法错误，请移除括号/破折号/逗号',
                                   False, None))

        # ── 检查5：emoji在节点标签中 ──
        emoji_pattern = re.compile(
            '[\U0001F300-\U0001F9FF'  # Misc symbols + emoticons
            '\u2600-\u27BF'           # Misc symbols + dingbats
            '\u2B05-\u2B55'           # Arrows + misc
            '\u2702-\u27B0'           # Dingbats
            '\u23E9-\u23FA'           # Transport symbols
            '\u25AA-\u25FE'           # Geometric shapes
            '\u00A9\u00AE\u2122'     # Copyright, registered, trademark
            ']')
        for bline in block_lines:
            emojis = emoji_pattern.findall(bline)
            if emojis:
                issues.append((start_line + 1, 'WARN',
                               f'Mermaid图{idx} 节点含emoji: {" ".join(set(emojis))}'
                               f' → 替换为纯文字（Obsidian渲染崩溃）',
                               False, None))

        # ── 检查6：%%{init} 格式 ──
        for bline in block_lines:
            stripped = bline.strip()
            if '%%{init' in stripped:
                if "'" in stripped:
                    issues.append((start_line + 1, 'WARN',
                                   f'Mermaid图{idx} %%{{init}}用了单引号'
                                   f' → 必须用双引号JSON',
                                   False, None))
                if not stripped.endswith('%%'):
                    issues.append((start_line + 1, 'WARN',
                                   f'Mermaid图{idx} %%{{init}}缺闭合%%',
                                   False, None))

        # ── 检查6：classDef 定义覆盖 ──
        classdefs = set()
        class_uses = set()
        for bline in block_lines:
            m = re.match(r'classDef\s+(\w+)', bline.strip())
            if m:
                classdefs.add(m.group(1))
            for cm in re.finditer(r'([A-Za-z0-9_]+)\s*:::\s*(\w+)', bline.strip()):
                class_uses.add(cm.group(2))
        undefined_classes = class_uses - classdefs
        if undefined_classes:
            issues.append((start_line + 1, 'ERROR',
                           f'Mermaid图{idx} 引用未定义的classDef: '
                           f'{", ".join(sorted(undefined_classes))}',
                           False, None))

    return issues


def check_wikilinks(text: str) -> list:
    """检查教材中是否含有[[wikilink]]（教材禁用），返回问题列表"""
    issues = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', text):
        line_num = text[:m.start()].count('\n') + 1
        issues.append((line_num, 'ERROR',
                       f'行{line_num}: 发现[[{m.group(1)}]] → 教材正文禁用wikilink'))
    return issues


def check_tag_placement(text: str) -> list:
    """检查\\tag{}是否放在$$块外部（渲染失败的根本原因之一），返回问题列表"""
    issues = []
    lines = text.split('\n')
    in_math = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '$$':
            in_math = not in_math
            continue
        # 在 $$ 块外部发现 \\tag{...} → 孤立标签
        if not in_math and re.match(r'^\\tag\{\d+-\d+\}$', stripped):
            issues.append((i + 1, 'ERROR',
                           f'L{i+1}: \\tag{stripped[5:]} 在$$块外部 → '
                           f'渲染失败，必须移入$$...$$内部',
                           True, lambda t: t))  # 可标记但自动修复用clean_formula_numbers
    return issues


def check_spelling(text: str, verbose: bool = False) -> list:
    """检查常见LaTeX拼写错误，返回问题列表"""
    issues = []
    # 这些是真正的拼写错误（不是命令子串）
    patterns = {
        r'\bomege\b': 'omega',
        r'\bthets\b': 'theta',
        r'\bepsilo\b': 'epsilon',
        r'\blamda\b': 'lambda',
        r'\bdelat\b': 'delta',
        r'\bsgima\b': 'sigma',
        r'\balfe\b': 'alpha',
        r'\bbete\b': 'beta',
        r'\bgama\b': 'gamma',
        r'\bpai\b': 'pi',
        r'\binfinty\b': 'infty',
        r'\bOmege\b': 'Omega',
    }
    for pattern, correct in patterns.items():
        for m in re.finditer(pattern, text):
            # 确保不是命令的一部分
            line_num = text[:m.start()].count('\n') + 1
            issues.append((line_num, 'WARN', f'疑似拼写错误: "{m.group()}"→"{correct}"', True,
                          lambda t, p=pattern, c=correct: t.replace(p, c)))

    return issues


def _fix_mermaid_issues(text: str) -> str:
    """修复Mermaid语法问题：移除xychart-beta中的非法关键字"""
    lines = text.split('\n')
    new_lines = []
    in_mermaid = False
    in_xychart = False

    # 已知的xychart-beta非法关键字列表
    INVALID_XYCHART_KW = {
        'bar-group-group', 'bar-group', 'group-bar',
        'test-chart', 'sample-chart', 'demo-chart',
    }

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == '```mermaid':
            in_mermaid = True
            in_xychart = False
            new_lines.append(line)
        elif in_mermaid and stripped == '```':
            in_mermaid = False
            in_xychart = False
            new_lines.append(line)
        elif in_mermaid:
            # 检测xychart-beta类型
            if stripped.startswith('xychart-beta'):
                in_xychart = True
                new_lines.append(line)
            elif in_xychart:
                kw = stripped.split()[0] if stripped else ''
                if kw in INVALID_XYCHART_KW:
                    # 跳过该行（移除非法关键字行）
                    continue
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    return '\n'.join(new_lines)


def check_mermaid_has_caption(text: str, verbose: bool = False) -> list:
    """检查Mermaid图后是否有文字说明（有图必有说明）。

    规则：每个 ```mermaid...``` 块之后、下一个标题/代码块之前，
    必须存在 *图N-X：描述* 格式的图注。
    """
    issues = []
    lines = text.split('\n')
    in_mermaid = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '```mermaid':
            in_mermaid = True
        elif in_mermaid and stripped == '```':
            in_mermaid = False
            # 检查闭合后3行内是否有 *图 图注
            has_caption = False
            for j in range(i + 1, min(i + 6, len(lines))):
                if re.match(r'\*图\d+-\d+', lines[j].strip()):
                    has_caption = True
                    break
                if not lines[j].strip():
                    continue
                if lines[j].strip().startswith('#') or lines[j].strip().startswith('```'):
                    break
            if not has_caption:
                issues.append((i + 1, 'WARN',
                               f'L{i + 1}: Mermaid图后3行内缺图注'
                               f' (*图N-X：描述*) → 有图必有说明',
                               False, None))
    return issues
