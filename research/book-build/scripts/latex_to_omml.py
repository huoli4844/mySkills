#!/usr/bin/env python3
"""
LaTeX → OMML 转换器
将 LaTeX 数学公式字符串转为 Word OMML (Office Math Markup Language) XML 元素。

支持的结构：
- 上下标：x^2, x_1, x_1^2
- 分数：\frac{a}{b}, \dfrac{a}{b}
- 根号：\sqrt{x}, \sqrt[n]{x}
- 希腊字母：\alpha, \beta, \gamma, ...
- 运算符：\sum, \int, \prod, \lim
- 函数：\sin, \cos, \ln, \lg, \log, \exp, \min, \max
- 括号：\left( \right), \biggl( \biggr)
- 特殊符号：\infty, \partial, \nabla, \cdot, \times
- 矩阵/行列式基本支持
- 文本模式：\mathrm{}, \text{}, \mathcal{}, \mathbf{}
"""
import re
from lxml import etree

M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_NS = '{http://www.w3.org/XML/1998/namespace}'

def _e(tag, attrib=None, text=None):
    el = etree.Element(tag, attrib or {})
    if text is not None:
        el.text = text
    return el

def omml_r(text, sty=None):
    """<m:r><m:rPr>?<m:t>text</m:t></m:r>"""
    r = _e(M + 'r')
    if sty:
        rPr = _e(M + 'rPr')
        if sty == 'roman':
            sty_el = _e(M + 'sty'); sty_el.set(M + 'val', 'p')
            rPr.append(sty_el)
        elif sty == 'bold':
            sty_el = _e(M + 'sty'); sty_el.set(M + 'val', 'b')
            rPr.append(sty_el)
        elif sty == 'italic':
            sty_el = _e(M + 'sty'); sty_el.set(M + 'val', 'i')
            rPr.append(sty_el)
        if len(rPr) > 0:
            r.append(rPr)
    t = _e(M + 't')
    if text and (' ' in text or text.startswith(' ') or text.endswith(' ')):
        t.set(XML_NS + 'space', 'preserve')
    t.text = text or ''
    r.append(t)
    return r

# ── LaTeX 解析器 ──────────────────────────────────────────────────

