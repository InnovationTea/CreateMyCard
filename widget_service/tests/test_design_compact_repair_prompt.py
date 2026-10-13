"""验证 Design Compact Repair 提示词保留通用、语义优先的修复流程。"""

import json

import pytest

from services.prompt_builder import REPAIR_SYSTEM_PROMPT, PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID


def _repair_feedback(messages: list[dict[str, str]]) -> dict:
    return json.loads(messages[-1]["content"])


def test_repair_system_prompt_requires_root_cause_and_regression_checks() -> None:
    assert "先恢复语义事实" in REPAIR_SYSTEM_PROMPT
    assert "再定位共同根因" in REPAIR_SYSTEM_PROMPT
    assert "按值形态选择结构" in REPAIR_SYSTEM_PROMPT
    assert "重算受影响子树" in REPAIR_SYSTEM_PROMPT
    assert "最后整体回归" in REPAIR_SYSTEM_PROMPT
    assert "TaskSpec 是值语义的唯一依据" in REPAIR_SYSTEM_PROMPT
    assert "已经包含单位的" in REPAIR_SYSTEM_PROMPT
    assert "不得追加或拆出单位" in REPAIR_SYSTEM_PROMPT
    assert "无损紧凑组件替换阶段" in REPAIR_SYSTEM_PROMPT
    assert "本阶段最多连续提交两次完整 Compact DSL" in REPAIR_SYSTEM_PROMPT
    assert "不启用可选信息删除" in REPAIR_SYSTEM_PROMPT
    assert "整组单行用14" in REPAIR_SYSTEM_PROMPT
    assert "多行用12；行高分别19和16" in REPAIR_SYSTEM_PROMPT
    assert "drop_optional_component" in REPAIR_SYSTEM_PROMPT
    assert "唯一可删的非 Action 业务展示组件" in REPAIR_SYSTEM_PROMPT
    assert "等待微服务根据剩余 DSL" in REPAIR_SYSTEM_PROMPT
    assert "必须删除指定组件行及其直接父级 children 引用" in REPAIR_SYSTEM_PROMPT
    assert "禁止原样返回" in REPAIR_SYSTEM_PROMPT
    assert "没有 repairStrategy 的兼容调用才以上一轮 DSL 为直接修复对象" in (REPAIR_SYSTEM_PROMPT)
    assert "首次修复时追加一次" in REPAIR_SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("scope", "expected_instruction"),
    [
        ("component", "以上一轮 Compact DSL 为直接修复对象"),
        ("sublayout", "重建报错所属信息组"),
        ("parent_layout", "允许替换整个报错父布局"),
        ("full_dsl", "上一轮 Compact DSL 只作为失败诊断与事实核对材料"),
    ],
)
def test_build_repair_changes_invalid_source_role_by_scope(
    scope: str,
    expected_instruction: str,
) -> None:
    messages = PromptBuilder().build_repair(
        [
            {"role": "system", "content": "create constraints"},
            {"role": "user", "content": '{"size":"2x4"}'},
        ],
        "invalid source",
        [
            {
                "stage": "validation",
                "code": "COMPACT_DSL_VALIDATION_FAILED",
                "message": "invalid structure",
            }
        ],
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
        repair_strategy={
            "category": "layout_structure",
            "scope": scope,
            "repairStrategy": "plan_guided_recompose",
            "retryTarget": "dsl_recompose",
            "instruction": "按当前范围修复。",
        },
    )

    payload = _repair_feedback(messages)
    instruction = payload["instruction"]
    assert expected_instruction in instruction
    if scope != "component":
        assert "以上一轮 Compact DSL 为直接修复对象" not in instruction


def test_build_repair_reinforces_semantic_and_related_structure_checks() -> None:
    initial_prompt = [
        {"role": "system", "content": "create constraints"},
        {"role": "user", "content": '{"size":"2x2"}'},
    ]
    quality_errors = [
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": "invalid display structure",
        }
    ]

    messages = PromptBuilder().build_repair(
        initial_prompt,
        "invalid source",
        quality_errors,
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
        compact_plan={
            "info_required": [
                {
                    "requirement": "核心信息",
                    "dataId": "/data/value",
                    "priority": "must",
                }
            ],
            "layoutHints": ["W-top-bottom"],
        },
        repair_strategy={
            "category": "layout_capacity",
            "scope": "parent_layout",
            "repairStrategy": "parent_layout_recompose",
            "retryTarget": "dsl_recompose",
            "instruction": "重新选择父布局变体。",
        },
    )

    assert messages[0]["content"] == "create constraints"
    assert messages[-3] == {"role": "assistant", "content": "invalid source"}
    assert messages[-2]["content"].startswith("<repair_contract>")
    assert REPAIR_SYSTEM_PROMPT in messages[-2]["content"]
    payload = _repair_feedback(messages)
    instruction = payload["instruction"]
    assert "字段类型与展示语义" in instruction
    assert "共同根因" in instruction
    assert "父容器" in instruction
    assert "重复单位" in instruction
    assert "允许替换整个报错父布局" in instruction
    assert "以上一轮 Compact DSL 为直接修复对象" not in instruction
    assert payload["qualityErrors"] == quality_errors
    assert "invalidSourceDsl" not in payload
    assert "repairContext" not in payload
    assert "originalUserContent" not in payload
    assert payload["toolResult"] == {
        "name": "validate_compact_dsl",
        "ok": False,
    }
    assert payload["repairStrategy"]["scope"] == "parent_layout"
    assert payload["repairStrategy"]["retryTarget"] == "dsl_recompose"
    assert "本轮修复路由：重新选择父布局变体。" in instruction


