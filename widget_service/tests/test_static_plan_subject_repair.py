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
