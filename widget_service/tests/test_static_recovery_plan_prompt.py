"""静态容量恢复把已有事实账本交给Plan，不改变首次提示或事实校验。"""

import copy
import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from models.generation import CompactDslRecoveryFact, CompactDslRetryContext, TaskSpec
from services.artifact_store import ArtifactStore
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
from services.widget_generation_service import WidgetGenerationService


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("提示构建回归不得访问网络")

    # 底层 socket 由离线运行器管控；不包装 Windows asyncio 的唤醒配对。
    monkeypatch.setattr(httpx.Client, "request", reject_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
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
        "contentGroups": [
            {"id": "topic", "kind": "shared", "identity": None, "facts": [
                {"id": "title", "text": "演出安排", "requirement": "主题", "priority": "must"},
            ]},
            {"id": "record", "kind": "object", "identity": None, "facts": [
                {
                    "id": "time",
                    "text": "11月7日–9日 每日19:30",
                    "requirement": "日期与时间",
                    "priority": "must",
                },
            ]},
        ],
        "omittedContents": [],
    }


def submitted_facts(submitted):
    groups = submitted.get("contentGroups")
    assert isinstance(groups, list)
    facts = []
    for group in groups:
        assert isinstance(group, dict)
        group_facts = group.get("facts")
        assert isinstance(group_facts, list)
        facts.extend(group_facts)
    return facts


def test_recovery_schema_keeps_visible_text_and_priority_together():
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY, context()))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    submitted = recovery_submission()
    assert not list(validator.iter_errors(submitted))
    facts = submitted_facts(submitted)
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
    facts = submitted_facts(submitted)
    facts[1]["text"] = "11月7日–9日"
    groups = submitted.get("contentGroups")
    assert isinstance(groups, list)
    record = groups[1]
    assert isinstance(record, dict)
    record_facts = record.get("facts")
    assert isinstance(record_facts, list)
    record_facts.append({
        "id": "time_extra", "text": "每日19:30", "requirement": "时间", "priority": "must",
    })
    assert list(Draft202012Validator(schema).iter_errors(submitted))


def test_same_visible_text_in_distinct_objects_does_not_make_schema_ambiguous():
    fact = CompactDslRecoveryFact("text", "每日19:30", "时间", "must")
    retry = CompactDslRetryContext(
        failure_category="layout_capacity", capacity_recovery=True,
        retained_facts=(fact, fact),
    )
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY, retry))
    submitted = recovery_submission()
    facts = submitted_facts(submitted)
    for value in facts:
        value["text"] = "每日19:30"
    assert not list(Draft202012Validator(schema).iter_errors(submitted))


def test_first_static_schema_allows_selection_but_recovery_is_frozen():
    schema = tool_schema_from(prompt(STATIC_CONTENT_POLICY))
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    groups = properties.get("contentGroups")
    assert isinstance(groups, dict)
    group_item = groups.get("items")
    assert isinstance(group_item, dict)
    group_fields = group_item.get("properties")
    assert isinstance(group_fields, dict)
    facts = group_fields.get("facts")
    assert isinstance(facts, dict)
    assert "本组事实" in facts.get("description", "")
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


def test_refinement_default_payload_is_unchanged_with_noncapacity_context():
    messages = [{"role": "system", "content": "原合同"}]
    feedback = ["候选组件尚未容纳完整文字"]
    expected_instruction = (
        "结构合法，但有限候选尚未排下，尚未冻结计划；不代表所有布局无解。"
        "请使用本阶段剩余的最后一次提交，按用户用途重新总结过长展示文字，"
        "拆出名称、短标签和读数，保留条件及或/且关系；长出处降为可选短说明。"
        "以最终可见文字核算整卡总行数，不只满足单字段行数。"
        "避免同一对象每句重复主体、周期和单位；共同适用范围写一次，"
        "必要人群、强度、范围、例外和替代关系不能列入遗漏。"
        "名称可与完整正文同放无标签属性行，避免额外标签行挤占容量。"
        "用户明确要求完整或原文时仍遵守，不由程序删除事实。"
        "本次只提交完整submit_card_plan，不输出DSL或原样重复过长计划。"
        "最后一次结构合法计划仍将交由DSL尝试，不新增模型阶段。"
    )
    original = PromptBuilder.build_static_plan_refinement(messages, feedback)
    noncapacity = PromptBuilder.build_static_plan_refinement(
        messages, feedback, retry_context=context(capacity_recovery=False),
    )
    assert original == noncapacity
    assert original[:-1] == messages
    assert messages == [{"role": "system", "content": "原合同"}]
    assert json.loads(original[-1].get("content", "")) == {
        "toolResult": {
            "name": "submit_card_plan", "ok": True,
            "accepted": False, "capacityReference": feedback,
        },
        "instruction": expected_instruction,
    }


