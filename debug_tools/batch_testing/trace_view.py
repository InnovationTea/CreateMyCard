"""将语义 Span 与所属事件转换为独立于微服务的阶段视图。"""

import math
import re
from typing import Any

from .trace_semantics import content_label, operation_title

_ID = re.compile(r"^[a-f0-9]{16}$")
_EVENT_ID = re.compile(r"^[a-f0-9]{32}$")


def build_semantic_view(uid, records, manifest, normalize_artifacts, warnings):
    spans: dict[str, dict[str, Any]] = {}
    sequences: set[int] = set()
    event_ids: set[str] = set()
    for index, record in enumerate(records, 1):
        sequence = record.get("sequence")
        valid = all(
            (
                record.get("schemaVersion") == "generation-trace-v2",
                record.get("traceId") == manifest.get("traceId"),
                _ID.fullmatch(str(record.get("spanId") or "")) is not None,
                isinstance(sequence, int) and not isinstance(sequence, bool),
                isinstance(sequence, int) and sequence > 0 and sequence not in sequences,
                _nonnegative(record.get("startOffsetMs")),
                isinstance(record.get("timestamp"), str),
            )
        )
        if isinstance(sequence, int):
            sequences.add(sequence)
        if record.get("recordType") == "span":
            valid = valid and all(
                (
                    record.get("spanId") not in spans,
                    _nonnegative(record.get("durationMs")),
                    record.get("kind") in {"group", "step", "model"},
                    isinstance(record.get("operation"), str),
                    bool(record.get("status")),
                )
            )
            spans[str(record.get("spanId"))] = record
        elif record.get("recordType") == "event":
            event_id = str(record.get("eventId") or "")
            valid = valid and bool(_EVENT_ID.fullmatch(event_id)) and event_id not in event_ids
            event_ids.add(event_id)
        else:
            valid = False
        if not valid:
            warnings.append(f"trace.jsonl:{index}: 语义记录结构不合法")
    if manifest.get("uid") != uid or not _EVENT_ID.fullmatch(str(manifest.get("traceId") or "")):
        warnings.append("manifest UID 或 Trace ID 不合法")
    state = manifest.get("state")
    if state not in {"recording", "complete", "partial"}:
        warnings.append("manifest 状态不合法")
    if state != "recording" and manifest.get("recordCount") != len(records):
        warnings.append("manifest recordCount 与记录数不一致")
    root = spans.get(manifest.get("rootSpanId"))
    if state != "recording" and not root:
        warnings.append("终态缺少请求根 Span")
    if root and (root.get("operation") != "request" or root.get("parentSpanId")):
        warnings.append("请求根 Span 不合法")
    if state == "complete" and not isinstance(manifest.get("summary"), dict):
        warnings.append("complete manifest 缺少 summary")
    for record in records:
        if record.get("recordType") == "event":
            if record.get("spanId") not in spans:
                warnings.append("事件所属 Span 不存在")
            continue
        parent_id = record.get("parentSpanId")
        if parent_id and parent_id not in spans:
            warnings.append("父 Span 不存在")
        seen: set[str] = set()
        current = record
        while current:
            identifier = str(current.get("spanId"))
            if identifier in seen:
                warnings.append("父子 Span 关系存在环")
                break
            seen.add(identifier)
            current = spans.get(current.get("parentSpanId"))
    invalid = bool(warnings)
    nodes: list[dict[str, Any]] = []
    node_map: dict[str, dict[str, Any]] = {}
    for span_id, record in spans.items():
        operation = str(record.get("operation") or "other")
        attempts = _object(record.get("attempts"))
        details = _object(record.get("details"))
        node = {
            "id": span_id,
            "parentId": record.get("parentSpanId"),
            "operation": operation,
            "title": operation_title(operation, attempts),
            "kind": record.get("kind", "step"),
            "name": record.get("event"),
            "description": str(details.get("message") or details.get("reason") or ""),
            "category": record.get("category", "other"),
            "stage": record.get("stage", ""),
            "status": record.get("status", ""),
            "recordType": "span",
            "startOffsetMs": record.get("startOffsetMs", 0.0),
            "durationMs": record.get("durationMs", 0.0),
            "attempts": attempts,
            "attributes": details,
            "metrics": _object(record.get("metrics")),
            "artifacts": [],
            "events": [],
            "raw": record,
        }
        node["artifacts"] = _owned_refs(normalize_artifacts(record.get("artifacts")), span_id)
        nodes.append(node)
        node_map[span_id] = node
    for record in records:
        if record.get("recordType") != "event":
            continue
        node = node_map.get(record.get("spanId"))
        if node is None:
            continue
        events = node.get("events")
        artifacts = node.get("artifacts")
        metrics = node.get("metrics")
        if not isinstance(events, list) or not isinstance(artifacts, list):
            raise ValueError("节点缺少内容列表")
        events.append(record)
        artifacts.extend(
            _owned_refs(
                normalize_artifacts(record.get("artifacts")),
                str(node.get("id")),
            )
        )
        if isinstance(metrics, dict):
            metrics.update(_object(record.get("metrics")))
    for node in nodes:
        if node.get("kind") != "group":
            continue
        own_refs = node.get("artifacts")
        aggregated: list[dict[str, Any]] = list(own_refs) if isinstance(own_refs, list) else []
        for child in nodes:
            if _descendant(child, str(node.get("id")), node_map):
                refs = child.get("artifacts")
                if isinstance(refs, list):
                    aggregated.extend(refs)
        node["contentIndex"] = aggregated
    summary = _object(manifest.get("summary"))
    if root:
        summary["status"] = root.get("status")
    model_nodes = [node for node in nodes if node.get("kind") == "model"]
    tokens = 0
    first_token = None
    for node in model_nodes:
        metrics = _object(node.get("metrics"))
        for key in ("inputTokens", "completionTokens"):
            value = metrics.get(key)
            if isinstance(value, int):
                tokens += value
        if first_token is None:
            first_token = metrics.get("firstTokenLatencyMs")
    summary.update(
        {
            "modelPhysicalCalls": len(model_nodes),
            "totalTokens": tokens,
            "firstTokenMs": first_token,
        }
    )
    retries = _object(summary.get("retryCounts"))
    summary["retryCount"] = sum(value for value in retries.values() if isinstance(value, int))
    status = "complete" if state == "complete" else "partial"
    if invalid:
        status = "invalid"
    elif warnings:
        status = "partial"
    return {
        "viewVersion": "trace-view-v2",
        "instrumentationVersion": 2,
        "uid": uid,
        "traceId": manifest.get("traceId"),
        "sourceSchemaVersion": "generation-trace-v2",
        "status": status,
        "timingMode": "exact",
        "recordCount": len(records),
        "summary": summary,
        "nodes": nodes,
        "warnings": warnings,
    }


def _owned_refs(refs, span_id):
    for ref in refs:
        name = str(ref.get("name"))
        ref.update(
            {
                "id": f"{span_id}:{name}:{ref.get('sha256')}",
                "ownerNodeId": span_id,
                "label": content_label(name),
            }
        )
    return refs


def _descendant(node, ancestor, node_map):
    seen: set[str] = set()
    current = node
    while current:
        identifier = str(current.get("id"))
        if identifier in seen:
            return False
        seen.add(identifier)
        if identifier == ancestor:
            return True
        current = node_map.get(current.get("parentId"))
    return False


def _object(value):
    return dict(value) if isinstance(value, dict) else {}


def _nonnegative(value):
    valid_type = isinstance(value, (int, float)) and not isinstance(value, bool)
    return valid_type and math.isfinite(value) and value >= 0
