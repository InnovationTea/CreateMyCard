from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class TypographyValidator(BaseValidator):
    stage = "quality"
    name = "typography"
    allowed = frozenset({10, 12, 14, 16, 18, 20, 32, 40})
    allowed_weights = frozenset(range(100, 1000, 100))

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        configured_sizes = rules.layout.get("allowedFontSizes") if rules is not None else None
        configured_weights = rules.layout.get("allowedFontWeights") if rules is not None else None
        allowed_sizes = self.allowed
        allowed_weights = self.allowed_weights
        if isinstance(configured_sizes, list):
            parsed_sizes = {
                float(size)
                for size in configured_sizes
                if isinstance(size, (int, float)) and not isinstance(size, bool)
            }
            if parsed_sizes:
                allowed_sizes = frozenset(parsed_sizes)
        if isinstance(configured_weights, list):
            parsed_weights = {
                float(weight)
                for weight in configured_weights
                if isinstance(weight, (int, float)) and not isinstance(weight, bool)
            }
            if parsed_weights:
                allowed_weights = frozenset(parsed_weights)
        for index, component in iter_components(context):
            if component.get("component") not in {"Text", "Button"}:
                continue
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            self._check_sizes(index, styles, allowed_sizes, reporter)
            weight = numeric(styles.get("fontWeight"))
            if weight is not None and weight not in allowed_weights:
                add(
                    reporter,
                    "TYPE.WEIGHT_MATRIX",
                    component_pointer(index, "styles/fontWeight"),
                    "字重不在允许范围内。",
                    weight,
                    sorted(allowed_weights),
                )

    @staticmethod
    def _check_sizes(
        index: int,
        styles: dict[str, Any],
        allowed_sizes: frozenset[float],
        reporter: Any,
    ) -> None:
        for field in ("fontSize", "minFontSize", "maxFontSize"):
            size = numeric(styles.get(field))
            if size is not None and size not in allowed_sizes:
                add(
                    reporter,
                    "TYPE.FONT_SIZE_STEP",
                    component_pointer(index, f"styles/{field}"),
                    "字号不在登记的字体档位中。",
                    size,
                    sorted(allowed_sizes),
                )
        has_min = "minFontSize" in styles
        has_max = "maxFontSize" in styles
        min_size = numeric(styles.get("minFontSize"))
        max_size = numeric(styles.get("maxFontSize"))
        invalid_pair = has_min != has_max
        invalid_order = min_size is not None and max_size is not None and min_size > max_size
        if invalid_pair or invalid_order:
            add(
                reporter,
                "TYPE.FONT_SIZE_STEP",
                component_pointer(index, "styles"),
                "minFontSize 与 maxFontSize 必须成对声明且范围有效。",
                {
                    "minFontSize": styles.get("minFontSize"),
                    "maxFontSize": styles.get("maxFontSize"),
                },
                "minFontSize <= maxFontSize，且两者同时存在",
            )
