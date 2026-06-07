"""dag_state.py — DAG 状态管理、工作区配置和文件工具

从 dag_utils.py 拆分。包含状态文件读写、并发锁、工作区布局检测等。
"""

import contextlib
import json
import os
import re
import time as _time
from typing import Any

from log_utils import get_logger

log = get_logger(__name__)


import yaml  # noqa: E402
from dag_constants import DAG_ORDER, DIR, DIR_BY_PHASE, NODE_CONFIG, PipelineArgs  # noqa: E402


from workspace_paths import WorkspacePaths  # noqa: F401 — v43.1 re-export

STATE_SCHEMA_VERSION = "1.0.0"

# ── P0-3: 并发锁（防止两个 pipeline 同时运行）─────────────
try:
    import fcntl
except ImportError:
    fcntl = None  # Windows 环境降级


# ===== 工具 =====
def _wr(args: PipelineArgs) -> str:
    return os.path.abspath(args.wiki_root or ".")


class PipelineLock:
    """基于文件锁的并发控制"""

    def __init__(self, wiki_root):
        lock_dir = os.path.join(wiki_root, ".dag")
        os.makedirs(lock_dir, exist_ok=True)
        self.lock_path = os.path.join(lock_dir, "pipeline.lock")
        self.fd = None

    def acquire(self, timeout=10):
        """尝试获取锁，超时返回 False"""
        self.fd = open(self.lock_path, "w")  # noqa: SIM115 — fd 在 release() 中关闭
        if fcntl is None:
            # Windows 环境无 fcntl，降级为无锁
            self.fd.write(str(os.getpid()))
            self.fd.flush()
            return True
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fd.write(str(os.getpid()))
                self.fd.flush()
                return True
            except OSError:
                _time.sleep(0.3)
        self.fd.close()
        self.fd = None
        return False

    def release(self):
        if self.fd:
            try:
                if fcntl is not None:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
            self.fd.close()
            self.fd = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(
                f"无法获取 pipeline 锁（超时），可能有另一个进程正在运行。\\n手动清除: rm {self.lock_path}"
            )
        return self

    def __exit__(self, *args):
        self.release()


# ===== 工作区布局检测与配置管理 =====
def detect_layout(wr: str) -> dict[str, str]:
    """自动检测工作区布局类型（嵌套 vs 平铺），并计算 KB 根目录。

    嵌套模式（新）：KB_ROOT/{domain_name}/{book_id_name}/
      → layout="nested", kb_root=KB_ROOT, wiki_root_depth=2

    平铺模式：KB_ROOT/BOOK_ID/
      → layout="flat", kb_root=KB_ROOT, wiki_root_depth=1

    Returns: {'layout': 'nested'|'flat', 'kb_root': str}
    """
    wr = os.path.abspath(wr)

    # 策略0：wr 含源文件目录 → 必为 book 目录，往上 2 级即 KB 根（v43.1）
    src_dir = os.path.join(wr, DIR["SOURCE"])
    if os.path.isdir(src_dir):
        up2 = os.path.normpath(os.path.join(wr, "..", ".."))
        # 检查 up2 不是 wr 的父目录的父目录（排除异常）
        return {"layout": "nested", "kb_root": up2}

    # 策略1：wr 往上 2 级存在 知识库总控/ → nested
    up2 = os.path.normpath(os.path.join(wr, "..", ".."))
    if os.path.isdir(os.path.join(up2, DIR["KB_CTRL"])):
        return {"layout": "nested", "kb_root": up2}

    # 策略2：wr 上级目录存在 领域总控/ → nested
    up1 = os.path.normpath(os.path.join(wr, ".."))
    if os.path.isdir(os.path.join(up1, DIR["DOMAIN_CTRL"])):
        up2_b = os.path.normpath(os.path.join(up1, ".."))
        return {"layout": "nested", "kb_root": up2_b}

    # 策略3：平铺模式 — wr 直接在 KB 根目录下
    return {"layout": "flat", "kb_root": up1}


