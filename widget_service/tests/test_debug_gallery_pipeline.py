"""截图、分析和离线画廊依赖链的集成验证。"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.batch_testing.task_manager import BatchTaskManager
from debug_tools.postprocess_plugins.gallery.capture import run_capture
from debug_tools.postprocess_plugins.gallery.plugin import BatchGalleryManager
from debug_tools.postprocess_plugins.gallery.report import _asset_path, build_document, run_gallery
from fastapi import FastAPI
from fastapi.testclient import TestClient

PLUGINS = Path(__file__).resolve().parents[2] / "debug_tools/postprocess_plugins"


def _write(path: Path, value: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["browser", "device"])
async def test_gallery_consumes_direct_dependencies_and_reuses_history(tmp_path, kind):
    run_dir = tmp_path / "run"
    _write(
        run_dir / "summary.json",
        {
            "runId": "run",
            "status": "completed",
            "samples": [
                {
                    "id": "Q001",
                    "query": "<script>window.injected=1</script>",
                    "size": "2x4",
                    "status": "success",
                },
                {"id": "Q002", "query": "无截图", "status": "failed"},
            ],
        },
    )
    _write(run_dir / "Q001/result.json", {"finalAttempt": 0})
    final = run_dir / "Q001/attempt_000"
    _write(
        final / "blocks.json",
        {
            "designcompactdsl": '["x","SingleLineTitle",{}]',
            "genui": "{}",
            "cardspec": {"dataBindings": []},
        },
    )
    _write(final / "result.json", {"elapsedMs": 10, "status": "success"})
    _write(
        final / "trace/view.json",
        {
            "status": "complete",
            "timingMode": "exact",
            "nodes": [
                {
                    "operation": "interface.attempt",
                    "attempts": {"interface": 1},
                    "status": "success",
                },
            ],
        },
    )
    calls = []

    async def capture(_run, output, _config):
        calls.append(kind)
        (output / "card").mkdir()
        (output / "card/Q001.png").write_bytes(b"unique screenshot")
        return {
            "status": "partial",
            "sampleResults": [
                {
                    "sampleId": "Q001",
                    "status": "success",
                    "facts": {"size": "2x4"},
                    "artifacts": [{"key": f"{kind}-capture", "path": "card/Q001.png"}],
                },
                {"sampleId": "Q002", "status": "failed", "summary": "渲染失败", "artifacts": []},
            ],
            "datasetResult": {
                "status": "partial",
                "artifacts": [
                    {"key": "capture-summary", "data": []},
                ],
            },
        }

    class Host:
        output_root = tmp_path

    manager = PostprocessManager(
        tmp_path,
        PLUGINS,
        builtin_runners={
            f"{kind}-capture": capture,
            f"{kind}-gallery": partial(run_gallery, Host(), kind),
        },
    )
    configs = {"device-capture": {"targetId": "fake-device"}}
    await manager.start()
    try:
        first = manager.enqueue("run", [f"{kind}-gallery"], configs)
        await manager.queue.join()
        execution_id = first.get("executionId")
        assert isinstance(execution_id, str)
        state = manager.get_execution("run", execution_id)
        assert state.get("status") in {"completed", "partial"}
        samples = manager.sample_result("run", execution_id, "data-analysis", "Q001")
        assert samples.get("facts", {}).get("paddedCount") == 1
        path = manager.asset_path("run", execution_id, f"{kind}-gallery", "gallery.html")
        document = path.read_text(encoding="utf-8")
        assert "data:image/png;base64," in document
        assert "精简布局" in document
        assert "渲染失败" in document
        assert "<script>window.injected=1</script>" not in document
        assert "\\u003cscript>" in document
        original = document
        second = manager.enqueue("run", [f"{kind}-gallery"], configs, rerun=True)
        await manager.queue.join()
        assert calls == [kind]
        assert path.read_text(encoding="utf-8") == original
        assert second.get("executionId") != execution_id
        host = object.__new__(BatchTaskManager)
        host.postprocess_manager = manager
        if kind == "device":
            assert (
                host.device_capture_path("run", "Q001", "card").read_bytes() == b"unique screenshot"
            )
            item = host.sample_device_capture("run", "Q001")
            assert item.get("status") == "success"
            assert "/assets/device-capture/card/Q001.png" in item.get("cardUrl", "")
            assert host.device_gallery_path("run").is_file()
        else:
            assert host.gallery_path("run").is_file()
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_browser_capture_records_failure_and_does_not_generate_html(tmp_path):
    (tmp_path / "run").mkdir()

    async def capture(_url, _output):
        return {"items": [{"id": "Q001", "error": "不可渲染"}]}

    manager = BatchGalleryManager(tmp_path, "http://localhost/debug", capture=capture)
    result = await run_capture(manager, "run", tmp_path / "capture", {})
    assert result.get("status") == "partial"
    samples = result.get("sampleResults")
    assert isinstance(samples, list)
    assert samples[0].get("summary") == "不可渲染"
    assert not list(tmp_path.rglob("*.html"))


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/image.png",
        "/debug/batch/runs/run/postprocess/exec/assets/browser-capture/../../other/file.png",
        "/debug/batch/runs/run/postprocess/exec/assets/device-capture/file.png",
        "/debug/batch/runs/other/postprocess/exec/assets/browser-capture/file.png",
    ],
)
def test_gallery_rejects_foreign_or_escaping_asset_urls(tmp_path, url):
    for relative in ("postprocess/exec/plugins/other/file.png", "postprocess/exec/other/file.png"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"outside capture plugin")
    assert _asset_path(tmp_path, "run", {"url": url}, "browser-capture") is None


def test_gallery_accepts_only_existing_capture_asset(tmp_path):
    path = tmp_path / "postprocess/exec/plugins/browser-capture/image.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"capture")
    artifact = {"url": "/debug/batch/runs/run/postprocess/exec/assets/browser-capture/image.png"}
    assert _asset_path(tmp_path, "run", artifact, "browser-capture") == path.resolve()


def test_document_escapes_script_and_preserves_template_like_user_text():
    document = build_document("画廊", "run", [{"query": "</script>{{CREATED}}"}])
    assert "\\u003c/script>{{CREATED}}" in document
    assert "</script>{{CREATED}}" not in document


def test_business_plugin_manifests_have_explicit_analysis_dependency(tmp_path):
    manager = PostprocessManager(tmp_path, PLUGINS)
    manifests = manager._manifests()
    by_id = {}
    for manifest in manifests:
        by_id[manifest.get("id")] = manifest
    for identifier in (
        "browser-gallery",
        "device-gallery",
        "quality-score",
        "validation-failure-gallery",
        "component-recall",
    ):
        manifest = by_id.get(identifier)
        assert manifest is not None
        assert "data-analysis" in manifest.get("dependence", [])


@pytest.mark.parametrize(("suffix", "media_type"), [("png", "image/png"), ("jpeg", "image/jpeg")])
def test_legacy_full_capture_route_preserves_actual_image_type(tmp_path, suffix, media_type):
    path = tmp_path / f"full.{suffix}"
    path.write_bytes(b"image")

    async def idle():
        return None

    host = SimpleNamespace(
        run_manager=None, start=idle, close=idle, device_capture_path=lambda *_args: path
    )
    app = FastAPI()
    register_batch_routes(app, task_manager=host)
    with TestClient(app) as client:
        response = client.get("/debug/batch/runs/run/device-captures/Q001/full")
    assert response.status_code == 200
    assert response.headers.get("content-type") == media_type
