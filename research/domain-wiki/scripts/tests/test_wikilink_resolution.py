"""Unit tests for kb_graph.py wikilink resolution and path normalization logic.

Tests the two critical functions that caused the 228 dead_link bug:
1. _full_target() — path prefix normalization
2. _process_file() — wikilink → node_id resolution (short-name lookup + path stripping)

v44.3: fixture .md 文件由 conftest.py _build_fixture_wiki() 动态生成，
不再依赖磁盘文件。目录名与 kb_graph._type_dir_map 对齐。
"""

import os

import pytest
from conftest import _KGraphForTest
from kb_graph import KGraph

pytestmark = pytest.mark.integration


# ── Dynamic fixture paths (v44.3: 由 conftest.py _build_fixture_wiki 动态生成) ──
_wiki_dir = os.path.join(os.path.dirname(__file__), "fixtures", "wiki")
_BOOK_DIR = os.path.join(_wiki_dir, "01_领域", "01_资料库", "01_测试书")

# 目录名必须与 kb_graph._type_dir_map 一致:
_CONCEPT_DIR = os.path.join(_BOOK_DIR, "30_核心概念")
_KE_DIR = os.path.join(_BOOK_DIR, "40_知识要素")       # 注意: 40 而非 30
_KP_DIR = os.path.join(_BOOK_DIR, "60_技能点")          # 注意: 60 而非 50


# ═══════════════════════════════════════════════════════════════
# Tests for _full_target()
# This is the path prefix normalizer that had the 01_资料库/ bug.
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_kg(tmp_path):
    """KGraph with a temp directory (no real files, just tests pure logic)."""
    kg = KGraph(str(tmp_path))
    return kg


class TestFullTarget:
    """_full_target(target, book_dir) — path prefix normalization"""

    def test_strips_01_domain_01_data_prefix(self, tmp_kg):
        """01_领域/01_资料库/ prefix → stripped (legacy behavior)"""
        result = tmp_kg._full_target(
            "01_领域/01_资料库/01_测试书/30_核心概念/概念Alpha",
            _BOOK_DIR,
        )
        assert result == "01_测试书/30_核心概念/概念Alpha"

    def test_strips_01_data_prefix(self, tmp_kg):
        """01_资料库/ prefix → stripped (the fix for the 228 bug)"""
        result = tmp_kg._full_target(
            "01_资料库/01_测试书/30_核心概念/概念Alpha",
            _BOOK_DIR,
        )
        assert result == "01_测试书/30_核心概念/概念Alpha"

    def test_short_name_no_slash_unchanged(self, tmp_kg):
        """Short name without '/' stays unchanged (no / → no book_dir prepend)"""
        result = tmp_kg._full_target("概念Alpha", _BOOK_DIR)
        assert result == "概念Alpha"

    def test_relative_path_prepends_book_dir(self, tmp_kg):
        """Relative path with '/' but no 01_ prefix → prepend book_dir basename"""
        result = tmp_kg._full_target("30_核心概念/概念Alpha", _BOOK_DIR)
        assert result == "01_测试书/30_核心概念/概念Alpha"

    def test_book_dir_not_starting_01_unchanged(self, tmp_kg):
        """If book_dir basename does NOT start with 01_, no prepend"""
        weird_book = "/some/other/path/99_杂项"
        result = tmp_kg._full_target("30_核心概念/概念Alpha", weird_book)
        # 99_杂项 doesn't start with 01_, so no prepend
        assert result == "30_核心概念/概念Alpha"

    def test_already_has_01_prefix_no_double_prepend(self, tmp_kg):
        """If target already starts with 01_, never double-prepend"""
        result = tmp_kg._full_target(
            "01_测试书/30_核心概念/概念Alpha",
            _BOOK_DIR,
        )
        assert result == "01_测试书/30_核心概念/概念Alpha"

    def test_empty_book_dir(self, tmp_kg):
        """book_dir=None or empty → no prepend"""
        result = tmp_kg._full_target("短路径/名称", "")
        assert result == "短路径/名称"

        result2 = tmp_kg._full_target("短路径/名称", None)
        assert result2 == "短路径/名称"


