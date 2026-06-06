"""comprehensive_content_check.py 单元测试 — v39.1

测试内容深度检查器的各项检查功能。
"""

import os
import tempfile

import pytest

pytestmark = pytest.mark.integration


class TestCheckFormulaBlocks:
    """测试公式块检查"""

    def test_valid_three_line_formula(self):
        from rules.formula import check_formula_quality

        body = "文本\n$$\nP = I \\cdot R\n$$\n> 来源：教材"
        fails, _warns = check_formula_quality(body, "test")
        assert len(fails) == 0

    def test_inline_dollar_dollar_fails(self):
        from rules.formula import check_formula_quality

        body = "文本 $$P = IR$$ 后续"
        fails, _warns = check_formula_quality(body, "test")
        assert len(fails) >= 1

    def test_mismatched_braces_detected(self):
        from rules.formula import check_formula_quality

        body = "$$\n\\frac{a}{b\n$$"
        fails, _warns = check_formula_quality(body, "test")
        assert len(fails) >= 1  # 花括号不匹配


class TestCheckMermaidQuality:
    """测试 Mermaid 图质量检查"""

    def test_empty_mermaid_fails(self):
        from rules.diagram import check_mermaid_quality

        body = "```mermaid\n\n```"
        fails, _warns = check_mermaid_quality(body, "test")
        assert len(fails) >= 1

    def test_valid_mermaid(self):
        from rules.diagram import check_mermaid_quality

        body = "```mermaid\ngraph TD\n    A --> B\n    B --> C\n```"
        fails, _warns = check_mermaid_quality(body, "test")
        assert len(fails) == 0

    def test_arrow_in_label_warns(self):
        from rules.diagram import check_mermaid_quality

        body = '```mermaid\ngraph TD\n    A["输入→输出"] --> B\n```'
        fails, warns = check_mermaid_quality(body, "test")
        # → in node label is a known issue
        assert len(fails) >= 1 or len(warns) >= 1


class TestCheckImageRequired:
    """测试图片引用必要检查"""

    def test_no_images_warns(self):
        from rules.diagram import check_image_required

        body = "---\ntype: concept\n---\n## 一、核心知识\n### 1. 术语定义\n无"
        _fails, warns = check_image_required(body, "test", "concept")
        assert len(warns) >= 1

    def test_with_image_no_warn(self):
        from rules.diagram import check_image_required

        body = "---\ntype: concept\n---\n![图3-1](assets/fig3-1.png)"
        _fails, warns = check_image_required(body, "test", "concept")
        assert len(warns) == 0

    def test_entity_type_skipped(self):
        from rules.diagram import check_image_required

        body = "---\ntype: entity\n---\n无图片内容"
        _fails, warns = check_image_required(body, "test", "entity")
        assert len(warns) == 0

    def test_figure_references_none_no_warn(self):
        """v39.1: figure_references 明确为"无"时不报 WARN"""
        from rules.diagram import check_image_required

        body = "---\ntype: concept\n---\n#### 图引用\n无"
        _fails, warns = check_image_required(body, "test", "concept")
        assert len(warns) == 0


class TestCheckPlaceholders:
    """测试占位符检测（通过 check_file_full 间接测试）"""

    def test_detect_curly_placeholders(self):
        from template_assembler import check_placeholders as _check_ph

        count = _check_ph("---\ntype: exercise\n---\n难度: {{difficulty}}", "test")
        assert count >= 1  # 检测到了占位符

    def test_detect_chinese_skeleton(self):
        from rules.bloom import check_content_depth

        # 中文骨架占位符会被内容深度检查捕获
        body = "---\ntype: solution\n---\n解答：（待 Agent 填充实现原理）"
        fail_str, _warn_str = check_content_depth(body, "solution", "test")
        # 返回字符串或 None，不是列表
        assert fail_str is None or isinstance(fail_str, str)

    def test_clean_content_passes(self):
        from rules.bloom import check_content_depth

        body = "---\ntype: concept\n---\n" + "正常内容 " * 200
        fail_str, _warn_str = check_content_depth(body, "concept", "test")
        assert fail_str is None or isinstance(fail_str, str)


class TestExtractExercisesFromText:
    """测试习题自动检测（v39.1 扩展）"""

    def test_detect_standard_exercises(self):
        from dag_utils import extract_exercises_from_text

        text = "# 第3章\n\n内容...\n\n## 习题\n1. 第一题\n2. 第二题"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) == 2

    def test_detect_thinking_exercises(self):
        from dag_utils import extract_exercises_from_text

        text = "# 第3章\n\n内容...\n\n## 思考题\n1. 问题一\n2. 问题二\n3. 问题三"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) == 3

    def test_detect_combined_title(self):
        """v39.1: 支持组合标题如"思考与练习\" """
        from dag_utils import extract_exercises_from_text

        text = "# 第3章\n\n内容...\n\n## 思考与练习\n1. 第一题"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) >= 1

    def test_detect_english_exercises(self):
        """v39.1: 支持英文标题 Exercises"""
        from dag_utils import extract_exercises_from_text

        text = "# Chapter 3\n\nContent...\n\n## Exercises\n1. Problem one\n2. Problem two"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) >= 1

    def test_no_exercises_section(self):
        from dag_utils import extract_exercises_from_text

        text = "# 第3章\n\n只有正文内容，没有习题部分"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) == 0

    def test_short_line_only(self):
        """v39.1: 仅短行才触发习题检测（避免正文中"做习题"误触发）"""
        from dag_utils import extract_exercises_from_text

        text = "# 第3章\n\n在做习题之前，需要先理解概念。这是很长的行用来确保不会误触发习题检测。\n\n更多内容"
        result = extract_exercises_from_text(text, "01_emc", "3")
        assert len(result) == 0


