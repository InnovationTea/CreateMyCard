# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""重复动作的完整处理、既有修复路由和动态参数反馈集成回归。"""

import copy
import json
import socket
from dataclasses import replace

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    parse_compact_dsl_rows,
    serialize_compact_dsl_source,
)
from services.compact_plan import evaluate_compact_plan_coverage
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.prompt_builder import PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID

_URI = "{{ 'weather://details?city=' + ${/data/location/cityCode} }}"
_HANDLER = {
    "call": "clickToDeeplink",
    "args": {"intentName": "Weather_CityCode", "uri": _URI},
}


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("duplicate action tests must not access network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr("services.generation_pipeline.report_ops_metrics", lambda **_: None)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)


def _source(rows):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _case(*, fixed_slots=False):
    facts = [
        {"text": "晴天", "requirement": "当前天气", "priority": "must"},
        {"actionId": "event.weather", "requirement": "查看天气", "priority": "must"},
    ]
    task = {
        "size": "2x4", "appVersion": "99.0", "userQuery": "显示晴天并查看天气详情",
        "dataModelSchema": {"data": {"location": {
            "cityCode": {"type": "string", "sampleValue": "city-current"},
        }}},
        "eventCandidates": [{"id": "event.weather", **copy.deepcopy(_HANDLER)}],
        "assetCandidates": [],
    }
    if fixed_slots:
        rows = [
            ["root", "Layout", {"layout": "W-content-side-slots"},
             ["content", "upper", "lower"]],
            ["content", "Region", {"variant": "center"}, ["body"]],
            ["body", "EmphasisText", {"mainText": "晴天", "fontSize": 18}],
            ["upper", "CardButton", {"label": "天气详情", "onClick": [copy.deepcopy(_HANDLER)]}],
            ["lower", "CardButton", {"label": "天气详情", "onClick": [copy.deepcopy(_HANDLER)]}],
        ]
    else:
        rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]]]
        for name in ("left", "right"):
            rows.extend([
                [name, "Region", {"variant": "title-content-action"},
                 [f"{name}_title", f"{name}_body", f"{name}_action"]],
                [f"{name}_title", "SingleLineTitle", {"title": "天气"}],
                [f"{name}_body", "EmphasisText", {"mainText": "晴天", "fontSize": 18}],
                [f"{name}_action", "PillButton", {
                    "label": "查看天气", "onClick": [copy.deepcopy(_HANDLER)],
                }],
            ])
    rows.append(["/data/location/cityCode", "city-current"])
    context = DslProcessingContext(
        size="2x4", card_spec={"suggestSize": "2x4"}, task_spec=task,
        protocol_profile={}, event_candidates=task.get("eventCandidates", []),
        compact_plan={"info_required": facts}, colorless_layout=True,
    )
    return rows, context


def _action_issue(source, context):
    result = DesignCompactProcessor().process(source, context)
    matches = []
    for issue in result.errors:
        payload = issue.to_prompt_payload()
        if payload.get("duplicateActions"):
            matches.append(payload)
    assert matches, [issue.repair_message() for issue in result.errors]
    return matches[0]


def _component_map(source):
    result = {}
    for row in parse_compact_dsl_rows(source, expand_layouts=False):
        if isinstance(row, ComponentRow):
            result[row.component_id] = row
    return result


@pytest.mark.parametrize("fixed_slots", [False, True])
@pytest.mark.parametrize("deterministic_repair", [False, True])
def test_full_processor_reports_duplicates_without_rewriting_buttons(
    monkeypatch, fixed_slots, deterministic_repair,
):
    rows, context = _case(fixed_slots=fixed_slots)
    source = _source(rows)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair",
                        deterministic_repair)
    result = DesignCompactProcessor().process(source, context)
    assert result.errors
    duplicate_issues = []
    for issue in result.errors:
        if issue.prompt_context.get("duplicateActions"):
            duplicate_issues.append(issue.to_prompt_payload())
    assert len(duplicate_issues) == 1

    before = _component_map(source)
    after = _component_map(result.source_dsl)
    assert after == before
    assert serialize_compact_dsl_source(result.source_dsl) == serialize_compact_dsl_source(source)
    button_type = "CardButton" if fixed_slots else "PillButton"
    buttons = [row for row in after.values() if row.component_type == button_type]
    assert len(buttons) == 2
    for button in buttons:
        assert button.props.get("onClick") == [_HANDLER]
    strategy = CompactRepairStrategyTracker().next_directive(source, duplicate_issues)
    expected = "parent_layout_recompose" if fixed_slots else "deduplicate_visible_actions"
    assert strategy.repair_strategy == expected
    assert strategy.retryable is True
    assert strategy.optional_drop is None
    again = DesignCompactProcessor().process(result.source_dsl, context)
    assert again.errors == result.errors
    assert again.source_dsl == result.source_dsl