# ═══════════════════════════════════════════════════════════════
# Tests for _process_file() wikilink edge resolution
# This is the function that had the short-name lookup bug.
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def kg(_ensure_fixture_wiki):
    """KGraph instance pointed at the dynamic fixture wiki root.

    Uses _KGraphForTest which overrides _book_dirs() for 3-level nesting.
    """
    return _KGraphForTest(str(_ensure_fixture_wiki))


@pytest.fixture
def _wiki_root(_ensure_fixture_wiki):
    """Temp wiki root path where fixture .md files exist."""
    return str(_ensure_fixture_wiki)


@pytest.fixture
def _book_dir(_wiki_root):
    """Book directory inside the temp wiki root."""
    return os.path.join(_wiki_root, "01_领域", "01_资料库", "01_测试书")


@pytest.fixture
def name_to_id(kg):
    """Pre-built name→node_id mapping from fixture files."""
    return kg._build_name_to_id_pre()


# -- Node ID helpers (expected values) --


def _expected_node_id(wiki_root, book_dir, relative_path_without_ext):
    """Compute expected node_id the same way KGraph._make_node_id does.

    Uses the actual temp paths so relpath + replace produce correct IDs.
    """
    kg = _KGraphForTest(wiki_root)
    full = os.path.join(wiki_root, relative_path_without_ext + ".md")
    return kg._make_node_id(full, book_dir)


