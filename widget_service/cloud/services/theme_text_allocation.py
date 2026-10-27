"""复用定稿组件的展开来源，区分内容宽度和分栏占位；不测量真实卡片尺寸。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from services.compact_component_runtime import VISUAL_RECIPE_VERSION
from services.theme_style_roles import layout_phase

if TYPE_CHECKING:
    from services.compact_dsl_a2ui_converter import ComponentRow

logger = logging.getLogger(__name__)


def content_sized_width_ids(
    nodes: list[dict], data_model: dict | None, final_layout: str | None, size: str | None,
) -> set[str]:
    """仅核验编译器既有输出，不改变前景或推断真实设备中的文字宽度。"""
    if not final_layout or size not in {"2x2", "2x4"} or data_model is None:
        return set()
    from services.compact_dsl_a2ui_converter import (
        ComponentRow,
        expand_high_level_component_rows,
        parse_compact_dsl_rows,
    )

    try:
        with layout_phase(True):
            rows = parse_compact_dsl_rows(final_layout, size=size)
            components = [row for row in rows if isinstance(row, ComponentRow)]
            if not any(row.component_type == "SecondaryBody" for row in components):
                return set()
            expected = expand_high_level_component_rows(
                components, size=size, data_model=data_model,
            )
    except ValueError as exc:
        logger.debug("Cannot confirm content width provenance: %s", exc)
        return set()
    by_id = {node.get("id"): node for node in nodes}
    result = set()
    marker = VISUAL_RECIPE_VERSION + ":SecondaryBody.item"
    for row in expected:
        if row.props.get("_visualRecipe") != marker:
            continue
        width = row.props.get("width")
        if type(width) not in {int, float} or width <= 0:
            continue
        actual = by_id.get(row.component_id)
        if actual is not None and _matches_allocation(actual, row):
            result.add(row.component_id)
    return result


def _matches_allocation(actual: dict, expected: ComponentRow) -> bool:
    if actual.get("component") != expected.component_type:
        return False
    if tuple(actual.get("children", ())) != expected.children:
        return False
    styles = actual.get("styles", {})
    # 明确占位、独立偏移或不同宽度不能借用原组件的来源说明。
    for key in (
        "width", "layoutWeight", "constraintSize", "padding", "margin", "minWidth", "maxWidth",
        "position", "offset", "translate", "alignSelf",
    ):
        if styles.get(key) != expected.props.get(key):
            return False
    return actual.get("itemMargin", 0) == expected.props.get("itemMargin", 0)
