from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .log_parser import LogEvent, ParsedLog, ToolCallInfo
from .time_utils import format_duration_ms


class ActionKind(Enum):
    MODEL_CHANGE = "model_change"
    ASSISTANT_ROUND = "assistant_round"
    TOOL_RESULT = "tool_result"
    ASSISTANT_RESPONSE = "assistant_response"
    CUSTOM_EVENT = "custom_event"
    CUSTOM_MESSAGE = "custom_message"
    OTHER = "other"


ACTION_KIND_LABELS = {
    ActionKind.MODEL_CHANGE: "模型切换",
    ActionKind.ASSISTANT_ROUND: "LLM 推理 + 工具决策",
    ActionKind.TOOL_RESULT: "工具执行结果",
    ActionKind.ASSISTANT_RESPONSE: "最终回复",
    ActionKind.CUSTOM_EVENT: "系统事件",
    ActionKind.CUSTOM_MESSAGE: "运行时上下文",
    ActionKind.OTHER: "其他",
}


@dataclass
class ActionStep:
    step_index: int = 0
    kind: ActionKind = ActionKind.OTHER
    event_id: str = ""
    timestamp: str = ""
    timestamp_ms: int = 0
    latency_from_prev_ms: int = 0
    latency_from_query_ms: int = 0
    reported_duration_ms: int = -1
    scheduling_overhead_ms: int = -1
    description: str = ""
    model: str = ""
    provider: str = ""
    tool_name: str = ""
    stop_reason: str = ""
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    full_content: str = ""
    thinking_content: str = ""
    details_text: str = ""
    usage_text: str = ""
    tool_call_id: str = ""
    hidden_from_ui: bool = False


@dataclass
class UserQueryAnalysis:
    query_index: int = 0
    query_id: str = ""
    query_text: str = ""
    timestamp: str = ""
    timestamp_ms: int = 0
    total_duration_ms: int = 0
    run_id: str = ""
    model_at_start: str = ""
    steps: list[ActionStep] = field(default_factory=list)


def _is_real_user_query(event: LogEvent) -> bool:
    if event.type != "message" or event.role != "user":
        return False
    return "Session Startup" not in event.text_content and "/new or /reset" not in event.text_content


def _classify_event(event: LogEvent) -> ActionKind:
    if event.type == "model_change":
        return ActionKind.MODEL_CHANGE
    if event.type == "custom_message":
        return ActionKind.CUSTOM_MESSAGE
    if event.type == "custom":
        return ActionKind.CUSTOM_EVENT
    if event.type == "message" and event.role == "assistant":
        if event.tool_calls or event.stop_reason == "toolUse":
            return ActionKind.ASSISTANT_ROUND
        if event.stop_reason == "stop":
            return ActionKind.ASSISTANT_RESPONSE
        return ActionKind.ASSISTANT_ROUND
    if event.type == "message" and event.role == "toolResult":
        return ActionKind.TOOL_RESULT
    return ActionKind.OTHER


def _extract_user_query_text(raw: str) -> str:
    pos = raw.rfind("]")
    if pos != -1 and pos + 1 < len(raw):
        tail = raw[pos + 1 :].lstrip()
        if tail:
            return tail
    return raw


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _assistant_description(event: LogEvent, *, limit: int) -> str:
    if event.text_content:
        return _truncate(event.text_content, limit)
    if event.thinking_content:
        return "[思考链] " + _truncate(event.thinking_content, max(limit - 5, 20))
    return "模型生成工具调用"


def _assistant_turn_ended(event: LogEvent) -> bool:
    if event.type != "message" or event.role != "assistant":
        return False
    if event.tool_calls:
        return False
    return event.stop_reason in ("stop", "end_turn", "end")


def _latency_label_for_kind(kind: ActionKind) -> str:
    if kind in (ActionKind.ASSISTANT_ROUND, ActionKind.ASSISTANT_RESPONSE):
        return "推理耗时"
    if kind == ActionKind.TOOL_RESULT:
        return "等待+执行"
    return "距上一步"


def _scheduling_overhead_ms(latency_from_prev_ms: int, reported_duration_ms: int) -> int:
    if reported_duration_ms < 0 or latency_from_prev_ms < 0:
        return -1
    return max(0, latency_from_prev_ms - reported_duration_ms)


