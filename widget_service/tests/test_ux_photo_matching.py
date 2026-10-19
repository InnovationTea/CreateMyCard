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
from services.theme_content_regions import button_ids, photo_layout_evidence
from theme_photo_samples import expansion_photo, protected_photo

SPORT_LAYOUT = '\n'.join([
    '["root","Layout",{"layout":"W-content-side-slots"},["main","upper","lower"]]',
    '["main","Region",{"variant":"title-content"},["heading","value"]]',
    '["heading","SingleLineTitle",{"title":"最近跑步"}]',
    '["value","EmphasizedData",{"value":{"path":"/data/healthSport/exerciseDurationText"}}]',
    '["upper","InfoBlock",{"variant":"slot","primaryText":"今日运动"}]',
    '["lower","CardButton",{"label":"锻炼记录"}]',
])
SLEEP_LAYOUT = '\n'.join([
    '["root","Layout",{"layout":"S-title-content"},["header","reading"]]',
    '["header","SingleLineTitle",{"title":"睡眠"}]',
    '["reading","EmphasisText",{"mainText":{"path":"/data/healthSport/sleepStatus"}}]',
])


def sleep_task(query="睡眠"):
    return {"size": "2x2", "userQuery": query,
            "dataModelSchema": {"data": {"healthSport": {"sleepStatus": {"type": "string"}}}}}


def sleep_nodes():
    return [
        {"id": "root", "component": "Column", "children": ["header", "reading"],
         "styles": {"width": "matchParent", "height": "matchParent", "alignItems": "start"}},
        {"id": "header", "component": "Text", "content": "睡眠",
         "styles": {"maxLines": 1, "textAlign": "start"}},
        {"id": "reading", "component": "Text", "content": "{{ ${/data/healthSport/sleepStatus} }}",
         "styles": {"maxLines": 1, "textAlign": "start"}},
    ]


def ux(identity):
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == "photo-ux-" + identity)


def evidence(size, rects):
    return {"basis": "layout-only", "complete": True, "deviceGeometryKnown": False,
            "contentIds": [str(index) for index in range(len(rects))],
            "textFlow": photo_layout_evidence(sleep_nodes()).get("textFlow"),
            "occupied": [{"id": str(index), "rect": rect} for index, rect in enumerate(rects)]}


@pytest.mark.parametrize("identity,query", [
    ("sleep-square", "睡眠"), ("sport-center-wide", "运动"),
])
def test_subjectless_photos_match_without_device_geometry(identity, query):
    theme = ux(identity)
    size = theme.get("size")
    task = sleep_task(query) if identity == "sleep-square" else {"size": size, "userQuery": query}
    layout = SLEEP_LAYOUT if identity == "sleep-square" else SPORT_LAYOUT
    assert themes.photo_reason(theme, task, evidence(size, [[0, 0, 1, 1]]),
                               final_layout=layout) is None


@pytest.mark.parametrize("rect", [[.05, .05, .3, .2], [.05, .7, .8, .2]])
def test_protected_photo_cannot_use_test_rectangles_without_device_geometry(rect):
    photo = protected_photo()
    reason = themes.photo_reason(photo, {"size": "2x2", "userQuery": "天气"},
                                 evidence("2x2", [rect]))
    assert reason is not None and "真实卡片宽高未知" in reason


def test_button_interior_is_not_empty_even_when_its_label_avoids_subject():
    task = {"size": "2x2", "userQuery": "天气"}
    measured = evidence("2x2", [[.1, .1, .2, .1], [.1, .4, .8, .2]])
    measured["subjectAvoidance"] = measured.get("occupied", [])[:1]
    assert themes.photo_reason(ux("water-lily-square"), task, measured) is not None


@pytest.mark.parametrize("basis", [None, "production-web-renderer", "explicit-test-viewport"])
def test_test_viewports_cannot_authorize_runtime_photos(basis):
    measured = evidence("2x4", [[.1, .1, .2, .2]])
    measured["basis"] = basis
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "运动"}, measured,
                               final_layout=SPORT_LAYOUT) is not None


@pytest.mark.parametrize("query", ["运动", "今天走了多少步", "跑步记录", "训练", "马拉松备赛"])
def test_center_sport_photo_uses_left_running_content_not_only_request_keywords(query):
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
    assert themes.photo_reason(protected_photo(), {"size": "2x2", "userQuery": "天气"},
                               measured, final_layout=SPORT_LAYOUT) is not None


