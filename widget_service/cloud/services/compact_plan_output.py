"""Plan 文本传输封装适配；不负责计划内容校验。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class PlanOutputEnvelope:
    text: str
    warnings: tuple[str, ...] = ()


def normalize_plan_output(raw_output: str) -> PlanOutputEnvelope:
    """只拆已知单调用封装；未知输出交原 JSON 解析器拒绝。"""
    text = raw_output.strip()
    call_prefix = re.match(r"call[ \t]*\r?\n", text)
    if call_prefix is not None:
        return PlanOutputEnvelope(
            text=text.removeprefix(call_prefix.group()).strip(),
            warnings=("Plan call line prefix removed; JSON content unchanged.",),
        )
    prefix = _DSML_PREFIX.match(text)
    if prefix is None:
        return PlanOutputEnvelope(text=text)
    body = text.removeprefix(prefix.group())
    try:
        _arguments, end = json.JSONDecoder().raw_decode(body)
    except json.JSONDecodeError:
        return PlanOutputEnvelope(text=text)
    suffix = re.sub(r">\s+<", "><", body[end:].strip())
    if suffix not in _DSML_SUFFIXES:
        return PlanOutputEnvelope(text=text)
    return PlanOutputEnvelope(
        text='{"name":"submit_card_plan","arguments":' + body[:end] + "}",
        warnings=("Plan DSML transport wrapper normalized; arguments unchanged.",),
    )


def plan_output_format_feedback(raw_output: str) -> dict[str, str | int]:
    """提供外层格式和解析位置，不改变失败输出或业务错误。"""
    text = raw_output.strip()
    envelope = "plain_json"
    if text.startswith(f"<{_DSML}"):
        envelope = "DSML"
    elif re.match(r"call[ \t]*\r?\n", text):
        envelope = "call_prefix"
    elif text.startswith("```"):
        envelope = "markdown_fence"
    feedback: dict[str, str | int] = {"detectedEnvelope": envelope}
    candidate = normalize_plan_output(text).text
    prefix = _DSML_PREFIX.match(text)
    if prefix is not None and candidate == text:
        candidate = text.removeprefix(prefix.group())
        feedback["jsonScope"] = "DSML_arguments"
    else:
        feedback["jsonScope"] = "tool_call"
    try:
        json.loads(candidate)
    except json.JSONDecodeError as exc:
        feedback.update(jsonLine=exc.lineno, jsonColumn=exc.colno, jsonError=exc.msg)
    return feedback
