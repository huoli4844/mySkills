#!/usr/bin/env python3
"""
renumber.py — 公式编号统一重排脚本（合并 fix_formula_numbers +
clean_formula_numbers + fix_tag_placement 功能，消除功能重叠和截断 bug）。

用法:
    python3 scripts/renumber.py output/第N章.md              # 重排（自动备份）
    python3 scripts/renumber.py output/第N章.md --dry-run    # 预览改动
    python3 scripts/renumber.py output/第N章.md --chapter 8  # 指定章号

流程：
    1. 自动备份（.bak）
    2. 修复孤立 \tag{}（$$ 外部的 tag → 移入 $$ 内部）
    3. 清理 >$$ 引用块格式（>$$ → $$，删除 > 引用行）
    4. 删除连续 $$ 行（空块）
    5. 检测并修复未闭合 $$
    6. 转换单行 $$inline$$ 为多行 block 格式
    7. 清除所有旧编号
    8. 按出现顺序分配连续编号 N-1, N-2, ...
    9. 验证无重复编号

注意：对于有复杂格式问题的文件（>$$ + 未闭合 $$ 同时出现），
推荐使用 batch_fix_formula_numbers.py（行级状态机，更稳健）。
"""

import re
import sys
import os
import shutil


def backup(path):
    """创建 .bak 备份，不覆盖已有备份。"""
    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        return bak
    return bak  # 已存在


def detect_chapter(path, content):
    """从文件名或已有 tag 推断章号。"""
    m = re.search(r"第(\d+)章", os.path.basename(path))
    if m:
        return m.group(1)
    m = re.search(r"Ch(\d+)", os.path.basename(path), re.IGNORECASE)
    if m:
        return m.group(1)
    existing = re.findall(r"tag\{(\d+)-\d+\}", content)
    if existing:
        return existing[0]
    return "1"


def fix_orphan_tags(lines):
    """将 $$ 外部的孤立 \tag{} 移入最近的 $$ 块。"""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # 孤立 tag（后面紧邻 $$）
        if re.match(r"^\\tag\{\d+-\d+\}$", stripped):
            lookahead = None
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip():
                    lookahead = lines[j].strip()
                    break
            if lookahead == "$$":
                # 找到该 $$ 块的闭合 $$
                close_idx = None
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == "$$":
                        close_idx = j
                        break
                if close_idx:
                    out.append(line)  # 输出 tag 行
                    # 输出 $$ 开始
                    # 找到实际的开 $$（i+1 行开始第一个非空）
                    open_idx = i + 1
                    while open_idx < len(lines) and not lines[open_idx].strip():
                        open_idx += 1
                    out.append(lines[i + 1])  # $$
                    # 中间内容
                    for k in range(i + 2, close_idx):
                        out.append(lines[k])
                    out.append(stripped)  # tag 在闭合 $$ 前
                    out.append("$$")
                    i = close_idx + 1
                    continue
        out.append(line)
        i += 1
    return out


def convert_inline_blocks(text):
    """将单行 $$inline$$ 转换为多行 $$ \\n content \\n tag \\n $$ 格式。"""
    return re.sub(
        r"\$\$(.+?)\$\$",
        lambda m: "$$\n" + m.group(1).strip() + "\n\\tag{XX-XX}\n$$",
        text,
    )


