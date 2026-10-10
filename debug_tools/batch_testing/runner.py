"""DSL 批跑执行器与持久化状态管理。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import re
import shutil
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import websockets

from debug_tools.end_to_end_debug.backend.debug_agent.upstream_ws_client import (
    UpstreamToolError,
    parse_legacy_stream_content,
)

from .artifacts import download_artifact, parse_artifact_blocks, write_artifact_blocks
from .trace_parser import TraceImporter

_OPERATION = "generateWidgetCardCompactDsl"
_SAMPLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_TRACE_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_DETERMINISTIC_ERROR_CODES = frozenset(
    {
        "INVALID_ARGUMENTS",
        "APP_VERSION_UNSUPPORTED",
        "PROTOCOL_CAPABILITY_UNSUPPORTED",
    }
)
InvokeCallable = Callable[[str, dict[str, Any], float], Awaitable[dict[str, Any]]]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def normalize_endpoint(base_url: str) -> str:
    configured = base_url.strip()
    parsed = urlsplit(configured)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise ValueError("微服务地址必须是完整的 ws:// 或 wss:// URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("微服务地址不能包含认证信息或 fragment")
    path = parsed.path.rstrip("/")
    if not path.endswith(f"/{_OPERATION}"):
        path = f"{path}/{_OPERATION}"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


async def invoke_generate(
    endpoint: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """发送完整工具包络并等待、校验 final 帧。"""

    session = payload.get("session")
    if not isinstance(session, dict):
        raise ValueError("请求缺少 session")
    session_id = session.get("sessionId")
    interaction_id = session.get("interactionId")
    request_id = f"{session_id}&{interaction_id}"
    frames: list[dict[str, Any]] = []
    try:
        async with websockets.connect(
            endpoint,
            open_timeout=15,
            close_timeout=5,
            ping_interval=None,
            ping_timeout=None,
        ) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout_seconds)
                if not isinstance(raw, str):
                    raise UpstreamToolError("正式工具返回非文本 WebSocket 帧")
                frame = json.loads(raw)
                if not isinstance(frame, dict):
                    raise UpstreamToolError("正式工具返回帧不是对象")
                frames.append(frame)
                outer_error = frame.get("errorCode")
                if outer_error not in (None, "", "0", 0):
                    raise UpstreamToolError(f"正式工具外层错误: {outer_error}")
                reply = frame.get("reply")
                stream_info = reply.get("streamInfo") if isinstance(reply, dict) else None
                if not isinstance(stream_info, dict):
                    raise UpstreamToolError("正式工具帧缺少 streamInfo")
                stream_type = stream_info.get("streamType")
                if stream_type in {"start", "partial", "command"}:
                    continue
                if stream_type not in {"final", "final_error"}:
                    raise UpstreamToolError("正式工具返回未知流类型")
                content = stream_info.get("streamContent")
                if not isinstance(content, str) or not content:
                    raise UpstreamToolError("正式工具 final 缺少 streamContent")
                parsed_content = parse_legacy_stream_content(content)
                if parsed_content.get("requestId") != request_id:
                    raise UpstreamToolError("正式工具 requestId 与当前请求不匹配")
                if parsed_content.get("operation") != _OPERATION:
                    raise UpstreamToolError("正式工具 operation 与当前请求不匹配")
                data = parsed_content.get("data")
                return {
                    "requestId": request_id,
                    "status": str(parsed_content.get("status") or "failed"),
                    "errorCode": str(parsed_content.get("errorCode") or ""),
                    "error": parsed_content.get("error"),
                    "data": data if isinstance(data, dict) else {},
                    "frames": frames,
                }
    except TimeoutError as exc:
        raise UpstreamToolError("正式工具 WebSocket 调用超时") from exc
    except json.JSONDecodeError as exc:
        raise UpstreamToolError("正式工具返回非法 JSON") from exc
    except UpstreamToolError:
        raise
    except (OSError, websockets.WebSocketException) as exc:
        raise UpstreamToolError(f"正式工具 WebSocket 调用失败: {type(exc).__name__}") from exc


@dataclass(frozen=True)
class DatasetItem:
    sample_id: str
    file_name: str
    path: Path
    title: str
    query: str
    size: str
    valid: bool
    error: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.sample_id,
            "fileName": self.file_name,
            "title": self.title,
            "query": self.query,
            "size": self.size,
            "valid": self.valid,
            "error": self.error,
        }


def discover_datasets(dataset_root: Path) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    if not dataset_root.is_dir():
        return items
    for path in sorted(dataset_root.glob("*.json"), key=lambda item: item.name.lower()):
        sample_id = path.stem
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON 根节点必须是对象")
            content = payload.get("content")
            if not isinstance(content, dict):
                raise ValueError("请求缺少 content 对象")
            user_query = content.get("userQuery")
            if not isinstance(user_query, str) or not user_query.strip():
                raise ValueError("content.userQuery 必须是非空字符串")
            items.append(
                DatasetItem(
                    sample_id=sample_id,
                    file_name=path.name,
                    path=path,
                    title=str(content.get("title") or sample_id),
                    query=user_query,
                    size=str(content.get("size") or ""),
                    valid=True,
                )
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            items.append(
                DatasetItem(
                    sample_id=sample_id,
                    file_name=path.name,
                    path=path,
                    title=sample_id,
                    query="",
                    size="",
                    valid=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return items


def prepare_request(
    source: dict[str, Any],
    *,
    uid: str,
    run_token: str,
    sample_id: str,
    attempt: int,
) -> dict[str, Any]:
    payload = copy.deepcopy(source)
    content = payload.get("content")
    if not isinstance(content, dict):
        raise ValueError("请求缺少 content 对象")
    content["uid"] = uid
    user_auth = payload.get("userAuth")
    if not isinstance(user_auth, dict):
        user_auth = {}
        payload["userAuth"] = user_auth
    user = user_auth.get("user")
    if not isinstance(user, dict):
        user = {}
        user_auth["user"] = user
    user["userId"] = uid
    session = payload.get("session")
    if not isinstance(session, dict):
        session = {}
        payload["session"] = session
    session["sessionId"] = f"batch-{run_token}"
    session["interactionId"] = f"{sample_id}-{attempt:03d}"
    session["isNew"] = attempt == 0
    return payload


def apply_request_overrides(
    source: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """把任务级公共字段覆盖到请求副本，不改变样本源文件。"""

    payload = copy.deepcopy(source)
    content = payload.get("content")
    if not isinstance(content, dict):
        raise ValueError("请求缺少 content 对象")
    device_info = payload.get("deviceInfo")
    if not isinstance(device_info, dict):
        device_info = {}
        payload["deviceInfo"] = device_info
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        pagination = {}
        payload["pagination"] = pagination

    protocol_version = overrides.get("protocolVersion")
    if isinstance(protocol_version, str) and protocol_version:
        payload["version"] = protocol_version
    bundle_name = overrides.get("bundleName")
    if isinstance(bundle_name, str) and bundle_name:
        payload["bundleName"] = bundle_name
        content["bundleName"] = bundle_name
    device_id = overrides.get("deviceId")
    if isinstance(device_id, str) and device_id:
        content["odid"] = device_id
        device_info["deviceId"] = device_id

    device_fields = {
        "phoneType": "phoneType",
        "appVersion": "prdVer",
        "romVersion": "romVersion",
        "locale": "locale",
        "countryCode": "countryCode",
        "deviceFormation": "deviceFormation",
        "deviceType": "deviceType",
        "sysVer": "sysVer",
    }
    for source_name, target_name in device_fields.items():
        value = overrides.get(source_name)
        if value is not None and value != "":
            device_info[target_name] = value

    pagination_limit = overrides.get("paginationLimit")
    if isinstance(pagination_limit, int) and not isinstance(pagination_limit, bool):
        pagination["limit"] = pagination_limit
    pagination_start = overrides.get("paginationStart")
    if isinstance(pagination_start, str):
        pagination["start"] = pagination_start
    return payload


@dataclass
class BatchRunState:
    run_id: str
    run_token: str
    endpoint: str
    concurrency: int
    max_retries: int
    timeout_seconds: float
    samples: list[dict[str, Any]]
    output_dir: Path
    task_id: str = ""
    dataset_id: str = ""
    backend_mode: str = "deployed"
    service_status: str = "external"
    request_overrides: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    workers: list[asyncio.Task[None]] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        total = len(self.samples)
        completed_states = {"success", "degraded", "failed", "unsupported", "cancelled"}
        completed = sum(1 for item in self.samples if item.get("status") in completed_states)
        success = sum(1 for item in self.samples if item.get("status") == "success")
        degraded = sum(1 for item in self.samples if item.get("status") == "degraded")
        failed = sum(1 for item in self.samples if item.get("status") in {"failed", "unsupported"})
        cancelled = sum(1 for item in self.samples if item.get("status") == "cancelled")
        elapsed_values = [
            float(item.get("elapsedMs", 0.0))
            for item in self.samples
            if item.get("status") in completed_states
        ]
        trace_warnings = sum(
            1
            for item in self.samples
            if item.get("traceStatus") in {"missing", "partial", "invalid"}
        )
        return {
            "runId": self.run_id,
            "status": self.status,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "endpoint": self.endpoint,
            "concurrency": self.concurrency,
            "maxRetries": self.max_retries,
            "timeoutSeconds": self.timeout_seconds,
            "taskId": self.task_id,
            "datasetId": self.dataset_id,
            "backendMode": self.backend_mode,
            "serviceStatus": self.service_status,
            "interrupted": self.status == "interrupted",
            "total": total,
            "completed": completed,
            "success": success,
            "degraded": degraded,
            "failed": failed,
            "cancelled": cancelled,
            "averageElapsedMs": (
                round(sum(elapsed_values) / len(elapsed_values), 2) if elapsed_values else 0.0
            ),
            "traceWarnings": trace_warnings,
            "samples": self.samples,
        }


class BatchRunManager:
    """管理内存中的活动批跑，并把可恢复结果写入 batch_output。"""

    def __init__(
        self,
        dataset_root: Path,
        output_root: Path,
        trace_root: Path,
        cloud_root: Path,
        *,
        invoke: InvokeCallable = invoke_generate,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.dataset_root = dataset_root.resolve()
        self.output_root = output_root.resolve()
        self.trace_importer = TraceImporter(trace_root)
        self.cloud_root = cloud_root.resolve()
        self.invoke = invoke
        self.timeout_seconds = timeout_seconds
        self.runs: dict[str, BatchRunState] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self._trace_refresh_lock = RLock()

    def datasets(self) -> list[dict[str, Any]]:
        return [item.public_dict() for item in discover_datasets(self.dataset_root)]

    def start_run(
        self,
        sample_ids: list[str],
        tool_ws_base_url: str,
        concurrency: int,
        max_retries: int,
        *,
        task_id: str = "",
        dataset_id: str = "",
        dataset_root: Path | None = None,
        request_overrides: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        backend_mode: str = "deployed",
        service_status: str = "external",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_dataset_root = (dataset_root or self.dataset_root).resolve()
        available = {item.sample_id: item for item in discover_datasets(resolved_dataset_root)}
        selected: list[DatasetItem] = []
        seen: set[str] = set()
        for sample_id in sample_ids:
            if sample_id in seen:
                continue
            seen.add(sample_id)
            item = available.get(sample_id)
            if item is None or not _SAMPLE_ID_PATTERN.fullmatch(sample_id):
                raise ValueError(f"未知数据样本: {sample_id}")
            if not item.valid:
                raise ValueError(f"数据样本无效: {sample_id}: {item.error}")
            selected.append(item)
        if not selected:
            raise ValueError("至少选择一个有效数据样本")
        endpoint = normalize_endpoint(tool_ws_base_url)
        run_token = uuid.uuid4().hex[:8]
        if run_id is None:
            run_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_token}"
        else:
            run_token = run_id.rsplit("_", maxsplit=1)[-1]
        samples: list[dict[str, Any]] = []
        for sequence, item in enumerate(selected, start=1):
            samples.append(
                {
                    "id": item.sample_id,
                    "fileName": item.file_name,
                    "title": item.title,
                    "query": item.query,
                    "size": item.size,
                    "sequence": sequence,
                    "status": "queued",
                    "attemptCount": 0,
                    "elapsedMs": 0.0,
                    "errorCode": "",
                    "error": "",
                    "artifactAvailable": False,
                    "dslAvailable": False,
                    "traceStatus": "pending",
                    "traceRecordCount": 0,
                    "traceSchemaVersion": "",
                    "traceDurationMs": 0.0,
                }
            )
        state = BatchRunState(
            run_id=run_id,
            run_token=run_token,
            endpoint=endpoint,
            concurrency=concurrency,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds or self.timeout_seconds,
            samples=samples,
            output_dir=self.output_root / run_id,
            task_id=task_id,
            dataset_id=dataset_id,
            backend_mode=backend_mode,
            service_status=service_status,
            request_overrides=dict(request_overrides or {}),
        )
        self.runs[run_id] = state
        self._persist_state(state)
        self._snapshot_evaluation(resolved_dataset_root, state.output_dir)
        self.tasks[run_id] = asyncio.create_task(self._execute_run(state, available))
        return state.public_dict()

    def continue_run(
        self,
        run_id: str,
        tool_ws_base_url: str,
        *,
        dataset_root: Path,
        service_status: str,
        request_overrides: dict[str, Any],
    ) -> dict[str, Any]:
        summary = self._read_run_file(run_id, "summary.json")
        if summary.get("status") not in {"cancelled", "interrupted"}:
            raise ValueError("只有已停止或已中断的任务可以继续执行")
        samples = copy.deepcopy(summary.get("samples"))
        if not isinstance(samples, list):
            raise ValueError("执行记录缺少样本状态")
        max_retries = int(summary.get("maxRetries", 0))
        resumable = 0
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            status = str(sample.get("status") or "")
            attempt_count = int(sample.get("attemptCount") or 0)
            can_resume = status in {"queued", "running", "cancelled"}
            if can_resume and attempt_count <= max_retries:
                sample["status"] = "queued"
                resumable += 1
        if not resumable:
            raise ValueError("没有未执行或中断且仍在重试上限内的样本")
        resolved_dataset_root = dataset_root.resolve()
        available = {item.sample_id: item for item in discover_datasets(resolved_dataset_root)}
        state = BatchRunState(
            run_id=run_id,
            run_token=str(summary.get("runId") or run_id).rsplit("_", maxsplit=1)[-1],
            endpoint=normalize_endpoint(tool_ws_base_url),
            concurrency=int(summary.get("concurrency", 4)),
            max_retries=max_retries,
            timeout_seconds=float(summary.get("timeoutSeconds", self.timeout_seconds)),
            samples=samples,
            output_dir=self.output_root / run_id,
            task_id=str(summary.get("taskId") or ""),
            dataset_id=str(summary.get("datasetId") or ""),
            backend_mode=str(summary.get("backendMode") or "deployed"),
            service_status=service_status,
            request_overrides=dict(request_overrides),
        )
        self.runs[run_id] = state
        self._persist_state(state)
        self.tasks[run_id] = asyncio.create_task(self._execute_run(state, available))
        return state.public_dict()

    async def cancel_run(self, run_id: str) -> dict[str, Any]:
        state = self.runs.get(run_id)
        if state is None:
            raise KeyError(run_id)
        if state.status not in {"queued", "running"}:
            return state.public_dict()
        state.cancel_event.set()
        for worker in state.workers:
            if not worker.done():
                worker.cancel()
        return state.public_dict()

    def list_runs(self) -> list[dict[str, Any]]:
        persisted: dict[str, dict[str, Any]] = {}
        if self.output_root.is_dir():
            for path in self.output_root.glob("*/summary.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(value, dict) and isinstance(value.get("runId"), str):
                    persisted[value["runId"]] = value
        for run_id, state in self.runs.items():
            persisted[run_id] = state.public_dict()
        return sorted(
            persisted.values(),
            key=lambda item: str(item.get("startedAt", "")),
            reverse=True,
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        state = self.runs.get(run_id)
        if state is not None:
            return state.public_dict()
        return self._read_run_file(run_id, "summary.json")

    def get_sample(self, run_id: str, sample_id: str) -> dict[str, Any]:
        if not _SAMPLE_ID_PATTERN.fullmatch(sample_id):
            raise KeyError(sample_id)
        run_dir = self._safe_run_dir(run_id)
        sample_dir = (run_dir / sample_id).resolve()
        try:
            sample_dir.relative_to(run_dir)
        except ValueError as exc:
            raise KeyError(sample_id) from exc
        result = self._read_json(sample_dir / "result.json")
        attempts: list[dict[str, Any]] = []
        trace_metadata_updated = False
        for attempt_dir in sorted(sample_dir.glob("attempt_*")):
            attempt: dict[str, Any] = {"name": attempt_dir.name}
            for name in ("request", "response", "result", "blocks"):
                path = attempt_dir / f"{name}.json"
                if path.is_file():
                    attempt[name] = self._read_json(path)
            trace_view_path = attempt_dir / "trace" / "view.json"
            if trace_view_path.is_file():
                attempt["trace"] = self._read_json(trace_view_path)
            if self._refresh_missing_trace(run_dir, attempt_dir, attempt):
                trace_metadata_updated = True
                final_attempt = result.get("finalAttempt")
                if isinstance(final_attempt, int) and attempt_dir.name == (
                    f"attempt_{final_attempt:03d}"
                ):
                    refreshed_view = attempt.get("trace")
                    if isinstance(refreshed_view, dict):
                        self._apply_trace_view_metadata(refreshed_view, result)
            genui_path = attempt_dir / "genui.jsonl"
            if genui_path.is_file():
                attempt["genui"] = genui_path.read_text(encoding="utf-8")
            attempts.append(attempt)
        if trace_metadata_updated:
            atomic_write_json(sample_dir / "result.json", result)
            self._update_run_trace_metadata(run_id, sample_id, result, run_dir)
        return {"summary": result, "attempts": attempts}

    def _refresh_missing_trace(
        self,
        run_dir: Path,
        attempt_dir: Path,
        attempt: dict[str, Any],
    ) -> bool:
        view = attempt.get("trace")
        attempt_result = attempt.get("result")
        if not isinstance(view, dict) or view.get("status") != "missing":
            return False
        if not isinstance(attempt_result, dict):
            return False
        uid = attempt_result.get("uid")
        if not isinstance(uid, str) or not uid:
            return False
        with self._trace_refresh_lock:
            if not self.trace_importer.is_terminal(uid):
                return False
            refreshed = self.trace_importer.import_trace(
                uid,
                attempt_dir / "trace",
                run_dir / "trace_blobs",
            )
            attempt["trace"] = refreshed
            self._apply_trace_view_metadata(refreshed, attempt_result)
            atomic_write_json(attempt_dir / "result.json", attempt_result)
        return True

    @staticmethod
    def _apply_trace_view_metadata(view: dict[str, Any], target: dict[str, Any]) -> None:
        target["traceStatus"] = view.get("status", "missing")
        target["traceRecordCount"] = view.get("recordCount", 0)
        target["traceSchemaVersion"] = view.get("sourceSchemaVersion", "")
        target["traceDurationMs"] = _trace_duration(view)

    @staticmethod
    def _copy_trace_result_metadata(source: dict[str, Any], target: dict[str, Any]) -> None:
        for name in (
            "traceStatus",
            "traceRecordCount",
            "traceSchemaVersion",
            "traceDurationMs",
        ):
            target[name] = source.get(name)

    def _update_run_trace_metadata(
        self,
        run_id: str,
        sample_id: str,
        result: dict[str, Any],
        run_dir: Path,
    ) -> None:
        state = self.runs.get(run_id)
        if state is not None:
            for sample in state.samples:
                if sample.get("id") == sample_id:
                    self._copy_trace_result_metadata(result, sample)
                    break
            self._persist_state(state)
            return
        for name in ("manifest.json", "summary.json"):
            path = run_dir / name
            if not path.is_file():
                continue
            summary = self._read_json(path)
            samples = summary.get("samples")
            if not isinstance(samples, list):
                continue
            for sample in samples:
                if isinstance(sample, dict) and sample.get("id") == sample_id:
                    self._copy_trace_result_metadata(result, sample)
                    break
            summary["traceWarnings"] = sum(
                1
                for sample in samples
                if isinstance(sample, dict)
                and sample.get("traceStatus") in {"missing", "partial", "invalid"}
            )
            atomic_write_json(path, summary)
            if name == "summary.json":
                (run_dir / "summary.md").write_text(
                    self._summary_markdown(summary),
                    encoding="utf-8",
                )

    def get_trace_artifact(self, run_id: str, digest: str) -> tuple[Path, str]:
        if not _TRACE_DIGEST_PATTERN.fullmatch(digest):
            raise KeyError(digest)
        run_dir = self._safe_run_dir(run_id)
        manifest_path = run_dir / "trace_blob_manifest.json"
        if not manifest_path.is_file():
            raise KeyError("Trace 附件未登记")
        manifest = self._read_json(manifest_path)
        blobs = manifest.get("blobs")
        registration = blobs.get(digest) if isinstance(blobs, dict) else None
        if not isinstance(registration, dict):
            raise KeyError("Trace 附件未登记")
        blob_root = (run_dir / "trace_blobs").resolve()
        artifact_path = (blob_root / digest).resolve()
        if not artifact_path.is_relative_to(run_dir):
            raise KeyError("Trace 附件路径越界")
        if not artifact_path.is_file():
            raise KeyError("Trace 附件文件缺失")
        content = artifact_path.read_bytes()
        if len(content) != registration.get("bytes"):
            raise ValueError("Trace 附件字节数不匹配")
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Trace 附件 SHA-256 不匹配")
        return artifact_path, str(registration.get("mediaType") or "application/octet-stream")

    async def _execute_run(
        self,
        state: BatchRunState,
        available: dict[str, DatasetItem],
    ) -> None:
        state.status = "running"
        self._persist_state(state)
        semaphore = asyncio.Semaphore(state.concurrency)

        async def execute_sample(sample: dict[str, Any]) -> None:
            try:
                async with semaphore:
                    if state.cancel_event.is_set():
                        sample["status"] = "cancelled"
                        return
                    item = available.get(str(sample.get("id")))
                    if item is None:
                        sample["status"] = "failed"
                        sample["error"] = "数据样本不存在"
                        return
                    await self._execute_sample(state, sample, item)
            except asyncio.CancelledError:
                sample["status"] = "cancelled"
            except Exception as exc:
                sample["status"] = "failed"
                sample["error"] = f"{type(exc).__name__}: {exc}"
                self._persist_state(state)

        state.workers = [
            asyncio.create_task(execute_sample(sample))
            for sample in state.samples
            if sample.get("status") == "queued"
        ]
        await asyncio.gather(*state.workers, return_exceptions=True)
        if state.cancel_event.is_set():
            for sample in state.samples:
                if sample.get("status") in {"queued", "running"}:
                    sample["status"] = "cancelled"
            state.status = "cancelled"
        else:
            state.status = "completed"
        state.finished_at = utc_now()
        self._persist_state(state)
        self.tasks.pop(state.run_id, None)

    async def _execute_sample(
        self,
        state: BatchRunState,
        sample: dict[str, Any],
        item: DatasetItem,
    ) -> None:
        sample["status"] = "running"
        source = json.loads(item.path.read_text(encoding="utf-8"))
        total_started = time.perf_counter()
        final_attempt: dict[str, Any] | None = None
        start_attempt = int(sample.get("attemptCount") or 0)
        for attempt in range(start_attempt, state.max_retries + 1):
            if state.cancel_event.is_set():
                sample["status"] = "cancelled"
                break
            uid = f"batch-{state.run_token}-{int(sample.get('sequence', 0)):05d}-{attempt:03d}"
            request = prepare_request(
                source,
                uid=uid,
                run_token=state.run_token,
                sample_id=str(sample.get("id")),
                attempt=attempt,
            )
            request = apply_request_overrides(request, state.request_overrides)
            attempt_dir = state.output_dir / str(sample.get("id")) / f"attempt_{attempt:03d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(attempt_dir / "request.json", request)
            sample["attemptCount"] = attempt + 1
            self._persist_state(state)
            final_attempt = await self._execute_attempt(state, request, uid, attempt_dir, attempt)
            sample["uid"] = uid
            sample["status"] = final_attempt.get("status", "failed")
            sample["errorCode"] = final_attempt.get("errorCode", "")
            sample["error"] = final_attempt.get("error", "")
            sample["artifactAvailable"] = final_attempt.get("artifactAvailable", False)
            sample["dslAvailable"] = final_attempt.get("dslAvailable", False)
            sample["traceStatus"] = final_attempt.get("traceStatus", "missing")
            sample["traceRecordCount"] = final_attempt.get("traceRecordCount", 0)
            sample["traceSchemaVersion"] = final_attempt.get("traceSchemaVersion", "")
            sample["traceDurationMs"] = final_attempt.get("traceDurationMs", 0.0)
            if final_attempt.get("completed"):
                break
            error_code = str(final_attempt.get("errorCode") or "")
            if final_attempt.get("status") == "unsupported":
                break
            if error_code in _DETERMINISTIC_ERROR_CODES:
                break
        sample["elapsedMs"] = round((time.perf_counter() - total_started) * 1000, 2)
        if final_attempt is not None:
            result = {**sample, "finalAttempt": int(sample.get("attemptCount", 1)) - 1}
            atomic_write_json(
                state.output_dir / str(sample.get("id")) / "result.json",
                result,
            )
        self._persist_state(state)

    async def _execute_attempt(
        self,
        state: BatchRunState,
        request: dict[str, Any],
        uid: str,
        attempt_dir: Path,
        attempt: int,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        response: dict[str, Any] = {}
        error = ""
        artifact_available = False
        dsl_available = False
        blocks: dict[str, Any] = {}
        try:
            response = await self.invoke(state.endpoint, request, state.timeout_seconds)
            atomic_write_json(attempt_dir / "response.json", response)
            data = response.get("data")
            artifact_url = data.get("artifactUrl") if isinstance(data, dict) else None
            if response.get("status") in {"success", "degraded"} and artifact_url:
                artifact_text = await asyncio.to_thread(
                    download_artifact,
                    str(artifact_url),
                    attempt_dir / "artifact.md",
                    self._artifact_roots(),
                )
                artifact_available = True
                blocks = parse_artifact_blocks(artifact_text)
                atomic_write_json(attempt_dir / "blocks.json", blocks)
                write_artifact_blocks(attempt_dir, blocks)
                genui = blocks.get("genui")
                if isinstance(genui, str) and genui.strip():
                    (attempt_dir / "genui.jsonl").write_text(genui, encoding="utf-8")
                    dsl_available = True
                else:
                    error = "artifact 缺少有效 genui 代码块"
            elif response.get("status") in {"success", "degraded"}:
                error = "响应未返回 artifactUrl"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        trace = await self._import_trace(uid, attempt_dir, state.output_dir)
        status = str(response.get("status") or "failed")
        completed = status in {"success", "degraded"} and artifact_available and dsl_available
        if status in {"success", "degraded"} and not completed:
            status = "failed"
        result = {
            "attempt": attempt,
            "uid": uid,
            "status": status,
            "errorCode": str(response.get("errorCode") or ""),
            "error": error or _error_text(response.get("error")),
            "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            "artifactAvailable": artifact_available,
            "dslAvailable": dsl_available,
            "blockNames": sorted(blocks),
            "traceStatus": trace.get("status", "missing"),
            "traceRecordCount": trace.get("recordCount", 0),
            "traceSchemaVersion": trace.get("sourceSchemaVersion", ""),
            "traceDurationMs": _trace_duration(trace),
            "completed": completed,
        }
        atomic_write_json(attempt_dir / "result.json", result)
        return result

    async def _import_trace(
        self,
        uid: str,
        attempt_dir: Path,
        run_dir: Path,
    ) -> dict[str, Any]:
        for _ in range(50):
            if await asyncio.to_thread(self.trace_importer.is_terminal, uid):
                break
            await asyncio.sleep(0.1)
        return await asyncio.to_thread(
            self.trace_importer.import_trace,
            uid,
            attempt_dir / "trace",
            run_dir / "trace_blobs",
        )

    def _artifact_roots(self) -> tuple[Path, ...]:
        workspace = self.cloud_root / "workspace"
        return workspace, workspace / "mock_obs", self.cloud_root

    @staticmethod
    def _snapshot_evaluation(dataset_root: Path, output_dir: Path) -> None:
        source = (dataset_root / "evaluation").resolve()
        if not source.is_relative_to(dataset_root.resolve()) or not source.is_dir():
            return
        target = output_dir / "dataset_evaluation"
        shutil.copytree(source, target, dirs_exist_ok=True)
        files: list[dict[str, Any]] = []
        for path in sorted(target.glob("*.json")):
            if path.name == "summary.json":
                continue
            content = path.read_bytes()
            item: dict[str, Any] = {
                "name": path.name,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            try:
                value = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = None
            if isinstance(value, dict):
                item["schemaVersion"] = str(value.get("schemaVersion") or "")
                samples = value.get("samples")
                if isinstance(samples, dict):
                    item["annotatedSamples"] = len(samples)
            files.append(item)
        atomic_write_json(
            target / "summary.json",
            {
                "schemaVersion": "batch-dataset-evaluation-snapshot-v1",
                "files": files,
            },
        )

    def _persist_state(self, state: BatchRunState) -> None:
        summary = state.public_dict()
        atomic_write_json(state.output_dir / "manifest.json", summary)
        atomic_write_json(state.output_dir / "summary.json", summary)
        (state.output_dir / "summary.md").write_text(
            self._summary_markdown(summary),
            encoding="utf-8",
        )

    @staticmethod
    def _summary_markdown(summary: dict[str, Any]) -> str:
        lines = [
            f"# Batch {summary.get('runId', '')}",
            "",
            f"- 状态: {summary.get('status', '')}",
            f"- 开始时间: {summary.get('startedAt', '')}",
            f"- 总数: {summary.get('total', 0)}",
            f"- 成功/降级/失败: {summary.get('success', 0)}/"
            f"{summary.get('degraded', 0)}/{summary.get('failed', 0)}",
            f"- Trace 告警: {summary.get('traceWarnings', 0)}",
            "",
            "| 样本 | 状态 | 尝试 | 耗时(ms) | Trace | 错误码 |",
            "|---|---|---:|---:|---|---|",
        ]
        samples = summary.get("samples")
        if isinstance(samples, list):
            for sample in samples:
                if not isinstance(sample, dict):
                    continue
                lines.append(
                    f"| {sample.get('id', '')} | {sample.get('status', '')} | "
                    f"{sample.get('attemptCount', 0)} | {sample.get('elapsedMs', 0)} | "
                    f"{sample.get('traceStatus', '')} | {sample.get('errorCode', '')} |"
                )
        return "\n".join(lines) + "\n"

    def _safe_run_dir(self, run_id: str) -> Path:
        if not _SAMPLE_ID_PATTERN.fullmatch(run_id):
            raise KeyError(run_id)
        run_dir = (self.output_root / run_id).resolve()
        try:
            run_dir.relative_to(self.output_root)
        except ValueError as exc:
            raise KeyError(run_id) from exc
        if not run_dir.is_dir():
            raise KeyError(run_id)
        return run_dir

    def _read_run_file(self, run_id: str, name: str) -> dict[str, Any]:
        return self._read_json(self._safe_run_dir(run_id) / name)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError(str(path)) from exc
        if not isinstance(value, dict):
            raise KeyError(str(path))
        return value


def _error_text(value: Any) -> str:
    if value in (None, "", {}, []):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _trace_duration(trace: dict[str, Any]) -> float:
    summary = trace.get("summary")
    if not isinstance(summary, dict):
        return 0.0
    value = summary.get("totalDurationMs")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return round(float(value), 2)
