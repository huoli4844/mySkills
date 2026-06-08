#!/usr/bin/env python3
"""
audit_wmf_formulas.py — 审计 WMF 公式与 YAML 公式内容的匹配情况

扫描 BOOK_DIR/20_正文/ 下所有 .md 文件，提取 WMF 图片引用及其公式编号，
读取 WMF 二进制内容获取可读文本片段，然后与 .dag/ 下 YAML 的
mathematical_model 字段中的公式进行交叉对比，输出差异报告。

用法:
    python audit_wmf_formulas.py --book-dir /path/to/book
    python audit_wmf_formulas.py --book-dir /path/to/book --dry-run
    python audit_wmf_formulas.py --book-dir /path/to/book --verbose
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ── 常量 ──────────────────────────────────────────────────────────────
TEXT_DIR = "20_正文"
DAG_DIR = ".dag"
ASSETS_DIR = "assets"

# WMF 文件中常见的字体/软件名称，应排除
KNOWN_FONTS: Set[str] = {
    "MathType", "Times New Roman", "Symbol", "MT Extra",
    "System", "Times", "deciBel", "Arial", "Courier New",
    "Helvetica", "MTExtra", "MT", "Extra",
}


# ═══════════════════════════════════════════════════════════════════════
#   WMF 二进制解析
# ═══════════════════════════════════════════════════════════════════════

def extract_wmf_chars(wmf_path: str) -> Tuple[List[str], List[str]]:
    """从 WMF 二进制文件中提取字符信息。

    MathType 创建的 WMF 公式以 PostScript/EPS 方式存储，
    字符信息分散在二进制数据中，本函数从多个启发式模式中
    尽可能提取。

    Returns:
        (long_strings, single_chars) —— 长串和单字符列表
    """
    try:
        with open(wmf_path, "rb") as f:
            data = f.read()
    except (FileNotFoundError, PermissionError):
        return [], []

    # ── 策略 1：strings 式连续可打印 ASCII ──
    long_strings: List[str] = []
    current: List[str] = []
    for b in data:
        if 32 <= b <= 126:
            current.append(chr(b))
        else:
            if len(current) >= 2:
                long_strings.append("".join(current))
            current = []
    if len(current) >= 2:
        long_strings.append("".join(current))

    # ── 策略 2：MathType 单字符记录 ──
    # 两个偏移模式都尝试
    single_chars: List[str] = []
    for offset in (0, 4):  # 偏移 0 和偏移 4 两种模式
        i = offset
        while i < len(data) - 9:
            if (data[i] == 0x01 and data[i+1] == 0x00
                    and data[i+2] == 0x00 and data[i+3] == 0x00):
                char_byte = data[i+4]
                if 40 <= char_byte <= 126:  # 包括字母、数字、常见运算符
                    # 避免重复 (检查前几个字符是否相同)
                    next_byte = data[i+5] if i+5 < len(data) else 0xFF
                    prev_byte = data[i-1] if i > 0 else 0xFF
                    # 仅当字符后面是 0x00 或前面是非字母时才记录
                    if next_byte == 0x00 or not (32 <= prev_byte <= 126):
                        single_chars.append(chr(char_byte))
            i += 1

    return long_strings, single_chars


def filter_wmf_text(long_strings: List[str], single_chars: List[str]) -> Dict[str, List[str]]:
    """过滤 WMF 提取的文本，返回有意义的部分。"""
    meaningful: List[str] = []
    for s in long_strings:
        s = s.strip()
        if not s or len(s) < 2:
            continue
        # 排除已知字体
        if s in KNOWN_FONTS:
            continue
        # 排除纯数字/标点
        if re.match(r'^[\d\W]+$', s):
            continue
        meaningful.append(s)

    # 单字符去重保序
    seen: Set[str] = set()
    unique_chars: List[str] = []
    for c in single_chars:
        if c not in seen:
            seen.add(c)
            unique_chars.append(c)

    return {
        "long_strings": meaningful,
        "single_chars": unique_chars,
    }


# ═══════════════════════════════════════════════════════════════════════
#   Markdown 解析
# ═══════════════════════════════════════════════════════════════════════

def extract_wmf_refs(md_path: str) -> List[Tuple[str, str, int]]:
    """从 .md 文件中提取 (WMF 文件名, 公式编号, 行号) 元组。

    模式: ![](assets/image-XXX.wmf) (N-XX)
    也处理多图共享一个编号的情况。
    """
    refs: List[Tuple[str, str, int]] = []
    wmf_pattern = re.compile(r'!\[.*?\]\(assets/(image-\d+\.wmf)\)')
    num_pattern = re.compile(r'\((\d+-\d+)\)')

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return refs

    for lineno, line in enumerate(lines, 1):
        wmfs = wmf_pattern.findall(line)
        nums = num_pattern.findall(line)
        if not wmfs or not nums:
            continue
        for wmf in wmfs:
            refs.append((wmf, nums[0], lineno))

    return refs


# ═══════════════════════════════════════════════════════════════════════
#   YAML 解析
# ═══════════════════════════════════════════════════════════════════════

def extract_yaml_formulas(yaml_path: str) -> Dict[str, str]:
    """从 YAML 文件的 mathematical_model 字段中提取 {公式编号: 公式内容} 映射。"""
    import yaml as yaml_lib

    formulas: Dict[str, str] = {}
    formula_num_pattern = re.compile(r'\((\d+-\d+)\)')

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml_lib.safe_load(f)
    except Exception:
        return formulas

    if not data or not isinstance(data, list):
        return formulas

    for item in data:
        if not isinstance(item, dict):
            continue
        bd = item.get("bd", {})
        if not isinstance(bd, dict):
            continue
        mm = bd.get("mathematical_model", "")
        if not isinstance(mm, str) or not mm.strip():
            continue

        # 提取 formula_references 中的编号用于补充
        fr = bd.get("formula_references", "")
        fr_nums = set()
        if isinstance(fr, str):
            fr_nums = set(re.findall(r'(\d+-\d+)', fr))

        # 从 mathematical_model 中提取编号
        mm_nums = set(re.findall(r'(\d+-\d+)', mm))

        all_nums = mm_nums | fr_nums
        for num in all_nums:
            if num not in formulas:
                formulas[num] = mm

    return formulas


def scan_dag_formulas(book_dir: str) -> Dict[str, Dict[str, str]]:
    """扫描 .dag/ 下所有 yaml，返回 {章节号: {公式编号: 公式内容}}。"""
    dag_path = Path(book_dir) / DAG_DIR
    if not dag_path.exists():
        return {}

    result: Dict[str, Dict[str, str]] = {}
    for ch_dir in sorted(dag_path.iterdir()):
        if not ch_dir.is_dir():
            continue
        ch_name = ch_dir.name
        ch_match = re.match(r'第(\d+)章', ch_name)
        if not ch_match:
            continue
        ch_num = ch_match.group(1)

        data_dir = ch_dir / "data"
        if not data_dir.exists():
            continue

        ch_formulas: Dict[str, str] = {}
        for yaml_file in data_dir.glob("*.yaml"):
            if yaml_file.name.startswith("."):
                continue
            try:
                formulas = extract_yaml_formulas(str(yaml_file))
                ch_formulas.update(formulas)
            except Exception:
                continue

        if ch_formulas:
            result[ch_num] = ch_formulas

    return result


# ═══════════════════════════════════════════════════════════════════════
#   比较逻辑
# ═══════════════════════════════════════════════════════════════════════

def extract_key_tokens(text: str) -> Set[str]:
    """从公式文本中提取关键 token 集合，用于模糊匹配。"""
    tokens: Set[str] = set()

    # LaTeX 命令: \alpha, \beta, \theta
    tokens.update(re.findall(r'\\[a-zA-Z]+', text))

    # 独立标识符：E, H, B, D, J, V, I, R, C, L, Z, 等
    # 希腊字母的近似拉丁拼写
    greek_like = r'θωφλπμερδησΦΛΩΠΣ'
    tokens.update(re.findall(rf'(?<![a-zA-Z])([A-Za-z{greek_like}])(?![a-zA-Z])', text))

    # 操作符
    tokens.update(re.findall(r'[+\-*/×·=≈<>]', text))

    # 数字常量
    tokens.update(re.findall(r'\b\d+\b', text))

    return tokens


def compare_wmf_yaml(
    wmf_data: Dict[str, List[str]],
    yaml_formula: str,
) -> Tuple[float, List[str], str]:
    """比较 WMF 文本片段与 YAML 公式内容。

    Returns:
        (similarity_score, matched_tokens, brief_explanation)
    """
    yaml_tokens = extract_key_tokens(yaml_formula)

    # 从 WMF 长串中提取 token
    wmf_text = " ".join(wmf_data.get("long_strings", []))
    wmf_chars = "".join(wmf_data.get("single_chars", []))
    wmf_combined = wmf_text + " " + wmf_chars
    wmf_tokens = extract_key_tokens(wmf_combined)

    if not yaml_tokens:
        return 1.0, [], "YAML 公式无实质数学token"

    if not wmf_tokens and not wmf_chars:
        return 0.0, [], "WMF 未提取到任何字符信息"

    # 计算匹配度
    matched = yaml_tokens & wmf_tokens
    score = len(matched) / len(yaml_tokens)

    if score == 0 and wmf_chars:
        # 尝试逐个字符匹配
        wmf_char_set = set(wmf_chars)
        char_matches = [t for t in yaml_tokens if t in wmf_char_set and len(t) == 1]
        if char_matches:
            score = len(char_matches) / len(yaml_tokens) * 0.5  # 权重减半

    return score, list(matched), f"tok_match={len(matched)}/{len(yaml_tokens)}"


# ═══════════════════════════════════════════════════════════════════════
#   主审计逻辑
# ═══════════════════════════════════════════════════════════════════════

def audit_book(book_dir: str, dry_run: bool = False, verbose: bool = False) -> Dict:
    """执行审计，返回结果字典。"""
    book_path = Path(book_dir)
    text_path = book_path / TEXT_DIR

    if not text_path.exists():
        print(f"错误：{text_path} 不存在")
        sys.exit(1)

    # ── 步骤 1：扫描 .md 中所有 WMF 引用 ──
    print(f"{'[DRY-RUN] ' if dry_run else ''}[1/4] 扫描 {text_path}/ 下 *.md ...")
    all_refs: Dict[str, List[Tuple[str, str, int, str]]] = defaultdict(list)
    # {ch_num: [(wmf_name, formula_num, lineno, md_file)]}

    for md_file in sorted(text_path.glob("*.md")):
        ch_match = re.match(r'第(\d+)章', md_file.stem)
        if not ch_match:
            continue
        ch_num = ch_match.group(1)
        refs = extract_wmf_refs(str(md_file))
        if refs:
            for wmf_name, formula_num, lineno in refs:
                all_refs[ch_num].append((wmf_name, formula_num, lineno, md_file.name))
            print(f"   {md_file.name}: 发现 {len(refs)} 个公式引用")

    total_refs = sum(len(refs) for refs in all_refs.values())
    unique_formula_nums: Set[str] = set()
    for refs in all_refs.values():
        for _, fnum, _, _ in refs:
            unique_formula_nums.add(fnum)
    print(f"  共计 {total_refs} 个公式引用（{len(unique_formula_nums)} 个唯一公式编号）")

    if dry_run:
        print("\n[DRY-RUN] 跳过 WMF 二进制读取和 YAML 对比")
        return {"total": total_refs, "matched": 0, "unmatched": 0, "warnings": []}

    # ── 步骤 2：读取 WMF 二进制内容 ──
    print("\n[2/4] 读取 WMF 文件文本片段 ...")
    assets_path = text_path / ASSETS_DIR
    wmf_cache: Dict[str, Dict[str, List[str]]] = {}
    wmf_errors: List[str] = []

    for ch_num, refs in all_refs.items():
        for wmf_name, formula_num, lineno, md_file in refs:
            if wmf_name in wmf_cache:
                continue
            wmf_path = assets_path / wmf_name
            if not wmf_path.exists():
                wmf_errors.append(f"{wmf_name}: 文件不存在")
                wmf_cache[wmf_name] = {"long_strings": [], "single_chars": []}
                continue
            long_strs, single_chars = extract_wmf_chars(str(wmf_path))
            wmf_cache[wmf_name] = filter_wmf_text(long_strs, single_chars)
            if not wmf_cache[wmf_name]["long_strings"] and not wmf_cache[wmf_name]["single_chars"]:
                wmf_errors.append(f"{wmf_name}: 未提取到有效文本片段")

    print(f"  已处理 {len(wmf_cache)} 个 WMF 文件")
    if wmf_errors and verbose:
        for e in wmf_errors[:10]:
            print(f"   [!] {e}")

    # ── 步骤 3：提取 YAML 公式 ──
    print("\n[3/4] 提取 YAML 公式内容 ...")
    dag_formulas = scan_dag_formulas(book_dir)
    total_yaml = sum(len(fs) for fs in dag_formulas.values())
    print(f"  从 {len(dag_formulas)} 章的 YAML 中发现 {total_yaml} 个公式编号")

    if verbose:
        for ch_num, fs in sorted(dag_formulas.items()):
            print(f"   第{ch_num}章: {sorted(fs.keys())}")

    # ── 步骤 4：匹配与比较 ──
    print("\n[4/4] 执行匹配与比较 ...")
    warnings: List[str] = []
    matched_count = 0
    unmatched_count = 0
    matched_details: List[Dict] = []

    # 追踪每个唯一公式编号的匹配结果
    formula_match_stats: Dict[str, Tuple[str, float]] = {}  # fnum -> (status, score)

    for ch_num, refs in all_refs.items():
        ch_yaml = dag_formulas.get(ch_num, {})

        for wmf_name, formula_num, lineno, md_file in refs:
            # 检查该公式编号是否在 YAML 中出现
            if formula_num not in ch_yaml:
                warn_key = f"[MISSING] {md_file} line {lineno}"
                msg = f"公式 {formula_num}（{wmf_name}）在 YAML 中未找到对应 mathematical_model"
                full_msg = f"{warn_key} — {msg}"
                if full_msg not in [w.split(" — ", 1)[1] if " — " in w else w for w in warnings]:
                    warnings.append(full_msg)
                unmatched_count += 1
                formula_match_stats[formula_num] = ("MISSING", 0.0)
                continue

            yaml_content = ch_yaml[formula_num]
            wmf_data = wmf_cache.get(wmf_name, {"long_strings": [], "single_chars": []})

            if not wmf_data["long_strings"] and not wmf_data["single_chars"]:
                warn_key = f"[NO_TEXT] {md_file} line {lineno}"
                full_msg = f"{warn_key} — 公式 {formula_num}（{wmf_name}）WMF 无有效文本片段"
                warnings.append(full_msg)
                unmatched_count += 1
                continue

            score, matched_tokens, brief = compare_wmf_yaml(wmf_data, yaml_content)

            # 相似度阈值：低于 0.1 认为不匹配
            THRESHOLD = 0.1
            if score < THRESHOLD:
                warn_key = f"[MISMATCH] {md_file} line {lineno}"
                char_preview = "".join(wmf_data["single_chars"][:10])
                full_msg = (f"{warn_key} — 公式 {formula_num}（{wmf_name}）"
                           f" 相似度={score:.2f} ({brief})"
                           f" WMF字符: [{char_preview}]")
                warnings.append(full_msg)
                unmatched_count += 1
                formula_match_stats[formula_num] = ("MISMATCH", score)
            else:
                matched_count += 1
                if formula_num not in formula_match_stats:
                    formula_match_stats[formula_num] = ("MATCH", score)

            matched_details.append({
                "wmf": wmf_name,
                "formula_num": formula_num,
                "md_file": md_file,
                "lineno": lineno,
                "yaml_snippet": yaml_content[:80] + ("..." if len(yaml_content) > 80 else ""),
                "wmf_chars": "".join(wmf_data["single_chars"][:15]),
                "wmf_strings": wmf_data["long_strings"][:3],
                "similarity": round(score, 2),
                "brief": brief,
            })

    # ── 步骤 5：输出汇总报告 ──
    print("\n" + "=" * 70)
    print("  WMF 公式审计报告")
    print("=" * 70)

    # 统计唯一公式编号的匹配情况
    unique_total = len(unique_formula_nums)
    unique_matched = sum(1 for v in formula_match_stats.values() if v[0] == "MATCH")
    unique_missing = sum(1 for v in formula_match_stats.values() if v[0] == "MISSING")
    unique_mismatch = sum(1 for v in formula_match_stats.values() if v[0] == "MISMATCH")

    print(f"  扫描范围:         {text_path}")
    print(f"  扫描章节:         {sorted(all_refs.keys())}")
    print(f"  总公式引用数:     {total_refs}")
    print(f"  唯一公式编号数:   {unique_total}")
    print(f"  YAML 可查编号数:  {total_yaml} (跨 {len(dag_formulas)} 章)")
    print()
    print(f"  匹配数 (唯一):    {unique_matched}")
    print(f"  缺失数 (唯一):    {unique_missing}")
    print(f"  不匹配数 (唯一):  {unique_mismatch}")
    print(f"  总 WARN 数:       {len(warnings)}")
    print()

    if warnings:
        print("─" * 70)
        print("  WARN 清单（按类型分组）")
        print("─" * 70)

        missing_warns = [w for w in warnings if w.startswith("[MISSING]")]
        mismatch_warns = [w for w in warnings if w.startswith("[MISMATCH]")]
        notext_warns = [w for w in warnings if w.startswith("[NO_TEXT]")]

        if missing_warns:
            print(f"\n  1. 公式编号在 YAML 中缺失 ({len(missing_warns)} 条):")
            # 去重显示（只显示唯一公式编号）
            seen_nums: Set[str] = set()
            for w in missing_warns:
                m = re.search(r'公式 (\d+-\d+)', w)
                if m and m.group(1) not in seen_nums:
                    seen_nums.add(m.group(1))
                    md = re.search(r'([^/]+\.md)', w)
                    md_name = md.group(1) if md else "?"
                    print(f"      {m.group(1):>8s}  ({md_name})")

        if mismatch_warns:
            print(f"\n  2. WMF 与 YAML 内容不匹配 ({len(mismatch_warns)} 条):")
            for i, w in enumerate(mismatch_warns[:15], 1):
                # 截短显示
                short = w[:100] + "..." if len(w) > 100 else w
                print(f"      {short}")
            if len(mismatch_warns) > 15:
                print(f"      ... 还有 {len(mismatch_warns) - 15} 条")

        if notext_warns:
            print(f"\n  3. WMF 无有效文本片段 ({len(notext_warns)} 条):")
            for w in notext_warns[:10]:
                print(f"      {w}")

    # 打印部分匹配详情
    if matched_details and verbose:
        print("\n" + "─" * 70)
        print("  匹配详情样例")
        print("─" * 70)
        for d in matched_details[:15]:
            print(f"  {d['formula_num']:>8s} | {d['wmf']:<22s} | sim={d['similarity']:.2f}")
            chars = d.get('wmf_chars', '')
            if chars:
                print(f"          WMF chars: [{chars}]")
            print(f"          YAML: {d['yaml_snippet'][:55]}")
        if len(matched_details) > 15:
            print(f"  ... (共 {len(matched_details)} 条匹配)")

    return {
        "total_refs": total_refs,
        "unique_formulas": unique_total,
        "yaml_formulas": total_yaml,
        "matched": unique_matched,
        "missing": unique_missing,
        "mismatch": unique_mismatch,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


# ═══════════════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="审计 WMF 公式与 YAML 公式内容的匹配情况"
    )
    parser.add_argument(
        "--book-dir",
        default=os.environ.get("BOOK_DIR"),
        help="教材根目录（包含 20_正文/ 和 .dag/）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅扫描 .md 中的 WMF 引用，不读取 WMF 也不对比 YAML",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="输出更详细的匹配信息",
    )
    args = parser.parse_args()

    book_dir = args.book_dir
    if not book_dir:
        print("错误：请使用 --book-dir 指定教材根目录，或设置 BOOK_DIR 环境变量")
        sys.exit(1)

    if not os.path.isdir(book_dir):
        print(f"错误：{book_dir} 不是有效目录")
        sys.exit(1)

    result = audit_book(book_dir, dry_run=args.dry_run, verbose=args.verbose)

    # 非零退出码表示有问题
    if result["warning_count"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
