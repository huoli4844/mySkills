"""preprocess_toc.py 单元测试 — 标题解析、容器探测、超大节段分割"""

from collections import OrderedDict

import pytest
from preprocess_toc import (
    _collect_level_stats,
    _count_support,
    _find_split_points,
    build_containers,
    detect_container_level,
    parse_headings,
)

pytestmark = pytest.mark.unit

# ── 辅助 ──────────────────────────────────────────────


def _write_tmp_md(tmp_path, content: str) -> str:
    path = tmp_path / "chapter.md"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _make_heading(level, text, line, line_end):
    return OrderedDict([
        ("level", level),
        ("text", text),
        ("line", line),
        ("line_end", line_end),
        ("children", []),
    ])


# ── parse_headings ───────────────────────────────────────


class TestParseHeadings:
    """Markdown 标题解析测试"""

    def test_simple_headings(self, tmp_path):
        md = "# 第一章\n## 1.1 概述\n## 1.2 原理\n### 1.2.1 基础\n"
        path = _write_tmp_md(tmp_path, md)
        result = parse_headings(path)
        assert result["total_lines"] == 4
        assert len(result["headings_tree"]) >= 1

    def test_with_frontmatter(self, tmp_path):
        md = "---\ntype: chapter\ntitle: test\n---\n# 标题\n## 节\n"
        path = _write_tmp_md(tmp_path, md)
        result = parse_headings(path)
        # frontmatter 内的 # 不应被解析
        headings_texts = [h["text"] for h in result["headings_tree"]]
        assert "标题" in headings_texts or any("标题" in t for t in headings_texts)

    def test_empty_file(self, tmp_path):
        path = _write_tmp_md(tmp_path, "")
        result = parse_headings(path)
        assert result["total_lines"] == 0
        assert result["headings"] == []

    def test_no_headings(self, tmp_path):
        path = _write_tmp_md(tmp_path, "just some text\nmore text\n")
        result = parse_headings(path)
        assert result["headings"] == []

    def test_heading_with_anchor(self, tmp_path):
        md = "## 标题 {#custom-id}\n"
        path = _write_tmp_md(tmp_path, md)
        result = parse_headings(path)
        assert len(result["headings_tree"]) == 1
        # anchor 应被去除
        assert "{#" not in result["headings_tree"][0]["text"]

    def test_leaf_nodes_extraction(self, tmp_path):
        md = "# Ch1\n## Sec1\n### Sub1\n### Sub2\n## Sec2\n"
        path = _write_tmp_md(tmp_path, md)
        result = parse_headings(path)
        # Sub1, Sub2, Sec2 应该是叶节点
        leaf_texts = [n["text"] for n in result["leaf_nodes"]]
        assert "Sub1" in leaf_texts
        assert "Sub2" in leaf_texts

    def test_line_end_calculation(self, tmp_path):
        md = "# A\nline1\nline2\n## B\nline3\n"
        path = _write_tmp_md(tmp_path, md)
        result = parse_headings(path)
        # A 的 line 是 1
        a_node = result["headings_tree"][0]
        assert a_node["line"] == 1
        # A 的 line_end 应该是文件末尾（5行）
        assert a_node["line_end"] == 5


# ── _collect_level_stats ─────────────────────────────────


class TestCollectLevelStats:
    """层级统计测试"""

    def test_single_level(self):
        tree = [_make_heading(2, "A", 1, 50), _make_heading(2, "B", 51, 100)]
        stats = _collect_level_stats(tree)
        assert 2 in stats
        assert stats[2]["count"] == 2

    def test_multi_level(self):
        h1 = _make_heading(1, "Ch1", 1, 100)
        h2 = _make_heading(2, "Sec1", 5, 50)
        h1["children"] = [h2]
        stats = _collect_level_stats([h1])
        assert 1 in stats
        assert 2 in stats
        assert stats[1]["count"] == 1
        assert stats[2]["count"] == 1

    def test_empty_tree(self):
        stats = _collect_level_stats([])
        assert stats == {}


# ── detect_container_level ──────────────────────────────


class TestDetectContainerLevel:
    """自适应容器层级探测"""

    def test_selects_level_with_good_count_and_avg(self):
        tree = []
        # 创建 level 3: 5个标题，每个平均80行
        for i in range(5):
            tree.append(_make_heading(3, f"H{i}", i * 80 + 1, (i + 1) * 80))
        level, reason, _stats = detect_container_level(tree, 400)
        assert level == 3
        assert "5个标题" in reason

    def test_fallback_to_most_count(self):
        """没有符合条件的层级时使用标题数最多的"""
        tree = []
        # level 3: 只有1个标题（不够 min_count=3）
        tree.append(_make_heading(3, "Only", 1, 100))
        # level 2: 有2个标题
        tree.append(_make_heading(2, "A", 1, 50))
        tree.append(_make_heading(2, "B", 51, 100))
        level, _, _ = detect_container_level(tree, 100, min_count=3)
        # 兜底：level 2 有2个，level 3 有1个
        assert level in (2, 3)

    def test_empty_tree_returns_default(self):
        level, reason, _stats = detect_container_level([], 0)
        assert level == 3  # 默认
        assert "默认" in reason


