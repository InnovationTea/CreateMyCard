from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric, spacing_tuple
from .common import (
    FUSION_BACKGROUND_ID,
    FUSION_CONTENT_ID_PREFIX,
    add,
    component_pointer,
    iter_components,
)


class SpacingValidator(BaseValidator):
    stage = "quality"
    name = "spacing"
    allowed = frozenset({0, 2, 4, 6, 8, 10, 12, 14, 16})

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        configured_spacing = rules.layout.get("allowedSpacing") if rules is not None else None
        allowed = self.allowed
        if isinstance(configured_spacing, list):
            values: set[float] = set()
            for value in configured_spacing:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                values.add(float(value))
            if values:
                allowed = frozenset(values)
        default_padding = 12
        if rules is not None:
            configured_padding = numeric(rules.layout.get("defaultPadding"))
            if configured_padding is not None:
                default_padding = configured_padding
        safe_root_id = self._safe_root_id(context)
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                if component.get("id") == safe_root_id:
                    add(
                        reporter,
                        "SPACING.SAFE_MARGIN",
                        component_pointer(index, "styles/padding"),
                        f"根容器安全边距应为 {default_padding:g}vp。",
                        None,
                        default_padding,
                    )
                continue
            padding = styles.get("padding")
            if component.get("id") == safe_root_id and not self._matches_padding(
                padding,
                default_padding,
            ):
                add(
                    reporter,
                    "SPACING.SAFE_MARGIN",
                    component_pointer(index, "styles/padding"),
                    f"根容器安全边距应为 {default_padding:g}vp。",
                    padding,
                    default_padding,
                )
            self._check_spacing_value(
                reporter,
                component_pointer(index, "styles/padding"),
                padding,
                allowed,
            )
            self._check_spacing_value(
                reporter,
                component_pointer(index, "styles/margin"),
                styles.get("margin"),
                allowed,
            )
            gap_field = "space" if component.get("component") == "List" else "itemMargin"
            self._check_spacing_value(
                reporter,
                component_pointer(index, gap_field),
                component.get(gap_field),
                allowed,
            )

    @staticmethod
    def _safe_root_id(context: Any) -> str | None:
        safe_root_id: str | None = context.root_id
        root = context.components_by_id.get(safe_root_id)
        if not isinstance(root, dict) or root.get("component") != "Stack":
            return safe_root_id
        children = root.get("children")
        if not isinstance(children, list) or "root_0" in children:
            return safe_root_id
        foreground_ids = [child for child in children if child != FUSION_BACKGROUND_ID]
        if len(foreground_ids) != 1:
            return safe_root_id
        foreground_id = foreground_ids[0]
        if not isinstance(foreground_id, str):
            return safe_root_id
        foreground = context.components_by_id.get(foreground_id)
        if not isinstance(foreground, dict):
            return safe_root_id
        if foreground.get("component") not in {"Row", "Column", "Stack"}:
            return safe_root_id
        is_fusion = FUSION_BACKGROUND_ID in children
        is_template = SpacingValidator._is_template_foreground(foreground, context)
        if is_fusion or is_template:
            safe_root_id = foreground_id
        return safe_root_id

    @staticmethod
    def _is_template_foreground(foreground: dict[str, Any], context: Any) -> bool:
        if foreground.get("id") != "template_root" or foreground.get("component") != "Stack":
            return False
        children = foreground.get("children")
        if not isinstance(children, list) or len(children) != 1:
            return False
        content_id = children[0]
        if not isinstance(content_id, str) or not content_id.startswith(FUSION_CONTENT_ID_PREFIX):
            return False
        content = context.components_by_id.get(content_id)
        return isinstance(content, dict) and content.get("component") in {"Row", "Column", "Stack"}

    @staticmethod
    def _matches_padding(value: Any, expected: float) -> bool:
        if value is None:
            return False
        return spacing_tuple(value) == (expected, expected, expected, expected)

    @staticmethod
    def _check_spacing_value(
        reporter: Any,
        pointer: str,
        value: Any,
        allowed: frozenset[float],
    ) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            values = [numeric(item) for item in value.values()]
            if not values:
                values = [None]
        else:
            values = [numeric(value)]
        invalid = any(item is None or item not in allowed for item in values)
        if invalid:
            add(
                reporter,
                "SPACING.SCALE",
                pointer,
                "间距不在登记档位中。",
                value,
                sorted(allowed),
            )
