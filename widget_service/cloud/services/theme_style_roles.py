"""请求局部的无颜色布局阶段；语义角色只在末尾解析为真实色值。"""

from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_LAYOUT = ContextVar("colorless_layout", default=False)
_NATIVE = ContextVar("native_color_assets", default=frozenset())
ROLE_PATTERN = re.compile(r"^@theme:([A-Za-z]+)(?:/(\d+(?:\.\d+)?))?$")
COLOR_FIELDS = frozenset({
    "fontColor", "fillColor", "color", "backgroundColor", "borderColor", "barColor",
    "trackColor", "dividerColor", "strokeColor", "selectedColor", "unSelectedColor",
    "actionInk", "shadowColor",
})
ROLES = frozenset({
    "primary", "secondary", "tertiary", "graphicPrimary", "graphicSecondary",
    "graphicTertiary", "componentSecondary", "componentTertiary", "panel", "transparent",
})
_PANEL_RECIPE_PARTS = {
    "CardButton": ("root",),
    "SummaryList": ("item",),
    "TextBlock": ("item",),
}


def in_layout_phase() -> bool:
    return _LAYOUT.get()


@contextmanager
def layout_phase(enabled: bool = True, task: dict | None = None):
    token = _LAYOUT.set(enabled)
    native = set()
    for asset in (task or {}).get("assetCandidates", []):
        description = asset.get("description", "")
        if re.search("多色|彩色|保留原色|不可染色|禁止染色|渐变|品牌", description):
            native.add(asset.get("src"))
    native_token = _NATIVE.set(frozenset(native))
    try:
        yield
    finally:
        _NATIVE.reset(native_token)
        _LAYOUT.reset(token)


def role(name: str, opacity: float = 1.0) -> str:
    if name not in ROLES or not 0 <= opacity <= 1:
        raise ValueError("Invalid internal style role")
    return f"@theme:{name}/{opacity:g}"


def is_role(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = ROLE_PATTERN.fullmatch(value)
    return bool(match and match[1] in ROLES and 0 <= float(match[2] or 1) <= 1)


def alpha_role(value: str, opacity: float) -> str:
    match = ROLE_PATTERN.fullmatch(value)
    if match is None or not is_role(value):
        raise ValueError("Invalid internal style role")
    return role(match[1], float(match[2] or 1) * opacity)


def property_role(key: str, value: Any = None) -> str:
    if is_role(value):
        return value
    if isinstance(value, str) and value.startswith("#00"):
        return role("transparent")
    if key in {"backgroundColor", "trackColor"}:
        return role("componentSecondary")
    if key in {"dividerColor", "borderColor"}:
        return role("graphicTertiary")
    if key == "fontColor" and isinstance(value, str) and value.startswith(("#99", "#66")):
        return role("secondary")
    return role("primary")


def role_styles(value: Any) -> Any:
    """在 Recipe 读取边界转换颜色声明，不修改共享缓存。"""
    if isinstance(value, list):
        return [role_styles(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "color" and item == "native":
            result[key] = item
            continue
        if key in {"linearGradient", "backgroundImage", "backgroundImageSizeWithStyle"}:
            continue
        result[key] = property_role(key, item) if key in COLOR_FIELDS else role_styles(item)
    return result


def recipe_roles(kind: str, recipe: dict) -> dict:
    result = role_styles(recipe)
    # 点击能力不改变内容背板的语义，不能按普通按钮底色展开。
    for name in _PANEL_RECIPE_PARTS.get(kind, ()):
        part = result.get("parts", {}).get(name)
        if not isinstance(part, dict) or not isinstance(part.get("styles"), dict):
            raise ValueError(f"Missing registered content surface: {kind}.{name}")
        part.get("styles")["backgroundColor"] = role("panel")
    return result


def component_roles(kind: str, props: dict) -> dict:
    result = role_styles(props)
    surface = result.pop("surfaceRole", None)
    if surface and kind in {"Row", "Column", "Stack", "InfoBlock"}:
        result["backgroundColor"] = role("panel")
    required = {
        "Badge": ("backgroundColor",),
        "ProgressCircle": ("color", "backgroundColor"),
        "ProgressLine2": ("color", "backgroundColor"),
        "ProgressCircleSingle": ("color", "backgroundColor"),
        "NumericRatioStack": ("fillColor",),
        "H_BarChart": ("barColor", "trackColor"),
        "InfoBlock": ("backgroundColor",),
        "Divider": ("color",),
        "TopTextBottomValue": ("dividerColor",),
        "Text": ("fontColor",),
        "Button": ("fontColor",),
    }
    for key in required.get(kind, ()):
        default_role = role("panel") if kind == "InfoBlock" else property_role(key)
        result.setdefault(key, default_role)
    icon = result.get("icon") or result.get("src")
    if isinstance(icon, str) and icon.endswith(".svg"):
        if icon in _NATIVE.get():
            result.pop("fillColor", None)
        elif kind in {"Image", "SingleLineTitle", "ProgressCircle", "CardButton"}:
            result["fillColor"] = role("primary")
    return result


def native_asset(source: Any) -> bool:
    return isinstance(source, str) and source in _NATIVE.get()


def resolve_role(value: str, palette: dict, panel: str | None = None) -> str:
    match = ROLE_PATTERN.fullmatch(value)
    if match is None or not is_role(value):
        raise ValueError("Unknown style role in frozen layout")
    name, opacity = match[1], float(match[2] or 1)
    if name == "transparent":
        return "#00000000"
    color = panel if name == "panel" else palette.get(name)
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{8}", color):
        raise ValueError("Registered theme is missing a required color role")
    return f"#{round(int(color[1:3], 16) * opacity):02X}{color[3:]}"


def unpainted_document(source: str) -> str:
    """测量只移除视觉角色，绝不注入预览颜色或改变几何。"""
    import json

    records = [json.loads(line) for line in source.splitlines() if line.strip()]
    records = copy.deepcopy(records)
    for record in records:
        for node in record.get("updateComponents", {}).get("components", []):
            styles = node.get("styles", {})
            for key in list(styles):
                if is_role(styles[key]):
                    del styles[key]
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in records)