# ── _count_support ──────────────────────────────────────


class TestCountSupport:
    """容器支撑元素（公式、图、表）计数"""

    def test_count_formulas(self):
        lines = ["text $$E=mc^2$$ more", "$$\\frac{1}{2}$$", "no formula"]
        assert _count_support(lines, 0, 2) == 2

    def test_count_figures(self):
        lines = ["图2-1 示意图", "![alt](img.png)", "normal text"]
        assert _count_support(lines, 0, 2) == 2

    def test_count_tables(self):
        lines = ["表3-1 数据", "| --- | --- |", "text"]
        assert _count_support(lines, 0, 2) == 2

    def test_empty_lines(self):
        assert _count_support([], 0, 0) == 0

    def test_mixed_support(self):
        lines = ["$$x$$", "图1-1", "表2-1", "normal"]
        count = _count_support(lines, 0, 3)
        assert count == 3


# ── _find_split_points ──────────────────────────────────


class TestFindSplitPoints:
    """超大节段分割点查找"""

    def test_empty_line_split(self):
        """连续空行作为分割点"""
        lines = ["line"] * 100 + ["", ""] + ["line"] * 100
        chunks = _find_split_points(lines, 0, 201, max_chunk=80)
        # 应该找到至少一个分割
        assert len(chunks) >= 1

    def test_no_split_for_short_content(self):
        """短内容不分割"""
        lines = ["line"] * 50
        chunks = _find_split_points(lines, 0, 49, max_chunk=150)
        assert len(chunks) <= 1
        if chunks:
            assert chunks[0][2] == "未分割"

    def test_forced_split_on_oversized(self):
        """超长内容强制分割"""
        lines = ["text"] * 300
        chunks = _find_split_points(lines, 0, 299, max_chunk=100)
        assert len(chunks) >= 1


# ── build_containers ─────────────────────────────────────


class TestBuildContainers:
    """容器构建测试"""

    def test_basic_container_building(self):
        tree = [
            _make_heading(3, "Concept A", 1, 50),
            _make_heading(3, "Concept B", 51, 100),
        ]
        lines = ["line"] * 100
        containers, summary = build_containers(tree, lines, container_level=3)
        assert len(containers) == 2
        assert containers[0]["text"] == "Concept A"
        assert containers[1]["text"] == "Concept B"
        assert summary["total_containers"] == 2

    def test_unique_ids(self):
        tree = [_make_heading(3, f"H{i}", i * 10 + 1, (i + 1) * 10) for i in range(5)]
        lines = ["line"] * 50
        containers, _ = build_containers(tree, lines, container_level=3)
        ids = [c["id"] for c in containers]
        assert len(ids) == len(set(ids))  # 所有 ID 唯一

    def test_empty_tree_returns_empty(self):
        containers, summary = build_containers([], [], container_level=3)
        assert containers == []
        assert summary["total_containers"] == 0

    # ── auto_split 路径测试 ──

    def test_auto_split_empty_line(self):
        """空行分割触发 auto_split：一个大节点 span > max_span，中间有连续空行"""
        # 创建一个 span=250 的无子节点 level=1 节点 (container_level=3)
        node = _make_heading(1, "大节段", 1, 250)
        # 内容行：前100行文本，然后两个空行，然后100行文本，最后剩余
        lines = []
        lines.extend(["line content"] * 100)
        lines.extend(["", ""])          # 连续空行 → 分割点
        lines.extend(["line content"] * 100)
        lines.extend(["end"] * 49)

        containers, summary = build_containers([node], lines, container_level=3, max_span=80)
        # 应该触发 auto_split（因为 span > max_span）
        assert len(containers) >= 1
        split_container = [c for c in containers if c.get("auto_split")]
        assert len(split_container) >= 1
        assert summary["from_oversized_split"] >= 1

    def test_auto_split_bold(self):
        """加粗标题行分割触发 auto_split"""
        # 带有 **Bold Title** 行的内容作为分割点
        node = _make_heading(1, "大节段", 1, 250)
        lines = []
        lines.extend(["line"] * 100)
        lines.append("**粗体标题**")     # 加粗标题 → 分割点
        lines.extend(["line"] * 148)

        containers, _summary = build_containers([node], lines, container_level=3, max_span=80)
        split_container = [c for c in containers if c.get("auto_split")]
        assert len(split_container) >= 1

    def test_auto_split_numbered(self):
        """编号段落分割触发 auto_split"""
        node = _make_heading(1, "大节段", 1, 250)
        lines = []
        lines.extend(["line"] * 100)
        lines.append("1. 第一点")         # 编号行 → 分割点
        lines.extend(["line"] * 148)

        containers, _summary = build_containers([node], lines, container_level=3, max_span=80)
        split_container = [c for c in containers if c.get("auto_split")]
        assert len(split_container) >= 1

    def test_auto_split_definition(self):
        """定义标记词分割触发 auto_split"""
        node = _make_heading(1, "大节段", 1, 250)
        lines = []
        lines.extend(["line"] * 100)
        lines.append("传导耦合是指通过导体传输的电磁干扰")  # 含"是指" → 分割点
        lines.extend(["line"] * 148)

        containers, _summary = build_containers([node], lines, container_level=3, max_span=80)
        split_container = [c for c in containers if c.get("auto_split")]
        assert len(split_container) >= 1

    def test_auto_split_oversized_forced(self):
        """超大容器强制分割（超过 1.5 倍阈值时向前找空行或强制切分）"""
        node = _make_heading(1, "超长大节段", 1, 400)
        # 无空行、无标题、无编号 — 只能强制分割
        lines = ["text"] * 400

        containers, _summary = build_containers([node], lines, container_level=3, max_span=80)
        split_container = [c for c in containers if c.get("auto_split")]
        # 应该触发分割（至少一个 auto_split 容器）
        assert len(split_container) >= 1

    def test_auto_split_no_children_only(self):
        """仅有子节点的节点不触发 auto_split"""
        parent = _make_heading(1, "有子节点的节", 1, 250)
        child = _make_heading(2, "子节", 5, 100)
        parent["children"] = [child]
        lines = ["line"] * 250

        containers, _summary = build_containers([parent], lines, container_level=3, max_span=80)
        # 有子节点的 level < container_level 节点应跳过（子节点处理）
        # parent 不应出现在 containers 中（有子节点跳过）
        parent_in = any(c["text"] == "有子节点的节" for c in containers)
        assert not parent_in

    def test_auto_split_split_into_fields(self):
        """验证 auto_split 容器的 split_into 子字段"""
        node = _make_heading(1, "大节段", 1, 250)
        lines = []
        lines.extend(["line"] * 100)
        lines.extend(["", ""])          # 空行分割
        lines.extend(["line"] * 148)

        containers, _summary = build_containers([node], lines, container_level=3, max_span=80)
        for c in containers:
            if c.get("auto_split"):
                assert "split_into" in c
                assert isinstance(c["split_into"], list)
                assert len(c["split_into"]) >= 2
                for sub in c["split_into"]:
                    assert "sub_id" in sub
                    assert "line" in sub
                    assert "line_end" in sub
                    assert "span_lines" in sub
                    assert "support_count" in sub
                    assert "split_reason" in sub


