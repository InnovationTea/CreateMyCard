"""模板预选尊重显式主题要求，复用共享颜色偏好解析。"""

import re

from services.post_layout_theme import user_color_overrides


def photo_preference_reason(query: str) -> str | None:
    reason: str | None = None
    if re.search(r"纯色|渐变|[融绒]球|不要.*(?:图|背景)|不用.*(?:图|背景)|无(?:背景)?图", query):
        reason = "用户明确其它主题或不要图片"
    elif user_color_overrides(query):
        reason = "用户明确颜色优先，本轮使用固定底色/渐变"
    return reason
