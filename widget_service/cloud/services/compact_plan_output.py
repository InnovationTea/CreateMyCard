"""Plan 文本传输封装适配；不负责计划内容校验。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

PLAN_JSON_OUTPUT_INSTRUCTION = (
    '只输出一个纯 JSON 对象，结构为 {"name":"submit_card_plan","arguments":{...}}。'
    "仅当本轮另行提供了 report_missing_data 合同且必要动态输入确实缺失时，"
    "使用该名称及对应arguments报告缺口，不能同时提交两种结果。"
    "arguments 必须按本轮 Schema 填写完整对象，不是 JSON 字符串。"
    "这是文本 JSON 协议，不是原生工具调用；禁止 DSML/XML 标记、call 前缀、"
    "Markdown 代码围栏、解释和多个调用。第一个非空字符必须是 {，最后一个必须是 }。"
)

_DSML = "｜｜DSML｜｜"
_DSML_PREFIX = re.compile(
    rf'<{_DSML} calls>\s*<{_DSML} invoke name="submit_card_plan">\s*'
    rf'(?:<{_DSML} parameter name="arguments" string="false">\s*)?'
)
_PARAMETER_END = f"</{_DSML} parameter>"
_INVOKE_END = f"</{_DSML} invoke>"
_CALLS_END = f"</{_DSML} calls>"
_NAME_PARAMETER = (
    f'<{_DSML} parameter name="name" string="true">'
    f"submit_card_plan{_PARAMETER_END}"
)
_DSML_SUFFIXES = frozenset(
    re.sub(r">\s+<", "><", suffix.strip())
    for suffix in (
        "",
        _PARAMETER_END + _NAME_PARAMETER + _INVOKE_END + _CALLS_END,
        _PARAMETER_END + _INVOKE_END + _CALLS_END,
        f"<{_DSML} end_invoke><{_DSML} end_calls>",
        _PARAMETER_END + _INVOKE_END + f"</{_DSML}>",
    )
)
_PLAN_ARGUMENT_KEYS = frozenset({
    "info_required", "layoutHints", "contentGroups", "selectionNotes", "omittedContents",
    "presentationStyle", "paletteFamily", "assetAssignments", "composition",
})
_OPEN_JSON_FENCE = re.compile(r"^```(?:json)?[ \t]*\r?\n", re.IGNORECASE)
_CLOSE_JSON_FENCE = re.compile(r"\r?\n[ \t]*```[ \t]*$")


class PlanDuplicateKeyError(ValueError):
    """重复 JSON 键存在歧义，不能选择最后一个值继续修复。"""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Plan JSON contains duplicate key {key!r}.")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanDuplicateKeyError(key)
        result[key] = value
    return result


def decode_plan_json(text: str) -> Any:
    """保留 JSON 原类型并拒绝任意层级的重复键。"""
    return json.loads(text, object_pairs_hook=_unique_json_object)


@dataclass(frozen=True)
class PlanOutputEnvelope:
    text: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanObjectEnvelope:
    payload: dict[str, Any]
    warnings: tuple[str, ...] = ()


def normalize_plan_root_arguments(payload: dict[str, Any]) -> PlanObjectEnvelope:
    """仅搬移已知、无重名的参数；不填值、不决定当前 Schema 是否允许它。"""
    original = PlanObjectEnvelope(payload=payload)
    if payload.get("name") != "submit_card_plan":
        return original
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        return original
    misplaced = set(payload) - {"name", "arguments"}
    if not misplaced or misplaced - _PLAN_ARGUMENT_KEYS:
        return original
    if set(arguments) - _PLAN_ARGUMENT_KEYS or misplaced.intersection(arguments):
        return original
    normalized_arguments = dict(arguments)
    for key, value in payload.items():
        if key in misplaced:
            normalized_arguments[key] = value
    return PlanObjectEnvelope(
        payload={"name": "submit_card_plan", "arguments": normalized_arguments},
        warnings=(
            "Plan root parameters moved to arguments without changing values: "
            + ", ".join(sorted(misplaced)) + ".",
        ),
    )


def _normalize_transport(raw_output: str) -> PlanOutputEnvelope:
    """只拆既有单调用传输封装，普通输出保留原始字节。"""
    text = raw_output.strip()
    call_prefix = re.match(r"call[ \t]*\r?\n", text)
    if call_prefix is not None:
        return PlanOutputEnvelope(
            text=text.removeprefix(call_prefix.group()).strip(),
            warnings=("Plan call line prefix removed; JSON content unchanged.",),
        )
    prefix = _DSML_PREFIX.match(text)
    if prefix is None:
        return PlanOutputEnvelope(text=raw_output)
    body = text.removeprefix(prefix.group())
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_unique_json_object)
        _arguments, end = decoder.raw_decode(body)
    except (json.JSONDecodeError, PlanDuplicateKeyError):
        return PlanOutputEnvelope(text=raw_output)
    suffix = re.sub(r">\s+<", "><", body[end:].strip())
    if suffix not in _DSML_SUFFIXES:
        return PlanOutputEnvelope(text=text)
    return PlanOutputEnvelope(
        text='{"name":"submit_card_plan","arguments":' + body[:end] + "}",
        warnings=("Plan DSML transport wrapper normalized; arguments unchanged.",),
    )


def _complete_json_object(text: str) -> dict[str, Any] | None:
    payload: dict[str, Any] | None = None
    try:
        decoded = decode_plan_json(text)
    except (json.JSONDecodeError, PlanDuplicateKeyError):
        return payload
    if isinstance(decoded, dict):
        payload = decoded
    return payload


def _normalize_single_sided_fence(envelope: PlanOutputEnvelope) -> PlanOutputEnvelope:
    text = envelope.text.strip()
    opening = _OPEN_JSON_FENCE.match(text)
    closing = _CLOSE_JSON_FENCE.search(text)
    if bool(opening) == bool(closing):
        return envelope
    candidate = text
    if opening is not None:
        candidate = text.removeprefix(opening.group()).strip()
    elif closing is not None:
        candidate = text.removesuffix(closing.group()).strip()
    if _complete_json_object(candidate) is None:
        return envelope
    return PlanOutputEnvelope(
        text=candidate,
        warnings=envelope.warnings + (
            "Plan single-sided Markdown fence removed; complete JSON unchanged.",
        ),
    )


def normalize_plan_output(raw_output: str) -> PlanOutputEnvelope:
    """无歧义封装及错层参数规范化，业务字段仍交原 Schema 校验。"""
    envelope = _normalize_single_sided_fence(_normalize_transport(raw_output))
    payload = _complete_json_object(envelope.text)
    if payload is None:
        return envelope
    normalized = normalize_plan_root_arguments(payload)
    if not normalized.warnings:
        return envelope
    return PlanOutputEnvelope(
        text=json.dumps(normalized.payload, ensure_ascii=False),
        warnings=envelope.warnings + normalized.warnings,
    )


def _root_parameter_feedback(payload: Any) -> dict[str, Any]:
    feedback: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return feedback
    unexpected = set(payload) - {"name", "arguments"}
    if not unexpected:
        return feedback
    feedback["unexpectedRootKeys"] = sorted(unexpected)
    expected_paths = {}
    for key in sorted(unexpected):
        if key in _PLAN_ARGUMENT_KEYS:
            expected_paths[key] = "/arguments/" + key
    feedback["expectedPaths"] = expected_paths
    arguments = payload.get("arguments")
    if isinstance(arguments, dict):
        conflicts = unexpected.intersection(arguments)
        if conflicts:
            feedback["conflictingArgumentKeys"] = sorted(conflicts)
    return feedback


def plan_output_format_feedback(raw_output: str) -> dict[str, Any]:
    """提供外层格式和解析位置，不改变失败输出或业务错误。"""
    text = raw_output.strip()
    envelope = "plain_json"
    if text.startswith(f"<{_DSML}"):
        envelope = "DSML"
    elif re.match(r"call[ \t]*\r?\n", text):
        envelope = "call_prefix"
    elif text.startswith("```") or _CLOSE_JSON_FENCE.search(text):
        envelope = "markdown_fence"
    feedback: dict[str, Any] = {"detectedEnvelope": envelope}
    candidate = _normalize_single_sided_fence(_normalize_transport(text)).text
    prefix = _DSML_PREFIX.match(text)
    if prefix is not None and candidate == text:
        candidate = text.removeprefix(prefix.group())
        feedback["jsonScope"] = "DSML_arguments"
    else:
        feedback["jsonScope"] = "tool_call"
    opening = _OPEN_JSON_FENCE.match(candidate)
    closing = _CLOSE_JSON_FENCE.search(candidate)
    if opening is not None and closing is not None:
        candidate = candidate.removeprefix(opening.group()).removesuffix(closing.group()).strip()
    try:
        payload = decode_plan_json(candidate)
    except json.JSONDecodeError as exc:
        start = max(0, exc.pos - 40)
        end = min(len(candidate), exc.pos + 40)
        feedback.update(
            jsonLine=exc.lineno, jsonColumn=exc.colno, jsonOffset=exc.pos,
            jsonError=exc.msg, jsonContext=candidate[start:end],
        )
    except PlanDuplicateKeyError as exc:
        feedback.update(jsonError=str(exc), duplicateJsonKey=exc.key)
    else:
        feedback.update(_root_parameter_feedback(payload))
    return feedback
