"""真实失败末稿的反馈与路由回放；不把离线测试当作模型生成成功。"""

import copy
import json
from pathlib import Path

import pytest

from core.errors import GenerationStatus
from models.generation import TaskSpec
from services.compact_plan import compact_plan_omitted_facts
from services.compact_repair_evidence import RepairProgress, repair_failure_evidence
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.prompt_builder import PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID
from services.response_planner import ResponsePlanner

FIXTURE = (
    Path(__file__).parent / "fixtures/validator_batch_replay/task_a2b68e673af4.json"
)


def _case(sample_id: str) -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    assert isinstance(cases, list)
    for case in cases:
        if case.get("sampleId") == sample_id:
            return case
    raise AssertionError(f"Missing replay case: {sample_id}")


def _source_and_issues(sample_id: str) -> tuple[str, list[dict]]:
    case = _case(sample_id)
    source = case.get("dsl")
    issues = case.get("issues")
    assert isinstance(source, str)
    assert isinstance(issues, list)
    return source, issues


def test_q043_missing_core_recomposes_whole_card_and_preserves_actions() -> None:
    source, issues = _source_and_issues("Q043")
    case = _case("Q043")
    before = copy.deepcopy(case)
    directive = CompactRepairStrategyTracker(max_repair_attempts=5).next_directive(
        source, issues, compact_plan=case.get("plan"), task_spec={"size": "2x4"},
    )
    assert directive.scope == "full_dsl"
    assert directive.repair_strategy == "plan_guided_recompose"
    assert "不能新增占位核心" in directive.instruction
    assert "保留全部动作" in directive.instruction
    assert directive.optional_drop is None
    evidence = directive.to_prompt_payload().get("failureEvidence")
    assert isinstance(evidence, dict)
    assert evidence.get("missingCoreInformation") is True
    members = evidence.get("sourceComponents")
    assert isinstance(members, list)
    actions = []
    for member in members:
        if member.get("hasAction"):
            actions.append(member.get("componentId"))
    assert actions == ["left_action", "right_action"]
    assert case == before


@pytest.mark.parametrize(
    ("sample_id", "component_id", "required", "available", "overflow"),
    [("Q084", "root", 146.0, 126.0, 20.0), ("Q109", "right", 148.0, 110.0, 38.0)],
)
def test_real_height_evidence_retains_budget_and_visible_facts(
    sample_id: str, component_id: str, required: float, available: float, overflow: float,
) -> None:
    source, issues = _source_and_issues(sample_id)
    directive = CompactRepairStrategyTracker().next_directive(
        source, issues, compact_plan=_case(sample_id).get("plan"),
    )
    evidence = directive.to_prompt_payload().get("failureEvidence")
    assert isinstance(evidence, dict)
    budgets = evidence.get("heightBudgets")
    assert isinstance(budgets, list)
    budget = next(item for item in budgets if item.get("componentId") == component_id)
    assert budget.get("minimumRequiredHeight") == required
    assert budget.get("maximumHeight") == available
    assert budget.get("overflow") == overflow
    assert budget.get("sourceComponentId") == component_id
    members = budget.get("sourceComponents")
    assert isinstance(members, list)
    assert any(member.get("planFacts") for member in members)
    for item in budgets:
        identifier = item.get("componentId")
        assert isinstance(identifier, str)
        if identifier.startswith("__layout__"):
            assert item.get("sourceComponentId") is None
            assert item.get("sourceComponents") == []
    assert directive.optional_drop is None


def _recolor(source: str) -> str:
    rows = []
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) >= 3:
            props = row[2]
            assert isinstance(props, dict)
            props["fontColor"] = "#FF123456"
        rows.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(rows)


def test_q084_cosmetic_change_is_stalled_and_escalates() -> None:
    source, issues = _source_and_issues("Q084")
    tracker = CompactRepairStrategyTracker()
    tracker.next_directive(source, issues)
    repeated = tracker.next_directive(_recolor(source), issues)
    assert repeated.no_progress is True
    assert repeated.to_prompt_payload().get("progress") == "stalled"
    assert repeated.repair_strategy == "plan_guided_recompose"


