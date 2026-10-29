"""静态分组修复保留需求主体；引用错误不等于可删除标题事实。"""

import copy
import json

import pytest

from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.prompt_builder import PLAN_JSON_OUTPUT_INSTRUCTION, PromptBuilder

QUERY = "展示星光巡演：2028年10月17日甲馆，10月24日乙馆，11月14日丙馆，11月28日丁馆，均19:00开演。"


def _fact(text, source, role="body"):
    return {
        "requirement": text, "text": text, "sourceTexts": [source], "priority": "must",
        "displayRole": role, "componentHints": ["ComparisonGroup"],
    }


def _plan():
    return {
        "info_required": [
            _fact("星光2028巡演", "星光巡演：2028年10月17日甲馆", "title"),
            _fact("10月17日 甲馆", "2028年10月17日甲馆"),
            _fact("10月24日 乙馆", "10月24日乙馆"),
            _fact("11月14日 丙馆", "11月14日丙馆"),
            _fact("11月28日 丁馆", "11月28日丁馆"),
            _fact("均19:00开演", "均19:00开演"),
        ],
        "contentGroups": [
            {"id": "theme", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "a", "kind": "object", "identity": "甲馆", "factIndexes": [1]},
            {"id": "b", "kind": "object", "identity": "乙馆", "factIndexes": [2]},
            {"id": "c", "kind": "object", "identity": "丙馆", "factIndexes": [3]},
            {"id": "d", "kind": "object", "identity": "丁馆", "factIndexes": [4]},
            {"id": "time", "kind": "shared", "identity": None, "factIndexes": [5]},
        ],
        "layoutHints": ["W-static-content"], "presentationStyle": "comparison",
        "omittedContents": [],
    }


def _raw(plan):
    return json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)


def _parse(plan):
    return parse_compact_plan_call(_raw(plan), {"userQuery": QUERY, "size": "2x4"})


def _repair(plan, errors, policy=STATIC_CONTENT_POLICY):
    raw = _raw(plan)
    messages = [
        {"role": "system", "content": "当前Plan合同"},
        {"role": "user", "content": QUERY},
        {"role": "assistant", "content": raw},
    ]
    before = copy.deepcopy(messages)
    with content_policy_scope(policy):
        repaired = PromptBuilder.build_compact_plan_repair(messages, raw, errors)
    assert messages == before
    assert repaired[:-1] == before
    assert len(repaired) == len(messages) + 1
    return json.loads(repaired[-1].get("content", ""))


def test_shared_fact_membership_error_does_not_authorize_removing_subject_or_year():
    plan = _plan()
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    groups.pop()
    for group in groups[1:]:
        group["factIndexes"].append(5)
    before = copy.deepcopy(plan)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError) as caught:
            _parse(plan)
    assert len(caught.value.errors) == 3
    assert all("只能归属一个组" in error for error in caught.value.errors)
    payload = _repair(plan, caught.value.errors)
    instruction = payload.get("instruction", "")
    assert "原始需求的主体、年份和作用范围即使放在header也不是装饰" in instruction
    assert "应移到现有合法显示字段，不能删除信息凑结构" in instruction
    assert "但应移除模型自行新增且用户未要求的装饰标题事实" not in instruction
    ledger = payload.get("staticPlanReferences", {})
    assert ledger.get("facts", [])[0].get("text") == "星光2028巡演"
    assert ledger.get("facts", [])[0].get("priority") == "must"
    assert plan == before
    with content_policy_scope(STATIC_CONTENT_POLICY):
        accepted = _parse(_plan()).plan
    assert accepted.get("info_required", [])[0].get("text") == "星光2028巡演"


def test_real_subject_with_wrong_citation_requires_citation_repair():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[0]["sourceTexts"] = ["不在本轮输入的引用"]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError) as caught:
            _parse(plan)
    assert any("COMPACT_STATIC_SOURCE_NOT_ALLOWED" in error for error in caught.value.errors)
    payload = _repair(plan, caught.value.errors)
    assert "来源引用错误先核对并修正引用" in payload.get("instruction", "")
    assert "只有来源诊断与原始输入共同确认是模型虚构" in payload.get("instruction", "")
    facts[0]["sourceTexts"] = ["星光巡演：2028年10月17日甲馆"]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert _parse(plan).plan.get("info_required", [])[0].get("text") == "星光2028巡演"


def test_proven_invented_decoration_can_be_removed_without_freezing_invalid_plan():
    plan = _plan()
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    assert isinstance(facts, list)
    assert isinstance(groups, list)
    facts.append(_fact("好运每日来", "好运每日来", "title"))
    groups.append({"id": "decoration", "kind": "shared", "identity": None, "factIndexes": [6]})
    assert "好运每日来" not in QUERY
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError) as caught:
            _parse(plan)
    assert any("COMPACT_STATIC_SOURCE_NOT_ALLOWED" in error for error in caught.value.errors)
    payload = _repair(plan, caught.value.errors)
    assert "且不承载用户要求的装饰文字才移除" in payload.get("instruction", "")
    facts.pop()
    groups.pop()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        accepted = _parse(plan).plan
    assert len(accepted.get("info_required", [])) == 6
    assert accepted.get("info_required", [])[0].get("text") == "星光2028巡演"


