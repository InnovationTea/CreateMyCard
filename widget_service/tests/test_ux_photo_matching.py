"""UX 图片不猜测真实宽高；无主体按布局匹配，有主体保守回退。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import square_photo_expansion, subjectless_wide_theme
from services.theme_content_regions import button_ids

SPORT_LAYOUT = '\n'.join([
    '["root","Layout",{"layout":"W-content-side-slots"},["main","upper","lower"]]',
    '["main","Region",{"variant":"title-hero-support"},["value"]]',
    '["value","EmphasizedData",{"value":"6200","unit":"步"}]',
    '["upper","InfoBlock",{"variant":"slot","primaryText":"今日运动"}]',
    '["lower","CardButton",{"label":"锻炼记录"}]',
])


def ux(identity):
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == "photo-ux-" + identity)


def evidence(size, rects):
    return {"basis": "layout-only", "complete": True, "deviceGeometryKnown": False,
            "contentIds": [str(index) for index in range(len(rects))],
            "occupied": [{"id": str(index), "rect": rect} for index, rect in enumerate(rects)]}


@pytest.mark.parametrize("identity,query,rect", [
    ("weather-square", "天气", [.05, .05, .3, .2]),
    ("sleep-square", "睡眠", [.05, .05, .2, .8]),
    ("sleep-square", "睡眠", [.05, .05, .6, .15]),
    ("sleep-square", "睡眠", [.05, .86, .7, .1]),
    ("sport1-square", "运动", [.05, .8, .7, .15]),
    ("sport2-square", "运动", [.05, .84, .7, .1]),
    ("sport3-square", "运动", [.05, .88, .7, .08]),
    ("sport-center-wide", "运动", [.05, .1, .3, .6]),
    ("sport-center-wide", "运动", [.65, .1, .3, .6]),
    ("travel-wide", "出行航班", [.05, .8, .7, .15]),
    ("information-wide", "新闻资讯", [.05, .8, .7, .15]),
    ("home-wide", "智慧家", [.05, .8, .7, .15]),
    ("sleep-wide", "睡眠", [.65, .2, .3, .6]),
    ("concert-wide", "音乐", [.55, .2, .3, .6]),
])
def test_only_subjectless_photos_match_without_device_geometry(identity, query, rect):
    theme = ux(identity)
    size = theme.get("size")
    reason = themes.photo_reason(theme, {"size": size, "userQuery": query},
                                 evidence(size, [rect]), final_layout=SPORT_LAYOUT)
    if theme.get("subjectless"):
        assert reason is None
    else:
        assert "真实卡片宽高未知" in reason


@pytest.mark.parametrize("identity,query,rect", [
    ("weather-square", "天气", [.05, .7, .8, .2]),
    ("sport1-square", "运动", [.05, .05, .8, .2]),
    ("sport2-square", "运动", [.05, .05, .8, .2]),
    ("sport3-square", "运动", [.05, .05, .8, .2]),
    ("sport-center-wide", "运动", [.4, .4, .4, .2]),
    ("sport-wide", "运动", [.05, .05, .8, .2]),
    ("travel-wide", "航班", [.05, .05, .8, .2]),
    ("information-wide", "新闻", [.05, .05, .8, .2]),
    ("home-wide", "智慧家", [.05, .05, .8, .2]),
    ("sleep-wide", "睡眠", [.2, .2, .3, .2]),
    ("concert-wide", "音乐", [.3, .2, .3, .2]),
])
def test_subject_or_reserved_area_rejects_content(identity, query, rect):
    theme = ux(identity)
    size = theme.get("size")
    assert themes.photo_reason(theme, {"size": size, "userQuery": query},
                               evidence(size, [rect])) is not None


def test_button_interior_is_not_empty_even_when_its_label_avoids_subject():
    task = {"size": "2x2", "userQuery": "天气"}
    measured = evidence("2x2", [[.1, .1, .2, .1], [.1, .4, .8, .2]])
    measured["subjectAvoidance"] = measured.get("occupied", [])[:1]
    assert themes.photo_reason(ux("weather-square"), task, measured) is not None


@pytest.mark.parametrize("basis", [None, "production-web-renderer", "explicit-test-viewport"])
def test_test_viewports_cannot_authorize_runtime_photos(basis):
    measured = evidence("2x4", [[.1, .1, .2, .2]])
    measured["basis"] = basis
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "运动"}, measured,
                               final_layout=SPORT_LAYOUT) is not None


@pytest.mark.parametrize("query", ["运动", "今天走了多少步", "跑步记录", "训练", "马拉松备赛"])
def test_center_sport_photo_is_subjectless_for_sports_with_left_main_right_slots(query):
    measured = evidence("2x4", [[.4, .25, .4, .3], [.45, .6, .5, .3]])
    measured.get("occupied", [])[1]["id"] = "whole-button"
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": query}, measured,
                               final_layout=SPORT_LAYOUT) is None


@pytest.mark.parametrize("layout", [
    None, "invalid compact",
    SPORT_LAYOUT.replace("W-content-side-slots", "W-split-panels"),
    SPORT_LAYOUT.replace('"layout":"W-content-side-slots"',
                         '"layout":"W-content-side-slots","orientation":"content-right"'),
    SPORT_LAYOUT.replace('["main","upper","lower"]', '["main","upper"]'),
    SPORT_LAYOUT.replace('"lower","CardButton"', '"lower","TextBlock"'),
    SPORT_LAYOUT.replace('"main","Region"', '"main","Group"'),
])
def test_center_sport_photo_requires_verified_matching_layout_even_without_collision(layout):
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "运动"},
                               evidence("2x4", [[.1, .1, .2, .2]]),
                               final_layout=layout) is not None


@pytest.mark.parametrize("query", ["天气", "日程", "纯色运动卡", "运动不要背景图"])
def test_subjectless_layout_does_not_override_business_or_user_preference(query):
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": query},
                               evidence("2x4", [[.4, .25, .4, .3]]),
                               final_layout=SPORT_LAYOUT) is not None


@pytest.mark.parametrize("field,value", [
    ("contentIds", []), ("contentIds", None), ("deviceGeometryKnown", True), ("complete", False),
])
def test_subjectless_layout_requires_dimension_free_content_evidence(field, value):
    measured = evidence("2x4", [[.4, .25, .4, .3]])
    measured[field] = value
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "运动"}, measured,
                               final_layout=SPORT_LAYOUT) is not None


def test_subjectless_policy_does_not_apply_to_other_photos():
    measured = evidence("2x4", [[.4, .25, .4, .3]])
    assert themes.photo_reason(ux("sport-wide"), {"size": "2x4", "userQuery": "运动"},
                               measured, final_layout=SPORT_LAYOUT) is not None


@pytest.mark.parametrize("query", ["睡眠", "白天小睡", "昨晚睡了多久", "深睡时长"])
def test_sleep_square_is_subjectless_without_specific_layout(query):
    measured = evidence("2x2", [[.5, .32, .35, .14], [.6, .6, .3, .3]])
    measured.get("occupied", [])[1]["id"] = "whole-icon-button"
    assert themes.photo_reason(ux("sleep-square"),
                               {"size": "2x2", "userQuery": query}, measured) is None


def test_sleep_subjectless_policy_can_be_disabled_without_changing_regions():
    photo = ux("sleep-square")
    photo["subjectless"] = False
    assert themes.photo_reason(photo, {"size": "2x2", "userQuery": "睡眠"},
                               evidence("2x2", [[.5, .5, .3, .2]])) is not None


@pytest.mark.parametrize("size,query", [
    ("2x4", "睡眠"), ("2x2", "天气"), ("2x2", "运动"),
    ("2x2", "睡眠用纯色"), ("2x2", "睡眠不要图片"),
])
def test_sleep_subjectless_policy_keeps_size_business_and_user_gates(size, query):
    assert themes.photo_reason(ux("sleep-square"), {"size": size, "userQuery": query},
                               evidence(size, [[.5, .5, .3, .2]])) is not None


@pytest.mark.parametrize("field,value", [
    ("basis", None), ("basis", "explicit-test-viewport"), ("basis", "production-web-renderer"),
    ("complete", False), ("contentIds", []), ("contentIds", None), ("deviceGeometryKnown", True),
])
def test_sleep_subjectless_policy_does_not_accept_fake_device_geometry(field, value):
    measured = evidence("2x2", [[.5, .5, .3, .2]])
    measured[field] = value
    assert themes.photo_reason(ux("sleep-square"), {"size": "2x2", "userQuery": "睡眠"},
                               measured) is not None


@pytest.mark.parametrize("enabled", [True, False])
def test_sleep_photo_selection_respects_global_image_switch(monkeypatch, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    process = AsyncMock(side_effect=RuntimeError("Cloud must not render a guessed viewport"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", process)
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "睡眠", "styles": {}},
    ]}}])
    identity = "photo-ux-sleep-square"
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x2", "userQuery": "睡眠"}, client,
    ))
    assert (audit.get("themeId") == identity) is enabled
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    process.assert_not_called()
    assert audit.get("deviceGeometryKnown") is False
    assert "measurement" not in audit


@pytest.mark.parametrize("identity,field,value", [
    ("photo-ux-sleep-square", "subjectless", "true"),
    ("photo-ux-sleep-square", "composition", "square-left"),
    ("photo-ux-sport-center-wide", "subjectless", False),
    ("gradient-blue", "subjectless", True),
])
def test_subjectless_policy_validation(identity, field, value):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", []) if item.get("id") == identity)
    photo[field] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_subjectless_photo_selected_without_changing_layout(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "跑步", "styles": {}},
    ]}}])
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"photo-ux-sport-center-wide"}'))
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x4", "userQuery": "跑步"}, client, final_layout=SPORT_LAYOUT,
    ))
    assert audit.get("candidates") == ["photo-ux-sport-center-wide"]
    assert audit.get("themeId") == "photo-ux-sport-center-wide"
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


@pytest.mark.parametrize("field,value", [
    ("subjectlessLayout", {}),
    ("subjectlessLayout", {"layout": "W-four-slots", "orientation": "content-left"}),
    ("subjectlessLayout", {"layout": "W-content-side-slots", "orientation": "content-right"}),
    ("composition", "square-left"),
])
def test_subjectless_configuration_rejects_unsupported_policy(field, value):
    config = registry.load_theme_registry()
    theme = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-sport-center-wide")
    theme[field] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_noninteractive_panels_remain_empty_but_clickable_cards_are_content():
    nodes = [{"id": "root", "component": "Column", "onClick": ["open"]},
             {"id": "panel", "component": "Column"},
             {"id": "card", "component": "Row", "onClick": ["open"]},
             {"id": "button", "component": "Button"}]
    assert button_ids(nodes) == ["card", "button"]


def test_expansion_geometry_diagnostics_check_all_supplied_samples():
    before = evidence("2x2", [[.1, .1, .3, .2]])
    before["responsive"] = [copy.deepcopy(before)]
    after = copy.deepcopy(before)
    for view in [before, *before.get("responsive", [])]:
        view["visible"] = [{"id": "text", "text": "ok", "rect": [.1, .1, .3, .2]}]
    for view in [after, *after.get("responsive", [])]:
        view["occupied"] = [{"id": "0", "rect": [.05, .1, .15, .2]}]
        view["visible"] = [{"id": "text", "text": "ok", "rect": [.05, .1, .15, .2]}]
    assert square_photo_expansion.same_square_geometry(before, after)
    after.get("responsive", [])[0].get("visible", [])[0]["rect"] = [.05, .2, .15, .2]
    assert not square_photo_expansion.same_square_geometry(before, after)


@pytest.mark.parametrize("photo", registry.registered_themes("photos"))
def test_original_assets_are_present_and_fully_adaptive(photo):
    root = Path(__file__).resolve().parents[2]
    src = photo.get("src")
    assert src
    assert hashlib.sha256((root / src).read_bytes()).hexdigest() == (
        photo.get("source", {}).get("assetSha256")
    )
    assert photo.get("objectFit") == "fill"
    assert photo.get("sizes") == [photo.get("size")]
    layers = themes.photo_background(photo)
    for layer in layers:
        if layer.get("component") == "Image":
            assert layer.get("styles") == {
                "width": "matchParent", "height": "matchParent", "objectFit": "fill",
            }


@pytest.mark.parametrize("module,pool,size,data", [
    (square_photo_expansion, "squareExpansions", "2x2", "countdown"),
    (subjectless_wide_theme, "subjectlessWidePhotos", "2x4", "phoneBattery"),
])
def test_retained_feature_gates_no_longer_sample(monkeypatch, module, pool, size, data):
    settings = get_settings()
    for flag in ("enable_photo_background_theme", "enable_square_photo_expansion",
                 "enable_subjectless_wide_theme"):
        monkeypatch.setattr(settings, flag, True)
    entries = registry.registered_themes(pool, include_disabled=True)
    monkeypatch.setattr(module, "registered_themes", lambda _pool: entries)
    gate = module.expansion_gate if size == "2x2" else module.wide_gate
    for number in range(100):
        task = {"size": size, "userQuery": f"显示倒计时{number}",
                "dataModelSchema": {"data": {data: {"value": {"type": "integer"}}}}}
        assert gate(task).get("eligible") is True


@pytest.mark.parametrize("model_id", ["photo-ux-sleep-square", "gradient-blue", "invalid"])
def test_eligible_photo_always_wins_without_user_override(monkeypatch, model_id):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "睡眠", "styles": {}},
    ]}}])
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": model_id})))
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x2", "userQuery": "睡眠"}, client,
    ))
    assert audit.get("themeId") == "photo-ux-sleep-square"
    assert audit.get("candidates") == ["photo-ux-sleep-square"]
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


@pytest.mark.parametrize("query", ["纯色天气", "不要背景图", "天气用渐变", "使用融球天气"])
def test_explicit_theme_preferences_override_photos(query):
    assert themes.photo_reason(ux("weather-square"), {"size": "2x2", "userQuery": query},
                               evidence("2x2", [[.1, .1, .2, .2]])) is not None


@pytest.mark.parametrize("field,value", [
    ("contentRegions", []), ("contentRegions", [[0, 0, 2, 1]]),
    ("subjectRegions", [[0, 0, 0, 1]]),
    ("measurementPolicy", "legacy-capsule-exemption"),
    ("matchingPolicy", "whole-buttons-responsive"),
    ("subjectBounds", [0, 0, .1, .1]),
])
def test_invalid_ux_regions_rejected_at_config_load(field, value):
    config = registry.load_theme_registry()
    theme = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-weather-square")
    theme[field] = copy.deepcopy(value)
    with pytest.raises(ValueError):
        registry.validate_registry(config)
