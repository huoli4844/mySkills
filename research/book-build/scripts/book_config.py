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
    cfg.writing_guide_dir # output/写作大纲/
    cfg.cases_dir         # output/案例/
    cfg.experiments_dir   # output/实验/
    cfg.exercise_dir      # output/习题解答/
    cfg.input_dir         # input/（大纲所在目录）

用法（Shell）:
    python3 -c "from book_config import Config; c=Config(); print(c.book_a_name)"
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional

_CONFIG_CACHE = None


class Config:
    """领域配置的 Python 访问接口。"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)

    def __repr__(self):
        return f"<Config textbook={self.textbook_name}>"

    # ── 教材信息 ──
    @property
    def textbook_name(self) -> str:
        return self._raw["textbook"]["name"]

    @property
    def outline_file(self) -> str:
        return self._raw["textbook"]["outline_file"]

    @property
    def outline_path(self) -> str:
        """大纲文件完整路径（input/目录下）。"""
        return os.path.join(self.input_dir, self.outline_file)

    # ── 项目目录 ──
    @property
    def project_root(self) -> str:
        return self._raw["project"]["root"]

    @property
    def input_dir(self) -> str:
        return self._raw["project"]["input_dir"]

    @property
    def output_dir(self) -> str:
        return self._raw["project"]["output_dir"]

    @property
    def writing_guide_dir(self) -> str:
        """写作大纲目录：output/写作大纲/"""
        sub = self._raw["project"]["subdirs"]["writing_guide"]
        return os.path.join(self.output_dir, sub)

    @property
    def cases_dir(self) -> str:
        """案例目录：output/案例/"""
        sub = self._raw["project"]["subdirs"]["cases"]
        return os.path.join(self.output_dir, sub)

    @property
    def experiments_dir(self) -> str:
        """实验目录：output/实验/"""
        sub = self._raw["project"]["subdirs"]["experiments"]
        return os.path.join(self.output_dir, sub)

    @property
    def exercise_dir(self) -> str:
        """习题解答目录：output/习题解答/"""
        sub = self._raw["project"]["subdirs"]["exercise_solutions"]
        return os.path.join(self.output_dir, sub)

    def ensure_dirs(self):
        """确保所有输出子目录存在。"""
        for d in [self.writing_guide_dir, self.cases_dir,
                  self.experiments_dir, self.exercise_dir]:
            os.makedirs(d, exist_ok=True)

    def writing_guide_path(self, chapter_num: int) -> str:
        """获取第N章写作指南的完整路径。"""
        return os.path.join(self.writing_guide_dir, f"writing-guide-ch{chapter_num}.md")

    def case_path(self, chapter: int, seq: int, title: str) -> str:
        """获取案例文件路径。例：案例2-1_通信设备辐射发射超标事件.md"""
        return os.path.join(self.cases_dir, f"案例{chapter}-{seq}_{title}.md")

    def experiment_path(self, chapter: int, title: str) -> str:
        """获取实验文件路径。例：实验04_电磁干扰源定位.md"""
        return os.path.join(self.experiments_dir, f"实验{chapter:02d}_{title}.md")

    def chapter_path(self, chapter_num: int, title_hint: str = "") -> str:
        """获取章文件路径。例：output/第8章-屏蔽技术.md"""
        suffix = f"-{title_hint}" if title_hint else ""
        return os.path.join(self.output_dir, f"第{chapter_num}章{suffix}.md")

    # ── 三书访问 ──
    @property
    def source_books(self) -> List[Dict]:
        """返回三书字典列表，按 priority 排序。"""
        books = list(self._raw["source_books"].values())
        return sorted(books, key=lambda b: b.get("priority", 99))

    @property
    def book_a_path(self) -> str:
        return self._raw["source_books"]["book_a"]["path"]

    @property
    def book_a_author(self) -> str:
        return self._raw["source_books"]["book_a"]["author"]

    @property
    def book_a_name(self) -> str:
        return self._raw["source_books"]["book_a"]["display_name"]

    @property
    def book_a_processed_dir(self) -> str:
        return self._raw["source_books"]["book_a"]["path_processed"]

    @property
    def book_b_path(self) -> str:
        return self._raw["source_books"]["book_b"]["path"]

    @property
    def book_b_author(self) -> str:
        return self._raw["source_books"]["book_b"]["author"]

    @property
    def book_b_name(self) -> str:
        return self._raw["source_books"]["book_b"]["display_name"]

    @property
    def book_c_path(self) -> str:
        return self._raw["source_books"]["book_c"]["path"]

    @property
    def book_c_author(self) -> str:
        return self._raw["source_books"]["book_c"]["author"]

    @property
    def book_c_name(self) -> str:
        return self._raw["source_books"]["book_c"]["display_name"]

    # ── 知识库路径 ──
    @property
    def kb_processed_dir(self) -> str:
        return self._raw["knowledge_base"]["processed_dir"]

    @property
    def kb_raw_dir(self) -> str:
        return self._raw["knowledge_base"]["raw_dir"]

    @property
    def kb_domain_dir(self) -> str:
        return self._raw["knowledge_base"]["domain_dir"]

    # ── 工作流 ──
    @property
    def workflow_mode(self) -> str:
        return self._raw["workflow"].get("default_mode", "fast")

    @property
    def phase_0_5_auto(self) -> bool:
        return self._raw["workflow"].get("phase_0_5_auto", True)

    @property
    def quality_auto_fix(self) -> bool:
        return self._raw["workflow"].get("quality_auto_fix", True)

    # ── 体量 ──
    @property
    def thin_threshold_lines(self) -> int:
        return self._raw["volume"].get("thin_threshold_lines", 700)

    @property
    def thin_threshold_kb(self) -> int:
        return self._raw["volume"].get("thin_threshold_kb", 35)

    @property
    def target_mermaid_min(self) -> int:
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

    def get_book_by_author(self, author: str) -> Optional[Dict]:
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
        print(f"输入: {cfg.input_dir}")
        print(f"输出: {cfg.output_dir}")
        print(f"  写作大纲: {cfg.writing_guide_dir}")
        print(f"  案例:     {cfg.cases_dir}")
        print(f"  实验:     {cfg.experiments_dir}")
        print(f"  习题解答: {cfg.exercise_dir}")
        print(f"模式: {cfg.workflow_mode}")
        for book in cfg.source_books:
            print(f"  [{book['author']}] {book['display_name']}")

if __name__ == "__main__":
    main()
