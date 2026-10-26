"""静态容量反馈、对象名称与带标签字段覆盖的通用回归。"""

import copy
import json

import pytest

from services.card_validation.compact_validation.semantic.static_content import (
    _fact_covered,
    static_group_errors,
)
from services.compact_plan import (
    CompactPlanValidationError,
    build_compact_plan_tool,
    parse_compact_plan_call,
)
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.static_content_presentation import trial_static_presentation


def fact(text, **extras):
    return {
        "requirement": "展示内容", "priority": "must", "text": text,
        "sourceTexts": [text], **extras,
    }


def source(component, props):
    rows = [
        ["root", "Layout", {"layout": "W-static-content"}, ["body"]],
        ["body", component, props], ["/state/ready", True],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("text,parts", [
    ("128元/月 · 30GB · 500分钟", ["128元/月", "国内流量30GB", "通话500分钟"]),
    ("30GB｜500分钟", ["国内流量30GB", "通话500分钟"]),
    ("示例对象128元/月", ["128元/月", "示例对象"]),
    ("输入2.50美元；输出10.00美元", ["每百万token输入2.50美元", "输出10.00美元"]),
])
def test_same_object_complete_fields_allow_labels_and_reordering(text, parts):
    assert _fact_covered(fact(text), parts)


@pytest.mark.parametrize("text,parts", [
    ("30GB", ["130GB"]), ("30GB", ["3", "0GB"]),
    ("500分钟", ["1500分钟"]), ("-5℃", ["5℃"]),
    ("5–7天", ["7天", "5天"]), ("不可入场", ["可入场", "不"]),
    ("30GB · 500分钟", ["国内流量30GB", "通话600分钟"]),
    ("GPT", ["ChatGPT"]), ("128元/月", ["128元/年"]),
])
def test_coverage_rejects_partial_tokens_changed_units_and_character_bags(text, parts):
    assert not _fact_covered(fact(text), parts)


def test_explicit_verbatim_does_not_use_formatting_tolerance():
    assert not _fact_covered(fact("30GB · 500分钟", preserveVerbatim=True), ["30GB", "500分钟"])


def test_named_objects_survive_candidate_recovery_and_cannot_share_names():
    plan = {
        "info_required": [fact("输入2.50；输出10.00"), fact("输入3.00；输出15.00")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": "模型甲", "factIndexes": [0]},
            {"id": "b", "kind": "object", "identity": "模型乙", "factIndexes": [1]},
        ],
    }
    query = "模型甲输入2.50；输出10.00；模型乙输入3.00；输出15.00"
    with content_policy_scope(STATIC_CONTENT_POLICY):
        trial = trial_static_presentation(plan, query, "2x4")
        assert trial.source is not None
        assert not static_group_errors(trial.source, plan)
        missing = trial.source.replace("模型甲", "")
        assert any("缺少对象名称" in error for error in static_group_errors(missing, plan))
        swapped = trial.source.replace("模型甲", "占位").replace("模型乙", "模型甲")
        swapped = swapped.replace("占位", "模型乙")
        assert static_group_errors(swapped, plan)


def test_named_plan_keeps_identity_and_rejects_missing_key_for_new_submissions():
    plan = {
        "info_required": [fact("30GB")],
        "contentGroups": [{"id": "x", "kind": "object", "identity": "方案甲", "factIndexes": [0]}],
    }
    task = {"userQuery": "方案甲30GB", "size": "2x4"}
    with content_policy_scope(STATIC_CONTENT_POLICY):
        raw = json.dumps({"name": "submit_card_plan", "arguments": plan})
        result = parse_compact_plan_call(raw, task, require_static_identity=True)
        groups = result.plan.get("contentGroups")
        assert groups and groups[0].get("identity") == "方案甲"
        legacy = copy.deepcopy(plan)
        legacy_groups = legacy.get("contentGroups")
        assert legacy_groups
        legacy_groups[0].pop("identity")
        raw = json.dumps({"name": "submit_card_plan", "arguments": legacy})
        with pytest.raises(CompactPlanValidationError, match="identity"):
            parse_compact_plan_call(raw, task, require_static_identity=True)
        assert parse_compact_plan_call(raw, task).plan


def test_no_eligible_candidate_still_returns_capacity_feedback_without_deleting_plan():
    facts = []
    groups = []
    for index in range(7):
        facts.append(fact(f"对象{index}"))
        groups.append({
            "id": str(index), "kind": "object", "identity": None, "factIndexes": [index],
        })
    plan = {"info_required": facts, "contentGroups": groups}
    before = copy.deepcopy(plan)
    query = "；".join(item.get("text", "") for item in facts)
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        result = parse_compact_plan_call(raw, {"userQuery": query, "size": "2x4"})
    assert result.plan.get("staticPresentationFeedback")
    assert result.plan.get("info_required") == before.get("info_required")
    assert plan == before


def test_dynamic_plan_tool_has_no_static_identity_roles_or_capacity_feedback():
    task = {"size": "2x4", "userQuery": "动态数据", "dataModelSchema": {"data": {}}}
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        tool = build_compact_plan_tool(task)
    encoded = json.dumps(tool)
    for static_key in ("identity", "displayRole", "contentGroups", "staticPresentationFeedback"):
        assert static_key not in encoded


def test_inline_identity_candidate_keeps_names_without_extra_label_lines():
    from services.static_content_presentation import static_presentation_candidates

    plan = {
        "info_required": [fact("30GB"), fact("60GB")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": "方案甲", "factIndexes": [0]},
            {"id": "b", "kind": "object", "identity": "方案乙", "factIndexes": [1]},
        ],
        "presentationStyle": "attributes",
    }
    with content_policy_scope(STATIC_CONTENT_POLICY):
        candidates = static_presentation_candidates(plan, "2x4")
    inline = []
    for candidate in candidates:
        rows = [json.loads(line) for line in candidate.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        if body[2].get("attributes") == [{"value": "方案甲：30GB"}, {"value": "方案乙：60GB"}]:
            inline.append(candidate)
    assert inline
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert not static_group_errors(inline[0], plan)


def test_actions_without_trial_support_do_not_consume_capacity_refinement_budget():
    plan = {"info_required": [{"actionId": "approved", "priority": "must"}]}
    with content_policy_scope(STATIC_CONTENT_POLICY):
        trial = trial_static_presentation(plan, "任意主题", "2x2")
    assert trial.source is None
    assert trial.attempted == 0
    assert not trial.errors


@pytest.mark.parametrize("font", [12, 11, 10, 12.0, 11.0, 10.0])
def test_registered_body_font_preserves_title_and_primary_hierarchy(font):
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    from services.static_content_context import standard_components

    dsl = source("ContentBlock", {"title": "可见标题", "body": "完整内容", "fontSize": font})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        converted = convert_compact_dsl_to_a2ui(dsl, size="2x4")
    nodes = standard_components(converted)
    title = nodes.get("body__static_title")
    body = nodes.get("body__static_body")
    assert title and body
    assert title.get("styles", {}).get("fontSize") == 16
    assert body.get("styles", {}).get("fontSize") == font
    assert body.get("content") == "完整内容"


@pytest.mark.parametrize("font", [9, 8, 0, 10.5, 13, True, None, "11"])
def test_static_font_rejects_values_below_floor_or_outside_registered_steps(font):
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    from services.compact_high_level_components import CompactDslConversionError

    dsl = source("ContentBlock", {"body": "完整内容", "fontSize": font})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactDslConversionError, match="最小为10"):
            convert_compact_dsl_to_a2ui(dsl, size="2x4")


def test_candidates_try_smaller_complete_content_before_optional_omission():
    from services.static_content_presentation import static_presentation_candidates

    plan = {
        "info_required": [fact("核心内容"), fact("补充内容", priority="should")],
        "contentGroups": [{"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]}],
    }
    candidates = static_presentation_candidates(plan, "2x2")
    last_complete = -1
    first_omitted = len(candidates)
    sizes = []
    for index, candidate in enumerate(candidates):
        rows = [json.loads(line) for line in candidate.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        if "补充内容" in candidate:
            last_complete = index
            sizes.append(body[2].get("fontSize", 12))
        else:
            first_omitted = min(first_omitted, index)
    assert last_complete < first_omitted
    assert sizes == sorted(sizes, reverse=True)
    assert set(sizes) == {12, 11, 10}


def test_complex_core_content_remains_rejected_at_minimum_font_without_mutation():
    from services.static_content_presentation import static_presentation_candidates

    facts = []
    groups = []
    for index in range(6):
        facts.append(fact(f"对象{index}：" + "不可省略的完整必要说明" * 50))
        groups.append({
            "id": str(index), "kind": "object", "identity": None, "factIndexes": [index],
        })
    plan = {"info_required": facts, "contentGroups": groups}
    before = copy.deepcopy(plan)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        trial = trial_static_presentation(plan, "复杂但要求完整的输入", "2x4")
        candidates = static_presentation_candidates(plan, "2x4")
    assert trial.source is None
    assert trial.errors
    assert plan == before
    sizes = []
    for candidate in candidates:
        rows = [json.loads(line) for line in candidate.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        sizes.append(body[2].get("fontSize", 12))
    assert sizes and min(sizes) == 10
    assert set(sizes) == {12, 11, 10}