def test_different_content_regions_are_diagnosed_without_automatic_action_removal():
    rows, context = _case()
    rows[7][2]["mainText"] = "明天多云"
    source = _source(rows)
    result = DesignCompactProcessor().process(source, context)
    assert result.errors
    assert any(issue.prompt_context.get("duplicateActions") for issue in result.errors)
    assert serialize_compact_dsl_source(result.source_dsl) == serialize_compact_dsl_source(source)


def test_duplicate_action_and_other_contract_failures_are_both_reported():
    rows, context = _case()
    for index in (4, 8):
        rows[index][2]["label"] = "查看当前天气详情"
    source = _source(rows)
    result = DesignCompactProcessor().process(source, context)
    assert result.errors
    assert any("at most 5 visible characters" in issue.message for issue in result.errors)
    assert any(issue.prompt_context.get("duplicateActions") for issue in result.errors)
    assert serialize_compact_dsl_source(result.source_dsl) == serialize_compact_dsl_source(source)


@pytest.mark.parametrize("fixed_slots", [False, True])
def test_duplicate_action_diagnostic_is_separate_and_keeps_full_handler(monkeypatch, fixed_slots):
    rows, context = _case(fixed_slots=fixed_slots)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    issue = _action_issue(_source(rows), context)
    assert issue.get("code") == "COMPACT_PLAN_COVERAGE_FAILED"
    assert not issue.get("duplicateFacts")
    actions = issue.get("duplicateActions")
    assert isinstance(actions, list) and len(actions) == 1
    action = actions[0]
    assert action.get("actionId") == "event.weather"
    assert action.get("factIndex") == 1
    assert action.get("expectedVisibleCount") == 1
    assert action.get("actualVisibleCount") == 2
    occurrences = action.get("occurrences")
    assert isinstance(occurrences, list) and len(occurrences) == 2
    for occurrence in occurrences:
        assert occurrence.get("property") == "onClick"
        assert occurrence.get("onClick") == [_HANDLER]
        assert occurrence.get("parentId")
        assert occurrence.get("parentRole")
        assert occurrence.get("fixedRequiredSlot") is fixed_slots


@pytest.mark.parametrize("change", ["unknown_handler", "different_parameters"])
def test_unregistered_or_different_execution_parameters_are_not_deduplicated(change):
    rows, context = _case()
    if change == "unknown_handler":
        for index in (4, 8):
            rows[index][2]["onClick"] = [{"call": "unknownAction", "args": {"target": "same"}}]
    else:
        right = copy.deepcopy(_HANDLER)
        args = right.get("args")
        assert isinstance(args, dict)
        args["uri"] = "{{ 'weather://details?other=' + ${/data/location/cityCode} }}"
        rows[8][2]["onClick"] = [right]
    coverage = evaluate_compact_plan_coverage(
        _source(rows), context.compact_plan, context.task_spec,
    )
    assert coverage.duplicate_actions == ()
    if change == "unknown_handler":
        assert any("Plan action is missing" in error for error in coverage.errors)


