"""验证 Design Compact Repair 提示词保留通用、语义优先的修复流程。"""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from services.compact_repair_candidate import select_compact_repair_candidate
from services.compact_repair_simplification import simplification_variants
from services.compact_wide_recomposition import recompose_wide_card
from services.generation_pipeline import DslProcessingContext
from services.prompt_builder import REPAIR_SYSTEM_PROMPT, PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry


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
    assert "轻量组件替换、信息合并与冗余去重" in REPAIR_SYSTEM_PROMPT
    assert "这不是可选业务字段的省略授权" in REPAIR_SYSTEM_PROMPT


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


def test_repair_history_allows_restoring_mistakenly_deleted_required_facts() -> None:
    initial = [
        {"role": "system", "content": "original generation constraints"},
        {"role": "user", "content": '{"size":"2x4"}'},
    ]
    messages = PromptBuilder().build_repair(
        initial, "candidate", [], repair_history=[], dsl_format="design-compact-dsl"
    )
    payload = _repair_feedback(messages)
    instruction = payload.get("instruction")
    assert isinstance(instruction, str)
    assert "误删的必要事实和动作必须恢复" in instruction
    assert "仅程序批准省略的内容不得恢复" in instruction
    assert "不得恢复历史候选已经删除" not in instruction
    assert initial[0].get("content") == "original generation constraints"
    assert initial[1].get("content") == '{"size":"2x4"}'


def _candidate_context() -> DslProcessingContext:
    return DslProcessingContext(
        size="2x4",
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        task_spec={
            "size": "2x4",
            "appVersion": "11.9.9.342",
            "dataModelSchema": {"data": {"value": {"type": "integer", "sampleValue": 80}}},
            "eventCandidates": [
                {"id": "blue", "call": "clickToDeeplink", "args": {"uri": "blue"}},
                {"id": "battery", "call": "clickToDeeplink", "args": {"uri": "battery"}},
            ],
        },
        protocol_profile={},
        compact_plan={
            "info_required": [
                {"priority": "must", "requirement": "电量", "dataId": "/data/value"},
                {"priority": "must", "requirement": "蓝牙", "actionId": "blue"},
                {"priority": "must", "requirement": "电池", "actionId": "battery"},
            ]
        },
    )


def _candidate_source(*, removed: str | None = None) -> str:
    children = ["value", "blue", "battery"]
    if removed is not None:
        children.remove(removed)
    rows = [
        [
            "root",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
                "borderRadius": 20,
                "clip": True,
                "itemMargin": 8,
            },
            children,
        ]
    ]
    if removed != "value":
        rows.append(
            [
                "value",
                "EmphasizedData",
                {
                    "value": {"path": "/data/value"},
                    "unit": "%",
                    "fontSize": 30,
                },
            ]
        )
    for name in ("blue", "battery"):
        if name != removed:
            rows.append(
                [
                    name,
                    "PillButton",
                    {
                        "label": "设置",
                        "onClick": [
                            {"call": "clickToDeeplink", "args": {"uri": name}},
                        ],
                    },
                ]
            )
    rows.append(["/data/value", 80])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("removed", ["value", "blue", "battery"])
def test_repair_candidate_does_not_trade_existing_required_content_for_space(removed) -> None:
    previous = _candidate_source()
    candidate = _candidate_source(removed=removed)
    selection = select_compact_repair_candidate(previous, candidate, _candidate_context())
    assert selection.source_dsl == previous
    assert selection.candidate_dsl == candidate
    assert any(
        issue.get("code") == "COMPACT_PLAN_COVERAGE_FAILED" for issue in selection.rejection_issues
    )


def test_repair_candidate_can_restore_a_missing_action_without_new_losses() -> None:
    candidate = _candidate_source()
    selection = select_compact_repair_candidate(
        _candidate_source(removed="blue"), candidate, _candidate_context()
    )
    assert selection.source_dsl == candidate
    assert not selection.rejection_issues


def test_repair_candidate_keeps_parsable_source_after_broken_model_output() -> None:
    previous = _candidate_source()
    selection = select_compact_repair_candidate(previous, "broken response", _candidate_context())
    assert selection.source_dsl == previous
    assert selection.rejection_issues


