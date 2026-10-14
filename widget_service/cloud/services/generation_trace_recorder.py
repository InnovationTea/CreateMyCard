# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""generateWidgetCardCompactDsl 的开发调试 Trace。"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any

from app.logger import logger

_MODULE = "[Generation Trace]"
_UID_PATTERN = re.compile(
    r"^(?P<task_type>[A-Za-z]+)-(?P<identifier>[A-Za-z0-9]{8})-"
    r"(?P<request_sequence>\d{5})-(?P<retry_count>\d{3})$"
)
_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
_TRACE_FILE_NAME = "trace.jsonl"
_TRACE_MANIFEST_NAME = "manifest.json"
_TRACE_SCHEMA_VERSION = "generation-trace-v2"
_TRACE_CATEGORIES = frozenset(
    {
        "request",
        "protocol",
        "source",
        "preflight",
        "prompt",
        "plan",
        "model",
        "transform",
        "validation",
        "repair",
        "artifact",
        "response",
        "other",
    }
)
_ARTIFACT_ROLES = frozenset({"input", "output", "diagnostic", "snapshot"})


@dataclass(frozen=True)
class TraceRecord:
    """一条紧凑 Trace 事件；空字段在落盘时自动省略。"""

    event: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    record_type: str
    category: str
    start_offset_ms: float
    event_id: str | None = None
    operation: str | None = None
    kind: str | None = None
    stage: str | None = None
    status: str | None = None
    duration_ms: float | None = None
    attempts: Mapping[str, int] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_payload(self, *, sequence: int, timestamp: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": _TRACE_SCHEMA_VERSION,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "sequence": sequence,
            "timestamp": timestamp,
            "recordType": self.record_type,
            "event": self.event,
            "category": self.category,
            "startOffsetMs": self.start_offset_ms,
        }
        optional_values: dict[str, Any] = {
            "eventId": self.event_id,
            "operation": self.operation,
            "kind": self.kind,
            "stage": self.stage,
            "status": self.status,
            "durationMs": self.duration_ms,
            "attempts": _compact_mapping(self.attempts),
            "details": _compact_mapping(self.details),
            "metrics": _compact_mapping(self.metrics),
            "artifacts": _compact_mapping(self.artifacts),
        }
        if self.parent_span_id:
            payload["parentSpanId"] = self.parent_span_id
        for key, value in optional_values.items():
            if _has_trace_value(value):
                payload[key] = value
        return payload


