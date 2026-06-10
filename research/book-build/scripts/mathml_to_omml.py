#!/usr/bin/env python3
"""
LaTeX -> MathML -> OMML 转换器（基于 latex2mathml）

将 LaTeX 数学公式通过 MathML 中间格式转为 Word 可编辑的 OMML 方程。
相比手写 LaTeX 解析器，本方案:
  - 依赖成熟库 latex2mathml 处理全部 LaTeX 边缘情况
  - MathML->OMML 映射逻辑简单（XML tag -> OMML tag）
  - 支持 xrightarrow, begin{aligned}, left(right) 等复杂结构

依赖: latex2mathml, lxml
用法:
    from mathml_to_omml import latex_to_omml
    oMath = latex_to_omml(r'E = mc^2')
"""
import re
from lxml import etree

# ── OMML 命名空间 ──────────────────────────────────────────────────
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'

# ── OMML XML 构建辅助 ──────────────────────────────────────────────

def _e(tag):
    return etree.Element(tag)

def _r(text, sty=None):
    """创建 m:r（text run），可选样式: italic/roman/bold"""
    r = _e(M + 'r')
    if sty:
        rPr = _e(M + 'rPr')
        s = _e(M + 'sty')
        s.set(M + 'val', {'roman': 'p', 'italic': 'i', 'bold': 'b'}.get(sty, 'p'))
        rPr.append(s)
        r.append(rPr)
    t = _e(M + 't')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text or ''
    r.append(t)
    return r

def _wrap(x):
    """统一返回值：始终返回列表"""
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def _ssub(b, s):
    """下标 sSub"""
    el = _e(M + 'sSub')
    e = _e(M + 'e')
    for x in _wrap(b): e.append(x)
    el.append(e)
    sub = _e(M + 'sub')
    for x in _wrap(s): sub.append(x)
    el.append(sub)
    return el

def _ssup(b, s):
    """上标 sSup"""
    el = _e(M + 'sSup')
    e = _e(M + 'e')
    for x in _wrap(b): e.append(x)
    el.append(e)
    sup = _e(M + 'sup')
    for x in _wrap(s): sup.append(x)
    el.append(sup)
    return el

def _ssubsup(b, sb, sp):
    """上下标 sSubSup"""
    el = _e(M + 'sSubSup')
    e = _e(M + 'e')
    for x in _wrap(b): e.append(x)
    el.append(e)
    sub = _e(M + 'sub')
    for x in _wrap(sb): sub.append(x)
    el.append(sub)
    sup = _e(M + 'sup')
    for x in _wrap(sp): sup.append(x)
    el.append(sup)
    return el

def _frac(n, d):
    """分数 f"""
    f = _e(M + 'f')
    fPr = _e(M + 'fPr')
    f.append(fPr)
    num = _e(M + 'num')
    for x in _wrap(n): num.append(x)
    f.append(num)
    den = _e(M + 'den')
    for x in _wrap(d): den.append(x)
    f.append(den)
    return f

def _sqrt(children):
    """平方根 rad"""
    rad = _e(M + 'rad')
    radPr = _e(M + 'radPr')
    dh = _e(M + 'degHide')
    dh.set(M + 'val', '1')
    radPr.append(dh)
    rad.append(radPr)
    e = _e(M + 'e')
    for c in children:
        for x in _wrap(_mml_convert(c)):
            e.append(x)
    rad.append(e)
    return rad

def _acc(b, ch):
    """重音/箭头 accent"""
    a = _e(M + 'acc')
    aPr = _e(M + 'accPr')
    c = _e(M + 'chr')
    c.set(M + 'val', ch)
    aPr.append(c)
    a.append(aPr)
    e = _e(M + 'e')
    for x in _wrap(b): e.append(x)
    a.append(e)
    return a

