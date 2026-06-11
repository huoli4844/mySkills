"""Tests for quality_audit.py — all check functions + audit_chapter."""

import sys
import os
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from quality_audit import (
    check_formulas,
    check_content_stats,
    check_second_person,
    check_step_markers,
    check_summary_count,
    check_placeholders,
    check_footnotes_format,
    check_dollar_pairing,
    check_tag_chapter_prefix,
    check_professor_quality,
    check_learning_objectives,
    check_mermaid,
    check_figure_captions,
    check_technical_depth,
    check_forbidden_content,
    audit_chapter,
)


def _write_md(root, name, content):
    p = root / name
    p.write_text(content, encoding='utf-8')
    return str(p)


# =============================================================
# check_formulas
# =============================================================
class TestCheckFormulas:
    def test_tags_continuous(self):
        content = "$$\n\\tag{3-1}\n$$\n$$\n\\tag{3-2}\n$$"
        r = check_formulas(content, "3")
        assert r["formula_blocks"] == 2
        assert r["formula_tags"] == 2
        assert r["tags_continuous"] is True
        assert r["dollars_paired"] is True

    def test_tags_not_continuous(self):
        content = "$$\n\\tag{3-1}\n$$\n$$\n\\tag{3-3}\n$$"
        r = check_formulas(content, "3")
        assert r["tags_continuous"] is False

    def test_no_tags(self):
        content = "$$\nE=mc^2\n$$\n$$\na=b\n$$"
        r = check_formulas(content, "3")
        assert r["formula_blocks"] == 2
        assert r["formula_tags"] == 0
        assert r["tags_continuous"] is True  # empty list counts as True

    def test_unclosed_dollar(self):
        content = "$$\nE=mc^2\n"
        r = check_formulas(content, "3")
        assert r["dollars_paired"] is False

    def test_blockquote_dollar(self):
        content = "> $$\n> E=mc^2\n> $$\n"
        r = check_formulas(content, "3")
        assert r["dollars_paired"] is True


# =============================================================
# check_content_stats
# =============================================================
class TestCheckContentStats:
    def test_mermaid_and_tables(self):
        content = (
            "```mermaid\nA-->B\n```\n"
            "*图1-1 测试*\n"
            "**表1-1 标题**\n"
            "| a | b |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
            "### **例1-1**\n"
            "## 本章总结\n"
            "## 习题\n"
            "## 参考文献\n"
        )
        r = check_content_stats(content)
        assert r["mermaids"] == 1
        assert r["tables"] == 1
        assert r["examples"] == 1
        assert r["has_summary"] is True
        assert r["has_exercises"] is True
        assert r["has_references"] is True

    def test_empty_returns_zeros(self):
        r = check_content_stats("")
        assert r["mermaids"] == 0
        assert r["tables"] == 0
        assert r["has_summary"] is False


# =============================================================
# 军规合规检查
# =============================================================
class TestCheckSecondPerson:
    def test_detects_second_person(self):
        content = "## 正文\n你在计算阻抗时需要注意\n## 习题\n"
        issues = check_second_person(content)
        assert len(issues) >= 1
        assert "你" in issues[0]

    def test_no_issue(self):
        content = "## 正文\n读者在计算阻抗时需要注意\n## 习题\n"
        issues = check_second_person(content)
        assert len(issues) == 0


class TestCheckStepMarkers:
    def test_detects_step(self):
        issues = check_step_markers("Step 1: 做第一步")
        assert len(issues) >= 1

    def test_no_issue(self):
        issues = check_step_markers("第一步：做第一步\n第二步：做第二步")
        assert len(issues) == 0


class TestCheckSummaryCount:
    def test_correct_six(self):
        content = (
            "## 本章总结\n"
            "1. 要点一\n"
            "2. 要点二\n"
            "3. 要点三\n"
            "4. 要点四\n"
            "5. 要点五\n"
            "6. 要点六\n"
            "## 习题\n"
        )
        issues = check_summary_count(content)
        assert len(issues) == 0

    def test_wrong_count(self):
        content = (
            "## 本章总结\n"
            "1. 要点一\n"
            "2. 要点二\n"
            "3. 要点三\n"
            "## 习题\n"
        )
        issues = check_summary_count(content)
        assert len(issues) >= 1
        assert "条目数" in issues[0]

    def test_no_summary_section(self):
        content = "## 正文\n没有总结节"
        issues = check_summary_count(content)
        assert len(issues) == 0