def test_build_repair_exposes_compact_component_fallback_budget() -> None:
    initial_prompt = [
        {"role": "system", "content": "create constraints"},
        {"role": "user", "content": '{"size":"2x4"}'},
    ]

    messages = PromptBuilder().build_repair(
        initial_prompt,
        "invalid source",
        [
            {
                "stage": "validation",
                "code": "COMPACT_DSL_VALIDATION_FAILED",
                "message": "vertical layout requires at least 142vp within 126vp",
            }
        ],
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
        repair_strategy={
            "category": "layout_capacity",
            "scope": "full_dsl",
            "repairStrategy": "compact_component",
            "retryTarget": "dsl_recompose",
            "fallbackStage": "compact_component",
            "fallbackAttempt": 0,
            "fallbackAttemptLimit": 2,
            "fallbackRemainingAttempts": 2,
            "instruction": "进入无损紧凑组件替换阶段。",
        },
    )

    payload = _repair_feedback(messages)
    strategy = payload["repairStrategy"]
    assert strategy["repairStrategy"] == "compact_component"
    assert strategy["fallbackStage"] == "compact_component"
    assert strategy["fallbackAttemptLimit"] == 2
    assert strategy["fallbackRemainingAttempts"] == 2
    assert "禁止沿用其旧拓扑" in payload["instruction"]
    assert "以上一轮 Compact DSL 为直接修复对象" not in payload["instruction"]
    assert "本轮修复路由：进入无损紧凑组件替换阶段。" in payload["instruction"]


def test_build_repair_exposes_the_only_allowed_optional_drop() -> None:
    messages = PromptBuilder().build_repair(
        [
            {"role": "system", "content": "create constraints"},
            {"role": "user", "content": '{"size":"2x4"}'},
        ],
        "invalid source",
        [
            {
                "stage": "validation",
                "code": "COMPACT_DSL_VALIDATION_FAILED",
                "message": "vertical layout requires at least 142vp within 126vp",
            }
        ],
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
        repair_history=[
            {
                "repairAttempt": 1,
                "sourceDsl": "older invalid source",
                "qualityErrors": [{"code": "COMPACT_DSL_VALIDATION_FAILED"}],
            }
        ],
        compact_plan={
            "info_required": [
                {
                    "requirement": "主信息",
                    "priority": "must",
                    "dataId": "/data/main",
                },
                {
                    "requirement": "按钮",
                    "priority": "must",
                    "actionId": "open",
                },
                {
                    "requirement": "补充时间",
                    "priority": "should",
                    "dataId": "/data/time",
                },
            ]
        },
        repair_strategy={
            "category": "layout_capacity",
            "scope": "full_dsl",
            "repairStrategy": "drop_optional_component",
            "retryTarget": "dsl_recompose",
            "fallbackStage": "drop_optional_component",
            "fallbackAttempt": 0,
            "fallbackAttemptLimit": 3,
            "fallbackRemainingAttempts": 3,
            "approvedOmittedFactIndexes": [2],
            "optionalDrop": {
                "componentId": "support",
                "componentType": "SecondaryBody",
                "allowedOmittedFactIndexes": [2],
                "requirements": ["补充时间"],
            },
            "instruction": "只删除指定的补充信息组件。",
        },
    )

    payload = _repair_feedback(messages)
    optional_drop = payload["repairStrategy"]["optionalDrop"]
    assert optional_drop["componentId"] == "support"
    assert optional_drop["allowedOmittedFactIndexes"] == [2]
    assert "repairHistory" not in payload
    assert payload["approvedOmissions"] == [
        {
            "factIndex": 2,
            "requirement": "补充时间",
            "dataId": "/data/time",
            "priority": "should",
        }
    ]
    assert "累计、只增不减" in payload["instruction"]
    assert "上一轮 Compact DSL 只作为失败诊断" in payload["instruction"]


def test_build_repair_appends_to_one_conversation_without_reencoding_history() -> None:
    messages = PromptBuilder().build_repair(
        [
            {
                "role": "system",
                "content": "CREATE_SENTINEL\nFEWSHOT_SENTINEL\nPLAN_SENTINEL",
            },
            {"role": "user", "content": '{"size":"2x4"}'},
        ],
        "current invalid source",
        [{"stage": "validation", "code": "E_CURRENT", "message": "current error"}],
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
        previous_failures=[[{"stage": "validation", "code": "E_OLD", "message": "old error"}]],
        repair_history=[
            {
                "repairAttempt": 1,
                "sourceDsl": "historical invalid source",
                "qualityErrors": [{"code": "E_OLD"}],
                "selectedRepairStrategy": {"scope": "component"},
            }
        ],
        repair_strategy={
            "category": "component_contract",
            "scope": "component",
            "repairStrategy": "component_contract_repair",
            "instruction": "修复当前组件合同。",
        },
    )

    assert messages[0]["content"] == "CREATE_SENTINEL\nFEWSHOT_SENTINEL\nPLAN_SENTINEL"
    assert messages[-3] == {
        "role": "assistant",
        "content": "current invalid source",
    }
    assert messages[-2]["content"].startswith("<repair_contract>")
    payload = _repair_feedback(messages)
    assert "invalidSourceDsl" not in payload
    assert "previousFailures" not in payload
    assert "repairHistory" not in payload
    assert "historical invalid source" not in messages[-1]["content"]

    second = PromptBuilder().build_repair(
        messages + [{"role": "assistant", "content": "second invalid source"}],
        "second invalid source",
        [{"stage": "validation", "code": "E_SECOND", "message": "second error"}],
        dsl_format=DESIGN_COMPACT_PROFILE_ID,
    )
    assert sum(message["content"].count("<repair_contract>") for message in second) == 1
