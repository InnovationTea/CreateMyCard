"""共享辅助文字别名只恢复正文语义，不改变对象角色、事实或容量合同。"""

import copy
import json

import pytest

from services.card_validation.compact_validation.semantic.static_content import static_group_errors
from services.compact_plan import (
    CompactPlanValidationError,
    build_compact_plan_tool,
    parse_compact_plan_call,
)
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope


@pytest.fixture(autouse=True)
def static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def _fact(text, role="body", priority="must", protected=False):
    return {
        "requirement": text, "text": text, "sourceTexts": [text], "priority": priority,
        "displayRole": role, "protectedTexts": [text] if protected else [],
        "preserveVerbatim": protected,
    }


def _plan(shared_role="secondaryText", priority="must", protected=False):
    return {
        "info_required": [
            _fact("甲项", "label"), _fact("完整内容"),
            _fact("适用于全部项目", shared_role, priority, protected),
        ],
        "contentGroups": [
            {"id": "object", "kind": "object", "identity": None, "factIndexes": [0, 1]},
            {"id": "note", "kind": "shared", "identity": None, "factIndexes": [2]},
        ],
        "omittedContents": [],
    }


def _task(plan, size):
    return {
        "userQuery": "；".join(fact.get("text", "") for fact in plan.get("info_required", [])),
        "size": size, "dataModelSchema": {"data": {}},
        "assetCandidates": [], "eventCandidates": [],
        "appVersion": "11.8.8.512",
    }


def _accept(plan, size="2x4"):
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    return parse_compact_plan_call(
        raw, _task(plan, size), require_static_identity=True, require_static_omission_refs=True,
    ).plan


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("priority,protected", [("must", False), ("should", False), ("must", True)])
def test_shared_alias_preserves_all_fact_metadata_and_group_membership(size, priority, protected):
    plan = _plan(priority=priority, protected=protected)
    before = copy.deepcopy(plan)
    accepted = _accept(plan, size)
    original = plan.get("info_required")
    actual = accepted.get("info_required")
    assert original and actual
    expected = {**original[2], "displayRole": "body"}
    assert actual[2] == expected
    assert actual[:2] == original[:2]
    assert accepted.get("contentGroups") == plan.get("contentGroups")
    assert accepted.get("omittedContents") == []
    assert not accepted.get("omissionCandidates")
    assert plan == before


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_object_secondary_alias_keeps_existing_title_semantics(size):
    plan = _plan()
    facts = plan.get("info_required")
    assert facts
    facts[0]["displayRole"] = "secondaryText"
    accepted = _accept(plan, size)
    actual = accepted.get("info_required")
    assert actual
    assert actual[0] == {**facts[0], "displayRole": "title"}
    assert actual[2].get("displayRole") == "body"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_explicit_shared_title_is_not_reclassified(size):
    plan = _plan(shared_role="title")
    accepted = _accept(plan, size)
    assert accepted.get("info_required") == plan.get("info_required")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_missing_shared_membership_is_still_rejected(size):
    plan = _plan()
    groups = plan.get("contentGroups")
    assert groups
    groups.pop()
    with pytest.raises(CompactPlanValidationError, match="必须归属contentGroups"):
        _accept(plan, size)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_alias_does_not_resolve_conflicting_group_membership(size):
    plan = _plan()
    groups = plan.get("contentGroups")
    assert groups
    groups.append({"id": "conflict", "kind": "object", "identity": None, "factIndexes": [2]})
    with pytest.raises(CompactPlanValidationError, match="只能归属一个组"):
        _accept(plan, size)


def _three_records():
    facts = [
        _fact("谷段 23:00–次日7:00", "primaryText"), _fact("0.42元/度", "value"),
        _fact("平段 7:00–10:00、15:00–18:00", "primaryText"), _fact("0.78元/度", "value"),
        _fact("峰段 11:00–14:00、18:00–21:00", "primaryText"), _fact("1.16元/度", "value"),
        _fact("服务费另收0.55元/度", "secondaryText"),
    ]
    groups = []
    for index, name in enumerate(("谷段", "平段", "峰段")):
        groups.append({"id": f"period{index}", "kind": "object", "identity": name,
                       "factIndexes": [index * 2, index * 2 + 1]})
    groups.append({"id": "shared", "kind": "shared", "identity": None, "factIndexes": [6]})
    return {"info_required": facts, "contentGroups": groups, "presentationStyle": "records",
            "layoutHints": ["W-static-content"], "omittedContents": []}


def test_three_long_records_keep_shared_alias_and_report_new_panel_capacity():
    plan = _three_records()
    accepted = _accept(plan)
    canonical = copy.deepcopy(plan)
    canonical_facts = canonical.get("info_required")
    assert canonical_facts
    canonical_facts[6]["displayRole"] = "body"
    assert accepted == _accept(canonical)
    source = accepted.get("staticPresentation")
    assert source is None
    assert accepted.get("staticPresentationFeedback")
    accepted_facts = accepted.get("info_required")
    assert accepted_facts
    assert accepted_facts[6].get("displayRole") == "body"
    assert [fact.get("text") for fact in accepted_facts] == [
        fact.get("text") for fact in canonical_facts
    ]
    assert all(fact.get("priority") == "must" for fact in accepted_facts)


