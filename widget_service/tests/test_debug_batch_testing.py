from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.batch_testing.api import _default_paths, register_batch_routes
from debug_tools.batch_testing.runner import (
    BatchRunManager,
    discover_datasets,
    normalize_endpoint,
    prepare_request,
)
from debug_tools.batch_testing.trace_parser import TraceImporter
from debug_tools.end_to_end_debug.backend.debug_agent.config import DebugSettings
from debug_tools.end_to_end_debug.backend.server import create_app as create_full_app
from debug_tools.static_site import create_frontend_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _request(query: str = "生成天气卡片") -> dict:
    return {
        "content": {
            "userQuery": query,
            "title": "天气",
            "description": "天气卡片",
            "size": "2x2",
        },
        "session": {"sessionId": "source", "interactionId": "1"},
        "userAuth": {"user": {"userId": "source-user"}},
        "deviceInfo": {"prdVer": "12.0.0.1", "romVersion": "7.0"},
        "bundleName": "com.omega_w_0823.hmservice",
    }


def _write_dataset(root: Path, name: str, query: str = "生成天气卡片") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.json").write_text(
        json.dumps(_request(query), ensure_ascii=False),
        encoding="utf-8",
    )


def _artifact_text() -> str:
    return """```cardspec
{"title":"天气","description":"天气卡片","suggestSize":"2x2"}
```
```genui
{"version":"v0.9","createSurface":{}}
{"version":"v0.9","updateComponents":{}}
{"version":"v0.9","updateDataModel":{}}
```
```schema
{"schemaVersion":"widget-artifact-v2"}
```
"""


def _write_v2_trace(trace_root: Path, uid: str) -> None:
    parts = uid.split("-")
    trace_dir = trace_root.joinpath(parts[0], parts[1], parts[2], parts[3])
    trace_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schemaVersion": "generation-trace-v2",
        "traceId": "a" * 32,
        "spanId": "b" * 16,
        "sequence": 1,
        "timestamp": "2026-10-02T00:00:00+00:00",
        "recordType": "span",
        "operation": "request",
        "kind": "group",
        "event": "request.completed",
        "category": "request",
        "startOffsetMs": 0.0,
        "durationMs": 10.0,
        "status": "success",
        "details": {"totalDurationMs": 10.0},
    }
    (trace_dir / "trace.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (trace_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "generation-trace-v2",
                "traceId": "a" * 32,
                "rootSpanId": "b" * 16,
                "instrumentationVersion": 2,
                "uid": uid,
                "state": "complete",
                "recordCount": 1,
                "summary": {"totalDurationMs": 10.0},
            }
        ),
        encoding="utf-8",
    )


def test_dataset_discovery_keeps_invalid_entries_visible(tmp_path):
    _write_dataset(tmp_path, "Q001")
    (tmp_path / "Q002.json").write_text("[]", encoding="utf-8")

    items = discover_datasets(tmp_path)

    assert [item.sample_id for item in items] == ["Q001", "Q002"]
    assert items[0].valid is True
    assert items[1].valid is False
    assert "根节点" in items[1].error


def test_prepare_request_overrides_uid_without_mutating_source():
    source = _request()

    prepared = prepare_request(
        source,
        uid="batch-1234abcd-00001-002",
        run_token="1234abcd",
        sample_id="Q001",
        attempt=2,
    )

    content = prepared.get("content")
    user_auth = prepared.get("userAuth")
    session = prepared.get("session")
    source_content = source.get("content")
    source_user_auth = source.get("userAuth")
    assert isinstance(content, dict)
    assert isinstance(user_auth, dict)
    assert isinstance(session, dict)
    assert isinstance(source_content, dict)
    assert isinstance(source_user_auth, dict)
    user = user_auth.get("user")
    source_user = source_user_auth.get("user")
    assert isinstance(user, dict)
    assert isinstance(source_user, dict)
    assert content.get("uid") == "batch-1234abcd-00001-002"
    assert user.get("userId") == "batch-1234abcd-00001-002"
    assert session.get("interactionId") == "Q001-002"
    assert source_content.get("uid") is None
    assert source_user.get("userId") == "source-user"


def test_trace_reader_rejects_non_v2_trace(tmp_path):
    trace_dir = tmp_path / "batch" / "1234abcd" / "00001" / "000"
    trace_dir.mkdir(parents=True)
    (trace_dir / "model_trace.jsonl").write_text(
        '{"model_output":"first"}\ninvalid\n{"model_output":"second"}\n',
        encoding="utf-8",
    )
    (trace_dir / "future_trace.jsonl").write_text(
        '{"kind":"prompt","value":"hello"}\n',
        encoding="utf-8",
    )

    bundle = TraceImporter(tmp_path).read("batch-1234abcd-00001-000")

    assert bundle.get("status") == "invalid"
    assert bundle.get("sourceSchemaVersion") == ""
    assert bundle.get("recordCount") == 0
    assert bundle.get("nodes") == []
    assert len(bundle.get("warnings", [])) == 1