@pytest.mark.parametrize("query", ["睡眠", "白天小睡", "昨晚睡了多久", "深睡时长"])
def test_sleep_square_requires_single_sleep_business_and_known_layout(query):
    measured = evidence("2x2", [[.5, .32, .35, .14], [.6, .6, .3, .3]])
    measured.get("occupied", [])[1]["id"] = "whole-icon-button"
    assert themes.photo_reason(ux("sleep-square"),
                               sleep_task(query), measured, final_layout=SLEEP_LAYOUT) is None


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
    source = themes.encode([{"updateComponents": {"components": sleep_nodes()}}])
    identity = "photo-ux-sleep-square"
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    result, audit = asyncio.run(themes.select_theme(
        source, sleep_task(), client, final_layout=SLEEP_LAYOUT,
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
    photo = expansion_photo()
    if size == "2x4":
        photo.update(pool=pool, composition="subjectless", business="battery")
    entries = [photo]
    monkeypatch.setattr(module, "registered_themes", lambda _pool: entries)
    gate = module.expansion_gate if size == "2x2" else module.wide_gate
    for number in range(100):
        task = {"size": size, "userQuery": f"显示倒计时{number}",
                "dataModelSchema": {"data": {data: {"value": {"type": "integer"}}}}}
        assert gate(task).get("eligible") is True


@pytest.mark.parametrize("model_id", ["photo-ux-sleep-square", "gradient-blue", "invalid"])
def test_eligible_photo_always_wins_without_user_override(monkeypatch, model_id):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    source = themes.encode([{"updateComponents": {"components": sleep_nodes()}}])
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": model_id})))
    result, audit = asyncio.run(themes.select_theme(
        source, sleep_task(), client, final_layout=SLEEP_LAYOUT,
    ))
    assert audit.get("themeId") == "photo-ux-sleep-square"
    assert audit.get("candidates") == ["photo-ux-sleep-square"]
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


@pytest.mark.parametrize("query", ["纯色天气", "不要背景图", "天气用渐变", "使用融球天气"])
def test_explicit_theme_preferences_override_photos(query):
    assert themes.photo_reason(ux("water-lily-square"), {"size": "2x2", "userQuery": query},
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
                 if item.get("id") == "photo-ux-water-lily-square")
    theme[field] = copy.deepcopy(value)
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("limit,allowed", [
    (1, True), (2, True), (3, True), (4, False), (None, False),
])
def test_sleep_line_budget_excludes_top_title_and_uses_dynamic_max_lines(limit, allowed):
    nodes = sleep_nodes()
    nodes[2].get("styles", {})["maxLines"] = limit
    reason = themes.photo_reason(ux("sleep-square"), sleep_task(), photo_layout_evidence(nodes),
                                 final_layout=SLEEP_LAYOUT)
    assert (reason is None) is allowed


@pytest.mark.parametrize("include_title", [True, False])
def test_sleep_title_count_is_configured_not_a_pixel_assumption(include_title):
    photo = ux("sleep-square")
    photo.get("contentEligibility", {})["includeTitle"] = include_title
    nodes = sleep_nodes()
    nodes[2].get("styles", {})["maxLines"] = 3
    reason = themes.photo_reason(photo, sleep_task(), photo_layout_evidence(nodes),
                                 final_layout=SLEEP_LAYOUT)
    assert (reason is None) is not include_title


@pytest.mark.parametrize("support_lines,allowed", [(2, True), (3, False)])
def test_sleep_only_excludes_top_title_not_bottom_support(support_lines, allowed):
    nodes = sleep_nodes()
    nodes[0].get("children", []).append("support")
    nodes.append({"id": "support", "component": "Text", "content": "睡眠详情",
                  "styles": {"maxLines": support_lines}})
    reason = themes.photo_reason(ux("sleep-square"), sleep_task(), photo_layout_evidence(nodes),
                                 final_layout=sleep_anchor_layout())
    assert (reason is None) is allowed


@pytest.mark.parametrize("layout", [
    None, "invalid", SLEEP_LAYOUT.replace("S-title-content", "S-center"),
])
def test_sleep_rejects_unknown_or_center_layout(layout):
    measured = photo_layout_evidence(sleep_nodes())
    assert themes.photo_reason(ux("sleep-square"), sleep_task(), measured,
                               final_layout=layout) is not None


def sleep_anchor_layout(button="CircleButton"):
    return '\n'.join([
        '["root","Layout",{"layout":"S-title-anchor"},["header","reading","support","action"]]',
        '["header","SingleLineTitle",{"title":"睡眠"}]',
        '["reading","EmphasisText",{"mainText":{"path":"/data/healthSport/sleepStatus"}}]',
        '["support","SecondaryBody",{"items":[{"value":"昨晚"}]}]',
        json.dumps(["action", button, {"icon": "resources/base/media/alarm_fill_1.svg"}]),
    ])


@pytest.mark.parametrize("button", ["CircleButton", "PillButton"])
def test_sleep_allows_icon_and_capsule_buttons(button):
    nodes = sleep_nodes()
    nodes[0].get("children", []).extend(["support", "action"])
    nodes.extend([
        {"id": "support", "component": "Text", "content": "昨晚", "styles": {"maxLines": 1}},
        {"id": "action", "component": "Stack", "onClick": ["open"], "children": ["icon"]},
        {"id": "icon", "component": "Image"},
    ])
    reason = themes.photo_reason(ux("sleep-square"), sleep_task(), photo_layout_evidence(nodes),
                                 final_layout=sleep_anchor_layout(button))
    assert reason is None


@pytest.mark.parametrize("alignment", ["center", "end"])
def test_sleep_left_layout_cannot_hide_centered_or_right_aligned_text(alignment):
    nodes = sleep_nodes()
    nodes[2].get("styles", {})["textAlign"] = alignment
    assert themes.photo_reason(ux("sleep-square"), sleep_task(), photo_layout_evidence(nodes),
                               final_layout=sleep_anchor_layout()) is not None


def test_sleep_bottom_content_may_have_centered_text():
    nodes = sleep_nodes()
    nodes[2].get("styles", {})["textAlign"] = "center"
    assert themes.photo_reason(ux("sleep-square"), sleep_task(), photo_layout_evidence(nodes),
                               final_layout=SLEEP_LAYOUT) is None


@pytest.mark.parametrize("extra", ["dailySteps", "exerciseDurationText", "exerciseHeartRateAvg"])
def test_sleep_rejects_other_health_business_in_same_data_root(extra):
    task = sleep_task()
    health = task.get("dataModelSchema", {}).get("data", {}).get("healthSport", {})
    health[extra] = {"type": "number"}
    assert themes.photo_reason(ux("sleep-square"), task, photo_layout_evidence(sleep_nodes()),
                               final_layout=SLEEP_LAYOUT) is not None


def test_sleep_rejects_other_business_even_if_request_mentions_sleep():
    task = sleep_task("睡眠和天气")
    task.get("dataModelSchema", {}).get("data", {})["weather"] = {"temperature": {"type": "number"}}
    assert themes.photo_reason(ux("sleep-square"), task, photo_layout_evidence(sleep_nodes()),
                               final_layout=SLEEP_LAYOUT) is not None


def test_sleep_rejects_foreign_visible_binding_even_when_task_is_sleep_only():
    layout = SLEEP_LAYOUT.replace("/data/healthSport/sleepStatus", "/data/healthSport/dailySteps")
    measured = photo_layout_evidence(sleep_nodes())
    assert themes.photo_reason(ux("sleep-square"), sleep_task(), measured,
                               final_layout=layout) is not None


@pytest.mark.parametrize("heading,path,allowed", [
    ("广州马拉松倒计时", "/data/countdown/countdownDays", True),
    ("旅行倒计时", "/data/countdown/countdownDays", False),
    ("今日步数", "/data/healthSport/dailySteps", False),
    ("今日运动", "/data/healthSport/exerciseDurationText", False),
    ("最近跑步", "/data/healthSport/exerciseDurationText", True),
    ("夜跑", "/data/healthSport/exerciseDistanceText", True),
    ("今日跑步", "/data/healthSport/dailySteps", False),
    ("跑步天气", "/data/weather/temperature", False),
    ("马拉松天气", "/data/weather/temperature", False),
    ("马拉松赛事名称", "/data/countdown/name", False),
    ("睡眠", "/data/healthSport/nightSleepDurationText", False),
])
def test_sport_photo_requires_running_or_marathon_countdown_in_left_primary(heading, path, allowed):
    layout = SPORT_LAYOUT.replace("最近跑步", heading).replace(
        "/data/healthSport/exerciseDurationText", path)
    reason = themes.photo_reason(ux("sport-center-wide"),
                                 {"size": "2x4", "userQuery": "马拉松跑步运动卡"},
                                 evidence("2x4", [[0, 0, 1, 1]]), final_layout=layout)
    assert (reason is None) is allowed


def test_running_only_in_right_side_or_support_does_not_authorize_photo():
    layout = SPORT_LAYOUT.replace("最近跑步", "天气").replace(
        "/data/healthSport/exerciseDurationText", "/data/weather/temperature")
    layout = layout.replace("今日运动", "马拉松倒计时，最近跑步")
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "天气配跑步记录"},
                               evidence("2x4", [[0, 0, 1, 1]]), final_layout=layout) is not None