def test_q084_renaming_nodes_is_not_progress() -> None:
    source, issues = _source_and_issues("Q084")
    changed_source = source.replace('"content"', '"renamed_content"')
    changed_issues = copy.deepcopy(issues)
    for issue in changed_issues:
        message = issue.get("message")
        assert isinstance(message, str)
        issue["message"] = message.replace("content", "renamed_content")
    earlier = RepairProgress.capture(source, issues)
    current = RepairProgress.capture(changed_source, changed_issues)
    assert current.compare(earlier) == "stalled"


def _reduced_overflow(issues: list[dict]) -> list[dict]:
    result = copy.deepcopy(issues)
    for issue in result:
        message = issue.get("message")
        assert isinstance(message, str)
        issue["message"] = message.replace("146vp", "136vp").replace("120vp", "110vp")
    return result


def test_lower_reported_overflow_does_not_escalate_only_for_repeated_topology() -> None:
    source, issues = _source_and_issues("Q084")
    tracker = CompactRepairStrategyTracker()
    plan = _case("Q084").get("plan")
    tracker.next_directive(source, issues, compact_plan=plan, task_spec={"size": "2x2"})
    improved = tracker.next_directive(
        _recolor(source), _reduced_overflow(issues),
        compact_plan=plan, task_spec={"size": "2x2"},
    )
    # 衍生诊断仅测试进展比较，不声称该源稿真实测量已减少高度。
    assert improved.to_prompt_payload().get("progress") == "improved"
    assert improved.no_progress is False
    assert improved.repair_strategy == "rebudget"
    assert improved.consecutive_failures == 1


def test_unknown_or_new_action_error_cannot_claim_capacity_progress() -> None:
    source, issues = _source_and_issues("Q084")
    earlier = RepairProgress.capture(source, issues)
    changed = _reduced_overflow(issues)
    changed.append({"code": "COMPACT_PLAN_COVERAGE_FAILED", "message": "Missing Action"})
    assert RepairProgress.capture(source, changed).compare(earlier) == "unknown"


def test_removed_information_cannot_claim_progress() -> None:
    source, issues = _source_and_issues("Q109")
    earlier = RepairProgress.capture(source, issues)
    changed_source = source.replace("11:30-13:00知竹素菜馆午餐", "")
    assert RepairProgress.capture(changed_source, issues).compare(earlier) == "unknown"


def test_invalid_source_keeps_progress_unknown() -> None:
    _, issues = _source_and_issues("Q084")
    earlier = RepairProgress.capture("not JSON", issues)
    assert RepairProgress.capture("still not JSON", issues).compare(earlier) == "unknown"


def test_structured_height_diagnostic_is_preferred_over_legacy_message() -> None:
    source, issues = _source_and_issues("Q084")
    issue = copy.deepcopy(issues[0])
    issue["compactDiagnostics"] = [{
        "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        "componentId": "root",
        "expected": {"maximumHeight": 126.0},
        "actual": {"minimumRequiredHeight": 140.0, "occupancy": "recorded occupancy"},
    }]
    evidence = repair_failure_evidence(source, [issue], _case("Q084").get("plan"))
    budgets = evidence.get("heightBudgets")
    assert isinstance(budgets, list)
    assert len(budgets) == 1
    assert budgets[0].get("overflow") == 14.0
    assert budgets[0].get("occupancy") == "recorded occupancy"


def test_global_budget_still_exhausts_after_five_repairs() -> None:
    source, issues = _source_and_issues("Q043")
    tracker = CompactRepairStrategyTracker(max_repair_attempts=5)
    for _ in range(5):
        assert tracker.next_directive(source, issues).retryable is True
    assert tracker.next_directive(source, issues).retryable is False
    assert tracker.allowed_omitted_fact_indexes == ()