def renumber(path, chapter=None, dry_run=False):
    """主函数：修复并重排编号。"""
    original = open(path, "r", encoding="utf-8").read()

    # 推断章号
    if chapter is None:
        chapter = detect_chapter(path, original)

    lines = original.split("\n")

    # Step 1: 修复孤立 tag
    lines = fix_orphan_tags(lines)

    # Step 2: 清理 >$$ 引用块格式
    lines = [re.sub(r'^>\s*\$\$', '$$', l) for l in lines]
    lines = [l for l in lines if l.strip() != '>']

    # Step 3: 删除连续 $$ 对（空块）
    changed = True
    while changed:
        tmp = []
        i = 0
        changed = False
        while i < len(lines):
            if i+1 < len(lines) and lines[i].strip() == '$$' and lines[i+1].strip() == '$$':
                i += 2
                changed = True
                continue
            tmp.append(lines[i])
            i += 1
        lines = tmp

    # Step 4: 检测并修复未闭合 $$
    in_f = False
    for i, line in enumerate(lines):
        if line.strip() == '$$':
            in_f = not in_f
    if in_f:
        # 找到最后一个 $$（未闭合），在其后第一个公式内容行后插入 $$
        for i in range(len(lines) - 1, max(0, len(lines) - 10), -1):
            if lines[i].strip() == '$$':
                for j in range(i + 1, min(len(lines), i + 10)):
                    if lines[j].strip() and lines[j].strip() != '$$':
                        lines.insert(j + 1, '$$')
                        break
                break

    text = "\n".join(lines)

    # Step 5: 转换单行 inline $$ 为多行 block
    text = convert_inline_blocks(text)

    # Step 6: 移除所有临时/占位编号
    for pat in [
        r"\\\\tag\{XX-XX\}",
        r"\\\\tag\{\d+-\d+\}",
        r"\\tag\{XX-XX\}",
        r"\\tag\{\d+-\d+\}",
    ]:
        text = re.sub(pat, "", text)

    # Step 7: 重新编号所有 $$...$$ 块
    eq_pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
    parts = []
    pos = 0
    counter = 0
    for m in eq_pattern.finditer(text):
        parts.append(text[pos : m.start()])
        eq_text = m.group(1)
        counter += 1
        # 清理残留 tag
        eq_text = re.sub(r"\\{0,2}tag\{\d+-\d+\}", "", eq_text)
        content_lines = [l for l in eq_text.split("\n") if l.strip()]
        clean = "\n".join(content_lines)
        clean += f"\n\\tag{{{chapter}-{counter}}}"
        parts.append("$$\n" + clean + "\n$$")
        pos = m.end()
    parts.append(text[pos:])
    result = "".join(parts)

    # 验证
    final_tags = re.findall(r"tag\{(\d+-\d+)\}", result)
    from collections import Counter

    dups = {k: v for k, v in Counter(final_tags).items() if v > 1}

    if dry_run:
        print(f"[DRY RUN] {path}")
        print(f"  章号: {chapter}")
        print(f"  公式块: {len(list(eq_pattern.finditer(text)))}")
        print(f"  编号后: {len(final_tags)} 个标签")
        if dups:
            print(f"  ⚠️ 会重复: {dups}")
        return True

    # Step 8: 备份 + 写入
    bak = backup(path)
    open(path, "w", encoding="utf-8").write(result)

    # 最终统计
    stats = f"""
📊 {path}
   章号前缀: {chapter}
   备份: {bak}
   公式块: {len(final_tags)}
   编号: {chapter}-1 ~ {chapter}-{len(final_tags)}
   重复: {'❌ ' + str(dups) if dups else '✅ 无'}
   连续: {'✅' if _check_sequential(final_tags, chapter) else '❌'}
"""
    print(stats)
    return not dups


def _check_sequential(tags, chapter):
    """检查编号是否连续。"""
    nums = []
    for t in tags:
        parts = t.split("-")
        if parts[0] == chapter:
            nums.append(int(parts[1]))
    return nums == list(range(1, len(nums) + 1))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="公式编号统一重排")
    parser.add_argument("path", help="文件路径（支持 glob 如 output/第8章-*.md）")
    parser.add_argument("--chapter", "-c", help="指定章号（默认自动检测）")
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="预览模式（不改文件）"
    )
    args = parser.parse_args()

    # 支持 glob
    import glob as glob_mod

    files = glob_mod.glob(args.path) or [args.path]
    for f in files:
        if not os.path.exists(f):
            print(f"❌ 文件不存在: {f}", file=sys.stderr)
            continue
        renumber(f, chapter=args.chapter, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
