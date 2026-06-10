#!/usr/bin/env python3
"""
book_config.py — 配置加载模块（技能默认 + 项目覆盖）。

加载策略：
  1. 加载 skill 级 config.yaml（工作流/体量/输出格式默认值）
  2. 如果提供了 project_root，加载 {project_root}/book-build.yaml（项目特有参数）
  3. 合并，项目配置优先级更高
  4. 自动创建 project_root/input/ 和 project_root/output/ 及子目录

用法：
    from book_config import Config

    # 仅加载技能默认值
    cfg = Config()

    # 从项目目录加载
    cfg = Config(project_root="/Users/huoli4844/Desktop/查老师教材")

    # 动态获取属性
    cfg.textbook_name      → "查老师教材"
    cfg.source_books       → [有序列表，按 priority 排序]
    cfg.outline_path       → /path/to/project/input/教材提纲.docx
    cfg.writing_guide_dir  → /path/to/project/output/写作大纲/
    cfg.chapter_path(3)    → /path/to/project/output/第3章.md

Shell 入口:
    python3 book_config.py --project /path/to/project [属性名]
    python3 book_config.py --project /path/to/project --show
"""

import os
import yaml
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any

_SKILL_CONFIG_CACHE = None
_PROJECT_CONFIG_CACHE: Dict[str, "Config"] = {}


