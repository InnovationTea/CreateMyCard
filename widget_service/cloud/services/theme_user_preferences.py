"""校验主题模型的结构化偏好；不按用户原文中的词汇或句式判断意图。"""

import re

from services.post_layout_theme_registry import (
    load_theme_registry,
    palette_family_options,
    registered_themes,
    theme_palette_families,
    user_background_roles,
)
from services.theme_background_color import normalize_background_colors

_KINDS = frozenset({"photo", "fusion", "gradient", "solid"})
_PROPERTIES = frozenset({
    "backgroundKind", "backgroundTone", "backgroundColor", "textColor", "paletteFamily", "themeId",
})
_FIELDS = frozenset({"property", "operator", "value", "evidence"})
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

PREFERENCE_INSTRUCTION = """
同时理解原始query中的最终有效视觉偏好，返回themeId及preferences，不增加布局或素材。
preferences为数组；无明确偏好返回[]。每项严格为
{"property":"属性","operator":"prefer或avoid","value":"值","evidence":"query中的连续原文"}。
属性和值：
- backgroundKind: photo/fusion/gradient/solid，仅用户明确指定背景形式时输出，
  不从普通色系或氛围需求推导背景形式。
- backgroundTone: dark/light，表示背景明暗。
- paletteFamily: 普通颜色或氛围对应的登记色系，候选的family或paletteFamilies说明其适用范围。
  优先使用可承接该色系的已有融球或渐变，不把普通色名直接变成高饱和纯色。
  登记色系本轮没有合格融球或渐变时由程序提供普通底色，不需要伪造候选或精确色值。
- backgroundColor/textColor: 明确纯色、精确色值或现有候选无法承接的背景色，以及明确文字色，
  规范化为#RRGGBB或#AARRGGBB；不要据普通配色需求额外生成背景色覆盖。
  明确纯色还需返回backgroundKind=solid；精确背景色证据须包含用户给出的同值HEX/RGB。
- themeId: 仅用户明确要求/排除某张登记素材时使用，值须来自本轮候选。
先确定颜色指向的对象和具体程度，图标或文字颜色不改成整卡颜色。氛围需求可选择已有色系，
不虚构精确色值；纯业务标题不构成视觉要求。精确色值和明确纯色仍按用户原意保留。
同一背景不要同时输出paletteFamily和backgroundColor；backgroundColor是固定底色，
不与渐变/图片/融球要求同时输出。未要求纯色时，优先融球，其次已有渐变。
根据整句语义处理否定、转折及最终修正，不按单词出现与否判断。排除要求使用avoid，不得反向设为prefer。
只描述文字、图标或业务内容的明暗不属于背景偏好；普通业务标题、时间、图片名称不是用户颜色指令。
不得从业务、样例或候选内容虚构用户偏好。每项evidence必须引用query真实原文，包含判断所需上下文。
同一属性最多一个最终prefer；不输出已经被用户撤回的要求。未知意图不要猜色值或添加偏好。
图片不具有可靠明暗/背景色元数据，背景颜色、深浅约束将由程序落实为可验证底色。
具体底色优先于深浅；textColor只处理明确文字颜色；不要输出其它设计参数或任意URL。
paletteFusionCandidates仅在用户肯定指定登记色系时可选，此时不受原融球内容门禁限制；
未指定色系、仅排除色系或仅指定融球形式时仍使用默认候选，不扩展候选。
用户偏好不能突破尺寸、启停、端侧版本和图片门禁；无法满足的组合不能伪造新候选。
候选包含通过门禁的全部类型。无偏好时由程序按主体图>抽象图>合格融球>渐变执行，
同级图片由程序等概率选择；普通主题按defaultPalette及原规则选择。
只返回JSON：{"themeId":"本轮候选ID","preferences":[]}。
"""


def parse_preferences(value: object, query: str, candidates: list[dict]) -> list[dict]:
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError("Theme preferences must be an array with at most 16 entries")
    families = set(palette_family_options())
    for candidate in candidates:
        families.update(theme_palette_families(candidate))
    identities = {item.get("id") for item in candidates}
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("Invalid theme preference fields")
        attribute = item.get("property")
        operation = item.get("operator")
        requested = item.get("value")
        evidence = item.get("evidence")
        if not isinstance(attribute, str) or attribute not in _PROPERTIES:
            raise ValueError("Unknown theme preference property")
        if not isinstance(operation, str) or operation not in {"prefer", "avoid"}:
            raise ValueError("Unknown theme preference operator")
        if not isinstance(evidence, str) or not evidence.strip() or evidence not in query:
            raise ValueError("Theme preference requires evidence from the original query")
        if not isinstance(requested, str):
            raise ValueError("Theme preference value must be a string")
        choices = {
            "backgroundKind": _KINDS, "backgroundTone": {"dark", "light"},
            "paletteFamily": families, "themeId": identities,
        }
        if attribute in {"backgroundColor", "textColor"}:
            if not _COLOR.fullmatch(requested):
                raise ValueError("Invalid theme preference color")
            requested = requested.upper()
            if len(requested) == 7:
                requested = "#FF" + requested[1:]
            if attribute == "backgroundColor" and not requested.startswith("#FF"):
                raise ValueError("Requested background must be opaque")
        elif requested not in choices.get(attribute, set()):
            raise ValueError("Preference value is not in the registered choices")
        normalized = {**item, "value": requested}
        result.append(normalized)
    return _merge_preferences(normalize_background_colors(result), candidates)


