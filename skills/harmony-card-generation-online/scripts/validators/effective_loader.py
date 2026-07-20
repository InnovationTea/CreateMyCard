"""Effective capability resolution.

Only used in dynamic effective mode. Resolves effective data / event / asset
capabilities from three sources, with priority (higher wins):

1. Inline dict/str entries in ``effectiveCapabilities``.
2. ``artifact.taskSpec.assetCandidates`` for asset id → src.
3. ``capabilities_dir/{data,asset}_capabilities.json`` from the cloud-new
   capability registry.

Populates the fields on ``ValidationContext`` that BindingValidator /
EffectiveCapabilityValidator read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def attach_effective_capabilities(
    context,
    effective: dict[str, Any],
    artifact: dict[str, Any],
    capabilities_dir: Path | None,
) -> None:
    if not effective:
        return
    normalized = {
        "data": _as_list(effective.get("data")),
        "event": _as_list(effective.get("event")),
        "asset": _as_list(effective.get("asset")),
    }
    context.use_effective_capabilities = True
    context.effective_capabilities = normalized
    context.effective_data_capabilities = _resolve_effective_data_capabilities(
        normalized["data"],
        capabilities_dir,
    )
    asset_sources, unresolved = _resolve_effective_asset_sources(
        normalized["asset"],
        artifact,
        capabilities_dir,
    )
    context.effective_asset_sources = asset_sources
    context.unresolved_effective_asset_ids = unresolved


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve_effective_data_capabilities(
    items: list[Any],
    capabilities_dir: Path | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            capability_id = item.get("id") or item.get("capabilityId")
            if isinstance(capability_id, str):
                result[capability_id] = item
    if capabilities_dir is None:
        return result
    data_map = _load_capability_map(capabilities_dir / "data_capabilities.json")
    for item in items:
        capability_id = ""
        if isinstance(item, str):
            capability_id = item
        elif isinstance(item, dict):
            raw_id = item.get("id") or item.get("capabilityId")
            capability_id = raw_id if isinstance(raw_id, str) else ""
        if capability_id and capability_id in data_map:
            result[capability_id] = data_map[capability_id]
    return result


def _resolve_effective_asset_sources(
    items: list[Any],
    artifact: dict[str, Any],
    capabilities_dir: Path | None,
) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    sources: set[str] = set()
    resolved_ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("capabilityId")
            src = item.get("src")
            if isinstance(src, str):
                sources.add(src)
            if isinstance(item_id, str):
                if isinstance(src, str):
                    resolved_ids.add(item_id)
                else:
                    ids.add(item_id)
        elif isinstance(item, str):
            if item.startswith("resources/"):
                sources.add(item)
            else:
                ids.add(item)

    source_by_id: dict[str, str] = {}
    for item in _task_asset_candidates(artifact):
        item_id = item.get("id")
        src = item.get("src")
        if isinstance(item_id, str) and isinstance(src, str):
            source_by_id[item_id] = src

    if capabilities_dir is not None:
        source_by_id.update(_load_asset_capability_map(capabilities_dir))

    for item_id in ids:
        src = source_by_id.get(item_id)
        if src:
            sources.add(src)
            resolved_ids.add(item_id)

    return sources, ids - resolved_ids


def _task_asset_candidates(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    task_spec = artifact.get("taskSpec")
    if not isinstance(task_spec, dict):
        return []
    candidates = task_spec.get("assetCandidates")
    return (
        [item for item in candidates if isinstance(item, dict)]
        if isinstance(candidates, list)
        else []
    )


def _load_asset_capability_map(capabilities_dir: Path) -> dict[str, str]:
    data = _load_capability_list(capabilities_dir / "asset_capabilities.json")
    result: dict[str, str] = {}
    for item in data:
        item_id = item.get("id")
        src = item.get("src")
        if isinstance(item_id, str) and isinstance(src, str):
            result[item_id] = src
    return result


def _load_capability_map(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _load_capability_list(path):
        item_id = item.get("id")
        if isinstance(item_id, str):
            result[item_id] = item
    return result


def _load_capability_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