def test_dynamic_repair_keeps_exact_previous_instruction():
    payload = _repair(_plan(), ("原错误",), EXISTING_CONTENT_POLICY)
    assert payload.get("instruction") == (
        PLAN_JSON_OUTPUT_INSTRUCTION + " "
        "按本轮提供的合同修正计划或必要数据缺口报告，不得新增未开放的调用。"
        "不得删除用户要求来规避错误，但应移除模型自行新增且用户未要求的装饰标题事实。"
        "text 必须保留原文，不能只修改 requirement 后重复提交不合法的 text。"
        "不得生成 Compact DSL、Markdown 或解释。"
    )
    assert "staticPlanReferences" not in payload


def test_unaccepted_static_plan_repair_can_choose_records_and_reports_real_omission():
    plan = _plan()
    before = copy.deepcopy(plan)
    payload = _repair(plan, ("记录数超限",))
    instruction = payload.get("instruction", "")
    assert "本轮普通Plan尚未接受" in instruction
    assert "可以合理未选完整记录" in instruction
    assert "明确要求全部、完整或逐字展示时不得擅自省略" in instruction
    assert "已声明未选的完整记录不能仍以must保留在展示账本中" in instruction
    assert "description和空factIndexes记入omittedContents" in instruction
    assert "切换presentationStyle时同步正文componentHints" in instruction
    assert "SingleLineList仅适合实际能单行承载的短键值" in instruction
    assert "不是记录数超限的通用解法" in instruction
    assert plan == before


def test_record_capacity_error_keeps_original_gate_and_conditional_switch_guidance():
    from services.card_validation.compact_validation.semantic.layout.text_capacity import (
        static_plan_capacity_errors,
    )

    plan = _plan()
    plan["presentationStyle"] = "records"
    before = copy.deepcopy(plan)
    errors = static_plan_capacity_errors(plan, "2x4")
    assert len(errors) == 1
    assert errors[0].startswith("COMPACT_STATIC_TEXT_CAPACITY: TextList最多三项")
    assert "仅适合能完整单行承载的短键值" in errors[0]
    assert "恢复Plan仍须保持固定事实" in errors[0]
    assert "请改用单行列表" not in errors[0]
    assert plan == before


def test_long_venue_records_can_use_declared_selection_with_unchanged_contract():
    from services.card_validation import validate_compact_dsl

    title = "Rivergate 2031 · 19:30 local"
    records = [
        ("Blue Quartet", "Jun 4 · Grand Riverside Hall"),
        ("Silver Ensemble", "Jun 8 · Northbank Concert Hall"),
        ("Amber Trio", "Jun 12 · Mountain Theatre"),
        ("Cedar Orchestra", "Jun 19 · Lakeside Auditorium"),
    ]
    facts = [{
        "requirement": "共同主题和开演时间", "priority": "must", "text": title,
        "sourceTexts": [title], "displayRole": "title", "componentHints": ["SingleLineTitle"],
    }]
    groups = [{"id": "topic", "kind": "shared", "identity": None, "factIndexes": [0]}]
    for index, (name, venue) in enumerate(records, 1):
        text = f"{name} — Evening Set｜{venue}"
        facts.append({
            "requirement": text, "priority": "must", "text": text, "sourceTexts": [text],
            "displayRole": "body", "componentHints": ["TextList"],
        })
        groups.append({
            "id": f"record{index}", "kind": "object", "identity": name,
            "factIndexes": [index],
        })
    plan = {
        "info_required": facts, "contentGroups": groups, "omittedContents": [],
        "presentationStyle": "records", "layoutHints": ["W-static-content"],
    }
    query = "展示演出日程，可按容量选取完整场次。" + "；".join(
        fact.get("text", "") for fact in facts
    )
    task = {"size": "2x4", "userQuery": query, "dataModelSchema": {"data": {}}}
    before = copy.deepcopy(plan)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError, match="TextList最多三项"):
            parse_compact_plan_call(_raw(plan), task)
        selected = copy.deepcopy(plan)
        selected["info_required"] = facts[:3]
        selected["contentGroups"] = groups[:3]
        selected["omittedContents"] = [{
            "description": "未选后两场：Amber Trio、Cedar Orchestra", "factIndexes": [],
        }]
        accepted = parse_compact_plan_call(
            _raw(selected), task, require_static_identity=True, require_static_omission_refs=True,
        ).plan
        items = []
        for name, venue in records[:2]:
            items.append({"primaryText": f"{name} — Evening Set", "secondaryText": venue})
        source = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
            ["root", "Layout", {"layout": "W-static-content"}, ["header", "body"]],
            ["header", "SingleLineTitle", {"title": title}],
            ["body", "TextList", {"items": items}], ["/state/ready", True],
        ])
        validate_compact_dsl(
            source, task_spec=task, card_spec={"suggestSize": "2x4"}, compact_plan=accepted,
            layout_scope="W-static-content-guided",
        )
    assert accepted.get("omittedContents") == ["未选后两场：Amber Trio、Cedar Orchestra"]
    assert len(accepted.get("info_required", [])) == 3
    assert accepted.get("info_required", [])[1].get("text") == facts[1].get("text")
    assert accepted.get("info_required", [])[2].get("text") == facts[2].get("text")
    assert plan == before
