"""图片加载兜底仅增加背景层，不改变图片匹配、前景和普通主题。"""

import copy

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.card_validator import validate_card
from services.square_photo_expansion import expand_square
from services.theme_style_roles import role
from theme_photo_samples import expansion_photo


def photo_theme(size):
    return next(item for item in registry.registered_themes("photos")
                if item.get("size") == size)


def source():
    nodes = [
        {"id": "root", "component": "Column", "children": ["primary", "panel"],
         "styles": {"width": "matchParent", "height": "matchParent", "padding": 12,
                    "borderRadius": 20, "clip": True}},
        {"id": "primary", "component": "Text", "content": "主信息",
         "styles": {"fontColor": role("primary"), "fontSize": 18}},
        {"id": "panel", "component": "Column", "children": ["secondary", "tertiary"],
         "styles": {"backgroundColor": role("panel")}},
        {"id": "secondary", "component": "Text", "content": "辅助信息",
         "styles": {"fontColor": role("secondary"), "fontSize": 12}},
        {"id": "tertiary", "component": "Text", "content": "次要信息",
         "styles": {"fontColor": role("tertiary"), "fontSize": 12}},
    ]
    return themes.encode([
        {"version": "v0.9", "createSurface": {
            "surfaceId": "surface_card", "catalogId": "ohos.a2ui.extended.catalog.form"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "surface_card", "root": "root", "components": nodes}},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "surface_card", "path": "/", "value": {"data": {}}}},
    ])


def node_by_id(result, identity):
    return next(node for node in themes.components(themes.decode(result))
                if node.get("id") == identity)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("rgb", ["000000", "FFFFFF"])
@pytest.mark.parametrize("explicit", [False, True])
def test_black_and_white_text_share_opacity_levels(monkeypatch, size, rgb, explicit):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    theme = photo_theme(size)
    expected = {"primary": "#FF" + rgb, "secondary": "#CC" + rgb, "tertiary": "#99" + rgb}
    overrides = {}
    if explicit:
        overrides = {"text": {"color": "#FF" + rgb}}
    else:
        theme.get("content", {}).get("roles", {}).update(expected)
    original = source()
    result = themes.apply_theme(original, theme, {"size": size}, overrides)
    for identity, color in expected.items():
        assert node_by_id(result, identity).get("styles", {}).get("fontColor") == color
    panel = theme.get("content", {}).get("panelBySize", {}).get(size)
    assert node_by_id(result, "panel").get("styles", {}).get("backgroundColor") == panel
    assert themes.foreground_signature(result) == themes.foreground_signature(original)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion_enabled", [False, True])
@pytest.mark.parametrize("color", ["#FF000000", "#CC000000"])
def test_black_text_uses_original_white_gradient(monkeypatch, size, fusion_enabled, color):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: fusion_enabled)
    result = themes.apply_theme(source(), photo_theme(size), {"size": size},
                                {"text": {"color": color}})
    styles = node_by_id(result, "root").get("styles", {})
    assert styles.get("backgroundColor") == "#FFE6E6E6"
    assert styles.get("linearGradient") == {
        "direction": "LeftBottom", "colors": [["#FFFFFFFF", 0], ["#FFE6E6E6", 1]],
    }
    assert styles.get("width") == styles.get("height") == "matchParent"
    assert "fusionBall" not in result
    assert node_by_id(result, themes.PREFIX + "base").get("src") == photo_theme(size).get("src")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion_enabled", [False, True])
def test_white_text_uses_existing_blue_fusion_without_changing_foreground(
    monkeypatch, size, fusion_enabled,
):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: fusion_enabled)
    result = themes.apply_theme(source(), photo_theme(size), {"size": size}, {})
    root = node_by_id(result, "root")
    assert root.get("styles", {}).get("backgroundColor") == "#FF1F1F99"
    background = node_by_id(result, themes.PREFIX + "background")
    if fusion_enabled:
        assert root.get("children") == [themes.PREFIX + "background", themes.FUSION_FOREGROUND_ID]
        assert background.get("children") == ["fusionBallBackground", themes.PREFIX + "base"]
        blue = next(item for item in registry.registered_themes("standard")
                    if item.get("id") == "fusion-ball-schedule-blue")
        for node in themes.fusion_background(blue, {"size": size}):
            assert node_by_id(result, node.get("id")) == node
    else:
        assert root.get("children")[-1] == themes.PREFIX + "foreground"
        assert background.get("children") == [themes.PREFIX + "base"]
        assert "fusionBall" not in result
    assert themes.foreground_signature(source()) == themes.foreground_signature(result)