class TestProcessFileWikilinkResolution:
    """Test that _process_file correctly resolves wikilinks to node IDs.

    This targets the two specific bugs:
    Bug #1: short-name wikilinks like [[概念Alpha]] were NOT resolved via
            name_to_id lookup (fixed by adding the '/'-not-in check with
            name_to_id fallback around line 734).
    Bug #2: only 01_领域/01_资料库/ prefix was handled, but 01_资料库/
            prefix was missed (fixed around line 731).
    """

    def test_short_name_wikilink_resolves_via_name_to_id(self, kg, name_to_id, _wiki_root, _book_dir):
        """[[概念Alpha]] (no '/') → resolved to '01_测试书/30_核心概念/概念Alpha'
        via name_to_id lookup, NOT left as the bare name."""
        fpath = os.path.join(_book_dir, "40_知识要素", "要素Gamma.md")
        # This file has [[概念Alpha]] in the "关联概念" section.
        # "关联概念" → rel_type "RELATED_TO"

        nodes, edges = [], []
        kg._process_file(fpath, "knowledge-element", _book_dir, nodes, edges, name_to_id)

        # Build a set of edge targets for easy assertion
        edge_targets = {e["target"] for e in edges}

        # [[概念Alpha]] should resolve to the expected node ID
        expected_id = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/30_核心概念/概念Alpha")
        assert expected_id in edge_targets, (
            f"Short-name wikilink [[概念Alpha]] should resolve to {expected_id}, "
            f"but edge targets are: {edge_targets}"
        )

    def test_01_data_prefix_wikilink_normalized(self, kg, name_to_id, _wiki_root, _book_dir):
        """[[01_资料库/...]] → stripped to book-relative path.
        This is the SECOND prefix bug: only 01_领域/01_资料库/ was handled,
        but bare 01_资料库/ was missed."""
        fpath = os.path.join(_book_dir, "40_知识要素", "要素Gamma.md")
        # This file has [[01_资料库/01_测试书/10_总揽/book_overview_01_测试书_0]]
        # in the "关联目录" section.
        # "关联目录" → no matching SECTION_REL_MAP key → rel_type "RELATED_TO"

        nodes, edges = [], []
        kg._process_file(fpath, "knowledge-element", _book_dir, nodes, edges, name_to_id)

        edge_targets = {e["target"] for e in edges}

        expected_id = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/10_总揽/book_overview_01_测试书_0")
        assert expected_id in edge_targets, (
            f"01_资料库/ prefix should normalize to {expected_id}, " f"but edge targets are: {edge_targets}"
        )

    def test_old_01_domain_01_data_prefix_still_works(self, kg, name_to_id):
        """[[01_领域/01_资料库/...]] → stripped (legacy prefix, must not break)"""
        # Test using a file that might have this prefix.
        # We can monkey-patch content or use an existing fixture.
        # The fixture files don't have this exact prefix in wikilinks,
        # so we'll test _full_target directly in a scenario context,
        # AND also verify the _process_file path works for the code path.

        # Actual integration: the "关联目录" wikilinks in the KE file
        # use "01_资料库/" prefix, not "01_领域/01_资料库/".
        # The 概念Beta.md concept file also uses "01_资料库/" prefix.
        # Both prefixes go through the same normalization logic.

        # Verify that _full_target (called for ANSWERS edges) handles it:
        prefix_path = "01_领域/01_资料库/01_测试书/30_核心概念/概念Beta"
        result = kg._full_target(prefix_path, _BOOK_DIR)
        assert (
            result == "01_测试书/30_核心概念/概念Beta"
        ), f"Legacy 01_领域/01_资料库/ prefix broken: got {result}"

    def test_edge_rel_type_from_section(self, kg, name_to_id, _book_dir):
        """Edge rel_type is derived from section heading, not hardcoded."""
        fpath = os.path.join(_book_dir, "40_知识要素", "要素Gamma.md")
        nodes, edges = [], []
        kg._process_file(fpath, "knowledge-element", _book_dir, nodes, edges, name_to_id)

        # "关联概念" section → SECTION_REL_MAP has "关联概念" → "RELATED_TO"
        for e in edges:
            if e["section"] == "关联概念":
                assert e["rel_type"] == "RELATED_TO", f"Expected RELATED_TO for 关联概念, got {e['rel_type']}"

        # "关联目录" section → should fall back to RELATED_TO (no exact match)
        for e in edges:
            if e["section"] == "关联目录":
                # "关联目录" not in SECTION_REL_MAP → default RELATED_TO
                assert e["rel_type"] == "RELATED_TO", f"Expected RELATED_TO for 关联目录, got {e['rel_type']}"

    def test_skill_point_file_resolves_wikilinks(self, kg, name_to_id, _wiki_root, _book_dir):
        """Skill-point files also resolve wikilinks correctly via _process_file."""
        fpath = os.path.join(_book_dir, "60_技能点", "技能Delta.md")
        nodes, edges = [], []
        kg._process_file(fpath, "skill", _book_dir, nodes, edges, name_to_id)

        edge_targets = {e["target"] for e in edges}

        # This KP file has [[概念Alpha]] and [[要素Gamma]] in "关联概念/知识点/知识要素" section
        expected_Alpha = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/30_核心概念/概念Alpha")
        _expected_要素Gamma = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/40_知识要素/要素Gamma")  # noqa: F841

        if expected_Alpha in edge_targets:
            pass  # resolved correctly
        else:
            # Check if the name is in edge targets (might have been left unresolved)
            assert (
                expected_Alpha in edge_targets or "概念Alpha" in edge_targets
            ), f"概念Alpha not resolved. Edge targets: {edge_targets}"

        # The critical assertion: short-name wikilinks must NOT be left as bare names
        # They should resolve to full node IDs
        unresolved_bare_names = {t for t in edge_targets if "/" not in t}
        # Known allowable bare names: none — all should resolve
        assert len(unresolved_bare_names) == 0, (
            f"Unresolved short-name wikilinks found: {unresolved_bare_names}. "
            "These are dead links that the bug fix should have resolved."
        )


# ═══════════════════════════════════════════════════════════════
# Tests for _build_name_to_id_pre()
# ═══════════════════════════════════════════════════════════════


