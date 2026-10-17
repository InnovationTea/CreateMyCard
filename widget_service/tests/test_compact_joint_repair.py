"""请求内跨约束重组与完整合同交接；不以单个业务样本定义策略。"""

import copy
import json

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_repair_context import joint_repair_contract, repair_topology_fingerprint
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.prompt_builder import PromptBuilder


def _source(identifier: str = "body", columns: int = 1) -> str:
    rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, [identifier]],
        [identifier, "SecondaryBody", {"columns": columns, "items": [{"value": "内容"}]}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _plan() -> dict:
    return {
        "info_required": [
            {"requirement": "核心读数", "dataId": "/data/value", "priority": "must"},
            {"requirement": "辅助读数", "dataId": "/data/detail", "priority": "should"},
            {"requirement": "打开设置", "actionId": "settings", "priority": "must"},
        ],
        "assetAssignments": {
            "actions": [{"actionId": "settings", "assetId": "asset.settings"}],
            "title": {"assetId": None, "reason": "没有剩余合适图标"},
        },
    }


def _task() -> dict:
    return {
        "size": "2x4", "userQuery": "显示读数并打开设置",
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.settings", "src": "resources/settings.svg"},
            {"id": "asset.unused", "src": "resources/unused.svg"},
        ],
        "eventCandidates": [
            {"id": "settings", "call": "clickToIntent",
             "args": {"enabled": False, "count": 0, "optional": None}},
        ],
    }


def _errors(category: str) -> list[dict]:
    cases = {
        "capacity": "component root: vertical layout requires at least 160vp within 126vp",
        "structure": (
            "Component rows must form one tree rooted at root. Unreachable component(s): x."
        ),
        "coverage": "Plan action is missing from visible DSL: 打开设置 (settings).",
        "asset": (
            "button for action 'settings' must use Plan-assigned icon 'resources/settings.svg'."
        ),
        "props": "component value: unsupported prop invented",
    }
    message = cases.get(category)
    assert isinstance(message, str)
    code = "COMPACT_DSL_VALIDATION_FAILED"
    if category == "coverage":
        code = "COMPACT_PLAN_COVERAGE_FAILED"
    return [{"stage": "validation", "code": code, "message": message}]


def _next(tracker, category: str, source: str):
    return tracker.next_directive(
        source, _errors(category), compact_plan=_plan(), task_spec=_task()
    )


def test_topology_ignores_ids_and_colors_but_preserves_capacity_configuration() -> None:
    first = _source("first")
    renamed = _source("renamed")
    rows = [json.loads(line) for line in renamed.splitlines()]
    root_props = rows[0][2]
    assert isinstance(root_props, dict)
    root_props["backgroundColor"] = "#FFFFFFFF"
    recolored = "\n".join(json.dumps(row) for row in rows)
    assert repair_topology_fingerprint(first) == repair_topology_fingerprint(recolored)
    assert repair_topology_fingerprint(first) != repair_topology_fingerprint(_source(columns=2))
    assert repair_topology_fingerprint("not json") is None


@pytest.mark.parametrize("next_category", ["capacity", "structure", "coverage", "asset"])
def test_prior_capacity_failure_triggers_joint_recompose(next_category: str) -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=3)
    first = _next(tracker, "capacity", _source())
    assert first.scope == "sublayout"
    second = _next(tracker, next_category, _source("renamed"))
    assert second.scope == "full_dsl"
    assert second.repair_strategy == "plan_guided_recompose"
    assert "事实、动作和素材" in second.instruction
    context = second.to_prompt_payload().get("jointRecomposition")
    assert isinstance(context, dict)
    assert context.get("layoutPreviouslyFailed") is True
    assert context.get("revisitedTopology") is True


def test_changed_topology_does_not_reset_consecutive_capacity_work() -> None:
    tracker = CompactRepairStrategyTracker()
    _next(tracker, "capacity", _source(columns=1))
    directive = _next(tracker, "capacity", _source(columns=2))
    assert directive.scope == "full_dsl"
    context = directive.joint_context
    assert isinstance(context, dict)
    assert context.get("revisitedTopology") is False


def test_joint_stage_survives_targeted_repairs_and_preserves_budget() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=4)
    _next(tracker, "capacity", _source())
    joint = _next(tracker, "coverage", _source("b"))
    assert joint.repair_strategy == "plan_guided_recompose"
    local = _next(tracker, "asset", _source("c"))
    assert local.repair_strategy == "component_contract_repair"
    resumed = _next(tracker, "capacity", _source("d"))
    assert resumed.repair_strategy == "compact_component"
    exhausted = _next(tracker, "capacity", _source("e"))
    assert exhausted.retryable is False
    assert tracker.allowed_omitted_fact_indexes == ()


def test_unrelated_props_and_new_requests_keep_targeted_route() -> None:
    tracker = CompactRepairStrategyTracker()
    _next(tracker, "capacity", _source())
    directive = _next(tracker, "props", _source("other"))
    assert directive.scope == "component"
    assert directive.joint_context is None
    fresh = _next(CompactRepairStrategyTracker(), "coverage", _source())
    assert fresh.repair_strategy == "coverage_restore"


def test_contract_preserves_types_assignments_and_only_authorized_non_action_omissions() -> None:
    plan = _plan()
    task = _task()
    original = copy.deepcopy((plan, task))
    ledger = joint_repair_contract(plan, task, [{"factIndex": 1}, {"factIndex": 2}])
    assert ledger.get("facts") == [
        {"factIndex": 0, "requirement": "核心读数", "dataId": "/data/value", "priority": "must"}
    ]
    assert ledger.get("actions") == task.get("eventCandidates")
    assert ledger.get("assetAssignments") == plan.get("assetAssignments")
    assert ledger.get("assignedAssets") == [
        {"id": "asset.settings", "src": "resources/settings.svg"}
    ]
    assert ledger.get("approvedOmissions") == [{"factIndex": 1}]
    assert (plan, task) == original
    actions = ledger.get("actions")
    assert isinstance(actions, list)
    candidate = actions[0]
    assert isinstance(candidate, dict)
    candidate["call"] = "changed"
    assert (plan, task) == original


@pytest.mark.parametrize("runtime_context", [False, True])
def test_actual_repair_feedback_carries_joint_contract_without_reencoding_history(
    monkeypatch, runtime_context: bool,
) -> None:
    monkeypatch.setattr(
        get_settings(), "enable_design_compact_runtime_prompt_context", runtime_context
    )
    task = TaskSpec.model_validate(_task())
    messages = [
        {"role": "system", "content": "合同"},
        {"role": "user", "content": task.model_dump_json()},
    ]
    result = PromptBuilder().build_repair(
        messages, _source(), _errors("asset"), dsl_format="design-compact-dsl",
        task_spec=task, compact_plan=_plan(),
        repair_strategy={"scope": "full_dsl", "approvedOmittedFactIndexes": [1]},
        previous_failures=[_errors("capacity")],
    )
    content = result[-1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    ledger = payload.get("repairObligations")
    assert isinstance(ledger, dict)
    assert ledger.get("actions") == task.model_dump(mode="json").get("eventCandidates")
    assert ledger.get("assetAssignments") == _plan().get("assetAssignments")
    assert ledger.get("approvedOmissions") == payload.get("approvedOmissions")
    assert "previousFailures" not in payload
    assert "repairHistory" not in payload
    assert len(messages) == 2