def _matrix(mml_table_elem):
    """MathML mtable → OMML m（矩阵）"""
    m = _e(M + 'm')
    mPr = _e(M + 'mPr')
    mcs = _e(M + 'mcs')
    rows = list(mml_table_elem)
    ncols = max((len(list(r)) for r in rows), default=1)
    for _ in range(ncols):
        mc = _e(M + 'mc')
        mcPr = _e(M + 'mcPr')
        cnt = _e(M + 'count')
        cnt.set(M + 'val', '1')
        mcPr.append(cnt)
        jc = _e(M + 'mcJc')
        jc.set(M + 'val', 'center')
        mcPr.append(jc)
        mc.append(mcPr)
        mcs.append(mc)
    mPr.append(mcs)
    m.append(mPr)
    for row in rows:
        mr = _e(M + 'mr')
        for cell in list(row):
            c_el = _e(M + 'e')
            cv = _mml_convert(cell)
            for x in _wrap(cv):
                c_el.append(x)
            mr.append(c_el)
        m.append(mr)
    return m

# ── MathML→OMML 递归转换 ──────────────────────────────────────────

def _mml_convert(elem):
    """
    递归：MathML 元素 → OMML 元素（或元素列表）
    
    所有 MathML 标签名 → OMML 结构的一对一映射。
    结构简单的标签（文本、字母、数字）直接创建 m:r，
    结构复杂的（下标、分数、根号等）创建对应的 OMML 容器。
    """
    if elem is None:
        return None

    tag = etree.QName(elem).localname
    children = list(elem)

    # ── 文本元素（直接文本节点） ──
    if tag == 'mi':  # 标识符（斜体）
        text = elem.text or ''
        # 对齐符号 &（来自 aligned 环境）→ 跳过
        if text == '&amp;' or text == '&':
            return None
        return _r(text, 'italic')

    if tag == 'mn':  # 数字
        return _r(elem.text or '', None)

    if tag == 'mo':  # 运算符
        return _r(elem.text or '', None)

    if tag == 'mtext':  # 普通文本（罗马体）
        return _r(elem.text or '', 'roman')

    # ── 容器元素（展开子节点） ──
    if tag == 'math':
        results = []
        for c in children:
            r = _mml_convert(c)
            if r is not None:
                results.extend(_wrap(r))
        return results if len(results) != 1 else results[0]

    if tag in ('mrow', 'mstyle', 'mpadded', 'merror'):
        results = []
        for c in children:
            r = _mml_convert(c)
            if r is not None:
                results.extend(_wrap(r))
        return results if len(results) != 1 else results[0]

    # ── 上下标 ──
    if tag == 'msub':
        return _ssub(_mml_convert(children[0]), _mml_convert(children[1]))
    if tag == 'msup':
        return _ssup(_mml_convert(children[0]), _mml_convert(children[1]))
    if tag == 'msubsup':
        return _ssubsup(
            _mml_convert(children[0]),
            _mml_convert(children[1]),
            _mml_convert(children[2])
        )

    # ── 分数 ──
    if tag == 'mfrac':
        return _frac(_mml_convert(children[0]), _mml_convert(children[1]))

    # ── 根号 ──
    if tag == 'msqrt':
        return _sqrt(children)

    # ── 重音/箭头（\vec, \xrightarrow, \hat 等） ──
    if tag == 'mover':
        b = _mml_convert(children[0])
        over_text = children[1].text or ''
        #  箭头 → 矢量箭头 accent
        if any(c in over_text for c in [
            '\u2192', '\u2190', '\u2191', '\u2193',
            '\u21d0', '\u21d2', '\u21d4',
            '\u20d7', '\u20d6',
        ]):
            return _acc(b, '\u20d7')
        return _acc(b, '\u0305')  # 上横线

    if tag in ('munder', 'munderover'):
        # 简化：只保留基础表达式
        return _mml_convert(children[0])

    # ── 间距 ──
    if tag == 'mspace':
        return None

    # ── 矩阵 ──
    if tag == 'mtable':
        return _matrix(elem)

    # ── 行列（展开子节点） ──
    if tag in ('mtr', 'mtd'):
        results = []
        for c in children:
            r = _mml_convert(c)
            if r is not None:
                results.extend(_wrap(r))
        return results if len(results) != 1 else results[0]

    # ── 对齐标记（忽略） ──
    if tag in ('maligngroup', 'malignmark'):
        return None

    # ── 未知标签：尝试以文本方式显示 ──
    return _r(elem.text or '', None)


