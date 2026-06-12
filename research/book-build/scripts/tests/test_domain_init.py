"""Tests for domain_init.py — 合并 book_toc + kg_builder + domain_injector 测试。"""

import sys
import os
import json
import tempfile
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from domain_init import (
    extract_toc, extract_terms_from_title, _detect_standards,
    build_variable_map, inject_variables, is_noise,
)

# ============================================================
# 真实教材文件路径
# ============================================================
BOOK_BASE = "/Users/huoli4844/Desktop/电磁兼容/处理后"

BOOK_PATHS = {
    "路宏敏": f"{BOOK_BASE}/工程电磁兼容第3版_路宏敏/优先级1-十二五规划教材_工程电磁兼容第3版_路宏敏.md",
    "张亮": f"{BOOK_BASE}/电磁兼容EMC技术及应用实例详解_张亮/优先级2-电磁兼容EMC技术及应用实例详解-张亮.md",
    "柯金良": f"{BOOK_BASE}/电磁兼容概论_柯金良/优先级3-电磁兼容概论-柯金良.md",
    "梁振光": f"{BOOK_BASE}/电磁兼容原理技术及应用第2版_梁振光/优先级4-十三五_电磁兼容原理技术及应用第2版_梁振光.md",
}


# ============================================================
# SECTION 1 — TOC 提取测试
# ============================================================