@pytest.mark.parametrize(
    "theme",
    registry.registered_themes("photos", include_disabled=True)
    + registry.registered_themes("texturePhotos", include_disabled=True),
    ids=lambda theme: theme.get("id"),
)
@pytest.mark.parametrize("fusion_enabled", [False, True])
def test_every_photo_has_one_image_and_keeps_fallback_and_foreground(
    monkeypatch, theme, fusion_enabled,
):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: fusion_enabled)
    original = source()
    original_theme = copy.deepcopy(theme)
    result = themes.apply_theme(original, theme, {"size": theme.get("size")}, {})
    nodes = themes.components(themes.decode(result))
    layers = themes.photo_background(theme)
    assert len(layers) == 2
    images = [node for node in nodes if node.get("component") == "Image"]
    assert len(images) == 1
    assert images[0].get("id") == themes.PREFIX + "base"
    assert images[0].get("src") == theme.get("src")
    assert images[0].get("styles") == {
        "width": "matchParent", "height": "matchParent", "objectFit": "fill",
    }
    retired = {themes.PREFIX + name for name in ("slot", "imageBox", "image")}
    assert not retired.intersection(node.get("id") for node in nodes)
    for node in nodes:
        assert not retired.intersection(node.get("children", []))
    primary = theme.get("content", {}).get("roles", {}).get("primary")
    styles = node_by_id(result, "root").get("styles", {})
    if primary == "#FF000000":
        assert styles.get("backgroundColor") == "#FFE6E6E6"
        assert styles.get("linearGradient", {}).get("colors") == [
            ["#FFFFFFFF", 0], ["#FFE6E6E6", 1],
        ]
        assert "fusionBall" not in result
    else:
        assert styles.get("backgroundColor") == "#FF1F1F99"
        assert "linearGradient" not in styles
        assert ("fusionBallBackground" in result) is fusion_enabled
    assert "#FF8FADCC" not in result
    assert themes.foreground_signature(result) == themes.foreground_signature(original)
    assert theme == original_theme


@pytest.mark.parametrize("rgb", ["000000", "FFFFFF"])
@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_photo_with_fallback_passes_protocol_validation(monkeypatch, rgb, size):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    theme = photo_theme(size)
    result = themes.apply_theme(source(), theme, {"size": size},
                                {"text": {"color": "#FF" + rgb}})
    card = {"title": "图片兜底", "description": "背景加载测试", "suggestSize": size}
    report = validate_card(result, card, allowed_asset_sources={theme.get("src")})
    assert not report.errors, report.errors


def test_expansion_keeps_background_and_correct_foreground_reference(monkeypatch):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    theme = expansion_photo()
    result = expand_square(source(), theme, {"size": "2x2"})
    half = node_by_id(result, themes.PREFIX + "contentHalf")
    assert half.get("children") == [themes.FUSION_FOREGROUND_ID]
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF1F1F99"
    assert node_by_id(result, "fusionBallBackground")
    assert themes.foreground_signature(result) == themes.foreground_signature(source())


def test_explicit_background_bypasses_photo_and_its_fallback(monkeypatch):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    result = themes.apply_theme(source(), photo_theme("2x2"), {"size": "2x2"},
                                {"background": {"color": "#FFFFFFFF"}})
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FFFFFFFF"
    assert "fusionBall" not in result
    assert themes.PREFIX + "background" not in result


@pytest.mark.parametrize("replacement", [
    None,
    {},
    {"color": "#008FADCC"},
    {"color": "#CC8FADCC"},
    {"color": "#8FADCC"},
    {"color": "invalid"},
    {"color": "#FF8FADCC", "lightText": {"themeId": "fusion-ball-schedule-blue"}},
    {"darkText": {"colors": ["#00FFFFFF", "#FFE6E6E6"], "direction": "LeftBottom"},
     "lightText": {"themeId": "fusion-ball-schedule-blue"}},
    {"darkText": {"colors": ["#FFFFFFFF", "#FFE6E6E6"], "direction": "wrong"},
     "lightText": {"themeId": "fusion-ball-schedule-blue"}},
    {"darkText": {"colors": ["#FFFFFFFF", "#FFE6E6E6"], "direction": "LeftBottom"},
     "lightText": {"themeId": "gradient-blue"}},
    {"darkText": {"colors": ["#FFFFFFFF", "#FFE6E6E6"], "direction": "LeftBottom"},
     "lightText": {"themeId": "missing"}},
])
def test_invalid_fallback_config_is_rejected(replacement):
    config = registry.load_theme_registry()
    config["photoFallbacks"] = copy.deepcopy(replacement)
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("change", ["disabled", "transparent"])
def test_blue_fallback_must_be_enabled_and_opaque(change):
    config = registry.load_theme_registry()
    blue = next(item for item in config.get("themes", [])
                if item.get("id") == "fusion-ball-schedule-blue")
    if change == "disabled":
        blue["enabled"] = False
    else:
        blue.get("background", {}).get("ballColors", {})["large"] = "#001F1F99"
    with pytest.raises(ValueError, match="Photo fallback"):
        registry.validate_registry(config)


def test_missing_fusion_fallback_is_not_silently_ignored(monkeypatch):
    config = registry.load_theme_registry()
    config["themes"] = []
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    with pytest.raises(ValueError, match="Missing photo fallback"):
        registry.photo_fallback("#FFFFFFFF")


@pytest.mark.parametrize("color,kind", [
    ("#FFFFFFFF", "fusion"), ("#CCFFFFFF", "fusion"), ("#99FFFFFF", "fusion"),
    ("#FF000000", "gradient"), ("#CC000000", "gradient"), ("#99000000", "gradient"),
    ("#FFEEEEEE", "fusion"), ("#FF111111", "gradient"),
])
def test_fallback_follows_final_text_brightness_and_opacity(color, kind):
    assert registry.photo_fallback(color).get("kind") == kind


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("version,expected", [
    (None, False), ("invalid", False), ("11.7.5.205", False),
    ("11.7.5.206", True), ("99.0.0", True),
])
def test_photo_fallback_respects_actual_version_gate(monkeypatch, size, version, expected):
    monkeypatch.setattr(get_settings(), "CONFIG", {"fusion_ball_min_prd_version": "11.7.5.206"})
    result = themes.apply_theme(source(), photo_theme(size),
                                {"size": size, "appVersion": version}, {})
    assert ("fusionBallBackground" in result) is expected
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF1F1F99"
    assert themes.foreground_signature(result) == themes.foreground_signature(source())