class _RequestTraceWriter:
    """串行写入事件和附件，并在单次请求内按内容摘要去重。"""

    def __init__(self, trace_directory: Path, uid: str) -> None:
        self.trace_directory = trace_directory
        self.uid = uid
        self.trace_id = uuid.uuid4().hex
        self.root_span_id = uuid.uuid4().hex[:16]
        self.started_at = datetime.now(UTC)
        self.started_perf = time.perf_counter()
        self._write_lock = RLock()
        self._event_sequence = 0
        self._artifact_sequence = 0
        self._artifact_refs_by_digest: dict[str, dict[str, Any]] = {}
        self._has_failures = False
        self._write_manifest(state="recording")

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started_perf) * 1000, 2)

    @staticmethod
    def new_span_id() -> str:
        return uuid.uuid4().hex[:16]

    def write_record(self, record: TraceRecord) -> None:
        with self._write_lock:
            self.trace_directory.mkdir(parents=True, exist_ok=True)
            self._event_sequence += 1
            payload = record.to_payload(
                sequence=self._event_sequence,
                timestamp=datetime.now(UTC).isoformat(),
            )
            output_path = self.trace_directory / _TRACE_FILE_NAME
            jsonl = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            with output_path.open("a", encoding="utf-8", newline="") as output_file:
                output_file.write(jsonl + "\n")

    def finalize_manifest(self, summary: Mapping[str, Any]) -> None:
        state = "partial" if self._has_failures else "complete"
        self._write_manifest(state=state, summary=summary)

    def mark_failure(self) -> None:
        self._has_failures = True

    def _write_manifest(
        self,
        *,
        state: str,
        summary: Mapping[str, Any] | None = None,
    ) -> None:
        self.trace_directory.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schemaVersion": _TRACE_SCHEMA_VERSION,
            "instrumentationVersion": 2,
            "traceId": self.trace_id,
            "rootSpanId": self.root_span_id,
            "uid": self.uid,
            "state": state,
            "startedAt": self.started_at.isoformat(),
            "recordCount": self._event_sequence,
            "artifactCount": self._artifact_sequence,
        }
        if state != "recording":
            payload["completedAt"] = datetime.now(UTC).isoformat()
        if summary:
            payload["summary"] = _compact_mapping(summary)
        output_path = self.trace_directory / _TRACE_MANIFEST_NAME
        temporary = output_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="",
        )
        temporary.replace(output_path)

    def write_artifact(
        self,
        name: str,
        value: Any,
        *,
        extension: str,
        attempts: Mapping[str, int],
    ) -> dict[str, Any]:
        content = self._serialize_artifact(value, extension)
        content_bytes = content.encode("utf-8")
        digest = hashlib.sha256(content_bytes).hexdigest()
        with self._write_lock:
            cached = self._artifact_refs_by_digest.get(digest)
            if cached is not None:
                return dict(cached)
            self._artifact_sequence += 1
            artifacts_dir = self.trace_directory / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            safe_name = self._artifact_file_stem(name, attempts)
            file_name = f"{self._artifact_sequence:04d}_{safe_name}.{extension}"
            output_path = artifacts_dir / file_name
            output_path.write_text(content, encoding="utf-8", newline="")
            relative_path = output_path.relative_to(self.trace_directory).as_posix()
            artifact_ref = {
                "path": relative_path,
                "sha256": digest,
                "bytes": len(content_bytes),
                "chars": len(content),
                "mediaType": ("application/json" if extension == "json" else "text/plain"),
            }
            self._artifact_refs_by_digest[digest] = artifact_ref
            return dict(artifact_ref)

    @staticmethod
    def _serialize_artifact(value: Any, extension: str) -> str:
        if extension == "json":
            return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if isinstance(value, str):
            return value
        return str(value) + "\n"

    @staticmethod
    def _artifact_file_stem(name: str, attempts: Mapping[str, int]) -> str:
        safe_name = _SAFE_NAME_PATTERN.sub("-", name).strip("-.") or "artifact"
        for key in ("plan", "qualityRepair", "modelPhysical", "interface"):
            value = attempts.get(key)
            if value is not None:
                return f"{safe_name}_attempt-{value}"
        return safe_name


@dataclass
class TraceSpan:
    """显式执行区间的可更新结果；关闭 Trace 时也保持相同调用语义。"""

    status: str = "success"
    details: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    text_artifacts: dict[str, str] = field(default_factory=dict)
    json_artifacts: dict[str, Any] = field(default_factory=dict)
    artifact_roles: dict[str, str] = field(default_factory=dict)

    def outcome(self, status: str, **details: Any) -> None:
        self.status = status
        self.details.update(details)


