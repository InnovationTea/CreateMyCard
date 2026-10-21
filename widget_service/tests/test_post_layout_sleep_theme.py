"""Sleep reminder wording must not route the post-layout theme to calendar blue."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services import post_layout_theme as themes
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


def column_sleep_sample():
    task = sleep_task("看昨天白天小睡多久、晚上几点入睡和早上几点醒，打开闹钟。")
    task["dataModelSchema"] = {"data": {"healthSport": {
        "totalNapDurationText": {"type": "string", "sampleValue": "0分"},
        "fallAsleepTimeText": {"type": "string", "sampleValue": "23:15"},
        "wakeupTimeText": {"type": "string", "sampleValue": "07:30"},
    }}}
    rows = [
        ["root", "Column", {
            "width": "matchParent", "height": "matchParent", "borderRadius": 20,
            "clip": True, "alignItems": "start", "justifyContent": "start",
            "padding": 12, "itemMargin": 6,
        }, ["title", "content_flow", "action"]],
        ["title", "SingleLineTitle", {
            "title": "昨日作息", "icon": "resources/base/media/moon_z_fill_1.svg",
            "fontSize": 12, "width": "matchParent",
        }],
        ["content_flow", "Column", {
            "width": "matchParent", "layoutWeight": 1, "itemMargin": 2,
            "alignItems": "start", "justifyContent": "start",
        }, ["primary", "support"]],
        ["primary", "EmphasisText", {
            "mainText": {"path": "/data/healthSport/totalNapDurationText"},
            "fontSize": 18, "width": "matchParent",
        }],
        ["support", "SecondaryBody", {
            "items": [
                {"label": "入睡 ", "value": {"path": "/data/healthSport/fallAsleepTimeText"}},
                {"label": "醒来 ", "value": {"path": "/data/healthSport/wakeupTimeText"}},
            ], "separator": " | ", "fontSize": 14, "width": "matchParent",
        }],
        ["action", "PillButton", {
            "label": "打开闹钟", "icon": "resources/base/media/alarm_fill_1.svg",
            "onClick": [ACTION],
        }],
        ["/data/healthSport/totalNapDurationText", "0分"],
        ["/data/healthSport/fallAsleepTimeText", "23:15"],
        ["/data/healthSport/wakeupTimeText", "07:30"],
        ["/state/ready", True],
    ]
    return SimpleNamespace(
        task=task, compact="\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
    )


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
    assert audit.get("themeId") == "fusion-ball-sleep-violet"
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