def test_repair_candidate_allows_required_label_even_if_it_exposes_height_overflow() -> None:
    previous = _candidate_source()
    rows = [json.loads(line) for line in previous.splitlines()]
    rows[0][3].insert(0, "label")
    rows.insert(
        1,
        [
            "label",
            "SecondaryBody",
            {
                "role": "body",
                "items": [{"value": "电量"}],
                "fontSize": 14,
            },
        ],
    )
    candidate = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    selection = select_compact_repair_candidate(previous, candidate, _candidate_context())
    assert selection.source_dsl == candidate
    assert not selection.rejection_issues


def test_repair_candidate_keeps_existing_required_title_placement() -> None:
    context = _candidate_context()
    plan = context.compact_plan
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[0]["componentHints"] = ["SingleLineTitle"]
    rows = [json.loads(line) for line in _candidate_source().splitlines()]
    rows[1] = [
        "value",
        "SingleLineTitle",
        {
            "title": {"path": "/data/value"},
            "fontSize": 12,
        },
    ]
    previous = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    selection = select_compact_repair_candidate(previous, _candidate_source(), context)
    assert selection.source_dsl == previous
    assert any("title fact" in issue.get("message", "") for issue in selection.rejection_issues)


def test_repair_candidate_respects_existing_omission_authorization_but_keeps_actions() -> None:
    context = replace(_candidate_context(), allowed_omitted_plan_fact_indexes=(0, 1))
    previous = _candidate_source()
    omitted_fact = select_compact_repair_candidate(
        previous, _candidate_source(removed="value"), context
    )
    assert not omitted_fact.rejection_issues
    omitted_action = select_compact_repair_candidate(
        previous, _candidate_source(removed="blue"), context
    )
    assert omitted_action.source_dsl == previous
    assert omitted_action.rejection_issues


def test_small_card_candidate_bypasses_new_wide_repair_processing() -> None:
    selection = select_compact_repair_candidate(
        "previous", "candidate", replace(_candidate_context(), size="2x2")
    )
    assert selection.source_dsl == "candidate"
    assert selection.corrections == ()
    assert selection.rejection_issues == ()