class GenerationTraceRecorder:
    """请求级 Trace Recorder；关闭时所有操作均为无副作用空操作。"""

    def __init__(self) -> None:
        self.enabled = False
        self.uid: str | None = None
        self.writer: _RequestTraceWriter | None = None
        self._binding_key: tuple[str, Path] | None = None
        self._state_lock = RLock()
        self._started_at = 0.0
        self._latency_by_stage: dict[str, float] = defaultdict(float)
        self._attempt_counts: dict[str, int] = defaultdict(int)
        self._retry_counts: dict[str, int] = defaultdict(int)
        self._finalized = False

    def bind_request(self, uid: str, *, enabled: bool, trace_root: Path) -> None:
        """绑定请求目录；同一请求重复绑定不会重置已记录状态。"""
        match = _UID_PATTERN.fullmatch(uid)
        if not enabled:
            self._disable(uid)
            return
        if not match:
            self._disable(uid)
            logger.warning(f"{_MODULE} trace_binding_skipped reason=invalid_uid")
            return
        try:
            trace_dir = trace_root.joinpath(
                match.group("task_type"),
                match.group("identifier"),
                match.group("request_sequence"),
                match.group("retry_count"),
            ).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            self._disable(uid)
            logger.warning(
                f"{_MODULE} trace_binding_skipped reason=invalid_path "
                f"exception_type={type(exc).__name__}"
            )
            return
        binding_key = (uid, trace_dir)
        with self._state_lock:
            if self._binding_key == binding_key and self.writer is not None:
                self.enabled = True
                return
            try:
                writer = _RequestTraceWriter(trace_dir, uid)
            except Exception as exc:
                self._disable(uid)
                logger.warning(
                    f"{_MODULE} trace_binding_skipped reason=writer_initialization_failed "
                    f"exception_type={type(exc).__name__}"
                )
                return
            self.uid = uid
            self.enabled = True
            self.writer = writer
            self._binding_key = binding_key
            self._started_at = time.perf_counter()
            self._latency_by_stage = defaultdict(float)
            self._attempt_counts = defaultdict(int)
            self._retry_counts = defaultdict(int)
            self._finalized = False

    def _disable(self, uid: str) -> None:
        with self._state_lock:
            self.uid = uid
            self.enabled = False
            self.writer = None
            self._binding_key = None

    def activate(self) -> Token | None:
        """把当前 Recorder 放入异步上下文；重复激活同一实例时不创建新 Token。"""
        if not self.enabled or self.writer is None:
            return None
        if _ACTIVE_RECORDER.get() is self:
            return None
        return _ACTIVE_RECORDER.set(self)

    @staticmethod
    def deactivate(token: Token | None) -> None:
        if token is not None:
            _ACTIVE_RECORDER.reset(token)

    def record(
        self,
        event: str,
        *,
        stage: str | None = None,
        status: str | None = None,
        duration_ms: float | None = None,
        details: Mapping[str, Any] | None = None,
        metrics: Mapping[str, Any] | None = None,
        text_artifacts: Mapping[str, str] | None = None,
        json_artifacts: Mapping[str, Any] | None = None,
        artifact_roles: Mapping[str, str] | None = None,
        category: str | None = None,
        operation: str | None = None,
        kind: str = "step",
        _span_id: str | None = None,
        _parent_span_id: str | None = None,
        _start_offset_ms: float | None = None,
        _record_type: str | None = None,
    ) -> None:
        """记录事件及可选附件；任何写入异常都不会向业务链路传播。"""
        if not self.enabled or self.writer is None:
            return
        try:
            attempts = dict(_ATTEMPT_CONTEXT.get() or {})
            merged_details = dict(_DETAIL_CONTEXT.get() or {})
            merged_details.update(details or {})
            artifact_refs: dict[str, dict[str, Any]] = {}
            for name, value in (text_artifacts or {}).items():
                artifact_ref = self.writer.write_artifact(
                    name,
                    value,
                    extension="txt",
                    attempts=attempts,
                )
                artifact_ref["role"] = _artifact_role(name, artifact_roles)
                artifact_refs[name] = artifact_ref
            for name, value in (json_artifacts or {}).items():
                artifact_ref = self.writer.write_artifact(
                    name,
                    value,
                    extension="json",
                    attempts=attempts,
                )
                artifact_ref["role"] = _artifact_role(name, artifact_roles)
                artifact_refs[name] = artifact_ref
            record_type = _record_type or "event"
            if stage and duration_ms is not None and record_type == "span":
                with self._state_lock:
                    self._latency_by_stage[stage] += duration_ms
            end_offset_ms = self.writer.elapsed_ms()
            start_offset_ms = _start_offset_ms
            if start_offset_ms is None:
                start_offset_ms = end_offset_ms
                if duration_ms is not None:
                    start_offset_ms = max(0.0, end_offset_ms - duration_ms)
            resolved_category = category or _event_category(event, stage)
            parent_span_id = _parent_span_id
            if parent_span_id is None and record_type == "span":
                parent_span_id = _SPAN_CONTEXT.get() or self.writer.root_span_id
            span_id = _span_id
            if span_id is None:
                if record_type == "span":
                    span_id = self.writer.new_span_id()
                else:
                    span_id = _SPAN_CONTEXT.get() or self.writer.root_span_id
            self.writer.write_record(
                TraceRecord(
                    event=event,
                    trace_id=self.writer.trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    record_type=record_type,
                    event_id=uuid.uuid4().hex if record_type == "event" else None,
                    operation=(operation or event) if record_type == "span" else None,
                    kind=kind if record_type == "span" else None,
                    category=resolved_category,
                    start_offset_ms=round(start_offset_ms, 2),
                    stage=stage,
                    status=status,
                    duration_ms=duration_ms,
                    attempts=attempts,
                    details=merged_details,
                    metrics=metrics or {},
                    artifacts=artifact_refs,
                )
            )
        except Exception as exc:
            self.writer.mark_failure()
            logger.warning(f"{_MODULE} trace_record_failed exception_type={type(exc).__name__}")

    @contextmanager
    def span(
        self,
        event: str,
        *,
        stage: str,
        details: Mapping[str, Any] | None = None,
        operation: str | None = None,
        kind: str = "step",
    ) -> Iterator[TraceSpan]:
        """记录一个同步或跨 await 使用的壁钟阶段。"""
        result = TraceSpan(details=dict(details or {}))
        if not self.enabled or self.writer is None:
            yield result
            return
        started_at = time.perf_counter()
        span_id = self.writer.new_span_id()
        parent_span_id = _SPAN_CONTEXT.get() or self.writer.root_span_id
        start_offset_ms = self.writer.elapsed_ms()
        token = _SPAN_CONTEXT.set(span_id)
        try:
            yield result
        except BaseException as exc:
            result.outcome(
                "cancelled" if type(exc).__name__ == "CancelledError" else "failed",
                exceptionType=type(exc).__name__,
                message=str(exc),
            )
            raise
        finally:
            self.record(
                event,
                stage=stage,
                status=result.status,
                duration_ms=self._elapsed_ms(started_at),
                details=result.details,
                metrics=result.metrics,
                text_artifacts=result.text_artifacts,
                json_artifacts=result.json_artifacts,
                artifact_roles=result.artifact_roles,
                operation=operation or event,
                kind=kind,
                _span_id=span_id,
                _parent_span_id=parent_span_id,
                _start_offset_ms=start_offset_ms,
                _record_type="span",
            )
            _SPAN_CONTEXT.reset(token)

    @contextmanager
    def attempt_scope(self, **attempts: int) -> Iterator[None]:
        current = dict(_ATTEMPT_CONTEXT.get() or {})
        current.update(attempts)
        token = _ATTEMPT_CONTEXT.set(current)
        try:
            yield
        finally:
            _ATTEMPT_CONTEXT.reset(token)

    @contextmanager
    def detail_scope(self, **details: Any) -> Iterator[None]:
        current = dict(_DETAIL_CONTEXT.get() or {})
        current.update(details)
        token = _DETAIL_CONTEXT.set(current)
        try:
            yield
        finally:
            _DETAIL_CONTEXT.reset(token)

    def observe_attempt(self, kind: str, attempt: int) -> None:
        with self._state_lock:
            self._attempt_counts[kind] = max(self._attempt_counts[kind], attempt)

    def next_attempt(self, kind: str) -> int:
        """分配请求级递增尝试编号，供跨 phase/provider 的物理调用使用。"""
        with self._state_lock:
            self._attempt_counts[kind] += 1
            return self._attempt_counts[kind]

    def increment_attempt(self, kind: str, count: int = 1) -> None:
        with self._state_lock:
            self._attempt_counts[kind] += count

    def increment_retry(self, kind: str, count: int = 1) -> None:
        with self._state_lock:
            self._retry_counts[kind] += count

    def finalize(
        self,
        *,
        status: str,
        error_code: str = "",
        artifact_url: str = "",
        artifact_digest: str = "",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        """写入一次且仅一次的请求终态和分层汇总。"""
        if not self.enabled or self.writer is None:
            return
        with self._state_lock:
            if self._finalized:
                return
            self._finalized = True
            total_duration_ms = self._elapsed_ms(self._started_at)
            summary_details = {
                "totalDurationMs": total_duration_ms,
                "latencyByStage": {
                    key: round(value, 2) for key, value in sorted(self._latency_by_stage.items())
                },
                "attemptCounts": dict(sorted(self._attempt_counts.items())),
                "retryCounts": dict(sorted(self._retry_counts.items())),
                "errorCode": error_code,
                "artifactUrl": artifact_url,
                "artifactDigest": artifact_digest,
            }
            summary_details.update(details or {})
        self.record(
            "request.completed",
            stage="request.total",
            status=status,
            duration_ms=total_duration_ms,
            details=summary_details,
            category="request",
            _span_id=self.writer.root_span_id,
            _parent_span_id="",
            _start_offset_ms=0.0,
            _record_type="span",
            operation="request",
            kind="group",
        )
        try:
            self.writer.finalize_manifest(summary_details)
        except Exception as exc:
            logger.warning(
                f"{_MODULE} trace_manifest_finalize_failed exception_type={type(exc).__name__}"
            )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 2)


