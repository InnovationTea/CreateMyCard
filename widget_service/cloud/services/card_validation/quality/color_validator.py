from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import (
    ALPHA_STEPS,
    add,
    all_colors,
    alpha,
    component_pointer,
    iter_components,
    static_color,
)


class ColorValidator(BaseValidator):
    stage = "quality"
    name = "color"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        configured_steps = rules.style.get("allowedAlphaSteps") if rules is not None else None
        allowed_steps = ALPHA_STEPS
        if isinstance(configured_steps, list):
            parsed_steps = {
                int(step)
                for step in configured_steps
                if isinstance(step, int) and not isinstance(step, bool) and 0 <= step <= 255
            }
            if parsed_steps:
                allowed_steps = frozenset(parsed_steps)
        for index, component in iter_components(context):
            for key, raw in all_colors(component):
                color = static_color(raw)
                is_dynamic = isinstance(raw, str) and raw.strip().startswith(
                    ("{{", "${", "$theme(")
                )
                if color is None and not is_dynamic:
                    add(
                        reporter,
                        "COLOR.INVALID_FORMAT",
                        component_pointer(index, f"styles/{key}"),
                        "颜色必须使用 #AARRGGBB 格式。",
                        raw,
                        "#AARRGGBB",
                    )
                    continue
                if color is not None and alpha(color) not in allowed_steps:
                    add(
                        reporter,
                        "COLOR.ALPHA_STEP",
                        component_pointer(index, f"styles/{key}"),
                        "颜色透明度不在登记档位中。",
                        raw,
                        sorted(allowed_steps),
                    )
            styles = component.get("styles")
            opacity = numeric(styles.get("opacity")) if isinstance(styles, dict) else None
            if opacity is not None and 0 <= opacity < 1:
                add(
                    reporter,
                    "COLOR.OPACITY_MISUSE",
                    component_pointer(index, "styles/opacity"),
                    "不应使用 opacity 绕过颜色透明度规范。",
                    opacity,
                    "将透明度编码在颜色 alpha 中。",
                )
