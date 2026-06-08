#!/usr/bin/env python3
"""dag_state.py — DAG 状态管理（简化版）

每个章节一个状态文件 .dag/书籍ID_chN.json
记录各阶段状态和依赖关系，支持断点续传。

用法:
  state = ChapterState(book_dir, "01_书ID", "3")
  state.get_status("concepts")  # "done" | "pending" | "failed"
  state.set_status("concepts", "done")
  state.save()
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

# ── Pipeline 阶段定义 ────────────────────────────────────

# 名字 / 序号 / 依赖
PHASES: list[dict[str, Any]] = [
    {"name": "chapter_toc",  "index": 0,  "deps": []},
    {"name": "concepts",     "index": 1,  "deps": ["chapter_toc"]},
    {"name": "ke",           "index": 2,  "deps": ["concepts"]},
    {"name": "entities",     "index": 3,  "deps": ["concepts"]},
    {"name": "kp",           "index": 4,  "deps": ["concepts", "ke", "entities"]},
    {"name": "sp",           "index": 5,  "deps": ["kp"]},
    {"name": "scene",        "index": 6,  "deps": ["kp", "sp"]},
    {"name": "exercises",    "index": 7,  "deps": ["scene"]},
    {"name": "solutions",    "index": 8,  "deps": ["exercises"]},
    {"name": "l2_indices",   "index": 9,  "deps": ["concepts", "ke", "entities", "kp", "sp", "scene", "exercises", "solutions"]},
    {"name": "l3_indices",   "index": 10, "deps": ["l2_indices"]},
    {"name": "l4_indices",   "index": 11, "deps": ["l3_indices"]},
]

PHASE_NAMES = [p["name"] for p in PHASES]
SCHEMA_VERSION = "2.0.0"

# ── 异常 ──────────────────────────────────────────────────

class PipelineError(Exception):
    """Pipeline 统一异常"""
    def __init__(self, message: str, phase: str = "", details: str = ""):
        self.phase = phase
        self.details = details
        super().__init__(f"[{phase}] {message}" if phase else message)


# ── 状态管理 ──────────────────────────────────────────────

class ChapterState:
    """单章状态管理器"""

    def __init__(self, book_dir: str, book_id: str, chapter: str):
        self.book_dir = os.path.abspath(book_dir)
        self.book_id = book_id
        self.chapter = str(chapter)
        self.state_dir = os.path.join(self.book_dir, ".dag")
        self.state_path = os.path.join(self.state_dir, f"{book_id}_ch{chapter}.json")
        os.makedirs(self.state_dir, exist_ok=True)
        self._data = self._load()

    # ── 读写 ──

    def _load(self) -> dict:
        """加载状态文件"""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_state()

    def _default_state(self) -> dict:
        """默认状态"""
        return {
            "book_id": self.book_id,
            "book_name": "",
            "chapter": self.chapter,
            "phases": {p["name"]: {"index": p["index"], "status": "pending", "files": 0, "deps": p["deps"]}
                       for p in PHASES},
            "_schema_version": SCHEMA_VERSION,
            "_last_modified": "",
        }

    def save(self):
        """写入状态文件"""
        self._data["_last_modified"] = datetime.now().isoformat()
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ── 查询 ──

    def get_status(self, phase: str) -> str:
        """获取阶段状态: done | pending | failed | running"""
        return self._data.get("phases", {}).get(phase, {}).get("status", "pending")

    def set_status(self, phase: str, status: str, files: int = 0):
        """设置阶段状态"""
        if phase in self._data.get("phases", {}):
            self._data["phases"][phase]["status"] = status
            if files:
                self._data["phases"][phase]["files"] = files

    def get_phase_count(self, phase: str) -> int:
        """获取阶段文件数"""
        return self._data.get("phases", {}).get(phase, {}).get("files", 0)

    def can_run(self, phase: str) -> tuple[bool, str]:
        """检查是否可运行某阶段（依赖已完成）"""
        deps = self._data.get("phases", {}).get(phase, {}).get("deps", [])
        pending_deps = [d for d in deps if self.get_status(d) != "done"]
        if pending_deps:
            return False, f"依赖未完成: {', '.join(pending_deps)}"
        current = self.get_status(phase)
        if current == "done":
            return False, f"已完成，跳过"
        return True, ""

    def next_pending(self) -> str | None:
        """返回下一个可运行的阶段名（按依赖顺序）"""
        for p in PHASES:
            name = p["name"]
            can, _ = self.can_run(name)
            if can:
                return name
        return None

    def all_done(self) -> bool:
        """全部阶段完成"""
        return all(self.get_status(p["name"]) == "done" for p in PHASES)

    def summary(self) -> str:
        """生成状态摘要"""
        lines = [f"📊 第{self.chapter}章 构建状态（{self.book_id}）", "=" * 50]
        for p in PHASES:
            name = p["name"]
            status = self.get_status(name)
            icons = {"done": "✅", "pending": "⏳", "failed": "❌", "running": "🔄"}
            icon = icons.get(status, "⏳")
            files = self.get_phase_count(name)
            file_str = f" {files}个文件" if files > 0 else ""
            lines.append(f"  {icon} {name:15s} {status}{file_str}")
        return "\n".join(lines)

    # ── 元数据 ──

    @property
    def phases_done_count(self) -> int:
        return sum(1 for p in PHASES if self.get_status(p["name"]) == "done")

    @property
    def phases_total(self) -> int:
        return len(PHASES)


def phase_status_summary(book_dir: str, book_id: str) -> str:
    """全书状态摘要"""
    from pathlib import Path
    dag_dir = os.path.join(book_dir, ".dag")
    if not os.path.isdir(dag_dir):
        return "❌ .dag 目录不存在"

    chapters = sorted(set(
        f.stem.replace(f"{book_id}_ch", "")
        for f in Path(dag_dir).glob(f"{book_id}_ch*.json")
    ))
    if not chapters:
        return "❌ 未找到章节状态文件"

    lines = [f"📊 全书状态（{book_id}）", "=" * 60]
    lines.append(f"| 章节 | {' | '.join(p['name'][:8] for p in PHASES)} | 进度 |")
    lines.append(f"|:----:|{'|:---:' * len(PHASES)}|:---:|")

    for ch in chapters:
        state = ChapterState(book_dir, book_id, str(ch))
        statuses = []
        done = 0
        for p in PHASES:
            s = state.get_status(p["name"])
            icons = {"done": "✅", "pending": "⏳", "failed": "❌"}
            statuses.append(icons.get(s, "⏳"))
            if s == "done":
                done += 1
        pct = done * 100 // len(PHASES)
        status_row = "|".join(statuses)
        lines.append(f"| 第{ch}章 | {status_row} | {pct}% |")

    return "\n".join(lines)
