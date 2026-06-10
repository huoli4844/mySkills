#!/usr/bin/env python3
"""
⚠️ DEPRECATED — 请使用 scripts/renumber.py 代替。

本脚本已与 fix_formula_numbers.py、clean_formula_numbers.py 合并为
统一的 renumber.py。功能更强、且修复了截断 bug。
留此文件仅用于向后兼容，新开发请用 renumber.py。
"""

import sys

if __name__ == "__main__":
    print("⚠️  fix_tag_placement.py 已废弃，请用: python3 scripts/renumber.py <file>")
    sys.exit(1)
