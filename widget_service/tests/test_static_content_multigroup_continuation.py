"""明确同一对象的安全连续行；不跨组借用事实或重新切分原文。"""

import copy
import json

import pytest

from services.card_validation.compact_validation.semantic.static_content import (
    static_fact_coverage,
    static_group_errors,
)
from services.compact_high_level_components import CompactDslConversionError
from services.compact_plan import compact_plan_omitted_facts
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.static_content_components import complete_static_text_trial


@pytest.fixture(autouse=True)
def static_policy():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def _case():
    texts = (
        ("2026考研时间", "title"),
        ("预报名", "label"),
        ("2025年10月10日至10月13日", "value"),
        ("正式报名", "label"),
        ("2025年10月16日至10月27日", "value"),
        ("每日9:00至22:00", "detail"),
        ("初试", "label"),
        ("2025年12月20日至12月21日", "value"),
    )
    facts = []
    for text, role in texts:
        facts.append({"text": text, "requirement": text, "sourceTexts": [text],
                      "priority": "must", "displayRole": role,
                      "componentHints": ["SingleLineList"]})
    plan = {
        "info_required": facts, "layoutHints": ["W-static-content"],
        "contentGroups": [
            {"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "pre", "kind": "object", "identity": "预报名", "factIndexes": [1, 2]},
            {"id": "formal", "kind": "object", "identity": "正式报名", "factIndexes": [3, 4, 5]},
            {"id": "exam", "kind": "object", "identity": "初试", "factIndexes": [6, 7]},
        ],
    }
    items = [
        {"text": "预报名", "assist": "2025年10月10日至10月13日"},
        {"text": "正式报名", "assist": "2025年10月16日至10月27日"},
        {"text": "正式报名", "assist": "每日9:00至22:00"},
        {"text": "初试", "assist": "2025年12月20日至12月21日"},
    ]
    return plan, items


def _source(items, extra=None):
    rows = [
        ["root", "Layout", {"layout": "W-static-content"}, ["header", "body"]],
        ["header", "SingleLineTitle", {"title": "2026考研时间"}],
        ["body", "SingleLineList", {"items": items}],
        ["/state/ready", True],
    ]
    rows.extend(extra or [])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _facts(plan):
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    return facts


def _groups(plan):
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    return groups


def test_complete_same_object_rows_keep_facts_source_and_fixed_geometry():
    plan, items = _case()
    source = _source(items)
    with content_policy_scope(STATIC_CONTENT_POLICY), complete_static_text_trial(True):
        assert not static_group_errors(source, plan)
        assert all(fact.visible for fact in static_fact_coverage(source, plan))
        result = DesignCompactProcessor().process(source, DslProcessingContext(
            size="2x4", task_spec={"size": "2x4", "userQuery": "展示报名与考试时间",
                                  "appVersion": "11.7.5.205", "romVersion": "6.0.0.328",
                                  "dataModelSchema": {"data": {}},
                                  "eventCandidates": [], "assetCandidates": []},
            card_spec={"suggestSize": "2x4"}, protocol_profile=None, compact_plan=plan,
            content_policy=STATIC_CONTENT_POLICY, layout_scope="W-static-content-guided",
        ))
    assert not result.errors
    assert [json.loads(line) for line in result.source_dsl.splitlines()] == [
        json.loads(line) for line in source.splitlines()
    ]
    components = []
    for line in result.standard_dsl.splitlines():
        components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    rendered_text = []
    body = None
    header = None
    for component in components:
        if component.get("component") == "Text":
            assert component.get("styles", {}).get("fontSize") == 12
            rendered_text.append(component.get("content"))
        if component.get("id") == "body":
            body = component
        if component.get("id") == "header":
            header = component
    assert body is not None and header is not None
    assert body.get("styles", {}).get("height") == 76
    assert header.get("styles", {}).get("height") == 16
    expected_text = ["2026考研时间"]
    for item in items:
        expected_text.extend(item.values())
    assert rendered_text == expected_text


@pytest.mark.parametrize("change", [
    "order", "duplicate", "unknown", "unknown_first", "missing_identity", "orphan",
    "fragment", "other_fact", "other_first_fact", "same_value", "same_name", "no_name",
])
def test_ambiguous_or_incomplete_continuations_are_rejected(change):
    plan, items = _case()
    extra = []
    if change == "order":
        items[2], items[3] = items[3], items[2]
    elif change == "duplicate":
        items.insert(3, copy.deepcopy(items[2]))
    elif change == "unknown":
        items[2]["assist"] += "；仅限周末"
    elif change == "unknown_first":
        items[1]["assist"] += "；仅限周末"
    elif change == "missing_identity":
        items[2]["text"] = "每日时段"
    elif change == "orphan":
        items.pop(2)
        extra.append(["orphan", "EmphasisText", {"mainText": "每日9:00至22:00"}])
    elif change == "fragment":
        items[2]["assist"] = "每日9:00至"
        items.insert(3, {"text": "正式报名", "assist": "22:00"})
    elif change == "other_fact":
        items[2]["assist"] += "；2025年12月20日至12月21日"
    elif change == "other_first_fact":
        items[1]["assist"] += "；2025年12月20日至12月21日"
    elif change == "same_value":
        _facts(plan)[7]["text"] = "每日9:00至22:00"
        items[3]["assist"] = "每日9:00至22:00"
    elif change == "same_name":
        _groups(plan)[3]["identity"] = "正式报名"
    elif change == "no_name":
        _groups(plan)[2]["identity"] = None
    if change == "orphan":
        with pytest.raises(CompactDslConversionError, match="Unreachable"):
            static_group_errors(_source(items, extra), plan)
    else:
        assert static_group_errors(_source(items, extra), plan)


@pytest.mark.parametrize("protected", ["preserveVerbatim", "protectedTexts"])
def test_protected_whole_fact_remains_complete_in_one_row(protected):
    plan, items = _case()
    _facts(plan)[5][protected] = True if protected == "preserveVerbatim" else ["每日9:00至22:00"]
    assert not static_group_errors(_source(items), plan)
    items[2]["assist"] = "每日9:00至"
    items.insert(3, {"text": "正式报名", "assist": "22:00"})
    assert static_group_errors(_source(items), plan)


@pytest.mark.parametrize("still_visible", [False, True])
def test_authorized_fact_actual_omission_uses_the_same_object_mapping(still_visible):
    plan, items = _case()
    if not still_visible:
        items.pop(2)
    source = _source(items)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert not static_group_errors(source, plan, (5,))
        coverage = static_fact_coverage(source, plan, (5,))
        assert coverage[5].visible is still_visible
        omitted = compact_plan_omitted_facts(source, plan, {}, (5,))
    assert len(omitted) == (0 if still_visible else 1)
    if omitted:
        assert omitted[0].get("text") == "每日9:00至22:00"


def test_omitted_other_group_fact_still_blocks_ambiguous_continuation():
    plan, items = _case()
    _facts(plan)[7]["text"] = "每日9:00至22:00"
    items[3]["assist"] = "每日9:00至22:00"
    assert static_group_errors(_source(items), plan, (7,))


def test_fully_authorized_multiline_object_retains_conservative_mapping_failure():
    plan, items = _case()
    source = _source(items)
    allowed = (3, 4, 5)
    errors = static_group_errors(source, plan, allowed)
    assert any("COMPACT_STATIC_GROUP_MISMATCH" in error for error in errors)
    coverage = static_fact_coverage(source, plan, allowed)
    assert coverage[5].text_present
    assert not coverage[5].visible
    # The rejected mapping is not evidence that the literal continuation was deleted.
    assert "每日9:00至22:00" in source
