"""会议图片准入按当前正文计数，不计按钮文案或maxLines预算。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.compact_composition_context import small_card_display_text
from services.display_text import concatenated_display_text
from services.theme_content_regions import photo_layout_evidence
from test_autumn_calendar_photos import calendar_sample, expanded
from test_uniform_photo_eligibility import rejection

CALENDAR_ID = "photo-ux-texture-blue-diamond-square"
CALENDAR_IDS = {
    "photo-ux-meeting-room-square",
}


def event_sample(title="项目例会", time="{{ ${/data/calendar/events/0/dtStart} + ' - ' "
                 "+ ${/data/calendar/events/0/dtEnd} }}"):
    prefix = "/data/calendar/events/0/"
    rows = [
        ["root", "Layout", {"layout": "S-title-content-action"}, ["header", "event", "cta"]],
        ["header", "SingleLineTitle", {"title": "日程安排"}],
        ["event", "EventCard", {"items": [{"title": {"path": prefix + "title"}, "time": time}]}],
        ["cta", "PillButton", {"label": "查看日程",
                               "icon": "resources/base/media/calendar_fill.svg",
                               "onClick": [{"call": "clickToIntent", "args": {
                                   "intentName": "ViewCalendarEvent", "params": {
                                       "entityId": "{{ ${" + prefix + "entityId} }}",
                                   },
                               }}]}],
        [prefix + "title", title], [prefix + "dtStart", "14:00"],
        [prefix + "dtEnd", "15:00"], [prefix + "entityId", "example-event"],
    ]
    task = {"size": "2x2", "userQuery": "展示日程安排", "appVersion": "11.7.7.323",
            "dataModelSchema": {"data": {"calendar": {"events": [{
                "title": {"type": "string", "sampleValue": "旧数据不参与计数"},
            }]}}}}
    return expanded(rows, task)


def evidence_for(sample):
    data = themes.decode(sample.source)[-1].get("updateDataModel", {}).get("value")
    return photo_layout_evidence(sample.nodes, data)


def test_supplied_event_card_has_two_current_body_lines_not_four():
    sample = event_sample()
    evidence = evidence_for(sample)
    assert evidence.get("textFlow", {}).get("event", {}).get("maxLines") == 3
    current = evidence.get("bodyTextFlow", {})
    assert current.get("event", {}).get("lineCount") == 2
    assert current.get("cta", {}).get("lineCount") == 0
    assert current.get("event", {}).get("basis") == "current-text"
    assert evidence.get("deviceGeometryKnown") is False
    assert rejection(sample, CALENDAR_ID) is None


@pytest.mark.parametrize("title,allowed", [
    ("项目例会", True), ("项目\n例会", True), ("项目\r\n例会", True),
    ("项目\r例会", True), ("项目例会\n", True),
])
def test_current_values_and_explicit_newlines_control_body_admission(title, allowed):
    assert (rejection(event_sample(title), CALENDAR_ID) is None) is allowed


@pytest.mark.parametrize("change", ["missing-data", "complex-expression", "missing-node"])
def test_unresolved_current_text_is_not_treated_as_one_line(change):
    sample = event_sample()
    if change == "missing-data":
        records = themes.decode(sample.source)
        records[-1].get("updateDataModel", {}).get("value", {}).clear()
        sample.source = themes.encode(records)
    elif change == "complex-expression":
        title = next(node for node in sample.nodes if node.get("id") == "event_title")
        title["content"] = "{{ ${/data/calendar/events/0/title} ? 'a' : 'b' }}"
    else:
        sample.nodes = [node for node in sample.nodes if node.get("id") != "event_title"]
    assert rejection(sample, CALENDAR_ID) == "无法确认图片正文行数"


@pytest.mark.parametrize("enabled", [False, True])
def test_event_card_selection_preserves_layout_and_actions(monkeypatch, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    sample = event_sample()
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": CALENDAR_ID})))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert (audit.get("themeId") in CALENDAR_IDS) is enabled
    assert themes.foreground_signature(result) == themes.foreground_signature(sample.source)
    if enabled:
        assert set(audit.get("candidates", [])) == CALENDAR_IDS


@pytest.mark.parametrize("nested", [False, True])
def test_button_subtree_and_header_do_not_contribute_lines(nested):
    sample = event_sample()
    header = next(node for node in sample.nodes if node.get("id") == "header_title")
    header["content"] = "标题\n第二行\n第三行"
    header.get("styles", {})["maxLines"] = 3
    label = next(node for node in sample.nodes if node.get("id") == "cta_text")
    label["content"] = "{{ ${/missing/button/text} }}"
    if nested:
        button = next(node for node in sample.nodes if node.get("id") == "cta")
        button["id"] = "nested_button"
        sample.nodes.append({"id": "cta", "component": "Column", "children": ["nested_button"],
                             "styles": {"alignItems": "start"}})
    assert rejection(sample, CALENDAR_ID) is None


def test_whole_card_click_does_not_hide_body_overflow():
    sample = event_sample("项目\n例会")
    for node in sample.nodes:
        if node.get("id") == "event_title":
            node["content"] = "第一行\n第二行\n第三行"
            node.get("styles", {})["maxLines"] = 3
    root = next(node for node in sample.nodes if node.get("id") == "root")
    root["onClick"] = [{"call": "open"}]
    assert rejection(sample, CALENDAR_ID) == "图片正文超过3行（不含顶部标题和按钮文案）"


def test_body_text_evidence_does_not_mutate_nodes_or_change_existing_upper_bounds():
    sample = event_sample()
    original = copy.deepcopy(sample.nodes)
    evidence = evidence_for(sample)
    assert sample.nodes == original
    assert evidence.get("textFlow") == photo_layout_evidence(sample.nodes).get("textFlow")
    assert "bodyTextFlow" not in photo_layout_evidence(sample.nodes)


@pytest.mark.parametrize("kind,count", [("Row", 2), ("Column", 3), ("Stack", None)])
def test_body_flow_respects_horizontal_vertical_and_ambiguous_stacking(kind, count):
    nodes = [
        {"id": "root", "component": kind, "children": ["first", "second"],
         "styles": {"width": "matchParent", "height": "matchParent", "alignContent": "topStart"}},
        {"id": "first", "component": "Text", "content": "a\nb", "styles": {"maxLines": 4}},
        {"id": "second", "component": "Text", "content": "c", "styles": {"maxLines": 3}},
    ]
    flow = photo_layout_evidence(nodes, {}).get("bodyTextFlow", {})
    assert flow.get("root", {}).get("lineCount") == count


def test_explicit_clipping_caps_current_lines_without_changing_layout():
    sample = event_sample("项目\n例会")
    title = next(node for node in sample.nodes if node.get("id") == "event_title")
    title.get("styles", {})["maxLines"] = 1
    assert rejection(sample, CALENDAR_ID) is None
    assert title.get("content") == "{{ ${/data/calendar/events/0/title} }}"


def test_two_line_body_with_capsule_is_now_allowed():
    sample = calendar_sample("S-title-primary-secondary-action", "PillButton")
    assert rejection(sample, CALENDAR_ID) is None


@pytest.mark.parametrize("value,expected", [
    ("plain\ntext", "plain\ntext"),
    ("", ""),
    ("{{ ${/data/title} }}", "meeting"),
    ("{{ ${/data/start} + ' - ' + ${/data/end} }}", "14:00 - 15:00"),
    ("{{ 'title\\n' + ${/data/title} }}", "title\nmeeting"),
    ("{{ ${/data/count} }}", "0"),
    ("{{ ${/data/count} + ' days' }}", "0 days"),
    ("{{ ${/data/count} + ${/data/count} }}", None),
    ("{{ ${/missing} }}", None),
    ("{{ ${/data/flag} }}", None),
    ("{{ ${/data/count} ? 'a' : 'b' }}", None),
    ("{{ __import__('os').system('echo forbidden') }}", None),
    ("{{ ${/data/title}", None),
])
def test_current_display_text_uses_restricted_existing_concatenation(value, expected):
    values = {"/data/title": "meeting", "/data/start": "14:00", "/data/end": "15:00",
              "/data/count": 0, "/data/flag": True}
    assert concatenated_display_text(value, values.get) == expected


@pytest.mark.parametrize("value,expected", [
    ("{{ ${/data/count} + ' days' }}", "3 days"),
    ("{{ ${/data/start} + ' - ' + ${/data/end} }}", "14:00 - 15:00"),
    ("{{ ${/data/count} + ${/data/count} }}", None),
    ("{{ ${/data/count} == 3 ? 'a' : 'longer' }}", "longer"),
    ("{{ ${/data/flag} ? 'a' : 'longer' }}", "longer"),
])
def test_composition_text_pressure_retains_existing_semantics(value, expected):
    task = {"dataModelSchema": {"data": {
        "count": {"type": "integer", "sampleValue": 3},
        "start": {"type": "string", "sampleValue": "14:00"},
        "end": {"type": "string", "sampleValue": "15:00"},
        "flag": {"type": "boolean", "sampleValue": True},
    }}}
    assert small_card_display_text(value, task) == expected
