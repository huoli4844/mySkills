"""Tests for book_toc.py — extract_toc from minerU .md files."""

import sys
import json
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from book_toc import extract_toc


# Real book files for testing
BOOK_BASE = "/Users/huoli4844/Desktop/电磁兼容/处理后"

BOOK_PATHS = {
    "路宏敏": f"{BOOK_BASE}/工程电磁兼容第3版_路宏敏/优先级1-十二五规划教材_工程电磁兼容第3版_路宏敏.md",
    "张亮": f"{BOOK_BASE}/电磁兼容EMC技术及应用实例详解_张亮/优先级2-电磁兼容EMC技术及应用实例详解-张亮.md",
    "柯金良": f"{BOOK_BASE}/电磁兼容概论_柯金良/优先级3-电磁兼容概论-柯金良.md",
    "梁振光": f"{BOOK_BASE}/电磁兼容原理技术及应用第2版_梁振光/优先级4-十三五_电磁兼容原理技术及应用第2版_梁振光.md",
}


class TestExtractToc:
    """Test extract_toc() against real book data."""

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
        assert len(shield_ch["sections"]) >= 20, f"屏蔽章应有30+节, 实际{len(shield_ch['sections'])}"

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
        """每本书至少有一个章有子节"""
        for name, path in BOOK_PATHS.items():
            result = extract_toc(path)
            chapters_with_sections = [c for c in result["chapters"] if len(c["sections"]) > 0]
            assert len(chapters_with_sections) > 0, f"{name}: 所有章节无子节"

    def test_no_toc_entries_in_chapters(self):
        """章节不应包含页码（"…… 1"）格式的TOC条目"""
        for name, path in BOOK_PATHS.items():
            result = extract_toc(path)
            for ch in result["chapters"]:
                assert "…" not in ch["title"], f"{name} 第{ch['num']}章含TOC页码"
                for sec in ch["sections"]:
                    assert "…" not in sec["title"], f"{name} {sec['num']}含TOC页码"

    def test_no_noise_titles(self):
        """过滤噪声：CIP/前言/目录等不应出现在章节中"""
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


class TestExtractTocEdgeCases:
    """Edge cases and missing file handling."""

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