def test_trace_reader_reports_missing_without_failing(tmp_path):
    importer = TraceImporter(tmp_path)
    bundle = importer.read("batch-1234abcd-00001-000")
    destination = tmp_path / "attempt" / "trace"
    imported = importer.import_trace(
        "batch-1234abcd-00001-000",
        destination,
        tmp_path / "trace_blobs",
    )

    assert bundle.get("status") == "missing"
    assert bundle.get("recordCount") == 0
    assert imported.get("status") == "missing"
    assert (destination / "import_manifest.json").is_file()
    assert (destination / "view.json").is_file()


def test_trace_v2_import_validates_and_deduplicates_artifacts(tmp_path):
    trace_root = tmp_path / "traces"
    trace_dir = trace_root / "batch" / "1234abcd" / "00001" / "000"
    artifact_dir = trace_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    content = b'{"messages":[{"role":"user","content":"hello"}]}\n'
    digest = hashlib.sha256(content).hexdigest()
    (artifact_dir / "prompt.json").write_bytes(content)
    record = {
        "schemaVersion": "generation-trace-v2",
        "traceId": "a" * 32,
        "spanId": "b" * 16,
        "sequence": 1,
        "timestamp": "2026-10-02T00:00:00+00:00",
        "recordType": "span",
        "operation": "request",
        "kind": "group",
        "event": "request.completed",
        "category": "request",
        "startOffsetMs": 0.0,
        "durationMs": 12.5,
        "status": "success",
        "details": {"totalDurationMs": 12.5},
        "artifacts": {
            "request": {
                "path": "artifacts/prompt.json",
                "sha256": digest,
                "bytes": len(content),
                "mediaType": "application/json",
                "role": "input",
            }
        },
    }
    (trace_dir / "trace.jsonl").write_text(
        json.dumps(record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (trace_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "generation-trace-v2",
                "traceId": "a" * 32,
                "rootSpanId": "b" * 16,
                "instrumentationVersion": 2,
                "uid": "batch-1234abcd-00001-000",
                "state": "complete",
                "recordCount": 1,
                "summary": {"totalDurationMs": 12.5},
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "attempt" / "trace"
    blob_root = tmp_path / "run" / "trace_blobs"

    reader = TraceImporter(trace_root)
    first = reader.import_trace(
        "batch-1234abcd-00001-000",
        destination,
        blob_root,
    )
    second = reader.import_trace(
        "batch-1234abcd-00001-000",
        tmp_path / "attempt2" / "trace",
        blob_root,
    )

    assert first["status"] == "complete"
    assert first["timingMode"] == "exact"
    assert first["nodes"][0]["artifacts"][0]["role"] == "input"
    assert second["nodes"][0]["artifacts"][0]["available"] is True
    assert len(list(blob_root.iterdir())) == 1
    assert (destination / "source" / "trace.jsonl").is_file()
    assert (destination / "view.json").is_file()


def test_trace_v2_rejects_artifact_path_outside_trace_directory(tmp_path):
    trace_root = tmp_path / "traces"
    trace_dir = trace_root / "batch" / "1234abcd" / "00001" / "000"
    trace_dir.mkdir(parents=True)
    outside = trace_root / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    digest = hashlib.sha256(b"secret").hexdigest()
    record = {
        "schemaVersion": "generation-trace-v2",
        "traceId": "a" * 32,
        "spanId": "b" * 16,
        "sequence": 1,
        "timestamp": "2026-10-02T00:00:00+00:00",
        "recordType": "span",
        "operation": "request",
        "kind": "group",
        "event": "request.completed",
        "category": "request",
        "startOffsetMs": 0.0,
        "durationMs": 0.0,
        "status": "success",
        "artifacts": {"bad": {"path": "../../../../secret.txt", "sha256": digest}},
    }
    (trace_dir / "trace.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (trace_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "generation-trace-v2",
                "traceId": "a" * 32,
                "rootSpanId": "b" * 16,
                "instrumentationVersion": 2,
                "uid": "batch-1234abcd-00001-000",
                "state": "complete",
                "recordCount": 1,
                "summary": {"totalDurationMs": 0.0},
            }
        ),
        encoding="utf-8",
    )

    view = TraceImporter(trace_root).read("batch-1234abcd-00001-000")

    assert view["status"] == "partial"
    assert view["nodes"][0]["artifacts"][0]["available"] is False
    assert "越界" in view["nodes"][0]["artifacts"][0]["error"]


def test_normalize_endpoint_appends_operation_and_rejects_invalid_scheme():
    assert normalize_endpoint("ws://127.0.0.1:8855/api/v1/ws/tools").endswith(
        "/generateWidgetCardCompactDsl"
    )
    with pytest.raises(ValueError, match="ws://"):
        normalize_endpoint("http://127.0.0.1:8855")


def test_trace_root_configuration_prefers_cli_then_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIDGET_SERVICE_GENERATION_TRACE_ROOT", raising=False)
    default_root = _default_paths()[2]
    monkeypatch.setenv("WIDGET_SERVICE_GENERATION_TRACE_ROOT", "environment-traces")

    environment_root = _default_paths()[2]
    explicit_root = _default_paths(Path("custom-traces"))[2]

    assert default_root.name == "traces"
    assert default_root.parent.name == "workspace"
    assert default_root.parent.parent.name == "widget_service"
    assert environment_root.name == "environment-traces"
    assert environment_root.parent.name == "widget_service"
    assert explicit_root.name == "custom-traces"
    assert explicit_root.parent.name == "widget_service"


def test_default_paths_use_sibling_debug_tools_and_widget_service_cloud() -> None:
    datasets_root, output_root, _trace_root, cloud_root = _default_paths()
    repository_root = Path(__file__).resolve().parents[2]

    assert datasets_root == repository_root / "debug_tools" / "Datasets"
    assert output_root == repository_root / "debug_tools" / "batch_output"
    assert cloud_root == repository_root / "widget_service" / "cloud"


def test_sample_detail_recovers_trace_created_after_batch_import(tmp_path):
    output_root = tmp_path / "output"
    trace_root = tmp_path / "traces"
    run_id = "batch_20261003_181435_69a0b9ae"
    uid = "batch-69a0b9ae-00001-000"
    run_dir = output_root / run_id
    sample_dir = run_dir / "Q001"
    attempt_dir = sample_dir / "attempt_000"
    trace_dir = attempt_dir / "trace"
    trace_dir.mkdir(parents=True)
    missing_view = {
        "viewVersion": "trace-view-v2",
        "status": "missing",
        "recordCount": 0,
        "summary": {"totalDurationMs": 0.0},
        "nodes": [],
        "warnings": ["未找到对应 Trace 目录"],
    }
    attempt_result = {
        "attempt": 0,
        "uid": uid,
        "traceStatus": "missing",
        "traceRecordCount": 0,
    }
    sample_result = {
        "id": "Q001",
        "finalAttempt": 0,
        "traceStatus": "missing",
        "traceRecordCount": 0,
    }
    summary = {
        "runId": run_id,
        "traceWarnings": 1,
        "samples": [dict(sample_result)],
    }
    (trace_dir / "view.json").write_text(json.dumps(missing_view), encoding="utf-8")
    (attempt_dir / "result.json").write_text(json.dumps(attempt_result), encoding="utf-8")
    (sample_dir / "result.json").write_text(json.dumps(sample_result), encoding="utf-8")
    for name in ("manifest.json", "summary.json"):
        (run_dir / name).write_text(json.dumps(summary), encoding="utf-8")
    _write_v2_trace(trace_root, uid)
    manager = BatchRunManager(
        tmp_path / "datasets",
        output_root,
        trace_root,
        tmp_path / "cloud",
    )

    detail = manager.get_sample(run_id, "Q001")

    attempts = detail.get("attempts")
    assert isinstance(attempts, list)
    assert attempts[0].get("trace", {}).get("status") == "complete"
    assert detail.get("summary", {}).get("traceStatus") == "complete"
    assert detail.get("summary", {}).get("traceRecordCount") == 1
    persisted_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert persisted_summary.get("traceWarnings") == 0
    assert persisted_summary.get("samples", [])[0].get("traceStatus") == "complete"


def test_trace_artifact_api_only_serves_registered_digest(tmp_path):
    dataset_root = tmp_path / "datasets"
    output_root = tmp_path / "output"
    trace_root = tmp_path / "traces"
    cloud_root = tmp_path / "cloud"
    run_id = "batch_20261002_000000_1234abcd"
    digest = hashlib.sha256(b"trace content").hexdigest()
    view_dir = output_root / run_id / "Q001" / "attempt_000" / "trace"
    view_dir.mkdir(parents=True)
    (output_root / run_id / "trace_blobs").mkdir()
    (output_root / run_id / "trace_blobs" / digest).write_bytes(b"trace content")
    (output_root / run_id / "trace_blob_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "blobs": {
                    digest: {"bytes": len(b"trace content"), "mediaType": "text/plain"},
                },
            }
        ),
        encoding="utf-8",
    )
    (view_dir / "view.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "artifacts": [
                            {
                                "sha256": digest,
                                "available": True,
                                "mediaType": "text/plain",
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    manager = BatchRunManager(dataset_root, output_root, trace_root, cloud_root)
    app = FastAPI()
    register_batch_routes(app, manager)
    client = TestClient(app)

    response = client.get(f"/debug/batch/runs/{run_id}/trace-artifacts/{digest}")
    invalid_response = client.get(f"/debug/batch/runs/{run_id}/trace-artifacts/not-a-digest")

    assert response.status_code == 200
    assert response.content == b"trace content"
    assert response.headers["content-type"].startswith("text/plain")
    assert invalid_response.status_code == 404


@pytest.mark.asyncio
async def test_batch_runner_honors_concurrency_retries_and_persists_trace(tmp_path):
    dataset_root = tmp_path / "datasets"
    output_root = tmp_path / "output"
    trace_root = tmp_path / "traces"
    cloud_root = tmp_path / "cloud"
    workspace = cloud_root / "workspace"
    workspace.mkdir(parents=True)
    artifact_path = workspace / "artifact_test.md"
    artifact_path.write_text(_artifact_text(), encoding="utf-8")
    for index in range(1, 4):
        _write_dataset(dataset_root, f"Q{index:03d}", f"query-{index}")
    active = 0
    maximum_active = 0
    calls: dict[str, int] = {}

    async def invoke(_endpoint, request, _timeout):
        nonlocal active, maximum_active
        content = request.get("content")
        assert isinstance(content, dict)
        uid = content.get("uid")
        assert isinstance(uid, str)
        session = request.get("session")
        assert isinstance(session, dict)
        interaction_id = session.get("interactionId")
        assert isinstance(interaction_id, str)
        sample = interaction_id.split("-")[0]
        calls[sample] = calls.get(sample, 0) + 1
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        _write_v2_trace(trace_root, uid)
        if calls[sample] == 1:
            return {"status": "failed", "errorCode": "VALIDATION_FAILED", "data": {}}
        return {
            "status": "success",
            "errorCode": "",
            "data": {"artifactUrl": f"https://obs.todo.local/{artifact_path.name}"},
        }

    manager = BatchRunManager(
        dataset_root,
        output_root,
        trace_root,
        cloud_root,
        invoke=invoke,
    )
    started = manager.start_run(
        ["Q001", "Q002", "Q003"],
        "ws://127.0.0.1:8855/api/v1/ws/tools",
        concurrency=2,
        max_retries=1,
    )
    run_id = started.get("runId")
    assert isinstance(run_id, str)
    task = manager.tasks[run_id]
    await task
    summary = manager.get_run(run_id)

    assert maximum_active == 2
    assert summary.get("status") == "completed"
    assert summary.get("success") == 3
    assert summary.get("traceWarnings") == 0
    assert all(sample.get("attemptCount") == 2 for sample in summary.get("samples", []))
    run_dir = output_root / run_id
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "Q001" / "attempt_001" / "genui.jsonl").is_file()
    assert manager.get_sample(run_id, "Q001").get("attempts")


@pytest.mark.parametrize(
    "app",
    [
        create_frontend_app(),
        create_full_app(DebugSettings(), production_settings=SimpleNamespace()),
    ],
    ids=["frontend", "full"],
)
def test_debug_apps_expose_batch_routes(app):
    paths = {route.path for route in app.routes}

    assert "/debug/batch/datasets" in paths
    assert "/debug/batch/runs" in paths
    assert "/debug/batch/runs/{run_id}/samples/{sample_id}" in paths
    assert "/debug/batch/runs/{run_id}/trace-artifacts/{digest}" in paths


@pytest.mark.parametrize(
    "app",
    [
        create_frontend_app(),
        create_full_app(DebugSettings(), production_settings=SimpleNamespace()),
    ],
    ids=["frontend", "full"],
)
def test_debug_apps_serve_harmonyos_fonts_from_render_assets(app):
    client = TestClient(app)

    response = client.get("/fonts/harmonyos/HarmonyOS_Sans_SC_Regular.ttf")
    missing = client.get("/fonts/harmonyos/not-found.ttf")

    assert response.status_code == 200
    assert response.headers.get("content-type") == "font/ttf"
    assert response.content
    assert missing.status_code == 404
