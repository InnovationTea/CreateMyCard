"""固定双动作骨架必须有真实动作支持，不能由错误候选反向制造动作。"""

import copy
import json

import pytest

from services.compact_plan import (
    CompactPlanValidationError,
    compact_plan_context,
    parse_compact_plan_call,
)


def _task(size: str = "2x2") -> dict:
    return {
        "userQuery": "显示通勤时间，提供去公司和回家导航",
        "size": size,
        "dataModelSchema": {
            "data": {"duration": {"type": "string", "sampleValue": "30分钟"}},
        },
        "eventCandidates": [
            {"id": "event.company", "call": "navigate", "args": {"target": "company"}},
            {"id": "event.home", "call": "navigate", "args": {"target": "home"}},
        ],
    }


def _action(identifier: str) -> dict:
    return {
        "requirement": "导航",
        "priority": "must",
        "actionId": identifier,
        "componentHints": ["PillButton"],
    }


def _data() -> dict:
    return {
        "requirement": "通勤时间",
        "priority": "must",
        "dataId": "/data/duration",
        "componentHints": ["EmphasisText"],
    }


def _data_at(path: str, requirement: str) -> dict:
    return {
        "requirement": requirement,
        "priority": "must",
        "dataId": path,
        "componentHints": ["EmphasisText"],
    }


def _parse(facts: list[dict], hints: list[str], size: str = "2x2"):
    call = {"name": "submit_card_plan", "arguments": {
        "info_required": facts, "layoutHints": hints,
    }}
    return parse_compact_plan_call(json.dumps(call), _task(size))


@pytest.mark.parametrize("facts", [
    [_action("event.company")],
    [_data(), _action("event.company")],
    [_data()],
    [_action("event.company"), _action("event.company")],
])
def test_invalid_dual_action_hint_never_invents_actions(facts: list[dict]) -> None:
    original = copy.deepcopy(facts)
    result = _parse(facts, ["S-content-dual-action"])
    assert "layoutHints" not in result.plan
    assert any("does not contain exactly two distinct actions" in item for item in result.warnings)
    accepted = result.plan.get("info_required")
    assert isinstance(accepted, list)
    actions = [fact.get("actionId") for fact in accepted if "actionId" in fact]
    expected_actions = []
    for fact in facts:
        action_id = fact.get("actionId")
        if action_id is not None and action_id not in expected_actions:
            expected_actions.append(action_id)
    assert actions == expected_actions
    assert "成为固定布局" not in compact_plan_context(result.plan)
    assert facts == original


def test_invalid_hint_removal_preserves_other_hint_and_fact_roles() -> None:
    facts = [_data(), _action("event.company")]
    result = _parse(facts, ["S-content-dual-action", "S-title-content-action"])
    assert result.plan.get("layoutHints") == ["S-title-content-action"]
    assert result.plan.get("info_required") == facts


@pytest.mark.parametrize("with_body", [False, True])
def test_two_distinct_actions_keep_original_contract(with_body: bool) -> None:
    facts = [_action("event.company"), _action("event.home")]
    if with_body:
        facts.insert(0, _data())
    result = _parse(facts, ["S-title-content-action"])
    assert result.plan.get("layoutHints") == ["S-content-dual-action"]
    accepted = result.plan.get("info_required")
    assert isinstance(accepted, list)
    for fact in accepted:
        if "actionId" in fact:
            assert fact.get("componentHints") == ["CardButton"]
        else:
            assert fact == _data()
    context = compact_plan_context(result.plan)
    assert "成为固定布局" in context
    assert ("actions-only 变体" in context) == (not with_body)


@pytest.mark.parametrize("facts", [
    [],
    [_action("event.company")],
    [_action("event.company"), _action("event.company")],
    [_action("event.company"), None],
])
def test_context_does_not_trust_stale_hint_without_distinct_actions(facts) -> None:
    plan = {"info_required": facts, "layoutHints": ["S-content-dual-action"]}
    context = compact_plan_context(plan, implementation_conflicts=[])
    assert "成为固定布局" not in context
    assert "actions-only 变体" not in context


@pytest.mark.parametrize("size,hints", [
    ("2x2", ["S-title-content-action"]),
    ("2x4", ["W-content-side-slots"]),
])
def test_valid_single_action_plan_unchanged(size: str, hints: list[str]) -> None:
    facts = [_data(), _action("event.company")]
    result = _parse(facts, hints, size)
    assert result.plan == {"info_required": facts, "layoutHints": hints}
    assert result.warnings == ()


def test_wide_action_context_forbids_top_bottom_and_requires_reachable_button() -> None:
    facts = [_data(), _action("event.company")]
    result = _parse(facts, ["W-top-bottom"], "2x4")

    context = compact_plan_context(result.plan)

    assert result.plan.get("layoutHints") == ["W-content-side-slots", "W-split-panels"]
    assert "W-top-bottom只允许[标题?, 主体, 明细]" in context
    assert "定义游离按钮" in context


def test_two_by_two_dual_action_plan_rejects_more_than_two_body_facts() -> None:
    task = _task()
    schema = task["dataModelSchema"]["data"]
    schema["weather"] = {"type": "string", "sampleValue": "多云"}
    schema["battery"] = {"type": "string", "sampleValue": "68%"}
    facts = [
        _data(),
        _data_at("/data/weather", "天气"),
        _data_at("/data/battery", "电量"),
        _action("event.company"),
        _action("event.home"),
    ]
    raw = json.dumps({"name": "submit_card_plan", "arguments": {
        "info_required": facts, "layoutHints": ["S-content-dual-action"],
    }}, ensure_ascii=False)

    with pytest.raises(CompactPlanValidationError, match="正文最多两条完整信息组"):
        parse_compact_plan_call(raw, task)