def load_workspace_config(wr: str) -> dict[str, Any]:
    """加载 .dag/config.yaml，不存在时自动检测布局并返回。

    Returns: dict with at least {'layout': str, 'kb_root': str}
    """
    config_path = os.path.join(wr, ".dag", "config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            if "layout" in config and "kb_root" in config:
                return config
        except Exception as e:
            log.debug(f"配置文件加载失败: {e}")
            pass
    return detect_layout(wr)


def save_workspace_config(wr: str, config: dict[str, Any]) -> None:
    """保存工作区配置到 .dag/config.yaml（原子写入）"""
    dag_dir = os.path.join(wr, ".dag")
    os.makedirs(dag_dir, exist_ok=True)
    config_path = os.path.join(dag_dir, "config.yaml")
    import tempfile as _tf

    fd, tmpname = _tf.mkstemp(dir=dag_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmpname, config_path)
    except OSError:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
        raise


def get_wiki_root(wr: str) -> str:
    """M1: 从书目录(wr)计算wiki根目录。

    根据 .dag/config.yaml 中的 layout 决定：
      nested → wr/../..   (2层：BOOK/domain/)
      flat   → wr/..      (1层：BOOK/)
    """
    config = load_workspace_config(wr)
    layout = config.get("layout", "nested")
    if layout == "flat":
        return os.path.normpath(os.path.join(wr, ".."))
    else:
        return os.path.normpath(os.path.join(wr, "..", ".."))


def _state_path(wr: str, bid: str, ch: str) -> str:
    """返回状态文件路径，自动创建 .dag/ 目录"""
    p = os.path.join(wr, ".dag")
    os.makedirs(p, exist_ok=True)
    return os.path.join(p, f"{bid}_ch{ch}.json")


@contextlib.contextmanager
def _state_lock(path: str, exclusive: bool = True):
    """v40.0: 文件锁上下文管理器，保护状态文件并发访问（跨平台安全）"""
    lock_path = path + ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield fd
    finally:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load_state(p: str) -> dict[str, Any]:
    """加载状态文件，自动恢复损坏的 JSON（v40.0: 加共享锁 + WAL 恢复）"""
    import time as _time

    if os.path.exists(p):
        try:
            with _state_lock(p, exclusive=False), open(p) as f:
                data = json.load(f)
            # Schema 版本检查
            ver = data.get("_schema_version", "")
            if not ver or ver < STATE_SCHEMA_VERSION:
                log.warning("⚠️ 状态文件 schema 版本 %s 低于当前 %s，尝试向后兼容加载", ver or "（无版本）", STATE_SCHEMA_VERSION)
            return data
        except (json.JSONDecodeError, ValueError):
            # 尝试从 WAL 恢复
            wal_path = p + ".wal"
            if os.path.exists(wal_path):
                try:
                    with open(wal_path) as f:
                        data = json.load(f)
                    log.warning("⚠️ 状态文件已损坏，已从 WAL 恢复")
                    # 用 WAL 数据修复主文件
                    _save_state(p, data)
                    return data
                except (json.JSONDecodeError, ValueError):
                    pass
            import shutil

            corrupted = f"{p}.corrupted.{int(_time.time())}"
            shutil.move(p, corrupted)
            log.warning(f"⚠️ 状态文件已损坏，已备份到 {corrupted}，使用空状态恢复")
            return {"phases": {}}
    return {"phases": {}}


def _save_state(p: str, s: dict[str, Any]) -> None:
    """原子写入 + WAL 日志（v40.0: 加排他锁, v41.0: 自动记录时间戳, v43.12: 阶段一致性检查）"""
    import tempfile

    # 自动记录最后修改时间
    s["_last_modified"] = _time.strftime("%Y-%m-%dT%H:%M:%S")
    s["_schema_version"] = STATE_SCHEMA_VERSION

    # v43.12: 阶段一致性检查 —— 防止"下游 done 但上游 pending"的矛盾状态
    DAG_ORDER = [
        "chapter_toc", "concepts", "ke", "entities",
        "kp", "sp", "scene", "exercises", "solutions",
        "l2_indices", "l3_indices", "l4_indices",
    ]
    phases = s.get("phases", {})
    for i, current in enumerate(DAG_ORDER):
        if current in phases and phases[current].get("status") == "done":
            # 检查所有上游阶段是否已完成
            broken = [ph for ph in DAG_ORDER[:i] if phases.get(ph, {}).get("status") != "done"]
            if broken:
                log.warning("⚠️ 阶段矛盾: %s=done 但上游 %s 未完成（可能为残留状态，需排查）", current, ", ".join(broken))

    with _state_lock(p, exclusive=True):
        # 写 WAL 日志（Write-Ahead Log）
        wal_path = p + ".wal"
        try:
            with open(wal_path, "w", encoding="utf-8") as wf:
                json.dump(s, wf, ensure_ascii=False, indent=2)
        except OSError:
            pass  # WAL 写入失败不阻断主流程
        # 原子写入主文件
        fd, tmpname = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
            os.replace(tmpname, p)  # 原子替换
        except OSError:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
            raise


def _log_check_result(wr: str, book_id: str, ch: str, check_name: str, result_dict: dict[str, Any]) -> None:
    """v33.1: 将检查结果写入结构化 JSON 日志 (.dag/check_logs/)"""
    import time as _time

    log_dir = os.path.join(wr, ".dag", "check_logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = _time.strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{book_id}_ch{ch}_{check_name}_{ts}.json")
    import tempfile

    fd, tmpname = tempfile.mkstemp(dir=log_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "_schema_version": STATE_SCHEMA_VERSION,
                    "timestamp": _time.time(),
                    "book_id": book_id,
                    "chapter": ch,
                    "check": check_name,
                    "result": result_dict,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(tmpname, log_file)
    except OSError:
        if os.path.exists(tmpname):
            os.unlink(tmpname)


def _phase_dir(wr: str, ph: str) -> str:
    """返回指定阶段的输出目录"""
    c = NODE_CONFIG.get(ph)
    if c and c.get("dir"):
        return os.path.join(wr, c["dir"])
    if c:
        return wr  # dir=None 的返回书目录
    return wr


def _phase_count(wr: str, ph: str) -> int:
    """统计指定阶段目录下的 .md 文件数"""
    if ph == "l2_indices":
        d = os.path.join(wr, DIR["OVERVIEW"])
    elif ph == "l3_indices":
        wiki_root = os.path.normpath(os.path.join(wr, "..", "..", ".."))
        d = os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"])
    elif ph == "l4_indices":
        wiki_root = os.path.normpath(os.path.join(wr, "..", "..", ".."))
        d = os.path.join(wiki_root, DIR["KB_CTRL"])
    else:
        d = _phase_dir(wr, ph)
    return len([f for f in os.listdir(d) if f.endswith(".md")]) if os.path.isdir(d) else 0


def _phase_latest_mtime(wr: str, ph: str) -> float:
    """返回指定阶段目录下所有 .md 文件的最新 mtime（无文件返回 0.0）"""
    d = _phase_dir(wr, ph)
    if not os.path.isdir(d):
        return 0.0
    mtimes = []
    for f in os.listdir(d):
        if f.endswith(".md"):
            try:
                mtimes.append(os.path.getmtime(os.path.join(d, f)))
            except OSError:
                pass
    return max(mtimes) if mtimes else 0.0


def _book_name(bid: str) -> str:
    """从 book_id 提取简短书名"""
    return bid.split("_", 1)[1] if "_" in bid else bid


def extract_chapter_num(fn: str) -> str:
    """从文件名中提取章号"""
    m = re.search(r"第?(\d+)章", fn)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d+)\.(\d+)", fn)
    return m2.group(0) if m2 else "1"


def validate_md_file(fp: str) -> dict:
    """校验单个 .md 文件的 FM 完整性和占位符"""
    r = {"file": fp, "valid": True, "errors": [], "warnings": []}
    if not os.path.exists(fp):
        r["valid"] = False
        r["errors"].append("不存在")
        return r
    with open(fp) as f:
        c = f.read()
    fm = re.match(r"^---\s*\n(.*?)\n---", c, re.DOTALL)
    if not fm:
        r["errors"].append("缺FM")
        r["valid"] = False
    else:
        for fld in ["type:", "name:", "book_id:", "chapter_num:"]:
            if fld not in fm.group(1):
                r["warnings"].append(f"FM缺{fld}")
    for ph in ["（待补充）", "TODO", "FIXME"]:
        if ph in c:
            r["warnings"].append(f"占位符:{ph}")
    if r["errors"]:
        r["valid"] = False
    return r


def batch_validate(d: str, n: int = 20) -> dict:
    """批量校验目录中前 n 个 .md 文件"""
    mfs = sorted(f for f in os.listdir(d) if f.endswith(".md"))[:n]
    issues = []
    for f in mfs:
        r = validate_md_file(os.path.join(d, f))
        if not r["valid"]:
            for e in r["errors"]:
                issues.append(f"{f}: {e}")
        for w in r["warnings"]:
            issues.append(f"{f}: ⚠{w}")
    total = len([f for f in os.listdir(d) if f.endswith(".md")])
    return {"total": total, "checked": len(mfs), "issues": issues}


def snapshot_output_dirs(wr: str, book_id: str, chapter: str) -> str:
    """P1-7: 构建前快照——备份当前输出目录到 .dag/backups/"""
    import shutil

    backup_base = os.path.join(wr, ".dag", "backups", f"{book_id}_ch{chapter}")
    ts = _time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(backup_base, ts)
    os.makedirs(backup_dir, exist_ok=True)

    saved = 0
    for ph in DAG_ORDER:
        d = _phase_dir(wr, ph)
        if os.path.isdir(d):
            dst = os.path.join(backup_dir, os.path.basename(d))
            try:
                shutil.copytree(d, dst)
                saved += 1
            except (OSError, shutil.Error):
                pass

    # Snapshot state file
    sp = _state_path(wr, book_id, chapter)
    if os.path.exists(sp):
        shutil.copy2(sp, os.path.join(backup_dir, "state.json"))

    # Prune old snapshots (keep last 5)
    parent = os.path.dirname(backup_dir)
    if os.path.isdir(parent):
        snaps = sorted(os.listdir(parent), reverse=True)
        for old in snaps[5:]:
            try:
                shutil.rmtree(os.path.join(parent, old))
            except (OSError, shutil.Error):
                pass

    return backup_dir


# ============================================================
# 工具函数（v42.0: 从 dag_utils.py 迁入）
# ============================================================


def scan_broken_links(wr: str, book_id: str, chapter: str) -> int:
    """扫描书中的所有 .md 文件，返回断链（无效 wikilink）数量

    Args:
        wr: wiki 根目录路径
        book_id: 书 ID（备用，当前未使用）
        chapter: 章号（备用，当前未使用）
    Returns:
        int: 断链数量
    """
    wiki_root = os.path.normpath(os.path.join(wr, "..", "..", ".."))

    # P12 fix: 收集所有已知 MD 文件（同时存储 basename 和完整相对路径，避免同名混淆）
    known_files = set()  # basename 集合（向后兼容）
    known_paths = set()  # 完整相对路径集合（精确匹配）
    for ph in DAG_ORDER:
        d = _phase_dir(wr, ph)
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".md"):
                    known_files.add(f[:-3])
                    known_paths.add(f[:-3])  # basename
                    # 也存储带目录前缀的路径
                    rel = os.path.relpath(os.path.join(d, f[:-3]), os.path.dirname(d))
                    known_paths.add(rel)

    # 额外搜索 L3/L4 索引目录（跨层引用）
    for extra in [os.path.join(wiki_root, DIR["FIELD"], DIR["DOMAIN_CTRL"]), os.path.join(wiki_root, DIR["KB_CTRL"])]:
        if os.path.isdir(extra):
            for f in os.listdir(extra):
                if f.endswith(".md"):
                    known_files.add(f[:-3])
                    known_paths.add(f[:-3])

    # P12 fix: 扫描所有阶段目录中的 MD 文件，同时检查 basename 和完整路径
    broken = 0
    for ph in DAG_ORDER:
        d = _phase_dir(wr, ph)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(d, f)
            with open(fpath) as fh:
                c = fh.read()
            for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", c):
                full_target = m.group(1)
                target_basename = full_target.split("/")[-1]
                # 先检查完整路径，再检查 basename
                if full_target not in known_paths and target_basename not in known_files:
                    broken += 1
    return broken


