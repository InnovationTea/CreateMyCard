"""静态 Plan 账本不冒充实际记录数，候选例外仍遵守原组件和事实合同。"""

import copy
import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.semantic.layout.text_capacity import (
    static_plan_candidate_preserves_required_content,
    static_plan_capacity_errors,
)
from services.card_validation.compact_validation.semantic.static_content import static_fact_coverage
from services.compact_plan import compact_plan_omitted_facts, parse_compact_plan_call
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)


def _plan(count=8):
    facts = []
    groups = []
    for index in range(count):
        text = f"对象{index + 1}；日期{index + 1}"
        facts.append({
            "requirement": text, "priority": "must" if index < 3 else "should",
            "text": text, "sourceTexts": [text], "displayRole": "body",
            "componentHints": ["TextList"],
        })
        groups.append({
            "id": f"g{index}", "kind": "object", "identity": f"对象{index + 1}",
            "factIndexes": [index],
        })
    return {"info_required": facts, "contentGroups": groups, "presentationStyle": "records"}


def _source(count=3, *, component="TextList", header=None):
    items = []
    for index in range(count):
        if component == "TextList":
            items.append({"primaryText": f"对象{index + 1}", "secondaryText": f"日期{index + 1}"})
        else:
            items.append({"text": f"对象{index + 1}", "assist": f"日期{index + 1}"})
    children = ["body"] if header is None else ["header", "body"]
    rows = [["root", "Layout", {"layout": "W-static-content"}, children]]
    if header is not None:
        rows.append(["header", "SingleLineTitle", {"title": header}])
    rows.extend([["body", component, {"items": items}], ["/state/ready", True]])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _validate(source, plan):
    return validate_compact_dsl(
        source, task_spec={"size": "2x4", "dataModelSchema": {"data": {}}},
        card_spec={"suggestSize": "2x4"}, compact_plan=plan,
        layout_scope="W-static-content-guided",
    )


@pytest.fixture(autouse=True)
def _static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def test_optional_inventory_survives_legal_three_record_candidate():
    plan = _plan()
    plan["staticPresentation"] = _source()
    original = copy.deepcopy(plan)
    assert static_plan_candidate_preserves_required_content(plan, "2x4")
    assert not static_plan_capacity_errors(plan, "2x4")
    assert plan == original
    omitted = compact_plan_omitted_facts(plan["staticPresentation"], plan, {"size": "2x4"}, ())
    assert len(omitted) == 5
    assert all(item.get("omissionReason") == "optional_omission" for item in omitted)


def test_real_plan_parser_retains_optional_inventory_and_omission_audit():
    plan = _plan()
    plan["omittedContents"] = [{"description": "可选记录容量不足", "factIndexes": [3, 4, 5, 6, 7]}]
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    query = "；".join(fact.get("text", "") for fact in facts)
    result = parse_compact_plan_call(
        json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False),
        {"userQuery": query, "size": "2x4"},
        require_static_identity=True, require_static_omission_refs=True,
    )
    accepted = result.plan
    assert len(accepted.get("info_required", [])) == 8
    assert len(accepted.get("contentGroups", [])) == 8
    assert accepted.get("omissionCandidates")
    source = accepted.get("staticPresentation")
    assert isinstance(source, str)
    coverage = static_fact_coverage(source, accepted)
    assert [item.fact_index for item in coverage if not item.visible] == [3, 4, 5, 6, 7]
    omitted = compact_plan_omitted_facts(source, accepted, {"size": "2x4"}, ())
    optional = [item for item in omitted if item.get("omissionReason") == "optional_omission"]
    assert len(optional) == 5


@pytest.mark.parametrize("protection", [
    {"priority": "must"}, {"protectedTexts": ["日期4"]}, {"preserveVerbatim": True},
])
def test_missing_required_or_protected_fact_never_uses_candidate_exception(protection):
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3].update(protection)
    plan["staticPresentation"] = _source()
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")
    assert static_plan_capacity_errors(plan, "2x4")


@pytest.mark.parametrize("candidate", [None, "", "not-json", _source(4), _source(header="未声明")])
def test_absent_or_forged_invalid_candidate_keeps_original_gate(candidate):
    plan = _plan()
    plan["staticPresentation"] = candidate
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")
    assert static_plan_capacity_errors(plan, "2x4")


def test_wrong_object_values_cannot_pass_with_globally_present_words():
    plan = _plan()
    plan["staticPresentation"] = _source().replace("日期1", "替换").replace("日期2", "日期1")
    plan["staticPresentation"] = plan["staticPresentation"].replace("替换", "日期2")
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")
    assert static_plan_capacity_errors(plan, "2x4")


def test_partial_required_fact_is_not_optional_inventory():
    plan = _plan()
    plan["staticPresentation"] = _source().replace("日期2", "日期")
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")
    assert static_plan_capacity_errors(plan, "2x4")


def test_unreachable_required_words_cannot_prove_candidate_coverage():
    plan = _plan()
    candidate = _source().replace("日期2", "错误")
    candidate += '\n["orphan", "EmphasisText", {"mainText": "对象2；日期2"}]'
    plan["staticPresentation"] = candidate
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")


def test_candidate_cannot_hide_fact_missing_from_group_inventory():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"requirement": "必要说明", "priority": "must", "text": "必要说明"})
    plan["staticPresentation"] = _source()
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")


def test_valid_alternative_component_is_measured_instead_of_records_preference():
    plan = _plan(4)
    for fact in plan.get("info_required", []):
        fact["priority"] = "must"
    plan["staticPresentation"] = _source(4, component="SingleLineList")
    assert static_plan_candidate_preserves_required_content(plan, "2x4")
    assert not static_plan_capacity_errors(plan, "2x4")
    assert all(item.visible for item in static_fact_coverage(plan["staticPresentation"], plan))


def test_three_records_and_required_title_can_use_valid_alternative_component():
    plan = _plan(3)
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    assert isinstance(facts, list) and isinstance(groups, list)
    facts.append({
        "requirement": "年度安排", "priority": "must", "text": "年度安排",
        "sourceTexts": ["年度安排"], "displayRole": "title",
    })
    groups.append({"id": "shared", "kind": "shared", "identity": None, "factIndexes": [3]})
    plan["staticPresentation"] = _source(component="SingleLineList", header="年度安排")
    assert static_plan_candidate_preserves_required_content(plan, "2x4")
    plan["staticPresentation"] = _source(header="年度安排")
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")


def test_actual_geometry_still_rejects_too_many_single_line_rows():
    plan = _plan()
    plan["staticPresentation"] = _source(8, component="SingleLineList")
    assert not static_plan_candidate_preserves_required_content(plan, "2x4")
    assert static_plan_capacity_errors(plan, "2x4")


def test_final_dsl_validation_cannot_borrow_legal_plan_candidate():
    plan = _plan()
    plan["staticPresentation"] = _source()
    assert not static_plan_capacity_errors(plan, "2x4")
    with pytest.raises(CompactDslValidationError):
        _validate(_source(4), plan)


def test_dynamic_policy_does_not_gain_static_candidate_exception():
    plan = _plan()
    plan["staticPresentation"] = _source()
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        assert not static_plan_candidate_preserves_required_content(plan, "2x4")
        assert static_plan_capacity_errors(plan, "2x4")