_ACTIVE_RECORDER: ContextVar[GenerationTraceRecorder | None] = ContextVar(
    "generation_trace_recorder",
    default=None,
)
_ATTEMPT_CONTEXT: ContextVar[dict[str, int] | None] = ContextVar(
    "generation_trace_attempts",
    default=None,
)
_DETAIL_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "generation_trace_details",
    default=None,
)
_SPAN_CONTEXT: ContextVar[str | None] = ContextVar(
    "generation_trace_span",
    default=None,
)


def current_trace_recorder() -> GenerationTraceRecorder | None:
    recorder = _ACTIVE_RECORDER.get()
    if recorder is None or not recorder.enabled:
        return None
    return recorder


def trace_record(event: str, **kwargs: Any) -> None:
    recorder = current_trace_recorder()
    if recorder is not None:
        recorder.record(event, **kwargs)


def trace_observe_attempt(kind: str, attempt: int) -> None:
    recorder = current_trace_recorder()
    if recorder is not None:
        recorder.observe_attempt(kind, attempt)


def trace_next_attempt(kind: str) -> int:
    recorder = current_trace_recorder()
    if recorder is None:
        return 0
    return recorder.next_attempt(kind)


def trace_increment_attempt(kind: str, count: int = 1) -> None:
    recorder = current_trace_recorder()
    if recorder is not None:
        recorder.increment_attempt(kind, count)


