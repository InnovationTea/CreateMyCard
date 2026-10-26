"""节假日与冰面专属准入、睡眠等概率及电量重新启用。"""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_autumn_calendar_photos import expanded
from test_photo_gallery_rules import BIRDS, double_countdown
from test_uniform_photo_eligibility import PATHS, choose, photo, rejection, sample
from test_wide_photo_focus import focus_sample
from theme_preference_samples import preference, reply

ICE = "photo-ux-ice-wide"
FIREWORKS = "photo-ux-fireworks-square"
SLEEP = "photo-ux-sleep-square"
BATTERY = "photo-ux-starry-sky-wide"
ROAD = "photo-ux-road-wide"


def panels(layout, weather_slot=0, lines=6):
    count = 2 if layout == "W-split-panels" else 4
    children = [f"slot{i}" for i in range(count)]
    rows = [["root", "Layout", {"layout": layout}, children]]
    for index, identity in enumerate(children):
        business = "weather" if index == weather_slot else "battery"
        path = PATHS.get(business)
        assert path is not None
        if count == 2:
            rows.extend([
                [identity, "Region", {"variant": "title-content"},
                 [identity + "_title", identity + "_text"]],
                [identity + "_title", "SingleLineTitle", {"title": "状态"}],
                [identity + "_text", "Text", {"content": {"path": path}, "maxLines": 20}],
            ])
        else:
            rows.append([identity, "InfoBlock", {
                "variant": "slot", "surfaceRole": "panel", "primaryText": {"path": path},
                "secondaryText": "状态",
            }])
    for path in (PATHS.get("weather"), PATHS.get("battery")):
        rows.append([path, "\n".join(["29"] * lines)])
    return expanded(rows, {"size": "2x4", "userQuery": "天气电量", "appVersion": "99.0.0"})


@pytest.mark.parametrize("align", ["start", "center", "end"])
@pytest.mark.parametrize("lines", [1, 4, 8])
def test_holiday_ignores_alignment_and_line_limit(align, lines):
    saved = sample(PATHS.get("countdown"), lines, title="中秋节", align=align)
    assert rejection(saved, BIRDS) is None
    assert rejection(sample(PATHS.get("countdown"), lines, title="生日", align=align), BIRDS)


def test_many_holiday_panels_allowed_but_mixed_business_rejected():
    assert rejection(double_countdown(lines=6), BIRDS) is None
    assert rejection(double_countdown(second="考试", lines=6), BIRDS)
    saved = double_countdown(lines=6)
    rows = themes.decode(saved.compact)
    rows[0][3].append("weather")
    rows.extend([["weather", "Text", {"content": {"path": PATHS.get("weather")}}],
                 [PATHS.get("weather"), 29]])
    assert rejection(expanded(rows, saved.task), BIRDS)


@pytest.mark.parametrize("layout,count", [("W-split-panels", 2), ("W-four-slots", 4)])
def test_ice_accepts_weather_in_any_panel_without_line_limit(monkeypatch, layout, count):
    for index in range(count):
        saved = panels(layout, index)
        assert rejection(saved, ICE) is None
        before = copy.deepcopy(saved.nodes)
        result, audit = choose(saved, monkeypatch)
        assert audit.get("candidates") == [ICE]
        assert audit.get("themeId") == ICE
        assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
        assert saved.nodes == before
        for identity in ("photo-ux-wave-wide", "photo-ux-fuzzy-wide", BATTERY):
            assert rejection(saved, identity)


@pytest.mark.parametrize("layout", ["W-split-panels", "W-four-slots"])
def test_ice_requires_visible_weather_not_query_or_unused_data(layout):
    saved = panels(layout, weather_slot=-1)
    assert rejection(saved, ICE)
    rows = themes.decode(saved.compact)
    rows.append(["hidden_weather", "Text", {"content": {"path": PATHS.get("weather")}}])
    saved.compact = themes.encode(rows)
    assert rejection(saved, ICE)


@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_ice_does_not_enter_focus_layouts(layout):
    assert rejection(focus_sample("weather", 1, layout), ICE)
    assert rejection(sample(PATHS.get("weather"), 1), ICE)


@pytest.mark.parametrize("selected", [SLEEP, FIREWORKS])
def test_sleep_pair_uses_single_unweighted_choice(monkeypatch, selected):
    calls = []

    def choice(items):
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = sample(button=False)
    result, audit = choose(saved, monkeypatch)
    assert len(calls) == 1
    assert len(calls[0]) == 2
    assert set(calls[0]) == {SLEEP, FIREWORKS}
    assert audit.get("themeId") == selected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("layout,lines,allowed", [
    ("left", 4, True), ("left", 5, False), ("right", 1, False), ("top", 1, False),
])
def test_a15_enabled_without_relaxing_existing_focus_rule(monkeypatch, layout, lines, allowed):
    saved = focus_sample("battery", lines, layout)
    assert (rejection(saved, BATTERY) is None) is allowed
    _, audit = choose(saved, monkeypatch)
    assert (BATTERY in audit.get("candidates", [])) is allowed


def test_retired_image_removed_and_road_disabled_without_assigned_business():
    items = registry.registered_themes(include_disabled=True)
    assert not any(item.get("id") == "photo-ux-galaxy-sleep-square" for item in items)
    road = photo(ROAD)
    assert road.get("enabled") is False
    assert road.get("contentEligibility", {}).get("businesses") == []
    assert road.get("src", "").endswith(".JPG")
    assert road.get("remoteUrl", "").endswith(".JPG")


@pytest.mark.parametrize("identity", [BIRDS, ICE])
@pytest.mark.parametrize("change", ["size", "business", "pool", "maxTextLines"])
def test_special_policies_cannot_relax_unrelated_photos(identity, change):
    config = registry.load_theme_registry()
    item = next(item for item in config.get("themes", []) if item.get("id") == identity)
    if change == "size":
        item["sizes"] = ["2x4" if identity == BIRDS else "2x2"]
    elif change == "business":
        item["contentEligibility"]["businesses"] = ["sleep"]
    elif change == "pool":
        item["pool"] = "texturePhotos"
        item["subjectless"] = True
        item["family"] = "blue"
    else:
        item["contentEligibility"]["maxTextLines"] = 3
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_unassigned_road_cannot_be_enabled():
    config = registry.load_theme_registry()
    item = next(item for item in config.get("themes", []) if item.get("id") == ROAD)
    item["enabled"] = True
    with pytest.raises(ValueError, match="business"):
        registry.validate_registry(config)


@pytest.mark.parametrize("query,attribute,value,operation", [
    ("不要背景图片", "backgroundKind", "photo", "avoid"),
    ("使用渐变", "backgroundKind", "gradient", "prefer"),
    ("背景用蓝色", "backgroundColor", "#FF0000FF", "prefer"),
])
def test_special_photos_respect_user_preference(monkeypatch, query, attribute, value, operation):
    for saved in (panels("W-split-panels"), double_countdown(lines=6)):
        saved.task["userQuery"] = query
        items = [preference(attribute, value, query, operation)]
        _, audit = choose(saved, monkeypatch, reply(items))
        assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))


def test_special_photos_respect_feature_switch(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    saved = panels("W-split-panels")
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    _, audit = asyncio.run(themes.select_theme(saved.source, saved.task, client,
                                              final_layout=saved.compact))
    assert ICE not in audit.get("candidates", [])
