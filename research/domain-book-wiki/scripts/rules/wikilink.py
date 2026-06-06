"""rules/wikilink.py — Wikilink 有效性检查 + 自动修复"""

import os
import re
from difflib import get_close_matches

from log_utils import get_logger

log = get_logger(__name__)

__all__ = [
    "_find_md_file",
    "check_wikilink_validity",
    "auto_fix_wikilinks",
    "get_all_md_filenames",
]


def _find_md_file(target: str, wiki_root: str) -> bool:
    """在 wiki_root 目录树下搜索 target.md 是否存在。"""
    clean = target.split("|")[0].strip()
    if not clean:
        return False

    direct = os.path.join(wiki_root, clean + ".md")
    if os.path.isfile(direct):
        return True

    for _root, _dirs, files in os.walk(wiki_root):
        for f in files:
            if f == clean + ".md":
                return True
            if f.endswith(".md") and f[:-3] == os.path.basename(clean):
                return True
    return False


def check_wikilink_validity(filepath: str, wiki_root: str) -> list[tuple[str, str, str]]:
    """验证文件中所有 wikilink 的有效性。"""
    results = []

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        log.warning(f"文件读取失败 ({filepath}): {e}")
        return results

    name = os.path.basename(filepath).replace(".md", "")
    label = f"wikilink/{name}"

    wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
    if not wikilinks:
        return results

    broken: list[str] = []
    for wl in wikilinks:
        if wl.startswith(("http://", "https://", "#")):
            continue
        if re.search(r"\.(png|jpg|jpeg|gif|svg|pdf|mp4|mov|avi)\b", wl, re.IGNORECASE):
            continue
        if not _find_md_file(wl, wiki_root):
            broken.append(wl)

    if broken:
        results.append(
            ("WARN", "WikilinkValidity",
             f"[{label}] {len(broken)} 个断裂 wikilink: {'; '.join(broken[:10])}"
             + ("..." if len(broken) > 10 else ""))
        )

    return results


def get_all_md_filenames(wiki_root: str) -> set[str]:
    """收集 wiki_root 下所有 .md 文件的基础名（不含扩展名和目录前缀）。"""
    filenames: set[str] = set()
    for root, _dirs, files in os.walk(wiki_root):
        for f in files:
            if f.endswith(".md"):
                filenames.add(f[:-3])  # strip .md
    return filenames


def auto_fix_wikilinks(
    wiki_root: str,
    dry_run: bool = False,
    min_confidence: float = 0.4,
) -> dict:
    """自动修复断裂 wikilink。

    扫描 wiki_root 下所有 .md 文件，检测断裂的 [[wikilink]]，
    使用模糊匹配找到最接近的已存在文件，自动替换。

    Args:
        wiki_root: 知识库根目录
        dry_run: True 时只报告不修改
        min_confidence: 模糊匹配最低相似度 (0-1)

    Returns:
        {"total_broken": N, "fixed": N, "skipped": N, "details": [...]}
    """
    all_filenames = get_all_md_filenames(wiki_root)
    
    # 收集所有 .md 文件
    md_files: list[str] = []
    for root, _dirs, files in os.walk(wiki_root):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))
    
    total_broken = 0
    fixed_count = 0
    skipped_count = 0
    details: list[dict] = []
    
    for filepath in md_files:
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            log.warning(f"读取失败 ({filepath}): {e}")
            continue
        
        # 提取所有 wikilink
        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
        modified = content
        file_fixes = []
        
        for wl in wikilinks:
            # 跳过外部链接和媒体引用
            if wl.startswith(("http://", "https://", "#")):
                continue
            if re.search(r"\.(png|jpg|jpeg|gif|svg|pdf|mp4|mov|avi)\b", wl, re.IGNORECASE):
                continue
            
            # 解析目标和别名
            parts = wl.split("|", 1)
            target = parts[0].strip()
            alias = parts[1].strip() if len(parts) > 1 else ""
            
            # 检查是否存在
            if _find_md_file(target, wiki_root):
                continue
            
            total_broken += 1
            
            # 提取基础名用于模糊匹配
            base_target = target.split("/")[-1] if "/" in target else target
            
            # 模糊匹配
            matches = get_close_matches(base_target, list(all_filenames), n=3, cutoff=min_confidence)
            
            if not matches:
                skipped_count += 1
                details.append({
                    "file": os.path.relpath(filepath, wiki_root),
                    "broken": wl,
                    "fixed_to": None,
                    "reason": "no_match",
                })
                continue
            
            best_match = matches[0]
            
            # 构建新的 wikilink：保留目录前缀逻辑
            # 如果原链接有目录前缀，保持格式
            if "/" in target:
                # 找到匹配文件的完整路径
                matched_path = None
                for root, _dirs, files in os.walk(wiki_root):
                    if best_match + ".md" in files:
                        matched_path = os.path.relpath(
                            os.path.join(root, best_match + ".md"), wiki_root
                        )
                        break
                if matched_path:
                    new_target = matched_path[:-3]  # strip .md
                else:
                    new_target = best_match
            else:
                # 找到匹配文件所在的子目录
                matched_rel = None
                for root, _dirs, files in os.walk(wiki_root):
                    if best_match + ".md" in files:
                        matched_rel = os.path.relpath(
                            os.path.join(root, best_match + ".md"), wiki_root
                        )
                        break
                if matched_rel:
                    new_target = matched_rel[:-3]  # strip .md
                else:
                    new_target = best_match
            
            # 构建替换后的 wikilink
            if alias:
                new_wl = f"[[{new_target}|{alias}]]"
            else:
                new_wl = f"[[{best_match}]]"
            
            # 替换
            old_wl = f"[[{wl}]]"
            modified = modified.replace(old_wl, new_wl)
            
            fixed_count += 1
            details.append({
                "file": os.path.relpath(filepath, wiki_root),
                "broken": wl,
                "fixed_to": new_wl,
                "reason": f"fuzzy_match({best_match}, score={matches})",
            })
        
        # 写回文件
        if modified != content and not dry_run:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(modified)
            except Exception as e:
                log.warning(f"写入失败 ({filepath}): {e}")
    
    return {
        "total_broken": total_broken,
        "fixed": fixed_count,
        "skipped": skipped_count,
        "details": details,
    }