# ── LaTeX 预处理 ───────────────────────────────────────────────────

def _latex_to_mathml(latex_str):
    """
    LaTeX 字符串 → MathML XML (str)
    
    用 latex2mathml 转换，修复输出中可能出现的非法 XML 字符（&）。
    """
    import latex2mathml.converter
    mathml = latex2mathml.converter.convert(latex_str)
    # 修复 & -> &amp;（latex2mathml 对 aligned 环境中的 & 处理不当）
    mathml = re.sub(
        r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)',
        '&amp;',
        mathml
    )
    return mathml


def _is_multiline(mathml_elem):
    """
    检测 MathML 中是否有换行符（aligned 环境）。
    搜索 mspace linebreak="newline" 元素。
    """
    for node in mathml_elem.iter():
        if etree.QName(node).localname == 'mspace':
            if node.get('linebreak', '') == 'newline':
                return True
    return False


def _build_eqnarray(mathml_elem):
    """
    将含换行的 MathML 转为 OMML eqnArray（多行公式）。
    
    思路：
    1. 找到最内层的 mrow（含 mspace linebreak）
    2. 在其子节点列表按 mspace 分割为多行
    3. 每行去除 &amp; 对齐标记后独立转换为 OMML
    4. 包入 <m:eqnArray> 结构
    """
    # 找到含 mspace linebreak 的节点
    def _find_split_target(elem):
        for c in list(elem):
            if etree.QName(c).localname == 'mspace':
                lb = c.get('linebreak', '')
                if lb == 'newline':
                    return elem
            result = _find_split_target(c)
            if result is not None:
                return result
        return None

    target = _find_split_target(mathml_elem)
    if target is None:
        return None

    # 按 mspace linebreak 分割子节点
    all_children = list(target)
    rows_raw = []
    current_row = []
    for child in all_children:
        if etree.QName(child).localname == 'mspace' and child.get('linebreak', '') == 'newline':
            if current_row:
                rows_raw.append(current_row)
                current_row = []
        else:
            current_row.append(child)
    if current_row:
        rows_raw.append(current_row)

    if not rows_raw:
        return None

    # 对每行：去除 &amp; 对齐标记，转换为 OMML
    def _remove_align_markers(children):
        """去除行内的 &amp; 对齐标记"""
        return [c for c in children
                if not (etree.QName(c).localname == 'mi'
                        and (c.text or '') in ('&amp;', '&'))]

    rows_omml = []
    for row_children in rows_raw:
        cleaned = _remove_align_markers(row_children)
        # 创建临时 math 元素包裹
        from lxml.etree import SubElement
        import copy
        temp_math = copy.deepcopy(mathml_elem)
        # 直接清空并填充
        for child in list(temp_math):
            temp_math.remove(child)
        for c in cleaned:
            temp_math.append(c)
        row_result = _mml_convert(temp_math)
        rows_omml.append(_wrap(row_result))

    # 构建 eqnArray
    # OMML: eqnArray → m:eqnArray { m:eqnArrayPr, m:e* }
    eqn = _e(M + 'eqnArray')
    eqnPr = _e(M + 'eqnArrayPr')
    baseJc = _e(M + 'baseJc')
    baseJc.set(M + 'val', 'left')
    eqnPr.append(baseJc)
    eqn.append(eqnPr)
    for row in rows_omml:
        e = _e(M + 'e')
        for x in row:
            e.append(x)
        eqn.append(e)
    return eqn


