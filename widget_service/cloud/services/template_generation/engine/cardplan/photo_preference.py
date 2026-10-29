"""模板预选保留既有偏好判断，不依赖 Fusion 的偏好解析接口。"""

import re

from services.post_layout_theme_registry import load_theme_registry


def _has_explicit_color(query: str) -> bool:
    """保留原字符串接口的命中语义；模板预选仅需要颜色要求是否存在。"""
    names = load_theme_registry().get("userColorOverrides", {}).get("namedColors", {})
    token = "(?:#[0-9A-Fa-f]{8}|#[0-9A-Fa-f]{6}|" + "|".join(names) + ")"
    for target in ("文字|字体|字色|字", "背景|底色"):
        pattern = rf"(?:{target})\s*(?:用|是|为|改成|改为|使用|要|：|:)?\s*({token})"
        reverse = rf"({token})\s*(?:的)?(?:{target})"
        if re.search(pattern, query) or re.search(reverse, query):
            return True
    return False


def photo_preference_reason(query: str) -> str | None:
    reason: str | None = None
    if re.search(r"纯色|渐变|[融绒]球|不要.*(?:图|背景)|不用.*(?:图|背景)|无(?:背景)?图", query):
        reason = "用户明确其它主题或不要图片"
    elif _has_explicit_color(query):
        reason = "用户明确颜色优先，本轮使用固定底色/渐变"
    return reason
