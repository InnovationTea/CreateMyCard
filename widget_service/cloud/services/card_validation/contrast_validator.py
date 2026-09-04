# -*- coding: utf-8 -*-
"""Minimal text/background contrast validation for the quality stage."""

from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator

_HEX_COLOR = re.compile(r"^#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_TEMPLATE_ROOT_ID = "template_root"
_NORMAL_ROOT_ID = "root_0"
_FUSION_BACKGROUND_ID = "fusionBallBackground"
_OPAQUE_ALPHA = 1.0

RgbColor = tuple[float, float, float]
RgbaColor = tuple[float, float, float, float]


def _rgba(value: Any) -> RgbaColor:
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


def _contrast(foreground: Any, background: RgbColor) -> float:
    parsed = _rgba(foreground)
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
        try:
            colors.append(_rgba(raw))
        except ValueError:
            continue

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
        root_children = root.get("children")
        root_child_ids = root_children if isinstance(root_children, list) else []
        is_fusion_scene = _FUSION_BACKGROUND_ID in root_child_ids
        is_normal_scene = _NORMAL_ROOT_ID in root_child_ids
        self._walk(
            context,
            reporter,
            root,
            [(1.0, 1.0, 1.0)],
            is_gradient=False,
            is_fusion_scene=is_fusion_scene and not is_normal_scene,
        )

    def _walk(
        self,
        context: Any,
        reporter: Any,
        component: dict[str, Any],
        backgrounds: list[RgbColor],
        *,
        is_gradient: bool,
        is_fusion_scene: bool,
    ) -> None:
        # 模板内容沿用模板配色，不追加对比度诊断；其它校验仍由各自的 validator 执行。
        if component.get("id") == _TEMPLATE_ROOT_ID:
            return
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        effective_backgrounds = list(backgrounds)
        try:
            background = _rgba(styles.get("backgroundColor"))
            effective_backgrounds = _composite_candidates(
                effective_backgrounds,
                [background],
            )
            if background[3] >= _OPAQUE_ALPHA:
                is_gradient = False
        except ValueError:
            pass
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
            if is_fusion_scene:
                component_id = component.get("id")
                pointer = (
                    f"/updateComponents/componentsById/{component_id}/styles/{color_key}"
                )
                reporter.add(
                    "warning",
                    "VISUAL.CONTRAST",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual={"scene": "fusionBall", "requiresRenderReview": True},
                    expected="端侧渲染后确认文字区域对比度",
                    message="fusionBall 背景由兄弟装饰层合成，静态对比度不作阻塞判定",
                    fix_hint="请在端侧渲染后复核文字可读性；仅在实际不可读时调整颜色。",
                    source="aesthetic-contrast",
                )
                return
            ratios = []
            for item in effective_backgrounds:
                try:
                    ratios.append(_contrast(foreground, item))
                except ValueError:
                    continue
            if ratios:
                ratio = _reported_contrast_ratio(ratios, is_gradient)
                if ratio < 4.5:
                    # 渐变 stop 只代表背景采样点，无法证明文本矩形整体不可读。
                    # 渐变场景统一进入渲染复核；纯色背景继续按最低阈值阻塞。
                    severity = "warning" if is_gradient else ("error" if ratio < 3 else "warning")
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
                        expected=(
                            ">= 3:1 after render review; >= 4.5:1 recommended"
                            if is_gradient
                            else ">= 3:1; >= 4.5:1 recommended"
                        ),
                        message=(
                            f"text contrast is {ratio:.2f}:1; gradient requires render review"
                            if is_gradient
                            else f"text contrast is {ratio:.2f}:1"
                        ),
                        fix_hint=(
                            "Confirm readability on the rendered gradient; adjust contrast "
                            "only if the text area is unclear."
                            if is_gradient
                            else "Use a stronger foreground color or adjust the background."
                        ),
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
                    is_fusion_scene=is_fusion_scene,
                )

    @staticmethod
    def _has_text(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return bool(value)
        return value is not None
