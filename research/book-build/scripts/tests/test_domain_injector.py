"""Tests for domain_injector.py."""

import sys
import os
import json
import tempfile
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from domain_injector import build_variable_map, inject_variables


def make_ctx(**overrides):
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
        ctx = make_ctx()
        vm = build_variable_map(ctx)
        assert vm["domain_standards"] == "IEC、CISPR、GB标准"
        assert vm["domain_name"] == "电磁兼容"

    def test_empty_standards(self):
        ctx = make_ctx(standards_family=[])
        vm = build_variable_map(ctx)
        assert "行业" in vm["domain_standards"]

    def test_fallback_domain_name(self):
        vm = build_variable_map({})
        assert "本领域" in vm["domain_name"]

    def test_top_terms_included(self):
        ctx = make_ctx()
        vm = build_variable_map(ctx)
        # top 3 terms joined
        assert "屏蔽" in vm["domain_key_terms"]
        assert "滤波" in vm["domain_key_terms"]


class TestInjectVariables:
    def test_replaces_simple(self):
        vm = build_variable_map(make_ctx())
        result = inject_variables("Hello {{domain_name}}!", vm)
        assert result == "Hello 电磁兼容!"

    def test_unknown_var_kept(self):
        vm = build_variable_map(make_ctx())
        result = inject_variables("Hello {{unknown_var}}!", vm)
        assert "{{unknown_var}}" in result

    def test_no_vars_unchanged(self):
        vm = build_variable_map(make_ctx())
        result = inject_variables("Plain text without variables", vm)
        assert result == "Plain text without variables"

    def test_multiple_vars(self):
        vm = build_variable_map(make_ctx())
        result = inject_variables("{{domain_name}} uses {{domain_standards}}", vm)
        assert "电磁兼容" in result
        assert "IEC" in result
        assert "CISPR" in result

    def test_empty_ctx_uses_defaults(self):
        vm = build_variable_map({})
        result = inject_variables("{{domain_standards}}", vm)
        assert "行业" in result
