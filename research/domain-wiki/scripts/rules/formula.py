"""rules/formula.py — 公式/LaTeX 语法质量检查"""

import re

from log_utils import get_logger

log = get_logger(__name__)

__all__ = [
    "KNOWN_LATEX_CMDS",
    "check_formula_quality",
]

# ── 已知 LaTeX 命令白名单（非数学模式中的 \cmd 不报错） ──
KNOWN_LATEX_CMDS = {
    "frac", "sqrt", "sum", "int", "iint", "iiint", "oint", "prod", "coprod",
    "infty", "pi", "lambda", "mu", "omega", "Omega", "alpha", "beta", "gamma",
    "Gamma", "theta", "Theta", "phi", "Phi", "sigma", "Sigma", "delta", "Delta",
    "eta", "rho", "tau", "chi", "psi", "Psi", "zeta", "epsilon", "varepsilon",
    "approx", "geq", "leq", "neq", "equiv", "sim", "simeq", "cong", "propto",
    "times", "cdot", "div", "pm", "mp", "partial", "nabla", "hbar", "ell",
    "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow",
    "Leftrightarrow", "uparrow", "downarrow", "mapsto", "longrightarrow",
    "longleftarrow", "text",
    "mathrm", "mathbf", "mathit", "mathcal", "mathscr", "mathfrak", "mathbb",
    "log", "ln", "lg", "sin", "cos", "tan", "cot", "csc", "sec",
    "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "coth",
    "left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "bigm",
    "quad", "qquad", "hspace", "vspace", "hfill", "vfill",
    "ldots", "cdots", "vdots", "ddots",
    "begin", "end", "displaystyle", "textstyle", "scriptstyle",
    "hat", "tilde", "bar", "dot", "ddot", "vec", "overline", "underline",
    "widehat", "widetilde", "overset", "underset", "stackrel",
    "tag", "label", "ref", "eqref",
    "lim", "to",
}


def check_formula_quality(body, file_label):
    """检查 LaTeX 公式语法质量，返回 (FAIL列表, WARN列表)"""
    fails, warns = [], []

    # 检查 $$...$$ 块级公式
    dollar2_blocks = re.findall(r"\$\$(.*?)\$\$", body, re.DOTALL)
    for i, block in enumerate(dollar2_blocks):
        f = block.strip()
        if not f:
            fails.append(f"[{file_label}] 公式块#{i+1}: $$ 内容为空")
            continue

        if f.count("{") != f.count("}"):
            fails.append(f"[{file_label}] 公式块#{i+1}: 花括号不匹配")

        if re.search(r"\\frac\s*\{\s*\}\s*\{\s*\}", f):
            fails.append(f"[{file_label}] 公式块#{i+1}: 空 \\frac{{}}{{}}")

        left_cmds = re.findall(r"\\left\b(?!arrow|rightharpoon|harpoon)", f)
        right_cmds = re.findall(r"\\right\b(?!arrow|rightharpoon|harpoon)", f)
        if len(left_cmds) != len(right_cmds):
            fails.append(
                f"[{file_label}] 公式块#{i+1}: \\left({len(left_cmds)}) 与 \\right({len(right_cmds)}) 数量不匹配"
            )

        bad_text = re.findall(r"\\text(?!\{)[^a-zA-Z]", f)
        if bad_text:
            fails.append(f"[{file_label}] 公式块#{i+1}: \\text 后缺少花括号")

        cmds = set(re.findall(r"\\([a-zA-Z]+)", f))
        unknown = cmds - KNOWN_LATEX_CMDS
        unknown = {c for c in unknown if len(c) > 1}
        if unknown:
            warns.append(f"[{file_label}] 公式块#{i+1}: 未知命令 {sorted(unknown)[:5]}")

    # 检查 $...$ 行内公式
    dollar1_blocks = re.findall(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", body)
    for i, f in enumerate(dollar1_blocks):
        if f.count("{") != f.count("}"):
            fails.append(f"[{file_label}] 行内公式#{i+1}: 花括号不匹配 ({f[:40]}...)")

    # 检查连续的 `$$` 没有闭合（3个以上 $ 连写）
    dangling = re.findall(r"\${3,}", body)
    if dangling:
        warns.append(f"[{file_label}] 发现 {len(dangling)} 处 3+ 个连续 $ 符号")

    # ── LaTeX 双反斜杠检测（JSON/YAML 管道过度转义）──
    all_double = len(re.findall(r"\\\\([a-z]+)", body))
    if all_double > 0:
        samples = re.findall(r"\\\\([a-z]+)", body)[:5]
        warns.append(
            f"[{file_label}] LaTeX 转义异常: {all_double} 处双反斜杠命令 (如 {samples}), "
            f"可能来自 JSON/YAML 管道过度转义"
        )

    # ── $$ 块级公式格式检查（独占三行）──
    dollar2_blocks_inline = re.findall(
        r"(?<!\$)\$\$(?!\$)([^\n]*?[^\s\n])\$\$(?!\$)", body, re.MULTILINE
    )
    for i, content in enumerate(dollar2_blocks_inline):
        if content.strip():
            fails.append(
                f"[{file_label}] 公式块#{i+1}: $$ 未独占三行, "
                f"内容与 $$ 在同一行 ('{content.strip()[:40]}...')"
            )

    return fails, warns
