"""真实 Recorder -> 导入 -> HTTP 附件读取的语义 Trace 回归。"""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.runner import BatchRunManager
from debug_tools.batch_testing.trace_parser import TraceImporter
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.generation_trace_recorder import (
    GenerationTraceRecorder,
    trace_flow,
    trace_phase,
    trace_record,
    trace_span,
)

UID = "batch-1234abcd-00001-000"
RUN = "batch_20261003_000000_1234abcd"


def _record(root: Path, text: str = "完整中文模型输出") -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(UID, enabled=True, trace_root=root)
    token = recorder.activate()
    try:
        with trace_span("dsl", stage="dsl", kind="group"):
            with trace_span("model.physical_call", stage="model", kind="model") as span:
                span.json_artifacts["initial_model_messages"] = [
                    {"role": "user", "content": "完整需求"}
                ]
                span.artifact_roles["initial_model_messages"] = "input"
                span.text_artifacts["initial_assistant_raw"] = text
                span.artifact_roles["initial_assistant_raw"] = "output"
                trace_record(
                    "model.transport_metrics", metrics={"inputTokens": 10, "completionTokens": 20}
                )
        with trace_span("response", stage="response", kind="group") as span:
            span.json_artifacts["generation_response"] = {"status": "success"}
            span.artifact_roles["generation_response"] = "output"
        recorder.finalize(status="success")
    finally:
        recorder.deactivate(token)


def _import(root: Path):
    run_dir = root / "output" / RUN
    view = TraceImporter(root / "traces").import_trace(
        UID,
        run_dir / "Q001" / "attempt_000" / "trace",
        run_dir / "trace_blobs",
    )
    return view, run_dir


@pytest.mark.parametrize(
    "content",
    ["中文模型正文", "", "x" * 300000, "{invalid json"],
    ids=["unicode", "empty", "large", "invalid-json"],
)
def test_real_record_import_http_and_content_ownership(tmp_path, content):
    _record(tmp_path / "traces", content)
    view, run_dir = _import(tmp_path)
    assert view.get("viewVersion") == "trace-view-v2"
    assert view.get("status") == "complete", view.get("warnings")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    model = next(node for node in nodes if node.get("kind") == "model")
    group = next(node for node in nodes if node.get("operation") == "dsl")
    refs = model.get("artifacts")
    assert isinstance(refs, list)
    output = next(ref for ref in refs if ref.get("role") == "output")
    assert output.get("ownerNodeId") == model.get("id")
    assert output.get("label") == "模型原文"
    assert output in group.get("contentIndex", [])
    response_group = next(node for node in nodes if node.get("operation") == "response")
    response_refs = response_group.get("contentIndex")
    assert isinstance(response_refs, list)
    assert any(ref.get("name") == "generation_response" for ref in response_refs)
    assert model.get("metrics") == {"inputTokens": 10, "completionTokens": 20}
    assert view.get("summary", {}).get("totalTokens") == 30
    assert (run_dir / "trace_blob_manifest.json").is_file()
    manager = BatchRunManager(
        tmp_path / "datasets", tmp_path / "output", tmp_path / "traces", tmp_path
    )
    app = FastAPI()
    register_batch_routes(app, manager)
    response = TestClient(app).get(
        f"/debug/batch/runs/{RUN}/trace-artifacts/{output.get('sha256')}"
    )
    assert response.status_code == 200
    assert response.content == content.encode("utf-8")
    assert hashlib.sha256(response.content).hexdigest() == output.get("sha256")


