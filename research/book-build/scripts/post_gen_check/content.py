"""Content checks for post_generation_check — wikilinks, spelling, derivation depth, tag placement.""" 
import re

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


def check_derivation_depth(text: str, verbose: bool = False) -> list:
    """启发式检查公式推导深度。

    规则：每个显示公式之前应包含推导标记词（推导/原理/根据/由/代入）。
    如果连续3个公式前都没有推导标记词，标记为推导深度不足。
    """
    issues = []
    lines = text.split('\n')
    in_formula = False
    formula_positions = []
    formula_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '$$':
            if in_formula:
                context_start = max(0, formula_start - 5)
                context = '\n'.join(lines[context_start:formula_start])
                formula_positions.append((formula_start, context))
                in_formula = False
            else:
                formula_start = i
                in_formula = True

    # 检查每个公式前5行是否有推导词
    derivation_hints = ['推导', '原理', '根据', '代入', '由式', '可得',
                        '得', '代入式', '由', '可得', '整理得', '即']
    consecutive_bare = 0

    for f_line, context in formula_positions:
        has_hint = any(hint in context for hint in derivation_hints)
        if has_hint:
            consecutive_bare = 0
        else:
            consecutive_bare += 1

        if consecutive_bare >= 3:
            if issues and issues[-1][2].startswith(f'连续公式前无推导词'):
                continue
            issues.append((f_line + 1, 'WARN',
                           f'L{f_line + 1}: 连续{consecutive_bare}个公式前无推导词'
                           f' → 可能缺推导步骤（手动抽查确认）',
                           False, None))

    return issues
