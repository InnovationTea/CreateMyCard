# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Load the versioned visual recipes used by Compact high-level components."""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.theme_style_roles import in_layout_phase, recipe_roles, role

VISUAL_RECIPE_VERSION = "visual-recipes-v1"
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "protocol_profiles"
    / "design-compact-dsl-fusion"
    / "runtime"
    / "visual-recipes-v1.json"
)
_ALIGNMENT_VALUES = frozenset({"aligned", "adapted", "native"})
_ARGB_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{8}$")
_PALETTE_ROLES = frozenset(
    {
        "primary",
        "secondary",
        "tertiary",
        "graphicPrimary",
        "graphicSecondary",
        "graphicTertiary",
        "componentSecondary",
        "componentTertiary",
    }
)
_DEFAULT_PALETTE = "blue"
_TEXT_BLOCK_FULL_WIDTH_BUDGET = 280.0
_TEXT_BLOCK_FULL_WIDTH_ALLOWANCE = 4.0


class CompactComponentRuntimeError(ValueError):
    """Raised when the visual recipe contract is unavailable or malformed."""


@dataclass(frozen=True)
class TextBlockWidthContract:
    """组件能力与槽位容量分离；所有尺寸取自同一视觉配方。"""

    minimum_items: int
    maximum_items: int
    item_minimum_width: float
    gap: float

    def required_width(self, count: int) -> float:
        if isinstance(count, bool) or not isinstance(count, int):
            raise CompactComponentRuntimeError("TextBlock item count must be an integer.")
        if not self.minimum_items <= count <= self.maximum_items:
            raise CompactComponentRuntimeError("TextBlock item count is outside recipe capacity.")
        return count * self.item_minimum_width + (count - 1) * self.gap

    def capacity_for_width(self, width: float) -> int:
        if not math.isfinite(width) or width < 0:
            raise CompactComponentRuntimeError("TextBlock available width must be non-negative.")
        for count in range(self.maximum_items, self.minimum_items - 1, -1):
            if self.required_width(count) <= width:
                return count
        return 0


def text_block_width_contract(size: str = "2x4") -> TextBlockWidthContract:
    """读取配方的固有上限，不把某个卡片槽宽写成组件上限。"""
    recipe = component_visual_recipe("TextBlock", size=size)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactComponentRuntimeError("TextBlock visual recipe has invalid metrics.")
    minimum = metrics.get("minimumItems")
    maximum = metrics.get("maximumItems")
    width = metrics.get("minimumItemWidth")
    if isinstance(minimum, bool) or isinstance(maximum, bool):
        raise CompactComponentRuntimeError("TextBlock visual recipe has invalid capacity.")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise CompactComponentRuntimeError("TextBlock visual recipe has invalid capacity.")
    if minimum < 1 or maximum < minimum:
        raise CompactComponentRuntimeError("TextBlock visual recipe has invalid capacity.")
    _, root = visual_recipe_part("TextBlock", "root", size=size)
    gap = root.get("itemMargin")
    for value in (width, gap):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CompactComponentRuntimeError("TextBlock visual recipe has invalid width metrics.")
        if not math.isfinite(value) or value < 0:
            raise CompactComponentRuntimeError("TextBlock visual recipe has invalid width metrics.")
    if width <= 0:
        raise CompactComponentRuntimeError("TextBlock item minimum width must be positive.")
    return TextBlockWidthContract(minimum, maximum, float(width), float(gap))


def text_block_full_width_budget(available: float, full_width: float) -> float:
    """仅放宽接近 280vp 的满宽参考预算，不改变渲染尺寸或窄槽位。"""
    if available < full_width:
        return available
    if available < _TEXT_BLOCK_FULL_WIDTH_BUDGET - _TEXT_BLOCK_FULL_WIDTH_ALLOWANCE:
        return available
    return max(available, _TEXT_BLOCK_FULL_WIDTH_BUDGET)


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompactComponentRuntimeError(
            f"Unable to load Compact visual recipe contract: {_CONTRACT_PATH}"
        ) from exc
    _validate_contract(payload)
    return payload


