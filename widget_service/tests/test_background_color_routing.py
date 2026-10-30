"""模型展开的普通色值须复用预设；不在执行代码中重新理解中文词句。"""

import copy

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_user_preferences as preferences
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import PATHS, choose, sample
from theme_preference_samples import preference, reply


@pytest.mark.parametrize("color,family,expected", [
    ("#4CAF50", "green", "fusion-ball-battery-teal"),
    ("#FF0000", "red", "fusion-ball-sport-orange"),
    ("#FF8800", "orange", "fusion-ball-sport-orange"),
    ("#FFFF00", "yellow", "gradient-warm"),
    ("#00FFFF", "cyan", "fusion-ball-battery-teal"),
    ("#0000FF", "blue", "fusion-ball-schedule-blue"),
    ("#8000FF", "purple", "fusion-ball-sleep-violet"),
])
def test_model_generated_color_routes_to_registered_family(monkeypatch, color, family, expected):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "按我要求的色调配色"
    items = [preference("backgroundColor", color, "要求的色调")]
    before = copy.deepcopy(saved)
    result, audit = choose(saved, monkeypatch, reply(items, "solid-blue"))
    assert audit.get("themeId") == expected
    assert audit.get("userColors") == {}
    assert audit.get("modelPreferences") == items
    assert audit.get("userPreferences") == [preference("paletteFamily", family, "要求的色调")]
    assert audit.get("selectorError") is None
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert saved == before


@pytest.mark.parametrize("query,color", [
    ("背景色 #4caf50", "#FF4CAF50"),
    ("背景色 #ff4caf50", "#FF4CAF50"),
    ("背景色 rgb(76, 175, 80)", "#FF4CAF50"),
    ("背景色 rgba(76, 175, 80, 1)", "#FF4CAF50"),
    ("背景色 rgba(76, 175, 80, 1.0)", "#FF4CAF50"),
])
def test_literal_background_color_keeps_exact_value(monkeypatch, query, color):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = query
    items = [preference("backgroundColor", color, query)]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("userColors", {}).get("background", {}).get("color") == color
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == color


def test_explicit_solid_kind_keeps_color_even_when_order_is_reversed(monkeypatch):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "使用纯绿底色"
    items = [preference("backgroundColor", "#4CAF50", "纯绿底色"),
             preference("backgroundKind", "solid", "纯绿底色")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("userColors", {}).get("background", {}).get("color") == "#FF4CAF50"
    assert "fusionBallBackground" not in result


@pytest.mark.parametrize("wide,enabled", [(True, True), (False, False)])
def test_color_normalization_does_not_bypass_size_or_version(monkeypatch, wide, enabled):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: enabled)
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "背景是绿色的"
    items = [preference("backgroundColor", "#4CAF50", "背景是绿色的")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("theme", {}).get("kind") in {"solid", "gradient"}
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF1F9985"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_text_color_and_negative_color_keep_original_behavior():
    items = [preference("backgroundColor", "#4CAF50", "排除配色", "avoid"),
             preference("textColor", "#4CAF50", "文字配色")]
    parsed = preferences.parse_preferences(
        items, "排除配色，文字配色", registry.registered_themes(),
    )
    assert parsed == [preference("backgroundColor", "#FF4CAF50", "排除配色", "avoid"),
                      preference("textColor", "#FF4CAF50", "文字配色")]


@pytest.mark.parametrize("color", ["#FFFFFFFF", "#FF000000", "#FF808080"])
def test_neutral_colors_are_not_guessed_as_hue_families(color):
    items = [preference("backgroundColor", color, "配色")]
    parsed = preferences.parse_preferences(items, "配色", registry.registered_themes())
    assert parsed == items


def test_static_policy_still_excludes_fusion_after_color_resolution(monkeypatch):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "使用绿色背景"
    items = [preference("backgroundColor", "#4CAF50", "绿色背景")]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("theme", {}).get("kind") in {"solid", "gradient"}
    assert "fusionBallBackground" not in result
    assert not audit.get("fusionEligibility", {}).get("palettePreferenceTokens")


@pytest.mark.parametrize("evidence", ["#000000", "rgb(0,0,0)"])
def test_wrong_numeric_evidence_is_rejected(evidence):
    with pytest.raises(ValueError, match="numeric evidence"):
        preferences.parse_preferences(
            [preference("backgroundColor", "#4CAF50", evidence)], evidence,
            registry.registered_themes(),
        )


def test_duplicate_color_and_palette_converge_but_conflicts_are_rejected():
    query = "配色要求"
    color = preference("backgroundColor", "#4CAF50", query)
    green = preference("paletteFamily", "green", query)
    parsed = preferences.parse_preferences([color, green], query, registry.registered_themes())
    assert parsed == [green]
    red = preference("paletteFamily", "red", query)
    with pytest.raises(ValueError, match="Conflicting preferred palette"):
        preferences.parse_preferences([color, red], query, registry.registered_themes())


@pytest.mark.parametrize("value", [{"unknown": 10}, {"green": 360}])
def test_palette_routing_configuration_is_validated(value):
    config = registry.load_theme_registry()
    routing = config.get("selection", {}).get("backgroundPaletteRouting")
    assert isinstance(routing, dict)
    routing["hueAnchors"] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_disabled_palette_does_not_silently_route_to_another_color(monkeypatch):
    config = registry.load_theme_registry()
    for theme in config.get("themes", []):
        if theme.get("id") == "fusion-ball-battery-teal":
            theme["enabled"] = False
    monkeypatch.setattr(registry, "_load_registry", lambda _path: copy.deepcopy(config))
    item = preference("backgroundColor", "#4CAF50", "配色")
    parsed = preferences.parse_preferences([item], "配色", registry.registered_themes())
    assert parsed == [{**item, "value": "#FF4CAF50"}]


@pytest.mark.parametrize("extra", [
    [preference("backgroundTone", "dark", "配色")],
    [preference("backgroundTone", "light", "配色")],
    [preference("backgroundKind", "fusion", "配色", "avoid"),
     preference("backgroundKind", "gradient", "配色", "avoid")],
])
def test_fixed_background_constraints_keep_ordinary_color_without_empty_candidates(
    monkeypatch, extra,
):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "按配色要求"
    items = [preference("backgroundColor", "#4CAF50", "配色"), *extra]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("selectorError") is None
    assert audit.get("userColors", {}).get("background", {}).get("color") == "#FF4CAF50"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