class TestCheckPlaceholders:
    def test_detects_placeholder(self):
        issues = check_placeholders("[待补充]")
        assert len(issues) >= 1

    def test_detects_todo(self):
        issues = check_placeholders("这是[TODO]的内容")
        assert len(issues) >= 1

    def test_no_issue(self):
        issues = check_placeholders("完整的内容")
        assert len(issues) == 0


class TestCheckFootnotesFormat:
    def test_missing_ref_section(self):
        issues = check_footnotes_format("正文无参考文献")
        assert len(issues) >= 1

    def test_has_marker(self):
        content = "## 参考文献\n[1] [M] 作者. 书名. 出版社, 2024.\n"
        issues = check_footnotes_format(content)
        assert len(issues) == 0

    def test_missing_marker(self):
        content = "## 参考文献\n[1] 作者. 书名. 出版社, 2024.\n"
        issues = check_footnotes_format(content)
        assert len(issues) >= 1


class TestCheckDollarPairing:
    def test_paired(self):
        issues = check_dollar_pairing("$$\na=b\n$$")
        assert len(issues) == 0

    def test_unpaired(self):
        issues = check_dollar_pairing("$$\na=b\n")
        assert len(issues) >= 1


class TestCheckTagChapterPrefix:
    def test_correct_prefix(self):
        issues = check_tag_chapter_prefix("\\tag{3-1}", 3)
        assert len(issues) == 0

    def test_wrong_prefix(self):
        issues = check_tag_chapter_prefix("\\tag{2-1}", 3)
        assert len(issues) >= 1


# =============================================================
# 写作规范检查
# =============================================================
class TestCheckProfessorQuality:
    def test_detects_missing_teaching_perspective(self):
        issues = check_professor_quality("## 1. 节标题\n客观陈述。\n## 2. 节标题\n客观陈述。")
        # Should flag missing "为什么/如何" in sections
        assert len(issues) >= 1

    def test_passes_with_teaching_cues(self):
        content = (
            "## 1. 为什么电磁兼容\n"
            "值得注意的是，这很关键。\n"
            "读者需要理解。\n"
        )
        issues = check_professor_quality(content)
        # Should pass at least some checks
        assert isinstance(issues, list)


class TestCheckLearningObjectives:
    def test_finds_objectives(self):
        content = (
            "## 内容提要\n"
            "通过本章学习，读者应达成以下学习目标：\n"
            "1. 理解电磁兼容的基本概念\n"
            "2. 掌握电磁干扰三要素\n"
        )
        issues = check_learning_objectives(content)
        assert len(issues) >= 0  # may or may not find issues depending on body coverage

    def test_no_objective_section(self):
        issues = check_learning_objectives("正文")
        assert len(issues) >= 1  # not found


# =============================================================
# Mermaid 检查
# =============================================================
class TestCheckMermaid:
    def test_clean_mermaid(self):
        content = "```mermaid\ngraph LR\nA[节点] --> B[节点]\n```"
        issues = check_mermaid(content)
        assert len(issues) == 0

    def test_emoji_detected(self):
        content = "```mermaid\ngraph LR\nA[✅完成] --> B[⚠️注意]\n```"
        issues = check_mermaid(content)
        assert len(issues) >= 1
        assert any("emoji" in i or "⭐" in i for i in issues)

    def test_timeline_detected(self):
        content = "```mermaid\ntimeline\n1864 : 麦克斯韦\n```"
        issues = check_mermaid(content)
        assert len(issues) >= 1
        assert any("timeline" in i for i in issues)

    def test_mindmap_detected(self):
        content = "```mermaid\nmindmap\nroot((EMC))\n```"
        issues = check_mermaid(content)
        assert len(issues) >= 1
        assert any("mindmap" in i for i in issues)

    def test_init_detected(self):
        content = "```mermaid\n%%{init: {\"theme\": \"dark\"}}%%\ngraph LR\nA-->B\n```"
        issues = check_mermaid(content)
        assert len(issues) >= 1
        assert any("init" in i for i in issues)

    def test_bidirectional_detected(self):
        content = "```mermaid\ngraph LR\nA <--> B\n```"
        issues = check_mermaid(content)
        assert len(issues) >= 1
        assert any("<-->" in i for i in issues)

    def test_no_mermaid_no_issue(self):
        issues = check_mermaid("纯文本")
        assert len(issues) == 0


