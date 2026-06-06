"""dag_index.py — 索引生成 + 文件完整性检查

v35.7: 从 dag_controller.py 拆分出来。
包含: _build_level_indices, check_stray_files, fix_broken_links,
      build_skeleton, assemble, verify, auto_detect_exercises。
"""

import json
import os
import re

# dag_utils 公共导入
from dag_constants import (
    DAG_ITEM_HINTS,
    DAG_ORDER,
    DIR,
    NODE_CONFIG,
    PipelineError,
)
from dag_state import (
    _book_name,
    _load_state,
    _phase_count,
    _phase_dir,
    _save_state,
    _state_path,
    _wr,
    batch_validate,
    extract_chapter_num,
    extract_exercises_from_text,
    get_wiki_root,
    scan_broken_links,
)

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ASSEMBLER = os.path.join(SKILL_DIR, "template_assembler.py")
INDEX_ASSEMBLER = os.path.join(SKILL_DIR, "index_assembler.py")
GEN_INDEX = os.path.join(SKILL_DIR, "generate_index_data.py")

from log_utils import get_logger  # noqa: E402
from script_runner import run_script  # noqa: E402

log = get_logger(__name__)


def check_stray_files(args):
    """检查 wiki 根目录是否有被错误保存的 .md 文件"""
    wr = _wr(args)
    wiki_root = get_wiki_root(wr)
    known_dirs = [os.path.join(wr, c["dir"]) for c in NODE_CONFIG.values() if c.get("dir")]
    known_dirs.append(os.path.join(wr, DIR["OVERVIEW"]))
    known_dirs.append(os.path.join(wr, DIR["SOURCE"]))
    known_dirs.append(os.path.join(wr, DIR["KE"]))  # KE重定向目录
    known_dirs.append(os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"]))
    known_dirs.append(os.path.join(wiki_root, DIR["KB_CTRL"]))

    stray = []
    for root, _dirs, files in os.walk(wr):
        if ".dag" in root or "__pycache__" in root:
            continue
        # 判断此目录是否属于已知目录
        is_known = any(os.path.abspath(root) == os.path.abspath(k) for k in known_dirs)
        if not is_known and root != wr:
            # 在 wiki 子树中但不在已知子目录 → 检查有无 .md
            for f in files:
                if f.endswith(".md"):
                    fpath = os.path.join(root, f)
                    # 排除解答目录
                    if DIR["SOLUTIONS"] in root or DIR["SOURCE"] in root:
                        continue
                    stray.append(fpath)

    log.info("=== 子代理文件路径检查 ===")
    if stray:
        log.warning(f"发现 {len(stray)} 个文件在错误目录:")
        for s in stray:
            rel = os.path.relpath(s, wr)
            # 猜测正确目录
            guess = None
            for _ph, cfg in NODE_CONFIG.items():
                if not cfg.get("dir"):
                    continue
                if s.endswith(f"_{cfg['dir'].split('/')[0]}.md"):
                    guess = os.path.join(wr, cfg["dir"], os.path.basename(s))
            if guess and not os.path.exists(guess):
                log.info(f"{rel} → 应移至 {os.path.relpath(guess, wr)}")
            else:
                log.info(f"{rel}")
    else:
        log.success("文件位置全部正确")


# ===== 2. 断链自动修复 =====
def fix_broken_links(args):
    """扫描并自动修复断链"""
    wr = _wr(args)
    book_id = args.book_id
    wiki_root = get_wiki_root(wr)

    log.info("=== 断链扫描 ===")

    is_fix = hasattr(args, "fix") and hasattr(args, "action") and (args.fix or args.action == "fix")
    chapter = getattr(args, "chapter", "0")

    if is_fix:
        # ── 修复模式：需要完整的扫描+替换循环 ──
        known_files = set()
        for ph in DAG_ORDER:
            d = _phase_dir(wr, ph)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".md"):
                        known_files.add(f[:-3])
        for extra in [
            os.path.join(wr, DIR["OVERVIEW"]),
            os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"]),
            os.path.join(wiki_root, DIR["KB_CTRL"]),
        ]:
            if os.path.isdir(extra):
                for f in os.listdir(extra):
                    if f.endswith(".md"):
                        known_files.add(f[:-3])

        log.info(f"已知文件: {len(known_files)} 个")

        fixed_count = 0
        scan_dirs = [_phase_dir(wr, ph) for ph in DAG_ORDER if os.path.isdir(_phase_dir(wr, ph))]
        for extra in [
            os.path.join(wr, DIR["OVERVIEW"]),
            os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"]),
            os.path.join(wiki_root, DIR["KB_CTRL"]),
        ]:
            if os.path.isdir(extra):
                scan_dirs.append(extra)

        for sd in set(scan_dirs):
            for fname in os.listdir(sd):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(sd, fname)
                with open(fpath) as f:
                    content = f.read()

                def replace_link(m):
                    nonlocal fixed_count
                    full = m.group(0)
                    target_path = m.group(1)
                    display = m.group(2) if m.group(2) else target_path.split("/")[-1]
                    target_file = target_path.split("/")[-1] if "/" in target_path else target_path
                    if target_file in known_files:
                        return full
                    fixed_count += 1
                    return display

                pattern = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"
                new_content = re.sub(pattern, replace_link, content)

                if new_content != content:
                    with open(fpath, "w") as f:
                        f.write(new_content)

        log.info(f"🔧 修复 {fixed_count} 个断链（移除无效 [[link]] 保留显示文本）")
        if fixed_count == 0:
            log.success("无断链")
    else:
        # ── 扫描模式：使用公共函数 ──
        broken = scan_broken_links(wr, book_id, chapter)
        if broken > 0:
            log.warning(f"发现 {broken} 个断链")
            log.info("运行 'dag_controller.py fix' 自动修复（移除无效 [[link]] 保留文本）")
        else:
            log.success("无断链")