def test_mixed_structured_diagnostics_cannot_hide_new_blocker() -> None:
    source, issues = _source_and_issues("Q084")
    earlier = RepairProgress.capture(source, issues)
    changed = _reduced_overflow(issues)
    issue = changed[0]
    issue["compactDiagnostics"] = [
        {
            "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
            "componentId": "root",
            "expected": {"maximumHeight": 126.0},
            "actual": {"minimumRequiredHeight": 136.0},
        },
        {"code": "COMPACT_ACTION_MISSING", "message": "Missing Action"},
    ]
    assert RepairProgress.capture(source, changed).compare(earlier) == "unknown"


def test_height_evidence_reaches_model_repair_prompt() -> None:
    source, issues = _source_and_issues("Q084")
    plan = _case("Q084").get("plan")
    strategy = CompactRepairStrategyTracker().next_directive(
        source, issues, compact_plan=plan,
    ).to_prompt_payload()
    messages = PromptBuilder().build_repair(
        [{"role": "system", "content": "contract"}, {"role": "user", "content": "{}"}],
        source, issues, dsl_format=DESIGN_COMPACT_PROFILE_ID,
        task_spec=TaskSpec(userQuery="天气", size="2x2", dataModelSchema={"data": {}}),
        repair_strategy=strategy, compact_plan=plan,
    )
    content = messages[-1].get("content")
    assert isinstance(content, str)
    feedback = json.loads(content)
    actual_strategy = feedback.get("repairStrategy")
    assert isinstance(actual_strategy, dict)
    assert actual_strategy.get("failureEvidence") == strategy.get("failureEvidence")


def _verified_case(sample_id: str) -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    verification = payload.get("modelVerification")
    assert isinstance(verification, dict)
    cases = verification.get("cases")
    assert isinstance(cases, list)
    return next(case for case in cases if case.get("sampleId") == sample_id)


@pytest.mark.parametrize("sample_id", ["Q043", "Q084", "Q109"])
def test_actual_model_result_reports_all_missing_information(sample_id: str) -> None:
    case = _verified_case(sample_id)
    source, plan, task = case.get("dsl"), case.get("plan"), case.get("taskSpec")
    assert isinstance(source, str)
    assert isinstance(plan, dict)
    assert isinstance(task, dict)
    omitted = compact_plan_omitted_facts(source, plan, task)
    assert len(omitted) == case.get("expectedMissing")
    requirements = []
    for fact in omitted:
        assert "actionId" not in fact
        requirement = fact.get("requirement")
        assert isinstance(requirement, str)
        requirements.append(requirement)
    result = ResponsePlanner().plan(
        1, 1, [], has_artifact=True, omitted_requirements=requirements,
    )
    expected = GenerationStatus.SUCCESS if sample_id == "Q084" else GenerationStatus.DEGRADED
    assert result.status == expected
    # 显式空授权清单仍保持原行为，全量响应统计不能反向扩大 Drop 授权。
    assert compact_plan_omitted_facts(source, plan, task, ()) == ()


def test_q109_fallback_title_normalization_keeps_countdown_fact() -> None:
    from services.compact_plan import parse_compact_plan_call

    case = _verified_case("Q109")
    plan = case.get("plan")
    task = case.get("taskSpec")
    assert isinstance(plan, dict)
    assert isinstance(task, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    countdown = next(
        fact for fact in facts if fact.get("dataId") == "/data/countdown/countdownDays"
    )
    # 原始真实模型计划；新旧候选差异在已保存的 Q109 末稿中不改变右侧行程容量。
    assert "EmphasisText" in countdown.get("componentHints", [])
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    result = parse_compact_plan_call(raw, task)
    normalized = result.plan.get("info_required")
    assert isinstance(normalized, list)
    normalized_countdown = next(
        fact for fact in normalized if fact.get("dataId") == "/data/countdown/countdownDays"
    )
    assert normalized_countdown.get("componentHints") == ["EmphasisText"]
