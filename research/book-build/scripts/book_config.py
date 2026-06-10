#!/usr/bin/env python3
"""
book_config.py — 领域配置加载模块。

所有 book-build 脚本统一通过本模块加载 config.yaml，
避免在 SKILL.md、references/、脚本中硬编码路径/名称。

用法（Python）:
    from book_config import Config
    cfg = Config()
    cfg.book_a_path       # 书A的 md 路径
    cfg.source_books      # 三书列表
    cfg.workflow_mode     # "fast" 或 "full"

用法（Shell）:
    python3 -c "from book_config import Config; c=Config(); print(c.book_a_name)"
"""

import os
import yaml
from pathlib import Path

_CONFIG_CACHE = None

class Config:
    """领域配置的 Python 访问接口。"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

    def __repr__(self):
        return f"<Config textbook={self.textbook_name}>"

    # ── 教材信息 ──
    @property
    def textbook_name(self):
        return self._raw["textbook"]["name"]

    @property
    def outline_file(self):
        return self._raw["textbook"]["outline_file"]

    @property
    def output_dir(self):
        return Path(__file__).parent.parent / self._raw["textbook"]["output_dir"]

    # ── 三书访问 ──
    @property
    def source_books(self):
        """返回三书字典列表，按 priority 排序。"""
        books = list(self._raw["source_books"].values())
        return sorted(books, key=lambda b: b.get("priority", 99))

    @property
    def book_a_path(self):
        return self._raw["source_books"]["book_a"]["path"]

    @property
    def book_a_author(self):
        return self._raw["source_books"]["book_a"]["author"]

    @property
    def book_a_name(self):
        return self._raw["source_books"]["book_a"]["display_name"]

    @property
    def book_a_processed_dir(self):
        return self._raw["source_books"]["book_a"]["path_processed"]

    @property
    def book_b_path(self):
        return self._raw["source_books"]["book_b"]["path"]

    @property
    def book_b_author(self):
        return self._raw["source_books"]["book_b"]["author"]

    @property
    def book_b_name(self):
        return self._raw["source_books"]["book_b"]["display_name"]

    @property
    def book_c_path(self):
        return self._raw["source_books"]["book_c"]["path"]

    @property
    def book_c_author(self):
        return self._raw["source_books"]["book_c"]["author"]

    @property
    def book_c_name(self):
        return self._raw["source_books"]["book_c"]["display_name"]

    # ── 知识库路径 ──
    @property
    def kb_processed_dir(self):
        return self._raw["knowledge_base"]["processed_dir"]

    @property
    def kb_raw_dir(self):
        return self._raw["knowledge_base"]["raw_dir"]

    @property
    def kb_domain_dir(self):
        return self._raw["knowledge_base"]["domain_dir"]

    # ── 工作流 ──
    @property
    def workflow_mode(self):
        return self._raw["workflow"].get("default_mode", "fast")

    @property
    def phase_0_5_auto(self):
        return self._raw["workflow"].get("phase_0_5_auto", True)

    @property
    def quality_auto_fix(self):
        return self._raw["workflow"].get("quality_auto_fix", True)

    # ── 体量 ──
    @property
    def thin_threshold_lines(self):
        return self._raw["volume"].get("thin_threshold_lines", 700)

    @property
    def thin_threshold_kb(self):
        return self._raw["volume"].get("thin_threshold_kb", 35)

    @property
    def target_mermaid_min(self):
        return self._raw["volume"].get("target_mermaid_min", 6)

    # ── 快捷方法 ──
    def grep_all_books(self, keyword: str, head: int = 5) -> dict:
        """在三本书中同时搜索关键词。返回 {书名: [匹配行]}"""
        import subprocess
        results = {}
        for book in self.source_books:
            name = book["display_name"]
            path = book["path"]
            try:
                out = subprocess.check_output(
                    ["grep", "-n", keyword, path],
                    stderr=subprocess.DEVNULL,
                    timeout=10
                ).decode("utf-8", errors="replace")
                lines = out.strip().split("\n")[:head]
                results[name] = lines
            except (subprocess.CalledProcessError, FileNotFoundError):
                results[name] = []
        return results

    def get_book_by_author(self, author: str) -> dict:
        """按作者名查找书配置。"""
        for key in ["book_a", "book_b", "book_c"]:
            if self._raw["source_books"][key]["author"] == author:
                return self._raw["source_books"][key]
        return None

    # ── 全局缓存 ──
    @staticmethod
    def get_default():
        global _CONFIG_CACHE
        if _CONFIG_CACHE is None:
            _CONFIG_CACHE = Config()
        return _CONFIG_CACHE


def main():
    """Shell 入口：python3 book_config.py [属性名]"""
    import sys
    cfg = Config()
    if len(sys.argv) > 1:
        attr = sys.argv[1]
        val = getattr(cfg, attr, None)
        if val is not None:
            print(val)
        else:
            print(f"❌ 无此属性: {attr}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"教材: {cfg.textbook_name}")
        print(f"模式: {cfg.workflow_mode}")
        print(f"自动确认: {cfg.phase_0_5_auto}")
        for book in cfg.source_books:
            print(f"  [{book['author']}] {book['display_name']}")

if __name__ == "__main__":
    main()
