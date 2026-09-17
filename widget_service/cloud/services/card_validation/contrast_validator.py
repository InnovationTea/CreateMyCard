# -*- coding: utf-8 -*-
"""Minimal text/background contrast validation for the quality stage."""

from __future__ import annotations

import logging
import re
from typing import Any

from .base import BaseValidator

_LOGGER = logging.getLogger(__name__)
_HEX_COLOR = re.compile(r"^#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_NORMAL_ROOT_ID = "root_0"
_FUSION_BACKGROUND_ID = "fusionBallBackground"
_OPAQUE_ALPHA = 1.0

_APPROVED_PLAIN_PALETTES = {
    "#FFE5EDFE": {
        "foregrounds": frozenset({"#FF1F4799", "#991F4799"}),
        "surfaces": frozenset({"#FFE5EDFE", "#331F4799", "#1A1F4799"}),
    },
    "#FFEDE6FF": {
        "foregrounds": frozenset({"#FF401F99", "#99401F99"}),
        "surfaces": frozenset({"#FFEDE6FF", "#33401F99", "#1A401F99"}),
    },
    "#FFF0FFE6": {
        "foregrounds": frozenset({"#FF52991F", "#9952991F"}),
        "surfaces": frozenset({"#FFF0FFE6", "#3352991F", "#1A52991F"}),
    },
    "#FFFFF3E6": {
        "foregrounds": frozenset({"#FF99661F", "#9999661F"}),
        "surfaces": frozenset({"#FFFFF3E6", "#3399661F", "#1A99661F"}),
    },
    "#FFE6FDFF": {
        "foregrounds": frozenset({"#FF1F8F99", "#991F8F99"}),
        "surfaces": frozenset({"#FFE6FDFF", "#331F8F99", "#1A1F8F99"}),
    },
}

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


def _normalized_hex(value: Any) -> str | None:
    if not isinstance(value, str) or _HEX_COLOR.fullmatch(value.strip()) is None:
        return None
    raw = value.strip().upper()
    return f"#FF{raw[1:]}" if len(raw) == 7 else raw


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
        if context.has_fusion_template_root():
            _LOGGER.info(
                "quality_validation_skipped reason=template_root validator=contrast"
            )
            return
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
        root_styles = root.get("styles")
        root_styles = root_styles if isinstance(root_styles, dict) else {}
        palette = _APPROVED_PLAIN_PALETTES.get(
            _normalized_hex(root_styles.get("backgroundColor"))
        )
        self._walk(
            context,
            reporter,
            root,
            [(1.0, 1.0, 1.0)],
            is_gradient=False,
            is_fusion_scene=is_fusion_scene and not is_normal_scene,
            approved_palette=palette,
            approved_surface_path=palette is not None,
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
        approved_palette: dict[str, frozenset[str]] | None,
        approved_surface_path: bool,
    ) -> None:
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        effective_backgrounds = list(backgrounds)
        background_color = _normalized_hex(styles.get("backgroundColor"))
        if background_color is not None and approved_palette is not None:
            approved_surface_path = (
                approved_surface_path
                and background_color in approved_palette["surfaces"]
            )
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
            approved_surface_path = False

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
                    foreground_color = _normalized_hex(foreground)
                    uses_approved_palette = (
                        approved_palette is not None
                        and approved_surface_path
                        and foreground_color in approved_palette["foregrounds"]
                    )
                    # 渐变 stop 只代表背景采样点，无法证明文本矩形整体不可读。
                    # 固定色板是受控设计输入，与渐变一样进入渲染复核；
                    # 其他纯色背景继续按最低阈值阻塞。
                    requires_render_review = is_gradient or uses_approved_palette
                    severity = (
                        "warning"
                        if requires_render_review
                        else ("error" if ratio < 3 else "warning")
                    )
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
                    approved_palette=approved_palette,
                    approved_surface_path=approved_surface_path,
                )

    @staticmethod
    def _has_text(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return bool(value)
        return value is not None