def _merge_preferences(items: list[dict], candidates: list[dict]) -> list[dict]:
    result = []
    preferred = {}
    avoided: dict[str, set[str]] = {}
    for normalized in items:
        attribute = normalized.get("property")
        operation = normalized.get("operator")
        requested = normalized.get("value")
        if operation == "prefer":
            previous = preferred.get(attribute)
            if previous is not None:
                if attribute != "paletteFamily":
                    raise ValueError("Duplicate preferred theme property")
                previous.update(_merge_palette_preference(previous, normalized, candidates))
                continue
            preferred[attribute] = normalized
        else:
            avoided.setdefault(attribute, set()).add(requested)
        result.append(normalized)
    for attribute, item in preferred.items():
        if item.get("value") in avoided.get(attribute, set()):
            raise ValueError("Conflicting theme preferences")
    if avoided.get("backgroundTone") == {"dark", "light"}:
        raise ValueError("Both background tones are excluded")
    return result


def _merge_palette_preference(previous: dict, current: dict, candidates: list[dict]) -> dict:
    """重复色系描述只在登记主题集合具有包含关系时收敛，不猜测句子含义。"""
    available = registered_themes("standard") + candidates
    previous_ids = set()
    current_ids = set()
    for theme in available:
        families = theme_palette_families(theme)
        if previous.get("value") in families:
            previous_ids.add(theme.get("id"))
        if current.get("value") in families:
            current_ids.add(theme.get("id"))
    if previous_ids and previous_ids.issubset(current_ids):
        return previous
    if current_ids and current_ids.issubset(previous_ids):
        return current
    raise ValueError("Conflicting preferred palette families")


def color_overrides(preferences: list[dict], *, candidates: list[dict] | None = None) -> dict:
    result = {}
    tone = None
    for item in preferences:
        attribute = item.get("property")
        requested = item.get("value")
        if attribute == "backgroundTone":
            if item.get("operator") == "avoid":
                requested = {"dark": "light", "light": "dark"}.get(requested)
            tone = (requested, item.get("evidence"))
        if item.get("operator") != "prefer":
            continue
        color_role = {"backgroundColor": "background", "textColor": "text"}.get(attribute)
        if color_role:
            result[color_role] = {"color": requested, "evidence": item.get("evidence")}
            if color_role == "background":
                roles = user_background_roles(requested)
                result[color_role]["panelColor"] = roles.get("componentSecondary")
    if tone and "background" not in result:
        name, evidence = tone
        config = load_theme_registry().get("userColorOverrides", {}).get("toneBackgrounds", {})
        selected = config.get(name)
        if not selected:
            raise ValueError("Missing configured tone background")
        result["background"] = {**selected, "tone": name, "evidence": evidence}
    if candidates is not None and "background" not in result:
        fallback = _palette_fallback(preferences, candidates)
        if fallback:
            result["background"] = fallback
    return result


def _palette_fallback(preferences: list[dict], candidates: list[dict]) -> dict:
    """融球不可用且没有同色渐变时，用登记融球基色继续交付，避免卡住。"""
    for item in preferences:
        if item.get("property") != "paletteFamily" or item.get("operator") != "prefer":
            continue
        family = item.get("value")
        if any(family in theme_palette_families(theme) for theme in candidates):
            return {}
        for theme in registered_themes("standard"):
            if theme.get("kind") != "fusion" or family not in theme_palette_families(theme):
                continue
            color = theme.get("background", {}).get("ballColors", {}).get("large")
            return {"color": color, "paletteFamily": family, "evidence": item.get("evidence"),
                    "panelColor": user_background_roles(color).get("componentSecondary")}
    return {}


def _background_colors(theme: dict, overrides: dict) -> list[str]:
    requested = overrides.get("background", {}).get("color")
    if requested:
        return [requested]
    background = theme.get("background", {})
    colors = list(background.get("colors", []))
    if background.get("color"):
        colors.append(background.get("color"))
    colors.extend(background.get("ballColors", {}).values())
    return colors


