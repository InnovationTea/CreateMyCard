# -*- coding: utf-8 -*-
"""Minimal text/background contrast validation for the quality stage."""

from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator

_HEX_COLOR = re.compile(r"^#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_TEMPLATE_ROOT_ID = "template_root"


def _rgba(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, str):
        raise ValueError("color value must be a hex string")
    match = _HEX_COLOR.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid hex color: {value!r}")
    raw = match.group("hex")
    if len(raw) == 6:
        alpha = 1.0
        red, green, blue = (int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4))
        return (red, green, blue, alpha)
    # DSL uses ARGB for eight-digit colors.
    alpha = int(raw[:2], 16) / 255
    red, green, blue = (int(raw[index:index + 2], 16) / 255 for index in (2, 4, 6))
    return (red, green, blue, alpha)


def _composite(
    background: tuple[float, float, float],
    foreground: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    red, green, blue = background
    top_red, top_green, top_blue, alpha = foreground
    return (
        top_red * alpha + red * (1 - alpha),
        top_green * alpha + green * (1 - alpha),
        top_blue * alpha + blue * (1 - alpha),
    )


def _luminance(rgb: tuple[float, float, float]) -> float:
    def linear(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(foreground: Any, background: tuple[float, float, float]) -> float:
    parsed = _rgba(foreground)
    foreground_rgb = _composite(background, parsed)
    first = _luminance(foreground_rgb)
    second = _luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


class ContrastValidator(BaseValidator):
    """Check readable text against its effective ancestor backgrounds."""

    stage = "quality"
    name = "contrast"

    def validate(self, context, rules, reporter) -> None:
        del rules
        if not context.components or not context.root_id:
            return
        by_id = context.components_by_id
        root = by_id.get(context.root_id)
        if not isinstance(root, dict):
            return
        self._walk(context, reporter, root, [(1.0, 1.0, 1.0)])

    def _walk(self, context, reporter, component, backgrounds) -> None:
        # 模板内容沿用模板配色，不追加对比度诊断；其它校验仍由各自的 validator 执行。
        if component.get("id") == _TEMPLATE_ROOT_ID:
            return
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        effective_backgrounds = list(backgrounds)
        try:
            background = _rgba(styles.get("backgroundColor"))
            effective_backgrounds = [_composite(effective_backgrounds[-1], background)]
        except ValueError:
            pass
        gradient = styles.get("linearGradient") or styles.get("radialGradient")
        if isinstance(gradient, dict) and isinstance(gradient.get("colors"), list):
            for stop in gradient["colors"]:
                raw = stop[0] if isinstance(stop, (list, tuple)) and stop else stop
                try:
                    color = _rgba(raw)
                    effective_backgrounds.append(_composite(effective_backgrounds[-1], color))
                except ValueError:
                    continue

        if component.get("component") == "Text" and self._has_text(component.get("content")):
            color_key = "fontColor" if "fontColor" in styles else "textColor"
            foreground = styles.get(color_key)
            ratios = []
            for item in effective_backgrounds:
                try:
                    ratios.append(_contrast(foreground, item))
                except ValueError:
                    continue
            if ratios:
                ratio = min(ratios)
                if ratio < 4.5:
                    severity = "error" if ratio < 3 else "warning"
                    component_id = component.get("id")
                    pointer = (
                        f"/updateComponents/componentsById/{component_id}/styles/{color_key}"
                    )
                    reporter.add(
                        severity,
                        "VISUAL.CONTRAST",
                        self.stage,
                        "genui",
                        line=2,
                        json_pointer=pointer,
                        actual=round(ratio, 2),
                        expected=">= 3:1; >= 4.5:1 recommended",
                        message=f"text contrast is {ratio:.2f}:1",
                        fix_hint="Use a stronger foreground color or adjust the background.",
                        source="aesthetic-contrast",
                    )

        children = component.get("children")
        child_ids = children if isinstance(children, list) else []
        for child_id in child_ids:
            child = context.components_by_id.get(child_id)
            if isinstance(child, dict):
                self._walk(context, reporter, child, effective_backgrounds)

    @staticmethod
    def _has_text(value: Any) -> bool:
        return isinstance(value, str) and value.strip() and not value.strip().startswith("{{")
