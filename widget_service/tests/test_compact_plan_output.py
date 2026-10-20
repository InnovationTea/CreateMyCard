"""Plan 封装兼容、严格拒绝边界与格式纠错反馈。"""

import json

import pytest

from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.compact_plan_output import normalize_plan_output
from services.prompt_builder import PromptBuilder

_DSML = "｜｜DSML｜｜"
_PREFIX = (
    f'<{_DSML} calls>\n<{_DSML} invoke name="submit_card_plan">\n'
    f'<{_DSML} parameter name="arguments" string="false">'
)
_SUFFIX = f"</{_DSML} parameter>\n</{_DSML} invoke>\n</{_DSML} calls>"


def _spec() -> dict:
    return {
        "size": "2x2",
        "userQuery": "显示静态卡片",
        "dataModelSchema": {},
        "eventCandidates": [],
    }


def _arguments() -> dict:
    return {
        "info_required": [
            {"requirement": "用户原文", "text": "静态卡片", "priority": "must"}
        ],
        "layoutHints": ["S-center"],
    }


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        _SUFFIX,
        f'</{_DSML} parameter>\n<{_DSML} parameter name="name" string="true">'
        f'submit_card_plan</{_DSML} parameter>\n</{_DSML} invoke>\n</{_DSML} calls>',
        f"<{_DSML} end_invoke>\n<{_DSML} end_calls>",
        f"</{_DSML} parameter>\n</{_DSML} invoke>\n</{_DSML}>",
    ],
)
def test_known_dsml_envelopes_preserve_complete_plan(suffix: str) -> None:
    arguments = _arguments()
    raw = _PREFIX + json.dumps(arguments, ensure_ascii=False) + suffix
    result = parse_compact_plan_call(raw, _spec())
    expected = parse_compact_plan_call(
        json.dumps({"name": "submit_card_plan", "arguments": arguments}), _spec()
    )
    assert result.plan == expected.plan
    assert "Plan DSML transport wrapper normalized; arguments unchanged." in result.warnings


def test_dsml_direct_arguments_and_call_prefix() -> None:
    arguments = json.dumps(_arguments())
    direct = f'<{_DSML} calls>\n<{_DSML} invoke name="submit_card_plan">\n' + arguments
    wrapped = '{"name":"submit_card_plan","arguments":' + arguments + "}"
    expected = parse_compact_plan_call(wrapped, _spec()).plan
    assert parse_compact_plan_call(direct, _spec()).plan == expected
    assert parse_compact_plan_call("call\r\n" + wrapped, _spec()).plan == expected
    assert normalize_plan_output(wrapped).text == wrapped
    assert normalize_plan_output(wrapped).warnings == ()


@pytest.mark.parametrize(
    "change",
    [
        "unknown_tool", "unknown_parameter", "second_call", "trailing_prose",
        "leading_prose", "truncated_json", "truncated_marker", "wrong_name_parameter",
        "whitespace_in_name",
    ],
)
def test_unrecognized_or_incomplete_dsml_is_rejected(change: str) -> None:
    body = json.dumps(_arguments())
    raw = _PREFIX + body + _SUFFIX
    if change == "unknown_tool":
        raw = raw.replace("submit_card_plan", "other_tool")
    elif change == "unknown_parameter":
        raw = raw.replace('name="arguments"', 'name="other"')
    elif change == "second_call":
        raw += raw
    elif change == "trailing_prose":
        raw += "完成"
    elif change == "leading_prose":
        raw = "这是计划：" + raw
    elif change == "truncated_json":
        raw = _PREFIX + body.removesuffix("}")
    elif change == "truncated_marker":
        raw = _PREFIX + body + "</｜｜DSML"
    else:
        name = "submit_card_ plan" if change == "whitespace_in_name" else "other_tool"
        raw = _PREFIX + body + (
            f'</{_DSML} parameter><{_DSML} parameter name="name" string="true">'
            f'{name}</{_DSML} parameter></{_DSML} invoke></{_DSML} calls>'
        )
    with pytest.raises(CompactPlanValidationError, match="valid JSON"):
        parse_compact_plan_call(raw, _spec())


@pytest.mark.parametrize(
    "fact",
    [
        {"dataId": "/data/fake", "requirement": "不存在数据", "priority": "must"},
        {"actionId": "fake.action", "requirement": "不存在动作", "priority": "must"},
        {"text": "编造原文", "requirement": "错误原文", "priority": "must"},
        {"text": "静态卡片", "requirement": "错误优先级", "priority": "invalid"},
    ],
)
def test_wrapped_plan_keeps_original_contract_errors(fact: dict) -> None:
    arguments = {"info_required": [fact]}
    plain = json.dumps({"name": "submit_card_plan", "arguments": arguments})
    with pytest.raises(CompactPlanValidationError) as original:
        parse_compact_plan_call(plain, _spec())
    with pytest.raises(CompactPlanValidationError) as wrapped:
        parse_compact_plan_call(_PREFIX + json.dumps(arguments) + _SUFFIX, _spec())
    assert wrapped.value.errors == original.value.errors


def test_wrapped_plan_still_requires_composition() -> None:
    raw = _PREFIX + json.dumps(_arguments()) + _SUFFIX
    with pytest.raises(CompactPlanValidationError, match="composition"):
        parse_compact_plan_call(raw, _spec(), require_composition=True)


def test_retry_feedback_has_format_location_and_original_business_errors() -> None:
    invalid = _PREFIX + '{"info_required":'
    messages = [{"role": "system", "content": "合同"}, {"role": "user", "content": "需求"}]
    messages.append({"role": "user", "content": "plan"})
    errors = ("Plan output must be valid JSON.", "原始业务错误")
    repaired = PromptBuilder.build_compact_plan_repair(messages, invalid, errors)
    latest = repaired[-1].get("content")
    assert isinstance(latest, str)
    feedback = json.loads(latest)
    result = feedback.get("toolResult")
    assert isinstance(result, dict)
    assert result.get("errors") == list(errors)
    output_format = feedback.get("outputFormat")
    assert isinstance(output_format, dict)
    assert output_format.get("detectedEnvelope") == "DSML"
    assert output_format.get("jsonLine") == 1
    assert output_format.get("jsonScope") == "DSML_arguments"
    column = output_format.get("jsonColumn")
    assert isinstance(column, int)
    assert column > 1
    instruction = feedback.get("instruction")
    assert isinstance(instruction, str)
    assert "不是原生工具调用" in instruction
    assert "不得删除用户要求" in instruction
    assert len(messages) == 3


@pytest.mark.parametrize("suffix", ["另一个解释", "{}", "\ncall\n{}"])
def test_call_prefix_does_not_hide_trailing_content(suffix: str) -> None:
    raw = "call\n" + json.dumps({"name": "submit_card_plan", "arguments": _arguments()})
    with pytest.raises(CompactPlanValidationError):
        parse_compact_plan_call(raw + suffix, _spec())


@pytest.mark.parametrize("extra", [{"unexpected": True}, {"layoutHints": ["S-title-anchor"]}])
def test_wrapped_plan_keeps_argument_and_layout_checks(extra: dict) -> None:
    arguments = _arguments()
    arguments.update(extra)
    with pytest.raises(CompactPlanValidationError) as original:
        parse_compact_plan_call(
            json.dumps({"name": "submit_card_plan", "arguments": arguments}), _spec()
        )
    with pytest.raises(CompactPlanValidationError) as wrapped:
        parse_compact_plan_call(_PREFIX + json.dumps(arguments), _spec())
    assert wrapped.value.errors == original.value.errors