def test_pre_freeze_refinement_allows_priority_based_object_selection():
    messages = [{"role": "system", "content": "原合同"}]
    refined = PromptBuilder.build_static_plan_refinement(
        messages,
        ["有限候选尚未排下"],
        allow_priority_degradation=True,
    )
    payload = json.loads(refined[-1].get("content", ""))
    instruction = payload.get("instruction", "")
    assert "原计划尚未冻结" in instruction
    assert "重新按用户用途和priority选择可承载的完整对象组" in instruction
    assert "从should开始不选" in instruction
    assert "省略整个低优先级object组" in instruction
    assert "用户明确要求全部、完整、原文、指定条目或受保护文字不得删除" in instruction


def test_recovery_refinement_keeps_frozen_scope_and_existing_schema():
    retry = context()
    messages = prompt(STATIC_CONTENT_POLICY, retry)
    refined = PromptBuilder.build_static_plan_refinement(
        messages, ["有限候选尚未排下"], retry_context=retry,
    )
    assert refined[:-1] == messages
    assert scope_from(refined) == scope_from(messages)
    payload = json.loads(refined[-1].get("content", ""))
    instruction = payload.get("instruction", "")
    assert "逐条保留requiredFacts的完整text、对应priority" in instruction
    assert "不得重新总结、摘要、改写、拆分、合并或删除事实条目" in instruction
    assert "不得降低优先级，不新增遗漏或重新加入excludedFacts" in instruction
    assert "同对象的字段分槽" in instruction
    assert "不要原样重复过长计划" not in instruction
    assert "按用户用途重新总结过长展示文字" not in instruction
    submitted = recovery_submission()
    validator = Draft202012Validator(tool_schema_from(refined))
    assert not list(validator.iter_errors(submitted))
    facts = submitted_facts(submitted)
    facts[1]["text"] = "11月7日–9日"
    assert list(validator.iter_errors(submitted))


@pytest.mark.asyncio
async def test_service_passes_recovery_scope_to_capacity_refinement(
    monkeypatch, isolated_theme_stage,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "enable_model_failure_retry", False)
    text = "必须保留的完整说明" * 40
    plan = {
        "info_required": [{
            "text": text, "requirement": "完整说明", "sourceTexts": [text],
            "priority": "must", "componentHints": ["EmphasisText"],
            "protectedTexts": [], "displayRole": "body",
        }],
        "contentGroups": [{
            "id": "detail", "kind": "object", "identity": None, "factIndexes": [0],
        }],
        "layoutHints": ["S-static-content"], "omittedContents": [],
    }
    request = GenerateWidgetCardRequest(
        uid="recovery-refinement", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery=text, size="2x2", title="完整说明", description="静态容量恢复",
    )
    request._compact_dsl_retry_context = CompactDslRetryContext(
        failure_category="layout_capacity", capacity_recovery=True,
        retained_facts=(CompactDslRecoveryFact("text", text, "完整说明", "must"),),
        omitted_facts=(CompactDslRecoveryFact("text", "可选附注", "附注", "should"),),
    )
    calls = []

    async def generate(_client, messages, profile=None, **kwargs):
        calls.append({
            "messages": copy.deepcopy(messages), "phase": kwargs.get("phase"),
            "format": (profile or {}).get("format"),
        })
        if (profile or {}).get("format") == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in [
            ["root", "Layout", {"layout": "S-static-content"}, ["body"]],
            ["body", "EmphasisText", {"mainText": text}], ["/state/ready", True],
        ])

    def reject_save(*_args, **_kwargs):
        raise AssertionError("仍然放不下的固定事实不能被发布为成功")

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", reject_save)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.FAILED
    assert len(calls) == 3
    assert [call.get("phase") for call in calls[:2]] == ["plan", "plan"]
    assert [call.get("format") for call in calls] == ["raw-json", "raw-json", "compact-dsl"]
    second_messages = calls[1].get("messages")
    assert isinstance(second_messages, list)
    refined = json.loads(second_messages[-1].get("content", ""))
    assert refined.get("toolResult", {}).get("capacityReference")
    assert "保持既有recovery_fact_scope固定账本" in refined.get("instruction", "")
    assert "按用户用途重新总结过长展示文字" not in refined.get("instruction", "")
    assert scope_from(second_messages) == scope_from(calls[0].get("messages", []))
    assert "staticPlanReview" not in json.dumps(second_messages)
