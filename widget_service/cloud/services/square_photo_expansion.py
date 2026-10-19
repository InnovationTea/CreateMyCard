"""只在最终输出边界扩宽画布，原 2x2 前景不参与重排。"""

from __future__ import annotations

import copy
import re
import unicodedata

from config.config import get_settings
from services.post_layout_theme_registry import registered_themes

SLEEP_FIELDS = {
    "sleepScore", "sleepStatus", "sleepTypeDesc", "nightSleepDurationText",
    "deepSleepDurationText", "totalNapDurationText", "fallAsleepTimeText", "wakeupTimeText",
}


def expansion_business(task: dict) -> str | None:
    data = task.get("dataModelSchema", {}).get("data", {})
    if not isinstance(data, dict) or not data:
        return None
    roots = set(data)
    if "countdown" in roots and roots <= {"countdown", "calendar"}:
        return "countdown"
    if roots == {"healthSport"} and isinstance(data["healthSport"], dict):
        fields = set(data["healthSport"])
        if fields & SLEEP_FIELDS and fields <= SLEEP_FIELDS | {"targetDateText", "updatedAt"}:
            return "sleep"
    if roots == {"earphone"} and any(
        isinstance(event, dict) and str(event.get("id", "")).startswith("event.open.music.")
        for event in task.get("eventCandidates", [])
    ):
        return "music"
    return None


def expansion_gate(task: dict) -> dict:
    settings = get_settings()
    business = expansion_business(task)
    query = " ".join(unicodedata.normalize("NFKC", str(task.get("userQuery", ""))).lower().split())
    reason = None
    if not settings.enable_photo_background_theme:
        reason = "图片开关未开启"
    elif not (settings.enable_square_photo_expansion or (
        settings.enable_square_music_photo_expansion and business == "music"
    )):
        reason = "扩展开关未开启"
    elif task.get("size") != "2x2" or business is None:
        reason = "源尺寸或单业务条件不满足"
    elif not query:
        reason = "缺少稳定请求文本"
    elif re.search(
        r"2\s*[x×*]\s*2|二乘二|不(?:要)?扩|不要变大|(?:保持|保留|固定)(?:原)?尺寸", query
    ):
        reason = "用户要求保留原尺寸"
    elif re.search(r"纯色|渐变|融球|不要(?:背景)?图|不用(?:背景)?图|无(?:背景)?图", query):
        reason = "用户明确其它主题或不要图片"
    elif not any(theme.get("business") == business
                 for theme in registered_themes("squareExpansions")):
        reason = "没有启用的对应业务扩展图片"
    return {"eligible": reason is None, "reason": reason, "business": business}


def expansion_enabled(task: dict) -> bool:
    return expansion_gate(task)["eligible"]


def expansion_reason(theme: dict, task: dict, evidence: dict) -> str | None:
    gate = expansion_gate(task)
    if not gate["eligible"]:
        return gate["reason"]
    if theme.get("business") != gate["business"]:
        return "扩展图片业务不匹配"
    if theme.get("sourceSize") != "2x2" or theme.get("size") != "2x4":
        return "扩展预置尺寸不支持"
    if theme.get("composition") != "square-left" or theme.get("objectFit") != "fill":
        return "扩展构图或自适应方式不支持"
    if theme.get("frame") != {"slotWidth": 1, "slotHeight": 1, "imageWidth": 1,
                              "imageHeight": 1, "align": "topStart"}:
        return "扩展背景必须使用完整预置构图"
    return "真实卡片宽高未知，缺少扩展主体避让的尺寸无关依据"


def _expansion_geometry_reason(theme: dict, evidence: dict) -> str | None:
    """开发诊断中的归一化边界检查，不作为云侧准入依据。"""
    from services.post_layout_theme import valid_rect

    if not evidence.get("complete") or evidence.get("unsafe"):
        return "原2x2前景测量不完整或已有溢出"
    occupied = evidence.get("occupied", [])
    if not occupied:
        return "没有可验证的前景内容"
    bounds = theme.get("subjectBounds")
    if not valid_rect(bounds):
        return "图片主体侵入左侧内容半区"
    bx, by, bw, bh = bounds
    outside_right_half = bx < 0.5 or bx + bw > 1
    outside_height = by < 0 or by + bh > 1
    if outside_right_half or outside_height:
        return "图片主体侵入左侧内容半区"
    for item in occupied:
        if not isinstance(item, dict):
            return "前景占用范围无效"
        rect = item.get("rect")
        if not valid_rect(rect):
            return "前景占用范围无效"
        x, y, width, height = rect
        outside_horizontal = x < 0 or x + width > 1
        outside_vertical = y < 0 or y + height > 1
        if outside_horizontal or outside_vertical:
            return "原内容及动态预留超出2x2安全范围"
    return None


def expand_square(source: str, theme: dict, task: dict) -> str:
    from services.post_layout_theme import (
        PREFIX,
        apply_theme,
        components,
        decode,
        encode,
        foreground_signature,
    )

    records = decode(apply_theme(source, theme, task, {}))
    nodes = components(records)
    shell = next(node for node in nodes if node.get("id") == "root")
    foreground_id = shell.get("children", [])[-1]
    shell["children"] = [PREFIX + "background", PREFIX + "contentHalf"]
    nodes.append({
        "id": PREFIX + "contentHalf",
        "component": "Stack",
        "children": [foreground_id],
        "styles": {"width": "50%", "height": "matchParent", "alignContent": "topStart"},
    })
    result = encode(records)
    if foreground_signature(source) != foreground_signature(result):
        raise ValueError("Expansion changed original foreground, bindings or actions")
    return result


def same_square_geometry(before: dict, after: dict) -> bool:
    from services.post_layout_theme import same_visible_geometry, valid_rect

    if before.get("unsafe") or after.get("unsafe"):
        return False
    before_views, after_views = before.get("responsive", []), after.get("responsive", [])
    if len(before_views) != len(after_views):
        return False
    for first, second in zip(before_views, after_views, strict=True):
        if not same_square_geometry(first, second):
            return False
    original = {key: value for key, value in before.items() if key != "responsive"}
    normalized = copy.deepcopy(after)
    normalized.pop("responsive", None)
    for key in ("visible", "occupied"):
        items = normalized.get(key, [])
        if not items:
            return False
        for item in items:
            rect = item.get("rect")
            if not valid_rect(rect):
                return False
            rect[0] *= 2
            rect[2] *= 2
        if key == "occupied":
            left, right = before.get(key, []), items
            if len(left) != len(right):
                return False
            for first, second in zip(left, right, strict=True):
                if first.get("id") != second.get("id"):
                    return False
                old_rect = first.get("rect")
                if not valid_rect(old_rect):
                    return False
                if any(
                    abs(a - b) > 0.001
                    for a, b in zip(old_rect, second.get("rect"), strict=True)
                ):
                    return False
    return same_visible_geometry(original, normalized)
