"""Plan 展示取舍边界与双动作软候选回归；不调用模型或裁剪用户事实。"""

import copy
import json

import pytest
from services.compact_plan import (
    build_compact_plan_tool,
    compact_plan_context,
    compact_plan_coverage_errors,
    parse_compact_plan_call,
)
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry


def _selection_task(size: str = "2x2") -> dict:
    fields: dict = {}
    for index in range(5):
        fields[f"field{index}"] = {
            "type": "string",
            "description": f"用户指标{index}",
            "sampleValue": f"读数{index}",
        }
    return {
        "size": size,
        "userQuery": "展示设备的指定指标，提供用户要求的操作",
        "dataModelSchema": {"data": {"device": fields}},
        "eventCandidates": [
            {"id": "action.first", "call": "clickToDeeplink", "args": {"uri": "app://one"}},
            {"id": "action.second", "call": "clickToDeeplink", "args": {"uri": "app://two"}},
            {"id": "action.details", "call": "clickToDeeplink", "args": {"uri": "app://details"}},
        ],
    }


def _content_facts(count: int, *, include_hints: bool = True) -> list[dict]:
    facts: list[dict] = []
    for index in range(count):
        fact = {
            "requirement": f"用户要求的指标{index}",
            "priority": "must",
            "dataId": f"/data/device/field{index}",
        }
        if include_hints:
            fact["componentHints"] = ["EmphasisText"] if index == 0 else ["SecondaryBody"]
        facts.append(fact)
    return facts


def _action_fact(action_id: str) -> dict:
    return {
        "requirement": "用户要求的操作",
        "priority": "must",
        "actionId": action_id,
        "componentHints": ["PillButton"],
    }


def _parse(facts: list[dict], task: dict, layouts: list[str]) -> dict:
    output = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {"info_required": facts, "layoutHints": layouts},
        },
        ensure_ascii=False,
    )
    return parse_compact_plan_call(output, task).plan


@pytest.mark.parametrize("content_count", [0, 1, 2, 3, 5])
@pytest.mark.parametrize("include_hints", [False, True])
def test_dual_actions_never_select_content_by_fact_count(
    content_count: int, include_hints: bool,
) -> None:
    task = _selection_task()
    original_task = copy.deepcopy(task)
    content = _content_facts(content_count, include_hints=include_hints)
    original_content = copy.deepcopy(content)
    facts = [*content, _action_fact("action.first"), _action_fact("action.second")]
    plan = _parse(facts, task, ["S-title-content-action"])
    accepted = plan.get("info_required")
    assert isinstance(accepted, list)
    assert accepted[:content_count] == original_content
    assert len(accepted) == content_count + 2
    assert plan.get("layoutHints") == ["S-content-dual-action"]
    assert task == original_task
    for fact in accepted[content_count:]:
        assert fact.get("componentHints") == ["CardButton"]
    context = compact_plan_context(plan)
    assert "不按事实数量强制表格" in context
    assert "保留全部事实、两个动作及其完整参数" in context


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_unselected_candidates_do_not_become_plan_obligations(size: str) -> None:
    task = _selection_task(size)
    original_task = copy.deepcopy(task)
    facts = [*_content_facts(1), _action_fact("action.first")]
    layout = "S-title-content-action" if size == "2x2" else "W-split-panels"
    plan = _parse(facts, task, [layout])
    assert plan.get("info_required") == facts
    assert plan.get("layoutHints") == [layout]
    assert task == original_task
    tool = build_compact_plan_tool(task)
    function = tool.get("function")
    assert isinstance(function, dict)
    parameters = function.get("parameters")
    assert isinstance(parameters, dict)
    properties = parameters.get("properties")
    assert isinstance(properties, dict)
    assert set(properties) == {"info_required", "layoutHints"}
    info = properties.get("info_required")
    assert isinstance(info, dict)
    items = info.get("items")
    assert isinstance(items, dict)
    fact_properties = items.get("properties")
    assert isinstance(fact_properties, dict)
    data_id = fact_properties.get("dataId")
    assert isinstance(data_id, dict)
    assert len(data_id.get("enum", [])) == 5
    action_id = fact_properties.get("actionId")
    assert isinstance(action_id, dict)
    assert action_id.get("enum") == ["action.first", "action.second", "action.details"]


def test_accepted_optional_content_and_actions_are_not_automatically_deleted() -> None:
    task = _selection_task()
    content = _content_facts(5)
    content[-1]["priority"] = "should"
    facts = [*content, _action_fact("action.first"), _action_fact("action.second")]
    facts[-1]["priority"] = "should"
    plan = _parse(facts, task, ["S-content-dual-action"])
    accepted = plan.get("info_required")
    assert isinstance(accepted, list)
    assert accepted[:5] == content
    assert len(accepted) == 7
    assert accepted[-1].get("actionId") == "action.second"
    assert accepted[-1].get("priority") == "must"


@pytest.mark.parametrize("missing_target", ["/data/device/field0", "action.second"])
def test_first_dsl_still_rejects_missing_requested_content_or_action(missing_target: str) -> None:
    task = _selection_task()
    facts = [*_content_facts(5), _action_fact("action.first"), _action_fact("action.second")]
    plan = _parse(facts, task, ["S-content-dual-action"])
    rows: list[list] = []
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    for index, fact in enumerate(facts):
        data_id = fact.get("dataId")
        action_id = fact.get("actionId")
        if data_id == missing_target or action_id == missing_target:
            continue
        if isinstance(data_id, str):
            rows.append([f"content{index}", "EmphasisText", {"mainText": {"path": data_id}}])
            continue
        for candidate in candidates:
            if candidate.get("id") != action_id:
                continue
            handler = {"call": candidate.get("call"), "args": candidate.get("args")}
            rows.append([f"action{index}", "PillButton", {"onClick": [handler]}])
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    errors = compact_plan_coverage_errors(source, plan, task)
    assert any(missing_target in error for error in errors)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_effective_plan_contract_distinguishes_requested_facts_and_implicit_entries(
    size: str,
) -> None:
    prompt = A2UIProtocolRegistry.read_design_plan_prompt(DESIGN_COMPACT_PROFILE_ID, size=size)
    assert "逐项保留用户明确要求展示的指标、对象、集合成员、时间范围" in prompt
    assert "不先全选，再指望 DSL 或修复删减" in prompt
    assert "只读详情候选不自动入选" in prompt
    assert "不因非 Action 事实至少两项就推荐 TableText" in prompt
    assert "仅 Schema 含 composition 时" in prompt
