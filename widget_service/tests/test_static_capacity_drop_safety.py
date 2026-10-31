"""容量删减必须来自当前真实错误，并保留对象归属与实际遗漏语义。"""

import copy
import json
import socket

import pytest
from widget_service.tests.static_title_fixtures import titled_rows

from services.card_validation.compact_validation.semantic.static_content import static_group_errors
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_plan import compact_plan_omitted_facts, compact_plan_optional_drop_candidate
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope


@pytest.fixture(autouse=True)
def offline_static_policy(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("静态容量回归不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def task():
    return {
        "size": "2x4", "userQuery": "完整展示对象资料", "dataModelSchema": {"data": {}},
        "eventCandidates": [], "assetCandidates": [],
    }


def source(kind, items, *, header=False):
    rows = [["root", "Layout", {"layout": "W-static-content"},
             ["header", "body"] if header else ["body"]]]
    if header:
        rows.append(["header", "SingleLineTitle", {"title": "对象摘要"}])
    rows.append(["body", kind, {"items": items}])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in titled_rows(rows))


def list_case(kind="SingleLineList", count=2, *, header=True, long_first=False):
    items, facts, groups = [], [], []
    first_key, second_key = (
        ("text", "assist") if kind == "SingleLineList" else ("primaryText", "secondaryText")
    )
    for index in range(count):
        name = f"对象{index}"
        detail = "完整说明很长" * 12 if long_first and index == 0 else "短说明"
        items.append({first_key: name, second_key: detail})
        text = name + "；" + detail
        facts.append({
            "text": text, "requirement": text, "sourceTexts": [text],
            "priority": "should" if index == count - 1 else "must",
        })
        groups.append({
            "id": str(index), "kind": "object", "identity": name, "factIndexes": [index],
        })
    return source(kind, items, header=header), {"info_required": facts, "contentGroups": groups}


def real_issue(dsl):
    with pytest.raises(ValueError) as caught:
        convert_compact_dsl_to_a2ui(dsl, size="2x4")
    return {
        "stage": "conversion", "code": "COMPACT_DSL_CONVERSION_FAILED",
        "message": str(caught.value),
    }


def next_repair(tracker, dsl, issue, plan):
    return tracker.next_directive(dsl, [issue], compact_plan=plan, task_spec=task())


def test_overflow_targets_current_field_not_unrelated_tail_should():
    dsl, plan = list_case(long_first=True)
    before = copy.deepcopy(plan)
    issue = real_issue(dsl)
    assert "body.item0_assist" in issue.get("message", "")
    tracker = CompactRepairStrategyTracker(static_content=True)
    first = next_repair(tracker, dsl, issue, plan)
    assert first.optional_drop is None
    assert "无保护should可省略" not in first.instruction
    second = next_repair(tracker, dsl, issue, plan)
    assert second.optional_drop is not None
    assert second.optional_drop.fact_indexes == (0,)
    assert tracker.allowed_omitted_fact_indexes == (0,)
    assert plan == before


@pytest.mark.parametrize("kind,count,header", [
    ("TextList", 4, False), ("TextList", 3, True), ("ComparisonGroup", 4, True),
])
def test_upper_count_prefers_early_should_over_trailing_must(kind, count, header):
    dsl, plan = list_case(kind, count, header=header)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    for index, fact in enumerate(facts):
        fact["priority"] = "should" if index == 0 else "must"
    tracker = CompactRepairStrategyTracker(static_content=True)
    issue = real_issue(dsl)
    assert next_repair(tracker, dsl, issue, plan).optional_drop is None
    directive = next_repair(tracker, dsl, issue, plan)
    assert directive.optional_drop is not None
    assert directive.optional_drop.fact_indexes == (0,)
    assert not directive.optional_drop.contains_must_facts


@pytest.mark.parametrize("mode", ["underflow", "empty_field"])
def test_contract_errors_do_not_authorize_drop(mode):
    items = [
        {"primaryText": "对象0", "secondaryText": "短说明"},
        {"primaryText": "对象1", "secondaryText": "短说明"},
    ]
    _, plan = list_case()
    if mode == "underflow":
        items.pop()
    else:
        items[0]["secondaryText"] = ""
    dsl = source("TextList", items)
    issue = real_issue(dsl)
    tracker = CompactRepairStrategyTracker(static_content=True)
    for _ in range(3):
        assert next_repair(tracker, dsl, issue, plan).optional_drop is None
    assert tracker.allowed_omitted_fact_indexes == ()


@pytest.mark.parametrize("location", ["ghostbody", "other.body", "other/body", "orphan"])
def test_unknown_component_cannot_borrow_known_body_capacity(location):
    dsl, plan = list_case(long_first=True)
    issue = real_issue(dsl)
    message = issue.get("message")
    assert isinstance(message, str)
    issue["message"] = message.replace("body.", location + ".")
    tracker = CompactRepairStrategyTracker(static_content=True)
    next_repair(tracker, dsl, issue, plan)
    assert next_repair(tracker, dsl, issue, plan).optional_drop is None
    assert tracker.allowed_omitted_fact_indexes == ()


@pytest.mark.parametrize("message", [
    "component root: vertical layout requires at least 147vp within 126vp",
    "COMPACT_STATIC_TEXT_CAPACITY: SingleLineList完整单行文字超限",
])
def test_unlocated_capacity_keeps_lossless_repair_without_drop(message):
    dsl, plan = list_case()
    issue = {"stage": "validation", "code": "COMPACT_STATIC_TEXT_CAPACITY", "message": message}
    tracker = CompactRepairStrategyTracker(static_content=True)
    first = next_repair(tracker, dsl, issue, plan)
    assert first.category == "layout_capacity"
    assert first.optional_drop is None
    second = next_repair(tracker, dsl, issue, plan)
    assert second.optional_drop is None
    assert tracker.allowed_omitted_fact_indexes == ()


def test_prior_syntax_repair_does_not_replace_first_lossless_capacity_attempt():
    dsl, plan = list_case(long_first=True)
    tracker = CompactRepairStrategyTracker(static_content=True)
    syntax = {"stage": "conversion", "code": "COMPACT_DSL_CONVERSION_FAILED",
              "message": "field primaryText requires a string"}
    next_repair(tracker, dsl, syntax, plan)
    assert next_repair(tracker, dsl, real_issue(dsl), plan).optional_drop is None
    assert tracker.allowed_omitted_fact_indexes == ()


def test_capacity_repair_keeps_global_attempt_budget():
    dsl, plan = list_case(long_first=True)
    issue = real_issue(dsl)
    tracker = CompactRepairStrategyTracker(static_content=True, max_repair_attempts=1)
    assert next_repair(tracker, dsl, issue, plan).retryable
    exhausted = next_repair(tracker, dsl, issue, plan)
    assert not exhausted.retryable
    assert exhausted.stop_reason == "global_attempt_limit"
    assert exhausted.optional_drop is None


@pytest.mark.parametrize("retained", [False, True])
def test_middle_drop_preserves_ownership_and_only_reports_actual_omission(retained):
    original, plan = list_case(count=3)
    remaining = source("SingleLineList", [
        {"text": "对象0", "assist": "短说明"}, {"text": "对象2", "assist": "短说明"},
    ])
    dsl = original if retained else remaining
    assert not static_group_errors(dsl, plan, (1,))
    omitted = compact_plan_omitted_facts(dsl, plan, task(), (1,))
    if retained:
        assert not omitted
    else:
        assert len(omitted) == 1
        assert omitted[0].get("text") == "对象1；短说明"
        assert omitted[0].get("omissionReason") == "bounded_drop"


@pytest.mark.parametrize("protection", [
    {"protectedTexts": ["对象0"]}, {"preserveVerbatim": True},
])
def test_affected_protected_fact_cannot_be_dropped(protection):
    dsl, plan = list_case()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[0].update(protection)
    assert compact_plan_optional_drop_candidate(
        dsl, plan, task(), allowed_fact_indexes={0},
    ) is None


def pending_count_drop(*, limit=5, protected_target=False):
    initial, plan = list_case("TextList", count=3, header=True, long_first=True)
    current, _ = list_case(count=3, long_first=True)
    if protected_target:
        facts = plan.get("info_required")
        assert isinstance(facts, list)
        facts[0]["protectedTexts"] = ["对象0"]
    tracker = CompactRepairStrategyTracker(static_content=True, max_repair_attempts=limit)
    issue = real_issue(initial)
    next_repair(tracker, initial, issue, plan)
    directive = next_repair(tracker, initial, issue, plan)
    assert directive.optional_drop is not None
    assert directive.optional_drop.fact_indexes == (2,)
    return tracker, plan, initial, current


@pytest.mark.parametrize("previously_missing", [False, True])
def test_restored_unaffected_permission_is_replaced_not_accumulated(previously_missing):
    tracker, plan, _, current = pending_count_drop()
    if previously_missing:
        incomplete = source("SingleLineList", [{"text": "对象0", "assist": "完整说明很长" * 12}])
        issue = {"stage": "validation", "code": "COMPACT_PLAN_COVERAGE_FAILED",
                 "message": "COMPACT_STATIC_CORE_MISSING: 未授权事实缺失"}
        next_repair(tracker, incomplete, issue, plan)
    directive = next_repair(tracker, current, real_issue(current), plan)
    assert directive.optional_drop is not None
    assert directive.optional_drop.fact_indexes == (0,)
    assert tracker.allowed_omitted_fact_indexes == (0,)


@pytest.mark.parametrize("mode", ["missing", "partial", "other_owner"])
def test_incomplete_pending_fact_keeps_its_existing_permission(mode):
    tracker, plan, _, current = pending_count_drop()
    rows = [json.loads(line) for line in current.splitlines()]
    body = next(row for row in rows if row[0] == "body")
    items = body[2].get("items")
    assert isinstance(items, list)
    if mode == "missing":
        items.pop()
    elif mode == "partial":
        items[2]["assist"] = "短"
    else:
        items[2]["text"] = "其它对象"
    changed = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    next_repair(tracker, changed, real_issue(current), plan)
    assert 2 in tracker.allowed_omitted_fact_indexes


def test_pending_fact_still_affected_by_count_is_not_released():
    tracker, plan, initial, _ = pending_count_drop()
    directive = next_repair(tracker, initial, real_issue(initial), plan)
    assert directive.optional_drop is not None
    assert directive.optional_drop.fact_indexes == (2,)
    assert tracker.allowed_omitted_fact_indexes == (2,)


def test_retarget_cannot_add_budget_or_revoke_after_exhaustion():
    tracker, plan, _, current = pending_count_drop(limit=2)
    directive = next_repair(tracker, current, real_issue(current), plan)
    assert not directive.retryable
    assert directive.stop_reason == "global_attempt_limit"
    assert tracker.allowed_omitted_fact_indexes == (2,)


def test_released_candidate_without_legal_replacement_never_reappears():
    tracker, plan, _, current = pending_count_drop(protected_target=True)
    for _ in range(2):
        directive = next_repair(tracker, current, real_issue(current), plan)
        assert directive.optional_drop is None
        assert tracker.optional_drop_candidate is None
        assert tracker.allowed_omitted_fact_indexes == ()
