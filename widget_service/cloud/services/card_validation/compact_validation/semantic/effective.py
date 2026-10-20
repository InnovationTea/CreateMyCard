# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：semantic.effective。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.card_validation.compact_validation.semantic.asset_references import (
    model_asset_references,
    task_asset_candidates,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)
from services.event_matching import event_handlers_match


def _collect_asset_source_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
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
        for key in ("backgroundImage",):
            value = component.props.get(key)
            if not isinstance(value, str) or value.strip().startswith("{{"):
                continue
            _collect_asset_reference_error(component, key, "/" + key, value, sources, errors)


def _collect_model_asset_source_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    """只检查展开前的模型素材字段，背景仍由原有检查按原顺序处理。"""
    candidates = task_asset_candidates(task_spec)
    if candidates is None:
        return
    sources = set(candidates)
    for reference in model_asset_references(components):
        _collect_asset_reference_error(
            reference.component,
            reference.property_label,
            reference.property_path,
            reference.source,
            sources,
            errors,
        )


def _collect_asset_reference_error(
    component: ComponentRow,
    key: str,
    property_path: str,
    value: str,
    sources: set[str],
    errors: list[str],
) -> None:
    if value in sources:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_ASSET_NOT_ALLOWED",
            validation_class="semantic",
            category="effective",
            message=f"组件 {component.component_id} 的 {key} 引用了本轮候选范围以外的素材。",
            expected={"allowedSources": sorted(sources)},
            actual={"property": key, "src": value},
            component_id=component.component_id,
            property_path=property_path,
            legacy_message=(
                f"component {component.component_id}.props.{key}: asset must "
                f"use an original src from TaskSpec.assetCandidates."
            ),
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


def _event_handler_from_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
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


def _collect_event_candidate_error(
    component: ComponentRow,
    handler: dict[str, Any],
    allowed_handlers: list[dict[str, Any]],
    errors: list[str],
) -> None:
    location = f"component {component.component_id}.props.onClick"
    if not any(event_handlers_match(handler, candidate) for candidate in allowed_handlers):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_EVENT_NOT_ALLOWED",
                validation_class="semantic",
                category="effective",
                message=f"组件 {component.component_id} 的点击 handler 不匹配本轮事件候选。",
                expected={"allowedHandlers": allowed_handlers},
                actual=handler,
                component_id=component.component_id,
                property_path="/onClick/0",
                legacy_message=(
                    f"{location}[0]: handler must exactly match a TaskSpec eventCandidate."
                ),
            ),
        )