@pytest.mark.parametrize("font, expected", [(12, 14), (14, 14)])
def test_fixed_font_repair_preserves_items_roles_bindings_and_actions(font, expected) -> None:
    rows = [json.loads(line) for line in _candidate_source().splitlines()]
    root = rows[0]
    root[3].insert(1, "details")
    rows.insert(
        2,
        [
            "details",
            "SecondaryBody",
            {
                "role": "supporting",
                "fontSize": font,
                "items": [{"label": "电量", "value": {"path": "/data/value"}}],
            },
        ],
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    selection = select_compact_repair_candidate(source, source, _candidate_context())
    result = [json.loads(line) for line in selection.source_dsl.splitlines()]
    details = next(row for row in result if row[0] == "details")
    assert details[2].get("fontSize") == expected
    assert details[2].get("role") == "supporting"
    assert details[2].get("items") == rows[2][2].get("items")
    assert not selection.rejection_issues
    assert bool(selection.corrections) is (font != expected)


def test_repair_output_extracts_only_a_unique_valid_complete_dsl() -> None:
    valid = (Path(__file__).parents[1] / "cloud/custom/mock.design-compact-dsl-2x4.dat").read_text(
        encoding="utf-8"
    )
    context = replace(_candidate_context(), compact_plan=None)
    broken = "```genui\nbroken\n```\n说明\n```genui\n" + valid + "\n```"
    selection = select_compact_repair_candidate(valid, broken, context)
    assert "extract_unique_valid_dsl" in selection.corrections
    assert selection.source_dsl.strip() == valid.strip()
    assert not selection.rejection_issues


def test_repair_output_does_not_pick_between_two_different_valid_candidates() -> None:
    valid = (Path(__file__).parents[1] / "cloud/custom/mock.design-compact-dsl-2x4.dat").read_text(
        encoding="utf-8"
    )
    other = valid.replace("Design Compact Mock", "另一个合法版本")
    broken = "```genui\n" + valid + "\n```\n```genui\n" + other + "\n```"
    selection = select_compact_repair_candidate(
        valid, broken, replace(_candidate_context(), compact_plan=None)
    )
    assert selection.source_dsl == valid
    assert selection.rejection_issues
    assert "extract_unique_valid_dsl" not in selection.corrections


def _wide_reflow_example():
    rows = [
        [
            "root",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
                "itemMargin": 6,
                "borderRadius": 20,
                "clip": True,
            },
            ["title", "body", "action"],
        ],
        ["title", "SingleLineTitle", {"title": "训练", "fontSize": 12}],
        [
            "body",
            "Column",
            {"width": "matchParent", "layoutWeight": 1, "itemMargin": 6},
            ["primary", "details"],
        ],
        ["primary", "Column", {"width": "matchParent", "flexShrink": 0}, ["days"]],
        [
            "days",
            "EmphasisText",
            {
                "mainText": "{{ ${/data/days} + '天' }}",
                "secondaryText": "距开赛",
                "fontSize": 18,
                "width": "matchParent",
            },
        ],
        ["details", "Column", {"width": "matchParent", "layoutWeight": 1}, ["metrics"]],
        [
            "metrics",
            "SecondaryBody",
            {
                "role": "supporting",
                "columns": 1,
                "fontSize": 12,
                "width": "matchParent",
                "items": [
                    {"label": "步数", "value": {"path": "/data/steps"}},
                    {"label": "时长", "value": {"path": "/data/duration"}},
                    {"label": "心率", "value": {"path": "/data/heart"}},
                ],
            },
        ],
        [
            "action",
            "PillButton",
            {
                "label": "锻炼",
                "onClick": [
                    {"call": "clickToDeeplink", "args": {"uri": "sport"}},
                ],
            },
        ],
        ["/data/days", 30],
        ["/data/steps", "6200步"],
        ["/data/duration", "40分"],
        ["/data/heart", "135次/分钟"],
    ]
    fields = {"days": {"type": "integer", "sampleValue": 30}}
    for key, value in (("steps", "6200步"), ("duration", "40分"), ("heart", "135次/分钟")):
        fields[key] = {"type": "string", "sampleValue": value}
    task = {
        "size": "2x4",
        "dataModelSchema": {"data": fields},
        "eventCandidates": [
            {"id": "sport", "call": "clickToDeeplink", "args": {"uri": "sport"}},
        ],
    }
    facts = []
    for key in fields:
        facts.append({"priority": "must", "requirement": key, "dataId": "/data/" + key})
    facts.append({"priority": "must", "requirement": "锻炼", "actionId": "sport"})
    context = DslProcessingContext(
        size="2x4",
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        task_spec=task,
        protocol_profile={},
        layout_scope="W-plan-guided",
        compact_plan={"info_required": facts},
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    return source, context


def _recompose(source, context):
    return recompose_wide_card(
        source,
        task_spec=context.task_spec,
        card_spec=context.card_spec,
        protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile("design-compact-dsl"),
        layout_scope=context.layout_scope,
        compact_plan=context.compact_plan,
    )


def test_wide_recomposition_preserves_facts_actions_fonts_and_data() -> None:
    source, context = _wide_reflow_example()
    result = _recompose(source, context)
    assert result.applied
    assert 0 < result.candidate_count <= 64
    before = [json.loads(line) for line in source.splitlines()]
    after = [json.loads(line) for line in result.source_dsl.splitlines()]
    assert [row for row in before if len(row) == 2] == [row for row in after if len(row) == 2]
    for identifier in ("days", "metrics", "action", "title"):
        original = next(row for row in before if row[0] == identifier)
        candidate = next(row for row in after if row[0] == identifier)
        props = dict(candidate[2])
        props.pop("layoutWeight", None)
        assert props == original[2]
    selection = select_compact_repair_candidate(source, source, context)
    assert selection.source_dsl == result.source_dsl
    assert "wide_layout_recomposition" in selection.corrections
    assert selection.layout_candidate_count == result.candidate_count
    repeated = _recompose(result.source_dsl, context)
    assert not repeated.applied and repeated.candidate_count == 0
    assert repeated.source_dsl == result.source_dsl


def test_wide_recomposition_does_not_guess_missing_required_facts() -> None:
    source, context = _wide_reflow_example()
    plan = context.compact_plan
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"priority": "must", "requirement": "地点", "dataId": "/data/location"})
    result = _recompose(source, context)
    assert result.source_dsl == source
    assert not result.applied and result.candidate_count == 0


