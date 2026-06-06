#!/usr/bin/env python3
"""
preflight.py — Pre-flight check script for domain-book-wiki pipeline.

Runs all registered checks before any pipeline build. Uses a decorator-based
@check() registration pattern. Each check returns (passed: bool, message: str).

Usage:
    python preflight.py [-w /path/to/workspace] [-v|--verbose]

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
"""

import argparse
import importlib
import inspect
import os
import sys

from log_utils import get_logger

log = get_logger(__name__)


# ── Check registry (decorator-based) ────────────────────────
_CHECKS = []


def check(func):
    """
    Decorator to register a check function.

    The decorated function must return (bool, str) — whether the check
    passed and a human-readable message explaining the result.

    Check functions may accept:
        verbose: bool — for extra output
        workspace: str | None — the -w argument value
    """
    _CHECKS.append(func)
    return func


# ── Resolve paths relative to this script ───────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)  # domain-book-wiki/

# Ensure dag_utils is importable
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Try normal import first; fall back to source-extraction if dag_utils.py
# has a pre-existing syntax error at top level (should not happen, but robust).
_DIR = None
_NODE_CONFIG = None

try:
    from dag_constants import DIR as _DIR
    from dag_constants import NODE_CONFIG as _NODE_CONFIG
except SyntaxError:
    _dag_path = os.path.join(SCRIPT_DIR, "dag_utils.py")
    with open(_dag_path, encoding="utf-8") as _fh:
        _src = _fh.read()

    # Strip the section with the syntax error (the f-string with raw newline)
    # so we can safely exec() the rest of the module head to extract key dicts.
    _src_safe = _src.split("\nclass PipelineLock")[0]

    # Extract DIR, DIR_BY_PHASE, NODE_CONFIG by executing the head in a
    # controlled namespace.
    _ns = {"os": os, "re": __import__("re")}
    exec(_src_safe, _ns)
    _DIR = _ns.get("DIR", {})
    _NODE_CONFIG = _ns.get("NODE_CONFIG", {})

DIR = _DIR if _DIR is not None else globals().get("DIR", {})
NODE_CONFIG = _NODE_CONFIG if _NODE_CONFIG is not None else globals().get("NODE_CONFIG", {})


# ── Constants ───────────────────────────────────────────────
TEMPLATE_DIR = os.path.join(SKILL_DIR, "assets", "templates")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

REQUIRED_SCRIPTS = [
    "dag_controller.py",
    "template_assembler.py",
    "template_assembler.py",
    "index_assembler.py",
    "generate_index_data.py",
    "build_kb_files.py",
    "validate_chapter_data.py",
    "kb_graph.py",
    "check_dir_registry.py",
]

REQUIRED_MODULES = [
    "yaml",
    "json",
    "re",
    "os",
    "fcntl",
]

# Derive expected template files from NODE_CONFIG
TEMPLATE_FILES = set()
for _phase, _cfg in NODE_CONFIG.items():
    tpl = _cfg.get("template")
    if tpl:
        TEMPLATE_FILES.add(tpl)


# ── Helper ──────────────────────────────────────────────────


def _build_kwargs(fn, *, verbose=False, workspace=None):
    """Build kwargs dict for a check function, skipping args it doesn't accept."""
    params = inspect.signature(fn).parameters
    kwargs = {}
    if "verbose" in params:
        kwargs["verbose"] = verbose
    if "workspace" in params:
        kwargs["workspace"] = workspace
    return kwargs


# ── Check functions ─────────────────────────────────────────


@check
def check_templates_exist(verbose=False):
    """
    Verify all template files referenced in NODE_CONFIG exist on disk
    under assets/templates/.
    """
    missing = []
    for tpl in sorted(TEMPLATE_FILES):
        path = os.path.join(TEMPLATE_DIR, tpl)
        if not os.path.isfile(path):
            missing.append(tpl)
        elif verbose:
            log.info(f"  ✓ template: {tpl}")
    if missing:
        return False, f"Missing templates: {', '.join(missing)}"
    return True, f"All {len(TEMPLATE_FILES)} templates present"


@check
def check_yaml_parse(verbose=False):
    """
    Verify all YAML files under scripts/data/ parse without errors.
    Handles both .yaml and .yml extensions.
    """
    import yaml

    errors = []
    if not os.path.isdir(DATA_DIR):
        return False, f"Data directory not found: {DATA_DIR}"

    yaml_files = []
    for root, _dirs, files in os.walk(DATA_DIR):
        for fn in files:
            if fn.endswith((".yaml", ".yml")):
                yaml_files.append(os.path.join(root, fn))
    yaml_files.sort()
    if not yaml_files:
        return False, f"No YAML files found in {DATA_DIR}"

    for path in yaml_files:
        yf = os.path.relpath(path, DATA_DIR)
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if verbose:
                if isinstance(data, list):
                    log.info(f"  ✓ yaml: {yf} ({len(data)} items)")
                elif isinstance(data, dict):
                    log.info(f"  ✓ yaml: {yf} ({len(data)} keys)")
                else:
                    log.info(f"  ✓ yaml: {yf}")
        except yaml.YAMLError as e:
            errors.append(f"{yf}: {e}")
        except Exception as e:
            errors.append(f"{yf}: {e.__class__.__name__}: {e}")

    if errors:
        return False, f"YAML parse errors: {'; '.join(errors)}"
    return True, f"All {len(yaml_files)} YAML files parse OK"


