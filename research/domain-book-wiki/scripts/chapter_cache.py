"""chapter_cache.py — SHA256 增量缓存 (v46.0 新增, v47.0 版本感知)

借鉴 LLM Wiki 的 SHA256 增量缓存机制：
  1. 计算章节源文件的 SHA256
  2. 与上次成功的 hash 对比
  3. hash 相同 + YAML 完整 → 跳过，hash 不同 → 标记需要重新处理

v47.0 P2: 缓存版本感知
  - save 时记录 template_version + schema_version
  - check 时比较版本，版本不同 → 缓存失效
  - 新增 --invalidate-all 参数强制清空所有缓存

用法:
  python3 chapter_cache.py check -w BOOK_DIR -c 1   # 检查是否需要处理
  python3 chapter_cache.py save -w BOOK_DIR -c 1     # 保存当前 hash
  python3 chapter_cache.py list -w BOOK_DIR           # 列出所有章的缓存状态
  python3 chapter_cache.py invalidate-all -w BOOK_DIR  # 清空所有缓存
"""

import hashlib
import json
import os
import shutil

from dag_state import _load_state, _state_path
from log_utils import get_logger

log = get_logger(__name__)

HASH_FILE = ".source_hash"
VERSION_FILE = ".cache_version"
DEFAULT_VERSION = "1.0.0"


def _chapter_src(wr: str, ch: str) -> str | None:
    """查找章节源文件路径"""
    src_dir = os.path.join(wr, "20_正文")
    if not os.path.isdir(src_dir):
        return None
    for fname in sorted(os.listdir(src_dir)):
        if fname.startswith(f"第{ch}章") and fname.endswith(".md"):
            return os.path.join(src_dir, fname)
    return None


def _dag_dir(wr: str, ch: str) -> str:
    """章节 .dag 目录"""
    return os.path.join(wr, ".dag", f"第{ch}章")


def _hash_path(wr: str, ch: str) -> str:
    """hash 文件路径"""
    return os.path.join(_dag_dir(wr, ch), HASH_FILE)


def _version_path(wr: str, ch: str) -> str:
    """版本文件路径"""
    return os.path.join(_dag_dir(wr, ch), VERSION_FILE)


