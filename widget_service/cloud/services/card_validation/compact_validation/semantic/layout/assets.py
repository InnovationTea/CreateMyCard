# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""原始高阶组件的 SVG 显式着色约束，不改变转换器自动着色。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.semantic.asset_references import (
    model_asset_references,
    task_asset_candidates,
)
from services.compact_dsl_a2ui_converter import ComponentRow

_NATIVE_COLOR_MARKERS = (
    "不可染色",
    "禁止染色",
    "保留原色",
    "多色",
    "渐变",
    "品牌色",
    "品牌原色",
    "插画原色",
)


def _preserves_native_color(candidate: dict[str, Any]) -> bool:
    description = candidate.get("description")
    if not isinstance(description, str):
        return False
    return any(marker in description for marker in _NATIVE_COLOR_MARKERS)


def _collect_asset_color_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    candidates = task_asset_candidates(task_spec)
    if candidates is None:
        return
    for reference in model_asset_references(components):
        component = reference.component
        if component.component_type not in {"ProgressCircle", "CardButton", "SingleLineTitle"}:
            continue
        if not reference.source.lower().endswith(".svg"):
            continue
        candidate = candidates.get(reference.source)
        if candidate is None or _preserves_native_color(candidate):
            continue
        if "fillColor" in component.props:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_SVG_FILL_COLOR_MISSING",
                validation_class="semantic",
                category="layout",
                message=(
                    f"组件 {component.component_id} 的可染色 SVG 图标未提供显式颜色 fillColor。"
                ),
                expected={"requiredProperty": "fillColor", "colorPolicy": "tintable"},
                actual={"property": "icon", "src": reference.source, "fillColorPresent": False},
                component_id=component.component_id,
                property_path=reference.property_path,
                legacy_message=(
                    f"component {component.component_id}: tintable SVG {reference.source} "
                    "must set fillColor explicitly; omitting it renders the asset's default black."
                ),
            ),
        )
