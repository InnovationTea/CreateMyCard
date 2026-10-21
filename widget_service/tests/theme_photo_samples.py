"""仅供测试的构图，不向运行注册表添加已删除的图片。"""

from services.post_layout_theme_registry import registered_themes


def protected_photo():
    photo = next(item for item in registered_themes("photos")
                 if item.get("id") == "photo-ux-clouds-weather-square")
    photo["id"] = "test-protected-weather"
    photo.pop("contentEligibility", None)
    return photo


def expansion_photo():
    photo = next(item for item in registered_themes("photos")
                 if item.get("id") == "photo-ux-sport-center-wide")
    photo.update(id="test-square-expansion", pool="squareExpansions", sourceSize="2x2",
                 composition="square-left", business="countdown", subjectless=False,
                 subjectBounds=[0.6, 0.1, 0.3, 0.8])
    photo.pop("contentEligibility", None)
    photo.pop("subjectlessLayout", None)
    panels = photo.get("content", {}).get("panelBySize", {})
    panel = panels.get("2x4")
    assert panel is not None
    panels["2x2"] = panel
    return photo