class TestExtractToc:
    def test_luhongmin_detects_chapters(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        assert "error" not in result
        assert result["book_title"] == "工程电磁兼容"
        assert len(result["chapters"]) == 13
        assert result["chapters"][0]["num"] == 1
        assert result["chapters"][0]["title"] == "绪论"

    def test_luhongmin_section_count(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        chapters = result["chapters"]
        shield_ch = [c for c in chapters if "屏蔽" in c["title"]][0]
        assert len(shield_ch["sections"]) >= 20

    def test_zhangliang_detects_chapters(self):
        result = extract_toc(BOOK_PATHS["张亮"])
        assert "error" not in result
        assert len(result["chapters"]) >= 10

    def test_kejinliang_detects_chapters(self):
        result = extract_toc(BOOK_PATHS["柯金良"])
        assert "error" not in result
        assert result["book_title"] == "电磁兼容概论"
        assert len(result["chapters"]) >= 8

    def test_liangzhenguang_detects_chapters(self):
        result = extract_toc(BOOK_PATHS["梁振光"])
        assert "error" not in result
        assert len(result["chapters"]) >= 10

    def test_all_books_have_titles(self):
        for name, path in BOOK_PATHS.items():
            result = extract_toc(path)
            assert "error" not in result, f"{name}: {result.get('error')}"
            assert result["book_title"], f"{name}: 缺少书名"
            assert len(result["chapters"]) > 0, f"{name}: 无章节"

    def test_all_books_have_sections(self):
        for name, path in BOOK_PATHS.items():
            result = extract_toc(path)
            with_sections = [c for c in result["chapters"] if len(c["sections"]) > 0]
            assert len(with_sections) > 0, f"{name}: 所有章节无子节"

    def test_no_toc_entries_in_chapters(self):
        for name, path in BOOK_PATHS.items():
            result = extract_toc(path)
            for ch in result["chapters"]:
                assert "…" not in ch["title"], f"{name} 第{ch['num']}章含TOC页码"
                for sec in ch["sections"]:
                    assert "…" not in sec["title"], f"{name} {sec['num']}含TOC页码"

    def test_no_noise_titles(self):
        for path in BOOK_PATHS.values():
            result = extract_toc(path)
            for ch in result["chapters"]:
                assert "CIP" not in ch["title"]
                assert "前言" not in ch["title"]
                assert "目录" not in ch["title"]

    def test_json_serializable(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert len(parsed["chapters"]) == len(result["chapters"])

    def test_missing_file(self):
        result = extract_toc("/nonexistent/path.md")
        assert "error" in result

    def test_section_numbers_are_strings(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        for ch in result["chapters"]:
            for sec in ch["sections"]:
                assert isinstance(sec["num"], str)
                assert "." in sec["num"]

    def test_line_numbers_are_integers(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        for ch in result["chapters"]:
            assert isinstance(ch["line"], int)
            for sec in ch["sections"]:
                assert isinstance(sec["line"], int)

    def test_chapters_sequentially_ordered(self):
        result = extract_toc(BOOK_PATHS["路宏敏"])
        nums = [c["num"] for c in result["chapters"]]
        assert nums == sorted(nums), f"章节号不连续: {nums}"


# ============================================================
# SECTION 2 — 知识图谱测试
# ============================================================

class TestExtractTerms:
    def test_basic_term(self):
        terms = extract_terms_from_title("电磁兼容")
        assert len(terms) >= 1

    def test_multiple_terms(self):
        terms = extract_terms_from_title("印制电路板EMC设计技术")
        assert len(terms) >= 1

    def test_removes_punctuation(self):
        terms = extract_terms_from_title("接地（安全接地）")
        assert "接地" in terms

    def test_filters_stop_words(self):
        terms = extract_terms_from_title("主要概述")
        assert "主要" not in terms

    def test_empty_input(self):
        terms = extract_terms_from_title("")
        assert terms == []


class TestDetectStandards:
    def test_detects_iec(self):
        ch = [{"title": "IEC 标准体系", "sections": []}]
        assert "IEC" in _detect_standards(ch)

    def test_detects_gb(self):
        ch = [{"title": "GB/T 标准", "sections": []}]
        assert "GB" in _detect_standards(ch)

    def test_no_standards(self):
        ch = [{"title": "纯粹概念", "sections": []}]
        assert _detect_standards(ch) == []

    def test_multiple_standards(self):
        ch = [{"title": "IEC 与 CISPR 标准", "sections": []}]
        s = _detect_standards(ch)
        assert "IEC" in s
        assert "CISPR" in s


# ============================================================
# SECTION 3 — 领域注入测试
# ============================================================

def _make_ctx(**overrides):
    ctx = {
        "domain_name": "电磁兼容",
        "standards_family": ["IEC", "CISPR", "GB"],
        "top_terms": [
            {"term": "屏蔽", "frequency": 35},
            {"term": "滤波", "frequency": 28},
            {"term": "接地", "frequency": 22},
            {"term": "耦合", "frequency": 18},
        ],
    }
    ctx.update(overrides)
    return ctx


class TestBuildVariableMap:
    def test_builds_standards(self):
        vm = build_variable_map(_make_ctx())
        assert vm["domain_standards"] == "IEC、CISPR、GB标准"
        assert vm["domain_name"] == "电磁兼容"

    def test_empty_standards(self):
        vm = build_variable_map(_make_ctx(standards_family=[]))
        assert "行业" in vm["domain_standards"]

    def test_fallback_domain_name(self):
        vm = build_variable_map({})
        assert "本领域" in vm["domain_name"]

    def test_top_terms_included(self):
        vm = build_variable_map(_make_ctx())
        assert "屏蔽" in vm["domain_key_terms"]
        assert "滤波" in vm["domain_key_terms"]


class TestInjectVariables:
    def test_replaces_simple(self):
        vm = build_variable_map(_make_ctx())
        assert inject_variables("Hello {{domain_name}}!", vm) == "Hello 电磁兼容!"

    def test_unknown_var_kept(self):
        vm = build_variable_map(_make_ctx())
        result = inject_variables("Hello {{unknown_var}}!", vm)
        assert "{{unknown_var}}" in result

    def test_no_vars_unchanged(self):
        vm = build_variable_map(_make_ctx())
        assert inject_variables("Plain text", vm) == "Plain text"

    def test_multiple_vars(self):
        vm = build_variable_map(_make_ctx())
        result = inject_variables("{{domain_name}} uses {{domain_standards}}", vm)
        assert "电磁兼容" in result
        assert "IEC" in result
        assert "CISPR" in result

    def test_empty_ctx_uses_defaults(self):
        vm = build_variable_map({})
        result = inject_variables("{{domain_standards}}", vm)
        assert "行业" in result
