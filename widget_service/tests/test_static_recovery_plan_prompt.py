"""静态容量恢复把已有事实账本交给Plan，不改变首次提示或事实校验。"""

import json
import socket

import pytest

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
        repaired = PromptBuilder.build_compact_plan_repair(messages, json.dumps(invalid), errors)
    assert scope_from(repaired) == scope_from(messages)
    assert repaired[0] == messages[0]
    assert len(repaired) == 5
