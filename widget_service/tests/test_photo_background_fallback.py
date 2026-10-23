"""图片加载兜底仅增加背景层，不改变图片匹配、前景和普通主题。"""

import copy

import pytest

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
@pytest.mark.parametrize("color", ["#FF000000", "#FFFFFFFF", "#CC000000", "#FFFF0000"])
def test_all_text_colors_use_one_opaque_solid_fallback(monkeypatch, size, fusion_enabled, color):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: fusion_enabled)
    result = themes.apply_theme(source(), photo_theme(size), {"size": size},
                                {"text": {"color": color}})
    styles = node_by_id(result, "root").get("styles", {})
    assert styles.get("backgroundColor") == "#FF8FADCC"
    assert "linearGradient" not in styles
    assert styles.get("width") == styles.get("height") == "matchParent"
    assert "fusionBall" not in result
    assert node_by_id(result, themes.PREFIX + "base").get("src") == photo_theme(size).get("src")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion_enabled", [False, True])
def test_photo_fallback_never_adds_fusion_layers_or_changes_foreground(
    monkeypatch, size, fusion_enabled,
):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: fusion_enabled)
    result = themes.apply_theme(source(), photo_theme(size), {"size": size}, {})
    root = node_by_id(result, "root")
    assert root.get("styles", {}).get("backgroundColor") == "#FF8FADCC"
    background = node_by_id(result, themes.PREFIX + "background")
    assert root.get("children") == [themes.PREFIX + "background", themes.PREFIX + "foreground"]
    assert background.get("children") == [themes.PREFIX + "base", themes.PREFIX + "slot"]
    assert "fusionBall" not in result
    assert themes.foreground_signature(source()) == themes.foreground_signature(result)


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
    assert half.get("children") == [themes.PREFIX + "foreground"]
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF8FADCC"
    assert "fusionBall" not in result
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
])
def test_invalid_fallback_config_is_rejected(replacement):
    config = registry.load_theme_registry()
    config["photoFallbacks"] = copy.deepcopy(replacement)
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_solid_photo_fallback_does_not_depend_on_a_fusion_theme(monkeypatch):
    config = registry.load_theme_registry()
    config["themes"] = []
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    assert registry.photo_fallback() == {"color": "#FF8FADCC"}
