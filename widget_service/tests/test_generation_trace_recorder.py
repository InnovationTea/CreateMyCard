# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.routes import _trace_uid_from_raw_payload
from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from config.config import Settings, get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient
from services import artifact_store
from services.artifact_store import ArtifactStore, ArtifactUploadError
from services.compact_dsl_a2ui_converter import _strip_optional_genui_fence
from services.compact_dsl_interface_retry import run_compact_dsl_with_retry
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    QualityIssue,
    get_dsl_processor,
)
from services.generation_trace_recorder import (
    GenerationTraceRecorder,
    TraceRecord,
    trace_attempt,
    trace_record,
    trace_span,
)
from services.widget_generation_service import WidgetGenerationService

_UID = "create-ABCDEFGH-00001-002"


def _trace_directory(root: Path, uid: str = _UID) -> Path:
    task_type, identifier, request_sequence, caller_retry = uid.split("-")
    return root / task_type / identifier / request_sequence / caller_retry


def _read_records(root: Path, uid: str = _UID) -> list[dict]:
    trace_path = _trace_directory(root, uid) / "trace.jsonl"
    return [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]


def test_trace_record_omits_empty_fields() -> None:
    payload = TraceRecord(
        event="test",
        trace_id="trace-id",
        span_id="span-id",
        parent_span_id=None,
        record_type="event",
        category="other",
        start_offset_ms=0.0,
        stage="",
        status=None,
        attempts={},
        details={"empty": "", "none": None, "zero": 0, "false": False},
        artifacts={},
    ).to_payload(sequence=1, timestamp="2026-09-30T00:00:00+00:00")

    assert payload == {
        "schemaVersion": "generation-trace-v2",
        "traceId": "trace-id",
        "spanId": "span-id",
        "sequence": 1,
        "timestamp": "2026-09-30T00:00:00+00:00",
        "recordType": "event",
        "event": "test",
        "category": "other",
        "startOffsetMs": 0.0,
        "details": {"zero": 0, "false": False},
    }


def test_trace_uid_can_be_read_before_argument_repair() -> None:
    payload = {"content": {"arguments": json.dumps({"uid": _UID})}}

    assert _trace_uid_from_raw_payload(payload) == _UID


def test_artifact_sequence_sha_and_deduplication(tmp_path: Path) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        with trace_attempt(plan=1):
            trace_record(
                "plan.prompt",
                json_artifacts={"plan_prompt": {"messages": ["完整 Prompt"]}},
            )
            trace_record(
                "plan.prompt.reused",
                json_artifacts={"plan_prompt": {"messages": ["完整 Prompt"]}},
            )
    finally:
        recorder.deactivate(token)

    records = _read_records(tmp_path)
    first_ref = records[0]["artifacts"]["plan_prompt"]
    second_ref = records[1]["artifacts"]["plan_prompt"]
    assert first_ref == second_ref
    assert first_ref["path"] == "artifacts/0001_plan_prompt_attempt-1.json"
    assert first_ref["role"] == "input"
    assert len(first_ref["sha256"]) == 64
    assert len(list((_trace_directory(tmp_path) / "artifacts").iterdir())) == 1


def test_trace_v2_span_hierarchy_and_monotonic_offsets(tmp_path: Path) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        with trace_span("outer", stage="plan"):
            trace_record("inside", stage="plan.prompt")
            with trace_span("inner", stage="model"):
                trace_record("leaf", stage="model.execution")
        recorder.finalize(status="success")
    finally:
        recorder.deactivate(token)

    records = _read_records(tmp_path)
    by_event = {record["event"]: record for record in records}
    root = by_event["request.completed"]
    outer = by_event["outer"]
    inner = by_event["inner"]

    assert outer["parentSpanId"] == root["spanId"]
    assert by_event["inside"]["spanId"] == outer["spanId"]
    assert by_event["inside"].get("eventId")
    assert inner["parentSpanId"] == outer["spanId"]
    assert by_event["leaf"]["spanId"] == inner["spanId"]
    assert all(record["startOffsetMs"] >= 0 for record in records)


