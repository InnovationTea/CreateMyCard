"""按 UID 导入并归一化微服务生成轨迹。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path
from threading import RLock
from typing import Any

from .trace_view import build_semantic_view

_UID_PATTERN = re.compile(
    r"^(?P<task_type>[A-Za-z]+)-(?P<identifier>[A-Za-z0-9]{8})-"
    r"(?P<request_sequence>\d{5})-(?P<retry_count>\d{3})$"
)
_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRACE_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[a-f0-9]{16}$")
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
_VIEW_VERSION = "trace-view-v2"
_BLOB_LOCK = RLock()


class TraceImporter:
    """读取、校验并可选导入一个请求 UID 对应的 Trace。"""

    def __init__(self, trace_root: Path) -> None:
        self.trace_root = trace_root.resolve()

    def directory_for_uid(self, uid: str) -> Path | None:
        match = _UID_PATTERN.fullmatch(uid)
        if match is None:
            return None
        return self.trace_root.joinpath(
            match.group("task_type"),
            match.group("identifier"),
            match.group("request_sequence"),
            match.group("retry_count"),
        )

    def is_terminal(self, uid: str) -> bool:
        trace_directory = self.directory_for_uid(uid)
        if trace_directory is None or not trace_directory.is_dir():
            return False
        manifest = _read_json_object(trace_directory / "manifest.json")
        return bool(
            manifest is not None
            and manifest.get("schemaVersion") == "generation-trace-v2"
            and manifest.get("state") in {"complete", "partial"}
        )

    def read(self, uid: str) -> dict[str, Any]:
        return self._build_view(uid, None)

    def import_trace(
        self,
        uid: str,
        destination: Path,
        blob_root: Path,
    ) -> dict[str, Any]:
        view = self._build_view(uid, blob_root)
        destination.mkdir(parents=True, exist_ok=True)
        warnings = view.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
            view["warnings"] = warnings
        warning_count = len(warnings)
        trace_directory = self.directory_for_uid(uid)
        if trace_directory is not None and trace_directory.is_dir():
            self._copy_source_files(trace_directory, destination, warnings)
        if len(warnings) > warning_count and view.get("status") == "complete":
            view["status"] = "partial"
        import_manifest = {
            "viewVersion": _VIEW_VERSION,
            "uid": uid,
            "sourceSchemaVersion": view.get("sourceSchemaVersion", ""),
            "status": view.get("status", "invalid"),
            "recordCount": view.get("recordCount", 0),
            "warnings": warnings,
        }
        try:
            _atomic_write_json(destination / "import_manifest.json", import_manifest)
            _atomic_write_json(destination / "view.json", view)
        except (OSError, TypeError, ValueError) as exc:
            warnings.append(f"Trace 导入结果保存失败（{type(exc).__name__}）")
            if view.get("status") == "complete":
                view["status"] = "partial"
        return view

    def _build_view(
        self,
        uid: str,
        blob_root: Path | None,
    ) -> dict[str, Any]:
        trace_directory = self.directory_for_uid(uid)
        if trace_directory is None:
            return _empty_view(uid, "invalid", ["UID 格式不合法"])
        if not trace_directory.is_dir():
            return _empty_view(uid, "missing", ["未找到对应 Trace 目录"])

        manifest = _read_json_object(trace_directory / "manifest.json")
        trace_path = trace_directory / "trace.jsonl"
        warnings: list[str] = []
        if manifest is None or manifest.get("schemaVersion") != "generation-trace-v2":
            return _empty_view(uid, "invalid", ["Trace v2 manifest 缺失或版本不匹配"])
        if not trace_path.is_file():
            return _empty_view(uid, "invalid", ["Trace v2 缺少 trace.jsonl"])
        records = _read_jsonl(trace_path, warnings)
        if manifest.get("instrumentationVersion") == 2:
            return build_semantic_view(
                uid,
                records,
                manifest,
                lambda value: self._normalize_artifacts(
                    value,
                    trace_directory,
                    blob_root,
                    warnings,
                ),
                warnings,
            )
        return {
            **_empty_view(uid, "partial", ["旧埋点仅提供原始查看；请重新批跑取得阶段视图"]),
            "rawOnly": True,
            "rawRecords": records,
            "sourceManifest": manifest,
            "sourceSchemaVersion": "generation-trace-v2",
            "recordCount": len(records),
        }

    def _normalize_artifacts(
        self,
        value: Any,
        trace_directory: Path,
        blob_root: Path | None,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if not isinstance(value, dict):
            return []
        artifacts: list[dict[str, Any]] = []
        for name, raw_ref in value.items():
            if not isinstance(raw_ref, dict):
                warnings.append(f"附件 {name} 引用不是对象")
                continue
            path_value = raw_ref.get("path")
            digest = str(raw_ref.get("sha256") or "").casefold()
            role = str(raw_ref.get("role") or _artifact_role(str(name)))
            if role not in _ARTIFACT_ROLES:
                role = "snapshot"
            media_type = str(raw_ref.get("mediaType") or _media_type(path_value))
            available = False
            error = ""
            if not isinstance(path_value, str) or not path_value:
                error = "附件路径缺失"
            elif not _DIGEST_PATTERN.fullmatch(digest):
                error = "附件摘要格式非法"
            else:
                available, error = _import_artifact(
                    trace_directory,
                    path_value,
                    digest,
                    _integer(raw_ref.get("bytes"), -1),
                    blob_root,
                )
            if error:
                warnings.append(f"附件 {name}: {error}")
            artifacts.append(
                {
                    "id": digest or f"missing-{len(artifacts) + 1}",
                    "name": str(name),
                    "role": role,
                    "mediaType": media_type,
                    "bytes": _integer(raw_ref.get("bytes"), 0),
                    "sha256": digest,
                    "available": available,
                    "error": error,
                }
            )
        return artifacts

    @staticmethod
    def _copy_source_files(
        trace_directory: Path,
        destination: Path,
        warnings: list[str],
    ) -> None:
        source_dir = destination / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        for name in ("manifest.json", "trace.jsonl"):
            source = trace_directory / name
            if not source.is_file():
                continue
            try:
                shutil.copy2(source, source_dir / name)
            except OSError as exc:
                warnings.append(f"{name}: 原始文件复制失败（{type(exc).__name__}）")


def _read_jsonl(path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"{path.name}: 读取失败（{type(exc).__name__}）")
        return records
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("JSONL 根节点必须是对象")
            records.append(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            warnings.append(f"{path.name}:{line_number}: 解析失败（{type(exc).__name__}: {exc}）")
    return records


def _has_parent_cycle(records: list[dict[str, Any]]) -> bool:
    parent_by_span: dict[str, str] = {}
    for record in records:
        span_id = record.get("spanId")
        parent_span_id = record.get("parentSpanId")
        if isinstance(span_id, str) and isinstance(parent_span_id, str):
            parent_by_span[span_id] = parent_span_id
    for span_id in parent_by_span:
        current = span_id
        path: set[str] = set()
        while current in parent_by_span:
            if current in path:
                return True
            path.add(current)
            current = parent_by_span[current]
    return False


def _import_artifact(
    trace_directory: Path,
    relative_path: str,
    expected_digest: str,
    expected_bytes: int,
    blob_root: Path | None,
) -> tuple[bool, str]:
    source = (trace_directory / relative_path).resolve()
    try:
        source.relative_to(trace_directory.resolve())
    except ValueError:
        return False, "附件路径越界"
    if not source.is_file():
        return False, "附件文件不存在"
    try:
        content = source.read_bytes()
    except OSError as exc:
        return False, f"附件读取失败（{type(exc).__name__}）"
    actual_digest = hashlib.sha256(content).hexdigest()
    if expected_bytes < 0 or len(content) != expected_bytes:
        return False, "附件字节数不匹配"
    if actual_digest != expected_digest:
        return False, "附件 SHA-256 不匹配"
    if blob_root is not None:
        temporary: Path | None = None
        try:
            with _BLOB_LOCK:
                blob_root.mkdir(parents=True, exist_ok=True)
                target = blob_root / actual_digest
                if target.is_file() and target.read_bytes() != content:
                    return False, "运行级附件文件已损坏"
                if not target.is_file():
                    temporary = blob_root / f".{actual_digest}.{uuid.uuid4().hex}.tmp"
                    temporary.write_bytes(content)
                    temporary.replace(target)
                manifest_path = blob_root.parent / "trace_blob_manifest.json"
                manifest = _read_json_object(manifest_path) or {"version": 1, "blobs": {}}
                blobs = manifest.get("blobs")
                if not isinstance(blobs, dict):
                    return False, "运行级附件登记表损坏"
                blobs[actual_digest] = {
                    "bytes": expected_bytes,
                    "mediaType": _media_type(relative_path),
                }
                _atomic_write_json(manifest_path, manifest)
        except OSError as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            return False, f"附件导入失败（{type(exc).__name__}）"
    return True, ""


def _trace_summary(summary: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(summary)
    total_duration = _number_or_none(result.get("totalDurationMs"))
    if total_duration is None:
        total_duration = max(
            (
                float(node.get("startOffsetMs") or 0.0) + float(node.get("durationMs") or 0.0)
                for node in nodes
            ),
            default=0.0,
        )
    input_tokens = 0
    completion_tokens = 0
    first_token_latency: float | None = None
    failed_nodes = 0
    for node in nodes:
        if node.get("status") in {"failed", "error", "timeout", "invalid"}:
            failed_nodes += 1
        merged_metrics: dict[str, Any] = {}
        attributes = node.get("attributes")
        metrics = node.get("metrics")
        if isinstance(attributes, dict):
            merged_metrics.update(attributes)
        if isinstance(metrics, dict):
            merged_metrics.update(metrics)
        input_tokens += _integer(merged_metrics.get("inputTokens"), 0)
        completion_tokens += _integer(merged_metrics.get("completionTokens"), 0)
        latency = _number_or_none(merged_metrics.get("firstTokenLatencyMs"))
        if latency is not None and first_token_latency is None:
            first_token_latency = latency
    attempt_counts = result.get("attemptCounts")
    retry_counts = result.get("retryCounts")
    result.update(
        {
            "totalDurationMs": round(total_duration, 2),
            "nodeCount": len(nodes),
            "failedNodeCount": failed_nodes,
            "inputTokens": input_tokens,
            "completionTokens": completion_tokens,
            "firstTokenLatencyMs": first_token_latency,
            "modelPhysicalCalls": (
                _integer(attempt_counts.get("modelPhysicalAttempts"), 0)
                if isinstance(attempt_counts, dict)
                else 0
            ),
            "totalTokens": input_tokens + completion_tokens,
            "firstTokenMs": first_token_latency,
            "retryCount": (
                sum(_integer(value, 0) for value in retry_counts.values())
                if isinstance(retry_counts, dict)
                else 0
            ),
        }
    )
    return result


def _event_category(event: str) -> str:
    lowered = event.casefold()
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
        if any(keyword in lowered for keyword in keywords):
            return category
    return "other"


def _artifact_role(name: str) -> str:
    lowered = name.casefold()
    if "error" in lowered or "warning" in lowered or "validation" in lowered:
        return "diagnostic"
    if "prompt" in lowered or "request" in lowered or "source" in lowered:
        return "input"
    if "result" in lowered or "output" in lowered or "final" in lowered:
        return "output"
    return "snapshot"


def _media_type(path_value: Any) -> str:
    if isinstance(path_value, str) and path_value.casefold().endswith(".json"):
        return "application/json"
    return "text/plain"


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _integer(value: Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def _empty_view(uid: str, status: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "viewVersion": _VIEW_VERSION,
        "uid": uid,
        "traceId": "",
        "sourceSchemaVersion": "",
        "status": status,
        "timingMode": "exact",
        "recordCount": 0,
        "summary": _trace_summary({}, []),
        "nodes": [],
        "warnings": warnings,
    }
