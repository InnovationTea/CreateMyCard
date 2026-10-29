"""模板准入兼容入口；所有规则裁决委托公共图片算法。"""

from services.theme_photo_matching import photo_reason

from .photo_facts import template_photo_facts


def template_photo_reason(photo: dict, source: str, size: str, title: str | None) -> str | None:
    return photo_reason(photo, template_photo_facts(source, {"size": size}, title))