def test_compact_jsonl_repair_records_trace(tmp_path: Path) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        repaired = _strip_optional_genui_fence(
            '["root","Column",{"width":"matchParent" "height":"matchParent"},[]]'
        )
    finally:
        recorder.deactivate(token)

    record = next(
        item for item in _read_records(tmp_path) if item["event"] == "compact_dsl.jsonl_repair"
    )
    assert json.loads(repaired)[2] == {"width": "matchParent", "height": "matchParent"}
    assert record["recordType"] == "span"
    assert record["category"] == "repair"
    assert record["details"]["blockCount"] == 1
    assert record["details"]["repairedBlockCount"] == 1
    assert record["details"]["repairApplied"] is True
    assert record["artifacts"]["compact_dsl_extracted"]["role"] == "input"
    assert record["artifacts"]["compact_dsl_jsonl_repaired"]["role"] == "output"


def test_same_request_binding_is_idempotent_and_new_request_isolated(
    tmp_path: Path,
) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    recorder.record("first")
    recorder.observe_attempt("interfaceAttempts", 1)
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    recorder.record("second")
    recorder.finalize(status="success")

    first_records = _read_records(tmp_path)
    assert [record["sequence"] for record in first_records] == [1, 2, 3]
    assert first_records[-1]["details"]["attemptCounts"] == {"interfaceAttempts": 1}
    manifest = json.loads(
        (_trace_directory(tmp_path) / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["state"] == "complete"
    assert manifest["recordCount"] == 3
    assert first_records[-1]["spanId"] == manifest["rootSpanId"]

    next_uid = "edit-IJKLMNOP-00002-000"
    recorder.bind_request(next_uid, enabled=True, trace_root=tmp_path)
    recorder.record("new-request")
    assert _read_records(tmp_path, next_uid)[0]["sequence"] == 1


def test_concurrent_append_has_stable_unique_sequence(tmp_path: Path) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(recorder.record, "parallel") for _ in range(80)]
        for future in futures:
            future.result()

    sequences = [record["sequence"] for record in _read_records(tmp_path)]
    assert sequences == list(range(1, 81))


def test_disabled_invalid_uid_and_write_failure_do_not_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=False, trace_root=tmp_path)
    recorder.record("disabled")
    recorder.bind_request("invalid", enabled=True, trace_root=tmp_path)
    recorder.record("invalid")
    assert list(tmp_path.rglob("trace.jsonl")) == []

    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("blocked", encoding="utf-8")
    recorder.bind_request(_UID, enabled=True, trace_root=invalid_root)
    assert recorder.enabled is False

    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    assert recorder.writer is not None

    def fail_write(_record: TraceRecord) -> None:
        raise OSError("read-only trace directory")

    monkeypatch.setattr(recorder.writer, "write_record", fail_write)
    recorder.record("write-failure")
    recorder.finalize(status="failed")
    manifest = json.loads(
        (_trace_directory(tmp_path) / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["state"] == "partial"


@pytest.mark.asyncio
async def test_interface_retry_is_layered_in_summary(tmp_path: Path) -> None:
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    calls = 0
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="天气卡片",
        title="天气",
        description="天气速览",
    )

    async def generate(_request: GenerateWidgetCardRequest) -> GenerateWidgetCardResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                errorCode=ErrorCode.VALIDATION_FAILED,
                suggestSize="2x2",
                message="失败",
            )
        return GenerateWidgetCardResponse(
            status=GenerationStatus.SUCCESS,
            suggestSize="2x2",
            message="成功",
            artifactUrl="https://test.invalid/final.md",
        )

    try:
        result = await run_compact_dsl_with_retry(
            generate,
            request,
            enabled=True,
            retry_count=1,
            request_id="trace-test",
        )
        recorder.finalize(status=result.status.value)
    finally:
        recorder.deactivate(token)

    summary = _read_records(tmp_path)[-1]
    assert summary["details"]["attemptCounts"]["interfaceAttempts"] == 2
    assert summary["details"]["retryCounts"]["interfaceRetries"] == 1
    retry_event = next(
        record
        for record in _read_records(tmp_path)
        if record["event"] == "interface.retry.scheduled"
    )
    assert retry_event["attempts"]["interface"] == 1
    assert retry_event["details"]["nextAttempt"] == 2


class _AsyncTransport:
    async def generate(self, *_args, **_kwargs) -> str:
        return "unused"

    async def aclose(self) -> None:
        return None


class _TracingLlmClientTransport:
    def generate(self, _messages: list[dict[str, str]]) -> str:
        trace_record("thread.context.visible", status="success")
        return "thread-output"