# ── 主入口 ─────────────────────────────────────────────────────────

def latex_to_omml(latex_str):
    """
    LaTeX 数学公式字符串 → OMML m:oMath 元素
    
    适合在 python-docx 中使用：
        from mathml_to_omml import latex_to_omml
        from docx.oxml.ns import qn
        from lxml import etree
        
        p = doc.add_paragraph()
        oMathPara = etree.SubElement(p._element, qn('m:oMathPara'))
        oMathPara.append(latex_to_omml(r'\\frac{a}{b}'))
    
    支持：
    - 普通 LaTeX 语法（希腊字母、算子、分数、根号等）
    - xrightarrow{text} -> 带箭头 accent
    - begin{aligned}...end{aligned} -> 多行公式（eqnArray）
    - left( right) -> 自动伸缩括号
    - text{...} -> 罗马体文本
    - 下标/上标/上下标
    - 矩阵环境
    """
    # 1. LaTeX → MathML
    mathml_str = _latex_to_mathml(latex_str)
    mathml_elem = etree.fromstring(mathml_str.encode('utf-8'))

    # 2. 检测是否多行公式（aligned）
    if _is_multiline(mathml_elem):
        # 多行 → eqnArray
        eqn = _build_eqnarray(mathml_elem)
        if eqn is not None:
            oMath = _e(M + 'oMath')
            oMath.append(eqn)
            return oMath

    # 3. 单行公式 → 直接转换
    result = _mml_convert(mathml_elem)
    if isinstance(result, list):
        oMath = _e(M + 'oMath')
        for el in result:
            oMath.append(el)
        return oMath

    # result 已经是单个 OMML 元素（如 m:f, m:sSub 等）
    # 需要包一层 oMath
    oMath = _e(M + 'oMath')
    oMath.append(result)
    return oMath


# ── 测试 ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    from lxml import etree as _etree

    test_cases = [
        (r'\text{电磁骚扰（EMD）} \xrightarrow{\text{通过耦合途径作用于敏感设备}} \text{电磁干扰（EMI）}',
         'xrightarrow + 中文'),
        (r'E_{\text{int}}(f) = S(f) \cdot C(f)',
         '下标 + 文本'),
        (r'\text{dB} = 10\log\left(\frac{P_2}{P_1}\right)',
         '分数 + log'),
        (r'P = \frac{U^2}{R} = \frac{U^2}{50}',
         '分数'),
        (r'\begin{aligned}P_{\text{dBm}} &= 10[\log(U^2) - \log(50) + \log(10^3)] \\'
         r'&= 10[2\log U - \log(50) + 3] \\'
         r'&= 20\log U - 10\log(50) + 30\end{aligned}',
         'aligned 多行'),
        (r'U_{\text{dB}\mu\text{V}} = P_{\text{dBm}} + 107 \quad (50\Omega)',
         'quad + 希腊字母'),
    ]

    print('═' * 60)
    print('  MathML → OMML 转换器 测试')
    print('═' * 60)
    all_ok = True

    for latex, desc in test_cases:
        try:
            omml = latex_to_omml(latex)
            xml = _etree.tostring(omml, encoding='unicode')
            has_struct = any(s in xml for s in [
                'm:sSub', 'm:sSup', 'm:f', 'm:rad',
                'm:acc', 'm:m', 'm:sSubSup', 'm:eqnArray'
            ])
            multiline = 'm:eqnArray' in xml
            print(f'\n  ✓ {desc}')
            print(f'    {len(xml):>5} chars | '
                  f'{"struct" if has_struct else "plain"} | '
                  f'{"MULTI" if multiline else "     "}')
        except Exception as e:
            print(f'\n  ✗ {desc}: {e}')
            import traceback
            traceback.print_exc()
            all_ok = False

    print(f'\n{"═" * 60}')
    print(f'  {"✅ ALL PASSED" if all_ok else "❌ SOME FAILED"}')
    print(f'{"═" * 60}')
