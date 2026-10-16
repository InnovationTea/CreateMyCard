"""Shared subprocess execution with timeout and process-tree cleanup."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path

import psutil


class ProcessExecutionError(RuntimeError):
    def __init__(self, returncode: int | None, output: str) -> None:
        super().__init__(output)
        self.returncode = returncode
        self.output = output


def redact(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return re.sub(
        r"""(?i)((?:password|storePassword|keyPassword)["']?\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,}]+)""",
        r"\1***",
        text,
    )


async def terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
        parent.kill()
    except psutil.NoSuchProcess:
        return
    except psutil.Error:
        process.kill()
    await process.wait()


async def run_process(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float,
    log: Path | None = None,
) -> str:
    options: dict[str, int] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **options,
    )
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout)
    except (TimeoutError, asyncio.CancelledError):
        await terminate_process_tree(process)
        raise
    except Exception:
        await terminate_process_tree(process)
        raise
    result = redact(stdout.decode("utf-8", errors="replace"))
    if log is not None and result:
        with log.open("a", encoding="utf-8") as stream:
            stream.write(result)
    if process.returncode != 0:
        raise ProcessExecutionError(process.returncode, result[-2000:])
    return result


async def run_node_script(
    node: Path,
    script: Path,
    arguments: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    label: str,
) -> str:
    try:
        return await run_process(
            [str(node), str(script), *arguments],
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise RuntimeError(f"{label}超时") from exc
    except ProcessExecutionError as exc:
        detail = exc.output.strip()
        raise RuntimeError(detail or f"{label}进程失败") from exc
