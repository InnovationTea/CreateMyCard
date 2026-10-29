"""普通配色复用登记主题；测试提供结构化语义，不用关键词模拟模型理解。"""

import copy
import json

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_user_preferences as preferences
from services.theme_layout_summary import theme_description
from test_photo_background_fallback import node_by_id
from test_post_layout_sleep_theme import sleep_layout, sleep_task
from test_uniform_photo_eligibility import PATHS, choose, sample
from theme_preference_samples import preference, reply


def standard_candidates():
    return registry.registered_themes("standard")


def select(candidates, items):
    parsed = preferences.parse_preferences(items, "配色与要求由用户给定", candidates)
    overrides = preferences.color_overrides(parsed, candidates=candidates)
    allowed = preferences.filter_with_fusion_fallback(candidates, parsed, overrides)
    return preferences.prioritize_candidates(allowed, parsed, "blue"), overrides


@pytest.mark.parametrize("family,expected", [
    ("red", "fusion-ball-sport-orange"),
    ("orange", "fusion-ball-sport-orange"),
    ("green", "fusion-ball-battery-teal"),
    ("cyan", "fusion-ball-battery-teal"),
    ("yellow", "gradient-warm"),
    ("blue", "fusion-ball-schedule-blue"),
    ("purple", "fusion-ball-sleep-violet"),
])
def test_eligible_palette_uses_registered_preset_without_color_override(family, expected):
    candidates = standard_candidates()
    before = copy.deepcopy(candidates)
    items = [preference("paletteFamily", family, "配色")]
    allowed, overrides = select(candidates, items)
    assert [item.get("id") for item in allowed] == [expected]
    assert overrides == {}
    assert candidates == before


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("family,square,wide_theme", [
    ("red", "fusion-ball-sport-orange", "gradient-warm"),
    ("yellow", "gradient-warm", "gradient-warm"),
    ("orange", "fusion-ball-sport-orange", "gradient-warm"),
    ("blue", "fusion-ball-schedule-blue", "gradient-blue"),
    ("purple", "fusion-ball-sleep-violet", "gradient-purple"),
])
def test_requested_palette_relaxes_only_content_gate_and_preserves_foreground(
    monkeypatch, wide, family, square, wide_theme,
):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "配色与要求由用户给定"
    items = [preference("paletteFamily", family, "配色")]
    result, audit = choose(saved, monkeypatch, reply(items, "solid-warm"))
    assert audit.get("themeId") == (wide_theme if wide else square)
    assert not audit.get("fusionEligibility", {}).get("allowedTokens")
    assert audit.get("userColors") == {}
    assert audit.get("selectorError") is None
    root = node_by_id(result, "root").get("styles", {})
    if wide or family == "yellow":
        assert root.get("linearGradient")
        assert root.get("backgroundColor") is None
    else:
        assert "fusionBallBackground" in result
        assert audit.get("fusionEligibility", {}).get("palettePreferenceTokens") == [square]
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("family", ["red", "blue", "purple"])
def test_negative_palette_excludes_the_registered_equivalents(family):
    items = [preference("paletteFamily", family, "配色", "avoid")]
    candidates, overrides = select(standard_candidates(), items)
    assert candidates
    assert overrides == {}
    assert all(family not in registry.theme_palette_families(theme) for theme in candidates)


def test_explicit_photo_remains_possible_and_no_preference_keeps_photo_priority(monkeypatch):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "配色与要求由用户给定"
    items = [preference("paletteFamily", "blue", "配色"),
             preference("backgroundKind", "photo", "要求")]
    _, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("theme", {}).get("kind") == "photo"
    _, no_preference = choose(saved, monkeypatch, reply([]))
    assert no_preference.get("theme", {}).get("kind") == "photo"


@pytest.mark.parametrize("family", ["green", "cyan"])
def test_fusion_drawing_fallback_uses_existing_base_color_without_losing_preference(family):
    candidates = standard_candidates()
    items = [preference("paletteFamily", family, "配色")]
    overrides = preferences.color_overrides(items, candidates=candidates)
    assert overrides == {}
    fallback = themes.preference_fallback({"size": "2x2"}, items, overrides)
    teal = next(item for item in candidates if item.get("id") == "fusion-ball-battery-teal")
    assert fallback.get("kind") in {"gradient", "solid"}
    assert overrides.get("background", {}).get("color") == (
        teal.get("background", {}).get("ballColors", {}).get("large")
    )
    assert preferences.preference_reason(fallback, items, overrides) is None


