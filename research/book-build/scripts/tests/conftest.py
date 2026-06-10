"""pytest conftest — shared fixtures for book-build smoke tests."""

import pytest
import os
import shutil
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory with test .md files for smoke testing.

    Provides a dict::
        - root: Path to temp dir
        - paths: {name: Path} for each created file
        - file_contents: {name: str} for each file's content
    """
    with tempfile.TemporaryDirectory(prefix="book_build_test_") as tmpdir:
        root = Path(tmpdir)

        # ── renumber.py fixtures ──
        # A chapter file with formulas (no existing tags)
        ch3 = root / "第3章-搭接技术.md"
        ch3.write_text(
            "## 3.1 搭接概述\n\n"
            "根据公式：\n"
            "$$\n"
            "Z = R + j\\omega L\n"
            "$$\n\n"
            "代入可得：\n"
            "$$\n"
            "I = \\frac{V}{Z}\n"
            "$$\n"
        )

        # A file with orphan tags (tags outside $$ blocks)
        ch4 = root / "第4章-屏蔽.md"
        ch4.write_text(
            "## 4.1 屏蔽原理\n\n"
            "$$\n"
            "E = \\frac{Q}{4\\pi\\epsilon r^2}\n"
            "$$\n"
            "\\tag{4-1}\n"
            "$$\n"
            "B = \\mu H\n"
            "$$\n"
        )

        # A file with inline $$ formula
        ch5 = root / "第5章-滤波.md"
        ch5.write_text(
            "## 5.1 滤波电路\n\n"
            "传递函数为 $$H(s) = \\frac{1}{RCs+1}$$ 即低通。\n\n"
            "截止频率为 $$f_c = \\frac{1}{2\\pi RC}$$\n"
        )

        # An empty file
        empty = root / "第6章-空.md"
        empty.write_text("")

        # A file with no $$ formulas at all
        plain = root / "第7章-说明.md"
        plain.write_text("# 第7章 说明\n\n本章无公式，仅有文字说明。\n")

        # ── post_generation_check.py fixtures ──
        # Mermaid with missing caption
        mermaid_no_cap = root / "第8章-mermaid-no-cap.md"
        mermaid_no_cap.write_text(
            "## 8.1 流程图\n\n"
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n\n"
            "## 下一个标题\n"
        )

        # Mermaid with caption present
        mermaid_with_cap = root / "第9章-mermaid-cap.md"
        mermaid_with_cap.write_text(
            "## 9.1 流程图\n\n"
            "```mermaid\n"
            "flowchart LR\n"
            "  A-->B\n"
            "```\n\n"
            "*图9-1：流程图描述*\n\n"
            "后续文字\n"
        )

        # Bare formulas (no derivation hints) - enough to trigger 3 consecutive
        bare_formulas = root / "第10章-裸公式.md"
        bare_formulas.write_text(
            "## 10.1 公式堆叠\n\n"
            "$$\n"
            "a = b\n"
            "$$\n"
            "$$\n"
            "c = d\n"
            "$$\n"
            "$$\n"
            "e = f\n"
            "$$\n"
        )

        # Formulas with derivation hints (should NOT trigger depth issue)
        derived_formulas = root / "第11章-有推导.md"
        derived_formulas.write_text(
            "## 11.1 推导\n\n"
            "根据原理可得：\n"
            "$$\n"
            "F = ma\n"
            "$$\n\n"
            "代入上式：\n"
            "$$\n"
            "a = F/m\n"
            "$$\n\n"
            "由式(1)可得：\n"
            "$$\n"
            "v = at\n"
            "$$\n"
        )

        # Formulas missing tags
        missing_tags = root / "第12章-缺编号.md"
        missing_tags.write_text(
            "## 12.1 缺编号公式\n\n"
            "根据分析：\n"
            "$$\n"
            "\\tag{12-1}\n"
            "E = mc^2\n"
            "$$\n\n"
            "则有：\n"
            "$$\n"
            "p = mv  \\\\tag{12-2}\n"
            "$$\n\n"
            "但此处缺编号：\n"
            "$$\n"
            "F = G\\frac{m_1 m_2}{r^2}\n"
            "$$\n"
        )

        # Single-line $$inline$$ formula
        inline_formulas = root / "第13章-内联.md"
        inline_formulas.write_text(
            "## 13.1 内联公式\n\n"
            "根据 $$\\sigma = \\sqrt{\\frac{1}{N}\\sum(x_i-\\mu)^2}$$ 计算标准差。\n"
        )

        # ── renumber_cross_file.py fixtures ──
        cross_main = root / "第8章-正文.md"
        cross_main.write_text(
            "## 正文\n\n"
            "$$\n"
            "\\tag{8-1}\n"
            "a = b\n"
            "$$\n"
            "*图8-1：示例图*\n"
            "**例8-1：示例例题**\n"
            "**表8-1：示例表**\n"
        )

        cross_case = root / "案例8-案例1.md"
        cross_case.write_text(
            "## 案例\n\n"
            "$$\n"
            "\\tag{8-2}\n"
            "c = d\n"
            "$$\n"
            "*图8-2：案例图*\n"
        )

        cross_lab = root / "实验8_实验1.md"
        cross_lab.write_text(
            "## 实验\n\n"
            "$$\n"
            "\\tag{8-3}\n"
            "e = f\n"
            "$$\n"
            "**例8-2：实验例题**\n"
        )

        yield {
            "root": root,
            "paths": {
                "ch3": ch3,
                "ch4": ch4,
                "ch5": ch5,
                "empty": empty,
                "plain": plain,
                "mermaid_no_cap": mermaid_no_cap,
                "mermaid_with_cap": mermaid_with_cap,
                "bare_formulas": bare_formulas,
                "derived_formulas": derived_formulas,
                "missing_tags": missing_tags,
                "inline_formulas": inline_formulas,
                "cross_main": cross_main,
                "cross_case": cross_case,
                "cross_lab": cross_lab,
            },
            "file_contents": {
                "ch3": ch3.read_text(),
                "ch4": ch4.read_text(),
                "ch5": ch5.read_text(),
                "empty": empty.read_text(),
                "plain": plain.read_text(),
                "mermaid_no_cap": mermaid_no_cap.read_text(),
                "mermaid_with_cap": mermaid_with_cap.read_text(),
                "bare_formulas": bare_formulas.read_text(),
                "derived_formulas": derived_formulas.read_text(),
                "missing_tags": missing_tags.read_text(),
                "inline_formulas": inline_formulas.read_text(),
                "cross_main": cross_main.read_text(),
                "cross_case": cross_case.read_text(),
                "cross_lab": cross_lab.read_text(),
            },
        }


@pytest.fixture
def config_yaml_path():
    """Return the path to the real config.yaml for book_config tests."""
    # book_config.Config() resolves config relative to __file__
    # We test from scripts/tests/ which is two levels below the config yaml
    return str(
        Path(__file__).resolve().parent.parent.parent / "config.yaml"
    )