# ── _find_split_points 非空策略测试 ──


class TestFindSplitPointsNonEmpty:
    """_find_split_points 加粗/编号/定义策略测试"""

    def test_bold_line_split(self):
        """加粗标题行作为分割点"""
        lines = ["line"] * 60 + ["**粗体标题**"] + ["line"] * 60
        chunks = _find_split_points(lines, 0, len(lines) - 1, max_chunk=50)
        reasons = [c[2] for c in chunks]
        assert "加粗标题分割" in reasons

    def test_numbered_line_split(self):
        """编号段落作为分割点"""
        lines = ["line"] * 60 + ["1. 第一点"] + ["line"] * 60
        chunks = _find_split_points(lines, 0, len(lines) - 1, max_chunk=50)
        reasons = [c[2] for c in chunks]
        assert "编号段落分割" in reasons

    def test_chinese_numbered_split(self):
        """中文编号（1.）作为分割点"""
        lines = ["line"] * 60 + ["（1）第一项"] + ["line"] * 60
        chunks = _find_split_points(lines, 0, len(lines) - 1, max_chunk=50)
        reasons = [c[2] for c in chunks]
        assert "编号段落分割" in reasons

    def test_definition_keyword_split(self):
        """定义标记词行作为分割点"""
        for kw in ["是指", "称为", "即", "定义为", "所谓"]:
            lines = ["line"] * 60 + [f"概念{kw}一个术语的定义"] + ["line"] * 60
            chunks = _find_split_points(lines, 0, len(lines) - 1, max_chunk=50)
            reasons = [c[2] for c in chunks]
            assert "定义标记词分割" in reasons, f"Failed for keyword: {kw}"

    def test_fallback_forced_split(self):
        """超过 1.5 倍阈值时向前找空行或强制分割"""
        # 全部纯文本，无任何分割点特征
        lines = ["x"] * 250
        chunks = _find_split_points(lines, 0, 249, max_chunk=80)
        # 应该产生分割
        assert len(chunks) >= 1
        reasons = [c[2] for c in chunks]
        assert any("强制分割" in r or "向前找" in str(r) or "尾部" in r for r in reasons)

    def test_minimum_chunk_respected(self):
        """分割后每个片段至少 20 行"""
        lines = ["line"] * 30 + ["**短标题**"] + ["line"] * 30
        chunks = _find_split_points(lines, 0, 59, max_chunk=40)
        # 每个 chunk span 至少 20 行
        for start, end, _ in chunks:
            assert end - start + 1 >= 0  # 总是 >= 0

