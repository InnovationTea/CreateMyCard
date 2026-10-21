from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from debug_tools.postprocess_plugins.gallery import BatchGalleryManager


def _summary(run_id: str) -> dict:
    return {
        "runId": run_id,
        "status": "completed",
        "success": 1,
        "degraded": 0,
        "failed": 1,
        "cancelled": 0,
        "averageElapsedMs": 12.5,
        "samples": [
            {
                "id": "Q001",
                "title": "天气 <卡片>",
                "query": "显示今天的天气",
                "size": "2x2",
                "status": "success",
                "elapsedMs": 123456.78,
                "attemptCount": 1,
                "traceRecordCount": 3,
                "errorCode": "",
                "error": "",
            },
            {
                "id": "Q002",
                "title": "失败样本",
                "query": "<script>alert(1)</script>",
                "size": "2x4",
                "status": "failed",
                "elapsedMs": 15,
                "attemptCount": 2,
                "traceRecordCount": 1,
                "errorCode": "MODEL_FAILED",
                "error": "没有可用产物",
            },
        ],
    }


def _write_run(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(_summary(run_id), ensure_ascii=False),
        encoding="utf-8",
    )
    return run_dir


@pytest.mark.asyncio
async def test_gallery_embeds_screenshots_and_keeps_all_samples(tmp_path: Path) -> None:
    run_id = "batch_20261004_000000_1234abcd"
    run_dir = _write_run(tmp_path, run_id)

    async def capture(url: str, output_dir: Path) -> dict:
        assert url.endswith(f"/{run_id}/gallery-capture")
        (output_dir / "0001.png").write_bytes(b"png-image")
        return {
            "items": [
                {"id": "Q001", "file": "0001.png", "size": "2x4", "error": ""},
                {"id": "Q002", "file": "", "error": "DSL 渲染失败"},
            ]
        }

    manager = BatchGalleryManager(tmp_path, "http://127.0.0.1:8888/debug", capture=capture)
    state = manager.start(run_id)
    task = manager.tasks.get(run_id)
    assert state.get("status") == "generating"
    assert task is not None
    await task

    status = manager.status(run_id)
    assert status.get("status") == "ready"
    assert status.get("url") == f"/debug/batch/runs/{run_id}/gallery.html"
    document = (run_dir / "gallery.html").read_text(encoding="utf-8")
    assert "data:image/png;base64,cG5nLWltYWdl" in document
    assert "浏览器渲染画廊" in document
    assert "真机渲染" not in document
    assert "123456.78ms" in document
    assert document.index("Q001") < document.index("Q002")
    assert 'data-status="success" data-size="2x4"' in document
    assert "DSL 渲染失败" in document
    assert "天气 &lt;卡片&gt;" in document
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in document
    assert "<script>alert(1)</script>" not in document
    assert not list(run_dir.glob("gallery-*"))


@pytest.mark.asyncio
async def test_gallery_start_is_idempotent_and_failure_is_retryable(tmp_path: Path) -> None:
    run_id = "batch_20261004_000000_1234abcd"
    _write_run(tmp_path, run_id)
    release = asyncio.Event()
    calls = 0

    async def capture(_url: str, _output_dir: Path) -> dict:
        nonlocal calls
        calls += 1
        await release.wait()
        if calls == 1:
            raise RuntimeError("浏览器不可用")
        return {"items": []}

    manager = BatchGalleryManager(tmp_path, "http://127.0.0.1:8888/debug", capture=capture)
    first = manager.start(run_id)
    second = manager.start(run_id)
    first_task = manager.tasks.get(run_id)
    assert first.get("status") == second.get("status") == "generating"
    assert calls == 0
    release.set()
    assert first_task is not None
    await first_task
    assert manager.status(run_id).get("status") == "failed"

    release.clear()
    retry = manager.start(run_id)
    retry_task = manager.tasks.get(run_id)
    assert retry.get("status") == "generating"
    release.set()
    assert retry_task is not None
    await retry_task
    assert calls == 2
    assert manager.status(run_id).get("status") == "ready"
    assert manager.start(run_id).get("status") == "ready"
    assert calls == 2
    forced = manager.start(run_id, force=True)
    forced_task = manager.tasks.get(run_id)
    assert forced.get("status") == "generating"
    assert forced_task is not None
    await forced_task
    assert calls == 3


def test_gallery_rejects_unknown_and_traversal_run_ids(tmp_path: Path) -> None:
    manager = BatchGalleryManager(tmp_path, "http://127.0.0.1:8888/debug")

    with pytest.raises(KeyError):
        manager.start("../outside")
    with pytest.raises(KeyError):
        manager.gallery_path("missing")