class TestBuildNameToIdPre:
    """_build_name_to_id_pre() — pre-scan name → node_id mapping"""

    def test_returns_correct_name_to_id_map(self, kg, _wiki_root, _book_dir):
        """Map contains all fixture files with correct name→node_id entries."""
        name_to_id = kg._build_name_to_id_pre()

        assert "概念Alpha" in name_to_id, "概念Alpha not in name_to_id"
        assert "概念Beta" in name_to_id, "概念Beta not in name_to_id"
        assert "要素Gamma" in name_to_id, "要素Gamma not in name_to_id"
        assert "技能Delta" in name_to_id, "技能Delta not in name_to_id"

        # Verify node IDs are correct
        expected_Alpha = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/30_核心概念/概念Alpha")
        assert (
            name_to_id["概念Alpha"] == expected_Alpha
        ), f"Expected {expected_Alpha}, got {name_to_id['概念Alpha']}"

    def test_name_to_id_no_duplicate_overwrites(self, kg):
        """First-encountered name wins; later duplicates are skipped."""
        name_to_id = kg._build_name_to_id_pre()

        # 要素Gamma should be in the map
        assert "要素Gamma" in name_to_id

        # Count: 4 unique names from our 5 fixture files
        # (book_overview has name "测试总揽")
        assert len(name_to_id) == 5, f"Expected 5 unique names, got {len(name_to_id)}: {name_to_id}"

    def test_book_overview_has_name_测试总揽(self, kg):
        """Index files with different names are also captured."""
        name_to_id = kg._build_name_to_id_pre()
        assert "测试总揽" in name_to_id, f"book_overview name '测试总揽' not in map: {list(name_to_id.keys())}"

    def test_all_node_ids_start_with_book_prefix(self, kg):
        """All node IDs should start with 01_测试书/ for the fixture book."""
        name_to_id = kg._build_name_to_id_pre()
        for name, node_id in name_to_id.items():
            assert node_id.startswith(
                "01_测试书/"
            ), f"Node ID for '{name}' doesn't start with book prefix: {node_id}"


# ═══════════════════════════════════════════════════════════════
# Integration: verify the complete build pipeline for wikilinks
# ═══════════════════════════════════════════════════════════════


class TestProcessFileNoUnresolvedShortNames:
    """Regression test: NO edge target should contain an unresolved short name.

    The core fix for the 228 dead_link bug ensures that [[概念名]] (no '/')
    is resolved via name_to_id. Verify this across ALL fixture files.
    """

    @staticmethod
    def _files_to_process(book_dir):
        """动态构建文件列表，路径指向临时 fixture 目录。"""
        return [
            (os.path.join(book_dir, "30_核心概念", "概念Alpha.md"), "concept"),
            (os.path.join(book_dir, "30_核心概念", "概念Beta.md"), "concept"),
            (os.path.join(book_dir, "40_知识要素", "要素Gamma.md"), "knowledge-element"),
            (os.path.join(book_dir, "60_技能点", "技能Delta.md"), "skill"),
        ]

    def test_no_unresolved_short_names_in_any_file(self, kg, name_to_id, _book_dir):
        """Every short-name wikilink is resolved. No bare concept names remain."""
        edges = []
        nodes = []

        for fpath, ntype in self._files_to_process(_book_dir):
            if os.path.isfile(fpath):
                kg._process_file(fpath, ntype, _book_dir, nodes, edges, name_to_id)

        edge_targets = {e["target"] for e in edges}
        unresolved = {t for t in edge_targets if "/" not in t}

        # The only acceptable short targets are those that legitimately
        # couldn't be resolved (no matching name in name_to_id).
        # All our fixture wikilinks reference existing fixture files.
        assert len(unresolved) == 0, (
            f"Unresolved short-name wikilinks: {unresolved}. "
            "These should have been resolved via name_to_id lookup. "
            "Bug #1 fix is not working correctly."
        )

    def test_no_01_data_prefix_in_edge_targets(self, kg, name_to_id, _book_dir):
        """No edge target should retain the 01_资料库/ or 01_领域/01_资料库/ prefix."""
        edges = []
        nodes = []

        for fpath, ntype in self._files_to_process(_book_dir):
            if os.path.isfile(fpath):
                kg._process_file(fpath, ntype, _book_dir, nodes, edges, name_to_id)

        bad_prefixes = [
            t for t in {e["target"] for e in edges} if t.startswith("01_资料库/") or t.startswith("01_领域/")
        ]

        assert len(bad_prefixes) == 0, (
            f"Edge targets still contain normalized prefixes: {bad_prefixes}. " "Bug #2 fix is not working correctly."
        )

    def test_edge_source_is_node_id(self, kg, name_to_id, _wiki_root, _book_dir):
        """Edge source should be the file's node_id, not a bare name."""
        fpath = os.path.join(_book_dir, "40_知识要素", "要素Gamma.md")
        nodes, edges = [], []
        kg._process_file(fpath, "knowledge-element", _book_dir, nodes, edges, name_to_id)

        expected_source = _expected_node_id(_wiki_root, _book_dir, "01_领域/01_资料库/01_测试书/40_知识要素/要素Gamma")
        for e in edges:
            assert e["source"] == expected_source, f"Edge source should be {expected_source}, got {e['source']}"