def _get_current_versions(wr: str) -> dict[str, str]:
    """获取当前模板版本和 schema 版本。
    
    优先从 .dag/config.yaml 读取，回退到 dag_constants 中的 BUILDER_CONFIG。
    
    Returns:
        {"template_version": "v6.0", "schema_version": "v47.0"}
    """
    versions = {"template_version": DEFAULT_VERSION, "schema_version": DEFAULT_VERSION}

    # 尝试从 .dag/config.yaml 读取
    config_path = os.path.join(wr, ".dag", "config.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if config:
                versions["template_version"] = str(config.get("template_version", DEFAULT_VERSION))
                versions["schema_version"] = str(config.get("schema_version", DEFAULT_VERSION))
        except Exception as e:
            log.debug(f"配置文件加载失败: {e}")
            pass

    # 回退：从 dag_constants BUILDER_CONFIG 取最新版本
    if versions["template_version"] == DEFAULT_VERSION:
        try:
            from dag_constants import BUILDER_CONFIG
            max_tv = DEFAULT_VERSION
            for cfg in BUILDER_CONFIG.values():
                tv = cfg.get("template_version", "")
                if tv and tv > max_tv:
                    max_tv = tv
            versions["template_version"] = max_tv
        except Exception as e:
            log.debug(f"BUILDER_CONFIG加载失败: {e}")
            pass

    return versions


def read_saved_versions(wr: str, ch: str) -> dict[str, str] | None:
    """读取上次保存的版本信息"""
    vp = _version_path(wr, ch)
    if os.path.exists(vp):
        try:
            with open(vp, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.debug(f"版本文件加载失败: {e}")
            return None
    return None


def save_versions(wr: str, ch: str, versions: dict[str, str]) -> None:
    """保存版本信息"""
    os.makedirs(_dag_dir(wr, ch), exist_ok=True)
    with open(_version_path(wr, ch), "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False)


def versions_match(wr: str, ch: str) -> bool:
    """检查当前版本与缓存版本是否一致。
    
    Returns:
        True 如果版本一致或无法获取版本信息（宽容模式）
    """
    current = _get_current_versions(wr)
    saved = read_saved_versions(wr, ch)
    if not saved:
        return True  # 无缓存版本 → 视为匹配（不阻断）
    for key in ("template_version", "schema_version"):
        if current.get(key) != saved.get(key):
            log.info(f"  版本变更: {key} {saved.get(key)} → {current.get(key)}")
            return False
    return True


def compute_sha256(filepath: str) -> str:
    """计算文件的 SHA256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_saved_hash(wr: str, ch: str) -> str | None:
    """读取上次保存的 hash"""
    hp = _hash_path(wr, ch)
    if os.path.exists(hp):
        with open(hp) as f:
            return f.read().strip()
    return None


def save_hash(wr: str, ch: str, hash_value: str) -> None:
    """保存 hash 值"""
    os.makedirs(_dag_dir(wr, ch), exist_ok=True)
    with open(_hash_path(wr, ch), "w") as f:
        f.write(hash_value)


def yaml_files_exist(wr: str, ch: str) -> bool:
    """检查 .dag/第N章/data/ 下是否所有必需 YAML 都存在"""
    from dag_state import WorkspacePaths
    data_dir = WorkspacePaths(wr).data_dir(ch)
    if not os.path.isdir(data_dir):
        return False
    # 至少需要一个 YAML 文件
    yamls = [f for f in os.listdir(data_dir) if f.endswith(".yaml") or f.endswith(".yml")]
    return len(yamls) > 0


def is_pipeline_complete(wr: str, book_id: str, ch: str) -> bool:
    """检查 pipeline 是否已全部完成"""
    sp = _state_path(wr, book_id, ch)
    if not os.path.exists(sp):
        return False
    from dag_constants import DAG_ORDER

    s = _load_state(sp)
    l1_phases = [
        ph
        for ph in DAG_ORDER
        if ph not in ("l2_indices", "l3_indices", "l4_indices")
    ]
    return all(
        s.get("phases", {}).get(ph, {}).get("status") in ("done", "synced")
        for ph in l1_phases
    )


def check_chapter(wr: str, book_id: str, ch: str) -> dict:
    """检查章节是否需要处理。

    v47.0: 新增版本感知——template_version 或 schema_version 变化时缓存失效。

    Returns:
        {"status": "unchanged"|"changed"|"missing_yaml"|"no_source"|"incomplete"|"version_changed", ...}
    """
    result = {"chapter": ch, "status": "unknown"}

    src = _chapter_src(wr, ch)
    if not src:
        result["status"] = "no_source"
        return result

    result["source"] = os.path.basename(src)
    current_hash = compute_sha256(src)
    saved_hash = read_saved_hash(wr, ch)

    result["current_hash"] = current_hash[:12]
    result["saved_hash"] = saved_hash[:12] if saved_hash else None
    result["hash_match"] = current_hash == saved_hash

    # v47.0: 版本感知检查
    if not versions_match(wr, ch):
        result["status"] = "version_changed"
        result["version_mismatch"] = True
        return result

    if not yaml_files_exist(wr, ch):
        result["status"] = "missing_yaml"
        return result

    if not is_pipeline_complete(wr, book_id, ch):
        result["status"] = "incomplete"
        return result

    if current_hash == saved_hash:
        result["status"] = "unchanged"
    else:
        result["status"] = "changed"

    return result


def check_all(wr: str, book_id: str) -> list[dict]:
    """扫描所有章节的缓存状态"""
    from pipeline_batch import discover_chapters

    chapters = discover_chapters(wr)
    results = []
    for ch_num, _src_path in chapters:
        results.append(check_chapter(wr, book_id, ch_num))
    return results


def save_chapter_hash(wr: str, ch: str) -> bool:
    """保存章节源文件的当前 hash + 版本信息（仅在 pipeline 成功后调用）"""
    src = _chapter_src(wr, ch)
    if not src:
        log.error(f"第{ch}章源文件不存在")
        return False
    h = compute_sha256(src)
    save_hash(wr, ch, h)
    # v47.0: 同时保存版本信息
    versions = _get_current_versions(wr)
    save_versions(wr, ch, versions)
    log.info(f"第{ch}章: hash={h[:12]}... 已保存 (template_v={versions['template_version']}, "
             f"schema_v={versions['schema_version']})")
    return True


def invalidate_all(wr: str) -> int:
    """清空所有章节的缓存（hash + version）。
    
    Returns:
        被清除的缓存目录数量
    """
    dag_root = os.path.join(wr, ".dag")
    if not os.path.isdir(dag_root):
        return 0

    count = 0
    for ch_dirname in sorted(os.listdir(dag_root)):
        ch_dir = os.path.join(dag_root, ch_dirname)
        if not os.path.isdir(ch_dir) or ch_dirname == "_logs":
            continue
        # 删除 hash 和 version 文件
        for fname in (HASH_FILE, VERSION_FILE):
            fp = os.path.join(ch_dir, fname)
            if os.path.exists(fp):
                os.remove(fp)
                count += 1
    log.success(f"已清空 {count} 个缓存文件（跨 {len(os.listdir(dag_root))} 个目录）")
    return count


def main():
    import argparse

    p = argparse.ArgumentParser(description="chapter_cache — SHA256 增量缓存 (v47.0 版本感知)")
    sp = p.add_subparsers(dest="cmd")

    # check
    chk = sp.add_parser("check", help="检查章节是否需要处理")
    chk.add_argument("-w", "--wiki-root", required=True)
    chk.add_argument("--book-id", required=True)
    chk.add_argument("-c", "--chapter")

    # save
    sv = sp.add_parser("save", help="保存当前 hash + 版本信息")
    sv.add_argument("-w", "--wiki-root", required=True)
    sv.add_argument("-c", "--chapter", required=True)

    # list
    ls = sp.add_parser("list", help="列出所有章缓存状态")
    ls.add_argument("-w", "--wiki-root", required=True)
    ls.add_argument("--book-id", required=True)

    # v47.0: invalidate-all
    inv = sp.add_parser("invalidate-all", help="强制清空所有缓存")
    inv.add_argument("-w", "--wiki-root", required=True)

    args = p.parse_args()

    if args.cmd == "invalidate-all":
        invalidate_all(args.wiki_root)
        return

    if args.cmd == "check":
        if args.chapter:
            result = check_chapter(args.wiki_root, args.book_id, args.chapter)
            print(f"第{result['chapter']}章: {result['status']}")
            if result["status"] == "unchanged":
                print(f"  源文件: {result['source']}")
                print(f"  hash: {result['current_hash']} (未变化)")
            elif result["status"] == "changed":
                print(f"  源文件: {result['source']}")
                print(f"  旧hash: {result['saved_hash']}")
                print(f"  新hash: {result['current_hash']} (已变化)")
            elif result["status"] == "version_changed":
                print(f"  模板/schema 版本变更，缓存失效")
            elif result["status"] == "missing_yaml":
                print("  YAML 数据缺失，需要生成")
        else:
            results = check_all(args.wiki_root, args.book_id)
            unchanged = sum(1 for r in results if r["status"] == "unchanged")
            need_work = sum(1 for r in results if r["status"] != "unchanged")
            print(f"全书 {len(results)} 章: {unchanged} 未变化, {need_work} 需要处理")
            for r in results:
                if r["status"] == "unchanged":
                    icon = "✅"
                elif r["status"] == "version_changed":
                    icon = "🔁"
                else:
                    icon = "🔄"
                print(f"  {icon} 第{r['chapter']}章: {r['status']}")

    elif args.cmd == "save":
        save_chapter_hash(args.wiki_root, args.chapter)

    elif args.cmd == "list":
        results = check_all(args.wiki_root, args.book_id)
        for r in results:
            print(f"第{r['chapter']}章: {r['status']} | {r.get('source', 'N/A')}")


if __name__ == "__main__":
    main()
