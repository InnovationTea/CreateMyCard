"""日程条目点击的转换、归属、动作实例及旧行为回归。"""

import copy
import json

import pytest
from services.compact_action_instances import (
    action_instance_instruction,
    plan_action_candidates,
    plan_action_handlers,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.compact_plan import (
    build_compact_plan_tool,
    compact_plan_action_ids,
    compact_plan_context,
    compact_plan_coverage_errors,
    parse_compact_plan_call,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.protocol_registry import A2UIProtocolRegistry


def _path(index: int, name: str) -> str:
    return f"/data/calendar/events/{index}/{name}"


def _handler(index: int) -> dict:
    return {
        "call": "clickToIntent",
        "args": {
            "intentName": "ViewCalendarEvent",
            "params": {"entityId": "{{ ${" + _path(index, "entityId") + "} }}"},
        },
    }


def _task() -> dict:
    events = []
    candidates = []
    for index in range(3):
        events.append(
            {
                "title": {"type": "string", "description": "标题", "sampleValue": f"日程{index}"},
                "time": {"type": "string", "description": "时间", "sampleValue": "10:00"},
                "entityId": {"type": "string", "description": "标识", "sampleValue": f"id-{index}"},
            }
        )
        candidates.append({"id": "event.viewCalendarEvent", **_handler(index)})
    return {
        "userQuery": "显示两条日程的标题和时间，点击日程查看对应详情",
        "size": "2x4",
        "appVersion": "11.7.8.353",
        "dataModelSchema": {"data": {"calendar": {"events": events}}},
        "eventCandidates": candidates,
        "assetCandidates": [{"id": "asset.calendar", "src": "resources/calendar.svg"}],
    }


def _plan(task: dict, size: str = "2x4", count: int = 2) -> dict:
    facts = []
    actions = []
    references = compact_plan_action_ids(task)
    for index in range(count):
        for name in ("title", "time"):
            facts.append(
                {
                    "requirement": f"日程{index}{name}",
                    "dataId": _path(index, name),
                    "componentHints": ["EventCard"],
                }
            )
        facts.append(
            {
                "requirement": f"查看日程{index}",
                "actionId": references[index],
                "componentHints": ["EventCard"],
            }
        )
        actions.append({"actionId": references[index], "assetId": None, "reason": "条目点击"})
    call = {
        "name": "submit_card_plan",
        "arguments": {
            "info_required": facts,
            "layoutHints": ["W-top-bottom"] if size == "2x4" else ["S-title-content"],
            "assetAssignments": {
                "actions": actions,
                "title": {"assetId": None, "reason": "无图标标题"},
            },
        },
    }
    return parse_compact_plan_call(json.dumps(call, ensure_ascii=False), task).plan


def _source(*, clicks: bool = True, wrong_index: int | None = None) -> str:
    items = []
    rows = [
        [
            "root",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
            },
            ["events"],
        ]
    ]
    for index in range(2):
        item = {"title": {"path": _path(index, "title")}, "time": {"path": _path(index, "time")}}
        if clicks:
            target = wrong_index if index == 1 and wrong_index is not None else index
            item["onClick"] = [_handler(target)]
        items.append(item)
        rows.append([_path(index, "title"), f"日程{index}"])
        rows.append([_path(index, "time"), "10:00"])
    rows.insert(1, ["events", "EventCard", {"items": items, "fontColor": "#FF112233"}])
    for index in range(3):
        rows.append([_path(index, "entityId"), f"id-{index}"])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _process(source: str, task: dict, plan: dict | None = None):
    return DesignCompactProcessor().process(
        source,
        DslProcessingContext(
            size="2x4",
            task_spec=task,
            card_spec={"suggestSize": "2x4"},
            compact_plan=plan,
            protocol_profile={"id": "a2ui-form-rom6.0-v1", "version": "v0.9"},
        ),
    )


def _components(source: str) -> list[dict]:
    messages = convert_compact_dsl_to_a2ui(source, size="2x4").splitlines()
    update = json.loads(messages[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    return components


def test_same_event_id_keeps_each_candidate_and_exposes_internal_references() -> None:
    task = _task()
    original = copy.deepcopy(task)
    references = compact_plan_action_ids(task)
    assert len(references) == 3 and len(set(references)) == 3
    handlers = plan_action_handlers(task)
    for index, reference in enumerate(references):
        assert handlers.get(reference) == _handler(index)
    tool_text = json.dumps(build_compact_plan_tool(task), ensure_ascii=False)
    for reference in references:
        assert reference in tool_text
    assert task == original


def test_unique_event_keeps_original_id_and_collision_does_not_overwrite() -> None:
    task = _task()
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    candidates.append({"id": "event.viewCalendarEvent#candidate-0", **_handler(0)})
    mapping = plan_action_candidates(task)
    assert len(mapping) == 4
    assert mapping.get("event.viewCalendarEvent#candidate-0") == candidates[3]
    task["eventCandidates"] = [candidates[0]]
    assert compact_plan_action_ids(task) == ("event.viewCalendarEvent",)


def test_identical_candidates_keep_one_original_reference() -> None:
    task = _task()
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    task["eventCandidates"] = [candidates[0], copy.deepcopy(candidates[0])]
    assert compact_plan_action_ids(task) == ("event.viewCalendarEvent",)


def test_unrelated_unique_action_keeps_original_plan_instruction() -> None:
    task = {
        "eventCandidates": [
            {
                "id": "event.startNavigate",
                "call": "startNavigate",
                "args": {"destination": "home"},
            }
        ]
    }
    assert action_instance_instruction(task) == ""
    assert compact_plan_action_ids(task) == ("event.startNavigate",)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_item_details_do_not_force_independent_action_layout(size: str) -> None:
    task = _task()
    task["size"] = size
    plan = _plan(task, size)
    expected = ["W-top-bottom"] if size == "2x4" else ["S-title-content"]
    assert plan.get("layoutHints") == expected
    assignments = plan.get("assetAssignments")
    assert isinstance(assignments, dict)
    actions = assignments.get("actions")
    assert isinstance(actions, list)
    assert all(action.get("assetId") is None for action in actions)


@pytest.mark.parametrize("item_count", [1, 2])
@pytest.mark.parametrize("with_button", [False, True])
def test_stale_dual_action_hint_does_not_count_item_clicks_as_buttons(
    item_count: int, with_button: bool,
) -> None:
    task = _task()
    task["size"] = "2x2"
    plan = _plan(task, "2x2", item_count)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    if with_button:
        facts.append({
            "requirement": "独立操作",
            "actionId": "event.independent",
            "componentHints": ["CardButton"],
        })
    plan["layoutHints"] = ["S-content-dual-action"]
    context = compact_plan_context(plan, implementation_conflicts=[])
    assert "成为固定布局" not in context
    assert "actions-only 变体" not in context


def test_item_clicks_fulfill_only_selected_instances_and_survive_pipeline() -> None:
    task = _task()
    plan = _plan(task)
    result = _process(_source(), task, plan)
    assert not result.errors
    assert result.standard_dsl
    assert not compact_plan_coverage_errors(_source(), plan, task)
    components = _components(_source())
    clicks = {row.get("id"): row.get("onClick") for row in components if row.get("onClick")}
    assert clicks == {"events_item0": [_handler(0)], "events_item1": [_handler(1)]}
    assert all(row.get("component") != "Button" for row in components)


def test_third_candidate_cannot_silently_replace_second_selected_action() -> None:
    task = _task()
    errors = compact_plan_coverage_errors(_source(wrong_index=2), _plan(task), task)
    assert any("action is missing" in error and "candidate-1" in error for error in errors)


def test_three_selected_item_actions_cannot_use_two_button_omission_exception() -> None:
    task = _task()
    errors = compact_plan_coverage_errors(_source(), _plan(task, count=3), task)
    assert any("candidate-2" in error for error in errors)


def test_click_parameter_is_not_counted_as_a_visible_fact() -> None:
    task = _task()
    plan = _plan(task)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"requirement": "显式要求展示标识", "dataId": _path(0, "entityId")})
    errors = compact_plan_coverage_errors(_source(), plan, task)
    assert any("Plan fact is missing" in error and "entityId" in error for error in errors)


def test_formal_top_bottom_layout_accepts_item_actions_without_button_slots() -> None:
    task = _task()
    rows = [json.loads(line) for line in _source().splitlines()]
    rows[0] = ["root", "Layout", {"layout": "W-top-bottom"}, ["events", "details"]]
    rows.insert(
        2,
        [
            "details",
            "TextBlock",
            {
                "items": [
                    {"label": "范围", "value": "近期日程"},
                    {"label": "顺序", "value": "由近到远"},
                ]
            },
        ],
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = DesignCompactProcessor().process(
        source,
        DslProcessingContext(
            size="2x4",
            task_spec=task,
            card_spec={"suggestSize": "2x4"},
            compact_plan=_plan(task),
            protocol_profile=A2UIProtocolRegistry().get_profile(),
            layout_scope="W-plan-guided",
        ),
    )
    assert not result.errors
    assert result.standard_dsl


@pytest.mark.parametrize("target", [0, 2, 9])
def test_wrong_or_unregistered_detail_target_is_rejected(target: int) -> None:
    result = _process(_source(wrong_index=target), _task())
    assert result.errors
    assert any("same displayed array record" in issue.message for issue in result.errors)


def test_click_changes_no_existing_event_card_geometry() -> None:
    plain = _components(_source(clicks=False))
    clickable = _components(_source())
    for row in clickable:
        row.pop("onClick", None)
    assert clickable == plain
    assert not _process(_source(clicks=False), _task()).errors


@pytest.mark.parametrize("click", [[], [{"call": "x", "args": {}}] * 2, [{}]])
def test_invalid_item_handler_shape_is_rejected(click: list) -> None:
    rows = [json.loads(line) for line in _source().splitlines()]
    props = rows[1][2]
    items = props.get("items")
    assert isinstance(items, list)
    items[0]["onClick"] = click
    source = "\n".join(json.dumps(row) for row in rows)
    with pytest.raises(CompactDslConversionError, match="onClick"):
        convert_compact_dsl_to_a2ui(source, size="2x4")


def test_side_effect_candidate_is_not_allowed_as_item_detail() -> None:
    task = _task()
    call = {"call": "startNavigate", "args": {"destination": "home"}}
    task["eventCandidates"] = [{"id": "event.startNavigate", **call}]
    source = _source().replace(json.dumps(_handler(0)), json.dumps(call))
    assert _process(source, task).errors


def test_duplicate_detail_button_is_rejected() -> None:
    rows = [json.loads(line) for line in _source().splitlines()]
    rows[0][3].append("detail")
    rows.insert(2, ["detail", "CardButton", {"label": "查看日程", "onClick": [_handler(0)]}])
    source = "\n".join(json.dumps(row) for row in rows)
    result = _process(source, _task())
    assert any("duplicate detail entry" in issue.message for issue in result.errors)
