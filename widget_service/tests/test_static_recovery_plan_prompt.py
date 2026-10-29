"""静态容量恢复把已有事实账本交给Plan，不改变首次提示或事实校验。"""

import json
import socket

import pytest
from jsonschema import Draft202012Validator

from config.config import get_settings
from models.generation import CompactDslRecoveryFact, CompactDslRetryContext, TaskSpec
from services.compact_plan import compact_recovery_plan_errors
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.prompt_builder import (
    _CAPACITY_RECOVERY_PLAN_INSTRUCTION,
    PromptBuilder,
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("提示构建回归不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    monkeypatch.setattr(get_settings(), "enable_design_compact_runtime_prompt_context", False)


def context(*, capacity_recovery=True):
    return CompactDslRetryContext(
        failure_category="layout_capacity",
        capacity_recovery=capacity_recovery,
        retained_facts=(
            CompactDslRecoveryFact("text", "演出安排", "共同主题", "must"),
            CompactDslRecoveryFact("text", "11月7日–9日 每日19:30", "日期及开演时间", "must"),
        ),
        omitted_facts=(CompactDslRecoveryFact("text", "余票紧张", "余票状态", "must"),),
    )


def prompt(policy, retry=None):
    task = TaskSpec(userQuery="显示演出安排和余票", size="2x4", dataModelSchema={"data": {}})
    with content_policy_scope(policy):
        return PromptBuilder().build_compact_plan(task, "design rules", "{}", retry_context=retry)


def scope_from(messages):
    system = messages[0].get("content")
    assert isinstance(system, str)
    payload = system.split("<recovery_fact_scope>", 1)[1]
    return json.loads(payload.split("</recovery_fact_scope>", 1)[0])


def tool_schema_from(messages):
    system = messages[0].get("content")
    assert isinstance(system, str)
    payload = system.split("# 可用工具合同\n\n", 1)[1]
    tool, _ = json.JSONDecoder().raw_decode(payload)
    function = tool.get("function")
    assert isinstance(function, dict)
    schema = function.get("parameters")
    assert isinstance(schema, dict)
    return schema


def recovery_submission():
    return {
        "info_required": [
            {"text": "演出安排", "requirement": "主题", "priority": "must"},
            {
                "text": "11月7日–9日 每日19:30", "requirement": "日期与时间",
                "priority": "must",
            },
        ],
        "contentGroups": [
            {"id": "topic", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "record", "kind": "object", "identity": None, "factIndexes": [1]},
        ],
        "omittedContents": [],
    }


def test_recovery_schema_keeps_visible_text_and_priority_together():
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY, context()))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    submitted = recovery_submission()
    assert not list(validator.iter_errors(submitted))
    facts = submitted.get("info_required")
    assert isinstance(facts, list)
    facts[1]["text"] = "11月7日–9日"
    assert list(validator.iter_errors(submitted))
    facts[1]["text"] = "11月7日–9日 每日19:30"
    facts[1]["priority"] = "should"
    assert list(validator.iter_errors(submitted))
    facts[1]["priority"] = "must"
    facts[1]["text"] = "余票紧张"
    assert list(validator.iter_errors(submitted))


def test_recovery_schema_rejects_splitting_a_retained_fact_into_new_entries():
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY, context()))
    submitted = recovery_submission()
    facts = submitted.get("info_required")
    assert isinstance(facts, list)
    facts[1]["text"] = "11月7日–9日"
    facts.append({"text": "每日19:30", "requirement": "时间", "priority": "must"})
    assert list(Draft202012Validator(schema).iter_errors(submitted))


def test_same_visible_text_in_distinct_objects_does_not_make_schema_ambiguous():
    fact = CompactDslRecoveryFact("text", "每日19:30", "时间", "must")
    retry = CompactDslRetryContext(
        failure_category="layout_capacity", capacity_recovery=True,
        retained_facts=(fact, fact),
    )
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY, retry))
    submitted = recovery_submission()
    facts = submitted.get("info_required")
    assert isinstance(facts, list)
    for value in facts:
        value["text"] = "每日19:30"
    assert not list(Draft202012Validator(schema).iter_errors(submitted))


