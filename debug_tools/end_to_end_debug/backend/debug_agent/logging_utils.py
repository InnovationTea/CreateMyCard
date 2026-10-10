from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

_SENSITIVE = re.compile(
    r"(access[_-]?key|api[_-]?key|authorization|secret|signature|token|password)", re.I
)
_ANSI_RESET = "\033[0m"
_ANSI_COLORS = {
    "blue": "\033[1;94m",
    "cyan": "\033[1;96m",
    "green": "\033[1;92m",
    "yellow": "\033[1;93m",
    "red": "\033[1;91m",
    "magenta": "\033[1;95m",
}
_PAIRED_EVENTS = {
    "run_started": (">>>>", "blue"),
    "run_completed": ("<<<<", "blue"),
    "load_skill_started": (">>>>", "cyan"),
    "load_skill_completed": ("<<<<", "cyan"),
    "invoke_started": (">>>>", "yellow"),
    "invoke_completed": ("<<<<", "yellow"),
}


@dataclass(frozen=True)
class _EventVisual:
    marker: str
    closing_marker: str
    color: str
    level: int


def configure_debug_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("debug_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    formatter = logging.Formatter("%(message)s")
    for handler in logger.handlers:
        handler.setFormatter(formatter)
    logger.propagate = False
    return logger


def _event_visual(name: str, fields: dict[str, Any]) -> _EventVisual:
    normalized_name = name.lower()
    paired = _PAIRED_EVENTS.get(normalized_name)
    if paired is not None:
        marker, color = paired
        return _EventVisual(marker, marker, color, logging.INFO)
    status = str(fields.get("status") or "").lower()
    is_failure = status in {"failed", "error", "final_error"}
    is_failure = is_failure or any(token in normalized_name for token in ("failed", "error"))
    if is_failure:
        return _EventVisual("[ERR]", "", "red", logging.ERROR)
    is_warning = status in {"cancelled", "canceled", "degraded", "warning"}
    is_warning = is_warning or any(
        token in normalized_name for token in ("cancelled", "canceled", "warning")
    )
    if is_warning:
        return _EventVisual("[WARN]", "", "yellow", logging.WARNING)
    is_success = status in {"success", "completed"}
    is_success = is_success or normalized_name.endswith(("_completed", "_initialized"))
    if is_success:
        return _EventVisual("[OK]", "", "green", logging.INFO)
    is_started = status in {"started", "running"} or normalized_name.endswith("_started")
    if is_started:
        return _EventVisual("[RUN]", "", "cyan", logging.INFO)
    return _EventVisual("[INFO]", "", "magenta", logging.INFO)


def _supports_color(logger: logging.Logger) -> bool:
    if os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    for handler in logger.handlers:
        stream = getattr(handler, "stream", None)
        is_terminal = getattr(stream, "isatty", None)
        if callable(is_terminal) and is_terminal():
            return True
    return False


def _event_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(value).strip())
    return normalized[:80] or "event"


def _header_metadata(fields: dict[str, Any]) -> str:
    values: list[str] = []
    component = fields.get("component")
    status = fields.get("status")
    duration = fields.get("duration_ms")
    if isinstance(component, str) and component:
        values.append(component)
    if isinstance(status, str) and status:
        values.append(status)
    if isinstance(duration, int | float) and not isinstance(duration, bool):
        values.append(f"{duration:g} ms")
    return f"  [{' | '.join(values)}]" if values else ""


def _render_event(
    name: str,
    payload: dict[str, Any],
    raw_fields: dict[str, Any],
    *,
    color: bool,
) -> tuple[str, int]:
    visual = _event_visual(name, raw_fields)
    event_name = _event_name(name)
    header_parts = [visual.marker, event_name]
    if visual.closing_marker:
        header_parts.append(visual.closing_marker)
    header = f"{'  '.join(header_parts)}{_header_metadata(raw_fields)}"
    if color:
        header = f"{_ANSI_COLORS[visual.color]}{header}{_ANSI_RESET}"
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{header}\n      {body}", visual.level


def safe_value(value: Any, *, trace: bool = False, limit: int = 160) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[str(key)] = (
                "<redacted>"
                if _SENSITIVE.search(str(key))
                else safe_value(item, trace=trace, limit=limit)
            )
        return result
    if isinstance(value, list):
        return [safe_value(v, trace=trace, limit=limit) for v in value[:20]]
    if _SENSITIVE.search(str(value)):
        return "<redacted>"
    if isinstance(value, str):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        if trace:
            return {"text": value[:limit], "chars": len(value), "sha256_12": digest}
        if len(value) <= limit:
            return value
        return {"chars": len(value), "sha256_12": digest}
    return value


class DebugLogger:
    def __init__(self, *, skill: str = "", trace: bool = False, limit: int = 160) -> None:
        self.logger = configure_debug_logging("DEBUG" if trace else "INFO")
        self.skill = skill
        self.trace = trace
        self.limit = limit
        self.color = _supports_color(self.logger)

    def event(self, name: str, **fields: Any) -> None:
        payload = {"skill": self.skill}
        for key, value in fields.items():
            payload[key] = safe_value(value, trace=self.trace, limit=self.limit)
        message, level = _render_event(name, payload, fields, color=self.color)
        self.logger.log(level, message)

    def timed(self, name: str, **fields: Any) -> tuple[float, str, dict[str, Any]]:
        return time.perf_counter(), name, fields

    def finish(self, started: tuple[float, str, dict[str, Any]], **fields: Any) -> None:
        started_at, name, initial = started
        self.event(
            name,
            **initial,
            **fields,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

