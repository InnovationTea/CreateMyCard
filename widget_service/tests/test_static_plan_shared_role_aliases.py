"""共享辅助文字别名只恢复正文语义，不改变对象角色、事实或容量合同。"""

import copy
import json

import pytest

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


def test_schema_explains_shared_and_object_aliases_without_removing_canonical_roles():
    tool = build_compact_plan_tool(_task(_plan(), "2x4"))
    fields = tool.get("function", {}).get("parameters", {}).get("properties", {})
    group_fields = fields.get("contentGroups", {}).get("items", {}).get("properties", {})
    role = group_fields.get("facts", {}).get("items", {}).get("properties", {}).get("displayRole")
    assert isinstance(role, dict)
    assert {"title", "body", "secondaryText"}.issubset(role.get("enum", []))
    description = role.get("description", "")
    assert "在shared组归一为body" in description
    assert "在object组保留原title语义" in description
    assert "显式title不改" in description
