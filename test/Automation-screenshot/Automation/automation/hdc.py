from __future__ import annotations

import os
import subprocess
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class HdcError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class HdcClient:
    def __init__(
        self,
        executable: str = "hdc",
        default_timeout: float = 30,
        sn: str | None = None,
        logger: logging.Logger | None = None,
    ):
        self.executable = executable
        self.default_timeout = default_timeout
        self.sn = sn
        self._log = logger or logging.getLogger("hdc")
        self.env = os.environ.copy()
        self.env["MSYS_NO_PATHCONV"] = "1"

    def run(self, args: Sequence[object], *, timeout: float | None = None, check: bool = True) -> CommandResult:
        command = [self.executable]
        if self.sn:
            command.extend(["-t", self.sn])
        command.extend(str(arg) for arg in args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                env=self.env,
                text=True,
                timeout=self.default_timeout if timeout is None else timeout,
            )
        except FileNotFoundError as exc:
            raise HdcError(f"HDC executable not found: {self.executable}") from exc
        result = CommandResult(tuple(command), completed.returncode, completed.stdout or "", completed.stderr or "")
        if check and result.returncode != 0:
            raise HdcError(format_command_failure(result))
        return result

    def shell(self, *parts: object, timeout: float | None = None, check: bool = True) -> CommandResult:
        return self.run(["shell", *parts], timeout=timeout, check=check)

    def dump_layout(self, local_path: Path, remote_path: str, *, retries: int = 3, retry_wait: float = 1) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        for _ in range(retries):
            local_path.unlink(missing_ok=True)

            dump = self.shell("uitest", "dumpLayout", "-p", remote_path, timeout=15, check=False)
            if dump.returncode != 0:
                last_error = HdcError(format_command_failure(dump))
                self._log.warning("dumpLayout failed, retrying: %s", last_error)
                time.sleep(retry_wait)
                continue

            recv = self.run(["file", "recv", remote_path, str(local_path)], timeout=15, check=False)
            if recv.returncode != 0:
                last_error = HdcError(format_command_failure(recv))
                self._log.warning("dumpLayout recv failed, retrying: %s", last_error)
                time.sleep(retry_wait)
                continue

            if local_path.exists() and local_path.stat().st_size > 0:
                return local_path

            last_error = HdcError(f"Dump layout file is empty: {local_path}")
            self._log.warning("dumpLayout produced empty file, retrying: %s", local_path)
            time.sleep(retry_wait)

        raise HdcError(f"Failed to dump UI layout after {retries} attempts") from last_error

    def ui_input(self, action: str, *args: object, check: bool = True) -> CommandResult:
        return self.shell("uitest", "uiInput", action, *args, timeout=10, check=check)

    def snapshot_display(
        self,
        local_path: Path,
        remote_path: str,
        *,
        min_bytes: int = 1000,
        retries: int = 3,
        write_wait: float = 1,
    ) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        for _ in range(retries):
            local_path.unlink(missing_ok=True)
            self.shell("rm", "-f", remote_path, timeout=10, check=False)
            result = self.shell("snapshot_display", "-f", remote_path, timeout=30, check=False)
            if result.returncode != 0:
                result = self.shell("snapshot_display", remote_path, timeout=30, check=False)
                if result.returncode != 0:
                    last_error = HdcError(format_command_failure(result))
                    continue
            time.sleep(write_wait)

            recv = self.run(["file", "recv", remote_path, str(local_path)], timeout=30, check=False)
            if recv.returncode != 0:
                last_error = HdcError(format_command_failure(recv))
                continue
            if local_path.exists() and local_path.stat().st_size > min_bytes:
                return local_path
            size = local_path.stat().st_size if local_path.exists() else 0
            self._log.warning("snapshot_display file too small: %d bytes", size)
            last_error = HdcError(f"Screenshot file is too small: {local_path}")
            local_path.unlink(missing_ok=True)

        raise HdcError(f"Failed to capture a valid screenshot after {retries} attempts") from last_error

    @classmethod
    def list_targets(cls, executable: str = "hdc", timeout: float = 30) -> list[str]:
        client = cls(executable=executable, default_timeout=timeout)
        result = client.run(["list", "targets"], timeout=timeout)
        return parse_targets(result.stdout)


def parse_targets(output: str) -> list[str]:
    targets: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if "empty" in lower or "list of" in lower or lower.startswith("["):
            continue
        sn = line.split()[0]
        if sn and sn not in targets:
            targets.append(sn)
    return targets


def format_command_failure(result: CommandResult) -> str:
    command = " ".join(result.args)
    return f"Command failed ({result.returncode}): {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

