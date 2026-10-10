from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class ShapeValidator(BaseValidator):
    stage = "quality"
    name = "shape"
    root_radius_values = (18.0, 20.0)

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        root_radius_values = self._root_radius_values(rules)
        radius_labels = [f"{value:g}" for value in root_radius_values]
        radius_label = " 或 ".join(radius_labels)
        min_button_radius = 18.0
        if rules is not None:
            configured_button_radius = numeric(rules.layout.get("minButtonRadius"))
            if configured_button_radius is not None and configured_button_radius >= 0:
                min_button_radius = configured_button_radius
        radii: set[float] = set()
        for index, component in iter_components(context):
            styles = component.get("styles")
            is_root = component.get("id") == context.root_id
            if not isinstance(styles, dict):
                if is_root:
                    add(
                        reporter,
                        "SHAPE.CARD_ROOT_RADIUS",
                        component_pointer(index, "styles/borderRadius"),
                        f"根卡片圆角必须为 {radius_label}vp。",
                        None,
                        list(root_radius_values),
                    )
                continue
            radius = numeric(styles.get("borderRadius"))
            valid_root_radius = radius is not None and radius in root_radius_values
            if is_root and not valid_root_radius:
                add(
                    reporter,
                    "SHAPE.CARD_ROOT_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    f"根卡片圆角必须为 {radius_label}vp。",
                    radius,
                    list(root_radius_values),
                )
            if radius is None:
                continue
            if component.get("component") == "Button" and radius < min_button_radius:
                add(
                    reporter,
                    "SHAPE.BUTTON_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    f"按钮圆角应不小于 {min_button_radius:g}vp。",
                    radius,
                    f">= {min_button_radius:g}",
                )
            if component.get("component") == "Button":
                radii.add(radius)
        if len(radii) > 1:
            add(
                reporter,
                "SHAPE.RADIUS_FAMILY",
                "/updateComponents/components",
                "可点击控件应使用统一圆角体系。",
                sorted(radii),
                "单一圆角档位",
            )

    def _root_radius_values(self, rules: Any) -> tuple[float, ...]:
        root_radius_values = self.root_radius_values
        if rules is not None:
            configured = rules.layout.get("rootBorderRadius")
            values = configured if isinstance(configured, list) else [configured]
            parsed: list[float] = []
            for value in values:
                radius = numeric(value)
                if radius is None or radius < 0:
                    parsed.clear()
                    break
                if radius not in parsed:
                    parsed.append(radius)
            if parsed:
                root_radius_values = tuple(parsed)
        return root_radius_values
