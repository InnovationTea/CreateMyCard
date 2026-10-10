# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""按原顺序编排 S4 与倒计时的展示语义和布局检查。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import (
    _descendant_components,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_countdown_duplicate_unit,
    _collect_s4_action_hint,
)
from services.card_validation.compact_validation.semantic.layout.two_by_two import (
    _collect_2x2_countdown_layout,
    _collect_s4_calendar_typography,
    _collect_s4_text_budget,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_two_s4_text_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue
        text_components = []
        for descendant in _descendant_components(zone, components_by_id):
            if descendant.component_type == "Text":
                text_components.append(descendant)

        _collect_s4_text_budget(zone, text_components, errors)
        _collect_s4_action_hint(zone, text_components, errors)
        _collect_s4_calendar_typography(zone, text_components, errors)


def _collect_2x2_countdown_group_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    visible_binding_paths: list[str],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    has_countdown = any(path.endswith("/countdownDays") for path in visible_binding_paths)
    if not has_countdown:
        return

    _collect_countdown_duplicate_unit(components, errors)
    _collect_2x2_countdown_layout(
        components, components_by_id, visible_binding_paths, task_spec, errors
    )
