"""Build machine-readable and human-readable summaries for JSX Runner runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable


_GENERIC_CODES = {
    "contract-or-protocol",
    "contract_or_protocol",
    "static-validation",
    "static_validation",
    "validation",
}


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _rounded(value: float) -> float:
    return round(value, 2)


def _average(values: list[float]) -> float:
    return _rounded(sum(values) / len(values)) if values else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.5)))
    return _rounded(ordered[index])


def _rate(numerator: int, denominator: int) -> float:
    return _rounded(100.0 * numerator / denominator) if denominator else 0.0


def _enabled_state(value: Any) -> str:
    if value is True:
        return "enabled"
    if value is False:
        return "disabled"
    return "unknown"


def _message_category(message: str, phase: str = "", code: str = "") -> str:
    text = f"{phase} {code} {message}".lower()
    if any(token in text for token in (
        "validation_infrastructure",
        "validatorinfrastructureerror",
        "validator infrastructure",
        "校验基础设施",
        "校验器运行失败",
        "无法启动 jsx 校验器",
    )):
        return "validation_infrastructure"
    if any(token in text for token in ("静态文本", "业务数值", "invented", "not provided", "未提供", "固化")):
        return "invented_or_static_data"
    if any(token in text for token in ("ambiguous without a static semantic label", "requires a static semantic label", "语义标签")):
        return "metric_semantics"
    if any(token in text for token in ("dataids", "data id", "data binding", "data-binding", "绑定", "sample value")):
        return "data_binding"
    if any(token in text for token in ("assetcandidates", "functional icon", "resource", " icon", " src", "资源", "图标")):
        return "asset"
    if any(token in text for token in ("actionid", "duplicate-action", "interaction", "onclick", "交互", "动作")):
        return "interaction"
    if any(token in text for token in ("coverage", "unmetrequirement", "需求覆盖")):
        return "coverage"
    if any(token in text for token in ("overflow", "layout", "geometry", "budget", "card.size", "relative stack", "放不下", "溢出", "尺寸", "布局")):
        return "layout"
    if any(token in text for token in ("browser", "chromium", "浏览器")):
        return "browser_validation"
    if any(token in text for token in ("parse", "syntax", "compilation", "conversion", "编译", "转换", "语法")):
        return "conversion"
    if any(token in text for token in ("contract", "protocol", "unsupported", "unknown component", "组件合同")):
        return "component_contract"
    return phase or "other"


def _reason_code(message: str, phase: str = "", code: str = "") -> str:
    text = message.lower()
    patterns = (
        ((
            "validatorinfrastructureerror",
            "validator infrastructure",
            "校验基础设施",
            "校验器运行失败",
            "无法启动 jsx 校验器",
        ), "validator-infrastructure"),
        (("unknown data binding", "unknown binding", "未知数据绑定"), "unknown-data-binding"),
        (("cannot be data-bound", "不可绑定"), "unsupported-data-binding"),
        (("does not match sample value", "样例值"), "binding-sample-mismatch"),
        (("assetcandidates", "functional icon", "resource path", "资源候选"), "invalid-asset-reference"),
        (("duplicate-action", "同一个 action", "重复动作"), "duplicate-action-control"),
        (("actionid", "unknown action", "未知动作"), "invalid-action-reference"),
        (("coverage", "unmetrequirements", "需求覆盖"), "coverage-mismatch"),
        (("relative stack", "relative-stack"), "relative-stack-structure"),
        (("card.size", "size does not match", "尺寸不匹配"), "card-size-mismatch"),
        (("horizontal", "横向"), "horizontal-overflow"),
        (("vertical", "纵向"), "vertical-overflow"),
        (("overflow", "budget", "放不下", "溢出"), "layout-overflow"),
        (("静态文本", "业务数值", "invented", "未提供的数值"), "invented-or-static-business-value"),
        (("unsupported prop", "unknown prop", "不支持的属性"), "unsupported-component-prop"),
        (("browser", "chromium", "浏览器"), "browser-validation"),
    )
    for needles, label in patterns:
        if any(needle in text for needle in needles):
            return label
    normalized = str(code or phase or "other").strip().lower().replace("_", "-")
    if normalized and normalized not in _GENERIC_CODES:
        return normalized
    return _message_category(message, phase, code).replace("_", "-")


def _iter_findings(result: dict[str, Any]) -> Iterable[dict[str, str]]:
    findings = result.get("findings")
    if isinstance(findings, list) and findings:
        for finding in findings:
            if isinstance(finding, dict):
                yield {
                    "phase": str(finding.get("phase") or result.get("phase") or ""),
                    "code": str(finding.get("code") or ""),
                    "message": str(finding.get("message") or finding.get("error") or result.get("error") or "unknown error"),
                }
        return
    yield {
        "phase": str(result.get("phase") or ""),
        "code": "",
        "message": str(result.get("error") or "unknown error"),
    }


def _aggregate_reasons(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["category"], item["code"])
        record = grouped.setdefault(key, {
            "category": item["category"],
            "code": item["code"],
            "occurrenceCount": 0,
            "taskIds": set(),
            "sampleMessages": [],
        })
        record["occurrenceCount"] += 1
        record["taskIds"].add(str(item["taskId"]))
        message = item["message"]
        if message not in record["sampleMessages"] and len(record["sampleMessages"]) < 3:
            record["sampleMessages"].append(message)
    output = []
    for record in grouped.values():
        task_ids = sorted(
            record.pop("taskIds"),
            key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
        )
        record["affectedTaskCount"] = len(task_ids)
        record["taskIds"] = task_ids
        output.append(record)
    return sorted(
        output,
        key=lambda item: (-item["occurrenceCount"], item["category"], item["code"]),
    )


def _task_metrics(
    trace: dict[str, Any],
    validation_mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    turns = trace.get("turn_trace") if isinstance(trace.get("turn_trace"), list) else []
    rejected_submissions = 0
    accepted_submissions = 0
    conversion_failures = 0
    inferred_repair_calls = 0
    inferred_tool_argument_repairs = 0
    inferred_protocol_retries = 0
    repair_pending = False
    pending_rejection_reasons: list[dict[str, Any]] = []
    retry_reason_items: list[dict[str, Any]] = []
    issue_reason_items: list[dict[str, Any]] = []
    task_id = trace.get("task_id")

    for turn_index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        has_later_turn = turn_index + 1 < len(turns)
        if repair_pending:
            inferred_repair_calls += 1
            if pending_rejection_reasons:
                retry_reason_items.extend(pending_rejection_reasons)
                pending_rejection_reasons = []
        status = str(turn.get("status") or "")
        tool = str(turn.get("tool") or "")
        result = turn.get("tool_result") if isinstance(turn.get("tool_result"), dict) else {}
        if isinstance(turn.get("tool_argument_repair"), dict):
            inferred_tool_argument_repairs += 1
        if status == "tool_failed" and result.get("phase") == "tool_arguments":
            item = {
                "taskId": task_id,
                "category": "model_protocol",
                "code": "invalid-tool-arguments",
                "message": str(result.get("error") or "tool arguments were invalid JSON"),
            }
            if has_later_turn:
                inferred_protocol_retries += 1
                retry_reason_items.append(item)
            issue_reason_items.append(item)
        elif tool == "submit_card_jsx" and not result.get("ok"):
            rejected_submissions += 1
            repair_pending = True
            rejection_reasons = []
            submission_is_conversion_failure = validation_mode == "disabled"
            for finding in _iter_findings(result):
                category = _message_category(finding["message"], finding["phase"], finding["code"])
                item = {
                    "taskId": task_id,
                    "category": category,
                    "code": _reason_code(finding["message"], finding["phase"], finding["code"]),
                    "message": finding["message"],
                }
                rejection_reasons.append(item)
                issue_reason_items.append(item)
                if category == "conversion":
                    submission_is_conversion_failure = True
            if submission_is_conversion_failure:
                conversion_failures += 1
            pending_rejection_reasons = rejection_reasons
        elif tool == "submit_card_jsx" and result.get("ok"):
            accepted_submissions += 1
            repair_pending = False
        elif status == "no_tool_call":
            message = "model output was truncated" if turn.get("finish_reason") == "length" else "model did not call the expected tool"
            item = {
                "taskId": task_id,
                "category": "model_protocol",
                "code": "truncated-output" if turn.get("finish_reason") == "length" else "missing-tool-call",
                "message": message,
            }
            if has_later_turn:
                retry_reason_items.append(item)
            issue_reason_items.append(item)
        elif status == "request_error":
            issue_reason_items.append({
                "taskId": task_id,
                "category": "api_or_infrastructure",
                "code": str(turn.get("error_type") or "request-error"),
                "message": str(turn.get("error") or "model request failed"),
            })
        elif status == "tool_failed" and tool != "submit_card_jsx":
            item = {
                "taskId": task_id,
                "category": "model_protocol",
                "code": "unexpected-tool-call",
                "message": str(result.get("error") or "tool call failed"),
            }
            if has_later_turn:
                retry_reason_items.append(item)
            issue_reason_items.append(item)

    explicit_rejections = trace.get("failed_submissions")
    explicit_repairs = trace.get("repair_calls")
    explicit_argument_repairs = trace.get("tool_argument_repairs")
    explicit_protocol_retries = trace.get("protocol_retries")
    rejected_submissions = int(explicit_rejections) if isinstance(explicit_rejections, int) else rejected_submissions
    repair_calls = int(explicit_repairs) if isinstance(explicit_repairs, int) else inferred_repair_calls
    tool_argument_repairs = (
        int(explicit_argument_repairs)
        if isinstance(explicit_argument_repairs, int)
        else inferred_tool_argument_repairs
    )
    protocol_retries = (
        int(explicit_protocol_retries)
        if isinstance(explicit_protocol_retries, int)
        else inferred_protocol_retries
    )
    if accepted_submissions == 0 and str(trace.get("status")) not in {"failed", "running", ""}:
        accepted_submissions = 1
    elapsed = _number(trace.get("elapsed_seconds"))
    api_seconds = sum(_number(turn.get("api_elapsed_seconds")) for turn in turns if isinstance(turn, dict))
    usage = Counter()
    for turn in turns:
        if not isinstance(turn, dict) or not isinstance(turn.get("usage"), dict):
            continue
        for field in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            usage[field] += int(_number(turn["usage"].get(field)))
    warnings = trace.get("warnings") if isinstance(trace.get("warnings"), list) else []
    validation_reports = trace.get("validation_reports") if isinstance(trace.get("validation_reports"), list) else []
    browser_failed = sum(1 for report in validation_reports if isinstance(report, dict) and not report.get("ok"))
    task = {
        "taskId": task_id,
        "componentName": trace.get("component_name"),
        "status": trace.get("status"),
        "elapsedSeconds": _rounded(elapsed),
        "modelCalls": len(turns),
        "modelApiSeconds": _rounded(api_seconds),
        "submissionFailures": rejected_submissions,
        "validatedSubmissions": 0 if validation_mode == "disabled" else rejected_submissions + accepted_submissions,
        "acceptedSubmissions": accepted_submissions,
        "rejectedSubmissions": 0 if validation_mode == "disabled" else rejected_submissions,
        "conversionFailures": conversion_failures,
        "repairCalls": repair_calls,
        "toolArgumentRepairs": tool_argument_repairs,
        "protocolRetries": protocol_retries,
        "firstPass": (
            rejected_submissions == 0
            and protocol_retries == 0
            and str(trace.get("status")) != "failed"
        ),
        "warningCount": len(warnings),
        "browserValidationReports": len(validation_reports),
        "browserValidationFailures": browser_failed,
        "reasonCodes": sorted({item["code"] for item in issue_reason_items}),
        "tokens": dict(usage),
    }
    if trace.get("error"):
        failure_item = {
            "taskId": task_id,
            "category": "terminal_failure",
            "code": str(trace.get("error_type") or "task-failed"),
            "message": str(trace.get("error")),
        }
        issue_reason_items.append(failure_item)
        task["reasonCodes"] = sorted({*task["reasonCodes"], failure_item["code"]})
    return task, retry_reason_items, issue_reason_items


def build_run_summary(manifest: dict[str, Any], traces: list[dict[str, Any]]) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    retry_items: list[dict[str, Any]] = []
    issue_items: list[dict[str, Any]] = []
    validation_mode = str(manifest.get("validationMode") or "unknown")
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        task, task_retries, task_issues = _task_metrics(trace, validation_mode)
        task_rows.append(task)
        retry_items.extend(task_retries)
        issue_items.extend(task_issues)

    attempted = int(manifest.get("attemptedTasks") or len(task_rows))
    produced = len(manifest.get("cards") or [])
    failed = int(manifest.get("failedTasks") or 0)
    completed = int(manifest.get("completedTasks") or 0)
    partial = int(manifest.get("partialTasks") or 0)
    insufficient = int(manifest.get("insufficientInputTasks") or 0)
    task_times = [row["elapsedSeconds"] for row in task_rows]
    success_times = [row["elapsedSeconds"] for row in task_rows if row["status"] != "failed"]
    failure_times = [row["elapsedSeconds"] for row in task_rows if row["status"] == "failed"]
    total_calls = sum(row["modelCalls"] for row in task_rows)
    total_api_seconds = sum(row["modelApiSeconds"] for row in task_rows)
    total_submission_failures = sum(row["submissionFailures"] for row in task_rows)
    total_validated_submissions = sum(row["validatedSubmissions"] for row in task_rows)
    total_accepted_submissions = sum(row["acceptedSubmissions"] for row in task_rows)
    total_rejections = sum(row["rejectedSubmissions"] for row in task_rows)
    total_conversion_failures = sum(row["conversionFailures"] for row in task_rows)
    total_repairs = sum(row["repairCalls"] for row in task_rows)
    total_argument_repairs = sum(row["toolArgumentRepairs"] for row in task_rows)
    total_protocol_retries = sum(row["protocolRetries"] for row in task_rows)
    repaired_tasks = sum(1 for row in task_rows if row["repairCalls"] > 0 and row["status"] != "failed")
    first_pass_tasks = sum(1 for row in task_rows if row["firstPass"])
    repair_distribution = Counter(str(row["repairCalls"]) for row in task_rows)
    token_totals = Counter()
    for row in task_rows:
        token_totals.update(row["tokens"])

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(),
        "run": {
            "runId": manifest.get("runId"),
            "status": manifest.get("status"),
            "model": manifest.get("model"),
            "provider": manifest.get("provider"),
            "thinkingMode": manifest.get("thinkingMode"),
            "validationMode": manifest.get("validationMode"),
            "layoutBudgetValidationEnabled": manifest.get(
                "layoutBudgetValidationEnabled"
            ),
            "browserValidationEnabled": manifest.get("browserValidationEnabled"),
            "input": manifest.get("input"),
            "startedAt": manifest.get("startedAt"),
            "finishedAt": manifest.get("finishedAt"),
        },
        "outcome": {
            "requestedTasks": int(manifest.get("requestedTasks") or 0),
            "attemptedTasks": attempted,
            "producedTasks": produced,
            "completedTasks": completed,
            "partialTasks": partial,
            "insufficientInputTasks": insufficient,
            "failedTasks": failed,
            "unverifiedTasks": int(manifest.get("unverifiedTasks") or 0),
            "producedRatePercent": _rate(produced, attempted),
            "firstPassTasks": first_pass_tasks,
            "firstPassRatePercent": _rate(first_pass_tasks, produced),
        },
        "timing": {
            "runElapsedSeconds": _rounded(_number(manifest.get("elapsedSeconds"))),
            "taskElapsedTotalSeconds": _rounded(sum(task_times)),
            "averagePerAttemptedTaskSeconds": _average(task_times),
            "averageSuccessfulTaskSeconds": _average(success_times),
            "averageFailedTaskSeconds": _average(failure_times),
            "minTaskSeconds": _rounded(min(task_times)) if task_times else 0.0,
            "maxTaskSeconds": _rounded(max(task_times)) if task_times else 0.0,
            "p50TaskSeconds": _percentile(task_times, 0.50),
            "p90TaskSeconds": _percentile(task_times, 0.90),
            "modelApiTotalSeconds": _rounded(total_api_seconds),
            "averageModelCallSeconds": _rounded(total_api_seconds / total_calls) if total_calls else 0.0,
        },
        "modelUsage": {
            "modelCalls": total_calls,
            "averageCallsPerAttemptedTask": _rounded(total_calls / attempted) if attempted else 0.0,
            "tokens": dict(token_totals),
            "averageTokensPerAttemptedTask": {
                key: _rounded(value / attempted) if attempted else 0.0
                for key, value in token_totals.items()
            },
        },
        "validationAndRetry": {
            "validationMode": validation_mode,
            "submittedJsx": total_submission_failures + total_accepted_submissions,
            "validatedSubmissions": total_validated_submissions,
            "acceptedSubmissions": total_accepted_submissions,
            "validationPassRatePercent": _rate(total_accepted_submissions, total_validated_submissions),
            "submissionFailures": total_submission_failures,
            "rejectedSubmissions": total_rejections,
            "conversionFailures": total_conversion_failures,
            "repairCalls": total_repairs,
            "toolArgumentRepairs": total_argument_repairs,
            "protocolRetries": total_protocol_retries,
            "repairedTasks": repaired_tasks,
            "tasksWithToolArgumentRepairs": sum(
                1 for row in task_rows if row["toolArgumentRepairs"] > 0
            ),
            "tasksWithProtocolRetries": sum(
                1 for row in task_rows if row["protocolRetries"] > 0
            ),
            "tasksWithSubmissionFailures": sum(1 for row in task_rows if row["submissionFailures"] > 0),
            "tasksWithRejectedSubmissions": sum(1 for row in task_rows if row["rejectedSubmissions"] > 0),
            "averageRepairCallsPerAttemptedTask": _rounded(total_repairs / attempted) if attempted else 0.0,
            "maxRepairCallsPerTask": max((row["repairCalls"] for row in task_rows), default=0),
            "repairCallDistribution": dict(sorted(repair_distribution.items(), key=lambda item: int(item[0]))),
            "warningCount": sum(row["warningCount"] for row in task_rows),
            "browserValidationReports": sum(row["browserValidationReports"] for row in task_rows),
            "browserValidationFailures": sum(row["browserValidationFailures"] for row in task_rows),
            "retryReasons": _aggregate_reasons(retry_items),
            "allIssueReasons": _aggregate_reasons(issue_items),
        },
        "tasks": task_rows,
    }


def _markdown_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_run_summary_markdown(summary: dict[str, Any]) -> str:
    run = summary["run"]
    outcome = summary["outcome"]
    timing = summary["timing"]
    usage = summary["modelUsage"]
    validation = summary["validationAndRetry"]
    lines = [
        "# Run Summary",
        "",
        f"- Run ID: `{run.get('runId')}`",
        f"- Status: `{run.get('status')}`",
        f"- Model: `{run.get('provider')}/{run.get('model')}`",
        f"- Validation: `{run.get('validationMode')}`",
        f"- Python layout budget: `{_enabled_state(run.get('layoutBudgetValidationEnabled'))}`",
        f"- Browser validation: `{_enabled_state(run.get('browserValidationEnabled'))}`",
        f"- Input: `{run.get('input')}`",
        "",
        "## Outcome",
        "",
        "| Requested | Attempted | Produced | Completed | Partial | Insufficient | Failed | First pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {outcome['requestedTasks']} | {outcome['attemptedTasks']} | {outcome['producedTasks']} | "
            f"{outcome['completedTasks']} | {outcome['partialTasks']} | {outcome['insufficientInputTasks']} | "
            f"{outcome['failedTasks']} | {outcome['firstPassTasks']} ({outcome['firstPassRatePercent']}%) |"
        ),
        "",
        "## Timing and model usage",
        "",
        f"- Run elapsed: **{timing['runElapsedSeconds']}s**",
        f"- Average per attempted task: **{timing['averagePerAttemptedTaskSeconds']}s**",
        f"- P50 / P90 / max: **{timing['p50TaskSeconds']}s / {timing['p90TaskSeconds']}s / {timing['maxTaskSeconds']}s**",
        f"- Model calls: **{usage['modelCalls']}**, average **{usage['averageCallsPerAttemptedTask']}** per attempted task",
        f"- Model API time: **{timing['modelApiTotalSeconds']}s**, average **{timing['averageModelCallSeconds']}s** per call",
        f"- Tokens: `{usage['tokens']}`",
        "",
        "## Validation and retry",
        "",
        f"- Rejected submissions: **{validation['rejectedSubmissions']}**",
        f"- Submission failures: **{validation['submissionFailures']}**",
        f"- Validated / accepted submissions: **{validation['validatedSubmissions']} / {validation['acceptedSubmissions']}**",
        f"- Conversion failures: **{validation['conversionFailures']}**",
        f"- Repair calls: **{validation['repairCalls']}**",
        f"- Local tool-argument repairs: **{validation['toolArgumentRepairs']}**",
        f"- Tool-protocol retries: **{validation['protocolRetries']}**",
        f"- Repaired tasks: **{validation['repairedTasks']}**",
        f"- Repair distribution: `{validation['repairCallDistribution']}`",
        f"- Warnings: **{validation['warningCount']}**",
        "",
        "### Retry reasons",
        "",
        "| Category | Code | Occurrences | Tasks | Example |",
        "|---|---|---:|---:|---|",
    ]
    reasons = validation["retryReasons"]
    if reasons:
        for reason in reasons:
            example = reason["sampleMessages"][0] if reason["sampleMessages"] else ""
            lines.append(
                f"| {_markdown_cell(reason['category'])} | {_markdown_cell(reason['code'])} | "
                f"{reason['occurrenceCount']} | {reason['affectedTaskCount']} | {_markdown_cell(example)} |"
            )
    else:
        lines.append("| — | — | 0 | 0 | No retry-triggering issue |")
    lines.extend([
        "",
        "## Per task",
        "",
        "| Task | Component | Status | Elapsed | Calls | Submit failures | Repairs | Arg repairs | Protocol retries | Reasons |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for task in summary["tasks"]:
        lines.append(
            f"| {_markdown_cell(task['taskId'])} | {_markdown_cell(task['componentName'])} | "
            f"{_markdown_cell(task['status'])} | {task['elapsedSeconds']}s | {task['modelCalls']} | "
            f"{task['submissionFailures']} | {task['repairCalls']} | "
            f"{task['toolArgumentRepairs']} | {task['protocolRetries']} | "
            f"{_markdown_cell(', '.join(task['reasonCodes']))} |"
        )
    return "\n".join(lines) + "\n"


def terminal_summary_lines(summary: dict[str, Any]) -> list[str]:
    outcome = summary["outcome"]
    timing = summary["timing"]
    validation = summary["validationAndRetry"]
    top_reasons = ", ".join(
        f"{item['code']}={item['occurrenceCount']}"
        for item in validation["retryReasons"][:3]
    ) or "none"
    return [
        (
            f"[Summary] attempted={outcome['attemptedTasks']}, produced={outcome['producedTasks']}, "
            f"partial={outcome['partialTasks']}, failed={outcome['failedTasks']}"
        ),
        (
            f"[Summary] avg={timing['averagePerAttemptedTaskSeconds']}s, "
            f"p50={timing['p50TaskSeconds']}s, p90={timing['p90TaskSeconds']}s"
        ),
        (
            f"[Summary] first-pass={outcome['firstPassRatePercent']}%, "
            f"submit-failures={validation['submissionFailures']}, "
            f"rejected={validation['rejectedSubmissions']}, repair-calls={validation['repairCalls']}, "
            f"arg-repairs={validation['toolArgumentRepairs']}, protocol-retries={validation['protocolRetries']}"
        ),
        f"[Summary] top retry reasons: {top_reasons}",
    ]