def test_wide_recomposition_retains_source_when_bounded_search_fails(monkeypatch) -> None:
    from services import compact_wide_recomposition

    source, context = _wide_reflow_example()
    monkeypatch.setattr(compact_wide_recomposition, "_LIMIT", 3)
    monkeypatch.setattr(
        compact_wide_recomposition, "_errors", lambda *_args: ("text width overflow",)
    )
    result = _recompose(source, context)
    assert result.source_dsl == source
    assert not result.applied
    assert result.candidate_count == 3
    assert result.reasons == ("search_limit",)


def test_wide_recomposition_bypasses_small_cards_and_template_markers() -> None:
    source, context = _wide_reflow_example()
    small = replace(context, size="2x2", card_spec={"suggestSize": "2x2"})
    assert _recompose(source, small).source_dsl == source
    rows = [json.loads(line) for line in source.splitlines()]
    rows[0][2]["template_root"] = True
    template = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = _recompose(template, context)
    assert result.source_dsl == template and not result.applied


def _wide_text_block_example():
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    root = rows[0]
    root[1] = "Row"
    root[2]["itemMargin"] = 12
    root[3] = ["primary", "details"]
    panels = {"primary": ["title", "days", "action"], "details": ["right_title", "metrics"]}
    for row in rows:
        if row[0] in panels:
            row[2] = {
                "width": "matchParent",
                "height": "matchParent",
                "layoutWeight": 1,
                "padding": 8,
                "itemMargin": 6,
                "alignItems": "start",
                "justifyContent": "center",
                "borderRadius": 16,
                "backgroundColor": "#99FFFFFF",
                "clip": True,
            }
            row[3] = panels.get(row[0])
        if row[0] == "days":
            row[1] = "EmphasizedData"
            row[2] = {"value": {"path": "/data/days"}, "unit": "天", "fontSize": 30}
        if row[0] == "metrics":
            items = row[2].get("items")
            assert isinstance(items, list)
            row[1] = "TextBlock"
            row[2] = {
                "items": items,
                "width": "matchParent",
                "fontColor": "#FF563D99",
            }
    rows = [row for row in rows if row[0] != "body"]
    rows.insert(1, ["right_title", "SingleLineTitle", {"title": "训练数据", "fontSize": 12}])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), context


def test_wide_text_block_replacement_retains_source_without_core_information() -> None:
    from services.card_validation import CompactDslValidationError, validate_compact_dsl
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    from services.compact_wide_recomposition import _serialize

    source, context = _wide_text_block_example()
    original = [json.loads(line) for line in source.splitlines()]
    result = _recompose(source, context)
    assert not result.applied and result.source_dsl == source
    reason, candidate_rows = next(
        variant for variant in _simplifications(source, context) if "vertical_details" in variant[0]
    )
    assert "vertical_details" in reason
    candidate_source = _serialize(candidate_rows)
    with pytest.raises(CompactDslValidationError, match="SecondaryBody is auxiliary"):
        validate_compact_dsl(
            candidate_source,
            task_spec=context.task_spec,
            card_spec=context.card_spec,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile("design-compact-dsl"),
            layout_scope=context.layout_scope,
            enforce_model_component_types=True,
        )
    after = [json.loads(line) for line in candidate_source.splitlines()]
    for row in original:
        candidate = next(value for value in after if value[0] == row[0])
        if row[0] == "metrics":
            assert candidate[1] == "SecondaryBody"
            props = dict(candidate[2])
            assert "role" not in props
            assert props.pop("columns") == 1
            assert props == row[2]
        else:
            assert candidate == row
    repeated = _recompose(result.source_dsl, context)
    assert not repeated.applied and repeated.source_dsl == result.source_dsl
    genui = convert_compact_dsl_to_a2ui(candidate_source, size="2x4")
    for line in genui.splitlines():
        components = json.loads(line).get("updateComponents", {}).get("components", [])
        for component in components:
            if component.get("component") != "Text":
                continue
            if not component.get("id", "").startswith("metrics_"):
                continue
            font = component.get("styles", {}).get("fontSize")
            assert isinstance(font, int) and font >= 12


def test_wide_recomposition_does_not_replace_explicit_text_block_font() -> None:
    source, context = _wide_text_block_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    metrics[2]["fontSize"] = 10
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = _recompose(source, context)
    assert not result.applied and result.source_dsl == source


