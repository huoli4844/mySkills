#!/usr/bin/env python3
"""
setup_project.py — 新建教材项目，自动创建目录结构 + 默认配置 + .gitignore。
用法：
  python3 setup_project.py /path/to/新教材目录 --name "电磁兼容教材" --outline 教材提纲.docx

输出：
  /path/to/新教材目录/
    book-build.yaml      ← 项目配置（教材名 + 参考书空模板）
    .gitignore            ← 默认忽略规则
    input/                ← 放提纲文件
    output/               ← 输出目录
    output/写作大纲/       ← 各章写作大纲
    output/实验/           ← 实验
    output/案例/           ← 案例
    output/习题解答/        ← 习题解答
"""

import os
import sys
import shutil
import argparse
from pathlib import Path


DEFAULT_GITIGNORE = """# OS
.DS_Store

# IDE
.idea/
*.swp
*.swo

# Hermes temp
.hermes-tmp.*

# Backup
*.bak
*.bak2
*.orig

# Temp scripts
output/fix_*.py

# Audit artifacts (regenerated each run)
output/补充与完善分析报告.md
output/补充执行清单.json
"""

DEFAULT_YAML = """# =============================================================================
# book-build 项目配置
# =============================================================================

# --- 教材信息 ---
textbook:
  name: "{name}"
  outline_file: "{outline}"

# --- 参考教材配置 ---
# 按 priority 排序，数字越小优先级越高
# path: 参考教材处理后的 Markdown 文件路径
source_books:
  # - display_name: "工程电磁兼容（第3版）"
  #   author: "路宏敏"
  #   priority: 1
  #   path: "/path/to/参考书.md"
"""


def setup(project_root: str, textbook_name: str, outline_file: str):
    root = Path(project_root).expanduser().resolve()
    
    if root.exists() and any(root.iterdir()):
        print(f"⚠️  目录已存在且不为空: {root}")
        print("   继续执行将创建缺失的子目录，不会覆盖已有文件。")
    
    # 创建目录结构
    dirs = [
        root,
        root / "input",
        root / "output",
        root / "output" / "写作大纲",
        root / "output" / "实验",
        root / "output" / "案例",
        root / "output" / "习题解答",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {'已存在' if any(d.iterdir()) else '已创建'}: {d.name}/")
    
    # 创建 book-build.yaml（不覆盖已有）
    yaml_path = root / "book-build.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(
            DEFAULT_YAML.format(name=textbook_name, outline=outline_file),
            encoding="utf-8"
        )
        print(f"  📝 已创建: book-build.yaml")
    else:
        print(f"  ⏭️  已存在: book-build.yaml")
    
    # 创建 .gitignore（不覆盖已有）
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print(f"  📝 已创建: .gitignore")
    else:
        print(f"  ⏭️  已存在: .gitignore")
    
    # 提示用户放入提纲文件
    outline_path = root / "input" / outline_file
    if not outline_path.exists():
        print(f"\n  ⚠️  请将提纲文件放入: {outline_path}")
    else:
        print(f"  ✅ 提纲文件已就绪: {outline_path}")
    
    print(f"\n✅ 项目初始化完成: {root}")
    print(f"   下一步: 编辑 book-build.yaml 填入参考教材路径")
    print(f"   然后: 运行 generate_outlines.py 生成写作大纲")


def main():
    parser = argparse.ArgumentParser(
        description="新建教材项目，自动创建目录结构和默认配置"
    )
    parser.add_argument("project_root", help="新建或已有的项目目录")
    parser.add_argument("--name", default="电磁兼容教材", help="教材名称（默认：电磁兼容教材）")
    parser.add_argument("--outline", default="教材提纲.docx", help="提纲文件名（放在 input/ 下）")
    args = parser.parse_args()
    
    setup(args.project_root, args.name, args.outline)


if __name__ == "__main__":
    main()
