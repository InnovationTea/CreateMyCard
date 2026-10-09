from __future__ import annotations

from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components, static_color


class GradientValidator(BaseValidator):
    stage = "quality"
    name = "gradient"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            for key in ("linearGradient", "radialGradient"):
                gradient = styles.get(key)
                if gradient is None:
                    continue
                if not isinstance(gradient, dict):
                    add(
                        reporter,
                        "GRADIENT.UNREGISTERED",
                        component_pointer(index, f"styles/{key}"),
                        "渐变必须是包含方向和颜色 stops 的对象。",
                        gradient,
                    )
                    continue
                if not self._has_position(key, gradient):
                    expected = (
                        "direction 或 0~360 的 angle" if key == "linearGradient" else "center"
                    )
                    add(
                        reporter,
                        "GRADIENT.UNREGISTERED",
                        component_pointer(index, f"styles/{key}"),
                        f"{key} 必须声明 {expected}。",
                        gradient,
                        expected,
                    )
                colors = gradient.get("colors")
                if not isinstance(colors, list) or len(colors) < 2:
                    add(
                        reporter,
                        "GRADIENT.UNREGISTERED",
                        component_pointer(index, f"styles/{key}/colors"),
                        "渐变必须包含至少两个颜色 stops。",
                        colors,
                        ">= 2 stops",
                    )
                    continue
                previous_offset: float | None = None
                for stop_index, stop in enumerate(colors):
                    raw = stop[0] if isinstance(stop, (list, tuple)) and stop else None
                    offset = stop[1] if isinstance(stop, (list, tuple)) and len(stop) > 1 else None
                    valid_offset = self._valid_offset(offset)
                    ordered_offset = (
                        valid_offset
                        and previous_offset is not None
                        and float(offset) <= previous_offset
                    )
                    valid_stop = static_color(raw) is not None and valid_offset
                    if not valid_stop or ordered_offset:
                        add(
                            reporter,
                            "GRADIENT.UNREGISTERED",
                            component_pointer(index, f"styles/{key}/colors/{stop_index}"),
                            "渐变 stop 必须包含合法颜色和 0~1 offset。",
                            stop,
                        )
                    if valid_offset:
                        previous_offset = float(offset)
                self._check_coverage(index, key, colors, reporter)

    @staticmethod
    def _has_position(key: str, gradient: dict[str, Any]) -> bool:
        if key == "radialGradient":
            return bool(gradient.get("center"))
        angle = gradient.get("angle")
        if isinstance(angle, bool) or not isinstance(angle, (int, float)):
            return False
        return 0 <= angle <= 360

    @staticmethod
    def _valid_offset(offset: Any) -> bool:
        if isinstance(offset, bool) or not isinstance(offset, (int, float)):
            return False
        return 0 <= offset <= 1

    @classmethod
    def _check_coverage(
        cls,
        component_index: int,
        key: str,
        colors: list[Any],
        reporter: Any,
    ) -> None:
        first = colors[0]
        last = colors[-1]
        first_offset = first[1] if isinstance(first, (list, tuple)) and len(first) > 1 else None
        last_offset = last[1] if isinstance(last, (list, tuple)) and len(last) > 1 else None
        if cls._valid_offset(first_offset) and cls._valid_offset(last_offset):
            if float(first_offset) == 0.0 and float(last_offset) == 1.0:
                return
        add(
            reporter,
            "GRADIENT.UNREGISTERED",
            component_pointer(component_index, f"styles/{key}/colors"),
            "渐变 stops 应覆盖完整的 0~1 区间。",
            [first_offset, last_offset],
            [0, 1],
        )