def test_wide_partition_preserves_component_order_content_and_action() -> None:
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    rows[0][3] = ["title", "body"]
    body = next(row for row in rows if row[0] == "body")
    body[3] = ["days", "metrics", "action"]
    rows = [row for row in rows if row[0] not in ("primary", "details")]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = _recompose(source, context)
    assert result.applied and "ordered_column_partition" in result.reasons
    after = [json.loads(line) for line in result.source_dsl.splitlines()]
    new_body = next(row for row in after if row[0] == "body")
    assert new_body[1] == "Row"
    ordered_children = []
    for identifier in new_body[3]:
        group = next(row for row in after if row[0] == identifier)
        assert group[1] == "Column"
        ordered_children.extend(group[3])
    assert ordered_children == body[3]
    for row in rows:
        if row[0] != "body":
            assert next(candidate for candidate in after if candidate[0] == row[0]) == row


def _simplifications(source, context):
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows

    rows = list(parse_compact_dsl_rows(source))
    snapshot = copy.deepcopy(rows)
    result = list(simplification_variants(rows, context.task_spec))
    assert rows == snapshot
    return result


def _wide_card_action_example():
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    action = next(row for row in rows if row[0] == "action")
    action[1] = "CardButton"
    action[2].update({"width": "matchParent", "labelLines": 2})
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), context


def test_wide_lightweight_action_keeps_full_label_and_every_handler() -> None:
    from services.compact_dsl_a2ui_converter import DataRow

    source, context = _wide_card_action_example()
    original = [json.loads(line) for line in source.splitlines()]
    action = next(row for row in original if row[0] == "action")
    variants = _simplifications(source, context)
    reason, candidate = next(variant for variant in variants if "lightweight_actions" in variant[0])
    assert reason == "lightweight_actions"
    pill = next(row for row in candidate if getattr(row, "component_id", None) == "action")
    assert pill.component_type == "PillButton"
    assert pill.props.get("label") == action[2].get("label")
    assert pill.props.get("onClick") == action[2].get("onClick")
    assert "width" not in pill.props and "labelLines" not in pill.props
    data = []
    for row in candidate:
        if isinstance(row, DataRow):
            data.append([row.path, row.value])
    assert data == [row for row in original if len(row) == 2]


@pytest.mark.parametrize(
    "protected",
    [
        {"icon": "resources/base/media/icon.svg"},
        {"fontColor": "#FF112233"},
        {"height": 57},
        {"width": 120},
    ],
)
def test_lightweight_action_preserves_nontransferable_design(protected) -> None:
    source, context = _wide_card_action_example()
    rows = [json.loads(line) for line in source.splitlines()]
    action = next(row for row in rows if row[0] == "action")
    action[2].update(protected)
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    for _reason, candidate in _simplifications(source, context):
        result = next(row for row in candidate if getattr(row, "component_id", None) == "action")
        assert result.component_type == "CardButton"
        assert result.props == action[2]


def test_lightweight_action_respects_user_requested_large_button() -> None:
    source, context = _wide_card_action_example()
    task = dict(context.task_spec)
    task["userQuery"] = "请使用大按钮"
    context = replace(context, task_spec=task)
    for _reason, candidate in _simplifications(source, context):
        action = next(row for row in candidate if getattr(row, "component_id", None) == "action")
        assert action.component_type == "CardButton"


def _wide_separate_supporting_example():
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    items = metrics[2].get("items")
    assert isinstance(items, list)
    details = next(row for row in rows if row[0] == "details")
    identifiers = ["steps", "duration", "heart"]
    details[2]["itemMargin"] = 6
    details[3] = identifiers
    rows.remove(metrics)
    for identifier, item in zip(identifiers, items, strict=True):
        rows.append(
            [
                identifier,
                "SecondaryBody",
                {
                    "role": "supporting",
                    "items": [item],
                    "fontSize": 14,
                    "columns": 2,
                    "width": "matchParent",
                },
            ]
        )
    task = copy.deepcopy(context.task_spec)
    schema = task.get("dataModelSchema", {}).get("data")
    assert isinstance(schema, dict)
    sport = {}
    for identifier in identifiers:
        field = schema.pop(identifier)
        sport[identifier] = field
    schema["sport"] = sport
    plan = copy.deepcopy(context.compact_plan)
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    for fact in facts:
        path = fact.get("dataId")
        if isinstance(path, str) and path != "/data/days":
            fact["dataId"] = path.replace("/data/", "/data/sport/", 1)
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    for identifier in identifiers:
        source = source.replace("/data/" + identifier, "/data/sport/" + identifier)
    return source, replace(context, task_spec=task, compact_plan=plan)