def _load_yaml(path: str) -> dict:
    """安全加载 YAML，文件不存在返回空 dict。"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_skill_dir() -> str:
    """返回 book-build 技能目录（config.yaml 所在目录的父目录）。"""
    return str(Path(__file__).resolve().parent.parent)


def _get_skill_config() -> dict:
    """加载技能级 config.yaml（只加载一次）。"""
    global _SKILL_CONFIG_CACHE
    if _SKILL_CONFIG_CACHE is None:
        path = os.path.join(_get_skill_dir(), "config.yaml")
        _SKILL_CONFIG_CACHE = _load_yaml(path)
    return _SKILL_CONFIG_CACHE


class Config:
    """配置访问接口：技能默认值 + 项目覆盖。"""

    def __init__(self, project_root: Optional[str] = None):
        self._project_root = project_root

        # 1) 技能默认值（config.yaml）
        self._cfg = dict(_get_skill_config())  # deep-enough copy

        # 2) 项目覆盖（book-build.yaml）
        if project_root:
            project_config_path = os.path.join(project_root, "book-build.yaml")
            proj = _load_yaml(project_config_path)
            self._deep_merge(self._cfg, proj)

            # 自动创建项目目录
            self._ensure_project_dirs()

    def __repr__(self):
        root = self._project_root or "(skill defaults)"
        return f"<Config textbook={self.textbook_name} project={root}>"

    # ── 目录初始化 ──

    def _ensure_project_dirs(self):
        """自动创建 input/ output/ 及所有子目录。"""
        if not self._project_root:
            return
        dirs = [self.input_dir, self.output_dir]
        for d in [
            self.writing_guide_dir,
            self.cases_dir,
            self.experiments_dir,
            self.exercise_dir,
        ]:
            dirs.append(d)
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    @staticmethod
    def setup(project_root: str, config_template: Optional[str] = None):
        """初始化项目：创建目录 + 复制 book-build.yaml 模板。

        参数:
            project_root: 项目根路径
            config_template: 可选的配置模板路径（默认用技能内置模板）
        """
        os.makedirs(project_root, exist_ok=True)
        project_config = os.path.join(project_root, "book-build.yaml")

        if not os.path.exists(project_config):
            if config_template and os.path.exists(config_template):
                shutil.copy2(config_template, project_config)
            else:
                # 用技能内置模板
                default_template = os.path.join(
                    _get_skill_dir(), "templates", "project-config-template.yaml"
                )
                if os.path.exists(default_template):
                    shutil.copy2(default_template, project_config)
            print(f"✅ 已创建项目配置: {project_config}")
        else:
            print(f"ℹ️  项目配置已存在: {project_config}")

        # 创建目录结构
        cfg = Config(project_root=project_root)
        cfg._ensure_project_dirs()
        print(f"✅ 已创建目录结构:")
        print(f"   {cfg.input_dir}")
        print(f"   {cfg.output_dir}")
        for d in [cfg.writing_guide_dir, cfg.cases_dir,
                  cfg.experiments_dir, cfg.exercise_dir]:
            print(f"   {d}/")

    # ── 合并工具 ──

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """递归合并 override 到 base。"""
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                Config._deep_merge(base[key], val)
            else:
                base[key] = val

    # ── 教材信息 ──

    @property
    def textbook_name(self) -> str:
        return self._cfg.get("textbook", {}).get("name", "")

    @property
    def outline_file(self) -> str:
        return self._cfg.get("textbook", {}).get("outline_file", "教材提纲.docx")

    @property
    def outline_path(self) -> str:
        return os.path.join(self.input_dir, self.outline_file)

    # ── 项目目录 ──

    @property
    def project_root(self) -> Optional[str]:
        return self._project_root

    @property
    def input_dir(self) -> str:
        if not self._project_root:
            return os.path.join(_get_skill_dir(), "input")
        return os.path.join(self._project_root, "input")

    @property
    def output_dir(self) -> str:
        if not self._project_root:
            return os.path.join(_get_skill_dir(), "output")
        return os.path.join(self._project_root, "output")

    def _subdir(self, key: str) -> str:
        sub = self._cfg.get("subdirs", {}).get(key, key)
        return os.path.join(self.output_dir, sub)

    @property
    def writing_guide_dir(self) -> str:
        return self._subdir("writing_guide")

    @property
    def cases_dir(self) -> str:
        return self._subdir("cases")

    @property
    def experiments_dir(self) -> str:
        return self._subdir("experiments")

    @property
    def exercise_dir(self) -> str:
        return self._subdir("exercise_solutions")

    # ── 路径快捷方法 ──

    def writing_guide_path(self, chapter_num: int) -> str:
        return os.path.join(
            self.writing_guide_dir, f"writing-guide-ch{chapter_num}.md"
        )

    def case_path(self, chapter: int, seq: int, title: str) -> str:
        return os.path.join(self.cases_dir, f"案例{chapter}-{seq}_{title}.md")

    def experiment_path(self, chapter: int, title: str) -> str:
        return os.path.join(
            self.experiments_dir, f"实验{chapter:02d}_{title}.md"
        )

    def chapter_path(self, chapter_num: int, title_hint: str = "") -> str:
        suffix = f"-{title_hint}" if title_hint else ""
        return os.path.join(self.output_dir, f"第{chapter_num}章{suffix}.md")

    def ensure_dirs(self):
        """确保所有输出子目录存在。"""
        if not self._project_root:
            return
        for d in [self.input_dir, self.output_dir, self.writing_guide_dir,
                  self.cases_dir, self.experiments_dir, self.exercise_dir]:
            os.makedirs(d, exist_ok=True)

    # ── 参考教材 ──

    @property
    def source_books(self) -> List[Dict]:
        """按 priority 升序返回所有参考教材列表。"""
        books = list(self._cfg.get("source_books", []))
        return sorted(books, key=lambda b: b.get("priority", 99))

    def get_book_by_author(self, author: str) -> Optional[Dict]:
        """按作者名查找教材。"""
        for b in self.source_books:
            if b.get("author") == author:
                return b
        return None

    # ── 知识库（可选） ──

    @property
    def kb_processed_dir(self) -> Optional[str]:
        return self._cfg.get("knowledge_base", {}).get("processed_dir")

    @property
    def kb_raw_dir(self) -> Optional[str]:
        return self._cfg.get("knowledge_base", {}).get("raw_dir")

    @property
    def kb_domain_dir(self) -> Optional[str]:
        return self._cfg.get("knowledge_base", {}).get("domain_dir")

    # ── 工作流 ──

    @property
    def workflow_mode(self) -> str:
        return self._cfg.get("workflow", {}).get("default_mode", "fast")

    @property
    def phase_0_5_auto(self) -> bool:
        return self._cfg.get("workflow", {}).get("phase_0_5_auto", True)

    @property
    def quality_auto_fix(self) -> bool:
        return self._cfg.get("workflow", {}).get("quality_auto_fix", True)

    # ── 体量 ──

    @property
    def thin_threshold_lines(self) -> int:
        return self._cfg.get("volume", {}).get("thin_threshold_lines", 700)

    @property
    def thin_threshold_kb(self) -> int:
        return self._cfg.get("volume", {}).get("thin_threshold_kb", 35)

    @property
    def target_mermaid_min(self) -> int:
        return self._cfg.get("volume", {}).get("target_mermaid_min", 6)

    # ── 快捷方法 ──

    def grep_all_books(self, keyword: str, head: int = 5) -> dict:
        """在所有参考教材中搜索关键词。"""
        import subprocess

        results = {}
        for book in self.source_books:
            name = book.get("display_name", "?")
            path = book.get("path", "")
            if not path or not os.path.exists(path):
                results[name] = []
                continue
            try:
                out = subprocess.check_output(
                    ["grep", "-n", keyword, path],
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                ).decode("utf-8", errors="replace")
                lines = out.strip().split("\n")[:head]
                results[name] = lines
            except subprocess.CalledProcessError:
                results[name] = []
        return results

    # ── 缓存 ──

    @staticmethod
    def get_default():
        """返回全局缓存实例（无 project root）。"""
        global _SKILL_CONFIG_CACHE
        if _SKILL_CONFIG_CACHE is None:
            _SKILL_CONFIG_CACHE = Config()
        return _SKILL_CONFIG_CACHE


def main():
    """Shell 入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="book-build 配置工具")
    parser.add_argument("--project", "-p", help="项目根目录")
    parser.add_argument("--setup", action="store_true", help="初始化项目目录结构")
    parser.add_argument("--show", action="store_true", help="显示配置摘要")
    parser.add_argument("attr", nargs="?", help="获取指定属性值")
    args = parser.parse_args()

    if args.setup:
        if not args.project:
            print("❌ --setup 需要 --project 参数")
            sys.exit(1)
        Config.setup(args.project)
        return

    if args.project:
        cfg = Config(project_root=args.project)
    else:
        cfg = Config()

    if args.attr:
        val = getattr(cfg, args.attr, None)
        if val is not None:
            print(val)
        else:
            print(f"❌ 无此属性: {args.attr}", file=sys.stderr)
            sys.exit(1)
    elif args.show:
        print(f"教材: {cfg.textbook_name or '(未配置)'}")
        print(f"项目: {cfg.project_root or '(未指定)'}")
        print(f"输入: {cfg.input_dir}")
        print(f"输出: {cfg.output_dir}")
        print(f"  写作大纲: {cfg.writing_guide_dir}")
        print(f"  案例:     {cfg.cases_dir}")
        print(f"  实验:     {cfg.experiments_dir}")
        print(f"  习题解答: {cfg.exercise_dir}")
        print(f"模式: {cfg.workflow_mode}")
        books = cfg.source_books
        if books:
            print(f"参考教材 ({len(books)} 本):")
            for i, b in enumerate(books, 1):
                print(f"  {i}. {b.get('author','?')}《{b.get('display_name','?')}》")
        else:
            print("参考教材: (未配置)")
    else:
        print(f"教材: {cfg.textbook_name or '(未配置)'}")
        print(f"项目: {cfg.project_root or '(未指定)'}")
        if cfg.project_root:
            print("使用 --show 查看详情")


if __name__ == "__main__":
    main()
