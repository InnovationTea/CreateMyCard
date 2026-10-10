# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.effective。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_event_candidate_error(
    component: ComponentRow,
    handler: dict[str, Any],
    allowed_handlers: list[dict[str, Any]],
    errors: list[str],
) -> None:
    location = f"component {component.component_id}.props.onClick"
    if handler not in allowed_handlers:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_EVENT_NOT_ALLOWED",
                validation_class="semantic",
                category="effective",
                message=f"组件 {component.component_id} 的点击 handler 不匹配本轮事件候选。",
                expected={"allowedHandlers": allowed_handlers, "exactMatch": True},
                actual=handler,
                component_id=component.component_id,
                property_path="/onClick/0",
                legacy_message=(
                    f"{location}[0]: handler must exactly match a TaskSpec eventCandidate."
                ),
            ),
        )


def _collect_asset_source_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """转换前只接受模型输入中的原始静态素材路径，不提前放行交付 URL。"""
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return
    sources: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        src = candidate.get("src")
        if isinstance(src, str):
            sources.add(src)
    for component in components:
        keys = ["backgroundImage"]
        if component.component_type == "Image":
            keys.append("src")
        elif component.component_type in {"ActionUnit", "CardHeader"}:
            keys.append("icon")
        for key in keys:
            value = component.props.get(key)
            if not isinstance(value, str) or value.strip().startswith("{{"):
                continue
            if value not in sources:
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_ASSET_NOT_ALLOWED",
                        validation_class="semantic",
                        category="effective",
                        message=(
                            f"组件 {component.component_id} 的 {key} 引用了本轮候选范围以外的素材。"
                        ),
                        expected={"allowedSources": sorted(sources)},
                        actual={"property": key, "src": value},
                        component_id=component.component_id,
                        property_path="/" + key,
                        legacy_message=f"component {component.component_id}.props.{key}: "
                        "asset must use an original src from TaskSpec.assetCandidates.",
                    ),
                )


def _task_event_handlers(task_spec: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return []
    handlers: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        handler = _event_handler_from_candidate(candidate)
        if handler is not None:
            handlers.append(handler)
    return handlers


def _event_handler_from_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    source = candidate
    call = source.get("call")
    args = source.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        nested_action = candidate.get("action")
        if not isinstance(nested_action, dict):
            return None
        source = nested_action
        call = source.get("call")
        args = source.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return {"call": call, "args": args}