def test_two_distinct_registered_actions_succeed_without_recovery(monkeypatch):
    rows, context = _case()
    second = copy.deepcopy(_HANDLER)
    args = second.get("args")
    assert isinstance(args, dict)
    args["uri"] = "{{ 'weather://hourly?city=' + ${/data/location/cityCode} }}"
    rows[8][2]["onClick"] = [second]
    plan = copy.deepcopy(context.compact_plan)
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "event.hourly", "requirement": "逐小时天气", "priority": "must"})
    task = copy.deepcopy(context.task_spec)
    events = task.get("eventCandidates")
    assert isinstance(events, list)
    events.append({"id": "event.hourly", **second})
    context = replace(context, compact_plan=plan, task_spec=task, event_candidates=events)

    def forbidden(*_args, **_kwargs):
        pytest.fail("valid distinct actions must not enter recovery")

    monkeypatch.setattr(DesignCompactProcessor, "_repair_duplicate_display", forbidden)
    source = _source(rows)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors, [issue.repair_message() for issue in result.errors]
    assert serialize_compact_dsl_source(result.source_dsl) == serialize_compact_dsl_source(source)
    assert _URI in result.standard_dsl
    assert "weather://hourly?city=" in result.standard_dsl


@pytest.mark.parametrize("fixed_slots", [False, True])
def test_template_skip_does_not_apply_duplicate_action_gate_or_recovery(monkeypatch, fixed_slots):
    rows, context = _case(fixed_slots=fixed_slots)
    context = replace(context, skip_compact_dsl_validation=True)

    def forbidden(*_args, **_kwargs):
        pytest.fail("template skip must not enter duplicate action recovery")

    monkeypatch.setattr(DesignCompactProcessor, "_repair_duplicate_display", forbidden)
    source = _source(rows)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors, [issue.repair_message() for issue in result.errors]
    assert result.standard_dsl
    assert serialize_compact_dsl_source(result.source_dsl) == serialize_compact_dsl_source(source)


@pytest.mark.parametrize("fixed_slots", [False, True])
def test_mixed_capacity_and_duplicate_stay_targeted_until_original_budget(monkeypatch, fixed_slots):
    rows, context = _case(fixed_slots=fixed_slots)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    source = _source(rows)
    issue = _action_issue(source, context)
    capacity = {
        "stage": "validation", "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        "message": "component body: vertical layout requires at least 150vp within 126vp.",
    }
    original_issue = copy.deepcopy(issue)
    tracker = CompactRepairStrategyTracker(max_repair_attempts=3, capacity_recovery=True)
    expected_scope = "parent_layout" if fixed_slots else "information_group"
    expected_strategy = "parent_layout_recompose" if fixed_slots else "deduplicate_visible_actions"
    directives = []
    for _ in range(3):
        directive = tracker.next_directive(source, [capacity, issue],
                                          compact_plan=context.compact_plan,
                                          task_spec=context.task_spec)
        directives.append(directive)
        assert directive.category == "plan_coverage"
        assert directive.scope == expected_scope
        assert directive.repair_strategy == expected_strategy
        assert directive.retryable is True
        assert directive.optional_drop is None
        assert directive.approved_omitted_fact_indexes == ()
        assert directive.fallback_stage is None
    assert directives[1].no_progress is True
    exhausted = tracker.next_directive(source, [capacity, issue],
                                       compact_plan=context.compact_plan,
                                       task_spec=context.task_spec)
    assert exhausted.retryable is False
    assert exhausted.repair_strategy == "exhausted"
    assert exhausted.stop_reason == "global_attempt_limit"
    assert exhausted.scope == expected_scope
    assert issue == original_issue


def test_decreased_duplicate_count_is_progress_even_when_error_text_is_unchanged(monkeypatch):
    rows, context = _case()
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    issue = _action_issue(_source(rows), context)
    first = copy.deepcopy(issue)
    actions = first.get("duplicateActions")
    assert isinstance(actions, list)
    actions[0]["actualVisibleCount"] = 3
    tracker = CompactRepairStrategyTracker(max_repair_attempts=3)
    tracker.next_directive("source-three", [first])
    progress = tracker.next_directive("source-two", [issue])
    stalled = tracker.next_directive("renamed-only", [issue])
    assert progress.no_progress is False
    assert stalled.no_progress is False
    assert "上一轮重复超额数量没有减少" not in progress.instruction
    assert "上一轮重复超额数量没有减少" in stalled.instruction
    assert progress.repair_strategy == stalled.repair_strategy == "deduplicate_visible_actions"


