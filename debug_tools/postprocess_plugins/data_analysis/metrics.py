"""请求级 Trace 指标；仅消费已落盘证据，不补造缺失数据。"""

from __future__ import annotations

import math
from typing import Any

COUNT_KEYS = {
    "interfaceRetries": "interfaceRetries",
    "repairs": "qualityRepairRetries",
    "modelRetries": "modelTransportRetries",
    "planRetries": "planContractRetries",
    "providerFallbacks": "providerFallbacks",
}
PHASES = {"plan": "plan", "dsl": "generate", "repair": "repair"}


def number(value: object) -> float | None:
    result: float | None = None
    if isinstance(value, int | float) and not isinstance(value, bool):
        candidate = float(value)
        if math.isfinite(candidate) and candidate >= 0.0:
            result = candidate
    return result


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _spans(view: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for node in view.get("nodes") or []:
        if isinstance(node, dict):
            result.append(node)
    return result


def _phase_duration(nodes: list[dict[str, Any]], phase: str) -> float | None:
    # 合并区间，既保留多次阶段执行，也避免父子 span 或重叠 span 重复累计。
    intervals: list[tuple[float, float]] = []
    invalid = False
    for node in nodes:
        if node.get("operation") != phase:
            continue
        start = number(node.get("startOffsetMs"))
        duration = number(node.get("durationMs"))
        if start is None or duration is None:
            invalid = True
            continue
        intervals.append((start, start + duration))
    if invalid or not intervals:
        return None
    total = 0.0
    start, end = sorted(intervals)[0]
    for next_start, next_end in sorted(intervals)[1:]:
        if next_start <= end:
            end = max(end, next_end)
            continue
        total += end - start
        start, end = next_start, next_end
    return total + end - start


def _pass_values(nodes: list[dict[str, Any]], complete: bool) -> dict[str, bool | None]:
    attempts: dict[int, str] = {}
    for node in nodes:
        if node.get("operation") != "interface.attempt":
            continue
        index = _object(node.get("attempts")).get("interface")
        if isinstance(index, int) and index > 0:
            attempts[index] = str(node.get("status") or "")
    first = attempts.get(1)
    second = attempts.get(2)
    terminal = {"success", "degraded", "failed", "unsupported", "cancelled", "error", "timeout"}
    pass_one: bool | None = first == "success" if first in terminal else None
    pass_two: bool | None = None
    if first == "success" or second == "success":
        pass_two = True
    elif first in terminal and second in terminal:
        pass_two = False
    elif complete and first in terminal and second is None:
        pass_two = False
    return {"pass1": pass_one, "pass2": pass_two}


def _model_calls(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls = []
    for node in nodes:
        if node.get("operation") != "model.physical_call":
            continue
        metrics = _object(node.get("metrics"))
        attributes = _object(node.get("attributes"))
        ttft = number(metrics.get("firstTokenLatencyMs"))
        tps_value = metrics.get("tokensPerSecond")
        if isinstance(tps_value, str):
            try:
                tps_value = float(tps_value)
            except ValueError:
                tps_value = None
        tps = number(tps_value)
        inference = number(metrics.get("inferenceDurationMs"))
        if inference is None and ttft is not None:
            # 仅使用传输指标的 duration，不能拿包含排队的物理调用区间推算。
            for event in node.get("events") or []:
                if isinstance(event, dict) and event.get("event") == "model.transport_metrics":
                    duration = number(event.get("durationMs"))
                    if duration is not None and duration >= ttft:
                        inference = duration - ttft
        tokens = number(metrics.get("completionTokens"))
        can_derive = tokens is not None and inference is not None and inference > 0.0
        if tps is None and can_derive:
            assert tokens is not None and inference is not None
            tps = tokens * 1000.0 / inference
        phase = attributes.get("phase") or attributes.get("modelPhase")
        model_phase = "generate" if phase == "initial" else PHASES.get(str(phase), "unknown")
        calls.append(
            {
                "spanId": node.get("id"),
                "phase": model_phase,
                "sourcePhase": phase,
                "ttftMs": ttft,
                "tps": tps,
                "status": node.get("status"),
                "unknownMetrics": {
                    "ttftMs": "" if ttft is not None else "没有有效首 token 传输指标",
                    "tps": "" if tps is not None else "没有有效 TPS 或输出 token / 推理时长证据",
                },
            }
        )
    return calls


def analyze_request(view: dict[str, Any], saved: dict[str, Any], source: str) -> dict[str, Any]:
    usable = view.get("status") in {"complete", "partial"}
    nodes = _spans(view) if usable else []
    complete = view.get("status") == "complete"
    exact = view.get("timingMode") == "exact"
    summary = _object(view.get("summary")) if usable else {}
    retries = _object(summary.get("retryCounts"))
    counts: dict[str, float | None] = {}
    for label, key in COUNT_KEYS.items():
        value = number(retries.get(key))
        missing_in_complete_trace = key not in retries and complete and exact
        counts[label] = 0.0 if missing_in_complete_trace else value
    # 用 span 计修复次数，避免把计划重试或模型失败重试当作质量修复。
    repairs = sum(node.get("operation") == "repair.attempt" for node in nodes)
    if (complete and exact) or repairs:
        counts["repairs"] = float(repairs)
    phases = {}
    for operation, label in PHASES.items():
        value = _phase_duration(nodes, operation) if exact else None
        if value is None and complete and exact:
            present = any(node.get("operation") == operation for node in nodes)
            if not present:
                value = 0.0
        phases[label] = value
    elapsed = None
    elapsed_source = "unknown"
    for node in nodes:
        if node.get("operation") == "request" and exact:
            elapsed = number(node.get("durationMs"))
            if elapsed is not None:
                elapsed_source = "trace.request"
                break
    if elapsed is None:
        elapsed = number(saved.get("elapsedMs"))
        if elapsed is not None:
            elapsed_source = "result.elapsedMs"
    passes = _pass_values(nodes, complete)
    unknown_metrics = {}
    for label, value in phases.items():
        if value is None:
            unknown_metrics[f"{label}Ms"] = "没有可信的精确阶段区间"
    for label, value in counts.items():
        if value is None:
            unknown_metrics[label] = "没有完整精确 Trace 或显式次数记录"
    for label, value in passes.items():
        if value is None:
            unknown_metrics[label] = "缺少必要的接口尝试终态"
    if elapsed is None:
        unknown_metrics["elapsedMs"] = "请求根区间及同次请求耗时均缺失"
    return {
        "source": source,
        "uid": saved.get("uid") or view.get("uid"),
        "traceStatus": view.get("status", "missing"),
        "status": saved.get("status"),
        **passes,
        "weight": 2 if passes.get("pass1") is True else 1,
        "phasesMs": phases,
        "elapsedMs": elapsed,
        "elapsedSource": elapsed_source,
        "counts": counts,
        "models": _model_calls(nodes),
        "unknownMetrics": unknown_metrics,
        "warnings": list(view.get("warnings") or []),
        "unknownReason": "" if complete else "Trace 缺失、不完整或无效；缺失指标不计零",
    }


def mean(values: list[tuple[float, int]]) -> dict[str, float | int | None]:
    count = sum(weight for _, weight in values)
    total = sum(value * weight for value, weight in values)
    return {"sum": total, "count": count, "mean": total / count if count else None}


def aggregate(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    requests = []
    for sample in analyses:
        requests.extend(sample.get("requests") or [])
    result: dict[str, Any] = {
        "sampleCount": len(analyses),
        "requestCount": len(requests),
        "paddedCount": sum(int(item.get("weight", 1)) - 1 for item in requests),
    }
    result["effectiveCount"] = result.get("requestCount", 0) + result.get("paddedCount", 0)
    for key in ("pass1", "pass2"):
        known = [item.get(key) for item in requests if isinstance(item.get(key), bool)]
        hits = sum(value is True for value in known)
        result[key] = {
            "hits": hits,
            "count": len(known),
            "rate": hits / len(known) if known else None,
        }
    fields = ["elapsedMs", "planMs", "generateMs", "repairMs", *COUNT_KEYS]
    for key in fields:
        values = []
        for request in requests:
            value = request.get(key)
            if key in COUNT_KEYS:
                value = _object(request.get("counts")).get(key)
            elif key in {"planMs", "generateMs", "repairMs"}:
                value = _object(request.get("phasesMs")).get(key.removesuffix("Ms"))
            parsed = number(value)
            if parsed is not None:
                values.append((parsed, int(request.get("weight", 1))))
        result[key] = mean(values)
    models: dict[str, Any] = {}
    for phase in ("all", "plan", "generate", "repair", "unknown"):
        metrics: dict[str, Any] = {}
        for key in ("ttftMs", "tps"):
            values = []
            for request in requests:
                for model in request.get("models") or []:
                    if phase != "all" and model.get("phase") != phase:
                        continue
                    parsed = number(model.get(key))
                    if parsed is not None:
                        values.append((parsed, int(request.get("weight", 1))))
            metrics[key] = mean(values)
        models[phase] = metrics
    result["models"] = models
    usage: dict[str, Any] = {}
    for category in ("components", "assets", "events", "data"):
        denominator = 0
        used = 0
        items: dict[str, int] = {}
        for sample in analyses:
            values = _object(sample.get("usage")).get(category)
            if not isinstance(values, list):
                continue
            denominator += 1
            used += bool(values)
            for name in set(values):
                items[name] = items.get(name, 0) + 1
        rows = []
        for name, count in sorted(items.items()):
            rows.append({"id": name, "count": count, "rate": count / denominator})
        usage[category] = {
            "count": denominator,
            "used": used,
            "rate": used / denominator if denominator else None,
            "items": rows,
        }
    result["usage"] = usage
    return result
