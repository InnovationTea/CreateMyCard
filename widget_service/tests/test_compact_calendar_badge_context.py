"""集合数量与相邻标题构成可理解单元；不跨卡片区域借上下文。"""

import json

import pytest

from services.card_validation.compact_validation.semantic.display import (
    _collect_semantic_text_errors,
)
from services.compact_component_runtime import visual_recipe_part
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_plan import parse_compact_plan_call
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def _count(*, badge: bool = True, content=None) -> ComponentRow:
    if content is None:
        content = {"path": "/data/calendar/eventCount"}
    props = {"content": content}
    if badge:
        _, styles = visual_recipe_part("Badge", "root", size="2x4")
        props.update(styles)
    return ComponentRow("count", "Text", props, ())


def _errors(rows: list[ComponentRow], *, size="2x4") -> list[str]:
    errors = []
    _collect_semantic_text_errors(rows, {"size": size}, errors)
    return errors


@pytest.mark.parametrize("wrapped", [False, True])
def test_count_badge_accepts_same_row_title_scope(wrapped: bool) -> None:
    rows = [ComponentRow("title", "SingleLineTitle", {"title": "未来3天日程"}, ())]
    sibling = "title"
    if wrapped:
        sibling = "title_slot"
        rows.append(ComponentRow(sibling, "Column", {}, ("title",)))
    rows.extend([ComponentRow("header", "Row", {}, (sibling, "count")), _count()])
    assert not _errors(rows)


@pytest.mark.parametrize("title", ["日程", "未来3天", "设备概览", ""])
def test_count_badge_rejects_title_without_scope_or_collection(title: str) -> None:
    rows = [
        ComponentRow("header", "Row", {}, ("title", "count")),
        ComponentRow("title", "SingleLineTitle", {"title": title}, ()),
        _count(),
    ]
    assert any("calendar eventCount" in error for error in _errors(rows))


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_count_cannot_borrow_title_from_another_region(size: str) -> None:
    rows = [
        ComponentRow("root", "Row", {}, ("left", "right")),
        ComponentRow("left", "Column", {}, ("title",)),
        ComponentRow("right", "Column", {}, ("count",)),
        ComponentRow("title", "SingleLineTitle", {"title": "未来3天日程"}, ()),
        _count(),
    ]
    assert any("calendar eventCount" in error for error in _errors(rows, size=size))


def test_non_badge_readout_cannot_borrow_title() -> None:
    rows = [
        ComponentRow("header", "Row", {}, ("title", "count")),
        ComponentRow("title", "SingleLineTitle", {"title": "未来3天日程"}, ()),
        _count(badge=False),
    ]
    assert any("calendar eventCount" in error for error in _errors(rows))


def test_small_card_keeps_existing_count_policy() -> None:
    rows = [
        ComponentRow("header", "Row", {}, ("title", "count")),
        ComponentRow("title", "SingleLineTitle", {"title": "未来3天日程"}, ()),
        _count(),
    ]
    assert any("calendar eventCount" in error for error in _errors(rows, size="2x2"))


def test_wide_badge_wraps_its_full_number_without_changing_small_recipe() -> None:
    _, wide = visual_recipe_part("Badge", "root", size="2x4")
    _, small = visual_recipe_part("Badge", "root", size="2x2")
    assert wide.get("width") == "wrapContent"
    assert "width" not in small
    assert wide.get("padding") == small.get("padding")
    assert wide.get("fontSize") == small.get("fontSize")


def test_preferred_badge_is_not_rewritten_as_a_mandatory_title() -> None:
    task = {"size": "2x4", "userQuery": "查看未来3天日程数量", "eventCandidates": [],
            "dataModelSchema": {"data": {"calendar": {
                "eventCount": {"type": "integer", "sampleValue": 4},
            }}}}
    raw = {"name": "submit_card_plan", "arguments": {"info_required": [{
        "requirement": "未来3天日程数量", "priority": "must",
        "dataId": "/data/calendar/eventCount",
        "componentHints": ["Badge", "EmphasisText", "SingleLineTitle"],
    }]}}
    result = parse_compact_plan_call(json.dumps(raw, ensure_ascii=False), task)
    facts = result.plan.get("info_required")
    assert facts and facts[0].get("componentHints") == ["Badge", "EmphasisText"]
    assert facts[0].get("dataId") == "/data/calendar/eventCount"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_complete_count_sentence_remains_valid(size: str) -> None:
    value = "{{ '未来3天 ' + ${/data/calendar/eventCount} + '项日程' }}"
    assert not _errors([_count(badge=False, content=value)], size=size)


def test_semantic_calendar_header_and_dual_actions_pass_processor() -> None:
    actions = [
        {"call": "clickToDeeplink", "args": {"uri": "example://calendar"}},
        {"call": "clickToDeeplink", "args": {"uri": "example://focus"}},
    ]
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"},
         ["body", "detail", "focus"]],
        ["body", "Region", {"variant": "title-primary-details"},
         ["header", "event", "status"]],
        ["header", "Group", {"variant": "title-count"}, ["title", "count"]],
        ["title", "SingleLineTitle", {"title": "未来3天日程", "fontSize": 12}],
        ["count", "Badge", {"value": {"path": "/data/calendar/eventCount"},
         "backgroundColor": "#338C4B1C"}],
        ["event", "EventCard", {"items": [{
            "title": {"path": "/data/calendar/events/0/title"},
            "time": {"path": "/data/calendar/events/0/dtStart"},
        }]}],
        ["status", "SecondaryBody", {"fontSize": 14,
         "items": [{"value": "{{ ${/data/calendar/events/0/isAllDay} ? '全天' : '非全天' }}"}]}],
        ["detail", "CardButton", {"label": "查看详情", "onClick": [actions[0]]}],
        ["focus", "CardButton", {"label": "打开专注", "onClick": [actions[1]]}],
        ["/data/calendar/eventCount", 4],
        ["/data/calendar/events/0/title", "读书交流"],
        ["/data/calendar/events/0/dtStart", "09:30"],
        ["/data/calendar/events/0/isAllDay", False],
    ]
    task = {
        "size": "2x4", "appVersion": "12.0.0.1", "assetCandidates": [],
        "eventCandidates": actions,
        "dataModelSchema": {"data": {"calendar": {
            "eventCount": {"type": "integer", "sampleValue": 4},
            "events": [{
                "title": {"type": "string", "sampleValue": "读书交流"},
                "dtStart": {"type": "string", "sampleValue": "09:30"},
                "isAllDay": {"type": "boolean", "sampleValue": False},
            }],
        }}},
    }
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = DesignCompactProcessor().process(source, DslProcessingContext(
        size="2x4", card_spec={}, task_spec=task, protocol_profile={},
        layout_scope="W-plan-guided",
    ))
    assert not result.errors, [error.message for error in result.errors]
    assert result.standard_dsl
