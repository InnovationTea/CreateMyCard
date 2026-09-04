# -*- coding: utf-8 -*-
"""Minimal text/background contrast validation for the quality stage."""

from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator

_HEX_COLOR = re.compile(r"^#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_OPAQUE_ALPHA = 1.0

RgbColor = tuple[float, float, float]
RgbaColor = tuple[float, float, float, float]


def _rgba(value: Any) -> RgbaColor | None:
    if not isinstance(value, str):
        return None
    match = _HEX_COLOR.fullmatch(value.strip())
    if match is None:
        return None
    raw = match.group("hex")
    if len(raw) == 6:
        alpha = 1.0
        red, green, blue = (int(raw[index : index + 2], 16) / 255 for index in (0, 2, 4))
        return red, green, blue, alpha
    # DSL uses ARGB for eight-digit colors.
    alpha = int(raw[:2], 16) / 255
    red, green, blue = (int(raw[index : index + 2], 16) / 255 for index in (2, 4, 6))
    return red, green, blue, alpha


def _composite(
    background: RgbColor,
    foreground: RgbaColor,
) -> RgbColor:
    red, green, blue = background
    top_red, top_green, top_blue, alpha = foreground
    return (
        top_red * alpha + red * (1 - alpha),
        top_green * alpha + green * (1 - alpha),
        top_blue * alpha + blue * (1 - alpha),
    )


def _luminance(rgb: RgbColor) -> float:
    def linear(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(foreground: Any, background: RgbColor) -> float | None:
    parsed = _rgba(foreground)
    if parsed is None:
        return None
    foreground_rgb = _composite(background, parsed)
    first = _luminance(foreground_rgb)
    second = _luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _interpolate_color(left: RgbaColor, right: RgbaColor) -> RgbaColor:
    return (
        (left[0] + right[0]) / 2,
        (left[1] + right[1]) / 2,
        (left[2] + right[2]) / 2,
        (left[3] + right[3]) / 2,
    )


def _gradient_color_samples(gradient: Any) -> list[RgbaColor]:
    if not isinstance(gradient, dict):
        return []
    stops = gradient.get("colors")
    if not isinstance(stops, list):
        return []

    colors: list[RgbaColor] = []
    for stop in stops:
        raw = stop[0] if isinstance(stop, (list, tuple)) and stop else stop
        color = _rgba(raw)
        if color is not None:
            colors.append(color)

    samples: list[RgbaColor] = []
    for index, color in enumerate(colors):
        samples.append(color)
        if index + 1 < len(colors):
            samples.append(_interpolate_color(color, colors[index + 1]))
    return samples


def _composite_candidates(
    backgrounds: list[RgbColor],
    foregrounds: list[RgbaColor],
) -> list[RgbColor]:
    candidates: list[RgbColor] = []
    for background in backgrounds:
        for foreground in foregrounds:
            candidate = _composite(background, foreground)
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _reported_contrast_ratio(ratios: list[float], is_gradient: bool) -> float:
    ordered = sorted(ratios)
    if is_gradient and len(ordered) >= 3:
        # 容忍渐变边缘的一个孤立最差样本；多个低对比样本仍会触发诊断。
        return ordered[1]
    return ordered[0]


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
        self._walk(
            context,
            reporter,
            root,
            [(1.0, 1.0, 1.0)],
            is_gradient=False,
        )

    def _walk(
        self,
        context: Any,
        reporter: Any,
        component: dict[str, Any],
        backgrounds: list[RgbColor],
        *,
        is_gradient: bool,
    ) -> None:
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        effective_backgrounds = list(backgrounds)
        background = _rgba(styles.get("backgroundColor"))
        if background is not None:
            effective_backgrounds = _composite_candidates(
                effective_backgrounds,
                [background],
            )
            if background[3] >= _OPAQUE_ALPHA:
                is_gradient = False
        gradient = styles.get("linearGradient") or styles.get("radialGradient")
        gradient_samples = _gradient_color_samples(gradient)
        if gradient_samples:
            effective_backgrounds = _composite_candidates(
                effective_backgrounds,
                gradient_samples,
            )
            is_gradient = True

        if component.get("component") == "Text" and self._has_text(component.get("content")):
            color_key = "fontColor" if "fontColor" in styles else "textColor"
            foreground = styles.get(color_key)
            ratios: list[float] = []
            for item in effective_backgrounds:
                contrast_ratio = _contrast(foreground, item)
                if contrast_ratio is not None:
                    ratios.append(contrast_ratio)
            if ratios:
                ratio = _reported_contrast_ratio(ratios, is_gradient)
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
                self._walk(
                    context,
                    reporter,
                    child,
                    effective_backgrounds,
                    is_gradient=is_gradient,
                )

    @staticmethod
    def _has_text(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return bool(value)
        return value is not None
