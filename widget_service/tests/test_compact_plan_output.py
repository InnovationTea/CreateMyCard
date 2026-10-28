"""Plan 封装兼容、严格拒绝边界与格式纠错反馈。"""

import json

import pytest

from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.compact_plan_output import (
    PlanDuplicateKeyError,
    decode_plan_json,
    normalize_plan_output,
    normalize_plan_root_arguments,
    plan_output_format_feedback,
)
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


@pytest.mark.parametrize("wrapper", ["opening", "closing", "opening_json", "opening_upper"])
def test_single_sided_fence_preserves_complete_plan(wrapper: str) -> None:
    plain = json.dumps({"name": "submit_card_plan", "arguments": _arguments()}, ensure_ascii=False)
    raw = plain + "\n```"
    if wrapper == "opening":
        raw = "```\n" + plain
    elif wrapper == "opening_json":
        raw = "```json\r\n" + plain
    elif wrapper == "opening_upper":
        raw = "```JSON\n" + plain
    normalized = normalize_plan_output(raw)
    assert normalized.text == plain
    assert normalized.warnings == (
        "Plan single-sided Markdown fence removed; complete JSON unchanged.",
    )
    expected = parse_compact_plan_call(plain, _spec()).plan
    assert parse_compact_plan_call(raw, _spec()).plan == expected


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"name":"submit_card_plan","arguments":',
        '```json\n{"name":"submit_card_plan"}\n完成',
        '{"name":"submit_card_plan"}\n完成\n```',
        '```json\n{"name":"submit_card_plan"}{}',
        '{"name":"submit_card_plan"}{}\n```',
        '说明\n{"name":"submit_card_plan"}\n```',
        '```python\n{"name":"submit_card_plan"}',
        '```json\n{"name":"submit_card_plan",,"arguments":{}}',
        '```json\n{"name":"submit_card_plan"}\n```\n```',
    ],
)
def test_single_sided_fence_does_not_guess_incomplete_or_ambiguous_json(raw: str) -> None:
    result = normalize_plan_output(raw)
    assert result.text == raw
    assert result.warnings == ()
    with pytest.raises(CompactPlanValidationError):
        parse_compact_plan_call(raw, _spec())


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_json_or_complete_fence_bytes_remain_unchanged(fenced: bool) -> None:
    raw = json.dumps({"name": "submit_card_plan", "arguments": _arguments()}, indent=2)
    if fenced:
        raw = "```json\n" + raw + "\n```"
    raw = " \n" + raw + "\n "
    assert normalize_plan_output(raw).text == raw
    assert normalize_plan_output(raw).warnings == ()


@pytest.mark.parametrize(
    "extra",
    [
        {"layoutHints": ["S-center"]},
        {"presentationStyle": "records", "paletteFamily": "auto"},
        {"contentGroups": [{"id": "one", "kind": "object", "factIndexes": [0]}]},
        {"selectionNotes": ["保留主体"], "omittedContents": []},
        {"assetAssignments": [], "composition": {"layout": "S-center"}},
    ],
)
def test_known_root_parameters_move_without_changing_values(extra: dict) -> None:
    arguments = {"info_required": _arguments().get("info_required")}
    payload = {"name": "submit_card_plan", "arguments": arguments, **extra}
    unchanged = json.dumps(payload, ensure_ascii=False)
    result = normalize_plan_output(unchanged)
    expected = {"name": "submit_card_plan", "arguments": {**arguments, **extra}}
    assert json.loads(result.text) == expected
    assert result.warnings
    assert json.dumps(payload, ensure_ascii=False) == unchanged
    assert normalize_plan_output(result.text).text == result.text
    assert normalize_plan_output(result.text).warnings == ()


def test_moved_parameters_still_receive_original_schema_and_capability_checks() -> None:
    valid = {"name": "submit_card_plan", "arguments": _arguments()}
    misplaced = {
        "name": "submit_card_plan",
        "arguments": {"info_required": _arguments().get("info_required")},
        "layoutHints": ["S-center"],
    }
    assert parse_compact_plan_call(json.dumps(misplaced), _spec()).plan == (
        parse_compact_plan_call(json.dumps(valid), _spec()).plan
    )
    misplaced["paletteFamily"] = "blue"
    with pytest.raises(CompactPlanValidationError, match="Unsupported Plan arguments"):
        parse_compact_plan_call(json.dumps(misplaced), _spec())


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "submit_card_plan", "arguments": {}, "unknown": "value"},
        {"name": "submit_card_plan", "arguments": {"unknown": 1}, "layoutHints": []},
        {"name": "submit_card_plan", "arguments": {"layoutHints": []}, "layoutHints": []},
        {"name": "submit_card_plan", "arguments": {"paletteFamily": None}, "paletteFamily": "auto"},
        {"name": "other_tool", "arguments": {}, "layoutHints": []},
        {"name": "submit_card_plan", "arguments": "{}", "layoutHints": []},
        {"name": "submit_card_plan", "layoutHints": []},
        {"arguments": {}, "layoutHints": []},
    ],
)
def test_root_parameters_with_unknown_keys_or_conflicts_are_not_moved(payload: dict) -> None:
    raw = json.dumps(payload)
    result = normalize_plan_output(raw)
    assert result.text == raw
    assert result.warnings == ()
    normalized_object = normalize_plan_root_arguments(payload)
    assert normalized_object.payload is payload
    assert normalized_object.warnings == ()
    with pytest.raises(CompactPlanValidationError):
        parse_compact_plan_call(raw, _spec())


