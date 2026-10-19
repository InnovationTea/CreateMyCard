"""Windows 临时占用、并发写入及后处理结果持久化回归。"""

from __future__ import annotations

import ctypes
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from debug_tools import file_io
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.batch_testing.runner import atomic_write_json as write_run_json
from debug_tools.postprocess_plugins._io import atomic_write_json as write_plugin_json


def _windows_error(code: int) -> PermissionError:
    error = PermissionError("模拟 Windows 文件占用")
    error.winerror = code
    return error


@pytest.mark.parametrize("writer", [write_run_json, write_plugin_json])
def test_json_writers_preserve_format_and_clean_temporary_files(tmp_path, writer):
    path = tmp_path / "result.json"
    value = {"说明": "中文内容", "value": None}
    writer(path, value)
    assert (
        path.read_text(encoding="utf-8") == json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("code", [5, 32, 33])
def test_transient_windows_conflicts_retry_same_closed_temporary_file(tmp_path, monkeypatch, code):
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    original_replace = file_io.os.replace
    attempts = []
    delays = []

    def replace(source, destination):
        attempts.append(source)
        assert target.read_text(encoding="utf-8") == "old"
        assert source.read_text(encoding="utf-8") == "new"
        if len(attempts) < 3:
            raise _windows_error(code)
        original_replace(source, destination)

    monkeypatch.setattr(file_io.os, "replace", replace)
    monkeypatch.setattr(file_io.time, "sleep", delays.append)
    file_io.atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert len(set(attempts)) == 1
    assert delays == [0.01, 0.02]
    assert not list(tmp_path.glob("*.tmp"))


def test_permanent_denial_is_bounded_and_preserves_old_target(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    error = _windows_error(5)
    calls = []
    delays = []

    def replace(source, _destination):
        calls.append(source)
        raise error

    monkeypatch.setattr(file_io.os, "replace", replace)
    monkeypatch.setattr(file_io.time, "sleep", delays.append)
    with pytest.raises(PermissionError) as raised:
        file_io.atomic_write_text(target, "new")
    assert raised.value is error
    assert len(calls) == 8
    assert sum(delays) == pytest.approx(0.71)
    assert target.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("error", [PermissionError("真实权限错误"), OSError("磁盘错误")])
def test_unrelated_errors_are_not_retried(tmp_path, monkeypatch, error):
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    delays = []

    def replace(_source, _destination):
        raise error

    monkeypatch.setattr(file_io.os, "replace", replace)
    monkeypatch.setattr(file_io.time, "sleep", delays.append)
    with pytest.raises(type(error)) as raised:
        file_io.atomic_write_text(target, "new")
    assert raised.value is error
    assert delays == []
    assert target.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("*.tmp"))


def test_serialization_failure_keeps_target_and_creates_no_temporary_file(tmp_path):
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    with pytest.raises(TypeError):
        write_run_json(target, {"unsupported": object()})
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]


def test_concurrent_writers_use_distinct_temporary_files(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    original_replace = file_io.os.replace
    sources: set[Path] = set()
    source_lock = threading.Lock()
    barrier = threading.Barrier(4)

    def replace(source, destination):
        with source_lock:
            first_attempt = source not in sources
            sources.add(source)
        if first_attempt:
            barrier.wait(timeout=5)
        original_replace(source, destination)

    monkeypatch.setattr(file_io.os, "replace", replace)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for index in range(4):
            futures.append(
                pool.submit(write_run_json, target, {"value": index, "text": "中" * 1000})
            )
        for future in futures:
            future.result(timeout=10)
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result.get("value") in range(4)
    assert result.get("text") == "中" * 1000
    assert len(sources) == 4
    assert not list(tmp_path.glob("*.tmp"))


def test_cleanup_error_does_not_mask_original_failure(tmp_path, monkeypatch, caplog):
    target = tmp_path / "result.json"
    original_unlink = Path.unlink
    error = OSError("原始写入错误")
    leftovers = []

    def replace(_source, _destination):
        raise error

    def unlink(path, **_kwargs):
        leftovers.append(path)
        raise PermissionError("临时文件也被占用")

    with monkeypatch.context() as patches:
        patches.setattr(file_io.os, "replace", replace)
        patches.setattr(Path, "unlink", unlink)
        with pytest.raises(OSError) as raised:
            file_io.atomic_write_text(target, "new")
    assert raised.value is error
    assert "PermissionError" in caplog.text
    for path in leftovers:
        original_unlink(path, missing_ok=True)


def test_postprocess_checkpoint_survives_transient_sample_result_lock(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_run_json(run_dir / "summary.json", {"samples": [{"id": "Q023"}]})
    plugin_dir = run_dir / "postprocess/exec/plugins/data-analysis"
    manager = PostprocessManager(tmp_path, tmp_path / "plugins")
    result = {"sampleId": "Q023", "status": "success", "facts": {}, "artifacts": []}
    stage = {
        "status": "success",
        "sampleResults": [result],
        "datasetResult": {"status": "success", "facts": {}, "artifacts": []},
    }
    manifest = {"id": "data-analysis", "apiVersion": "batch-postprocess-v2"}
    original_replace = file_io.os.replace
    blocked = []

    def replace(source, destination):
        if destination.parent.name == "Q023" and not blocked:
            blocked.append(destination)
            raise _windows_error(5)
        original_replace(source, destination)

    monkeypatch.setattr(file_io.os, "replace", replace)
    monkeypatch.setattr(file_io.time, "sleep", lambda _delay: None)
    persisted = manager._persist_stage("run", "exec", plugin_dir, manifest, stage)
    assert persisted.get("status") == "success"
    assert len(blocked) == 1
    saved = json.loads((plugin_dir / "samples/Q023/result.json").read_text(encoding="utf-8"))
    assert saved == result
    assert (plugin_dir / "dashboard.json").is_file()
    assert not list(plugin_dir.rglob("*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 文件共享语义")
def test_real_windows_read_handle_conflict_recovers_after_reader_closes(tmp_path, monkeypatch):
    from ctypes import wintypes

    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    # 允许其它读写，但不允许删除/替换，模拟正在读取看板 JSON 的进程。
    handle = create_file(str(target), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    blocked = threading.Event()
    original_replace = file_io.os.replace

    def replace(source, destination):
        try:
            original_replace(source, destination)
        except PermissionError:
            blocked.set()
            raise

    monkeypatch.setattr(file_io.os, "replace", replace)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            future = pool.submit(file_io.atomic_write_text, target, "new")
            assert blocked.wait(timeout=2), "真实 Windows 句柄没有触发共享冲突"
            assert target.read_text(encoding="utf-8") == "old"
        finally:
            close_handle(handle)
        future.result(timeout=3)
    assert target.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("*.tmp"))
