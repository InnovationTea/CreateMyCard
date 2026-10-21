"""融合后置主题的单一配置入口；不读取或修改模板主题。"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

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
_CONTENT_ELIGIBILITY = {
    "type": "object", "additionalProperties": False, "required": ["kind", "businesses"],
    "properties": {
        "kind": {"const": "uniform"},
        "maxTextLines": {"type": "integer", "minimum": 1, "maximum": 3},
        "placement": {"enum": ["top-left-empty-bottom", "bottom-left", "not-bottom-left",
                               "center", "not-center"]},
        "businesses": {"type": "array", "minItems": 1, "uniqueItems": True,
                       "items": {"enum": ["calendar", "battery", "earphone", "weather",
                                          "sleep", "music", "sport", "countdown", "holiday",
                                          "travel", "information", "smart-home"]}},
    },
}
_PHOTO_ELIGIBILITY = {
    "type": "object", "additionalProperties": False,
    "required": ["maxTextLines", "includeTitle", "includeButtons", "squareSingleBusiness",
                 "squareSubjectAlignment", "wideLayout"],
    "properties": {
        "maxTextLines": {"const": 3}, "includeTitle": {"const": False},
        "includeButtons": {"const": False}, "squareSingleBusiness": {"const": True},
        "squareSubjectAlignment": {"const": "left"},
        "wideLayout": {
            "type": "object", "additionalProperties": False,
            "required": ["layout", "orientation"],
            "properties": {"layout": {"const": "W-content-side-slots"},
                           "orientation": {"const": "content-left"}},
        },
    },
}
_THEME = {
    "type": "object",
    "required": ["id", "enabled", "kind", "pool", "name", "description", "sizes",
                 "background", "content"],
    "properties": {
        "id": {"type": "string", "pattern": r"^[a-z][a-z0-9-]*$"},
        "enabled": {"type": "boolean"},
        "kind": {"enum": ["solid", "gradient", "fusion", "photo"]},
        "pool": {"enum": ["standard", "photos", "texturePhotos", "subjectlessWidePhotos",
                          "squareExpansions"]},
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
        "remoteUrl": {"type": "string"},
        "objectFit": {"enum": ["fill", "cover"]}, "frame": _FRAME,
    }},
}
_PHOTO_FALLBACKS = {
    "type": "object", "additionalProperties": False, "required": ["color"],
    "properties": {
        "color": {"type": "string", "pattern": r"^#FF[0-9A-Fa-f]{6}$"},
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
    if pool in {"photos", "texturePhotos"} and "contentEligibility" not in theme:
        raise ValueError("Native photos require unified content eligibility")
    if theme.get("subjectless") is True:
        native_pool = pool in {"photos", "texturePhotos"}
        if kind != "photo" or not native_pool or theme.get("composition") != "native":
            raise ValueError("Subjectless policy requires a native photo")
    if "contentEligibility" in theme:
        _validate_content_eligibility(theme)
    if "subjectlessLayout" in theme:
        if theme.get("subjectless") is not True:
            raise ValueError("Subjectless layout requires an explicit subjectless policy")
        native_wide = pool in {"photos", "texturePhotos"} and sizes == ["2x4"]
        if not native_wide or theme.get("composition") != "native":
            raise ValueError("Subjectless layout requires a native 2x4 photo")
    if (pool == "standard") != (kind != "photo"):
        raise ValueError("Theme pool does not match its kind")
    if kind in {"solid", "gradient"}:
        _check(theme.get("family"), _TEXT, "family")
    if kind == "photo":
        _validate_photo(theme)


def _validate_content_eligibility(theme: dict) -> None:
    if theme.get("pool") not in {"photos", "texturePhotos"}:
        raise ValueError("Unified photo eligibility requires a current native photo pool")
    if theme.get("kind") != "photo" or theme.get("composition") != "native":
        raise ValueError("Unified photo eligibility requires native composition")
    is_texture = theme.get("pool") == "texturePhotos"
    if theme.get("subjectless") is not is_texture:
        raise ValueError("Only the abstract texture pool uses subjectless policy")
    policy = theme.get("contentEligibility", {})
    placement = policy.get("placement")
    if placement == "top-left-empty-bottom":
        if is_texture or theme.get("sizes") != ["2x2"]:
            raise ValueError("Top-only content requires a square subject photo")
        if policy.get("maxTextLines") != 2:
            raise ValueError("Top-only content requires the approved two-line limit")
    elif placement in {"bottom-left", "not-bottom-left"}:
        if is_texture or theme.get("sizes") != ["2x4"]:
            raise ValueError("Bottom-left content requires a wide subject photo")
    elif placement in {"center", "not-center"}:
        if not is_texture or theme.get("sizes") != ["2x2"]:
            raise ValueError("Centered shape selection requires a square texture photo")


def _validate_photo(theme: dict) -> None:
    roles = theme.get("content", {}).get("roles", {})
    rgb = "FFFFFF"
    if theme.get("pool") == "photos" and roles.get("primary") == "#FF000000":
        rgb = "000000"
    expected = {
        "primary": "#FF" + rgb, "secondary": "#CC" + rgb, "tertiary": "#99" + rgb,
        "graphicPrimary": "#FF" + rgb, "graphicSecondary": "#CC" + rgb,
        "graphicTertiary": "#99" + rgb,
    }
    for name, color in expected.items():
        if roles.get(name) != color:
            raise ValueError("Photo foreground requires one black or white palette at 100/80/60%")
    _validate_photo_url(theme.get("background", {}).get("remoteUrl", ""))
    if "measurementPolicy" in theme:
        raise ValueError("Runtime photo matching must not depend on device measurements")
    pool = theme.get("pool")
    sizes = theme.get("sizes", [])
    native_pool = pool in {"photos", "texturePhotos"}
    if len(sizes) != 1 or (not native_pool and sizes != ["2x4"]):
        raise ValueError("Photo pool has incompatible sizes")
    _check(theme.get("business"), _TEXT, "photo.business")
    if pool == "subjectlessWidePhotos":
        if theme.get("composition") != "subjectless":
            raise ValueError("Native wide photos must be subjectless")
    elif not native_pool:
        bounds = theme.get("subjectBounds")
        rectangle = {"type": "array", "minItems": 4, "maxItems": 4,
                     "items": {"type": "number"}}
        _check(bounds, rectangle, "subjectBounds")
        if bounds[2] <= 0 or bounds[3] <= 0:
            raise ValueError("Photo subject bounds must have positive dimensions")
        regions = theme.get("subjectRegions")
        if regions is not None:
            minimum = 0 if pool == "texturePhotos" else 1
            _check(regions, {"type": "array", "minItems": minimum, "items": rectangle},
                   "subjectRegions")
    if theme.get("composition") == "native":
        _check(theme.get("matchingPolicy"), {"const": "layout-only"}, "matchingPolicy")
        _validate_native_photo(theme)
    if pool == "squareExpansions":
        if theme.get("sourceSize") != "2x2" or theme.get("composition") != "square-left":
            raise ValueError("Expansion must preserve the 2x2 foreground in the left half")


def _validate_photo_url(address: str) -> None:
    if not address:
        return
    for character in address:
        if character.isspace() or ord(character) < 32:
            raise ValueError("Photo remoteUrl must not contain whitespace or control characters")
    parsed = urlsplit(address)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("Photo remoteUrl must be a complete HTTPS asset URL")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("Photo remoteUrl must not contain credentials or fragments")


def _validate_native_photo(theme: dict) -> None:
    background = theme.get("background", {})
    frame = {"slotWidth": 1, "slotHeight": 1, "imageWidth": 1, "imageHeight": 1,
             "align": "topStart"}
    if background.get("objectFit") != "fill" or background.get("frame") != frame:
        raise ValueError("Native UX photos require full-frame adaptive fill")


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
    if "photoSelectionGroups" in payload:
        raise ValueError("Per-image selection groups are replaced by uniform pool selection")
    _check(payload.get("photoEligibility"), _PHOTO_ELIGIBILITY, "photoEligibility")
    _check(payload.get("photoSurfaceStyle"), {
        "type": "object", "additionalProperties": False, "required": ["backdropBlur"],
        "properties": {"backdropBlur": {
            "type": "object", "additionalProperties": False, "required": ["radius"],
            "properties": {"radius": {"type": "number", "minimum": 0}},
        }},
    }, "photoSurfaceStyle")
    photo_fallbacks = payload.get("photoFallbacks")
    _check(photo_fallbacks, _PHOTO_FALLBACKS, "photoFallbacks")
    _check(payload.get("matching"), {
        "type": "object", "additionalProperties": False,
        "required": ["mode", "unknownGeometryPolicy"],
        "properties": {"mode": {"const": "layout-only"},
                       "unknownGeometryPolicy": {"const": "layout-contract"}},
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


def photo_fallback() -> dict:
    """图片统一使用UX指定的不透明底色，与字色及普通主题选择无关。"""
    return load_theme_registry().get("photoFallbacks", {})


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