def test_real_required_title_without_legal_candidate_keeps_existing_rejection():
    plan = _three_records()
    facts = plan.get("info_required")
    assert facts
    facts[6] = _fact("共同说明内容" * 8, "title")
    with pytest.raises(CompactPlanValidationError, match="三条 records/TextList"):
        _accept(plan)


def test_schema_exposes_semantic_roles_instead_of_component_field_aliases():
    tool = build_compact_plan_tool(_task(_plan(), "2x4"))
    fields = tool.get("function", {}).get("parameters", {}).get("properties", {})
    group_fields = fields.get("contentGroups", {}).get("items", {}).get("properties", {})
    role = group_fields.get("facts", {}).get("items", {}).get("properties", {}).get("displayRole")
    assert isinstance(role, dict)
    assert set(role.get("enum", [])) == {
        "title", "body", "label", "value", "leading", "trailing", "detail",
    }
    description = role.get("description", "")
    assert "label为对象名称或短标签" in description
    assert "body为该对象说明" in description
    assert "value为短读数" in description


def _record_field_plan(presentation, hints):
    facts = [_fact("服务安排", "title")]
    groups = [{"id": "theme", "kind": "shared", "identity": None, "factIndexes": [0]}]
    for index, (name, detail) in enumerate((("甲服务", "须预约"), ("乙服务", "无需预约"))):
        indexes = []
        for text, role in ((name, "primaryText"), (detail, "secondaryText")):
            indexes.append(len(facts))
            fact = _fact(text, role, protected=True)
            if hints:
                fact["componentHints"] = hints
            facts.append(fact)
        groups.append({"id": f"service{index}", "kind": "object", "identity": name,
                       "factIndexes": indexes})
    return {"info_required": facts, "contentGroups": groups,
            "presentationStyle": presentation, "omittedContents": []}


@pytest.mark.parametrize("size,presentation,hints", [
    ("2x2", "records", []), ("2x4", "records", []),
    ("2x2", "auto", ["TextList"]), ("2x4", "auto", ["TextList"]),
    ("2x4", "records", ["TextList", "ComparisonGroup"]),
    ("2x4", "auto", ["TextList", "ComparisonGroup"]),
])
def test_record_aliases_keep_names_and_descriptions_in_consistent_slots(size, presentation, hints):
    plan = _record_field_plan(presentation, hints)
    original = copy.deepcopy(plan)
    accepted = _accept(plan, size)
    facts = accepted.get("info_required")
    original_facts = original.get("info_required")
    assert facts and original_facts
    assert len(facts) == len(original_facts) == 5
    for index in range(1, 5):
        expected_role = "label" if index % 2 else "body"
        assert facts[index] == {**original_facts[index],
                               "displayRole": expected_role}
    source = accepted.get("staticPresentation")
    assert source
    body = None
    for line in source.splitlines():
        row = json.loads(line)
        if row[0] == "body":
            body = row
            break
    assert body
    assert body[1] == "TextList"
    assert body[2].get("items") == [
        {"primaryText": "甲服务", "secondaryText": "须预约"},
        {"primaryText": "乙服务", "secondaryText": "无需预约"},
    ]
    assert not static_group_errors(source, accepted)
    assert accepted.get("contentGroups") == original.get("contentGroups")
    assert accepted.get("omittedContents") == []
    assert plan == original


@pytest.mark.parametrize("presentation,hints", [
    ("comparison", ["ComparisonGroup"]), ("auto", ["ComparisonGroup"]),
])
def test_comparison_context_preserves_legacy_value_and_title_aliases(presentation, hints):
    plan = _record_field_plan(presentation, hints)
    accepted = _accept(plan)
    facts = accepted.get("info_required")
    assert facts
    assert [fact.get("displayRole") for fact in facts] == [
        "title", "value", "title", "value", "title",
    ]


@pytest.mark.parametrize("presentation,hints", [
    ("comparison", ["TextList"]), ("records", ["ComparisonGroup"]),
])
def test_conflicting_presentation_and_component_hints_are_still_rejected(presentation, hints):
    with pytest.raises(CompactPlanValidationError, match="componentHints"):
        _accept(_record_field_plan(presentation, hints))


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_record_context_does_not_reclassify_explicit_semantic_roles(size):
    plan = _record_field_plan("records", ["TextList"])
    facts = plan.get("info_required")
    assert facts
    for index in range(1, 5):
        facts[index]["displayRole"] = "title" if index % 2 else "body"
    accepted = _accept(plan, size)
    assert accepted.get("info_required") == facts


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("invalid_hint", [{}, []])
def test_malformed_component_hint_uses_existing_plan_contract_error(size, invalid_hint):
    plan = _record_field_plan("records", [invalid_hint])
    with pytest.raises(CompactPlanValidationError) as error:
        _accept(plan, size)
    assert error.value.errors
