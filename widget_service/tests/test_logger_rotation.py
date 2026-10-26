"""本地独立进程日志隔离及异步轮转回归。"""

import os
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.logger as logger_module


@pytest.mark.parametrize("local", [True, False])
def test_log_file_configuration(monkeypatch, tmp_path, local):
    """本地按进程隔离日志，云侧保持固定文件及现有轮转配置。"""
    test_logger = Mock()
    monkeypatch.setattr(logger_module, "_logger", test_logger)
    monkeypatch.setattr(logger_module.LoggingConfig, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "get_settings", lambda: SimpleNamespace(LOCAL_FLAG=local))
    monkeypatch.setattr(logger_module.os, "getpid", lambda: 12345)
    monkeypatch.setattr(logger_module, "datetime", Mock(wraps=datetime))
    logger_module.datetime.now.return_value = datetime(2026, 10, 25, tzinfo=UTC)

    logger_module.TaskLogger()

    file_call = test_logger.add.call_args_list[1]
    expected_name = "agent_20261025_12345.log" if local else "debug_python.log"
    assert Path(file_call.args[0]) == tmp_path / expected_name
    assert file_call.kwargs.get("rotation") == "100 MB"
    assert file_call.kwargs.get("retention") == "30 days"
    assert file_call.kwargs.get("compression") == "zip"
    assert file_call.kwargs.get("enqueue") is True


_WRITER_SCRIPT = """
import os
import sys
from pathlib import Path

from config.config import LoggingConfig, get_settings
from loguru import logger

log_dir = Path(sys.argv[1])
marker = sys.argv[2]
LoggingConfig.LOG_DIR = log_dir
get_settings().LOCAL_FLAG = True
original_add = logger.add

def small_rotation(sink, **kwargs):
    if isinstance(sink, str):
        kwargs['rotation'] = 1024
    return original_add(sink, **kwargs)

logger.add = small_rotation
from app.logger import task_logger

task_logger.logger.info(marker + '-ready')
task_logger.logger.complete()
(log_dir / (marker + '.ready')).write_text(str(os.getpid()), encoding='utf-8')
sys.stdin.readline()
for index in range(20):
    task_logger.logger.info(f'{marker}-{index:02d}-' + 'x' * 200)
task_logger.logger.complete()
task_logger.logger.remove()
"""


def test_independent_processes_rotate_without_losing_messages(tmp_path):
    """两个独立导入的日志实例同时持有文件时仍能轮转，消息无丢失。"""
    service_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(service_root / "cloud")
    processes = []
    try:
        for marker in ("first", "second"):
            process = subprocess.Popen(
                [sys.executable, "-c", _WRITER_SCRIPT, str(tmp_path), marker],
                cwd=service_root,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            processes.append(process)

        deadline = time.monotonic() + 20.0
        while len(list(tmp_path.glob("*.ready"))) < 2:
            for process in processes:
                assert process.poll() is None, process.communicate(timeout=5)
            assert time.monotonic() < deadline, "日志子进程启动超时"
            time.sleep(0.02)

        for process in processes:
            assert process.stdin is not None
            process.stdin.write("rotate\n")
            process.stdin.flush()

        for process in processes:
            _stdout, stderr = process.communicate(timeout=20)
            assert process.returncode == 0, stderr
            assert "Logging error" not in stderr
            assert "PermissionError" not in stderr

        for marker in ("first", "second"):
            messages = ""
            writer_pid = (tmp_path / (marker + ".ready")).read_text(encoding="utf-8")
            files = list(tmp_path.glob(f"agent_*_{writer_pid}*.log*"))
            archives = []
            for path in files:
                if path.suffix == ".zip":
                    archives.append(path)
                    with zipfile.ZipFile(path) as archive:
                        for name in archive.namelist():
                            messages += archive.read(name).decode("utf-8")
                else:
                    messages += path.read_text(encoding="utf-8")
            assert archives, "应实际触发 ZIP 日志轮转"
            assert messages.count(marker + "-ready") == 1
            for index in range(20):
                assert messages.count(f"{marker}-{index:02d}-") == 1
            other_marker = "second" if marker == "first" else "first"
            assert other_marker not in messages
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
