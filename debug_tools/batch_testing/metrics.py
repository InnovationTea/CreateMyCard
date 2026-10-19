"""从原始批跑证据统计首稿、修复和交付指标，不改写历史结果。"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
_TERMINAL = frozenset({"success", "degraded", "failed", "unsupported"})
_DELIVERED = frozenset({"success", "degraded"})
RETRY_CONFIG_FIELDS = {
    "enableCompactDslInterfaceRetry": "interfaceRetryEnabled",
    "compactDslInterfaceRetryCount": "interfaceExtraRetries",
    "enableValidationFailureRetry": "qualityRepairEnabled",
    "validationFailureMaxRepairAttempts": "qualityRepairMaxAttempts",
    "enableModelFailureRetry": "modelFailureRetryEnabled",
    "modelFailureMaxRetryAttempts": "modelFailureExtraRetries",
    "fallbackModelFailureMaxRetryAttempts": "fallbackModelFailureExtraRetries",
    "enableOpenaiFallback": "fallbackEnabled",
    "enableCompactDslArgumentRepairFallback": "argumentRepairEnabled",
    "compactDslArgumentRepairMaxAttempts": "argumentRepairMaxAttempts",
    "compactDslArgumentRepairReminderCount": "argumentRepairReminderCount",
}
_RETRY_FIELDS = frozenset(RETRY_CONFIG_FIELDS.values()) | {
    "interfaceMaxAttempts",
    "planMaxAttempts",
}


def _retry_value(name: str, value: Any) -> bool:
    if name.endswith("Enabled"):
        return isinstance(value, bool)
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    minimum = 1 if name.endswith("MaxAttempts") else 0
    return value >= minimum


def retry_config_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for source, target in RETRY_CONFIG_FIELDS.items():
        canonical = re.sub(r"(?<!^)(?=[A-Z])", "_", source).lower()
        value = config.get(canonical, config.get(source))
        if _retry_value(target, value):
            snapshot[target] = value
    return snapshot


def _merge_retry_parameters(target: dict[str, list], source: dict[str, list]) -> None:
    for name, values in source.items():
        if name not in _RETRY_FIELDS or not isinstance(values, list):
            continue
        accepted = target.setdefault(name, [])
        for value in values:
            if _retry_value(name, value) and value not in accepted:
                accepted.append(value)


def _signature(path: Path) -> tuple[int, int] | None:
    signature = None
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError as exc:
        _LOGGER.debug("批跑指标证据不可读 %s: %s", path, exc)
    return signature


@lru_cache(maxsize=1024)
def _read_json(path: Path, signature: tuple[int, int]) -> dict[str, Any] | None:
    result = None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            result = value
    except (OSError, ValueError) as exc:
        _LOGGER.warning("批跑指标 JSON 读取失败 %s: %s", path, exc)
    return result


def _json_file(path: Path) -> dict[str, Any] | None:
    signature = _signature(path)
    return _read_json(path, signature) if signature is not None else None


@dataclass
class TraceEvidence:
    first_dsl: str = "unknown"
    terminal: bool = False
    repairs: int | None = None
    model_calls: int | None = None
    accepted_plan: dict[str, Any] | None = None
    coverage: dict[str, Any] | None = None
    retry_parameters: dict[str, list] = field(default_factory=dict)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


@lru_cache(maxsize=512)
def _read_trace(path: Path, signature: tuple[int, int]) -> TraceEvidence:
    evidence = TraceEvidence()
    try:
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Trace 记录不是对象")
                name = event.get("event")
                details = event.get("details")
                if isinstance(details, dict):
                    parameters: dict[str, list] = {}
                    if name == "retry.policy.configured":
                        for key, value in details.items():
                            if key in _RETRY_FIELDS and _retry_value(key, value):
                                parameters[key] = [value]
                    if name in {"interface.attempt.started", "plan.attempt"}:
                        key = (
                            "planMaxAttempts" if name == "plan.attempt" else "interfaceMaxAttempts"
                        )
                        value = details.get("maxAttempts")
                        if _retry_value(key, value):
                            parameters[key] = [value]
                    _merge_retry_parameters(evidence.retry_parameters, parameters)
                if name == "validation.evaluate" and evidence.first_dsl == "unknown":
                    status = event.get("status")
                    if status in {"success", "failed"}:
                        evidence.first_dsl = "passed" if status == "success" else "failed"
                if name == "dsl.plan_coverage_validation.completed":
                    artifacts = event.get("artifacts")
                    if isinstance(artifacts, dict):
                        evidence.coverage = artifacts.get("plan_coverage_result")
                if name == "plan.validation.completed" and event.get("status") == "success":
                    artifacts = event.get("artifacts")
                    if isinstance(artifacts, dict):
                        evidence.accepted_plan = artifacts.get("accepted_plan")
                if name == "request.completed":
                    evidence.terminal = True
                    details = event.get("details")
                    counts = details.get("attemptCounts") if isinstance(details, dict) else None
                    if isinstance(counts, dict):
                        # Trace v2 的计数器是稀疏映射；完整终态中未触发的计数为零。
                        evidence.repairs = _count(counts.get("qualityRepairAttempts", 0))
                        evidence.model_calls = _count(counts.get("modelPhysicalAttempts", 0))
    except (OSError, ValueError) as exc:
        _LOGGER.warning("批跑指标 Trace 读取失败 %s: %s", path, exc)
        evidence = TraceEvidence()
    return evidence


def _trace(attempt_dir: Path) -> TraceEvidence:
    path = attempt_dir / "trace" / "source" / "trace.jsonl"
    signature = _signature(path)
    return _read_trace(path, signature) if signature is not None else TraceEvidence()


@lru_cache(maxsize=1024)
def _read_coverage(
    path: Path,
    signature: tuple[int, int],
    digest: str,
    byte_count: int,
) -> dict[str, Any] | None:
    result = None
    try:
        content = path.read_bytes()
        if len(content) != byte_count or hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Trace 附件长度或摘要不匹配")
        value = json.loads(content)
        if isinstance(value, dict):
            result = value
    except (OSError, ValueError) as exc:
        _LOGGER.warning("批跑指标覆盖附件读取失败 %s: %s", path, exc)
    return result


def _verified_blob(run_dir: Path, descriptor: Any) -> dict[str, Any] | None:
    if not isinstance(descriptor, dict):
        return None
    digest = descriptor.get("sha256")
    size = _count(descriptor.get("bytes"))
    if not isinstance(digest, str) or len(digest) != 64 or size is None:
        return None
    if any(char not in "0123456789abcdef" for char in digest):
        return None
    path = run_dir / "trace_blobs" / digest
    signature = _signature(path)
    if signature is None:
        return None
    return _read_coverage(path, signature, digest, size)


def _coverage_warning_count(run_dir: Path, evidence: TraceEvidence) -> int | None:
    plan = _verified_blob(run_dir, evidence.accepted_plan)
    facts = plan.get("info_required") if plan is not None else None
    if not isinstance(facts, list) or not facts:
        return None
    payload = _verified_blob(run_dir, evidence.coverage)
    warnings = payload.get("warnings") if payload is not None else None
    errors = payload.get("errors") if payload is not None else None
    if not isinstance(warnings, list) or not isinstance(errors, list):
        return None
    missing: set[str] = set()
    prefixes = ("Plan fact is missing from visible DSL:", "Plan static text is not fully visible")
    for message in [*warnings, *errors]:
        if not isinstance(message, str):
            return None
        if message.startswith(prefixes):
            missing.add(message)
    return len(missing)


def _delivered(result: dict[str, Any]) -> bool:
    return result.get("status") in _DELIVERED and result.get("completed") is not False


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": round(numerator * 100.0 / denominator, 2) if denominator else None,
    }


@dataclass
class MetricTotals:
    terminal: int = 0
    delivered: int = 0
    first_requests: int = 0
    first_delivered: int = 0
    dsl_evaluated: int = 0
    dsl_passed: int = 0
    pre_dsl_failed: int = 0
    first_dsl_unknown: int = 0
    repair_failed: int = 0
    repair_rescued: int = 0
    retried: int = 0
    retry_terminal: int = 0
    retry_rescued: int = 0
    repairs: int = 0
    repair_observed: int = 0
    calls: int = 0
    calls_observed: int = 0
    attempt_terminal: int = 0
    coverage_observed: int = 0
    coverage_missing: int = 0
    elapsed: list[float] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        ordered = sorted(self.elapsed)
        p95 = ordered[math.ceil(len(ordered) * 0.95) - 1] if ordered else None
        return {
            "firstDslPassRate": _rate(self.dsl_passed, self.dsl_evaluated),
            "firstRequestDeliveryRate": _rate(self.first_delivered, self.first_requests),
            "finalDeliveryRate": _rate(self.delivered, self.terminal),
            "preDslFailed": self.pre_dsl_failed,
            "firstDslUnknown": self.first_dsl_unknown,
            "repairRescueRate": _rate(self.repair_rescued, self.repair_failed),
            "batchRetryRate": _rate(self.retried, self.first_requests),
            "batchRetryRescueRate": _rate(self.retry_rescued, self.retry_terminal),
            "qualityRepairAttempts": self.repairs if self.repair_observed else None,
            "modelPhysicalCalls": self.calls if self.calls_observed else None,
            "repairObservedAttempts": self.repair_observed,
            "modelObservedAttempts": self.calls_observed,
            "terminalAttempts": self.attempt_terminal,
            "coverageObserved": self.coverage_observed,
            "coverageMissing": self.coverage_missing,
            "p95ElapsedMs": round(p95, 2) if p95 is not None else None,
        }


def _sample_metrics(run_dir: Path, sample: dict[str, Any]) -> dict[str, Any]:
    sample_id = sample.get("id")
    if not isinstance(sample_id, str):
        return {}
    sample_dir = (run_dir / sample_id).resolve()
    if sample_dir.parent != run_dir.resolve():
        return {}
    first_result = _json_file(sample_dir / "attempt_000" / "result.json") or {}
    first_request = _json_file(sample_dir / "attempt_000" / "request.json") or {}
    content = first_request.get("content")
    request_size = content.get("size") if isinstance(content, dict) else None
    first_trace = _trace(sample_dir / "attempt_000")
    first_status = first_result.get("status")
    first_dsl = first_trace.first_dsl
    if (
        first_dsl == "unknown"
        and first_trace.terminal
        and first_status in {"failed", "unsupported"}
    ):
        first_dsl = "before_dsl_failure"
    repairs = 0
    calls = 0
    repair_observed = 0
    calls_observed = 0
    terminal_attempts = 0
    final_trace = TraceEvidence()
    retry_parameters: dict[str, list] = {}
    for attempt_dir in sorted(sample_dir.glob("attempt_*")):
        evidence = _trace(attempt_dir)
        _merge_retry_parameters(retry_parameters, evidence.retry_parameters)
        result = _json_file(attempt_dir / "result.json") or {}
        if result.get("status") not in _TERMINAL:
            continue
        terminal_attempts += 1
        final_trace = evidence
        if evidence.repairs is not None:
            repairs += evidence.repairs
            repair_observed += 1
        if evidence.model_calls is not None:
            calls += evidence.model_calls
            calls_observed += 1
    missing = None
    if sample.get("status") in _DELIVERED:
        missing = _coverage_warning_count(run_dir, final_trace)
    return {
        "firstDsl": first_dsl,
        "requestSize": request_size if isinstance(request_size, str) else sample.get("size"),
        "firstRequestStatus": first_status if first_status in _TERMINAL else None,
        "firstRequestDelivered": _delivered(first_result),
        "qualityRepairAttempts": repairs if repair_observed else None,
        "modelPhysicalCalls": calls if calls_observed else None,
        "repairObservedAttempts": repair_observed,
        "modelObservedAttempts": calls_observed,
        "terminalAttempts": terminal_attempts,
        "missingInformationWarnings": missing,
        "retryParameters": retry_parameters,
    }


def _accumulate(totals: MetricTotals, sample: dict[str, Any], evidence: dict[str, Any]) -> None:
    status = sample.get("status")
    delivered = status in _DELIVERED
    terminal = status in _TERMINAL
    first_known = evidence.get("firstRequestStatus") in _TERMINAL
    if terminal:
        totals.terminal += 1
        totals.delivered += int(delivered)
        elapsed = sample.get("elapsedMs")
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
            if math.isfinite(elapsed) and elapsed >= 0:
                totals.elapsed.append(float(elapsed))
    if first_known:
        totals.first_requests += 1
        totals.first_delivered += int(evidence.get("firstRequestDelivered") is True)
    first_dsl = evidence.get("firstDsl")
    if first_dsl in {"passed", "failed"}:
        totals.dsl_evaluated += 1
        totals.dsl_passed += int(first_dsl == "passed")
    elif first_dsl == "before_dsl_failure":
        totals.pre_dsl_failed += 1
    elif first_known or terminal:
        totals.first_dsl_unknown += 1
    if first_dsl == "failed" and first_known:
        totals.repair_failed += 1
        totals.repair_rescued += int(evidence.get("firstRequestDelivered") is True)
    attempts = _count(sample.get("attemptCount"))
    if attempts is not None and attempts > 1 and first_known:
        totals.retried += 1
        if terminal:
            totals.retry_terminal += 1
            totals.retry_rescued += int(delivered)
    totals.attempt_terminal += evidence.get("terminalAttempts", 0)
    totals.repairs += evidence.get("qualityRepairAttempts") or 0
    totals.calls += evidence.get("modelPhysicalCalls") or 0
    totals.repair_observed += evidence.get("repairObservedAttempts", 0)
    totals.calls_observed += evidence.get("modelObservedAttempts", 0)
    missing = evidence.get("missingInformationWarnings")
    if missing is not None:
        totals.coverage_observed += 1
        totals.coverage_missing += int(missing > 0)


def enrich_run_metrics(summary: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """按有效证据计算指标；历史批次只在返回值补充，不覆盖原始文件。"""
    enriched = dict(summary)
    totals = MetricTotals()
    groups: dict[str, MetricTotals] = {}
    samples: list[dict[str, Any]] = []
    retry_parameters: dict[str, list] = {}
    raw_samples = summary.get("samples")
    if not isinstance(raw_samples, list):
        raw_samples = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, dict):
            continue
        sample = dict(raw_sample)
        evidence = _sample_metrics(run_dir, sample)
        _merge_retry_parameters(retry_parameters, evidence.get("retryParameters", {}))
        sample["generationMetrics"] = evidence
        samples.append(sample)
        _accumulate(totals, sample, evidence)
        size = str(evidence.get("requestSize") or "unknown")
        if size not in groups:
            groups[size] = MetricTotals()
        group = groups.get(size)
        if group is not None:
            _accumulate(group, sample, evidence)
    enriched["samples"] = samples
    by_size = []
    for size, group in sorted(groups.items()):
        by_size.append({"size": size, **group.public_dict()})
    enriched["generationMetrics"] = {"version": 1, **totals.public_dict(), "bySize": by_size}
    enriched["observedRetryParameters"] = retry_parameters
    return enriched
