"""workspace_paths.py — 统一工作区路径管理

从 dag_state.py 拆分。WorkspacePaths 类从 book 目录推导所有层级路径。
"""

import os

from dag_constants import DIR, DIR_BY_PHASE


class WorkspacePaths:
    """从 book 目录（wr）统一推导所有层级路径。

    用法:
        wp = WorkspacePaths(wr)
        wp.kb_root              → KB 根目录
        wp.domain_dir           → 领域目录
        wp.l2_dir               → 书籍 L2 总揽
        wp.l3_dir               → 领域 L3 总控
        wp.l4_dir               → KB L4 总控
        wp.source_dir           → 20_正文/
        wp.content_dir(type)    → 各 L1 内容目录
        wp.data_dir(chapter)    → .dag/第N章/data/
        wp.dag_dir(chapter)     → .dag/第N章/
        wp.toc_path(chapter)    → .dag/第N章/chapter_toc.json
        wp.state_path(bid, ch)  → .dag/{bid}_ch{ch}.json

    禁止手拼 os.path.join(wr, ...) — 全部经此类。
    """

    def __init__(self, wr: str):
        self.book_dir: str = os.path.abspath(wr)
        self.domain_dir: str = os.path.dirname(self.book_dir)
        self.kb_root: str = os.path.dirname(self.domain_dir)
        self.domain_name: str = os.path.basename(self.domain_dir)
        self.book_name: str = os.path.basename(self.book_dir)

        # ── v50.0: 验证 wr 是合法的 book 目录 ──
        self._is_valid_book: bool = os.path.isdir(os.path.join(self.book_dir, DIR["SOURCE"]))
        if not self._is_valid_book:
            # 尝试回退：wr 可能是 domain 目录 → 子目录为 book
            sub_book = os.path.join(wr, self.book_name)
            if os.path.isdir(os.path.join(sub_book, DIR["SOURCE"])):
                self.book_dir = sub_book
                self.domain_dir = os.path.abspath(wr)
                self.kb_root = os.path.dirname(self.domain_dir)
                self.domain_name = os.path.basename(self.domain_dir)
                self._is_valid_book = True

        # 从 DIR 常量读取目录名（单一来源）
        self._ov = DIR["OVERVIEW"]  # 10_总揽
        self._dc = DIR["DOMAIN_CTRL"]  # 领域总控
        self._kb = DIR["KB_CTRL"]  # 知识库总控
        self._src = DIR["SOURCE"]  # 20_正文

    @property
    def l2_dir(self) -> str:
        return os.path.join(self.book_dir, self._ov)

    @property
    def l3_dir(self) -> str:
        return os.path.join(self.domain_dir, self._dc)

    @property
    def l4_dir(self) -> str:
        return os.path.join(self.kb_root, self._kb)

    @property
    def source_dir(self) -> str:
        return os.path.join(self.book_dir, self._src)

    def content_dir(self, phase: str) -> str:
        """根据 phase 名返回对应的 L1 内容目录。"""
        dir_key = DIR_BY_PHASE.get(phase, "")
        return os.path.join(self.book_dir, dir_key) if dir_key else ""

    def data_dir(self, chapter: str) -> str:
        """返回章节 YAML 数据目录: .dag/第N章/data/"""
        return os.path.join(self.book_dir, ".dag", f"第{chapter}章", "data")

    def dag_dir(self, chapter: str) -> str:
        """返回章节 DAG 状态目录: .dag/第N章/"""
        return os.path.join(self.book_dir, ".dag", f"第{chapter}章")

    def toc_path(self, chapter: str) -> str:
        """返回 chapter_toc.json 路径"""
        return os.path.join(self.dag_dir(chapter), "chapter_toc.json")

    def state_path(self, book_id: str, chapter: str) -> str:
        """返回 pipeline 状态文件路径"""
        # Follows _state_path convention: .dag/{book_id}_ch{chapter}.json
        ch_num = chapter.lstrip("第").rstrip("章") if "第" in chapter else chapter
        return os.path.join(self.book_dir, ".dag", f"{book_id}_ch{ch_num}.json")

    def ensure_all(self):
        """创建所有输出目录。"""
        for d in [self.l2_dir, self.l3_dir, self.l4_dir, self.source_dir]:
            os.makedirs(d, exist_ok=True)
        for key in DIR_BY_PHASE:
            cd = self.content_dir(key)
            if cd:
                os.makedirs(cd, exist_ok=True)
