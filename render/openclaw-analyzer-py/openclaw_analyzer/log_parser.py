from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .time_utils import parse_iso_timestamp_ms


@dataclass
class ToolCallInfo:
    id: str = ""
    name: str = ""
    arguments_summary: str = ""
    arguments_full: str = ""


@dataclass
class LogEvent:
    type: str = ""
    id: str = ""
    parent_id: str = ""
    timestamp: str = ""
    timestamp_ms: int = 0
    message_timestamp_ms: int = -1
    custom_type: str = ""
    run_id: str = ""
    role: str = ""
    text_content: str = ""
    thinking_content: str = ""
    model: str = ""
    provider: str = ""
    stop_reason: str = ""
    tool_name: str = ""
    tool_call_id: str = ""
    duration_ms: int = -1
    took_ms: int = -1
    is_error: bool = False
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    details_text: str = ""
    usage_text: str = ""
    hidden_from_ui: bool = False


@dataclass
class ParseStats:
    json_objects: int = 0
    skipped_regions: int = 0
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class SessionInfo:
    session_id: str = ""
    cwd: str = ""
    start_timestamp: str = ""


@dataclass
class ParsedLog:
    session: SessionInfo = field(default_factory=SessionInfo)
    events: list[LogEvent] = field(default_factory=list)
    ordered_events: list[LogEvent] = field(default_factory=list)
    parse_stats: ParseStats = field(default_factory=ParseStats)


def _extract_text_content(content_array: Any) -> str:
    if not isinstance(content_array, list):
        return ""
    parts = [
        item["text"]
        for item in content_array
        if isinstance(item, dict) and item.get("type") == "text" and "text" in item
    ]
    return "\n".join(parts)


def _extract_thinking_content(content_array: Any) -> str:
    if not isinstance(content_array, list):
        return ""
    parts = [
        item["thinking"]
        for item in content_array
        if isinstance(item, dict) and item.get("type") == "thinking" and "thinking" in item
    ]
    return "\n".join(parts)