def _mixed_failure_case(*, capacity):
    rows, context = _case()
    plan = copy.deepcopy(context.compact_plan)
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    task = copy.deepcopy(context.task_spec)
    schema = task.get("dataModelSchema")
    assert isinstance(schema, dict)
    data = schema.get("data")
    assert isinstance(data, dict)
    data["extra"] = {}
    items = []
    item_count = 5 if capacity else 2
    for index in range(item_count):
        path = f"/data/extra/item{index}"
        text = f"信息{index}"
        data["extra"][f"item{index}"] = {"type": "string", "sampleValue": text}
        reference = {"text": text} if capacity else {"dataId": path}
        facts.append({**reference, "requirement": text,
                      "priority": "must" if capacity or index == 0 else "should"})
        rows.append([path, text])
        items.append({"value": text if capacity else {"path": path}})
    if capacity:
        rows[7][1] = "SummaryList"
        rows[7][2] = {"items": items}
    else:
        rows[7][1] = "SecondaryBody"
        rows[7][2] = {"items": items[1:], "fontSize": 12}
    context = replace(context, compact_plan=plan, task_spec=task)
    deduplicated = copy.deepcopy(rows)
    deduplicated[5][2] = {"variant": "title-content"}
    deduplicated[5][3] = deduplicated[5][3][:2]
    del deduplicated[8]
    return _source(rows), _source(deduplicated), context


@pytest.mark.parametrize("capacity", [False, True])
def test_deduplication_does_not_consume_lossless_other_failure_stage(monkeypatch, capacity):
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    source, deduplicated, context = _mixed_failure_case(capacity=capacity)
    processor = DesignCompactProcessor()
    initial = processor.process(source, context)
    after = processor.process(deduplicated, context)
    initial_issues = [issue.to_prompt_payload() for issue in initial.errors]
    remaining_issues = [issue.to_prompt_payload() for issue in after.errors]
    assert any(issue.get("duplicateActions") for issue in initial_issues)
    assert remaining_issues
    assert not any(issue.get("duplicateActions") for issue in remaining_issues)
    if capacity:
        assert any(issue.get("capacityFits") for issue in initial_issues)
    else:
        assert any("Plan fact is missing" in issue.get("message", "")
                   for issue in remaining_issues)
    duplicate_rounds = 1 if capacity else 2
    tracker = CompactRepairStrategyTracker(max_repair_attempts=duplicate_rounds + 1)
    for _ in range(duplicate_rounds):
        directive = tracker.next_directive(source, initial_issues,
                                          compact_plan=context.compact_plan,
                                          task_spec=context.task_spec)
        assert directive.repair_strategy == "deduplicate_visible_actions"
        assert directive.optional_drop is None
        assert directive.approved_omitted_fact_indexes == ()
    next_stage = tracker.next_directive(deduplicated, remaining_issues,
                                        compact_plan=context.compact_plan,
                                        task_spec=context.task_spec)
    assert next_stage.repair_strategy != "drop_optional_component"
    assert next_stage.retryable is True
    assert next_stage.optional_drop is None
    assert next_stage.approved_omitted_fact_indexes == ()
    exhausted = tracker.next_directive(deduplicated, remaining_issues,
                                       compact_plan=context.compact_plan,
                                       task_spec=context.task_spec)
    assert exhausted.retryable is False
    assert exhausted.stop_reason == "global_attempt_limit"


def test_repair_prompt_carries_duplicate_actions_and_unchanged_dynamic_uri(monkeypatch):
    rows, context = _case(fixed_slots=True)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    source = _source(rows)
    issue = _action_issue(source, context)
    strategy = CompactRepairStrategyTracker().next_directive(source, [issue])
    messages = PromptBuilder().build_repair(
        [{"role": "system", "content": "contract"}, {"role": "user", "content": "{}"}],
        source, [issue], dsl_format=DESIGN_COMPACT_PROFILE_ID,
        task_spec=TaskSpec.model_validate(context.task_spec),
        repair_strategy=strategy.to_prompt_payload(),
    )
    content = messages[-1].get("content")
    assert isinstance(content, str)
    feedback = json.loads(content)
    assert feedback.get("duplicateActions") == issue.get("duplicateActions")
    assert _URI in content
    instruction = feedback.get("instruction")
    assert isinstance(instruction, str)
    for required in ("fixedRequiredSlot", "不同参数", "不改 accepted Plan", "不授权 Drop"):
        assert required in instruction
    assert feedback.get("repairStrategy") == strategy.to_prompt_payload()
