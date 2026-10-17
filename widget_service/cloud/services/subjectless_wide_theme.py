"""原生宽卡无主体背景准入；不参与布局和尺寸扩展。"""

import re
import unicodedata

from config.config import get_settings
from services.post_layout_theme_registry import registered_themes
from services.square_photo_expansion import SLEEP_FIELDS


def matching_businesses(task: dict) -> set[str]:
    data = task.get("dataModelSchema", {}).get("data", {})
    if not isinstance(data, dict):
        return set()
    businesses = set()
    for root, business in {
        "weather": "weather", "phoneBattery": "battery",
    }.items():
        if isinstance(data.get(root), dict) and data.get(root):
            businesses.add(business)
    health = data.get("healthSport", {})
    if isinstance(health, dict) and SLEEP_FIELDS.intersection(health):
        businesses.add("sleep")
    if re.search(r"预警|警报|台风|暴雨|暴雪|雷暴", task.get("userQuery", "")):
        businesses.discard("weather")
    return businesses


def wide_gate(task: dict) -> dict:
    settings = get_settings()
    query = " ".join(unicodedata.normalize("NFKC", task.get("userQuery", "")).lower().split())
    businesses = sorted(matching_businesses(task))
    reason = None
    enabled = settings.enable_subjectless_wide_theme and settings.enable_photo_background_theme
    if not enabled:
        reason = "无主体宽卡背景未启用"
    elif task.get("size") != "2x4":
        reason = "仅原生2x4，不参与2x2扩展"
    elif not businesses:
        reason = "没有匹配业务"
    elif re.search(r"纯色|渐变|融球|不要.*(?:图|背景)|不用.*(?:图|背景)|无图", query):
        reason = "用户要求优先，不使用图片背景"
    elif not registered_themes("subjectlessWidePhotos"):
        reason = "没有启用的无主体宽卡图片"
    return {"eligible": reason is None, "reason": reason, "businesses": businesses}


def background_reason(photo: dict, task: dict, evidence: dict, gate: dict) -> str | None:
    if not gate.get("eligible"):
        return gate.get("reason") or "未通过准入"
    if task.get("size") != "2x4" or photo.get("size") != "2x4":
        return "仅原生2x4"
    if photo.get("business") not in gate.get("businesses", []):
        return "业务不匹配"
    if photo.get("composition") != "subjectless" or photo.get("objectFit") != "fill":
        return "无主体背景必须自适应铺满"
    frame = photo.get("frame", {})
    dimensions = ("slotWidth", "slotHeight", "imageWidth", "imageHeight")
    if any(frame.get(key, 1) != 1 for key in dimensions):
        return "不允许运行态裁切或定位"
    if not evidence.get("complete"):
        return "布局测量未完成"
    return None
