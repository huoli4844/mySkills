"""post_build_fix.py 单元测试 — v39.1

测试构建后自动修复管道的各项修复功能。
"""

import os
import tempfile

import pytest

pytestmark = pytest.mark.integration


class TestFixLatexDoubleBackslash:
    """测试 LaTeX 双反斜杠修复"""

    def test_fix_in_dollar_block(self):
        from post_build_fix import fix_latex_double_backslash

        content = "$$\n\\\\frac{1}{2}\n$$"
        result, count = fix_latex_double_backslash(content)
        assert count >= 1
        assert "\\frac{1}{2}" in result
        assert "\\\\frac" not in result

    def test_fix_in_inline_math(self):
        from post_build_fix import fix_latex_double_backslash

        content = "公式 \\(\\\\alpha + \\\\beta\\) 结束"
        result, count = fix_latex_double_backslash(content)
        assert count >= 1
        assert "\\alpha" in result

    def test_fix_outside_formula(self):
        """公式块外的 LaTeX 命令也应修复"""
        from post_build_fix import fix_latex_double_backslash

        content = "- 公式：\\\\frac{a}{b}"
        result, _count = fix_latex_double_backslash(content)
        assert "\\frac{a}{b}" in result

    def test_no_false_positive(self):
        """Markdown 换行 (\\) 不应被修复"""
        from post_build_fix import fix_latex_double_backslash

        content = "line1  \nline2"
        result, _count = fix_latex_double_backslash(content)
        assert result == content


class TestFixFormulaCitations:
    """测试公式来源标注"""

    def test_add_citation_after_formula(self):
        from post_build_fix import fix_formula_citations

        content = "文本\n$$\nP = I \\cdot R\n$$\n\n下一段"
        result, fixes = fix_formula_citations(content, "第3章正文")
        assert fixes == 1
        assert "> 来源：第3章正文" in result

    def test_skip_existing_citation(self):
        from post_build_fix import fix_formula_citations

        content = "$$\nP = I \\cdot R\n$$\n\n> 来源：教材"
        _result, fixes = fix_formula_citations(content)
        assert fixes == 0

    def test_multiple_formulas(self):
        from post_build_fix import fix_formula_citations

        content = "$$\nA\n$$\n\n$$\nB\n$$\n"
        _result, fixes = fix_formula_citations(content, "正文")
        assert fixes == 2


class TestFixDefinitionMarkers:
    """测试定义标记词修复"""

    def test_add_marker(self):
        from post_build_fix import fix_definition_markers

        content = "### 2. 精准释义\n> 概念A预测评估系统概念A特性的方法"
        result, fixed = fix_definition_markers(content)
        assert fixed
        assert "> 即，概念A预测" in result

    def test_skip_existing_marker(self):
        from post_build_fix import fix_definition_markers

        content = "### 2. 精准释义\n> 概念A预测是指评估系统概念A特性的方法"
        _result, fixed = fix_definition_markers(content)
        assert not fixed


class TestFillPlaceholders:
    """测试占位符填充"""

    def test_fill_named_placeholders(self):
        from post_build_fix import fill_placeholders

        content = "难度: {{difficulty}}, 类型: {{type_tag}}"
        result, changed = fill_placeholders(content)
        assert changed
        assert "难度: 中等" in result
        assert "类型: 习题" in result

    def test_fill_unknown_placeholders(self):
        from post_build_fix import fill_placeholders

        content = "未知: {{custom_field}}"
        result, changed = fill_placeholders(content)
        assert changed
        assert "未知: 无" in result

    def test_fill_chinese_skeleton(self):
        from post_build_fix import fill_placeholders

        content = "解答：（待Agent填充实现原理）"
        result, changed = fill_placeholders(content)
        assert changed
        assert "待后续AI Agent深度填充" in result

    def test_no_change_when_clean(self):
        from post_build_fix import fill_placeholders

        content = "正常内容，没有占位符"
        _result, changed = fill_placeholders(content)
        assert not changed


class TestRunPhaseAutoFix:
    """测试统一自动修复入口"""

    def test_fix_ke_files(self):
        from post_build_fix import run_phase_auto_fix

        with tempfile.TemporaryDirectory() as tmpdir:
            ke_dir = os.path.join(tmpdir, "30_知识要素")
            os.makedirs(ke_dir)
            # 创建一个有双反斜杠的 KE 文件
            with open(os.path.join(ke_dir, "test.md"), "w") as f:
                f.write("---\ntype: ke\n---\n$$\n\\\\frac{a}{b}\n$$\n")
            summary = run_phase_auto_fix(tmpdir, "ke", "3")
            assert summary["double_backslash"] >= 1
            assert summary["files_touched"] >= 1

    def test_fix_exercise_placeholders(self):
        from post_build_fix import run_phase_auto_fix

        with tempfile.TemporaryDirectory() as tmpdir:
            ex_dir = os.path.join(tmpdir, "90_习题")
            os.makedirs(ex_dir)
            with open(os.path.join(ex_dir, "test.md"), "w") as f:
                f.write("---\ntype: exercise\n---\n难度: {{difficulty}}\n")
            summary = run_phase_auto_fix(tmpdir, "exercises", "3")
            assert summary["placeholder"] >= 1

    def test_no_target_dir_returns_zero(self):
        from post_build_fix import run_phase_auto_fix

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = run_phase_auto_fix(tmpdir, "concepts", "1")
            assert summary["files_touched"] == 0


class TestFixFormulaCitationsMermaid:
    """v39.2: 公式来源标注应跳过 Mermaid 代码块中的 $$"""

    def test_skip_mermaid_dollar_dollar(self):
        from post_build_fix import fix_formula_citations

        content = (
            "文本\n"
            "```mermaid\n"
            "flowchart TD\n"
            '    A --> B["V=(U+S)(U-S\\Gamma)^{"-1"}V_s"]\n'
            "```\n"
            "\n"
            "$$\n"
            "P = I \\cdot R\n"
            "$$\n"
            "\n> 来源：正文"
        )
        _result, fixes = fix_formula_citations(content, "正文")
        # Mermaid 块内的 $$ 不应触发来源添加，只有真实公式块需要
        assert fixes == 0  # 真实公式已有来源

    def test_real_formula_still_gets_citation(self):
        from post_build_fix import fix_formula_citations

        content = "```mermaid\n" '    B --> D["公式$$"]\n' "```\n" "\n" "$$\n" "E = mc^2\n" "$$\n" "\n后续文本"
        result, fixes = fix_formula_citations(content, "第3章")
        assert fixes == 1
        assert "> 来源：第3章" in result
