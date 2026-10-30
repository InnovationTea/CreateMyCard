"""将模型生成的背景参考色路由到登记色系，不解析用户语言关键词。"""

import colorsys
import re

from services.post_layout_theme_registry import load_theme_registry, palette_family_options

_HEX_LITERAL = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?(?![0-9a-fA-F])")
_RGB_LITERAL = re.compile(
    r"\brgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})"
    r"(?:\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?|\.\d+))?\s*\)", re.IGNORECASE,
)


def _literal_colors(evidence: str) -> set[str]:
    colors = set()
    for token in _HEX_LITERAL.findall(evidence):
        color = token.upper()
        colors.add("#FF" + color[1:] if len(color) == 7 else color)
    for red, green, blue, alpha in _RGB_LITERAL.findall(evidence):
        channels = [int(red), int(green), int(blue)]
        if max(channels) > 255:
            continue
        opacity = round(float(alpha) * 255) if alpha else 255
        colors.add(f"#{opacity:02X}{channels[0]:02X}{channels[1]:02X}{channels[2]:02X}")
    return colors


def _palette_family(color: str) -> str | None:
    red, green, blue = int(color[3:5], 16), int(color[5:7], 16), int(color[7:9], 16)
    hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    routing = load_theme_registry().get("selection", {}).get("backgroundPaletteRouting", {})
    selected: str | None = None
    closest = 361.0
    chromatic = saturation >= routing.get("minSaturation", 1)
    if chromatic and value >= routing.get("minValue", 1):
        for family, anchor in routing.get("hueAnchors", {}).items():
            delta = abs(hue * 360 - anchor)
            distance = min(delta, 360 - delta)
            if distance < closest:
                closest, selected = distance, family
    if selected not in palette_family_options():
        selected = None
    return selected


def _fixed_background_requested(items: list[dict]) -> bool:
    fixed = False
    excluded_kinds = set()
    for item in items:
        if item.get("property") == "backgroundTone":
            fixed = True  # 保留已有“具体底色优先于深浅”的行为。
        if item.get("property") != "backgroundKind":
            continue
        if item.get("operator") == "prefer" and item.get("value") == "solid":
            fixed = True
        if item.get("operator") == "avoid":
            excluded_kinds.add(item.get("value"))
    return fixed or {"fusion", "gradient"}.issubset(excluded_kinds)


def normalize_background_colors(items: list[dict]) -> list[dict]:
    """只接收已校验偏好；固定背景约束和原文精确数值的优先级高于色系。"""
    fixed_background = _fixed_background_requested(items)
    result = []
    for item in items:
        if item.get("property") != "backgroundColor" or item.get("operator") != "prefer":
            result.append(item)
            continue
        color = item.get("value")
        literals = _literal_colors(item.get("evidence", ""))
        if literals and color not in literals:
            raise ValueError("Background color does not match the numeric evidence")
        family = None if literals or fixed_background else _palette_family(color)
        if family:
            result.append({**item, "property": "paletteFamily", "value": family})
        else:
            result.append(item)
    return result
