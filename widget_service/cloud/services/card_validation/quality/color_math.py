"""共享颜色合成与候选采样；不推断空间覆盖或端侧模糊结果。"""

from __future__ import annotations

import re
from typing import Any

_HEX_COLOR = re.compile(r"^#(?P<hex>[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RgbColor = tuple[float, float, float]
RgbaColor = tuple[float, float, float, float]


def _rgba(value: Any) -> RgbaColor:
    if not isinstance(value, str):
        raise ValueError("color value must be a hex string")
    match = _HEX_COLOR.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid hex color: {value!r}")
    raw = match.group("hex")
    alpha = 1.0
    if len(raw) == 8:
        alpha = int(raw[:2], 16) / 255
        raw = raw[2:]
    red = int(raw[:2], 16) / 255
    green = int(raw[2:4], 16) / 255
    blue = int(raw[4:6], 16) / 255
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


def approved_color_pair(
    foreground: Any, backgrounds: list[RgbColor], approved_pairs: list[dict[str, Any]]
) -> bool:
    """仅认可已登记的前景与实际背景精确组合，不按近似色或组件 ID 豁免。"""
    if not isinstance(foreground, str):
        return False
    normalized = []
    for background in backgrounds:
        normalized.append([round(value, 9) for value in background])
    normalized.sort()
    for pair in approved_pairs:
        if pair.get("foreground") != foreground.upper():
            continue
        if pair.get("backgrounds") == normalized:
            return True
    return False