@pytest.mark.asyncio
async def test_llmclient_thread_copies_trace_context(tmp_path: Path) -> None:
    transport = _AsyncTransport()
    runtime = ModelExecutionRuntime(
        Settings(_env_file=None, model_max_concurrency=1),
        mep_transport=transport,
        deepseek_platform_transport=transport,
        llmclient_transport=_TracingLlmClientTransport(),
        deepseek_official_http_transport=transport,
    )
    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        assert await runtime.generate_once("llmclient", []) == "thread-output"
    finally:
        recorder.deactivate(token)
        await runtime.aclose()

    events = [record["event"] for record in _read_records(tmp_path)]
    assert "thread.context.visible" in events
    assert "model.queue" in events
    assert "model.provider_execution" in events


class _FallbackRuntime:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_once(self, *_args, **_kwargs) -> str:
        self.calls += 1
        if self.calls < 3:
            raise ModelTransportError("temporary", code="TEMPORARY")
        return "fallback-output"


@pytest.mark.asyncio
async def test_model_retry_and_provider_fallback_are_counted_separately(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        enable_model_failure_retry=True,
        model_failure_max_retry_attempts=1,
        fallback_model_failure_max_retry_attempts=0,
        enable_openai_fallback=True,
        openai_master_client="llmclient",
        openai_fallback_client="deepseek_official_http",
    )

    async def no_wait(_seconds: float) -> None:
        return None

    recorder = GenerationTraceRecorder()
    recorder.bind_request(_UID, enabled=True, trace_root=tmp_path)
    token = recorder.activate()
    try:
        client = UnifiedModelClient(
            settings,
            _FallbackRuntime(),
            operation_name="trace-test",
            sleep=no_wait,
            random_uniform=lambda lower, _upper: lower,
        )
        result = await client.generate("openai", [], None, phase="initial")
        recorder.finalize(status="success")
    finally:
        recorder.deactivate(token)

    assert result == "fallback-output"
    summary = _read_records(tmp_path)[-1]["details"]
    assert summary["attemptCounts"]["modelLogicalCalls"] == 1
    assert summary["attemptCounts"]["modelPhysicalAttempts"] == 3
    assert summary["retryCounts"]["modelTransportRetries"] == 1
    assert summary["retryCounts"]["providerFallbacks"] == 1


@pytest.mark.asyncio
async def test_compact_mock_flow_records_intermediate_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", True)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path / "traces")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        lambda _self: False,
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        lambda _self: False,
    )

    async def upload(_path: str) -> str:
        return "https://test.invalid/artifact.md"

    monkeypatch.setattr(artifact_store.file_obs, "upload_file", upload)
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        size="2x2",
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    records = _read_records(tmp_path / "traces")
    events = {record["event"] for record in records}
    assert {
        "plan.skipped",
        "model.assistant.received",
        "dsl.binding_repair.completed",
        "dsl.compact_validation.completed",
        "dsl.conversion.completed",
        "dsl.unit_repair.completed",
        "dsl.asset_mapping.completed",
        "artifact_validation.completed",
        "artifact.digest_calculated",
        "artifact.local_write",
        "artifact.upload",
        "request.completed",
    }.issubset(events)
    artifact_names = {name for record in records for name in record.get("artifacts", {})}
    assert "initial_assistant_raw" in artifact_names
    assert "compact_dsl_binding_repaired" in artifact_names
    assert "standard_a2ui_before_unit_repair" in artifact_names
    assert "standard_a2ui_after_unit_repair" in artifact_names
    assert "final_genui" in artifact_names
    span_operations = [
        record.get("operation") for record in records if record.get("recordType") == "span"
    ]
    assert span_operations.count("dsl") == 1
    response_span = next(record for record in records if record.get("operation") == "response")
    assert "generation_response" in response_span.get("artifacts", {})
    assert list((tmp_path / "traces").rglob("model_trace.jsonl")) == []


@pytest.mark.asyncio
async def test_compact_flow_does_not_write_trace_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", False)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path / "traces")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        lambda _self: False,
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        lambda _self: False,
    )

    async def upload(_path: str) -> str:
        return "https://test.invalid/no-trace.md"

    monkeypatch.setattr(artifact_store.file_obs, "upload_file", upload)
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        size="2x2",
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    assert list((tmp_path / "traces").rglob("trace.jsonl")) == []
    assert list((tmp_path / "traces").rglob("model_trace.jsonl")) == []


