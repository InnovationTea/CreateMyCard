"""Design Compact 运行时容量提示上下文开关回归。"""

import json
from typing import Any

import pytest

import services.prompt_builder as prompt_builder_module
from config.config import get_settings
from models.generation import TaskSpec
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
                    }
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
    assert "# 本轮组合容量工作表" in dsl_prompt[0]["content"]
    assert "legalLayoutAlternatives" in dsl_prompt[0]["content"]
    assert user_payload["compositionRecovery"] == {"status": "test_recovery"}