def test_running_title_alone_does_not_prove_main_business():
    layout = SPORT_LAYOUT.replace('{"path":"/data/healthSport/exerciseDurationText"}', '"31"')
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "跑步天气"},
                               evidence("2x4", [[0, 0, 1, 1]]), final_layout=layout) is not None


def test_bound_marathon_title_is_resolved_only_from_left_visible_bindings():
    layout = SPORT_LAYOUT.replace('"title":"最近跑步"',
                                  '"title":{"path":"/data/countdown/name"}')
    layout = layout.replace(
        "/data/healthSport/exerciseDurationText", "/data/countdown/countdownDays")
    layout += '\n["/data/countdown/name","广州马拉松"]'
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "马拉松倒计时"},
                               evidence("2x4", [[0, 0, 1, 1]]), final_layout=layout) is None


def test_right_info_panels_must_be_small_slot_variant():
    layout = SPORT_LAYOUT.replace('"variant":"slot"', '"variant":"stacked"')
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "跑步"},
                               evidence("2x4", [[0, 0, 1, 1]]), final_layout=layout) is not None


@pytest.mark.parametrize("container,limit,expected", [
    ("Row", 1, 1), ("Column", 1, 2), ("Row", 2, 4),
])
def test_text_flow_uses_declared_rows_without_a_device_viewport(container, limit, expected):
    nodes = [
        {"id": "root", "component": container, "children": ["value", "unit"], "styles": {}},
        {"id": "value", "component": "Text", "styles": {"maxLines": limit}},
        {"id": "unit", "component": "Text", "styles": {"maxLines": limit}},
    ]
    flow = photo_layout_evidence(nodes).get("textFlow", {}).get("root", {})
    assert flow.get("maxLines") == expected


