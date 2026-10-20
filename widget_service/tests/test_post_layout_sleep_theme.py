"""Sleep reminder wording must not route the post-layout theme to calendar blue."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_selection_policy as policy
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.prompt_builder import PromptBuilder
from services.theme_content_regions import photo_layout_evidence
from services.theme_style_roles import layout_phase

QUERY = "生成一个提醒按时睡觉的卡片，监测睡眠状况，显示睡眠时长，并可快速设置闹钟提醒"
ACTION = {
    "call": "clickToDeeplink",
    "args": {"intentName": "Clock", "bundleName": "com.huawei.hmos.clock",
             "abilityName": "com.huawei.hmos.clock.phone", "uri": ""},
}


def sleep_task(query=QUERY):
    return {
        "size": "2x2", "userQuery": query, "appVersion": "11.9.9.300",
        "dataModelSchema": {"data": {"healthSport": {
            "nightSleepDurationText": {"type": "string", "sampleValue": "7小时1分"},
            "sleepScore": {"type": "integer", "sampleValue": 82},
        }}},
        "eventCandidates": [{"id": "event.open.clock.alarm", **ACTION}],
    }


def sleep_layout(layout="S-title-primary-secondary-action", *, with_icon=False):
    rows = [
        ["root", "Layout", {"layout": layout},
         ["title", "primary", "support", "action"]],
        ["title", "SingleLineTitle", {"title": "按时睡觉", "fontSize": 12}],
        ["primary", "EmphasisText", {
            "mainText": {"path": "/data/healthSport/nightSleepDurationText"}, "fontSize": 18,
        }],
        ["support", "SecondaryBody", {
            "items": [{"label": "睡眠得分 ", "value": {"path": "/data/healthSport/sleepScore"}}],
            "fontSize": 14,
        }],
        ["action", "PillButton", {"label": "设置闹钟", "onClick": [ACTION]}],
        ["/data/healthSport/nightSleepDurationText", "7小时1分"],
        ["/data/healthSport/sleepScore", 82],
    ]
    if layout == "S-title-content-action":
        rows[0][3].remove("support")
        rows = [row for row in rows if row[0] != "support"]
    if with_icon:
        action = next(row for row in rows if row[0] == "action")
        action[2]["icon"] = "resources/base/media/alarm_fill_1.svg"
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("query", [QUERY, "安排睡眠监测", "活动后的睡眠情况"])
def test_sleep_reminder_theme_does_not_change_legacy_layout_route(query):
    task = sleep_task(query)
    typed = TaskSpec.model_validate(task)
    # The legacy layout selector remains unchanged; only theme routing is corrected.
    assert PromptBuilder._visual_route(typed)[0] == "calendar-event"
    evidence = policy.fusion_candidate_gate(task, sleep_layout())
    assert evidence.get("allowedTokens") == ["fusion-ball-sleep-violet"]
    assert evidence.get("visibleFieldCount") == 2
    assert evidence.get("actionCount") == 1
    assert evidence.get("businessCount") == 1


@pytest.mark.parametrize("photos_enabled", [False, True])
def test_sleep_reminder_expands_violet_without_photo_or_foreground_change(
    monkeypatch, photos_enabled,
):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", photos_enabled)
    task = sleep_task(QUERY + "，不要图片" if photos_enabled else QUERY)
    compact = sleep_layout()
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"fusion-ball-sleep-violet"}'
    ))
    final, audit = asyncio.run(themes.select_theme(source, task, client, final_layout=compact))
    assert audit.get("themeId") == "fusion-ball-sleep-violet"
    assert audit.get("selectorError") is None
    assert "fusion-ball-schedule-blue" not in audit.get("candidates", [])
    if photos_enabled:
        reason = audit.get("rejected", {}).get("photo-ux-sleep-square")
        assert reason == "用户明确其它主题或不要图片"
    assert themes.foreground_signature(source) == themes.foreground_signature(final)
    nodes = themes.components(themes.decode(final))
    by_id = {node.get("id"): node for node in nodes}
    for identity, expected in (
        ("fusionBallLarge", "#FF493D99"), ("fusionBallMedium", "#FF5536B3"),
        ("fusionBallSmall", "#FF7D6B99"),
    ):
        node = by_id.get(identity)
        assert node is not None
        assert node.get("styles", {}).get("backgroundColor") == expected
    assert "__post_theme_image" not in by_id


@pytest.mark.parametrize("layout,main_lines,body_lines", [
    ("S-title-content-action", 2, 3),
    ("S-title-content-action", 3, 4),
    ("S-title-primary-secondary-action", 1, 3),
    ("S-title-primary-secondary-action", 2, 4),
])
@pytest.mark.parametrize("with_icon", [False, True])
def test_capsule_uses_galaxy_without_three_line_limit_or_foreground_change(
    monkeypatch, layout, main_lines, body_lines, with_icon,
):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    compact = sleep_layout(layout, with_icon=with_icon)
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    messages = themes.decode(source)
    nodes = themes.components(messages)
    primary = next(node for node in nodes if node.get("id") == "primary_main")
    primary.get("styles", {})["maxLines"] = main_lines
    source = themes.encode(messages)
    flow = photo_layout_evidence(nodes).get("textFlow", {})
    assert flow.get("action", {}).get("maxLines") == 1
    assert not flow.get("action", {}).get("leftAligned")
    actual_lines = flow.get("root", {}).get("maxLines", 0)
    actual_lines -= flow.get("title", {}).get("maxLines", 0)
    assert actual_lines == body_lines
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"photo-ux-galaxy-sleep-square"}'
    ))
    final, audit = asyncio.run(themes.select_theme(
        source, sleep_task(), client, final_layout=compact,
    ))
    assert audit.get("themeId") == "photo-ux-galaxy-sleep-square"
    assert audit.get("selectorError") is None
    assert audit.get("candidates") == ["photo-ux-galaxy-sleep-square"]
    reason = audit.get("rejected", {}).get("photo-ux-sleep-square")
    assert reason == "卧室睡眠图片不允许按钮或独立可点击控件"
    assert themes.foreground_signature(source) == themes.foreground_signature(final)


@pytest.mark.parametrize("layout", ["S-title-content-action", "S-title-primary-secondary-action"])
@pytest.mark.parametrize("alignment", ["center", "end"])
def test_galaxy_sleep_does_not_restrict_content_alignment(monkeypatch, layout, alignment):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    compact = sleep_layout(layout)
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    messages = themes.decode(source)
    primary = next(node for node in themes.components(messages) if node.get("id") == "primary_main")
    primary.get("styles", {})["textAlign"] = alignment
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"photo-ux-galaxy-sleep-square"}'
    ))
    _, audit = asyncio.run(themes.select_theme(
        themes.encode(messages), sleep_task(), client, final_layout=compact,
    ))
    reason = audit.get("rejected", {}).get("photo-ux-sleep-square")
    assert reason == "卧室睡眠图片不允许按钮或独立可点击控件"
    assert audit.get("themeId") == "photo-ux-galaxy-sleep-square"


@pytest.mark.parametrize("change", [
    "no-button", "circle-only", "missing-click", "unreachable-button", "static", "mixed", "wide",
])
def test_galaxy_requires_reachable_clickable_capsule_and_real_square_sleep(change):
    task = sleep_task()
    compact = sleep_layout("S-title-content-action")
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    rows = [json.loads(line) for line in compact.splitlines()]
    root = next(row for row in rows if row[0] == "root")
    action = next(row for row in rows if row[0] == "action")
    primary = next(row for row in rows if row[0] == "primary")
    if change == "no-button":
        root[3].remove("action")
        rows.remove(action)
    elif change == "circle-only":
        action[1] = "CircleButton"
    elif change == "missing-click":
        action[2].pop("onClick")
    elif change == "unreachable-button":
        root[3].remove("action")
    elif change == "static":
        primary[2]["mainText"] = "昨晚睡得很好"
    elif change == "mixed":
        primary[2]["secondaryText"] = {"path": "/data/healthSport/dailySteps"}
    else:
        task["size"] = "2x4"
    compact = '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)
    evidence = photo_layout_evidence(themes.components(themes.decode(source)))
    photo = next(item for item in registry.registered_themes("photos")
                 if item.get("id") == "photo-ux-galaxy-sleep-square")
    assert themes.photo_reason(photo, task, evidence, final_layout=compact) is not None


def test_galaxy_does_not_require_line_count_evidence():
    compact = sleep_layout()
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    evidence = photo_layout_evidence(themes.components(themes.decode(source)))
    evidence.pop("textFlow")
    photo = next(item for item in registry.registered_themes("photos")
                 if item.get("id") == "photo-ux-galaxy-sleep-square")
    assert themes.photo_reason(photo, sleep_task(), evidence, final_layout=compact) is None


@pytest.mark.parametrize("change", ["business", "size", "circle", "line-limit"])
def test_galaxy_registry_keeps_capsule_sleep_contract(change):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-galaxy-sleep-square")
    if change == "business":
        photo["business"] = "sport"
    elif change == "size":
        photo["sizes"] = ["2x4"]
    elif change == "circle":
        photo.get("contentEligibility", {})["requiredComponent"] = "CircleButton"
    else:
        photo.get("contentEligibility", {})["maxTextLines"] = 3
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("label,limit,expected", [
    ("设置闹钟", 1, 1), ("设置闹钟", 2, 2), ("设置闹钟", None, None),
    ("设置\n闹钟", 1, None), ("", 1, None), (None, 1, None),
    ("{{ ${/data/label} }}", 1, None),
])
def test_native_button_line_evidence_is_bounded(label, limit, expected):
    nodes = [
        {"id": "root", "component": "Column", "children": ["action"]},
        {"id": "action", "component": "Button", "label": label,
         "styles": {"maxLines": limit}},
    ]
    flow = photo_layout_evidence(nodes).get("textFlow", {}).get("root", {})
    assert flow.get("maxLines") == expected


def test_mistaken_blue_selection_is_rejected_for_sleep(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    compact = sleep_layout()
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"fusion-ball-schedule-blue"}'
    ))
    _, audit = asyncio.run(themes.select_theme(source, sleep_task(), client, final_layout=compact))
    assert audit.get("themeId") == "gradient-purple"
    assert audit.get("selectorError")


def test_existing_generic_layout_route_still_excludes_fusion():
    task = sleep_task("睡眠监测，使用圆形按钮设置闹钟")
    assert PromptBuilder._visual_route(TaskSpec.model_validate(task))[0] == "generic"
    assert policy.fusion_candidate_gate(task, sleep_layout()).get("allowedTokens") == []


def test_multi_business_and_wide_gates_remain_closed():
    task = sleep_task()
    task["size"] = "2x4"
    assert policy.fusion_candidate_gate(task, sleep_layout()).get("allowedTokens") == []
    task["size"] = "2x2"
    schema = task.get("dataModelSchema", {}).get("data", {})
    schema["calendar"] = {"title": {"type": "string"}}
    assert policy.fusion_candidate_gate(task, sleep_layout()).get("allowedTokens") == []