def preference_reason(theme: dict, preferences: list[dict], overrides: dict) -> str | None:
    kind = theme.get("kind")
    reason: str | None = None
    if overrides and kind not in {"solid", "gradient"}:
        reason = "用户结构化颜色偏好要求可验证的固定背景"
    for item in preferences:
        if reason:
            break
        attribute = item.get("property")
        requested = item.get("value")
        operation = item.get("operator")
        if attribute == "backgroundTone":
            continue  # 已由color_overrides落实；具体背景色优先。
        if attribute == "backgroundColor":
            if kind == "photo":
                reason = "图片没有可验证的背景色元数据"
                break
            actual = _background_colors(theme, overrides)
        elif attribute == "textColor":
            roles = theme.get("content", {}).get("roles", {})
            background = overrides.get("background", {}).get("color")
            if background:
                roles = user_background_roles(background)
            actual = [overrides.get("text", {}).get("color", roles.get("primary"))]
        elif attribute == "paletteFamily":
            actual = theme_palette_families(theme)
            fallback_family = overrides.get("background", {}).get("paletteFamily")
            if fallback_family:
                actual = [fallback_family]
        else:
            keys = {"backgroundKind": "kind", "paletteFamily": "family", "themeId": "id"}
            key = keys.get(attribute)
            actual = [theme.get(key)]
            if attribute == "backgroundKind" and overrides.get("background"):
                actual = ["solid"]
        matches = requested in actual
        rejected = not matches if operation == "prefer" else matches
        if rejected:
            reason = "不满足用户结构化主题偏好：" + str(attribute)
    return reason


def filter_preferences(
    candidates: list[dict], preferences: list[dict], overrides: dict,
) -> list[dict]:
    result = []
    for theme in candidates:
        if preference_reason(theme, preferences, overrides) is None:
            result.append(theme)
    return result


def palette_fusion_candidates(candidates: list[dict], preferences: list[dict]) -> list[dict]:
    """兼容融球仅凭已校验的肯定色系启用，业务文字与模型猜选ID均不触发。"""
    family = None
    for item in preferences:
        if item.get("property") == "paletteFamily" and item.get("operator") == "prefer":
            family = item.get("value")
            break
    result = []
    for theme in candidates:
        if theme.get("kind") != "fusion":
            continue
        if family in theme_palette_families(theme):
            result.append(theme)
    return result


def _fusion_requests(preferences: list[dict]) -> list[dict]:
    fusion_ids = set()
    for theme in load_theme_registry().get("themes", []):
        if theme.get("kind") == "fusion":
            fusion_ids.add(theme.get("id"))
    result = []
    for item in preferences:
        if item.get("operator") != "prefer":
            continue
        attribute, value = item.get("property"), item.get("value")
        if attribute == "backgroundKind" and value == "fusion":
            result.append(item)
        elif attribute == "themeId" and value in fusion_ids:
            result.append(item)
    return result


def filter_with_fusion_fallback(
    candidates: list[dict], preferences: list[dict], overrides: dict,
) -> list[dict]:
    """融球不可用时只放下融球肯定要求，普通背景仍须满足其它偏好。"""
    allowed = filter_preferences(candidates, preferences, overrides)
    if allowed:
        return allowed
    requests = _fusion_requests(preferences)
    if not requests:
        return []
    retained = [item for item in preferences if item not in requests]
    ordinary = [item for item in candidates if item.get("kind") in {"solid", "gradient"}]
    return filter_preferences(ordinary, retained, overrides)


def unmet_fusion_preferences(theme: dict, preferences: list[dict]) -> list[dict]:
    if theme.get("kind") == "fusion":
        return []
    return _fusion_requests(preferences)


def prioritize_candidates(
    candidates: list[dict], preferences: list[dict], family: str | None,
) -> list[dict]:
    color_preference = any(
        item.get("property") in {"backgroundColor", "paletteFamily", "themeId"}
        for item in preferences
    )
    result = []
    for theme in candidates:
        ordinary = theme.get("kind") in {"solid", "gradient"}
        if ordinary and family and not color_preference:
            if theme.get("family") != family:
                continue
        result.append(theme)
    palette_requested = any(
        item.get("property") == "paletteFamily" and item.get("operator") == "prefer"
        for item in preferences
    )
    if palette_requested:
        presets = [item for item in result if item.get("kind") in {"fusion", "gradient"}]
        if presets:
            result = presets
    photos = [item for item in result if item.get("kind") == "photo"]
    subjects = [item for item in photos if item.get("pool") != "texturePhotos"]
    if subjects:
        photos = subjects
    if photos:
        priority = max(item.get("selectionPriority", 0) for item in photos)
        return [item for item in photos if item.get("selectionPriority", 0) == priority]
    balls = [item for item in result if item.get("kind") == "fusion"]
    return balls or result
