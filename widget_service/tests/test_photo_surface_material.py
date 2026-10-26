"""图片背板模糊只改变已存在的绘制材质，不影响布局和非图片主题。"""

import copy

import pytest

from photo_samples.common import expanded
from photo_samples.music import earphone_sample
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_style_roles import role
from test_autumn_calendar_photos import calendar_sample
from test_photo_background_fallback import node_by_id, photo_theme, source


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("rgb", ["000000", "FFFFFF"])
def test_panel_material_preserves_paint_geometry_and_fallback(monkeypatch, size, rgb):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    original = source()
    result = themes.apply_theme(original, photo_theme(size), {"size": size},
                                {"text": {"color": "#FF" + rgb}})
    panel = node_by_id(result, "panel")
    assert panel.get("styles", {}).get("backdropBlur") == {"radius": 20}
    expected = photo_theme(size).get("content", {}).get("panelBySize", {}).get(size)
    assert panel.get("styles", {}).get("backgroundColor") == expected
    assert themes.foreground_signature(original) == themes.foreground_signature(result)
    for node in themes.components(themes.decode(result)):
        radius = node.get("styles", {}).get("backdropBlur")
        if node.get("id") == "panel":
            assert radius == {"radius": 20}
        elif node.get("id") == "fusionBallGlassLayer":
            assert radius == {"radius": 210}
        else:
            assert radius is None
    # Removing failed image layers cannot remove the material from the foreground.
    records = themes.decode(result)
    for node in themes.components(records):
        if node.get("component") == "Image":
            node["src"] = "resources/base/media/missing.jpg"
    assert node_by_id(themes.encode(records), "panel") == panel


@pytest.mark.parametrize("button", ["PillButton", "CircleButton"])
def test_actual_button_expansion_receives_material(button):
    layout = "S-title-anchor" if button == "CircleButton" else "S-title-content-action"
    sample = calendar_sample(layout, button)
    result = themes.apply_theme(sample.source, photo_theme("2x2"), sample.task, {})
    action = node_by_id(result, "action")
    assert action.get("styles", {}).get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)


def test_native_button_without_icon_receives_material():
    original = earphone_sample()
    rows = themes.decode(original.compact)
    button = next(row for row in rows if row[0] == "cta")
    props = button[2]
    props.pop("icon", None)
    sample = expanded(rows, original.task)
    result = themes.apply_theme(sample.source, photo_theme("2x2"), sample.task, {})
    node = node_by_id(result, "cta")
    assert node.get("component") == "Button"
    assert node.get("onClick") == props.get("onClick")
    assert node.get("styles", {}).get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)


def test_actual_wide_infoblock_and_cardbutton_surfaces():
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["main", "upper", "lower"]],
        ["main", "Region", {"variant": "title-content"}, ["header", "reading"]],
        ["header", "SingleLineTitle", {"title": "睡眠"}],
        ["reading", "EmphasisText", {"mainText": "7小时1分"}],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "82", "secondaryText": "分"}],
        ["lower", "CardButton", {"label": "设置闹钟",
         "icon": "resources/base/media/alarm_fill_1.svg", "onClick": [
            {"call": "clickToDeeplink", "args": {"intentName": "Clock", "uri": "",
                                                 "bundleName": "", "abilityName": ""}},
        ]}],
    ]
    sample = expanded(rows, {"size": "2x4", "appVersion": "99.0.0"})
    result = themes.apply_theme(sample.source, photo_theme("2x4"), sample.task, {})
    for identity in ("upper", "lower"):
        assert node_by_id(result, identity).get("styles", {}).get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)


@pytest.mark.parametrize("kind,color,click,expected", [
    ("Column", role("panel"), False, True),
    ("Row", role("panel", 0), True, False),
    ("Stack", role("componentSecondary"), True, True),
    ("Stack", role("componentSecondary"), False, False),
    ("Column", role("graphicPrimary"), False, False),
    ("Image", role("panel"), True, False),
    ("Text", role("panel"), True, False),
    ("Divider", role("panel"), False, False),
    ("Button", "#00000000", True, False),
    ("Button", None, True, False),
    ("Stack", "#33FFFFFF", False, False),
    ("Button", "#33FFFFFF", True, True),
])
def test_semantic_surfaces_not_arbitrary_color_nodes(kind, color, click, expected):
    records = themes.decode(source())
    panel = next(node for node in themes.components(records) if node.get("id") == "panel")
    panel.update(component=kind)
    panel.get("styles", {})["backgroundColor"] = color
    if click:
        panel["onClick"] = [{"call": "clickToDeeplink", "args": {"intentName": "Music"}}]
    if color is None:
        panel.get("styles", {}).pop("backgroundColor")
    result = themes.apply_theme(themes.encode(records), photo_theme("2x2"), {"size": "2x2"}, {})
    actual = node_by_id(result, "panel").get("styles", {}).get("backdropBlur")
    assert actual == ({"radius": 20} if expected else None)


@pytest.mark.parametrize("theme", registry.registered_themes("standard"), ids=lambda t: t.get("id"))
def test_non_photo_themes_do_not_receive_surface_material(monkeypatch, theme):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    result = themes.apply_theme(source(), theme, {"size": "2x2"}, {})
    assert "backdropBlur" not in node_by_id(result, "panel").get("styles", {})


def test_explicit_background_does_not_receive_photo_material():
    result = themes.apply_theme(source(), photo_theme("2x2"), {"size": "2x2"},
                                {"background": {"color": "#FFFFFFFF"}})
    assert "backdropBlur" not in node_by_id(result, "panel").get("styles", {})


def test_material_comes_from_shared_registry_without_mutation(monkeypatch):
    config = registry.load_theme_registry()
    config["photoSurfaceStyle"] = {"backdropBlur": {"radius": 12}}
    registry.validate_registry(config)
    monkeypatch.setattr(themes, "load_theme_registry", lambda: copy.deepcopy(config))
    result = themes.apply_theme(source(), photo_theme("2x2"), {"size": "2x2"}, {})
    assert node_by_id(result, "panel").get("styles", {}).get("backdropBlur") == {"radius": 12}
    material = registry.load_theme_registry().get("photoSurfaceStyle")
    assert material == {"backdropBlur": {"radius": 20}}


@pytest.mark.parametrize("material", [None, {}, {"backdropBlur": {}},
                                      {"backdropBlur": {"radius": -1}},
                                      {"backdropBlur": {"radius": "20"}},
                                      {"backdropBlur": {"radius": float("nan")}},
                                      {"backdropBlur": {"radius": 20}, "padding": 10}])
def test_material_schema_rejects_invalid_or_geometric_settings(material):
    config = registry.load_theme_registry()
    config["photoSurfaceStyle"] = material
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_signature_still_detects_foreground_geometry_changes():
    original = source()
    records = themes.decode(original)
    panel = next(node for node in themes.components(records) if node.get("id") == "panel")
    panel.get("styles", {})["padding"] = 100
    changed = themes.encode(records)
    assert themes.foreground_signature(original) != themes.foreground_signature(changed)