@pytest.mark.parametrize("child", ["missing", "root"])
def test_text_flow_missing_or_recursive_nodes_are_unknown(child):
    nodes = [{"id": "root", "component": "Column", "children": [child]}]
    assert photo_layout_evidence(nodes).get("textFlow", {}).get("root", {}).get("maxLines") is None


@pytest.mark.parametrize("change", [
    {"maxTextLines": 0}, {"maxTextLines": "3"}, {"includeTitle": "true"},
    {"layouts": {"S-center": "left"}}, {"viewport": {"width": 123}},
    {"kind": "unknown"}, {"excludeComponents": ["CircleButton"]},
])
def test_invalid_content_eligibility_rejected_at_registry_load(change):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-sleep-square")
    photo.get("contentEligibility", {}).update(change)
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_model_cannot_bypass_sleep_line_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    nodes = sleep_nodes()
    nodes[2].get("styles", {})["maxLines"] = 4
    source = themes.encode([{"updateComponents": {"components": nodes}}])
    client = SimpleNamespace(generate=AsyncMock(return_value='{"themeId":"photo-ux-sleep-square"}'))
    result, audit = asyncio.run(themes.select_theme(
        source, sleep_task(), client, final_layout=SLEEP_LAYOUT,
    ))
    assert audit.get("themeId") != "photo-ux-sleep-square"
    assert "行数" in audit.get("rejected", {}).get("photo-ux-sleep-square", "")
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