def _build_step(event: LogEvent, step_index: int, query_start_ms: int, prev_ms: int) -> ActionStep:
    kind = _classify_event(event)
    reported = event.duration_ms if event.duration_ms >= 0 else event.took_ms
    latency_from_prev = event.timestamp_ms - prev_ms if prev_ms >= 0 else 0
    overhead = (
        _scheduling_overhead_ms(latency_from_prev, reported)
        if kind == ActionKind.TOOL_RESULT
        else -1
    )

    if kind == ActionKind.MODEL_CHANGE:
        description = f"切换模型 -> {event.provider} / {event.model}"
    elif kind == ActionKind.ASSISTANT_ROUND:
        description = _assistant_description(event, limit=100)
    elif kind == ActionKind.TOOL_RESULT:
        description = f"工具 [{event.tool_name}] 返回"
        if event.is_error:
            description += " (错误)"
    elif kind == ActionKind.ASSISTANT_RESPONSE:
        description = _assistant_description(event, limit=120)
    elif kind == ActionKind.CUSTOM_EVENT:
        description = event.custom_type
        if event.run_id:
            description += f" runId={event.run_id}"
    elif kind == ActionKind.CUSTOM_MESSAGE:
        description = event.custom_type or "custom_message"
        if event.hidden_from_ui:
            description += " (display=false)"
    else:
        description = event.type

    return ActionStep(
        step_index=step_index,
        kind=kind,
        event_id=event.id,
        timestamp=event.timestamp,
        timestamp_ms=event.timestamp_ms,
        latency_from_prev_ms=latency_from_prev,
        latency_from_query_ms=event.timestamp_ms - query_start_ms,
        reported_duration_ms=reported,
        scheduling_overhead_ms=overhead,
        description=description,
        model=event.model,
        provider=event.provider,
        tool_name=event.tool_name,
        stop_reason=event.stop_reason,
        tool_calls=list(event.tool_calls),
        full_content=event.text_content,
        thinking_content=event.thinking_content,
        details_text=event.details_text,
        usage_text=event.usage_text,
        tool_call_id=event.tool_call_id,
        hidden_from_ui=event.hidden_from_ui,
    )


def _collect_turn_event_indices(log: ParsedLog, user_event_index: int) -> list[int]:
    indices: list[int] = []
    user_event = log.ordered_events[user_event_index]

    prefetch_types = ("model_change", "custom", "custom_message")

    i = user_event_index
    while i > 0:
        prev = log.ordered_events[i - 1]
        if prev.type not in prefetch_types:
            break
        if user_event.timestamp_ms - prev.timestamp_ms > 10000:
            break
        indices.insert(0, i - 1)
        i -= 1

    for j in range(user_event_index + 1, len(log.ordered_events)):
        event = log.ordered_events[j]
        if _is_real_user_query(event):
            break
        if event.type == "message" and event.role == "user":
            break
        indices.append(j)
        if _assistant_turn_ended(event):
            break

    return indices


def _find_run_id_after_turn(log: ParsedLog, last_turn_index: int) -> str:
    for j in range(last_turn_index + 1, len(log.ordered_events)):
        event = log.ordered_events[j]
        if event.type == "custom" and event.custom_type == "openclaw:bootstrap-context:full" and event.run_id:
            return event.run_id
        if _is_real_user_query(event):
            break
    return ""


def analyze_queries(log: ParsedLog) -> list[UserQueryAnalysis]:
    queries: list[UserQueryAnalysis] = []
    query_index = 0

    for i, event in enumerate(log.ordered_events):
        if not _is_real_user_query(event):
            continue

        query_index += 1
        analysis = UserQueryAnalysis(
            query_index=query_index,
            query_id=event.id,
            query_text=_extract_user_query_text(event.text_content),
            timestamp=event.timestamp,
            timestamp_ms=event.timestamp_ms,
        )

        turn_indices = _collect_turn_event_indices(log, i)
        prev_ms = event.timestamp_ms
        step_index = 0

        for idx in turn_indices:
            turn_event = log.ordered_events[idx]
            if turn_event.type == "model_change" and not analysis.model_at_start:
                analysis.model_at_start = turn_event.model

            step_index += 1
            step = _build_step(turn_event, step_index, event.timestamp_ms, prev_ms)
            analysis.steps.append(step)
            prev_ms = turn_event.timestamp_ms

            if turn_event.type == "message" and turn_event.role == "assistant" and _assistant_turn_ended(turn_event):
                analysis.total_duration_ms = turn_event.timestamp_ms - event.timestamp_ms

        if turn_indices:
            analysis.run_id = _find_run_id_after_turn(log, turn_indices[-1])

        if analysis.total_duration_ms == 0 and analysis.steps:
            analysis.total_duration_ms = analysis.steps[-1].timestamp_ms - event.timestamp_ms

        queries.append(analysis)

    return queries