def test_first_static_schema_allows_selection_but_recovery_is_frozen():
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY))
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    facts = properties.get("info_required")
    assert isinstance(facts, dict)
    assert "全部原文清单" in facts.get("description", "")
    item = facts.get("items")
    assert isinstance(item, dict)
    assert "allOf" not in item
    fields = item.get("properties")
    assert isinstance(fields, dict)
    assert "enum" not in fields.get("text", {})
    assert "逐字" in fields.get("priority", {}).get("description", "")
    existing = tool_schema_from(prompt(EXISTING_CONTENT_POLICY))
    assert "全部原文清单" not in json.dumps(existing, ensure_ascii=False)


@pytest.mark.parametrize("runtime_context", [False, True])
def test_static_recovery_keeps_explicit_scope_without_composition(monkeypatch, runtime_context):
    monkeypatch.setattr(
        get_settings(), "enable_design_compact_runtime_prompt_context", runtime_context,
    )
    messages = prompt(STATIC_CONTENT_POLICY, context())
    assert scope_from(messages) == {
        "requiredFacts": [
            {"text": "演出安排", "requirement": "共同主题", "priority": "must"},
            {"text": "11月7日–9日 每日19:30", "requirement": "日期及开演时间", "priority": "must"},
        ],
        "excludedFacts": [{"text": "余票紧张", "requirement": "余票状态"}],
    }
    system = messages[0].get("content", "")
    assert "逐条保持text和priority原样" in system
    assert "不删除保留清单中的标题" in system
    assert "# Plan 分区与合组容量合同" not in system
    assert "compositionRecovery" not in system
    assert "SecondaryBody" not in system
    assert len(messages) == 3


@pytest.mark.parametrize("policy", [STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY])
def test_first_plan_ignores_noncapacity_retry_scope(policy):
    first = prompt(policy)
    assert first == prompt(policy, context(capacity_recovery=False))
    assert "<recovery_fact_scope>" not in first[0].get("content", "")


def test_dynamic_recovery_keeps_original_instruction_and_scope():
    messages = prompt(EXISTING_CONTENT_POLICY, context())
    system = messages[0].get("content", "")
    assert _CAPACITY_RECOVERY_PLAN_INSTRUCTION in system
    assert "不删除保留清单中的标题" not in system
    assert scope_from(messages) == scope_from(prompt(STATIC_CONTENT_POLICY, context()))


def test_repair_conversation_keeps_scope_and_exact_fact_validation():
    retry = context()
    messages = prompt(STATIC_CONTENT_POLICY, retry)
    invalid = {
        "info_required": [
            {"text": "演出安排", "priority": "must"},
            {"text": "11月7日—9日 每日19:30", "priority": "must"},
        ],
    }
    errors = compact_recovery_plan_errors(invalid, retry.retained_facts)
    assert len(errors) == 2
    with content_policy_scope(STATIC_CONTENT_POLICY):
        repaired = PromptBuilder.build_compact_plan_repair(
            messages, json.dumps(invalid), errors, retry_context=retry,
        )
    assert scope_from(repaired) == scope_from(messages)
    assert repaired[0] == messages[0]
    assert len(repaired) == 5
    payload = json.loads(repaired[-1].get("content", ""))
    instruction = payload.get("instruction", "")
    assert "本轮为接口容量恢复" in instruction
    assert "逐条保留requiredFacts的完整text、对应priority" in instruction
    assert "不得摘要、改写、拆分、合并或新增事实" in instruction
    assert "不重加excludedFacts" in instruction
    assert "仍允许忠于sourceTexts的摘要" not in instruction
    assert "可以合理未选完整记录" not in instruction
    assert "切换presentationStyle时同步正文componentHints" in instruction
    assert payload.get("toolResult", {}).get("errors") == list(errors)


@pytest.mark.parametrize("policy", [STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY])
def test_noncapacity_retry_context_keeps_normal_plan_repair(policy):
    messages = prompt(policy)
    with content_policy_scope(policy):
        original = PromptBuilder.build_compact_plan_repair(messages, "错误计划", ("缺组",))
        repaired = PromptBuilder.build_compact_plan_repair(
            messages, "错误计划", ("缺组",), retry_context=context(capacity_recovery=False),
        )
    assert original == repaired


def test_dynamic_repair_does_not_acquire_static_recovery_contract():
    messages = prompt(EXISTING_CONTENT_POLICY, context())
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        original = PromptBuilder.build_compact_plan_repair(messages, "错误计划", ("缺组",))
        repaired = PromptBuilder.build_compact_plan_repair(
            messages, "错误计划", ("缺组",), retry_context=context(),
        )
    assert original == repaired