def extract_exercises_from_text(ct: str, bid: str, ch: str = "0") -> list:
    """从正文文本中自动检测并提取习题

    v39.1: 扩展习题标题匹配，支持多种变体：
      - 中文：习题/练习题/思考题/课后题/复习题/思考与练习/本章习题 等
      - 英文：Exercises/Problems/Questions/Review Questions 等
      - 带编号/带章节前缀的变体
    """
    exs = []
    lines = ct.split("\n")
    # v39.1: 扩展的习题标题关键词（含中英文变体）
    _EXERCISE_PATTERNS = [
        r"习题",
        r"练习题",
        r"思考题",
        r"习\s*题",
        r"课后题",
        r"复习题",
        r"课后练习",
        r"思考与练习",
        r"练习与思考",
        r"思考与习题",
        r"本章习题",
        r"章末习题",
        r"课后习题",
        r"讨论题",
        r"案例分析题",
        r"[Ee]xercises?",
        r"[Pp]roblems?",
        r"[Qq]uestions?",
        r"[Rr]eview\s+[Qq]uestions?",
        r"[Dd]iscussion\s+[Qq]uestions?",
    ]
    _EXERCISE_RE = re.compile("|".join(_EXERCISE_PATTERNS))
    ins = False
    en = 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # v39.1: 使用编译的正则匹配习题标题行（仅匹配标题级，避免误匹配正文中的“习题”二字）
        if (
            not ins
            and (
                s.startswith("#")  # Markdown 标题行
                or (len(s) < 40 and _EXERCISE_RE.search(s))  # 短行含关键词
            )
            and _EXERCISE_RE.search(s)
        ):
            ins = True
            continue
        if ins:
            m = re.match(r"^[\s]*([0-9]+[\.、：:]|[（(][0-9]+[）)]|[一二三四五六七八九十]+[、.:])", s)
            if m:
                if exs and exs[-1].get("question", "").strip():
                    en += 1
                ct2 = s[m.end() :].strip() or s
                exs.append(
                    {
                        "name": f"第{ch}章-习题{en + 1}",
                        "question": ct2,
                        "related_answer": (f"[[{DIR['SOLUTIONS']}/第{ch}章-习题{en + 1}-解答_{bid}_{ch}|解答]]"),
                        "source_chapter": f"第{ch}章",
                    }
                )
            elif exs and len(exs) > 0:
                exs[-1]["question"] += "\n" + s
    return exs


def verify_exercise_solution_mapping(wr):
    """验证习题与解答的1:1对应关系，返回缺失解答的习题列表

    v39.1: 从 pipeline_auto.py 移入，打破 dag_quality↔ pipeline_auto 循环依赖
    """
    ex_dir = os.path.join(wr, DIR["EXERCISES"])
    sol_dir = os.path.join(wr, DIR["SOLUTIONS"])

    if not os.path.isdir(ex_dir):
        return []

    ex_files = set()
    for f in os.listdir(ex_dir):
        if f.endswith(".md") and f != "解答":
            ex_files.add(f)

    sol_files = set()
    if os.path.isdir(sol_dir):
        for f in os.listdir(sol_dir):
            if f.endswith(".md"):
                sol_files.add(f)

    missing = []
    for exf in sorted(ex_files):
        base = exf.replace(".md", "")
        if "-解答" in base:
            continue
        if "_" in base:
            prefix, suffix = base.split("_", 1)
            expected_sol = f"{prefix}-解答_{suffix}"
        else:
            expected_sol = f"{base}-解答"
        if not any(sf.startswith(expected_sol) for sf in sol_files):
            missing.append(exf)

    return missing
