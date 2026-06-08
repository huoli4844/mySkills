"""formula_utils.py — 公式块状态机工具

共享逻辑：扫描 Markdown 行，使用状态机识别真实公式块（$$...$$），
跳过代码块（如 Mermaid）内的 $$。

被 template_assembler.py（质量检查）和 post_build_fix.py（自动修复）共用。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FormulaBlock:
    """公式块位置信息（行索引从 0 开始）"""

    start_line: int  # opening $$ 所在行
    end_line: int  # closing $$ 所在行


def find_formula_blocks(lines: list[str]) -> list[FormulaBlock]:
    """使用状态机扫描所有真实公式块（跳过代码块内的 $$）。

    Parameters
    ----------
    lines : list[str]
        Markdown 文本的行列表

    Returns
    -------
    list[FormulaBlock]
        按出现顺序排列的公式块列表
    """
    blocks: list[FormulaBlock] = []
    in_formula = False
    in_code_block = False
    start = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        # 跟踪代码块（```mermaid ... ```），内部 $$ 不视为公式
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped == "$$":
            if not in_formula:
                in_formula = True
                start = i
            else:
                in_formula = False
                blocks.append(FormulaBlock(start_line=start, end_line=i))
                start = -1

    return blocks


def has_citation_after(lines: list[str], end_line: int, window: int = 20) -> bool:
    """检查 end_line 之后是否有来源标注。

    Parameters
    ----------
    lines : list[str]
        Markdown 文本的行列表
    end_line : int
        closing $$ 的行索引
    window : int
        向后搜索的最大行数（默认 20）

    Returns
    -------
    bool
        是否找到来源标注
    """
    for j in range(end_line + 1, min(end_line + 1 + window, len(lines))):
        if "来源：" in lines[j] or "来源:" in lines[j]:
            return True
        nxt = lines[j].strip()
        # 遇到下一个 opening $$ 或非引用/非空内容行则停止
        if nxt == "$$":
            break
        if nxt and not nxt.startswith(">") and not nxt.startswith("$$"):
            break
    return False