@check
def check_dir_paths(verbose=False):
    """
    Sanity-check the DIR dictionary: every value must be a non-empty string.
    This ensures no accidental None or empty-string dir names.
    """
    issues = []
    for key, value in sorted(DIR.items()):
        if not isinstance(value, str) or not value.strip():
            issues.append(f"DIR[{key!r}] = {value!r} is not a valid dir name")
        elif verbose:
            log.info(f"  ✓ DIR[{key}] = {value}")
    if issues:
        return False, f"DIR path issues: {'; '.join(issues)}"
    return True, f"All {len(DIR)} DIR entries valid"


@check
def check_python_modules(verbose=False):
    """
    Verify that all required Python standard-library and third-party
    modules are importable.
    """
    missing = []
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
            if verbose:
                log.info(f"  ✓ module: {mod}")
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"Missing Python modules: {', '.join(missing)}"
    return True, f"All {len(REQUIRED_MODULES)} modules importable"


@check
def check_required_scripts(verbose=False):
    """
    Verify that all companion scripts under scripts/ exist and compile
    without syntax errors.
    """
    missing = []
    invalid = []
    for script in REQUIRED_SCRIPTS:
        path = os.path.join(SCRIPT_DIR, script)
        if not os.path.isfile(path):
            missing.append(script)
            continue
        try:
            with open(path, encoding="utf-8") as f:
                compile(f.read(), path, "exec")
            if verbose:
                log.info(f"  ✓ script: {script}")
        except SyntaxError as e:
            invalid.append(f"{script}: {e}")
        except Exception as e:
            invalid.append(f"{script}: {e.__class__.__name__}: {e}")

    msgs = []
    if missing:
        msgs.append(f"Missing: {', '.join(missing)}")
    if invalid:
        msgs.append(f"Syntax errors: {'; '.join(invalid)}")
    if msgs:
        return False, " | ".join(msgs)
    return True, f"All {len(REQUIRED_SCRIPTS)} scripts present and valid"


@check
def check_workspace_paths(workspace=None, verbose=False):
    """
    If -w/--workspace is provided, verify the workspace directory exists
    and contains all expected subdirectories defined in DIR.
    In flat layout, container dirs (DOMAIN_CTRL, KB_CTRL, FIELD, LIBRARY)
    are not expected at workspace level — they live at kb_root.
    Skipped when no workspace argument is given.
    """
    if not workspace:
        return True, "No workspace specified (skip)"

    if not os.path.isdir(workspace):
        return False, f"Workspace does not exist: {workspace}"

    # Layout-aware: skip container dirs in flat mode
    from dag_state import load_workspace_config as _lwc
    layout = _lwc(workspace).get("layout", "nested")
    skip_keys = {"DOMAIN_CTRL", "KB_CTRL", "FIELD", "LIBRARY"} if layout == "flat" else set()

    missing_dirs = []
    found = 0
    for key, dname in sorted(DIR.items()):
        if key in skip_keys:
            continue
        dpath = os.path.join(workspace, dname)
        if os.path.isdir(dpath):
            found += 1
            if verbose:
                log.info(f"  ✓ workspace/{dname}")
        else:
            missing_dirs.append(f"{key} ({dname})")

    expected = len(DIR) - len(skip_keys)
    if missing_dirs:
        return False, (f"Workspace missing {len(missing_dirs)}/{expected} dir(s): "
                       f"{', '.join(missing_dirs)}")
    return True, f"Workspace has all {expected} expected directories"

@check
def check_node_config_integrity(verbose=False):
    """
    Verify that every template referenced in NODE_CONFIG actually exists
    on disk under assets/templates/.
    """
    issues = []
    for phase, config in sorted(NODE_CONFIG.items()):
        tpl = config.get("template")
        if tpl:
            tpl_path = os.path.join(TEMPLATE_DIR, tpl)
            if not os.path.isfile(tpl_path):
                issues.append(f"NODE_CONFIG['{phase}'].template='{tpl}' not found")
        if verbose and not issues:
            tpl_info = f"template={tpl}" if tpl else "no template"
            log.info(f"  ✓ NODE_CONFIG['{phase}']: {tpl_info}")

    if issues:
        return False, f"NODE_CONFIG issues: {'; '.join(issues)}"
    return True, f"All {len(NODE_CONFIG)} NODE_CONFIG entries OK"