def print_analysis_report(log: ParsedLog, queries: list[UserQueryAnalysis]) -> None:
    print()
    print("=" * 72)
    print(" OpenClaw 日志分析报告")
    print("=" * 72)
    print(f"Session ID : {log.session.session_id}")
    print(f"CWD        : {log.session.cwd}")
    print(f"事件总数   : {len(log.ordered_events)}")
    if log.parse_stats.skipped_regions:
        print(f"JSON 恢复  : {log.parse_stats.skipped_regions} 处损坏/粘连片段已尝试跳过")
    if log.parse_stats.parse_errors:
        print(f"解析警告   : {len(log.parse_stats.parse_errors)} 条")
    print(f"用户 Query : {len(queries)} 条")
    print("=" * 72)

    for query in queries:
        print(f"\n【Query #{query.query_index}】 {query.timestamp}")
        print(f"  内容: {query.query_text}")
        if query.model_at_start:
            print(f"  模型: {query.model_at_start}")
        if query.run_id:
            print(f"  RunId: {query.run_id}")
        print(f"  总耗时: {format_duration_ms(query.total_duration_ms)}")
        print()
        print("  行为链路 (含各阶段时延):")
        print("  " + "-" * 68)
        print(f"  {'#':<4}{'距上一步':<14}{'距Query':<14}{'类型':<16}行为描述")
        print("  " + "-" * 68)

        for step in query.steps:
            label = ACTION_KIND_LABELS.get(step.kind, "其他")
            print(
                f"  {step.step_index:<4}"
                f"{format_duration_ms(step.latency_from_prev_ms):<14}"
                f"{format_duration_ms(step.latency_from_query_ms):<14}"
                f"{label:<16}"
                f"{step.description}"
            )
            for call in step.tool_calls:
                suffix = f" ({call.arguments_summary})" if call.arguments_summary else ""
                print(f"       -> 工具调用: {call.name}{suffix}")
            if step.thinking_content:
                preview = _truncate(step.thinking_content, 80)
                print(f"       -> 思考链 (thinking): {preview}")
            if step.full_content and step.thinking_content:
                preview = _truncate(step.full_content, 80)
                print(f"       -> 对外输出 (text): {preview}")
            if step.reported_duration_ms >= 0:
                print(f"       -> 工具报告耗时: {format_duration_ms(step.reported_duration_ms)}")
            if step.scheduling_overhead_ms >= 0 and step.scheduling_overhead_ms > 0:
                print(f"       -> 调度开销: {format_duration_ms(step.scheduling_overhead_ms)}")
            if step.model:
                provider = f"{step.provider} / " if step.provider else ""
                reason = f" [{step.stop_reason}]" if step.stop_reason else ""
                print(f"       -> 模型: {provider}{step.model}{reason}")

        print("-" * 72)

    print("\n时延说明:")
    print("  - 推理耗时: LLM 推理步基于日志落盘时间的墙钟间隔")
    print("  - 等待+执行: 工具步从上一行为到结果落盘 (通常接近工具报告耗时)")
    print("  - 距Query : 从用户发送 query 到该行为的累计时间")
    print("  - 工具报告耗时: exec/web_fetch 等工具在 details 中记录的 durationMs/tookMs")
    print("  - 调度开销: 等待+执行 减去 工具报告耗时 (启动/排队/写日志)")
    print("\n内容类型说明:")
    print("  - thinking: 模型内部推理链，通常不直接展示给用户")
    print("  - text    : 模型对外输出正文，会作为助手消息展示给用户")


def build_analysis_payload(log: ParsedLog, queries: list[UserQueryAnalysis]) -> dict:
    return {
        "sessionId": log.session.session_id,
        "cwd": log.session.cwd,
        "queryCount": len(queries),
        "eventCount": len(log.ordered_events),
        "queries": [
            {
                "index": query.query_index,
                "id": query.query_id,
                "text": query.query_text,
                "timestamp": query.timestamp,
                "totalDurationMs": query.total_duration_ms,
                "runId": query.run_id,
                "model": query.model_at_start,
                "steps": [
                    {
                        "index": step.step_index,
                        "kind": ACTION_KIND_LABELS.get(step.kind, "其他"),
                        "timestamp": step.timestamp,
                        "latencyFromPrevMs": step.latency_from_prev_ms,
                        "latencyFromQueryMs": step.latency_from_query_ms,
                        "reportedDurationMs": step.reported_duration_ms,
                        "schedulingOverheadMs": step.scheduling_overhead_ms,
                        "latencyLabel": _latency_label_for_kind(step.kind),
                        "description": step.description,
                        "model": step.model,
                        "toolName": step.tool_name,
                        "stopReason": step.stop_reason,
                        "toolCalls": [
                            {
                                "id": call.id,
                                "name": call.name,
                                "arguments": call.arguments_summary,
                                "argumentsFull": call.arguments_full,
                            }
                            for call in step.tool_calls
                        ],
                        "fullContent": step.full_content,
                        "thinkingContent": step.thinking_content,
                        "detailsText": step.details_text,
                        "usageText": step.usage_text,
                        "toolCallId": step.tool_call_id,
                    }
                    for step in query.steps
                ],
            }
            for query in queries
        ],
    }


def export_analysis_json(path: str | Path, log: ParsedLog, queries: list[UserQueryAnalysis]) -> None:
    Path(path).write_text(
        json.dumps(build_analysis_payload(log, queries), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
