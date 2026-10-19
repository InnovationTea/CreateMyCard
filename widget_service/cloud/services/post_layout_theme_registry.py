"""融合后置主题的单一配置入口；不读取或修改模板主题。"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from services.compact_component_runtime import _composited_rgb, _contrast_ratio
from services.theme_style_roles import ROLES

MANIFEST = Path(__file__).resolve().parents[1] / "data/post_layout_themes.json"
_COLOR = {"type": "string", "pattern": r"^#[0-9A-Fa-f]{8}$"}
_TEXT = {"type": "string", "minLength": 1}
_SIZES = {"type": "array", "minItems": 1, "uniqueItems": True,
          "items": {"enum": ["2x2", "2x4"]}}
_ROLE_NAMES = sorted(ROLES - {"panel", "transparent"})
_ROLES = {"type": "object", "required": _ROLE_NAMES, "additionalProperties": False,
          "properties": {name: _COLOR for name in _ROLE_NAMES}}
_FRAME = {
    "type": "object", "additionalProperties": False,
    "required": ["slotWidth", "slotHeight", "imageWidth", "imageHeight", "align"],
    "properties": {
        "slotWidth": {"type": "number", "exclusiveMinimum": 0},
        "slotHeight": {"type": "number", "exclusiveMinimum": 0},
        "imageWidth": {"type": "number", "exclusiveMinimum": 0},
        "imageHeight": {"type": "number", "exclusiveMinimum": 0},
        "align": {"enum": ["topStart", "topEnd", "center", "bottomStart", "bottomEnd"]},
    },
}
_CONTENT_ELIGIBILITY = {"oneOf": [
    {"type": "object", "additionalProperties": False,
     "required": ["kind", "mainBusiness"],
     "properties": {"kind": {"const": "left-main-wide"},
                    "mainBusiness": {"enum": ["sleep", "weather"]}}},
    {"type": "object", "additionalProperties": False,
     "required": ["kind", "layouts", "maxTextLines", "includeTitle"],
     "properties": {
         "kind": {"const": "calendar-square"},
         "maxTextLines": {"const": 2}, "includeTitle": {"const": False},
         "layouts": {"type": "object", "minProperties": 1, "additionalProperties": False,
                     "properties": {"S-title-content": {"const": "left"},
                                    "S-title-dual-content": {"const": "left"}}},
     }},
    {"type": "object", "additionalProperties": False, "required": ["kind", "layouts"],
     "properties": {
         "kind": {"const": "weather-square"},
         "layouts": {"type": "object", "minProperties": 1, "additionalProperties": False,
                     "properties": {"S-title-content": {"const": "left"},
                                    "S-title-dual-content": {"const": "left"}}},
     }},
    {"type": "object", "additionalProperties": False,
     "required": ["kind", "maxTextLines", "includeTitle", "excludeComponents", "layouts"],
     "properties": {
         "kind": {"const": "sleep-square"},
         "maxTextLines": {"type": "integer", "minimum": 1},
         "includeTitle": {"type": "boolean"},
         "excludeComponents": {"const": ["PillButton"]},
         "layouts": {"type": "object", "minProperties": 1, "additionalProperties": False,
                     "properties": {"S-title-content": {"const": "bottom"},
                                    "S-title-dual-content": {"const": "left"},
                                    "S-title-anchor": {"const": "left"}}},
     }},
    {"type": "object", "additionalProperties": False, "required": ["kind", "mainBusinesses"],
     "properties": {
         "kind": {"const": "running-main"},
         "mainBusinesses": {"type": "array", "minItems": 1, "uniqueItems": True,
                            "items": {"enum": ["marathon-countdown", "running"]}},
     }},
]}
_THEME = {
    "type": "object",
    "required": ["id", "enabled", "kind", "pool", "name", "description", "sizes",
                 "background", "content"],
    "properties": {
        "id": {"type": "string", "pattern": r"^[a-z][a-z0-9-]*$"},
        "enabled": {"type": "boolean"},
        "kind": {"enum": ["solid", "gradient", "fusion", "photo"]},
        "pool": {"enum": ["standard", "photos", "subjectlessWidePhotos", "squareExpansions"]},
        "name": _TEXT, "description": _TEXT, "sizes": _SIZES,
        "sourceSize": {"enum": ["2x2"]},
        "businessDescription": _TEXT,
        "matchingPolicy": {"const": "layout-only"},
        "contentEligibility": _CONTENT_ELIGIBILITY,
        "subjectless": {"type": "boolean"},
        "subjectlessLayout": {
            "type": "object", "required": ["layout", "orientation"],
            "additionalProperties": False,
            "properties": {"layout": {"const": "W-content-side-slots"},
                           "orientation": {"const": "content-left"}},
        },
        "backgroundAliases": {"type": "array", "items": _COLOR},
        "content": {
            "type": "object", "additionalProperties": False,
            "required": ["roles", "panelBySize", "explicitTextAlpha"],
            "properties": {
                "roles": _ROLES,
                "panelBySize": {"type": "object", "minProperties": 1,
                                "propertyNames": {"enum": ["2x2", "2x4"]},
                                "additionalProperties": _COLOR},
                "explicitTextAlpha": {
                    "type": "object", "required": ["secondary", "tertiary"],
                    "additionalProperties": False,
                    "properties": {name: {"type": "integer", "minimum": 0, "maximum": 255}
                                   for name in ("secondary", "tertiary")},
                },
            },
        },
    },
}
_BACKGROUNDS = {
    "solid": {"required": ["color"], "properties": {"color": _COLOR}},
    "gradient": {"required": ["colors", "direction"], "properties": {
        "colors": {"type": "array", "minItems": 2, "maxItems": 2, "items": _COLOR},
        "direction": {"enum": ["RightBottom"]},
    }},
    "fusion": {"required": ["ballColors", "glassColor", "blurRadius", "shellColor"],
               "properties": {
                   "ballColors": {"type": "object", "required": ["large", "medium", "small"],
                                  "additionalProperties": False,
                                  "properties": {"large": _COLOR, "medium": _COLOR,
                                                 "small": _COLOR}},
                   "glassColor": _COLOR, "shellColor": _COLOR,
                   "blurRadius": {"type": "number", "minimum": 0},
               }},
    "photo": {"required": ["src", "objectFit", "frame"], "properties": {
        "src": {"type": "string", "pattern": r"^resources/base/media/[\w.-]+\.(jpg|png|jpeg)$"},
        "objectFit": {"enum": ["fill", "cover"]}, "frame": _FRAME,
    }},
}
_PHOTO_FALLBACKS = {
    "type": "object", "additionalProperties": False, "required": ["darkText", "lightText"],
    "properties": {
        "darkText": {
            "type": "object", "additionalProperties": False,
            "required": ["colors", "direction"],
            "properties": {
                "colors": {"type": "array", "minItems": 2, "maxItems": 2,
                           "items": {"type": "string", "pattern": r"^#FF[0-9A-Fa-f]{6}$"}},
                "direction": {"enum": ["LeftBottom", "RightBottom", "LeftTop", "RightTop"]},
            },
        },
        "lightText": {
            "type": "object", "additionalProperties": False, "required": ["themeId"],
            "properties": {"themeId": _TEXT},
        },
    },
}


def _check(value: object, schema: dict, label: str) -> None:
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error is not None:
        location = ".".join(str(part) for part in error.absolute_path)
        raise ValueError(f"Invalid theme registry {label}.{location}: {error.message}")


def _validate_theme(theme: dict) -> None:
    _check(theme, _THEME, "theme")
    kind = theme.get("kind")
    background_schema = _BACKGROUNDS.get(kind)
    if background_schema is None:
        raise ValueError("Unknown theme background kind")
    _check(theme.get("background"), {"type": "object", "additionalProperties": False,
                                     **background_schema}, str(theme.get("id")))
    sizes = theme.get("sizes", [])
    required_sizes = set(sizes)
    if theme.get("sourceSize"):
        required_sizes.add(theme.get("sourceSize"))
    panels = theme.get("content", {}).get("panelBySize", {})
    if not required_sizes.issubset(panels):
        raise ValueError("Theme is missing a panel color for an applicable size")
    if kind == "fusion" and sizes != ["2x2"]:
        raise ValueError("Fusion themes only support 2x2")
    if kind == "fusion":
        _check(theme.get("businessDescription"), _TEXT, "businessDescription")
    pool = theme.get("pool")
    if theme.get("subjectless") is True:
        if kind != "photo" or pool != "photos" or theme.get("composition") != "native":
            raise ValueError("Subjectless policy requires a native photo")
    if "contentEligibility" in theme:
        _validate_content_eligibility(theme)
    if "subjectlessLayout" in theme:
        if theme.get("subjectless") is not True:
            raise ValueError("Subjectless layout requires an explicit subjectless policy")
        native_wide = pool == "photos" and sizes == ["2x4"]
        if not native_wide or theme.get("composition") != "native":
            raise ValueError("Subjectless layout requires a native 2x4 photo")
    if (pool == "standard") != (kind != "photo"):
        raise ValueError("Theme pool does not match its kind")
    if kind in {"solid", "gradient"}:
        _check(theme.get("family"), _TEXT, "family")
    if kind == "photo":
        _validate_photo(theme)


def _validate_content_eligibility(theme: dict) -> None:
    native = theme.get("kind") == "photo" and theme.get("pool") == "photos"
    if not native or theme.get("composition") != "native":
        raise ValueError("Content eligibility requires a native photo")
    policy = theme.get("contentEligibility", {})
    sizes = theme.get("sizes", [])
    square_business = {"weather-square": "weather", "calendar-square": "calendar"}
    if policy.get("kind") in square_business:
        if sizes != ["2x2"] or theme.get("business") != square_business.get(policy.get("kind")):
            raise ValueError("Square eligibility requires a matching 2x2 business photo")
        if theme.get("subjectless") is not False:
            raise ValueError("Square layout policy must retain its subject")
    else:
        if theme.get("subjectless") is not True:
            raise ValueError("Content eligibility requires a native subjectless photo")
        if policy.get("kind") == "sleep-square":
            if sizes != ["2x2"] or theme.get("business") != "sleep":
                raise ValueError("Sleep content eligibility requires a 2x2 sleep photo")
        elif sizes != ["2x4"] or "subjectlessLayout" not in theme:
            raise ValueError("Main business eligibility requires a 2x4 side-slot photo")
        if policy.get("kind") == "left-main-wide":
            if theme.get("business") != policy.get("mainBusiness"):
                raise ValueError("Left main business must match the photo business")


def _validate_photo(theme: dict) -> None:
    if "measurementPolicy" in theme:
        raise ValueError("Runtime photo matching must not depend on device measurements")
    pool = theme.get("pool")
    sizes = theme.get("sizes", [])
    if len(sizes) != 1 or (pool != "photos" and sizes != ["2x4"]):
        raise ValueError("Photo pool has incompatible sizes")
    _check(theme.get("business"), _TEXT, "photo.business")
    if pool == "subjectlessWidePhotos":
        if theme.get("composition") != "subjectless":
            raise ValueError("Native wide photos must be subjectless")
    else:
        bounds = theme.get("subjectBounds")
        rectangle = {"type": "array", "minItems": 4, "maxItems": 4,
                     "items": {"type": "number"}}
        _check(bounds, rectangle, "subjectBounds")
        if bounds[2] <= 0 or bounds[3] <= 0:
            raise ValueError("Photo subject bounds must have positive dimensions")
        regions = theme.get("subjectRegions")
        if regions is not None:
            _check(regions, {"type": "array", "minItems": 1, "items": rectangle}, "subjectRegions")
    if theme.get("composition") == "native":
        _check(theme.get("matchingPolicy"), {"const": "layout-only"}, "matchingPolicy")
        _validate_native_photo(theme)
    if pool == "squareExpansions":
        if theme.get("sourceSize") != "2x2" or theme.get("composition") != "square-left":
            raise ValueError("Expansion must preserve the 2x2 foreground in the left half")


def _validate_native_photo(theme: dict) -> None:
    background = theme.get("background", {})
    frame = {"slotWidth": 1, "slotHeight": 1, "imageWidth": 1, "imageHeight": 1,
             "align": "topStart"}
    if background.get("objectFit") != "fill" or background.get("frame") != frame:
        raise ValueError("Native UX photos require full-frame adaptive fill")
    rectangle = {"type": "array", "minItems": 4, "maxItems": 4,
                 "items": {"type": "number", "minimum": 0, "maximum": 1}}
    _check(theme.get("subjectBounds"), rectangle, "subjectBounds")
    bx, by, bw, bh = theme.get("subjectBounds")
    if bx + bw > 1.000000001 or by + bh > 1.000000001:
        raise ValueError("Photo subject bounds exceed the canvas")
    for key in ("subjectRegions", "contentRegions"):
        _check(theme.get(key), {"type": "array", "minItems": 1, "maxItems": 32,
                               "items": rectangle}, key)
        for x, y, width, height in theme.get(key, []):
            if width <= 0 or height <= 0:
                raise ValueError("Photo regions require positive dimensions")
            if x + width > 1.000000001 or y + height > 1.000000001:
                raise ValueError("Photo region exceeds the normalized canvas")
            if key == "subjectRegions":
                outside_x = x < bx or x + width > bx + bw + 1e-9
                outside_y = y < by or y + height > by + bh + 1e-9
                if outside_x or outside_y:
                    raise ValueError("Photo subject region exceeds its bounds")


def validate_registry(payload: dict) -> None:
    # JSON numeric values must remain finite, including frame and blur parameters.
    json.dumps(payload, allow_nan=False)
    _check(payload, {"type": "object", "required": ["version", "themes", "selection",
                                                   "userColorOverrides", "matching"],
                     "properties": {"version": {"const": 2},
                                    "themes": {"type": "array", "minItems": 1}}}, "root")
    by_id = {}
    for theme in payload.get("themes", []):
        _validate_theme(theme)
        identity = theme.get("id")
        if identity in by_id:
            raise ValueError(f"Duplicate theme ID: {identity}")
        by_id[identity] = theme
    _validate_selection(payload.get("selection"), by_id)
    photo_fallbacks = payload.get("photoFallbacks")
    _check(photo_fallbacks, _PHOTO_FALLBACKS, "photoFallbacks")
    identity = photo_fallbacks.get("lightText", {}).get("themeId")
    target = by_id.get(identity, {})
    if target.get("kind") != "fusion" or not target.get("enabled"):
        raise ValueError("Photo fallback must reference an enabled fusion theme")
    large_color = target.get("background", {}).get("ballColors", {}).get("large", "")
    if not large_color.upper().startswith("#FF"):
        raise ValueError("Photo fallback requires an opaque fusion base color")
    _check(payload.get("matching"), {
        "type": "object", "additionalProperties": False,
        "required": ["mode", "unknownGeometryPolicy"],
        "properties": {"mode": {"const": "layout-only"},
                       "unknownGeometryPolicy": {"const": "reject-subject-photos"}},
    }, "matching")
    overrides = payload.get("userColorOverrides")
    _check(overrides, {"type": "object", "required": ["namedColors", "neutralLight",
                                                     "neutralDark", "legacyPanelColors"],
                       "properties": {
                           "namedColors": {"type": "object", "minProperties": 1,
                                           "additionalProperties": _COLOR},
                           "neutralLight": _ROLES, "neutralDark": _ROLES,
                           "legacyPanelColors": {"type": "array", "items": _COLOR},
                       }}, "userColorOverrides")


def _validate_selection(selection: dict, by_id: dict) -> None:
    _check(selection, {"type": "object", "required": ["rules", "defaultFamily", "familyByDataRoot",
                                                     "fallbacks", "fusionRouting"],
                       "properties": {
                           "rules": _TEXT, "defaultFamily": _TEXT,
                           "familyByDataRoot": {"type": "object", "additionalProperties": _TEXT},
                           "fallbacks": {"type": "object", "minProperties": 1,
                                         "additionalProperties": _TEXT},
                           "fusionRouting": {"type": "array", "items": {
                               "type": "object", "required": ["routes", "themeId"],
                               "properties": {
                                   "routes": {"type": "array", "minItems": 1, "items": _TEXT},
                                   "themeId": _TEXT,
                                   "queryAll": {"type": "array", "items": _TEXT},
                               },
                           }},
                       }}, "selection")
    fallbacks = selection.get("fallbacks", {})
    families = set(selection.get("familyByDataRoot", {}).values())
    families.add(selection.get("defaultFamily"))
    for theme in by_id.values():
        if theme.get("kind") in {"solid", "gradient"}:
            families.add(theme.get("family"))
    if not families.issubset(fallbacks):
        raise ValueError("Every theme family requires an explicit fallback")
    for family, identity in fallbacks.items():
        fallback = by_id.get(identity, {})
        if not fallback.get("enabled") or fallback.get("kind") != "gradient":
            raise ValueError("Fallback must reference an enabled gradient theme")
        if fallback.get("family") != family or set(fallback.get("sizes", [])) != {"2x2", "2x4"}:
            raise ValueError("Fallback family or sizes do not match")
    for rule in selection.get("fusionRouting", []):
        target = by_id.get(rule.get("themeId"), {})
        if target.get("kind") != "fusion":
            raise ValueError("Fusion routing references a missing or incompatible theme")
        for pattern in rule.get("queryAll", []):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError("Invalid fusion business pattern") from exc


@lru_cache(maxsize=1)
def _load_registry(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_registry(payload)
    return payload


def load_theme_registry() -> dict:
    """返回独立副本；配置随服务发布/重启加载，不在请求期间热改。"""
    return copy.deepcopy(_load_registry(MANIFEST))


def registered_themes(pool: str | None = None, *, include_disabled: bool = False) -> list[dict]:
    result = []
    for theme in load_theme_registry().get("themes", []):
        if not include_disabled and not theme.get("enabled"):
            continue
        if pool is not None and theme.get("pool") != pool:
            continue
        if theme.get("kind") == "photo":
            # 兼容既有图片准入/展开函数的参数形状；磁盘配置仍只有一份 background。
            theme.update(theme.get("background", {}))
            theme["size"] = theme.get("sizes", [])[0]
        result.append(theme)
    return result


def fallback_theme(family: str | None) -> dict:
    selection = load_theme_registry().get("selection", {})
    name = family or selection.get("defaultFamily")
    identity = selection.get("fallbacks", {}).get(name)
    for theme in registered_themes("standard"):
        if theme.get("id") == identity:
            return theme
    raise ValueError("No configured fallback theme")


def photo_fallback(primary: str) -> dict:
    """按最终字色选择兜底，只取背景，不改变图片前景或正常主题候选。"""
    config = load_theme_registry()
    fallbacks = config.get("photoFallbacks", {})
    black, white = (0, 0, 0), (255, 255, 255)
    on_light = _composited_rgb(primary, backdrop=white)
    on_dark = _composited_rgb(primary, backdrop=black)
    result = {"kind": "gradient", "background": fallbacks.get("darkText", {})}
    if _contrast_ratio(on_dark, black) > _contrast_ratio(on_light, white):
        identity = fallbacks.get("lightText", {}).get("themeId")
        target = next(
            (item for item in config.get("themes", []) if item.get("id") == identity), None,
        )
        if target is None:
            raise ValueError("Missing photo fallback theme")
        result = {"kind": "fusion", "background": target.get("background", {})}
    return result


def selection_rules() -> str:
    lines = [load_theme_registry().get("selection", {}).get("rules", ""), "", "融球业务映射："]
    for theme in registered_themes("standard"):
        if theme.get("kind") == "fusion":
            lines.append(f"- {theme.get('businessDescription')}: {theme.get('id')}")
    return "\n".join(lines)


def user_background_roles(color: str) -> dict:
    for theme in registered_themes("standard"):
        aliases = theme.get("backgroundAliases", [])
        if color.upper() in {alias.upper() for alias in aliases}:
            return theme.get("content", {}).get("roles", {})
    overrides = load_theme_registry().get("userColorOverrides", {})
    background = _composited_rgb(color, backdrop=(255, 255, 255))
    candidates = []
    for name in ("neutralLight", "neutralDark"):
        roles = overrides.get(name, {})
        foreground = _composited_rgb(roles.get("primary"), backdrop=(255, 255, 255))
        candidates.append((_contrast_ratio(foreground, background), roles))
    return max(candidates, key=lambda candidate: candidate[0])[1]