def test_wide_supporting_merge_keeps_content_but_does_not_accept_orphan_body() -> None:
    from services.compact_wide_recomposition import _serialize

    source, context = _wide_separate_supporting_example()
    result = _recompose(source, context)
    assert not result.applied and result.source_dsl == source
    reason, candidate_rows = next(
        variant for variant in _simplifications(source, context) if "merge_supporting" in variant[0]
    )
    assert "merge_supporting" in reason
    before = [json.loads(line) for line in source.splitlines()]
    after = [json.loads(line) for line in _serialize(candidate_rows).splitlines()]
    merged = next(row for row in after if row[0] == "steps")
    assert merged[2].get("role") == "supporting"
    assert merged[2].get("fontSize") == 14
    expected = []
    for identifier in ("steps", "duration"):
        row = next(row for row in before if row[0] == identifier)
        expected.extend(row[2].get("items", []))
    assert merged[2].get("items") == expected
    assert not any(row[0] == "duration" for row in after)
    assert [row for row in before if len(row) == 2] == [row for row in after if len(row) == 2]


def test_supporting_merge_does_not_mix_objects_or_lower_fixed_font() -> None:
    source, context = _wide_separate_supporting_example()
    rows = [json.loads(line) for line in source.splitlines()]
    for identifier in ("duration", "heart"):
        row = next(row for row in rows if row[0] == identifier)
        row[2]["items"][0]["value"] = {"path": "/data/other_" + identifier + "/value"}
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    variants = _simplifications(source, context)
    assert all("merge_supporting" not in reason for reason, _rows in variants)
    source, context = _wide_separate_supporting_example()
    rows = [json.loads(line) for line in source.splitlines()]
    steps = next(row for row in rows if row[0] == "steps")
    heart = next(row for row in rows if row[0] == "heart")
    steps[2]["items"].extend(heart[2].get("items", []))
    rows.remove(heart)
    details = next(row for row in rows if row[0] == "details")
    details[3].remove("heart")
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    assert all(
        "merge_supporting" not in reason for reason, _rows in _simplifications(source, context)
    )


@pytest.mark.parametrize("columns", [1, 2])
def test_supporting_merge_uses_actual_wrapping_recipe_without_adding_role(columns) -> None:
    source, context = _wide_separate_supporting_example()
    rows = [json.loads(line) for line in source.splitlines()]
    for identifier in ("steps", "duration"):
        row = next(row for row in rows if row[0] == identifier)
        row[2].pop("role", None)
        row[2]["columns"] = columns
        row[2]["fontSize"] = 12
        items = row[2].get("items")
        assert isinstance(items, list)
        for item in items:
            item["maxLines"] = 2
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    _reason, candidate = next(
        variant for variant in _simplifications(source, context) if "merge_supporting" in variant[0]
    )
    merged = next(row for row in candidate if getattr(row, "component_id", None) == "steps")
    assert merged.props.get("fontSize") == 12
    assert "role" not in merged.props
    assert len(merged.props.get("items", [])) == 2


def test_supporting_deduplication_keeps_multiline_font_without_adding_role() -> None:
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    props = metrics[2]
    props.pop("role", None)
    items = props.get("items")
    assert isinstance(items, list)
    item = copy.deepcopy(items[0])
    item["maxLines"] = 2
    props["items"] = [item, copy.deepcopy(item)]
    props["columns"] = 2
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    _reason, candidate = next(
        variant for variant in _simplifications(source, context)
        if "deduplicate_supporting" in variant[0]
    )
    deduplicated = next(row for row in candidate if getattr(row, "component_id", None) == "metrics")
    assert deduplicated.props.get("fontSize") == 12
    assert "role" not in deduplicated.props
    assert deduplicated.props.get("items") == [item]