@check
def check_source_files_ready(workspace=None, verbose=False):
    """Phase 1 完成校验：确认 20_正文/ 下源文件已就位（Phase 2 前置条件）

    检查：20_正文/ 目录存在且至少有一个 .md 源文件、assets/ 目录存在。
    不通过则拒绝进入 Phase 2。
    """
    if not workspace:
        return True, "No workspace specified (skip)"


    source_dir = os.path.join(workspace, _DIR.get("SOURCE", "20_正文"))
    assets_dir = os.path.join(source_dir, "assets")

    if not os.path.isdir(source_dir):
        return False, f"❌ Phase 1 未完成：源文件目录不存在 {source_dir}（请先运行 source-prepare 转换原始文档）"

    md_files = sorted(f for f in os.listdir(source_dir) if f.endswith(".md"))
    if not md_files:
        return False, f"❌ Phase 1 未完成：{source_dir}/ 下无 .md 源文件（请先运行 source-prepare 转换原始文档）"

    # 检查每个 md 文件非空
    empty_files = []
    for mf in md_files:
        fpath = os.path.join(source_dir, mf)
        if os.path.getsize(fpath) < 100:  # 小于100字节视为空
            empty_files.append(mf)
    if empty_files:
        return False, f"❌ Phase 1 未完成：{len(empty_files)} 个源文件疑似为空: {', '.join(empty_files[:3])}"

    has_assets = os.path.isdir(assets_dir) and len(os.listdir(assets_dir)) > 0
    assets_msg = "✓ assets/ 已就位" if has_assets else "⚠ assets/ 为空或不存在（如图片已内嵌则可忽略）"

    if verbose:
        for mf in md_files:
            log.info(f"  ✓ source: {mf}")

    return True, f"Phase 1 完成：{len(md_files)} 个章节源文件就位，{assets_msg}"


@check
def check_teaching_chain_completeness(workspace=None, verbose=False):
    if not workspace or not os.path.isdir(workspace):
        return True, "No workspace specified (skip)"

    dag_dir = os.path.join(workspace, ".dag")
    if not os.path.isdir(dag_dir):
        return True, "No .dag/ directory (skip)"

    chain = {"concepts": "KP", "kes": "KP", "kps": "SP", "sps": "Scene"}  # noqa: F841
    incomplete = []

    for entry in sorted(os.listdir(dag_dir)):
        ch_dir = os.path.join(dag_dir, entry)
        if not (entry.startswith("第") and os.path.isdir(ch_dir)):
            continue
        data_dir = os.path.join(ch_dir, "data")
        if not os.path.isdir(data_dir):
            continue

        files = set(os.listdir(data_dir))
        has_concepts = "concepts.yaml" in files
        has_ke = "kes.yaml" in files
        has_kp = "kps.yaml" in files
        has_sp = "sps.yaml" in files
        has_scene = "scenes.yaml" in files

        present = []
        missing = []
        for a, b in [("concepts+KE", has_concepts and has_ke), ("KP", has_kp), ("SP", has_sp), ("Scene", has_scene)]:
            if b:
                present.append(a)
            else:
                missing.append(a)

        if len(present) < 4:
            incomplete.append(f"{entry}: 有{','.join(present)}但缺{','.join(missing)}")

    if incomplete:
        msg = "教学链不完整：" + "; ".join(incomplete)
        log.warning(f"  ⚠️  {msg}")
        return True, msg  # WARN but don't fail
    return True, "All chapters have complete teaching chain"


@check
def check_data_dir_convention(workspace=None, verbose=False):
    """检查 YAML 数据是否在错误位置 (v49.0: 禁止 data/第N章/)"""
    if not workspace or not os.path.isdir(workspace):
        return True, "No workspace specified (skip)"

    wrong_data = os.path.join(workspace, "data")
    if not os.path.isdir(wrong_data):
        return True, "No stray data/ directory ✓"

    # 检查是否有 YAML
    yaml_count = 0
    for root, _, files in os.walk(wrong_data):
        yaml_count += sum(1 for f in files if f.endswith(('.yaml', '.yml')))
    if yaml_count == 0:
        return True, "data/ exists but empty (harmless)"

    msg = (f"❌ 发现 {yaml_count} 个 YAML 文件在错误位置: {wrong_data}。"
           f"v49.0 后数据必须存放在 .dag/第N章/data/，请迁移后删除 data/ 目录。")
    return False, msg


# ── Main ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for domain-book-wiki pipeline")
    parser.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="Path to workspace (book directory) for directory-structure validation",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output showing each item checked",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Pre-flight Check — domain-book-wiki pipeline")
    log.info(f"Workspace: {args.workspace or '(not specified)'}")
    log.info("=" * 60)
    log.info("")

    all_passed = True
    for fn in _CHECKS:
        name = fn.__name__
        label = name.replace("check_", "").replace("_", " ").title()

        kwargs = _build_kwargs(fn, verbose=args.verbose, workspace=args.workspace)

        try:
            passed, msg = fn(**kwargs)
        except Exception as exc:
            passed, msg = False, f"Check raised exception: {exc.__class__.__name__}: {exc}"

        status = "\u2713 PASS" if passed else "\u2717 FAIL"
        log.info(f"[{status}] {label}")
        log.info(f"         {msg}")
        if not passed:
            all_passed = False

    log.info("")
    log.info("=" * 60)
    if all_passed:
        log.info("All pre-flight checks passed \u2713")
    else:
        log.info("Some pre-flight checks FAILED \u2717")
    log.info("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
