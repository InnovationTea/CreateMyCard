# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.assets。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.compact_dsl_a2ui_converter import ComponentRow

_PRESERVE_ORIGINAL_COLOR_MARKERS = (
    "不可染色",
    "禁止染色",
    "保留原色",
    "多色",
    "渐变",
    "品牌色",
    "插画原色",
)


def _collect_asset_color_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """Require explicit tinting for SVG assets whose source color is not protected."""
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return

    descriptions: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("src")
        if not isinstance(source, str):
            continue
        description = candidate.get("description")
        descriptions[source] = description if isinstance(description, str) else ""

    for component in components:
        source: Any = None
        if component.component_type == "Image":
            source = component.props.get("src")
        elif component.component_type == "CardHeader":
            source = component.props.get("icon")
        if not isinstance(source, str) or not source.casefold().endswith(".svg"):
            continue
        description = descriptions.get(source)
        if description is None:
            continue
        preserve_original = any(
            marker in description for marker in _PRESERVE_ORIGINAL_COLOR_MARKERS
        )
        if preserve_original or "fillColor" in component.props:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_SVG_FILL_COLOR_MISSING",
                validation_class="semantic",
                category="layout",
                message=f"组件 {component.component_id} 的可染色 SVG 缺少显式 fillColor。",
                expected={"explicitFillColor": True},
                actual={"src": source, "fillColor": component.props.get("fillColor")},
                component_id=component.component_id,
                property_path="/fillColor",
                legacy_message=f"component {component.component_id}: "
                f"tintable SVG {source} must set "
                "fillColor explicitly; omitting it renders the asset's default black.",
            ),
        )
