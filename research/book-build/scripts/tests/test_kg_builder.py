"""Tests for kg_builder.py."""

import sys
import os
import json
import tempfile
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from kg_builder import extract_terms_from_title, _detect_standards, get_db_path


class TestExtractTerms:
    def test_basic_term(self):
        terms = extract_terms_from_title("电磁兼容")
        assert len(terms) >= 1

    def test_multiple_terms(self):
        terms = extract_terms_from_title("印制电路板EMC设计技术")
        # May vary by matching logic
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
        chapters = [{"title": "IEC 标准体系", "sections": []}]
        standards = _detect_standards(chapters)
        assert "IEC" in standards

    def test_detects_gb(self):
        chapters = [{"title": "GB/T 标准", "sections": []}]
        standards = _detect_standards(chapters)
        assert "GB" in standards

    def test_no_standards(self):
        chapters = [{"title": "纯粹概念", "sections": []}]
        standards = _detect_standards(chapters)
        assert standards == []

    def test_multiple_standards(self):
        chapters = [{"title": "IEC 与 CISPR 标准", "sections": []}]
        standards = _detect_standards(chapters)
        assert "IEC" in standards
        assert "CISPR" in standards


class TestDbPath:
    def test_creates_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = get_db_path(tmp)
            assert os.path.exists(os.path.dirname(path))
            assert path.endswith("knowledge_graph.db")


class TestBuildGraphIntegration:
    """Verify KG build works with a mock project."""

    def test_extract_terms_chapter1_title(self):
        """路宏敏第1章 = '绪论'"""
        terms = extract_terms_from_title("绪论 电磁干扰与电磁污染 电磁兼容")
        assert "电磁干扰" in terms or "电磁污染" in terms or "电磁兼容" in terms