@pytest.mark.parametrize(
    "raw",
    [
        '{"name":"other_tool","name":"submit_card_plan","arguments":{}}',
        '{"name":"submit_card_plan","arguments":{"layoutHints":[],"layoutHints":[]}}',
        '{"name":"submit_card_plan","arguments":{"info_required":[{"text":"a","text":"b"}]}}',
        '{"name":"submit_card_plan","arguments":{},"layoutHints":[],"layou\\u0074Hints":[]}',
    ],
)
def test_duplicate_json_keys_are_not_hidden_by_normalization(raw: str) -> None:
    for candidate in (raw, "```json\n" + raw, raw + "\n```"):
        normalized = normalize_plan_output(candidate)
        assert normalized.text == candidate
        assert normalized.warnings == ()
    with pytest.raises(PlanDuplicateKeyError):
        decode_plan_json(raw)
    feedback = plan_output_format_feedback(raw)
    assert feedback.get("duplicateJsonKey")
    assert "duplicate key" in str(feedback.get("jsonError"))


def test_format_feedback_locates_internal_json_error_without_repairing_it() -> None:
    raw = '{"name":"submit_card_plan","arguments":{"selectionNotes":["说明"]],"layoutHints":[]}}'
    normalized = normalize_plan_output(raw)
    assert normalized.text == raw
    assert normalized.warnings == ()
    feedback = plan_output_format_feedback(raw)
    assert feedback.get("jsonLine") == 1
    assert feedback.get("jsonOffset") == raw.index("]]") + 1
    context = feedback.get("jsonContext")
    assert isinstance(context, str)
    assert "]]" in context
    assert len(context) <= 80


def test_format_feedback_lists_root_parameter_paths_and_conflicts() -> None:
    raw = json.dumps({
        "name": "submit_card_plan",
        "arguments": {"layoutHints": ["S-center"]},
        "layoutHints": ["S-title-content"],
        "paletteFamily": "auto",
        "unknown": 1,
    })
    feedback = plan_output_format_feedback(raw)
    assert feedback.get("unexpectedRootKeys") == ["layoutHints", "paletteFamily", "unknown"]
    assert feedback.get("expectedPaths") == {
        "layoutHints": "/arguments/layoutHints", "paletteFamily": "/arguments/paletteFamily",
    }
    assert feedback.get("conflictingArgumentKeys") == ["layoutHints"]


def test_complete_fence_feedback_inspects_json_without_reporting_backticks_as_error() -> None:
    raw = '```json\n{"name":"submit_card_plan","arguments":{},"unknown":1}\n```'
    feedback = plan_output_format_feedback(raw)
    assert feedback.get("detectedEnvelope") == "markdown_fence"
    assert feedback.get("unexpectedRootKeys") == ["unknown"]
    assert "jsonError" not in feedback


@pytest.mark.parametrize("extra_closer", ["}", "}}"])
def test_terminal_closer_recovery_then_root_relocation_preserves_plan(extra_closer: str) -> None:
    arguments = _arguments()
    misplaced = {
        "name": "submit_card_plan",
        "arguments": {"info_required": arguments.get("info_required")},
        "layoutHints": arguments.get("layoutHints"),
    }
    raw = json.dumps(misplaced) + extra_closer
    # 封装层不猜修 JSON；原解析器恢复终端括号后再处理无冲突的字段层级。
    assert normalize_plan_output(raw).text == raw
    result = parse_compact_plan_call(raw, _spec())
    expected = parse_compact_plan_call(
        json.dumps({"name": "submit_card_plan", "arguments": arguments}), _spec()
    )
    assert result.plan == expected.plan
    assert len(result.warnings) == 2
    assert "terminal closing delimiters recovered" in result.warnings[0]
    assert "root parameters moved to arguments" in result.warnings[1]


@pytest.mark.parametrize("extra_closer", ["", "}"])
@pytest.mark.parametrize("root_value", [["S-center"], ["S-title-content"]])
def test_parser_rejects_root_argument_overlap_even_after_terminal_recovery(
    extra_closer: str, root_value: list[str],
) -> None:
    raw = json.dumps({
        "name": "submit_card_plan", "arguments": _arguments(), "layoutHints": root_value,
    }) + extra_closer
    with pytest.raises(CompactPlanValidationError, match="only name and arguments"):
        parse_compact_plan_call(raw, _spec())


@pytest.mark.parametrize("wrapper", ["plain", "complete_fence", "extra_closer"])
@pytest.mark.parametrize("duplicate_scope", ["name", "arguments", "fact"])
def test_parser_rejects_duplicate_keys_in_all_json_scopes(
    wrapper: str, duplicate_scope: str,
) -> None:
    raw = json.dumps({"name": "submit_card_plan", "arguments": _arguments()})
    if duplicate_scope == "name":
        raw = raw.replace('"name":', '"name":"other_tool","name":', 1)
    elif duplicate_scope == "arguments":
        raw = raw.replace('"layoutHints":', '"layoutHints":[],"layoutHints":', 1)
    else:
        raw = raw.replace('"priority":', '"priority":"should","priority":', 1)
    if wrapper == "complete_fence":
        raw = "```json\n" + raw + "\n```"
    elif wrapper == "extra_closer":
        raw += "}"
    with pytest.raises(CompactPlanValidationError, match="duplicate key"):
        parse_compact_plan_call(raw, _spec())