@pytest.mark.parametrize("repeated", [False, True])
def test_supporting_deduplication_preserves_explicit_repeated_display(repeated) -> None:
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    items = metrics[2].get("items")
    assert isinstance(items, list)
    items.append(copy.deepcopy(items[-1]))
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    task = dict(context.task_spec)
    task["userQuery"] = "重复显示心率两次" if repeated else "显示训练信息"
    context = replace(context, task_spec=task)
    variants = _simplifications(source, context)
    first_reason, first_rows = variants[0]
    candidate = next(row for row in first_rows if getattr(row, "component_id", None) == "metrics")
    assert candidate.props.get("fontSize") == 12
    assert candidate.props.get("items") == (items if repeated else items[:-1])
    assert ("deduplicate_supporting" in first_reason) is (not repeated)
    if not repeated:
        result = _recompose(source, context)
        assert result.applied
        assert result.reasons[0] == "deterministic_layout"
        after = [json.loads(line) for line in result.source_dsl.splitlines()]
        kept = next(row for row in after if row[0] == "metrics")
        assert kept[2].get("items") == items


def test_successful_pure_layout_never_invokes_simplification(monkeypatch) -> None:
    from services import compact_wide_recomposition

    def unexpected_simplification(*_args):
        pytest.fail("纯布局已通过，不得进行组件替换、信息合并或去重")

    monkeypatch.setattr(
        compact_wide_recomposition, "simplification_variants", unexpected_simplification
    )
    source, context = _wide_reflow_example()
    result = _recompose(source, context)
    assert result.applied and result.reasons[0] == "deterministic_layout"


def test_deduplication_runs_only_after_pure_layout_cannot_resolve_height(monkeypatch) -> None:
    from services import compact_wide_recomposition

    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    items = metrics[2].get("items")
    assert isinstance(items, list)
    items.append(copy.deepcopy(items[-1]))
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    monkeypatch.setattr(
        compact_wide_recomposition,
        "_text_variants",
        lambda candidate: iter((("existing_components", candidate),)),
    )
    result = _recompose(source, context)
    assert result.applied and result.reasons[0] == "component_simplification"
    assert any("deduplicate_supporting" in reason for reason in result.reasons)


@pytest.mark.parametrize("distinct", ["static", "label", "array_item"])
def test_simplification_keeps_distinct_context_and_static_occurrences(distinct) -> None:
    source, context = _wide_reflow_example()
    rows = [json.loads(line) for line in source.splitlines()]
    metrics = next(row for row in rows if row[0] == "metrics")
    items = metrics[2].get("items")
    assert isinstance(items, list)
    first = {"label": "会议", "value": {"path": "/data/calendar/events/0/time"}}
    second = copy.deepcopy(first)
    if distinct == "static":
        first["value"] = "09:00"
        second["value"] = "09:00"
    elif distinct == "label":
        second["label"] = "另一指标"
    else:
        second["value"] = {"path": "/data/calendar/events/1/time"}
    metrics[2]["items"] = [first, second]
    metrics[2]["fontSize"] = 14
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    variants = _simplifications(source, context)
    assert all("deduplicate_supporting" not in reason for reason, _rows in variants)


def test_repair_simplification_instructions_are_not_in_initial_prompt() -> None:
    create = A2UIProtocolRegistry.read_design_prompt(DESIGN_COMPACT_PROFILE_ID, size="2x4")
    assert "轻量组件替换、信息合并与冗余去重" not in create
    assert "仅当本轮是 2x4 且存在高度/布局容量错误时" in REPAIR_SYSTEM_PROMPT
    model_repair_rules = (
        "上述确定性处理由程序执行",
        "仅有属性或绑定错误时不启用这些容量简化",
        "两项 TextBlock 可改用合法 TableText",
        "三项辅助明细可合组为 SecondaryBody",
        "不能用标题、按钮或另一个 SecondaryBody 冒充核心",
        "替换后的标签和值字号均不得降低",
        "不得把多个指标\n拼入只接受单个数值的进度读数",
        "样例值相同不代表冗余",
        "核对原字段或表达式、对象、日期、限定条件和展示用途",
        "数据行与事件定义保持不变",
    )
    for rule in model_repair_rules:
        assert rule in REPAIR_SYSTEM_PROMPT
        assert rule not in create
