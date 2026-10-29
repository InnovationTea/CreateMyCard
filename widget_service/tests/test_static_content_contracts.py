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


def test_plan_rejects_conflicting_record_component_and_row_style():
    plan = {
        "info_required": [
            fact("中海寰宇时代", displayRole="title", componentHints=["TextList"]),
            fact("58600元/㎡，环比下跌1.2%", displayRole="body", componentHints=["TextList"]),
        ],
        "contentGroups": [{
            "id": "community",
            "kind": "object",
            "identity": "中海寰宇时代",
            "factIndexes": [0, 1],
        }],
        "presentationStyle": "rows",
    }
    task = {"userQuery": "中海寰宇时代58600元/㎡，环比下跌1.2%", "size": "2x4"}
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(
            CompactPlanValidationError,
            match="presentationStyle 与 componentHints 冲突",
        ):
            parse_compact_plan_call(raw, task)


def test_three_records_reject_a_required_shared_title_before_dsl_generation():
    facts = [fact("附近小区房价", displayRole="title")]
    groups = [{"id": "theme", "kind": "shared", "identity": None, "factIndexes": [0]}]
    communities = (
        ("中海寰宇时代", "58600元/㎡"),
        ("天通苑北一区", "41200元/㎡"),
        ("融泽嘉园", "46800元/㎡"),
    )
    for name, value in communities:
        title_index = len(facts)
        facts.append(fact(name, displayRole="title", componentHints=["TextList"]))
        value_index = len(facts)
        facts.append(fact(value, displayRole="value", componentHints=["TextList"]))
        groups.append({
            "id": name,
            "kind": "object",
            "identity": name,
            "factIndexes": [title_index, value_index],
        })
    plan = {
        "info_required": facts,
        "contentGroups": groups,
        "presentationStyle": "records",
    }
    task = {
        "userQuery": (
            "附近小区房价：中海寰宇时代58600元/㎡；天通苑北一区41200元/㎡；"
            "融泽嘉园46800元/㎡"
        ),
        "size": "2x4",
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(
            CompactPlanValidationError,
            match="三条 records/TextList 优先不设共同标题",
        ):
            parse_compact_plan_call(raw, task)


def test_dynamic_plan_tool_has_no_static_identity_roles_or_capacity_feedback():
    task = {"size": "2x4", "userQuery": "动态数据", "dataModelSchema": {"data": {}}}
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        tool = build_compact_plan_tool(task)
    encoded = json.dumps(tool)
    for static_key in ("identity", "displayRole", "contentGroups", "staticPresentationFeedback"):
        assert static_key not in encoded


def test_single_line_identity_candidate_keeps_names_and_complete_values():
    from services.static_content_presentation import static_presentation_candidates

    plan = {
        "info_required": [fact("30GB"), fact("60GB")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": "方案甲", "factIndexes": [0]},
            {"id": "b", "kind": "object", "identity": "方案乙", "factIndexes": [1]},
        ],
        "presentationStyle": "rows",
    }
    with content_policy_scope(STATIC_CONTENT_POLICY):
        candidates = static_presentation_candidates(plan, "2x4")
    inline = []
    for candidate in candidates:
        rows = [json.loads(line) for line in candidate.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        if body[1] == "SingleLineList" and body[2].get("items") == [
            {"text": "方案甲", "assist": "30GB"},
            {"text": "方案乙", "assist": "60GB"},
        ]:
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


@pytest.mark.parametrize("component,props,role", [
    ("EmphasisText", {"mainText": "完整内容", "secondaryText": "说明"}, "emphasis"),
    ("EmphasisText", {"mainText": "标题", "secondaryText": "完整内容"}, "emphasisSecondary"),
    ("SingleLineList", {"items": [{"text": "完整内容", "assist": "免费"}]}, "singleText"),
    ("SingleLineList", {"items": [{"text": "标签", "assist": "完整内容"}]}, "singleAssist"),
    ("ComparisonGroup", {"items": [
        {"primaryText": "完整内容"}, {"primaryText": "乙"},
    ]}, "comparisonPrimary"),
    ("ComparisonGroup", {"items": [
        {"primaryText": "甲", "secondaryText": "完整内容"}, {"primaryText": "乙"},
    ]}, "comparisonSecondary"),
])
def test_registered_semantic_font_preserves_role_hierarchy(component, props, role):
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    from services.static_content_context import standard_components
    from services.static_text_capacity import text_spec

    dsl = source(component, props)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        converted = convert_compact_dsl_to_a2ui(dsl, size="2x4")
    nodes = standard_components(converted)
    body = next(node for node in nodes.values() if node.get("content") == "完整内容")
    expected = text_spec(role)
    assert body.get("styles", {}).get("fontSize") == expected.get("fontSize")
    assert body.get("styles", {}).get("fontWeight") == expected.get("fontWeight")
    assert body.get("content") == "完整内容"


@pytest.mark.parametrize("font", [9, 8, 0, 10.5, 13, True, None, "11"])
def test_static_font_rejects_model_geometry_overrides(font):
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    from services.compact_high_level_components import CompactDslConversionError

    dsl = source("EmphasisText", {"mainText": "完整内容", "fontSize": font})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactDslConversionError, match="只允许字段"):
            convert_compact_dsl_to_a2ui(dsl, size="2x4")


def test_candidates_try_complete_content_before_optional_omission_without_font_override():
    from services.static_content_presentation import static_presentation_candidates

    plan = {
        "info_required": [fact("核心内容"), fact("补充内容", priority="should")],
        "contentGroups": [{"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]}],
    }
    candidates = static_presentation_candidates(plan, "2x2")
    last_complete = -1
    first_omitted = len(candidates)
    complete = []
    for index, candidate in enumerate(candidates):
        rows = [json.loads(line) for line in candidate.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        if "补充内容" in candidate:
            last_complete = index
            complete.append(candidate)
        else:
            first_omitted = min(first_omitted, index)
        assert "fontSize" not in body[2]
    assert last_complete < first_omitted
    assert complete
    assert first_omitted < len(candidates)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        for candidate in complete:
            assert not static_group_errors(candidate, plan)


def test_complex_core_content_remains_rejected_without_mutation_or_font_override():
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
    assert candidates == ()
    assert trial.attempted == 0
    assert "有限候选" in trial.errors[0]
    assert "不代表所有合法排版均不可行" in trial.errors[0]
