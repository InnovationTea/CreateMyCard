"""Normalization for validate_card inputs.

Handles all the "dsl/cardspec/artifact/effective 可能是 dict 也可能是 str，
artifact 可能包一层 artifact 键，effective 可能包一层 effectiveCapabilities 键"
的兼容层，让 api.py 只关心已归一化的字符串/字典。
"""

from __future__ import annotations

import json
from typing import Any


def parse_jsonish(value: dict[str, Any] | str | None) -> dict[str, Any]:
    """Best-effort parse dict-or-JSON-string into a dict."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def unwrap_artifact(value: dict[str, Any]) -> dict[str, Any]:
    """Peel an outer ``{"artifact": {...}}`` wrapper if present."""
    nested = value.get("artifact")
    if isinstance(nested, dict) and not value.get("genui"):
        return nested
    return value


def effective_from_inputs(
    effective_capabilities: dict[str, Any] | str | None,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Resolve the effectiveCapabilities dict from explicit input or artifact."""
    explicit = parse_jsonish(effective_capabilities)
    if "effectiveCapabilities" in explicit and isinstance(explicit["effectiveCapabilities"], dict):
        return explicit["effectiveCapabilities"]
    if explicit:
        return explicit
    artifact_effective = artifact.get("effectiveCapabilities")
    return artifact_effective if isinstance(artifact_effective, dict) else {}


def artifact_dsl(artifact: dict[str, Any]) -> str:
    value = artifact.get("genui")
    return value if isinstance(value, str) else ""


def cardspec_text(cardspec: dict[str, Any] | str | None) -> str:
    if isinstance(cardspec, dict):
        return json.dumps(cardspec, ensure_ascii=False)
    if isinstance(cardspec, str):
        return cardspec
    return ""


def artifact_cardspec_text(artifact: dict[str, Any]) -> str:
    value = artifact.get("cardSpec")
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return value
    return ""
