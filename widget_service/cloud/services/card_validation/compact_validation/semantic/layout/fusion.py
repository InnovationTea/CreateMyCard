# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.fusion。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import (
    _has_ancestor_component_type,
    component_graph,
    component_index,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.text import _is_status_or_ambiguous_text
from services.compact_dsl_a2ui_converter import ComponentRow

_FUSION_DESIGN_PREFIX = "fusion-ball-"


def _collect_fusion_composition_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    if task_spec.get("size") != "2x2":
        return
    components_by_id = component_index(components)
    root = components_by_id.get("root")
    design = root.props.get("design") if root is not None else None
    if not isinstance(design, str) or not design.startswith(_FUSION_DESIGN_PREFIX):
        return
    parent_by_child = component_graph(components).last_parent_ids
    ring_count = sum(
        component.component_type == "Progress" and component.props.get("type") == "ring"
        for component in components
    )
    action_count = sum(
        component.component_type in {"Button", "ActionUnit"} for component in components
    )
    image_count = sum(
        component.component_type == "Image"
        and not _has_ancestor_component_type(
            component.component_id, parent_by_child, components_by_id, "Progress"
        )
        for component in components
    )
    status_count = sum(
        _is_status_or_ambiguous_text(component, task_spec)
        for component in components
        if component.component_type == "Text"
    )
    has_competing_visuals = image_count >= 1 and ring_count >= 1
    if has_competing_visuals and action_count >= 1 and status_count >= 2:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_FUSION_FOCUS_COMPOSITION",
                validation_class="semantic",
                category="layout",
                message="融球卡片同时叠加了过多视觉与动作元素。",
                expected={
                    "primaryVisualFocusCount": 1,
                    "forbiddenCombination": ["标题或辅助图标", "环形进度", "多个状态文本", "按钮"],
                },
                legacy_message=(
                    "2x2 fusion-ball cards must not combine a title/auxiliary icon, a ring "
                    "Progress, multiple status texts, and a button. Keep one primary visual "
                    "focus: remove the icon or ring, merge status text, or fall back to a "
                    "non-fusion layout."
                ),
            ),
        )