def trace_increment_retry(kind: str, count: int = 1) -> None:
    recorder = current_trace_recorder()
    if recorder is not None:
        recorder.increment_retry(kind, count)


@contextmanager
def trace_span(
    event: str,
    *,
    stage: str,
    details: Mapping[str, Any] | None = None,
    operation: str | None = None,
    kind: str = "step",
):
    recorder = current_trace_recorder()
    if recorder is None:
        yield TraceSpan()
        return
    with recorder.span(
        event,
        stage=stage,
        details=details,
        operation=operation,
        kind=kind,
    ) as span:
        yield span


def trace_step(event: str, **kwargs: Any) -> None:
    """显式步骤记录；调用者必须测量该步骤的真实执行区间。"""
    trace_record(event, _record_type="span", **kwargs)


class _TraceFlow:
    """管理异步生成流程中依次执行的阶段，不推算或补造阶段耗时。"""

    def __init__(self) -> None:
        self.scope: Any = None
        self.span: TraceSpan | None = None

    def switch(self, operation: str) -> None:
        self.close()
        self.scope = trace_span(operation, stage=operation, operation=operation, kind="group")
        self.span = self.scope.__enter__()

    def close(self, exc: BaseException | None = None) -> None:
        if self.scope is not None:
            self.scope.__exit__(type(exc) if exc else None, exc, exc.__traceback__ if exc else None)
        self.scope = None
        self.span = None


_FLOW_CONTEXT: ContextVar[_TraceFlow | None] = ContextVar("generation_trace_flow", default=None)


def trace_phase(operation: str) -> None:
    flow = _FLOW_CONTEXT.get()
    if flow is not None:
        flow.switch(operation)


def trace_phase_outcome(status: str, **details: Any) -> None:
    flow = _FLOW_CONTEXT.get()
    if flow is not None and flow.span is not None:
        flow.span.outcome(status, **details)


