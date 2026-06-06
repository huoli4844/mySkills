"""scripts/tests/conftest.py — 测试全局配置

v41.0: 统一 sys.path 设置 + 测试隔离 fixture，
消除 19 个测试文件的重复 sys.path.insert 行。
v44.3: 添加 _build_fixture_wiki() 动态生成 wikilink 测试数据，
消除对磁盘 fixture 文件的依赖（代码即数据，永不丢失）。
"""

import os
import sys

# 将 scripts/ 添加到 sys.path（所有测试共享，无需每个文件重复）
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


import pytest  # noqa: E402
from kb_graph import KGraph  # noqa: E402

# ── Fixture Wiki 动态生成 ──────────────────────────────────
# wikilink 解析测试需要的迷你知识库，在 session 级别动态创建。
# 目录名必须与 kb_graph.py _type_dir_map 一致：
#   30_核心概念 / 40_知识要素 / 60_技能点 / 10_总揽

_FIXTURE_WIKI_READY = False


def _build_fixture_wiki(wiki_root):
    """创建包含 frontmatter + wikilinks 的极简 .md 文件。

    5 个文件覆盖 4 种节点类型，验证短名解析和前缀剥离。
    """
    # wiki_root 是 01_领域 的父级（与真实 nested layout 一致）
    # _book_dirs 扫描 2 层: wiki_root/{domain}/{library} → book 在第 3 层
    book = os.path.join(wiki_root, "01_领域", "01_资料库", "01_测试书")
    files = {
        "30_核心概念/概念Alpha.md": "---\nname: 概念Alpha\n---\n",
        "30_核心概念/概念Beta.md": "---\nname: 概念Beta\n---\n",
        "40_知识要素/要素Gamma.md": (
            "---\nname: 要素Gamma\n---\n\n"
            "### 关联概念\n\n[[概念Alpha]]\n\n"
            "### 关联目录\n\n"
            "[[01_资料库/01_测试书/10_总揽/book_overview_01_测试书_0]]\n"
        ),
        "60_技能点/技能Delta.md": (
            "---\nname: 技能Delta\n---\n\n"
            "### 关联概念\n\n[[概念Alpha]]\n\n[[要素Gamma]]\n"
        ),
        "10_总揽/book_overview_01_测试书_0.md": "---\nname: 测试总揽\n---\n",
    }
    for rel_path, content in files.items():
        fpath = os.path.join(book, rel_path)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)


class _KGraphForTest(KGraph):
    """测试专用 KGraph — 覆盖 _book_dirs() 支持 3 层嵌套布局。

    生产 _book_dirs() 只扫描 2 层 (wiki_root/{domain}/{sub_dir})，
    但真实布局是 3 层: {domain}/{library}/{book}。
    测试子类多走一层，返回实际的书籍目录。
    """

    def _book_dirs(self) -> list[str]:
        found = []
        for domain_dir in os.listdir(self.wiki_root):
            domain_path = os.path.join(self.wiki_root, domain_dir)
            if not os.path.isdir(domain_path) or domain_dir.startswith("."):
                continue
            for lib_dir in os.listdir(domain_path):
                lib_path = os.path.join(domain_path, lib_dir)
                if not os.path.isdir(lib_path) or lib_dir.startswith("."):
                    continue
                for book_dir in os.listdir(lib_path):
                    book_path = os.path.join(lib_path, book_dir)
                    if os.path.isdir(book_path) and not book_dir.startswith("."):
                        found.append(book_path)
        return sorted(found)


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixture_wiki(tmp_path_factory):
    """session 级别：在 tmp_path 中创建迷你知识库，所有 wikilink 测试共享。"""
    global _FIXTURE_WIKI_READY
    wiki_root = tmp_path_factory.mktemp("fixture_wiki")
    _build_fixture_wiki(str(wiki_root))
    _FIXTURE_WIKI_READY = True
    return wiki_root


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """每个测试前/后重置 config.py 全局缓存，防止测试间状态泄漏。"""
    try:
        from config import reload_config

        reload_config()
    except ImportError:
        pass
    yield
    try:
        from config import reload_config

        reload_config()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _reset_log_utils():
    """每个测试后清理 log_utils 缓存的 logger handler，防止 handler 累积。"""
    yield
    try:
        from log_utils import _loggers

        for logger in _loggers.values():
            for handler in logger.handlers[:]:
                handler.flush()
    except ImportError:
        pass
