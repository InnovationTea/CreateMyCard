"""图片兜底不能与普通融球主题混淆，也不能靠标识绕过画廊验收。"""

from __future__ import annotations

import copy

import pytest

from services.template_generation.test_support import gallery_background as background
from services.theme_photo_processing import apply_photo_fallback, photo_background


@pytest.fixture(autouse=True)
def version_gate(monkeypatch):
    monkeypatch.setattr(background, "fusion_ball_enabled", lambda version: version == "high")


def _photo_messages(color: str, version: str, size: str) -> list[dict]:
    theme = None
    for item in background.registered_themes():
        if item.get("kind") != "photo" or size not in item.get("sizes", []):
            continue
        if item.get("content", {}).get("roles", {}).get("primary") == color:
            theme = item
            break
    assert theme is not None
    root = {"id": "root", "component": "Stack", "children": [
        "__post_theme_background", "template_root",
    ], "styles": {}}
    layers = photo_background(theme)
    image = next(node for node in layers if node.get("component") == "Image")
    image["src"] = theme.get("remoteUrl") or theme.get("src")
    apply_photo_fallback(root, {}, layers, {"size": size}, color, enabled=version == "high")
    return [{"updateComponents": {"components": [
        root, {"id": "template_root", "component": "Column"}, *layers,
    ]}}]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("version", ["high", "low"])
@pytest.mark.parametrize("color", ["#FF000000", "#FFFFFFFF"])
@pytest.mark.parametrize("legacy_expected", [False, True])
def test_photo_uses_registered_fallback_instead_of_legacy_expectation(
    size, version, color, legacy_expected,
):
    messages = _photo_messages(color, version, size)
    original = copy.deepcopy(messages)
    result = background.check_gallery_background(
        messages, expected_fusion=legacy_expected, app_version=version,
    )
    assert result.error == ""
    assert result.kind == "photo"
    assert result.fusion_rendered is (color == "#FFFFFFFF" and version == "high")
    assert messages == original


@pytest.mark.parametrize("damage", [
    "missing_image", "unregistered", "not_full", "wrong_order", "missing_fusion",
    "wrong_base", "missing_gradient", "photo_on_top", "low_version_fusion",
])
def test_invalid_photo_background_is_rejected(damage):
    color = "#FF000000" if damage == "missing_gradient" else "#FFFFFFFF"
    messages = _photo_messages(color, "high", "2x2")
    update = messages[0].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    by_id = {node.get("id"): node for node in nodes}
    image = by_id.get("__post_theme_base")
    layer = by_id.get("__post_theme_background")
    root = by_id.get("root")
    assert image is not None and layer is not None and root is not None
    version = "high"
    if damage == "missing_image":
        nodes.remove(image)
    elif damage == "unregistered":
        image["src"] = "unregistered-background"
    elif damage == "not_full":
        image["styles"] = {"width": 20, "height": 20}
    elif damage == "wrong_order":
        layer["children"] = ["__post_theme_base", "fusionBallBackground"]
    elif damage == "missing_fusion":
        nodes[:] = [node for node in nodes if node.get("id") != "fusionBallBackground"]
    elif damage == "wrong_base":
        root["styles"] = {"backgroundColor": "#FFFFFFFF"}
    elif damage == "missing_gradient":
        root["styles"] = {"backgroundColor": "#FFE6E6E6"}
    elif damage == "photo_on_top":
        root["children"] = ["template_root", "__post_theme_background"]
    else:
        version = "low"
    result = background.check_gallery_background(
        messages, expected_fusion=True, app_version=version,
    )
    assert result.error


@pytest.mark.parametrize("expected,present,version,valid", [
    (False, False, "high", True), (True, True, "high", True),
    (True, False, "high", False), (False, True, "high", False),
    (True, True, "low", False),
])
def test_ordinary_background_keeps_fusion_contract(expected, present, version, valid):
    nodes = [{"id": "fusionBallBackground", "component": "Stack"}] if present else []
    result = background.check_gallery_background(
        [{"updateComponents": {"components": nodes}}],
        expected_fusion=expected, app_version=version,
    )
    assert (result.error == "") is valid