def load_visual_recipe_contract() -> dict[str, Any]:
    """Return an isolated copy of the complete visual recipe contract."""
    return copy.deepcopy(_load_contract())


def resolve_card_color_palette(
    root_props: dict[str, Any],
    *,
    theme: str = "light",
    fusion_ball_active: bool = False,
) -> dict[str, str]:
    """Resolve semantic content-color roles from the authored root surface."""
    if in_layout_phase():
        return {name: role(name) for name in _PALETTE_ROLES}
    palettes = _load_contract()["palettes"]
    if fusion_ball_active:
        return _palette_roles(palettes, "fusionDark")

    surface_colors, gradient_colors = _root_surface_colors(root_props)
    matched_name = _match_registered_palette(
        palettes,
        surface_colors=surface_colors,
        gradient_colors=gradient_colors,
    )
    if matched_name is not None:
        return _palette_roles(palettes, matched_name)

    if surface_colors:
        palette_name = _contrast_palette_name(surface_colors, theme=theme)
        return _palette_roles(palettes, palette_name)
    if root_props.get("backgroundImage") is not None and theme == "dark":
        return _palette_roles(palettes, "neutralDark")
    return _palette_roles(palettes, _DEFAULT_PALETTE)


def component_visual_recipe(
    component_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> dict[str, Any]:
    """Resolve one component recipe with size and variant overrides applied."""
    from services.generation_content_policy import STATIC_COMPONENTS, current_content_policy
    from services.static_text_capacity import component_spec

    if component_name in STATIC_COMPONENTS:
        if not current_content_policy().is_static:
            raise CompactComponentRuntimeError("静态组件未获本请求授权。")
        return {
            "alignment": "aligned",
            "metrics": component_spec(component_name),
            "parts": {"root": {"component": "Column", "styles": {"width": "matchParent"}}},
        }
    components = _load_contract()["components"]
    recipe = components.get(component_name)
    if not isinstance(recipe, dict):
        raise CompactComponentRuntimeError(f"Visual recipe is not registered for {component_name}.")
    resolved = copy.deepcopy(recipe)
    if size is not None:
        size_recipes = recipe.get("sizes", {})
        if not isinstance(size_recipes, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe sizes must be an object for {component_name}."
            )
        size_recipe = size_recipes.get(size)
        if isinstance(size_recipe, dict):
            resolved = _deep_merge(resolved, size_recipe)
    if variant is not None:
        variants = recipe.get("variants", {})
        if not isinstance(variants, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe variants must be an object for {component_name}."
            )
        variant_recipe = variants.get(variant)
        if not isinstance(variant_recipe, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe variant {variant} is not registered for {component_name}."
            )
        resolved = _deep_merge(resolved, variant_recipe)
    return recipe_roles(component_name, resolved) if in_layout_phase() else resolved


def secondary_body_variant(items: list[dict[str, Any]], columns: int = 2) -> str | None:
    """按实际声明的行布局选择字号，不按内容角色或字段数量区分。"""
    multiline = len(items) > columns
    for item in items:
        if item.get("maxLines", 1) == 2:
            multiline = True
    return "multiline" if multiline else None


@dataclass(frozen=True)
class SecondaryBodyLayout:
    row_sizes: tuple[int, ...]
    max_lines: tuple[int, ...]
    multiline: bool


def secondary_body_text_width(text: str, font: float) -> float:
    """保守字符压力估算，不作为精确字体测量或新的校验门禁。"""
    return sum(font * (0.6 if character.isascii() else 1.0) for character in text)


def secondary_body_layout(
    items: list[dict[str, Any]],
    *,
    columns: int,
    texts: list[str | None],
    width: float | None,
    separator: str,
) -> SecondaryBodyLayout:
    """首帧可知时按完整文字分组；未知文案不静态化，不猜测。"""
    row_sizes: list[int] = []
    max_lines: list[int] = []
    multiline = secondary_body_variant(items, columns) is not None
    for item in items:
        max_lines.append(item.get("maxLines", 1))
    index = 0
    while index < len(items):
        row_size = min(columns, len(items) - index)
        text = texts[index]
        if width is not None and text is not None:
            if "\n" in text or secondary_body_text_width(text, 14.0) > width:
                multiline = True
                row_size = 1
            if row_size == 2:
                next_text = texts[index + 1]
                if next_text is not None:
                    combined = text + separator + next_text
                    if secondary_body_text_width(combined, 14.0) > width:
                        row_size = 1
                        multiline = True
        row_sizes.append(row_size)
        index += row_size
    if len(row_sizes) > 1:
        multiline = True
    if multiline and width is not None:
        for index, text in enumerate(texts):
            if text is None:
                continue
            required = secondary_body_text_width(text, 12.0)
            if "\n" in text or width < required <= width * 2:
                max_lines[index] = 2
    return SecondaryBodyLayout(tuple(row_sizes), tuple(max_lines), multiline)


def visual_recipe_part(
    component_name: str,
    part_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return the base component type and styles for one named recipe part."""
    recipe = component_visual_recipe(component_name, size=size, variant=variant)
    parts = recipe.get("parts")
    part = parts.get(part_name) if isinstance(parts, dict) else None
    if not isinstance(part, dict):
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} is not registered."
        )
    component_type = part.get("component")
    styles = part.get("styles")
    if not isinstance(component_type, str) or not component_type:
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} has no component type."
        )
    if not isinstance(styles, dict):
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} has invalid styles."
        )
    output_styles = copy.deepcopy(styles)
    output_styles["_visualRecipe"] = f"{VISUAL_RECIPE_VERSION}:{component_name}.{part_name}"
    return component_type, output_styles


def _validate_contract(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("version") != VISUAL_RECIPE_VERSION:
        raise CompactComponentRuntimeError(
            f"Compact visual recipe contract must use version {VISUAL_RECIPE_VERSION}."
        )
    _validate_palettes(payload.get("palettes"))
    components = payload.get("components")
    if not isinstance(components, dict) or not components:
        raise CompactComponentRuntimeError(
            "Compact visual recipe contract must declare components."
        )
    for component_name, recipe in components.items():
        if not isinstance(component_name, str) or not isinstance(recipe, dict):
            raise CompactComponentRuntimeError(
                "Compact visual recipe components must be named objects."
            )
        if recipe.get("alignment") not in _ALIGNMENT_VALUES:
            raise CompactComponentRuntimeError(
                f"Visual recipe {component_name} has an invalid alignment classification."
            )
        parts = recipe.get("parts")
        if not isinstance(parts, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe {component_name}.parts must be an object."
            )


def _validate_palettes(palettes: Any) -> None:
    if not isinstance(palettes, dict) or not palettes:
        raise CompactComponentRuntimeError(
            "Compact visual recipe contract must declare palettes."
        )
    required_names = {
        "blue",
        "purple",
        "warm",
        "fusionDark",
        "neutralLight",
        "neutralDark",
    }
    if not required_names.issubset(palettes):
        raise CompactComponentRuntimeError(
            "Compact visual recipe contract is missing required palettes."
        )
    for palette_name, palette in palettes.items():
        if not isinstance(palette_name, str) or not isinstance(palette, dict):
            raise CompactComponentRuntimeError(
                "Compact visual recipe palettes must be named objects."
            )
        backgrounds = palette.get("backgrounds")
        gradients = palette.get("gradients")
        roles = palette.get("roles")
        if not isinstance(backgrounds, list) or not all(
            _is_argb_color(color) for color in backgrounds
        ):
            raise CompactComponentRuntimeError(
                f"Visual palette {palette_name}.backgrounds must contain ARGB colors."
            )
        if not isinstance(gradients, list) or not all(
            _is_color_pair(colors) for colors in gradients
        ):
            raise CompactComponentRuntimeError(
                f"Visual palette {palette_name}.gradients must contain ARGB color pairs."
            )
        if not isinstance(roles, dict) or set(roles) != _PALETTE_ROLES:
            raise CompactComponentRuntimeError(
                f"Visual palette {palette_name}.roles must declare every semantic role."
            )
        if not all(_is_argb_color(color) for color in roles.values()):
            raise CompactComponentRuntimeError(
                f"Visual palette {palette_name}.roles must use ARGB colors."
            )


def _palette_roles(palettes: dict[str, Any], palette_name: str) -> dict[str, str]:
    palette = palettes.get(palette_name)
    roles = palette.get("roles") if isinstance(palette, dict) else None
    if not isinstance(roles, dict):
        raise CompactComponentRuntimeError(
            f"Visual palette {palette_name} does not declare semantic roles."
        )
    return copy.deepcopy(roles)


def _root_surface_colors(
    root_props: dict[str, Any],
) -> tuple[list[str], tuple[str, ...] | None]:
    gradient = root_props.get("linearGradient")
    gradient_colors: tuple[str, ...] | None = None
    if isinstance(gradient, dict):
        stops = gradient.get("colors")
        extracted: list[str] = []
        if isinstance(stops, list):
            for stop in stops:
                if not isinstance(stop, list) or not stop:
                    continue
                color = stop[0]
                if _is_argb_color(color):
                    extracted.append(color.upper())
        if extracted:
            gradient_colors = tuple(extracted)

    surface_colors = list(gradient_colors or ())
    background = root_props.get("backgroundColor")
    if not surface_colors and _is_argb_color(background):
        surface_colors.append(background.upper())
    return surface_colors, gradient_colors


def _match_registered_palette(
    palettes: dict[str, Any],
    *,
    surface_colors: list[str],
    gradient_colors: tuple[str, ...] | None,
) -> str | None:
    for palette_name in ("blue", "purple", "warm"):
        palette = palettes.get(palette_name)
        if not isinstance(palette, dict):
            continue
        backgrounds = {
            color.upper()
            for color in palette.get("backgrounds", [])
            if isinstance(color, str)
        }
        if len(surface_colors) == 1 and surface_colors[0] in backgrounds:
            return palette_name
        gradients = palette.get("gradients", [])
        normalized_gradients = {
            tuple(color.upper() for color in colors)
            for colors in gradients
            if _is_color_pair(colors)
        }
        if gradient_colors in normalized_gradients:
            return palette_name
    return None


def _contrast_palette_name(colors: list[str], *, theme: str) -> str:
    backdrop = (0, 0, 0) if theme == "dark" else (255, 255, 255)
    backgrounds = [_composited_rgb(color, backdrop=backdrop) for color in colors]
    dark = (26, 26, 26)
    light = (255, 255, 255)
    dark_contrast = min(_contrast_ratio(dark, background) for background in backgrounds)
    light_contrast = min(_contrast_ratio(light, background) for background in backgrounds)
    return "neutralDark" if light_contrast > dark_contrast else "neutralLight"


def _composited_rgb(
    color: str,
    *,
    backdrop: tuple[int, int, int],
) -> tuple[int, int, int]:
    alpha = int(color[1:3], 16) / 255
    foreground = tuple(int(color[index:index + 2], 16) for index in (3, 5, 7))
    return tuple(
        round(channel * alpha + background * (1 - alpha))
        for channel, background in zip(foreground, backdrop, strict=True)
    )


def _contrast_ratio(
    foreground: tuple[int, int, int],
    background: tuple[int, int, int],
) -> float:
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: tuple[int, int, int]) -> float:
    channels: list[float] = []
    for value in color:
        normalized = value / 255
        if normalized <= 0.04045:
            channels.append(normalized / 12.92)
        else:
            channels.append(((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _is_argb_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_ARGB_COLOR_PATTERN.fullmatch(value))


def _is_color_pair(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(
        _is_argb_color(color) for color in value
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
            continue
        merged[key] = copy.deepcopy(value)
    return merged