@pytest.mark.parametrize("wide", [False, True])
def test_registered_palette_without_eligible_preset_uses_readable_plain_color(monkeypatch, wide):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: False)
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "配色与要求由用户给定"
    items = [preference("paletteFamily", "green", "配色")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("preferenceStatus") == "confirmed"
    assert audit.get("selectorError") is None
    assert audit.get("theme", {}).get("kind") in {"gradient", "solid"}
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF1F9985"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("items", [
    [], [preference("paletteFamily", "red", "配色", "avoid")],
    [preference("backgroundKind", "fusion", "配色")],
    [preference("backgroundColor", "#FFFF0000", "配色")],
])
def test_without_positive_palette_default_fusion_gate_is_unchanged(monkeypatch, items):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 4)
    saved.task["userQuery"] = "配色与要求由用户给定"
    result, audit = choose(saved, monkeypatch, reply(items, "fusion-ball-sport-orange"))
    assert audit.get("theme", {}).get("kind") != "fusion"
    assert not audit.get("fusionEligibility", {}).get("palettePreferenceTokens")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("family,expected", [
    ("red", "fusion-ball-sport-orange"), ("green", "fusion-ball-battery-teal"),
])
def test_many_body_lines_can_use_requested_fusion_palette(monkeypatch, family, expected):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 5)
    saved.task["userQuery"] = "配色与要求由用户给定"
    items = [preference("paletteFamily", family, "配色")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("themeId") == expected
    assert audit.get("userColors") == {}
    assert audit.get("selectorError") is None
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_five_visible_fields_and_different_business_allow_requested_color(monkeypatch):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    query = "配色与要求由用户给定"
    task = sleep_task(query)
    rows = themes.decode(sleep_layout())
    support = next(row for row in rows if row[0] == "support")
    data = task.get("dataModelSchema", {}).get("data", {}).get("healthSport")
    assert isinstance(data, dict)
    for name in ("fallAsleepTimeText", "wakeupTimeText", "totalNapDurationText"):
        path = "/data/healthSport/" + name
        data[name] = {"type": "string", "sampleValue": "07:00"}
        support[2].get("items", []).append({"value": {"path": path}})
        rows.append([path, "07:00"])
    saved = expanded(rows, task)
    items = [preference("paletteFamily", "red", "配色")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("fusionEligibility", {}).get("visibleFieldCount") == 5
    assert not audit.get("fusionEligibility", {}).get("allowedTokens")
    assert audit.get("themeId") == "fusion-ball-sport-orange"
    assert audit.get("selectorError") is None
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("response", [
    json.dumps({"themeId": "fusion-ball-sport-orange"}),
    reply([preference("paletteFamily", "red", "没有出现在请求里的证据")],
          "fusion-ball-sport-orange"),
])
def test_unconfirmed_palette_does_not_bypass_content_gate(monkeypatch, response):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    saved = sample(PATHS.get("weather"), 5)
    saved.task["userQuery"] = "配色与要求由用户给定"
    result, audit = choose(saved, monkeypatch, response)
    assert audit.get("theme", {}).get("kind") != "fusion"
    assert audit.get("preferenceStatus") != "confirmed"
    assert not audit.get("fusionEligibility", {}).get("palettePreferenceTokens")
    assert audit.get("selectorError")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("specific", ["#FF123456", "#FFFF0000", "#FFFFFFFF"])
def test_exact_colors_are_not_quantized_to_a_palette(specific):
    items = [preference("backgroundColor", specific, "配色")]
    _, overrides = select(standard_candidates(), items)
    assert overrides.get("background", {}).get("color") == specific


def test_palette_metadata_is_validated_and_projected_without_raw_colors():
    payload = registry.load_theme_registry()
    registry.validate_registry(payload)
    for theme in standard_candidates():
        if "paletteFamilies" not in theme:
            continue
        description = theme_description(theme)
        assert description.get("paletteFamilies") == theme.get("paletteFamilies")
        assert "background" not in description
        assert "content" not in description
    target = payload.get("themes", [])[0]
    target["paletteFamilies"] = ["blue", "blue"]
    with pytest.raises(ValueError, match="paletteFamilies"):
        registry.validate_registry(payload)


def test_unsupported_model_palette_is_rejected_not_silently_guessed():
    with pytest.raises(ValueError, match="registered choices"):
        preferences.parse_preferences(
            [preference("paletteFamily", "unknown", "配色")], "配色", standard_candidates(),
        )


@pytest.mark.parametrize("families", [("red", "warm"), ("warm", "red"), ("red", "red")])
def test_equivalent_palette_descriptions_converge_without_discarding_color(families):
    items = [preference("paletteFamily", family, "配色") for family in families]
    parsed = preferences.parse_preferences(items, "配色", standard_candidates())
    assert len(parsed) == 1
    assert parsed[0].get("value") == "red"


def test_incompatible_palette_preferences_still_fail():
    items = [preference("paletteFamily", family, "配色") for family in ["blue", "purple"]]
    with pytest.raises(ValueError, match="Conflicting preferred palette"):
        preferences.parse_preferences(items, "配色", standard_candidates())