# ===== 3. 增量更新 =====
def build_skeleton(node_type, args):
    cfg = NODE_CONFIG[node_type]
    wr = _wr(args)
    d = os.path.join(wr, cfg["dir"])
    bn = args.book_name or _book_name(args.book_id)
    sk = {
        "template": cfg["template"],
        "output_dir": d,
        "book_id": args.book_id,
        "book_name": bn,
        "chapter_num": args.chapter or "0",
        "items": [],
    }
    if args.append and os.path.exists(args.output):
        with open(args.output) as f:
            sk["items"] = json.load(f).get("items", [])
    os.makedirs(d, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(sk, f, ensure_ascii=False, indent=2)
    log.success(f"[{node_type}] skeleton → {args.output}  ({DAG_ITEM_HINTS.get(node_type,'')})")


def assemble(node_type, json_path, args):
    if not os.path.exists(json_path):
        raise PipelineError(node_type, f"JSON 不存在: {json_path}")
    with open(json_path) as f:
        data = json.load(f)
    items = data.get("items", [])
    if not items:
        log.warning("⚠️ items 为空")
        return
    log.success(f"[{node_type}] {len(items)} items → template_assembler")
    r = run_script("template_assembler.py", [json_path], timeout=120)
    if r.stdout:
        print(r.stdout, end="")
    if not r.success:
        raise PipelineError(node_type, f"template_assembler 失败 ({r.returncode}): {r.stderr[:200]}")
    if node_type in ("l2_indices", "l3_indices", "l4_indices"):
        _build_level_indices(_wr(args), node_type, args)
    sp = _state_path(_wr(args), args.book_id, args.chapter or "0")
    if os.path.exists(sp):
        s = _load_state(sp)
        ph = node_type
        if ph in s.get("phases", {}):
            s["phases"][ph]["status"] = "done"
            s["phases"][ph]["files"] = _phase_count(_wr(args), ph)
            _save_state(sp, s)
            log.info(f"   pipeline state: {ph} → done")
    # assemble 后自动检查子代理文件路径
    check_stray_files(args)
    log.success(f"[{node_type}] assemble 完成")


def verify(node_type, output_dir, args):
    cfg = NODE_CONFIG.get(node_type)
    if not cfg or not os.path.isdir(output_dir):
        return
    mfs = sorted(f for f in os.listdir(output_dir) if f.endswith(".md"))
    log.info(f"=== [{node_type}] 验证 ===  目录: {output_dir}  MD: {len(mfs)}")
    import re as _re

    nok = True
    for f in mfs:
        # 命名规则严格遵循 naming-convention.md
        # short = 概念/KP/SP/Scene/KE/Entity：纯短名 {名称}.md
        if cfg["verify_naming"] == "short":
            if _re.match(r"^第\d+章-", f):
                log.warning(f"  ⚠ [命名违规] 短名不应含章节前缀: {f}")
                nok = False
            if "_" in f and "-" not in f.split("_")[0]:
                log.warning(f"  ⚠ [命名违规] 短名含无效下划线: {f}")
                nok = False
        # long = 习题/解答：长名 {名称}_{书}_{章}.md
        if cfg["verify_naming"] == "long" and "_" not in f:
            log.warning(f"  ⚠ [命名违规] 长名缺后缀: {f}")
            nok = False
    if nok:
        log.info("  ✅ 命名规则检查通过（naming-convention.md）")
    fok = True
    for f in mfs[:10]:
        with open(os.path.join(output_dir, f)) as fh:
            c = fh.read()
        if not c.startswith("---"):
            log.warning(f"  ⚠缺FM: {f}")
            fok = False
        else:
            fm = c.split("---")[1]
            if "chapter_num:" not in fm:
                log.warning(f"  ⚠缺chapter_num: {f}")
                fok = False
    if fok:
        log.info("  ✅ Front Matter 检查通过")
    if mfs:
        r = batch_validate(output_dir, min(10, len(mfs)))
        if r["issues"]:
            log.warning(f"  ⚠{len(r['issues'])}个问题:")
            for i in r["issues"][:5]:
                log.info(f"    {i}")
        else:
            log.success(f"  ✅ 内容验证通过（采样 {r['checked']}/{r['total']}）")
    log.success(f"[{node_type}] verify 完成")


def auto_detect_exercises(args):
    if not args.chapter_file or not os.path.exists(args.chapter_file):
        return
    with open(args.chapter_file) as f:
        c = f.read()
    ch = args.chapter or extract_chapter_num(os.path.basename(args.chapter_file))
    exs = extract_exercises_from_text(c, args.book_id, ch)
    if not exs:
        log.warning("⚠️ 未检测到习题")
        return
    data = {
        "template": "eval_template.md",
        "quality_key": "eval/exercise",
        "output_dir": os.path.join(_wr(args), NODE_CONFIG["exercises"]["dir"]),
        "book_id": args.book_id,
        "book_name": args.book_name or _book_name(args.book_id),
        "chapter_num": ch,
        "items": exs,
    }
    with open(args.output, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.success(f"检测到 {len(exs)} 道习题 → {args.output}")


# ===== Pipeline =====
def _build_level_indices(wr, phase, args):
    """按层级构建索引: l2_indices → 单书总揽, l3_indices → 领域总控, l4_indices → 知识库总控"""
    level_map = {"l2_indices": "l2", "l3_indices": "l3", "l4_indices": "l4"}
    level = level_map.get(phase)
    if not level:
        log.error(f"未知索引阶段: {phase}")
        return False

    wiki_root = get_wiki_root(wr)

    log.info(f"\n  📊 [{phase}] 构建 {level.upper()} 层级索引...")

    # Step 1: 生成该层级的索引JSON
    errors = []
    if os.path.exists(GEN_INDEX):
        r = run_script(
            "generate_index_data.py",
            [
                "--wiki-root",
                wiki_root,
                "--book-id",
                args.book_id,
                "--book-name",
                args.book_name or "",
                "--book-dir",
                os.path.abspath(wr),
                "--level",
                level,
            ],
            timeout=60,
        )
        if not r.success:
            errors.append(f"generate_index_data失败: {r.stderr[:200]}")
        else:
            log.success("索引数据扫描完成")
    else:
        errors.append(f"generate_index_data.py 不存在: {GEN_INDEX}")

    # Step 2: 根据 level 后缀匹配索引 JSON 文件（generate_index_data 输出格式: {index_type}_{book_id}_{level}.json）
    index_dir = os.path.join(wr, ".dag")
    if os.path.isdir(index_dir):
        level_suffix = f"_{level}.json"
        # 索引类型前缀，按 level 过滤
        index_type_prefixes = {
            "l2": ["book_overview"],  # v43.15: 只 book_overview，索引入其中
            "l3": ["domain_overview"],  # v43.15: 只 domain_overview，索引入其中
            "l4": ["kb_overview"],  # v43.15: 只 kb_overview，索引入其中
        }
        prefixes = index_type_prefixes.get(level, [])
        idx_files = []
        for f in sorted(os.listdir(index_dir)):
            if f.endswith(level_suffix):
                fbase = f.replace(level_suffix, "")
                if any(p in fbase for p in prefixes):
                    idx_files.append(f)

        success = 0
        for idxf in idx_files:
            ij = os.path.join(index_dir, idxf)
            if os.path.exists(INDEX_ASSEMBLER):
                r = run_script("index_assembler.py", [ij], timeout=60)
                if r.success:
                    success += 1
                else:
                    errors.append(f"{idxf}: {r.stderr[:100] or r.stdout[-100:]}")
            else:
                errors.append(f"index-assembler.py 不存在: {INDEX_ASSEMBLER}")

        # v43.15: 只生成 overview 文件，清理旧的独立索引文件
        if success > 0:
            level_overview_dirs = {
                "l2": os.path.join(wr, DIR["OVERVIEW"]),
                "l3": os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"]),
                "l4": os.path.join(wiki_root, DIR["KB_CTRL"]),
            }
            overview_dir = level_overview_dirs.get(level)
            if overview_dir and os.path.isdir(overview_dir):
                for old_idx in ["concept_index", "knowledge_index", "skill_index", "scenario_index"]:
                    for f in os.listdir(overview_dir):
                        if f.startswith(old_idx) and f.endswith(".md"):
                            old_file = os.path.join(overview_dir, f)
                            os.remove(old_file)
                            log.info(f"  🧹 清理旧索引: {f}")

        if errors:
            for e in errors:
                log.warning(f"{e}")
        log.success(f"{level.upper()} 索引: {success}/{len(idx_files)} 成功")
    else:
        log.warning(f"索引JSON目录不存在: {index_dir}（尚未扫描节点）")

    # Step 3: 验证该层级文件已生成
    if level == "l2":
        verify_dir = os.path.join(wr, DIR["OVERVIEW"])
    elif level == "l3":
        verify_dir = os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"])
    else:
        verify_dir = os.path.join(wiki_root, DIR["KB_CTRL"])

    if os.path.isdir(verify_dir):
        files = [f for f in os.listdir(verify_dir) if f.endswith(".md")]
        log.success(f"{level.upper()} 共 {len(files)} 个索引文件 → {verify_dir}")
    else:
        log.warning(f"输出目录不存在: {verify_dir}")

    return len(errors) == 0


# ===== CLI =====
