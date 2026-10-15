"""受控子进程执行、取消及日志脱敏。"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from debug_tools.subprocesses import (
    ProcessExecutionError,
    run_process,
    terminate_process_tree,
)
from debug_tools.subprocesses import redact as redact


class DeviceError(RuntimeError):
    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


async def terminate(process: asyncio.subprocess.Process) -> None:
    await terminate_process_tree(process)


async def command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 15.0,
    log: Path | None = None,
) -> str:
    try:
        return await run_process(args, cwd=cwd, env=env, timeout=timeout, log=log)
    except ProcessExecutionError as exc:
        raise DeviceError(f"命令退出码 {exc.returncode}：{exc.output}") from exc


def executable_command(executable: Path, node: Path | None) -> list[str]:
    """按可执行文件类型返回启动参数前缀。"""

    suffix = executable.suffix.lower()
    if suffix == ".js":
        if node is None:
            raise DeviceError("Node.js 环境未配置")
        return [str(node), str(executable)]
    if os.name == "nt" and suffix in (".bat", ".cmd"):
        return ["cmd", "/c", "call", str(executable)]
    return [str(executable)]


async def install_ohpm_dependencies(
    *,
    ohpm: Path,
    node: Path | None,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float = 300.0,
    log: Path | None = None,
) -> None:
    """在工程副本中离线重建生产依赖，并恢复原始开发依赖配置。"""

    if not ohpm.is_file():
        raise DeviceError(f"配置的 Ohpm 可执行文件不存在：{ohpm}")
    package_path = cwd / "oh-package.json5"
    original = package_path.read_text(encoding="utf-8") if package_path.is_file() else None
    if original is None:
        raise DeviceError("工程副本缺少 oh-package.json5，无法安装依赖")
    rewritten = False
    try:
        package = json.loads(original)
        if isinstance(package, dict) and bool(package.get("devDependencies")):
            package["devDependencies"] = {}
            package_path.write_text(
                json.dumps(package, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            rewritten = True
        await command(
            [*executable_command(ohpm, node), "install"],
            cwd=cwd,
            env=env,
            timeout=timeout,
            log=log,
        )
    finally:
        if rewritten:
            package_path.write_text(original, encoding="utf-8")
