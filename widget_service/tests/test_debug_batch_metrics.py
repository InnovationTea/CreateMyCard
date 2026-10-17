"""验证首稿、首次请求、重跑与完整性分开统计，历史证据缺失不补零。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing.metrics import enrich_run_metrics, retry_config_snapshot
from debug_tools.batch_testing.runner import BatchRunManager


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _attempt(
    root: Path,
    sample_id: str,
    number: int = 0,
    *,
    status: str = "success",
    evaluations: tuple[str, ...] = ("success",),
    repairs: int = 0,
    calls: int = 3,
    coverage: dict | None = None,
) -> None:
    attempt_dir = root / sample_id / f"attempt_{number:03d}"
    _write_json(attempt_dir / "result.json", {"status": status})
    events = []
    for evaluation in evaluations:
        events.append({"event": "validation.evaluate", "status": evaluation})
    if coverage is not None:
        content = json.dumps(coverage).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        (root / "trace_blobs").mkdir(exist_ok=True)
        (root / "trace_blobs" / digest).write_bytes(content)
        events.append(
            {
                "event": "dsl.plan_coverage_validation.completed",
                "artifacts": {"plan_coverage_result": {"sha256": digest, "bytes": len(content)}},
            }
        )
        plan_content = json.dumps({"info_required": [{"text": "说明"}]}).encode("utf-8")
        plan_digest = hashlib.sha256(plan_content).hexdigest()
        (root / "trace_blobs" / plan_digest).write_bytes(plan_content)
        events.append(
            {
                "event": "plan.validation.completed",
                "status": "success",
                "artifacts": {"accepted_plan": {"sha256": plan_digest, "bytes": len(plan_content)}},
            }
        )
    events.append(
        {
            "event": "request.completed",
            "details": {
                "attemptCounts": {
                    "qualityRepairAttempts": repairs,
                    "modelPhysicalAttempts": calls,
                }
            },
        }
    )
    trace = attempt_dir / "trace/source/trace.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")


def _sample(sample_id: str, *, status: str = "success", attempts: int = 1) -> dict:
    return {
        "id": sample_id,
        "status": status,
        "attemptCount": attempts,
        "size": "2x2",
        "elapsedMs": 100.0,
    }


def _metrics(summary: dict) -> dict:
    metrics = summary.get("generationMetrics")
    assert isinstance(metrics, dict)
    return metrics


def test_metrics_distinguish_first_draft_internal_repair_and_batch_retry(tmp_path):
    _attempt(tmp_path, "A")
    _attempt(tmp_path, "B", evaluations=("failed", "success"), repairs=1, calls=4)
    _attempt(tmp_path, "C", status="failed", evaluations=("failed", "failed"), repairs=1)
    _attempt(tmp_path, "C", 1)
    _attempt(tmp_path, "D", status="failed", evaluations=(), calls=1)
    samples = [
        _sample("A"),
        _sample("B"),
        _sample("C", attempts=2),
        _sample("D", status="failed"),
        _sample("E", status="cancelled", attempts=0),
    ]
    source = {"samples": samples}
    metrics = _metrics(enrich_run_metrics(source, tmp_path))

    assert metrics.get("firstDslPassRate") == {"numerator": 1, "denominator": 3, "percent": 33.33}
    assert metrics.get("firstRequestDeliveryRate") == {
        "numerator": 2,
        "denominator": 4,
        "percent": 50.0,
    }
    assert metrics.get("finalDeliveryRate") == {"numerator": 3, "denominator": 4, "percent": 75.0}
    assert metrics.get("repairRescueRate") == {"numerator": 1, "denominator": 2, "percent": 50.0}
    assert metrics.get("batchRetryRate") == {"numerator": 1, "denominator": 4, "percent": 25.0}
    assert metrics.get("batchRetryRescueRate") == {
        "numerator": 1,
        "denominator": 1,
        "percent": 100.0,
    }
    assert metrics.get("preDslFailed") == 1
    assert metrics.get("qualityRepairAttempts") == 2
    assert metrics.get("modelPhysicalCalls") == 14
    assert metrics.get("terminalAttempts") == 5
    assert all("generationMetrics" not in sample for sample in samples)


def test_missing_trace_is_unknown_and_history_is_not_written(tmp_path):
    _write_json(tmp_path / "A/attempt_000/result.json", {"status": "failed"})
    summary_path = tmp_path / "summary.json"
    _write_json(summary_path, {"samples": [_sample("A", status="failed"), _sample("B")]})
    original = summary_path.read_bytes()
    metrics = _metrics(enrich_run_metrics(json.loads(original), tmp_path))

    assert metrics.get("firstDslPassRate") == {"numerator": 0, "denominator": 0, "percent": None}
    assert metrics.get("firstDslUnknown") == 2
    assert metrics.get("preDslFailed") == 0
    assert metrics.get("qualityRepairAttempts") is None
    assert metrics.get("modelPhysicalCalls") is None
    assert summary_path.read_bytes() == original


def test_manager_enriches_existing_runs_without_requiring_a_rerun(tmp_path):
    output = tmp_path / "output"
    run_dir = output / "batch_history"
    _attempt(run_dir, "A")
    summary_path = run_dir / "summary.json"
    _write_json(summary_path, {"runId": "batch_history", "samples": [_sample("A")]})
    original = summary_path.read_bytes()
    manager = BatchRunManager(tmp_path / "dataset", output, tmp_path / "traces", tmp_path / "cloud")
    result = manager.get_run("batch_history")
    assert _metrics(result).get("firstDslPassRate", {}).get("percent") == 100.0
    assert summary_path.read_bytes() == original


def test_final_coverage_is_checked_only_for_delivered_samples(tmp_path):
    warnings = [
        "Plan fact is missing from visible DSL: 温度 (/data/temperature).",
        "Plan static text is not fully visible in DSL: 说明.",
    ]
    _attempt(tmp_path, "A", coverage={"errors": [], "warnings": warnings})
    _attempt(tmp_path, "B", coverage={"errors": [], "warnings": []})
    _attempt(tmp_path, "C", status="failed", coverage={"errors": [], "warnings": warnings})
    result = enrich_run_metrics(
        {"samples": [_sample("A"), _sample("B"), _sample("C", status="failed"), _sample("D")]},
        tmp_path,
    )
    metrics = _metrics(result)
    assert metrics.get("coverageObserved") == 2
    assert metrics.get("coverageMissing") == 1
    samples = result.get("samples")
    assert isinstance(samples, list)
    first = samples[0]
    assert first.get("generationMetrics", {}).get("missingInformationWarnings") == 2


@pytest.mark.parametrize("damage", ["missing", "digest", "invalid_json"])
def test_missing_or_corrupt_coverage_blob_never_counts_as_clean(tmp_path, damage):
    _attempt(tmp_path, "A", coverage={"errors": [], "warnings": []})
    blobs = []
    for candidate in (tmp_path / "trace_blobs").iterdir():
        if "info_required" not in candidate.read_text(encoding="utf-8"):
            blobs.append(candidate)
    assert len(blobs) == 1
    blob = blobs[0]
    if damage == "missing":
        blob.unlink()
    elif damage == "digest":
        blob.write_bytes(b"corrupt")
    else:
        content = b"not json"
        digest = hashlib.sha256(content).hexdigest()
        blob.unlink()
        (tmp_path / "trace_blobs" / digest).write_bytes(content)
        trace = tmp_path / "A/attempt_000/trace/source/trace.jsonl"
        text = trace.read_text(encoding="utf-8").replace(blob.name, digest)
        events = [json.loads(line) for line in text.splitlines()]
        for event in events:
            if event.get("event") == "dsl.plan_coverage_validation.completed":
                artifacts = event.get("artifacts")
                assert isinstance(artifacts, dict)
                descriptor = artifacts.get("plan_coverage_result")
                assert isinstance(descriptor, dict)
                descriptor["bytes"] = len(content)
        trace.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    metrics = _metrics(enrich_run_metrics({"samples": [_sample("A")]}, tmp_path))
    assert metrics.get("coverageObserved") == 0


def test_skipped_plan_does_not_count_as_a_clean_coverage_check(tmp_path):
    _attempt(tmp_path, "A", coverage={"errors": [], "warnings": []})
    trace = tmp_path / "A/attempt_000/trace/source/trace.jsonl"
    events = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("event") != "plan.validation.completed":
            events.append(event)
    trace.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    metrics = _metrics(enrich_run_metrics({"samples": [_sample("A")]}, tmp_path))
    assert metrics.get("coverageObserved") == 0


def test_running_retry_is_not_yet_a_successful_or_failed_rescue(tmp_path):
    _attempt(tmp_path, "A", status="failed", evaluations=("failed",))
    metrics = _metrics(
        enrich_run_metrics({"samples": [_sample("A", status="running", attempts=2)]}, tmp_path)
    )
    assert metrics.get("batchRetryRate", {}).get("numerator") == 1
    assert metrics.get("batchRetryRescueRate", {}).get("denominator") == 0
    assert metrics.get("finalDeliveryRate", {}).get("denominator") == 0


def test_request_size_override_and_degraded_delivery_are_explicit(tmp_path):
    _attempt(tmp_path, "A", status="degraded")
    _write_json(tmp_path / "A/attempt_000/request.json", {"content": {"size": "2x4"}})
    metrics = _metrics(enrich_run_metrics({"samples": [_sample("A", status="degraded")]}, tmp_path))
    assert metrics.get("finalDeliveryRate", {}).get("percent") == 100.0
    groups = metrics.get("bySize")
    assert isinstance(groups, list)
    assert [group.get("size") for group in groups] == ["2x4"]


def test_new_evidence_and_changed_trace_invalidate_read_cache(tmp_path):
    sample = _sample("A")
    assert (
        _metrics(enrich_run_metrics({"samples": [sample]}, tmp_path))
        .get("firstDslPassRate", {})
        .get("percent")
        is None
    )
    _attempt(tmp_path, "A")
    assert (
        _metrics(enrich_run_metrics({"samples": [sample]}, tmp_path))
        .get("firstDslPassRate", {})
        .get("percent")
        == 100.0
    )
    _attempt(tmp_path, "A", evaluations=("failed", "success"), repairs=1)
    assert (
        _metrics(enrich_run_metrics({"samples": [sample]}, tmp_path))
        .get("firstDslPassRate", {})
        .get("percent")
        == 0.0
    )


def test_p95_uses_all_batch_attempt_elapsed_and_excludes_cancelled(tmp_path):
    samples = []
    for index in range(1, 21):
        sample = _sample(f"A{index}")
        sample["elapsedMs"] = float(index * 100)
        samples.append(sample)
    cancelled = _sample("cancelled", status="cancelled")
    cancelled["elapsedMs"] = 999999.0
    samples.append(cancelled)
    metrics = _metrics(enrich_run_metrics({"samples": samples}, tmp_path))
    assert metrics.get("p95ElapsedMs") == 1900.0


def test_sparse_terminal_counters_mean_zero_but_missing_counters_are_unknown(tmp_path):
    _attempt(tmp_path, "A")
    trace = tmp_path / "A/attempt_000/trace/source/trace.jsonl"
    trace.write_text(
        json.dumps({"event": "request.completed", "details": {"attemptCounts": {}}}),
        encoding="utf-8",
    )
    metrics = _metrics(enrich_run_metrics({"samples": [_sample("A")]}, tmp_path))
    assert metrics.get("qualityRepairAttempts") == 0
    trace.write_text(json.dumps({"event": "request.completed"}), encoding="utf-8")
    metrics = _metrics(enrich_run_metrics({"samples": [_sample("A")]}, tmp_path))
    assert metrics.get("qualityRepairAttempts") is None


def _prepend_trace_events(root: Path, sample_id: str, number: int, events: list[dict]) -> None:
    trace = root / sample_id / f"attempt_{number:03d}" / "trace/source/trace.jsonl"
    original = trace.read_text(encoding="utf-8")
    trace.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n" + original, encoding="utf-8"
    )


def test_retry_parameters_use_trace_configuration_not_executed_repair_count(tmp_path):
    _attempt(tmp_path, "A", repairs=1)
    _prepend_trace_events(
        tmp_path,
        "A",
        0,
        [
            {
                "event": "retry.policy.configured",
                "details": {
                    "interfaceRetryEnabled": True,
                    "interfaceExtraRetries": 2,
                    "qualityRepairEnabled": True,
                    "qualityRepairMaxAttempts": 5,
                    "modelFailureRetryEnabled": False,
                    "apiKey": "must-not-leak",
                },
            }
        ],
    )
    result = enrich_run_metrics({"samples": [_sample("A")]}, tmp_path)
    observed = result.get("observedRetryParameters")
    assert isinstance(observed, dict)
    assert observed.get("qualityRepairMaxAttempts") == [5]
    assert observed.get("modelFailureRetryEnabled") == [False]
    assert observed.get("apiKey") is None
    assert _metrics(result).get("qualityRepairAttempts") == 1


def test_legacy_trace_exposes_explicit_budgets_but_not_unknown_limits(tmp_path):
    _attempt(tmp_path, "A", repairs=3)
    _prepend_trace_events(
        tmp_path,
        "A",
        0,
        [
            {"event": "interface.attempt.started", "details": {"maxAttempts": 1}},
            {"event": "plan.attempt", "details": {"maxAttempts": 2}},
        ],
    )
    observed = enrich_run_metrics({"samples": [_sample("A")]}, tmp_path).get(
        "observedRetryParameters"
    )
    assert observed == {"interfaceMaxAttempts": [1], "planMaxAttempts": [2]}


def test_retry_parameters_preserve_mixed_values_across_batch_attempts(tmp_path):
    _attempt(tmp_path, "A", status="failed")
    _attempt(tmp_path, "A", 1)
    for number, limit in enumerate((3, 5)):
        _prepend_trace_events(
            tmp_path,
            "A",
            number,
            [
                {
                    "event": "retry.policy.configured",
                    "details": {"qualityRepairMaxAttempts": limit},
                }
            ],
        )
    observed = enrich_run_metrics({"samples": [_sample("A", attempts=2)]}, tmp_path).get(
        "observedRetryParameters"
    )
    assert isinstance(observed, dict)
    assert observed.get("qualityRepairMaxAttempts") == [3, 5]


def test_retry_snapshot_only_accepts_whitelisted_typed_configuration():
    snapshot = retry_config_snapshot(
        {
            "enableValidationFailureRetry": True,
            "validationFailureMaxRepairAttempts": 5,
            "modelFailureMaxRetryAttempts": False,
            "compactDslInterfaceRetryCount": -1,
            "apiKey": "must-not-leak",
            "enableOpenaiFallback": "true",
        }
    )
    assert snapshot == {"qualityRepairEnabled": True, "qualityRepairMaxAttempts": 5}


def test_service_retry_policy_snapshot_reports_settings_without_changing_them():
    from types import SimpleNamespace

    from services.generation_retry_policy import retry_policy_details

    settings = SimpleNamespace(
        enable_compact_dsl_interface_retry=True,
        compact_dsl_interface_retry_count=2,
        enable_validation_failure_retry=True,
        validation_failure_max_repair_attempts=5,
        enable_model_failure_retry=False,
        model_failure_max_retry_attempts=1,
        fallback_model_failure_max_retry_attempts=1,
        enable_openai_fallback=True,
        enable_compact_dsl_argument_repair_fallback=False,
        compact_dsl_argument_repair_max_attempts=2,
        compact_dsl_argument_repair_reminder_count=1,
    )
    before = vars(settings).copy()
    policy = retry_policy_details(settings)
    assert policy.get("interfaceExtraRetries") == 2
    assert policy.get("qualityRepairMaxAttempts") == 5
    assert policy.get("modelFailureRetryEnabled") is False
    assert vars(settings) == before