def _summarize_arguments(args: Any) -> str:
    if not isinstance(args, dict):
        return json.dumps(args, ensure_ascii=False)

    if "path" in args:
        return f"path={args['path']}"
    if "command" in args:
        cmd = str(args["command"])
        return cmd if len(cmd) <= 120 else cmd[:117] + "..."
    if "url" in args:
        return f"url={args['url']}"

    text = json.dumps(args, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "..."


def _format_arguments_full(args: Any) -> str:
    if args is None:
        return ""
    if isinstance(args, dict):
        return json.dumps(args, ensure_ascii=False, indent=2)
    return json.dumps(args, ensure_ascii=False, indent=2)


def _extract_tool_calls(content_array: Any) -> list[ToolCallInfo]:
    if not isinstance(content_array, list):
        return []

    calls: list[ToolCallInfo] = []
    for item in content_array:
        if not isinstance(item, dict) or item.get("type") != "toolCall":
            continue
        args = item.get("arguments")
        calls.append(
            ToolCallInfo(
                id=item.get("id", ""),
                name=item.get("name", ""),
                arguments_summary=_summarize_arguments(args),
                arguments_full=_format_arguments_full(args),
            )
        )
    return calls


def _iter_json_objects(text: str) -> tuple[list[dict[str, Any]], ParseStats]:
    decoder = json.JSONDecoder()
    stats = ParseStats()
    objects: list[dict[str, Any]] = []
    idx = 0
    length = len(text)

    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                objects.append(obj)
                stats.json_objects += 1
            idx = end
        except json.JSONDecodeError as exc:
            next_start = text.find('{"type":', idx + 1)
            if next_start == -1:
                stats.skipped_regions += 1
                stats.parse_errors.append(f"offset {idx}: {exc.msg}")
                break
            stats.skipped_regions += 1
            stats.parse_errors.append(f"offset {idx}: recovered at {next_start} ({exc.msg})")
            idx = next_start

    return objects, stats


def _parse_custom_message(data: dict[str, Any], event: LogEvent) -> LogEvent:
    event.custom_type = data.get("customType", "")
    event.text_content = data.get("content", "") if isinstance(data.get("content"), str) else ""
    event.hidden_from_ui = bool(data.get("display") is False)
    details = data.get("details") or {}
    if isinstance(details, dict):
        event.details_text = json.dumps(details, ensure_ascii=False, indent=2)
    return event


def _parse_json_line(data: dict[str, Any]) -> LogEvent:
    event = LogEvent(
        type=data.get("type", ""),
        id=data.get("id", ""),
        parent_id=data.get("parentId", ""),
        timestamp=data.get("timestamp", ""),
    )

    if event.timestamp:
        event.timestamp_ms = parse_iso_timestamp_ms(event.timestamp)

    if event.type == "custom":
        event.custom_type = data.get("customType", "")
        payload = data.get("data") or {}
        if isinstance(payload, dict):
            event.run_id = payload.get("runId", "")
            if isinstance(payload.get("timestamp"), int):
                event.timestamp_ms = payload["timestamp"]
            event.model = payload.get("modelId", "")
            event.provider = payload.get("provider", "")
        return event

    if event.type == "model_change":
        event.model = data.get("modelId", "")
        event.provider = data.get("provider", "")
        return event

    if event.type == "custom_message":
        return _parse_custom_message(data, event)

    if event.type != "message" or "message" not in data:
        return event

    msg = data["message"]
    event.role = msg.get("role", "")
    event.model = msg.get("model", "")
    event.provider = msg.get("provider", "")
    event.stop_reason = msg.get("stopReason", "")

    if isinstance(msg.get("timestamp"), int):
        event.message_timestamp_ms = int(msg["timestamp"])

    if "content" in msg:
        event.text_content = _extract_text_content(msg["content"])
        event.thinking_content = _extract_thinking_content(msg["content"])
        event.tool_calls = _extract_tool_calls(msg["content"])

    usage = msg.get("usage")
    if isinstance(usage, dict):
        event.usage_text = json.dumps(usage, ensure_ascii=False, indent=2)

    if event.role == "toolResult":
        event.tool_name = msg.get("toolName", "")
        event.tool_call_id = msg.get("toolCallId", "")
        event.is_error = bool(msg.get("isError", False))
        details = msg.get("details") or {}
        if isinstance(details, dict):
            if isinstance(details.get("durationMs"), (int, float)):
                event.duration_ms = int(details["durationMs"])
            if isinstance(details.get("tookMs"), (int, float)):
                event.took_ms = int(details["tookMs"])
            aggregated = details.get("aggregated")
            if isinstance(aggregated, str) and aggregated.strip():
                event.details_text = aggregated
            else:
                event.details_text = json.dumps(details, ensure_ascii=False, indent=2)

    return event


def _parse_log_objects(json_objects: list[dict[str, Any]], stats: ParseStats) -> ParsedLog:
    result = ParsedLog(parse_stats=stats)
    seen_ids: set[str] = set()

    for data in json_objects:
        if data.get("type") == "session":
            result.session = SessionInfo(
                session_id=data.get("id", ""),
                cwd=data.get("cwd", ""),
                start_timestamp=data.get("timestamp", ""),
            )
            continue

        event = _parse_json_line(data)
        if not event.id or event.id in seen_ids:
            continue
        seen_ids.add(event.id)
        result.events.append(event)

    result.ordered_events = list(result.events)
    return result


def parse_log_text(raw_text: str) -> ParsedLog:
    json_objects, stats = _iter_json_objects(raw_text)
    return _parse_log_objects(json_objects, stats)


def parse_log_file(path: str | Path) -> ParsedLog:
    log_path = Path(path)
    if not log_path.is_file():
        raise FileNotFoundError(f"cannot open log file: {log_path}")

    raw_text = log_path.read_text(encoding="utf-8")
    json_objects, stats = _iter_json_objects(raw_text)
    return _parse_log_objects(json_objects, stats)
