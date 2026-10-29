"""Design Compact 运行时容量提示上下文开关回归。"""

import json
from typing import Any

import pytest

import services.prompt_builder as prompt_builder_module
from config.config import get_settings
from models.generation import CompactDslRecoveryFact, CompactDslRetryContext, TaskSpec
from services.prompt_builder import PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID


def _task_spec() -> TaskSpec:
    return TaskSpec(
        userQuery="显示会议标题",
        size="2x2",
        dataModelSchema={
            "data": {
                "calendar": {
                    "title": {
                        "type": "string",
                        "description": "会议标题",
                        "sampleValue": "设计评审",
                    },
                    "location": {
                        "type": "string",
                        "description": "会议地点",
                        "sampleValue": "会议室",
                    },
                }
            }
        },
    )


def _compact_plan() -> dict[str, Any]:
    return {
        "info_required": [
            {
                "requirement": "会议标题",
                "dataId": "/data/calendar/title",
                "componentHints": ["SingleLineTitle"],
            }
        ],
        "layoutHints": ["S-title-content"],
    }


def _plan_tool_from_prompt(prompt: list[dict[str, str]]) -> dict[str, Any]:
    system = prompt[0]["content"]
    payload = system.split("# 可用工具合同\n\n", 1)[1]
    tool, _ = json.JSONDecoder().raw_decode(payload)
    return tool


def test_disabled_runtime_prompt_context_omits_plan_dsl_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(settings, "enable_design_compact_few_shots", False)

    def fail_if_called(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("disabled runtime prompt context must not run composition search")

    monkeypatch.setattr(
        prompt_builder_module,
        "feasible_composition_candidates",
        fail_if_called,
    )
    monkeypatch.setattr(
        prompt_builder_module,
        "composition_recovery_context",
        fail_if_called,
    )
    builder = PromptBuilder()
    task_spec = _task_spec()
    plan_prompt = builder.build_compact_plan(task_spec, "design rules", "{}")
    dsl_prompt = builder.build_design_token(
        task_spec,
        "design rules",
        DESIGN_COMPACT_PROFILE_ID,
        compact_plan=_compact_plan(),
    )

    assert "# Plan 分区与合组容量合同" not in plan_prompt[0]["content"]
    assert "# 本轮组合容量工作表" not in dsl_prompt[0]["content"]
    assert "legalLayoutAlternatives" not in dsl_prompt[0]["content"]
    assert "compositionRecovery" not in json.loads(dsl_prompt[1]["content"])
    assert "# 已接受的 Compact Info Plan" in dsl_prompt[0]["content"]
    tool_parameters = _plan_tool_from_prompt(plan_prompt)["function"]["parameters"]
    assert "composition" not in tool_parameters["properties"]
    assert tool_parameters["required"] == ["info_required"]


def test_enabled_runtime_prompt_context_includes_plan_dsl_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", True)
    monkeypatch.setattr(settings, "enable_design_compact_few_shots", False)
    constructive_result = {
        "status": "no_candidate_found",
        "candidates": [],
        "diagnostics": [],
    }
    monkeypatch.setattr(
        prompt_builder_module,
        "feasible_composition_candidates",
        lambda *_args, **_kwargs: constructive_result,
    )
    monkeypatch.setattr(
        prompt_builder_module,
        "composition_recovery_context",
        lambda *_args, **_kwargs: {"status": "test_recovery"},
    )
    monkeypatch.setattr(
        prompt_builder_module,
        "composition_implementation_conflicts",
        lambda *_args, **_kwargs: ["test composition conflict"],
    )
    builder = PromptBuilder()
    task_spec = _task_spec()
    plan_prompt = builder.build_compact_plan(task_spec, "design rules", "{}")
    dsl_prompt = builder.build_design_token(
        task_spec,
        "design rules",
        DESIGN_COMPACT_PROFILE_ID,
        compact_plan=_compact_plan(),
    )
    user_payload = json.loads(dsl_prompt[1]["content"])

    assert "# Plan 分区与合组容量合同" in plan_prompt[0]["content"]
    assert "# 本轮执行约束" in dsl_prompt[0]["content"]
    assert "referenceCanvasOnly" in dsl_prompt[0]["content"]
    assert user_payload["compositionRecovery"] == {"status": "test_recovery"}
    tool_parameters = _plan_tool_from_prompt(plan_prompt)["function"]["parameters"]
    assert "composition" in tool_parameters["properties"]
    assert tool_parameters["required"] == ["info_required", "composition"]


def test_capacity_recovery_plan_prompt_replans_components_and_priorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "enable_design_compact_runtime_prompt_context",
        False,
    )
    retry_context = CompactDslRetryContext(
        failure_category="layout_capacity",
        capacity_recovery=True,
        retained_facts=(
            CompactDslRecoveryFact(
                target="dataId",
                value="/data/calendar/title",
                requirement="会议标题",
                priority="must",
            ),
        ),
        omitted_facts=(
            CompactDslRecoveryFact(
                target="dataId",
                value="/data/calendar/location",
                requirement="会议地点",
                priority="must",
            ),
        ),
    )

    prompt = PromptBuilder().build_compact_plan(
        _task_spec(),
        "design rules",
        "{}",
        retry_context=retry_context,
    )

    system_prompt = prompt[0]["content"]
    assert "上一轮完整生成已经耗尽布局容量/结构修复预算" in system_prompt
    assert "优先选择占位更小且语义兼容的文本类组件" in system_prompt
    assert "不要依据该轮 capacityFits.doesNotFit 再删除仍然可见的信息" in system_prompt
    assert '"dataId":"/data/calendar/location"' in system_prompt
    tool = _plan_tool_from_prompt(prompt)
    fact_properties = tool["function"]["parameters"]["properties"]["info_required"]
    data_ids = fact_properties["items"]["properties"]["dataId"]["enum"]
    assert data_ids == ["/data/calendar/title"]
