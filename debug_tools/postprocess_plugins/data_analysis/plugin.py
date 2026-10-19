"""统一的数据分析后处理插件入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from debug_tools.postprocess_plugins.data_analysis.metrics import aggregate, analyze_request
from debug_tools.postprocess_plugins.data_analysis.usage import analyze_usage, read_object

VERSION = "batch-analysis-v1"


def process_sample(context: dict[str, Any]) -> dict[str, Any]:
    sample = context.get("sample") or {}
    requests = []
    warnings = []
    for directory in sorted(Path(context.get("sampleDir") or "").glob("attempt_*")):
        if not directory.is_dir() or not directory.name.removeprefix("attempt_").isdigit():
            continue
        saved = {}
        view = {}
        for name in ("result.json", "trace/view.json"):
            try:
                value = read_object(directory / name)
                if name == "result.json":
                    saved = value
                else:
                    view = value
            except (OSError, ValueError) as exc:
                warnings.append(f"{directory.name}/{name}: {type(exc).__name__}: {exc}")
        requests.append(analyze_request(view, saved, directory.name))
    final = context.get("finalAttemptDir")
    if not requests:
        warnings.append("没有已落盘的请求记录")
    usage = analyze_usage(Path(final) if final else None)
    analysis = {
        "schemaVersion": VERSION,
        "sampleId": sample.get("id"),
        "requests": requests,
        "usage": usage,
        "warnings": warnings,
    }
    summary = aggregate([analysis])
    partial = bool(warnings or usage.get("warnings"))
    for request in requests:
        partial = partial or request.get("traceStatus") != "complete"
    return {
        "status": "partial" if partial else "success",
        "summary": "请求与最终产物分析完成",
        "facts": {
            "requestCount": len(requests),
            "paddedCount": summary.get("paddedCount"),
            "traceKnown": sum(item.get("traceStatus") == "complete" for item in requests),
        },
        "artifacts": [{"key": "analysis", "data": analysis}],
    }


def process_dataset(context: dict[str, Any]) -> dict[str, Any]:
    analyses = []
    for sample in context.get("sampleResults") or []:
        for artifact in sample.get("artifacts") or []:
            if artifact.get("key") == "analysis" and isinstance(artifact.get("data"), dict):
                analyses.append(artifact.get("data"))
    result = aggregate(analyses)
    kpis = []
    for key, label in (
        ("requestCount", "实际请求"),
        ("paddedCount", "补齐记录"),
        ("effectiveCount", "有效统计记录"),
    ):
        kpis.append({"label": label, "value": result.get(key)})
    for key, label in (("pass1", "pass@1"), ("pass2", "pass@2")):
        metric = result.get(key) or {}
        rate = metric.get("rate")
        kpis.append(
            {
                "label": label,
                "value": rate * 100.0 if rate is not None else None,
                "unit": "%",
                "description": f"有效实际请求 {metric.get('count', 0)}",
            }
        )
    for key, label in (
        ("planMs", "计划平均耗时"),
        ("generateMs", "生成平均耗时"),
        ("repairMs", "修复平均耗时"),
        ("elapsedMs", "接口端到端平均耗时"),
        ("interfaceRetries", "平均接口重试"),
        ("repairs", "平均质量修复"),
        ("modelRetries", "平均模型失败重试"),
        ("planRetries", "平均计划重试"),
        ("providerFallbacks", "平均提供方切换"),
    ):
        metric = result.get(key) or {}
        kpis.append(
            {
                "label": label,
                "value": metric.get("mean"),
                "unit": "ms" if key.endswith("Ms") else "次",
                "description": f"有效记录 {metric.get('count', 0)}",
            }
        )
    distributions = []
    model_rows = []
    for phase, models in (result.get("models") or {}).items():
        for name, metric in models.items():
            model_rows.append({"phase": phase, "metric": name, **metric})
    for name, metric in (result.get("models") or {}).get("all", {}).items():
        kpis.append(
            {
                "label": "模型 TTFT" if name == "ttftMs" else "模型 TPS",
                "value": metric.get("mean"),
                "unit": "ms" if name == "ttftMs" else "token/s",
                "description": f"有效物理调用 {metric.get('count', 0)}",
            }
        )
    for category, usage in (result.get("usage") or {}).items():
        rate = usage.get("rate")
        kpis.append(
            {
                "label": f"{category} 类别使用率",
                "value": rate * 100.0 if rate is not None else None,
                "unit": "%",
                "description": f"使用 {usage.get('used')} / 可分析 {usage.get('count')}",
            }
        )
        for item in usage.get("items") or []:
            distributions.append({"category": category, **item, "denominator": usage.get("count")})
    return {
        "status": "success",
        "summary": f"已分析 {len(analyses)} 个样本，缺失指标保持未知",
        "facts": {"sampleCount": len(analyses)},
        "artifacts": [
            {"key": "statistics", "data": {"schemaVersion": VERSION, **result}},
            {"key": "overview", "data": kpis},
            {"key": "usage", "data": distributions},
            {"key": "models", "data": model_rows},
        ],
    }