def trace_flow(function):
    """确保提前返回、异常和取消时最后一个阶段也能正确终结。"""

    @wraps(function)
    async def wrapped(*args, **kwargs):
        flow = _TraceFlow()
        token = _FLOW_CONTEXT.set(flow)
        failure: BaseException | None = None
        try:
            flow.switch("prepare")
            result = await function(*args, **kwargs)
            status = getattr(result, "status", None)
            if status is not None:
                trace_phase_outcome(getattr(status, "value", str(status)))
            if flow.span is not None and hasattr(result, "model_dump"):
                flow.span.json_artifacts["generation_response"] = result.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                flow.span.artifact_roles["generation_response"] = "output"
            return result
        except BaseException as exc:
            failure = exc
            raise
        finally:
            flow.close(failure)
            _FLOW_CONTEXT.reset(token)

    return wrapped


def trace_operation(operation: str, *, kind: str = "step", capture: Any = None):
    """在已有函数边界建立真实区间，并从具名结果读取业务状态。"""

    def decorate(function):
        def complete(span: TraceSpan, result: Any) -> None:
            status = getattr(result, "status", None)
            errors = getattr(result, "errors", None)
            if status is not None:
                span.outcome(getattr(status, "value", str(status)))
            elif errors:
                span.outcome("failed", errorCount=len(errors))
            elif isinstance(result, list) and result:
                span.outcome("failed", errorCount=len(result))
            if capture is not None:
                try:
                    capture(span, result)
                except Exception as exc:
                    recorder = current_trace_recorder()
                    if recorder is not None and recorder.writer is not None:
                        recorder.writer.mark_failure()
                    logger.warning(
                        f"{_MODULE} trace_capture_failed "
                        f"operation={operation} exception_type={type(exc).__name__}"
                    )

        @wraps(function)
        async def async_wrapped(*args, **kwargs):
            with trace_span(operation, stage=operation, kind=kind) as span:
                result = await function(*args, **kwargs)
                complete(span, result)
                return result

        @wraps(function)
        def sync_wrapped(*args, **kwargs):
            with trace_span(operation, stage=operation, kind=kind) as span:
                result = function(*args, **kwargs)
                complete(span, result)
                return result

        return async_wrapped if inspect.iscoroutinefunction(function) else sync_wrapped

    return decorate


@contextmanager
def trace_attempt(**attempts: int):
    recorder = current_trace_recorder()
    if recorder is None:
        yield
        return
    with recorder.attempt_scope(**attempts):
        yield


@contextmanager
def trace_details(**details: Any):
    recorder = current_trace_recorder()
    if recorder is None:
        yield
        return
    with recorder.detail_scope(**details):
        yield


def _compact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            item = _compact_mapping(item)
        elif isinstance(item, list):
            item = [_compact_value(child) for child in item]
            item = [child for child in item if _has_trace_value(child)]
        elif isinstance(item, tuple):
            item = tuple(
                child
                for child in (_compact_value(child) for child in item)
                if _has_trace_value(child)
            )
        if _has_trace_value(item):
            compacted[key] = item
    return compacted


def _compact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _compact_mapping(value)
    return value


def _has_trace_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (Mapping, list, tuple, set)):
        return bool(value)
    return True


def _artifact_role(name: str, roles: Mapping[str, str] | None) -> str:
    configured = (roles or {}).get(name)
    if configured in _ARTIFACT_ROLES:
        return configured
    lowered = name.casefold()
    if "error" in lowered or "warning" in lowered or "validation" in lowered:
        return "diagnostic"
    if "prompt" in lowered or "request" in lowered or "source" in lowered:
        return "input"
    if "result" in lowered or "output" in lowered or "final" in lowered:
        return "output"
    return "snapshot"


def _event_category(event: str, stage: str | None) -> str:
    source = f"{event}.{stage or ''}".casefold()
    mappings = (
        ("request", ("request", "interface")),
        ("protocol", ("protocol", "registry")),
        ("source", ("source_artifact",)),
        ("preflight", ("preflight",)),
        ("prompt", ("prompt",)),
        ("plan", ("plan",)),
        ("model", ("model",)),
        ("validation", ("validation", "validate")),
        ("repair", ("repair",)),
        ("artifact", ("artifact", "upload", "digest")),
        ("transform", ("dsl", "convert", "mapping", "unit")),
        ("response", ("response",)),
    )
    for category, keywords in mappings:
        if any(keyword in source for keyword in keywords):
            return category
    return "other"