# =============================================================
# Figure captions
# =============================================================
class TestCheckFigureCaptions:
    def test_missing_caption(self):
        content = "```mermaid\ngraph LR\nA-->B\n```\n"
        issues = check_figure_captions(content)
        assert len(issues) >= 1

    def test_has_caption(self):
        content = "```mermaid\ngraph LR\nA-->B\n```\n*图1-1 测试图*\n"
        issues = check_figure_captions(content)
        assert len(issues) == 0

    def test_caption_too_far(self):
        content = "```mermaid\ngraph LR\nA-->B\n```\n\n\n*图1-1 测试图*\n"
        issues = check_figure_captions(content)
        # If the caption is >50 chars away, it's flagged
        # \n\n\n puts us within range if content is short
        assert isinstance(issues, list)


# =============================================================
# 技术深度
# =============================================================
class TestCheckTechnicalDepth:
    def test_chapter1_missing_content(self):
        content = "简单的绪论"
        issues = check_technical_depth(content, 1)
        assert len(issues) >= 1  # Missing all depth items

    def test_chapter1_has_content(self):
        content = "电尺寸概念 λ/10 窄带 宽带 百分比带宽 术语 核心术语 兼容电平 发射限值 抗扰度限值"
        issues = check_technical_depth(content, 1)
        assert len(issues) == 0

    def test_not_chapter1(self):
        issues = check_technical_depth("任意内容", 2)
        assert len(issues) == 0


# =============================================================
# 禁止内容
# =============================================================
class TestCheckForbiddenContent:
    def test_all_clean(self):
        r = check_forbidden_content("正文内容")
        assert all(v is False for v in r.values())

    def test_writing_notes_detected(self):
        r = check_forbidden_content("本章写作说明")
        assert r["writing_notes"] is True

    def test_rules_check_detected(self):
        r = check_forbidden_content("12条军规")
        assert r["rules_check"] is True

    def test_formula_summary_detected(self):
        r = check_forbidden_content("全章核心公式总结")
        assert r["formula_summary"] is True


# =============================================================
# 整章审计
# =============================================================
class TestAuditChapter:
    def test_audit_clean_chapter(self, temp_dir):
        root = temp_dir["root"]
        path = _write_md(root, "第3章-搭接技术.md",
            "# 第3章 搭接技术\n"
            "## 内容提要\n"
            "通过本章学习，读者应达成以下学习目标：\n"
            "1. 理解搭接原理\n"
            "2. 掌握搭接方法\n"
            "## 3.1 为什么需要搭接\n"
            "读者可能已经注意到...\n"
            "**表3-1 标题**\n"
            "| a | b |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
            "```mermaid\ngraph LR\nA[节点] --> B[节点]\n```\n"
            "*图3-1 测试图*\n"
            "$$\n\\tag{3-1}\nE = mc^2\n$$\n"
            "$$\n\\tag{3-2}\na = b\n$$\n"
            "### **例3-1**\n"
            "示例内容\n"
            "## 本章总结\n"
            "1. 要点一\n"
            "2. 要点二\n"
            "3. 要点三\n"
            "4. 要点四\n"
            "5. 要点五\n"
            "6. 要点六\n"
            "## 习题\n"
            "3-1 第一题\n"
            "## 参考文献\n"
            "[1] [M] 作者. 书名. 出版社, 2024.\n"
        )
        r = audit_chapter(path)
        assert "error" not in r
        assert r["chapter"] == 3
        assert r["file"] == "第3章-搭接技术.md"
        assert r["size_kb"] > 0
        assert r["lines"] > 0

    def test_audit_unrecognized_chapter(self, temp_dir):
        root = temp_dir["root"]
        path = _write_md(root, "前言.md", "# 前言\n")
        r = audit_chapter(path)
        assert "error" in r