class LatexToOmml:
    """递归下降解析 LaTeX 数学公式，生成 OMML 元素"""

    GREEK_LETTERS = {
        'alpha': '\u03b1', 'beta': '\u03b2', 'gamma': '\u03b3', 'delta': '\u03b4',
        'epsilon': '\u03b5', 'varepsilon': '\u03b5', 'zeta': '\u03b6', 'eta': '\u03b7',
        'theta': '\u03b8', 'vartheta': '\u03d1', 'iota': '\u03b9', 'kappa': '\u03ba',
        'lambda': '\u03bb', 'mu': '\u03bc', 'nu': '\u03bd', 'xi': '\u03be',
        'pi': '\u03c0', 'varpi': '\u03d6', 'rho': '\u03c1', 'varrho': '\u03f1',
        'sigma': '\u03c3', 'varsigma': '\u03c2', 'tau': '\u03c4', 'upsilon': '\u03c5',
        'phi': '\u03c6', 'varphi': '\u03d5', 'chi': '\u03c7', 'psi': '\u03c8',
        'omega': '\u03c9',
        'Gamma': '\u0393', 'Delta': '\u0394', 'Theta': '\u0398', 'Lambda': '\u039b',
        'Xi': '\u039e', 'Pi': '\u03a0', 'Sigma': '\u03a3', 'Upsilon': '\u03a5',
        'Phi': '\u03a6', 'Psi': '\u03a8', 'Omega': '\u03a9',
    }

    OPERATORS = {
        'sum': '\u2211', 'prod': '\u220f', 'coprod': '\u2210',
        'int': '\u222b', 'iint': '\u222c', 'iiint': '\u222d', 'oint': '\u222e',
        'bigcup': '\u22c3', 'bigcap': '\u22c2', 'bigsqcup': '\u2a06',
        'bigvee': '\u22c1', 'bigwedge': '\u22c0', 'bigoplus': '\u2a01',
        'bigotimes': '\u2a02', 'biguplus': '\u2a04',
    }

    FUNCTIONS = {
        'sin': 'sin', 'cos': 'cos', 'tan': 'tan', 'cot': 'cot',
        'sec': 'sec', 'csc': 'csc',
        'arcsin': 'arcsin', 'arccos': 'arccos', 'arctan': 'arctan',
        'sinh': 'sinh', 'cosh': 'cosh', 'tanh': 'tanh',
        'ln': 'ln', 'lg': 'lg', 'log': 'log', 'exp': 'exp',
        'lim': 'lim', 'limsup': 'lim sup', 'liminf': 'lim inf',
        'min': 'min', 'max': 'max', 'sup': 'sup', 'inf': 'inf',
        'det': 'det', 'dim': 'dim', 'ker': 'ker',
        'arg': 'arg', 'deg': 'deg', 'gcd': 'gcd',
        'Re': 'Re', 'Im': 'Im',
    }

    SYMBOLS = {
        'infty': '\u221e', 'partial': '\u2202', 'nabla': '\u2207',
        'cdot': '\u22c5', 'times': '\u00d7', 'div': '\u00f7',
        'pm': '\u00b1', 'mp': '\u2213',
        'leq': '\u2264', 'geq': '\u2265', 'neq': '\u2260',
        'approx': '\u2248', 'equiv': '\u2261', 'sim': '\u223c',
        'propto': '\u221d', 'perp': '\u22a5', 'parallel': '\u2225',
        'angle': '\u2220', 'triangle': '\u25b3',
        'circ': '\u2218', 'bullet': '\u2219',
        'oplus': '\u2295', 'otimes': '\u2297', 'odot': '\u2299',
        'vee': '\u2228', 'wedge': '\u2227',
        'rightarrow': '\u2192', 'leftarrow': '\u2190',
        'Rightarrow': '\u21d2', 'Leftarrow': '\u21d0',
        'leftrightarrow': '\u2194', 'Leftrightarrow': '\u21d4',
        'uparrow': '\u2191', 'downarrow': '\u2193',
        'to': '\u2192',
        'forall': '\u2200', 'exists': '\u2203', 'nexists': '\u2204',
        'in': '\u2208', 'notin': '\u2209',
        'subset': '\u2282', 'supset': '\u2283',
        'subseteq': '\u2286', 'supseteq': '\u2287',
        'cup': '\u222a', 'cap': '\u2229',
        'emptyset': '\u2205', 'varnothing': '\u2205',
        'mathbb{R}': '\u211d', 'mathbb{Z}': '\u2124',
        'mathbb{N}': '\u2115', 'mathbb{C}': '\u2102',
        'mathbb{Q}': '\u211a',
        'hbar': '\u210f', 'ell': '\u2113',
        'dag': '\u2020', 'ddag': '\u2021',
        'ldots': '\u2026', 'cdots': '\u22ef', 'vdots': '\u22ee', 'ddots': '\u22f1',
        'quad': '\u2003', 'qquad': '\u2003\u2003',
    }

    def __init__(self):
        self.pos = 0
        self.text = ''

    def parse(self, latex_str):
        """主入口：LaTeX 字符串 → OMML oMath 元素"""
        self.text = latex_str.strip()
        self.pos = 0
        oMath = _e(M + 'oMath')
        elements = self._parse_expr(top_level=True)
        for el in elements:
            oMath.append(el)
        return oMath

    def _peek(self, n=1):
        return self.text[self.pos:self.pos+n]

    def _remaining(self):
        return self.text[self.pos:]

    def _at_end(self):
        return self.pos >= len(self.text)

    def _consume(self, n=1):
        result = self.text[self.pos:self.pos+n]
        self.pos += n
        return result

    def _skip_whitespace(self):
        while self.pos < len(self.text) and self.text[self.pos] in ' \t\n\r':
            self.pos += 1

    def _read_command(self):
        """读取 \\command 形式的 LaTeX 命令"""
        start = self.pos
        self.pos += 1  # skip backslash
        if self.pos >= len(self.text):
            return '\\'
        ch = self.text[self.pos]
        if ch.isalpha():
            cmd_start = self.pos
            while self.pos < len(self.text) and self.text[self.pos].isalpha():
                self.pos += 1
            return self.text[cmd_start:self.pos]
        elif ch in '{}\\_ ^~&|':
            self.pos += 1
            return ch
        else:
            self.pos += 1
            return ch

    def _read_brace_group(self):
        """读取 {content}，返回 content 部分"""
        self._skip_whitespace()
        if self._at_end() or self.text[self.pos] != '{':
            return None
        self.pos += 1  # skip {
        depth = 1
        start = self.pos
        while self.pos < len(self.text) and depth > 0:
            if self.text[self.pos] == '{' and (self.pos == 0 or self.text[self.pos-1] != '\\'):
                depth += 1
            elif self.text[self.pos] == '}' and (self.pos == 0 or self.text[self.pos-1] != '\\'):
                depth -= 1
            self.pos += 1
        return self.text[start:self.pos-1]

    def _parse_expr(self, top_level=False):
        """解析一个表达式，返回 OMML 元素列表"""
        elements = []
        while not self._at_end():
            ch = self._peek()
            if ch == '}' and not top_level:
                break
            if ch == '&' or ch == '\\\\':
                break  # matrix cell separator

            if ch == '{':
                # Brace group - just parse contents
                content = self._read_brace_group()
                if content is not None:
                    sub_parser = LatexToOmml()
                    sub_parser.text = content
                    sub_parser.pos = 0
                    sub_elements = sub_parser._parse_expr(top_level=True)
                    elements.extend(sub_elements)
                continue

            if ch == '\\':
                cmd = self._read_command()
                el = self._handle_command(cmd)
                if el is not None:
                    if isinstance(el, list):
                        elements.extend(el)
                    else:
                        elements.append(el)
                continue

            if ch == '^':
                self.pos += 1
                # Superscript - attach to previous element
                sup_content = self._parse_supsub_arg()
                if elements:
                    prev = elements.pop()
                    sup_els = self._content_to_omml(sup_content)
                    elements.append(self._make_sup(prev, sup_els))
                else:
                    sup_els = self._content_to_omml(sup_content)
                    elements.append(self._make_sup(omml_r(''), sup_els))
                continue

            if ch == '_':
                self.pos += 1
                # Subscript
                sub_content = self._parse_supsub_arg()
                if elements:
                    prev = elements.pop()
                    sub_els = self._content_to_omml(sub_content)
                    # Check if next is ^ (subsup)
                    self._skip_whitespace()
                    if not self._at_end() and self._peek() == '^':
                        self.pos += 1
                        sup_content2 = self._parse_supsub_arg()
                        sup_els = self._content_to_omml(sup_content2)
                        elements.append(self._make_subsup(prev, sub_els, sup_els))
                    else:
                        elements.append(self._make_sub(prev, sub_els))
                else:
                    sub_els = self._content_to_omml(sub_content)
                    elements.append(self._make_sub(omml_r(''), sub_els))
                continue

            # Regular character
            self.pos += 1
            # Check if next is _ or ^ - if so, this is a base
            if not self._at_end() and self._peek() in '_^':
                elements.append(omml_r(ch))
            else:
                # Accumulate regular characters
                buf = ch
                while not self._at_end() and self._peek() not in '_^{}\\&':
                    buf += self._consume()
                elements.append(omml_r(buf))

        return elements

    def _parse_supsub_arg(self):
        """Parse a superscript/subscript argument"""
        self._skip_whitespace()
        if self._at_end():
            return ''
        if self.text[self.pos] == '{':
            return self._read_brace_group() or ''
        else:
            # Single token
            ch = self._consume()
            if ch == '\\':
                cmd = self._read_command()
                return '\\' + cmd
            return ch

    def _content_to_omml(self, content_str):
        """Parse a content string into OMML elements list"""
        sub_parser = LatexToOmml()
        sub_parser.text = content_str
        sub_parser.pos = 0
        return sub_parser._parse_expr(top_level=True)

    def _make_sub(self, base_el, sub_els):
        """Create m:sSub"""
        sSub = _e(M + 'sSub')
        e = _e(M + 'e')
        if isinstance(base_el, list):
            for el in base_el:
                e.append(el)
        else:
            e.append(base_el)
        sSub.append(e)
        sub = _e(M + 'sub')
        for el in sub_els:
            sub.append(el)
        sSub.append(sub)
        return sSub

    def _make_sup(self, base_el, sup_els):
        """Create m:sSup"""
        sSup = _e(M + 'sSup')
        e = _e(M + 'e')
        if isinstance(base_el, list):
            for el in base_el:
                e.append(el)
        else:
            e.append(base_el)
        sSup.append(e)
        sup = _e(M + 'sup')
        for el in sup_els:
            sup.append(el)
        sSup.append(sup)
        return sSup

    def _make_subsup(self, base_el, sub_els, sup_els):
        """Create m:sSubSup"""
        sSubSup = _e(M + 'sSubSup')
        e = _e(M + 'e')
        if isinstance(base_el, list):
            for el in base_el:
                e.append(el)
        else:
            e.append(base_el)
        sSubSup.append(e)
        sub = _e(M + 'sub')
        for el in sub_els:
            sub.append(el)
        sSubSup.append(sub)
        sup = _e(M + 'sup')
        for el in sup_els:
            sup.append(el)
        sSubSup.append(sup)
        return sSubSup

    def _handle_command(self, cmd):
        """Handle a LaTeX command, return OMML element(s)"""

        # Fractions
        if cmd in ('frac', 'dfrac', 'tfrac'):
            num_str = self._read_brace_group() or ''
            den_str = self._read_brace_group() or ''
            num_els = self._content_to_omml(num_str)
            den_els = self._content_to_omml(den_str)
            f = _e(M + 'f')
            fPr = _e(M + 'fPr')
            f.append(fPr)
            num = _e(M + 'num')
            for el in num_els:
                num.append(el)
            f.append(num)
            den = _e(M + 'den')
            for el in den_els:
                den.append(el)
            f.append(den)
            return f

        # Square root / nth root
        if cmd == 'sqrt':
            self._skip_whitespace()
            if not self._at_end() and self._peek() == '[':
                # nth root: \sqrt[n]{x}
                self.pos += 1
                deg_start = self.pos
                while self.pos < len(self.text) and self.text[self.pos] != ']':
                    self.pos += 1
                deg_str = self.text[deg_start:self.pos]
                if self.pos < len(self.text):
                    self.pos += 1  # skip ]
                content_str = self._read_brace_group() or ''
                deg_els = self._content_to_omml(deg_str)
                content_els = self._content_to_omml(content_str)
                rad = _e(M + 'rad')
                radPr = _e(M + 'radPr')
                degHide = _e(M + 'degHide')
                degHide.set(M + 'val', '0')
                radPr.append(degHide)
                rad.append(radPr)
                deg = _e(M + 'deg')
                for el in deg_els:
                    deg.append(el)
                rad.append(deg)
                e = _e(M + 'e')
                for el in content_els:
                    e.append(el)
                rad.append(e)
                return rad
            else:
                content_str = self._read_brace_group() or ''
                # If no brace group, take next token
                if not content_str:
                    self._skip_whitespace()
                    if not self._at_end():
                        if self._peek() == '\\':
                            self.pos += 1
                            tok = self._read_command()
                            content_str = '\\' + tok
                        else:
                            content_str = self._consume()
                content_els = self._content_to_omml(content_str)
                rad = _e(M + 'rad')
                radPr = _e(M + 'radPr')
                degHide = _e(M + 'degHide')
                degHide.set(M + 'val', '1')
                radPr.append(degHide)
                rad.append(radPr)
                e = _e(M + 'e')
                for el in content_els:
                    e.append(el)
                rad.append(e)
                return rad

        # Greek letters
        if cmd in self.GREEK_LETTERS:
            return omml_r(self.GREEK_LETTERS[cmd])

        # Big operators
        if cmd in self.OPERATORS:
            return omml_r(self.OPERATORS[cmd])

        # Functions
        if cmd in self.FUNCTIONS:
            r = _e(M + 'r')
            rPr = _e(M + 'rPr')
            sty = _e(M + 'sty')
            sty.set(M + 'val', 'p')
            rPr.append(sty)
            r.append(rPr)
            t = _e(M + 't')
            t.text = self.FUNCTIONS[cmd]
            r.append(t)
            return r

        # Symbols
        if cmd in self.SYMBOLS:
            return omml_r(self.SYMBOLS[cmd])

        # Text/font commands
        if cmd in ('mathrm', 'text', 'textrm', 'rm'):
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            # Wrap with roman style
            result = []
            for el in content_els:
                if el.tag == M + 'r':
                    # Add roman rPr
                    rPr = el.find(M + 'rPr')
                    if rPr is None:
                        rPr = _e(M + 'rPr')
                        el.insert(0, rPr)
                    sty = _e(M + 'sty')
                    sty.set(M + 'val', 'p')
                    rPr.append(sty)
                result.append(el)
            return result

        if cmd in ('mathbf', 'bf', 'boldsymbol', 'bm'):
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            result = []
            for el in content_els:
                if el.tag == M + 'r':
                    rPr = el.find(M + 'rPr')
                    if rPr is None:
                        rPr = _e(M + 'rPr')
                        el.insert(0, rPr)
                    sty = _e(M + 'sty')
                    sty.set(M + 'val', 'b')
                    rPr.append(sty)
                result.append(el)
            return result

        if cmd in ('mathcal', 'cal'):
            content = self._read_brace_group() or ''
            return omml_r(content)  # Simplified

        if cmd == 'mathit':
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            result = []
            for el in content_els:
                if el.tag == M + 'r':
                    rPr = el.find(M + 'rPr')
                    if rPr is None:
                        rPr = _e(M + 'rPr')
                        el.insert(0, rPr)
                    sty = _e(M + 'sty')
                    sty.set(M + 'val', 'i')
                    rPr.append(sty)
                result.append(el)
            return result

        # \left and \right - just skip these, the delimiters are handled as normal chars
        if cmd in ('left', 'right', 'big', 'bigg', 'Big', 'Bigg', 'bigl', 'bigr', 'biggl', 'biggr'):
            # Skip, the following delimiter will be parsed as normal
            return None

        # \overline, \underline, \bar
        if cmd in ('overline', 'bar'):
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            acc = _e(M + 'acc')
            accPr = _e(M + 'accPr')
            chr_el = _e(M + 'chr')
            chr_el.set(M + 'val', cmd == 'bar' and '\u0304' or '\u0305')
            accPr.append(chr_el)
            acc.append(accPr)
            e = _e(M + 'e')
            for el in content_els:
                e.append(el)
            acc.append(e)
            return acc

        # \hat, \vec, \tilde, \dot, \ddot
        if cmd in ('hat', 'vec', 'tilde', 'dot', 'ddot'):
            accent_map = {
                'hat': '\u0302', 'vec': '\u20d7', 'tilde': '\u0303',
                'dot': '\u0307', 'ddot': '\u0308'
            }
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            acc = _e(M + 'acc')
            accPr = _e(M + 'accPr')
            chr_el = _e(M + 'chr')
            chr_el.set(M + 'val', accent_map.get(cmd, '\u0302'))
            accPr.append(chr_el)
            acc.append(accPr)
            e = _e(M + 'e')
            for el in content_els:
                e.append(el)
            acc.append(e)
            return acc

        # \overrightarrow, \overleftarrow
        if cmd in ('overrightarrow', 'overleftarrow'):
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            acc = _e(M + 'acc')
            accPr = _e(M + 'accPr')
            chr_el = _e(M + 'chr')
            chr_el.set(M + 'val', cmd == 'overrightarrow' and '\u20d7' or '\u20d6')
            accPr.append(chr_el)
            acc.append(accPr)
            e = _e(M + 'e')
            for el in content_els:
                e.append(el)
            acc.append(e)
            return acc

        # \widehat, \widetilde
        if cmd in ('widehat', 'widetilde'):
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            acc = _e(M + 'acc')
            accPr = _e(M + 'accPr')
            chr_el = _e(M + 'chr')
            chr_el.set(M + 'val', cmd == 'widehat' and '\u0302' or '\u0303')
            accPr.append(chr_el)
            acc.append(accPr)
            e = _e(M + 'e')
            for el in content_els:
                e.append(el)
            acc.append(e)
            return acc

        # \not - negation
        if cmd == 'not':
            if not self._at_end():
                ch = self._consume()
                return omml_r(ch + '\u0338')  # combining long solidus
            return None

        # \quad, \qquad, \, \: \; spacing
        if cmd == 'quad':
            return omml_r('\u2003')
        if cmd == 'qquad':
            return omml_r('\u2003\u2003')

        # \, \: \; \! spacing
        if cmd == ',':
            return omml_r('\u2009')
        if cmd == ':':
            return omml_r('\u2005')
        if cmd == ';':
            return omml_r('\u2005')
        if cmd == '!':
            return omml_r('\u200b')

        # \varpi, etc. - already handled in GREEK_LETTERS

        # \operatorname
        if cmd in ('operatorname', 'mathrm'):
            content = self._read_brace_group() or ''
            r = _e(M + 'r')
            rPr = _e(M + 'rPr')
            sty = _e(M + 'sty')
            sty.set(M + 'val', 'p')
            rPr.append(sty)
            r.append(rPr)
            t = _e(M + 't')
            t.text = content
            r.append(t)
            return r

        # \begin/\end - matrix environments
        if cmd == 'begin':
            env_name = self._read_brace_group() or ''
            return self._parse_matrix(env_name)

        if cmd == 'end':
            # Consume the env name
            self._read_brace_group()
            return None

        # \boxed
        if cmd == 'boxed':
            content = self._read_brace_group() or ''
            content_els = self._content_to_omml(content)
            borderBox = _e(M + 'borderBox')
            borderBoxPr = _e(M + 'borderBoxPr')
            borderBox.append(borderBoxPr)
            e = _e(M + 'e')
            for el in content_els:
                e.append(el)
            borderBox.append(e)
            return borderBox

        # \color - skip color command but keep content
        if cmd == 'color':
            # Skip the color spec (could be {red} or simple word)
            self._skip_whitespace()
            if not self._at_end() and self._peek() == '{':
                self._read_brace_group()
            else:
                # Read until next command or space
                while not self._at_end() and self._peek().isalpha():
                    self.pos += 1
            return None

        # Unknown command - try to render as text
        if cmd and len(cmd) > 1 and cmd.isalpha():
            return omml_r('\\' + cmd)  # fallback: show raw command
        if cmd and len(cmd) == 1:
            return omml_r(cmd)

        return None

    def _parse_matrix(self, env_name):
        """Parse matrix environment"""
        # Collect all rows
        rows = []
        current_row = []
        current_cell = []

        while not self._at_end():
            ch = self._peek()
            if ch == '\\':
                cmd = self._read_command()
                if cmd == 'end':
                    env = self._read_brace_group() or ''
                    if env == env_name:
                        # Finish current cell and row
                        if current_cell:
                            current_row.append(''.join(current_cell))
                        if current_row:
                            rows.append(current_row)
                        break
                    else:
                        current_cell.append('\\end{' + env + '}')
                elif cmd == '\\':
                    # Row separator
                    if current_cell:
                        current_row.append(''.join(current_cell))
                        current_cell = []
                    if current_row:
                        rows.append(current_row)
                        current_row = []
                elif cmd == '&':
                    # Cell separator
                    if current_cell:
                        current_row.append(''.join(current_cell))
                        current_cell = []
                else:
                    current_cell.append('\\' + cmd)
            elif ch == '&':
                self.pos += 1
                if current_cell:
                    current_row.append(''.join(current_cell))
                    current_cell = []
            else:
                current_cell.append(ch)
                self.pos += 1

        # Build OMML m:m matrix
        m = _e(M + 'm')
        mPr = _e(M + 'mPr')
        # Set base justification
        mcs = _e(M + 'mcs')
        for _ in range(len(rows[0]) if rows else 0):
            mc = _e(M + 'mc')
            mcPr = _e(M + 'mcPr')
            count = _e(M + 'count')
            count.set(M + 'val', '1')
            mcPr.append(count)
            mcJc = _e(M + 'mcJc')
            mcJc.set(M + 'val', 'center')
            mcPr.append(mcJc)
            mc.append(mcPr)
            mcs.append(mc)
        mPr.append(mcs)
        m.append(mPr)

        for row in rows:
            mr = _e(M + 'mr')
            for cell in row:
                e = _e(M + 'e')
                cell_els = self._content_to_omml(cell.strip())
                for el in cell_els:
                    e.append(el)
                mr.append(e)
            m.append(mr)

        # Wrap in delimiter if needed
        if env_name in ('pmatrix', 'bmatrix'):
            d = _e(M + 'd')
            dPr = _e(M + 'dPr')
            begChr = _e(M + 'begChr')
            endChr = _e(M + 'endChr')
            if env_name == 'pmatrix':
                begChr.set(M + 'val', '(')
                endChr.set(M + 'val', ')')
            else:
                begChr.set(M + 'val', '[')
                endChr.set(M + 'val', ']')
            dPr.append(begChr)
            dPr.append(endChr)
            d.append(dPr)
            e = _e(M + 'e')
            e.append(m)
            d.append(e)
            return d

        return m


def latex_to_omml(latex_str):
    """LaTeX → OMML 便捷函数"""
    parser = LatexToOmml()
    return parser.parse(latex_str)


# ─── 测试 ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    test_cases = [
        r'E=mc^2',
        r'U_{\mathrm{dBV}}=20\lg(U)',
        r'\frac{a}{b}',
        r'\sqrt{x}',
        r'\sqrt[3]{x}',
        r'\alpha+\beta=\gamma',
        r'\sum_{i=1}^{n}i',
        r'\int_0^1 f(x)dx',
        r'N=\frac{\omega}{\beta^2+\omega^2}',
        r'\mathcal{E}=\mathrm{j}\frac{30kIdz}{r}',
    ]

    for latex in test_cases:
        print(f'\nLaTeX: {latex}')
        omml = latex_to_omml(latex)
        xml_str = etree.tostring(omml, pretty_print=True, encoding='unicode')
        # Only show first 300 chars
        print(f'OMML: {xml_str[:300]}...' if len(xml_str) > 300 else f'OMML: {xml_str}')
