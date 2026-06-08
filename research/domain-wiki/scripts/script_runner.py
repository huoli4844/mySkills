"""script_runner.py — 统一子进程调用抽象层

v40.0: 消除 subprocess.run + emoji stdout 解析的重复代码。
提供结构化 JSON 通信、超时处理、重试逻辑和统一结果对象。

用法:
    from script_runner import run_script, ScriptResult

    result = run_script("comprehensive_content_check.py", [wiki_root], json_mode=True)
    if result.success:
        print(result.data["fail"])  # 结构化访问
"""

from __future__ import annotations


import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScriptResult:
    """结构化子进程执行结果"""

    success: bool = False
    returncode: int = -1
    data: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    error_count: int = 0
    warn_count: int = 0
    elapsed_ms: int = 0

    def get(self, key: str, default=None):
        """从 data 字典安全获取值"""
        return self.data.get(key, default)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def items(self) -> list[dict]:
        """获取 data['items'] 列表（若存在）"""
        return self.data.get("items", [])


def _resolve_script(script_name: str) -> str:
    """解析脚本路径：支持绝对路径、相对路径、或仅文件名"""
    if os.path.isabs(script_name):
        return script_name
    if os.path.sep in script_name:
        return os.path.abspath(script_name)
    # 仅文件名 → 在 scripts/ 目录下查找
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(scripts_dir, script_name)


def run_script(
    script_name: str,
    args: list[str] | None = None,
    *,
    json_mode: bool = False,
    timeout: int = 120,
    retries: int = 0,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    quiet_on_success: bool = False,
) -> ScriptResult:
    """统一子进程调用入口。

    Args:
        script_name: 脚本文件名或路径（自动在 scripts/ 下查找）
        args: 脚本参数列表
        json_mode: 若 True，自动追加 --json 参数并解析 stdout 为 JSON
        timeout: 超时秒数
        retries: 失败时重试次数（0 = 不重试）
        cwd: 工作目录
        env: 额外环境变量
        quiet_on_success: 成功时不打印输出

    Returns:
        ScriptResult 对象
    """
    script_path = _resolve_script(script_name)
    if not os.path.exists(script_path):
        return ScriptResult(success=False, returncode=-1, stderr=f"脚本不存在: {script_path}")

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    if json_mode and "--json" not in cmd:
        cmd.append("--json")

    # 合并环境变量
    run_env = None
    if env:
        run_env = {**os.environ, **env}

    last_result = None
    for attempt in range(1 + retries):
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=run_env,
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            last_result = _parse_result(r, json_mode, elapsed)

            if last_result.success:
                return last_result

            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))  # 递增等待

        except subprocess.TimeoutExpired:
            elapsed = int((time.monotonic() - t0) * 1000)
            last_result = ScriptResult(
                success=False,
                returncode=-1,
                stderr=f"超时 ({timeout}s)",
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            last_result = ScriptResult(
                success=False,
                returncode=-1,
                stderr=str(e),
                elapsed_ms=elapsed,
            )

    return last_result or ScriptResult(success=False, returncode=-1, stderr="未知错误")


def _parse_result(r: subprocess.CompletedProcess, json_mode: bool, elapsed_ms: int) -> ScriptResult:
    """解析 subprocess 结果为 ScriptResult"""
    stdout = r.stdout or ""
    stderr = r.stderr or ""
    data = {}
    error_count = 0
    warn_count = 0

    if json_mode and stdout.strip():
        # 尝试从 stdout 解析 JSON（取最后一个有效 JSON 块）
        data = _extract_json(stdout)
        if data:
            error_count = data.get("errors", data.get("fail", data.get("error_count", 0)))
            warn_count = data.get("warnings", data.get("warn", data.get("warn_count", 0)))

    success = r.returncode == 0 and (not json_mode or error_count == 0)

    return ScriptResult(
        success=success,
        returncode=r.returncode,
        data=data,
        stdout=stdout,
        stderr=stderr,
        error_count=error_count,
        warn_count=warn_count,
        elapsed_ms=elapsed_ms,
    )


def _extract_json(stdout: str) -> dict[str, Any]:
    """从 stdout 提取 JSON 数据。

    策略：
    1. 尝试整行解析（stdout 就是 JSON）
    2. 查找 JSON_OUTPUT 标记行
    3. 查找最后一个 { 开头的行
    """
    # 策略 1: 整行 JSON
    stripped = stdout.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # 策略 2: JSON_OUTPUT 标记
    for line in stdout.split("\n"):
        if line.startswith("JSON_OUTPUT:"):
            try:
                return json.loads(line[len("JSON_OUTPUT:") :].strip())
            except json.JSONDecodeError:
                pass

    # 策略 3: 最后一个 JSON 行
    lines = stdout.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    return {}


def run_content_check(wiki_root: str, *, quiet: bool = False, json_mode: bool = True) -> ScriptResult:
    """快捷方法：运行 comprehensive_content_check.py"""
    args = [wiki_root]
    if quiet and not json_mode:
        args.append("--quiet")
    return run_script("comprehensive_content_check.py", args, json_mode=json_mode)


def run_mermaid_check(wiki_root: str, *, fix: bool = False, json_mode: bool = True) -> ScriptResult:
    """快捷方法：运行 validate_mermaid_syntax.py"""
    args = [wiki_root]
    if fix:
        args.append("--fix")
    else:
        args.append("--scan-only")
    return run_script("validate_mermaid_syntax.py", args, json_mode=json_mode)


def run_concept_verify(concept_dir: str, *, source: str = "", json_mode: bool = True) -> ScriptResult:
    """快捷方法：运行 verify_concepts.py"""
    args = [concept_dir]
    if source:
        args.extend(["--source", source])
    return run_script("verify_concepts.py", args, json_mode=json_mode)


def run_dir_registry_check(wiki_root: str, *, json_mode: bool = True) -> ScriptResult:
    """快捷方法：运行 check_dir_registry.py"""
    return run_script("check_dir_registry.py", ["--wiki-root", wiki_root], json_mode=json_mode)