@pytest.mark.parametrize("damage", ["missing", "size", "digest", "unregistered"])
def test_artifact_api_reports_local_failures(tmp_path, damage):
    _record(tmp_path / "traces", "original")
    view, run_dir = _import(tmp_path)
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    model = next(node for node in nodes if node.get("kind") == "model")
    refs = model.get("artifacts")
    assert isinstance(refs, list)
    ref = next(ref for ref in refs if ref.get("role") == "output")
    digest = ref.get("sha256")
    assert isinstance(digest, str)
    path = run_dir / "trace_blobs" / digest
    if damage == "missing":
        path.unlink()
    elif damage == "size":
        path.write_bytes(b"short")
    elif damage == "digest":
        path.write_bytes(b"modified")
    else:
        (run_dir / "trace_blob_manifest.json").write_text('{"blobs":{}}', encoding="utf-8")
    manager = BatchRunManager(
        tmp_path / "datasets", tmp_path / "output", tmp_path / "traces", tmp_path
    )
    app = FastAPI()
    register_batch_routes(app, manager)
    response = TestClient(app).get(f"/debug/batch/runs/{RUN}/trace-artifacts/{digest}")
    assert response.status_code == (409 if damage in {"size", "digest"} else 404)


def test_events_do_not_become_spans_and_span_business_failure_is_explicit(tmp_path):
    recorder = GenerationTraceRecorder()
    recorder.bind_request(UID, enabled=True, trace_root=tmp_path / "traces")
    token = recorder.activate()
    try:
        with trace_span("plan.attempt", stage="plan", kind="group") as span:
            trace_record("some.metric", duration_ms=123.0)
            span.outcome("failed", errorCount=1)
        recorder.finalize(status="failed")
    finally:
        recorder.deactivate(token)
    directory = TraceImporter(tmp_path / "traces").directory_for_uid(UID)
    assert directory is not None
    records = [json.loads(line) for line in (directory / "trace.jsonl").read_text().splitlines()]
    event = next(record for record in records if record.get("event") == "some.metric")
    parent = next(record for record in records if record.get("event") == "plan.attempt")
    assert event.get("recordType") == "event"
    assert event.get("spanId") == parent.get("spanId")
    assert parent.get("status") == "failed"


@pytest.mark.asyncio
async def test_flow_closes_phase_on_cancel_without_changing_exception(tmp_path):
    recorder = GenerationTraceRecorder()
    recorder.bind_request(UID, enabled=True, trace_root=tmp_path / "traces")
    token = recorder.activate()

    @trace_flow
    async def generation():
        trace_phase("plan")
        raise asyncio.CancelledError()

    try:
        with pytest.raises(asyncio.CancelledError):
            await generation()
        recorder.finalize(status="cancelled")
    finally:
        recorder.deactivate(token)
    view = TraceImporter(tmp_path / "traces").read(UID)
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    plan = next(node for node in nodes if node.get("operation") == "plan")
    assert plan.get("status") == "cancelled"


@pytest.mark.parametrize("damage", ["cycle", "orphan", "corrupt_line", "count"])
def test_invalid_structure_never_claims_complete(tmp_path, damage):
    _record(tmp_path / "traces")
    directory = TraceImporter(tmp_path / "traces").directory_for_uid(UID)
    assert directory is not None
    path = directory / "trace.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if damage == "cycle":
        span = next(record for record in records if record.get("recordType") == "span")
        span["parentSpanId"] = span.get("spanId")
    elif damage == "orphan":
        records[0]["spanId"] = "c" * 16
    elif damage == "count":
        records.pop()
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    if damage == "corrupt_line":
        with path.open("a", encoding="utf-8") as output:
            output.write("\n{broken\n")
    view = TraceImporter(tmp_path / "traces").read(UID)
    assert view.get("status") == "invalid"


def test_old_instrumentation_stays_raw_and_is_not_imported_as_semantic(tmp_path):
    _record(tmp_path / "traces")
    directory = TraceImporter(tmp_path / "traces").directory_for_uid(UID)
    assert directory is not None
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.pop("instrumentationVersion")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    view, run_dir = _import(tmp_path)
    assert view.get("rawOnly") is True
    assert view.get("nodes") == []
    assert not (run_dir / "trace_blob_manifest.json").exists()