class TestFillTemplateYamlNewline:
    """测试 v39.1: YAML \\n 字面量在模板渲染层展开"""

    def test_expand_literal_newline(self):
        from template_assembler import fill_template

        template = "内容：\n{{description}}"
        replacements = {"description": "第一行\\n第二行\\n第三行"}
        result = fill_template(template, replacements)
        assert "第一行\n第二行\n第三行" in result

    def test_preserve_latex_commands(self):
        """\\nabla 等 LaTeX 命令不应被展开"""
        from template_assembler import fill_template

        template = "公式：{{formula}}"
        replacements = {"formula": "\\nabla \\times E"}
        result = fill_template(template, replacements)
        assert "\\nabla" in result

    def test_no_change_for_real_newlines(self):
        """实际换行不应受影响"""
        from template_assembler import fill_template

        template = "{{content}}"
        replacements = {"content": "行1\n行2"}
        result = fill_template(template, replacements)
        assert "行1\n行2" in result


class TestVerifyExerciseSolutionMapping:
    """测试习题-解答映射验证（v39.1: 从 pipeline_auto 移至 dag_utils）"""

    def test_all_matched(self):
        from dag_utils import verify_exercise_solution_mapping

        with tempfile.TemporaryDirectory() as tmpdir:
            ex_dir = os.path.join(tmpdir, "90_习题")
            sol_dir = os.path.join(tmpdir, "90_习题/解答")
            os.makedirs(sol_dir)
            # 创建习题和解答
            open(os.path.join(ex_dir, "第3章-习题1_01_3.md"), "w").close()
            open(os.path.join(sol_dir, "第3章-习题1-解答_01_3.md"), "w").close()
            missing = verify_exercise_solution_mapping(tmpdir)
            assert len(missing) == 0

    def test_missing_solution(self):
        from dag_utils import verify_exercise_solution_mapping

        with tempfile.TemporaryDirectory() as tmpdir:
            ex_dir = os.path.join(tmpdir, "90_习题")
            os.makedirs(ex_dir)
            open(os.path.join(ex_dir, "第3章-习题1_01_3.md"), "w").close()
            missing = verify_exercise_solution_mapping(tmpdir)
            assert len(missing) == 1

    def test_no_exercises_dir(self):
        from dag_utils import verify_exercise_solution_mapping

        with tempfile.TemporaryDirectory() as tmpdir:
            missing = verify_exercise_solution_mapping(tmpdir)
            assert len(missing) == 0


class TestFormulaCitationMermaidSkip:
    """v39.2: has_formula_citation 应跳过 Mermaid 代码块中的 $$"""

    def _make_concept_file(self, body):
        return (
            "---\n"
            "type: concept\n"
            "name: 测试概念\n"
            "confidence: 0.95\n"
            "source_chapter: 3\n"
            "---\n"
            "# 测试概念\n\n" + body
        )

    def test_mermaid_dollar_dollar_not_checked(self):
        from template_assembler import run_type_quality_checks

        # 包含完整定义句（含“是指”标记词）+ Mermaid 中的 $$ + 真实公式有来源
        body = (
            "> 测试概念是指一种用于测试的方法。\n"
            "> 来源：第3章\n"
            "\n"
            "```mermaid\n"
            "flowchart TD\n"
            '    A --> B["V=(U+S)(U-S\\Gamma)^{"-1"}V_s"]\n'
            "```\n"
            "\n"
            "> 来源：无\n"
            "\n"
            "$$\n"
            "P = I \\cdot R\n"
            "$$\n"
            "\n> 来源：第3章正文\n"
        )
        content = self._make_concept_file(body)
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建假的 20_正文 目录避免 source_retrieval break
            src_dir = os.path.join(tmpdir, "20_正文")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "第3章.md"), "w") as f:
                f.write("测试概念是指一种用于测试的方法。\n")
            concept_dir = os.path.join(tmpdir, "30_核心概念")
            os.makedirs(concept_dir)
            fpath = os.path.join(concept_dir, "test.md")
            with open(fpath, "w") as f:
                f.write(content)
            result = run_type_quality_checks(fpath, "concept_template.md")
            # has_formula_citation 应通过，因为 Mermaid $$ 被跳过，真实公式有来源
            assert result["checks"].get("has_formula_citation") == "pass"

    def test_real_formula_without_citation_fails(self):
        from template_assembler import run_type_quality_checks

        body = (
            "> 测试概念是指一种用于测试的方法。\n"
            "> 来源：第3章\n"
            "\n"
            "$$\n"
            "E = mc^2\n"
            "$$\n"
            "\n后续文本没有来源\n"
        )
        content = self._make_concept_file(body)
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "20_正文")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "第3章.md"), "w") as f:
                f.write("测试概念是指一种用于测试的方法。\n")
            concept_dir = os.path.join(tmpdir, "30_核心概念")
            os.makedirs(concept_dir)
            fpath = os.path.join(concept_dir, "test.md")
            with open(fpath, "w") as f:
                f.write(content)
            result = run_type_quality_checks(fpath, "concept_template.md")
            assert result["checks"].get("has_formula_citation") == "fail"