@pytest.mark.asyncio
async def test_upload_failure_keeps_trace_terminal_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", True)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path / "traces")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        lambda _self: False,
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        lambda _self: False,
    )

    async def upload(_path: str) -> str:
        raise TimeoutError("upload timeout")

    monkeypatch.setattr(artifact_store.file_obs, "upload_file", upload)
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        size="2x2",
    )

    with pytest.raises(ArtifactUploadError):
        await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    records = _read_records(tmp_path / "traces")
    upload_event = next(record for record in records if record["event"] == "artifact.upload")
    assert upload_event["status"] == "failed"
    assert records[-1]["event"] == "request.completed"
    assert records[-1]["details"]["errorCode"] == ErrorCode.ARTIFACT_UPLOAD_FAILED


@pytest.mark.asyncio
async def test_plan_contract_retry_has_independent_trace_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", True)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path / "traces")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    plan_calls = 0

    async def generate(_client, _prompt, profile=None, **_kwargs) -> str:
        nonlocal plan_calls
        if (profile or {}).get("format") != "raw-json":
            return "source-compact-dsl"
        plan_calls += 1
        if plan_calls == 1:
            return "not-json"
        return json.dumps(
            {
                "name": "submit_card_plan",
                "arguments": {
                    "info_required": [
                        {
                            "requirement": "卡片标题",
                            "text": "天气",
                            "componentHints": ["Text"],
                        }
                    ],
                    "layoutHints": ["S-center"],
                },
            },
            ensure_ascii=False,
        )

    def process(source_dsl, _context) -> DslProcessingResult:
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl='{"createSurface":{"surfaceId":"surface_card"}}',
        )

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(processor, "process", process)
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        lambda _self: False,
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        lambda _self: False,
    )
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: SimpleNamespace(
            artifactUrl="https://test.invalid/plan.md",
            artifactDigest="sha256:plan",
        ),
    )
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        size="2x2",
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status == GenerationStatus.SUCCESS
    records = _read_records(tmp_path / "traces")
    summary = records[-1]["details"]
    assert summary["attemptCounts"]["planContractAttempts"] == 2
    assert summary["retryCounts"]["planContractRetries"] == 1
    plan_results = [record for record in records if record["event"] == "plan.validation.completed"]
    assert [record["status"] for record in plan_results] == ["failed", "success"]
    artifact_names = {name for record in records for name in record.get("artifacts", {})}
    assert "plan_validation_errors" in artifact_names
    assert "plan_validation_input" in artifact_names
    assert "accepted_plan" in artifact_names
    assert "dsl_prompt_final" in artifact_names
    phase_operations = [
        record.get("operation")
        for record in records
        if record.get("recordType") == "span"
        and record.get("operation")
        in {"prepare", "plan", "dsl", "validation", "artifact", "response"}
    ]
    assert phase_operations == [
        "prepare",
        "plan",
        "dsl",
        "validation",
        "artifact",
        "response",
    ]


@pytest.mark.asyncio
async def test_quality_repair_records_prompt_model_and_revalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", True)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path / "traces")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 1)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    processing_calls = 0

    def process(source_dsl, _context) -> DslProcessingResult:
        nonlocal processing_calls
        processing_calls += 1
        if processing_calls == 1:
            return DslProcessingResult(
                source_dsl=source_dsl,
                issues=(
                    QualityIssue(
                        stage="conversion",
                        code="TEST_CONVERSION_FAILED",
                        message="需要修复",
                    ),
                ),
            )
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl='{"createSurface":{"surfaceId":"surface_card"}}',
        )

    async def repair(_client, _prompt, _profile=None) -> str:
        return "repaired-source-compact-dsl"

    monkeypatch.setattr(processor, "process", process)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", repair)
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        lambda _self: False,
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        lambda _self: False,
    )
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: SimpleNamespace(
            artifactUrl="https://test.invalid/repaired.md",
            artifactDigest="sha256:repaired",
        ),
    )
    request = GenerateWidgetCardRequest(
        uid=_UID,
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        size="2x2",
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status == GenerationStatus.SUCCESS
    records = _read_records(tmp_path / "traces")
    summary = records[-1]["details"]
    assert summary["attemptCounts"]["qualityRepairAttempts"] == 1
    assert summary["attemptCounts"]["validationEvaluations"] == 2
    assert summary["retryCounts"]["qualityRepairRetries"] == 1
    repair_events = {
        record["event"]: record for record in records if record["event"].startswith("repair.")
    }
    assert repair_events["repair.prompt.built"]["attempts"]["qualityRepair"] == 1
    assert repair_events["repair.model.completed"]["status"] == "success"
    assert any(record.get("stage") == "repair.revalidate" for record in records)
