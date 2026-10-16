"""统一分析的业务口径与产物识别回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from debug_tools.postprocess_plugins.data_analysis.metrics import aggregate, analyze_request
from debug_tools.postprocess_plugins.data_analysis.plugin import process_sample
from debug_tools.postprocess_plugins.data_analysis.usage import analyze_usage


def _view(statuses: list[str], complete: bool = True) -> dict:
    nodes = []
    for index, status in enumerate(statuses, start=1):
        nodes.append(
            {
                "operation": "interface.attempt",
                "attempts": {"interface": index},
                "status": status,
            }
        )
    return {
        "status": "complete" if complete else "partial",
        "timingMode": "exact",
        "summary": {"retryCounts": {"interfaceRetries": max(len(statuses) - 1, 0)}},
        "nodes": nodes,
    }


@pytest.mark.parametrize(
    ("statuses", "first", "second", "weight"),
    [
        (["success"], True, True, 2),
        (["failed", "success"], False, True, 1),
        (["failed", "failed"], False, False, 1),
        (["failed", "failed", "success"], False, False, 1),
        (["degraded"], False, False, 1),
        (["unsupported"], False, False, 1),
        ([], None, None, 1),
    ],
)
def test_pass_uses_interface_attempt_status(statuses, first, second, weight):
    result = analyze_request(_view(statuses), {}, "attempt_000")
    assert result.get("pass1") is first
    assert result.get("pass2") is second
    assert result.get("weight") == weight


def test_partial_trace_does_not_invent_second_attempt_or_zero_counts():
    result = analyze_request(_view(["failed"], complete=False), {}, "attempt_000")
    assert result.get("pass1") is False
    assert result.get("pass2") is None
    assert result.get("counts", {}).get("modelRetries") is None
    assert result.get("phasesMs", {}).get("repair") is None


def test_duplicate_trace_weights_means_but_not_pass_denominator():
    one = analyze_request(_view(["success"]), {"elapsedMs": 10}, "attempt_000")
    two = analyze_request(_view(["failed", "success"]), {"elapsedMs": 40}, "attempt_001")
    result = aggregate([{"requests": [one, two]}])
    assert result.get("requestCount") == 2
    assert result.get("paddedCount") == 1
    assert result.get("effectiveCount") == 3
    assert result.get("pass1", {}).get("rate") == 0.5
    assert result.get("pass2", {}).get("rate") == 1.0
    assert result.get("elapsedMs", {}).get("mean") == 20.0
    assert result.get("interfaceRetries", {}).get("mean") == pytest.approx(1 / 3)


def test_phase_intervals_merge_and_root_elapsed_wins():
    view = _view(["success"])
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    nodes.extend(
        [
            {"operation": "request", "durationMs": 100},
            {"operation": "plan", "startOffsetMs": 0, "durationMs": 20},
            {"operation": "plan", "startOffsetMs": 5, "durationMs": 5},
            {"operation": "plan", "startOffsetMs": 40, "durationMs": 10},
            {"operation": "dsl", "startOffsetMs": 55, "durationMs": 25},
            {"operation": "repair.attempt"},
        ]
    )
    result = analyze_request(view, {"elapsedMs": 999}, "attempt_000")
    assert result.get("elapsedMs") == 100
    assert result.get("elapsedSource") == "trace.request"
    assert result.get("phasesMs") == {"plan": 30.0, "generate": 25.0, "repair": 0.0}
    assert result.get("counts", {}).get("repairs") == 1


def test_model_metrics_count_physical_calls_once_and_keep_unknown():
    view = _view(["success"])
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    nodes.extend(
        [
            {
                "operation": "model.physical_call",
                "attributes": {"phase": "initial"},
                "metrics": {
                    "firstTokenLatencyMs": 20,
                    "completionTokens": 12,
                    "inferenceDurationMs": 100,
                },
            },
            {
                "operation": "model.physical_call",
                "attributes": {"phase": "plan"},
                "metrics": {"firstTokenLatencyMs": 0, "tokensPerSecond": "30.5"},
            },
            {
                "operation": "model.physical_call",
                "metrics": {"completionTokens": 5, "inferenceDurationMs": 0},
            },
            {"operation": "model.provider_execution", "metrics": {"tokensPerSecond": 999}},
        ]
    )
    request = analyze_request(view, {}, "attempt_000")
    models = request.get("models")
    assert isinstance(models, list)
    assert len(models) == 3
    assert models[0].get("tps") == 120.0
    assert models[2].get("tps") is None
    result = aggregate([{"requests": [request]}])
    all_models = result.get("models", {}).get("all", {})
    assert all_models.get("tps", {}).get("count") == 4
    assert all_models.get("tps", {}).get("mean") == 75.25
    assert all_models.get("ttftMs", {}).get("mean") == 10
    assert result.get("models", {}).get("generate", {}).get("tps", {}).get("count") == 2


def test_retry_categories_are_independent():
    view = _view(["failed", "success"])
    view["summary"] = {
        "retryCounts": {
            "interfaceRetries": 1,
            "modelTransportRetries": 3,
            "planContractRetries": 2,
            "providerFallbacks": 4,
        }
    }
    assert analyze_request(view, {}, "attempt_000").get("counts") == {
        "interfaceRetries": 1.0,
        "repairs": 0.0,
        "modelRetries": 3.0,
        "planRetries": 2.0,
        "providerFallbacks": 4.0,
    }


def test_invalid_explicit_count_is_not_replaced_with_zero():
    view = _view(["success"])
    view["summary"] = {"retryCounts": {"modelTransportRetries": -1}}
    counts = analyze_request(view, {}, "attempt_000").get("counts", {})
    assert counts.get("modelRetries") is None
    assert counts.get("planRetries") == 0.0


def _write(path: Path, value: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_usage_deduplicates_and_ignores_unused_candidates(tmp_path):
    rows = [
        ["title", "SingleLineTitle", {"text": "标题"}],
        ["title2", "SingleLineTitle", {"text": "重复"}],
    ]
    action = {
        "call": "clickToApi",
        "args": {"intentName": "CallPhone", "params": {"phoneNumber": "123"}},
    }
    _write(
        tmp_path / "blocks.json",
        {
            "designcompactdsl": "\n".join(json.dumps(row) for row in rows),
            "genui": {
                "updateComponents": {
                    "components": [
                        {
                            "component": "Image",
                            "src": "asset.calendar_fill",
                            "onClick": [action, action],
                        },
                        {"component": "Image", "src": "resources/base/media/calendar_fill.svg"},
                    ]
                }
            },
            "cardspec": {
                "dataBindings": [{"capabilityId": "ViewWeather"}, {"capabilityId": "ViewWeather"}]
            },
            "taskspec": {
                "assetCandidates": [{"id": "asset.sun_max"}],
                "eventCandidates": [{"capabilityId": "event.unused", "action": {}}],
            },
        },
    )
    usage = analyze_usage(tmp_path)
    assert usage.get("components") == ["SingleLineTitle"]
    assert usage.get("assets") == ["asset.calendar_fill"]
    assert usage.get("events") == ["event.call.phone"]
    assert usage.get("data") == ["ViewWeather"]


def test_usage_denominator_excludes_unreadable_products():
    result = aggregate(
        [
            {"usage": {"components": ["Title", "Title"], "assets": []}},
            {"usage": {"components": [], "assets": None}},
            {"usage": {"components": None}},
        ]
    )
    components = result.get("usage", {}).get("components", {})
    assert components.get("count") == 2
    assert components.get("rate") == 0.5
    assert components.get("items") == [{"id": "Title", "count": 1, "rate": 0.5}]
    assert result.get("usage", {}).get("assets", {}).get("count") == 1


def test_usage_does_not_count_unrendered_model_values(tmp_path):
    _write(
        tmp_path / "blocks.json",
        {
            "genui": [
                {"updateComponents": {"components": []}},
                {
                    "updateDataModel": {
                        "value": {
                            "src": "asset.calendar_fill",
                            "onClick": [
                                {"call": "clickToApi", "args": {"intentName": "CallPhone"}},
                            ],
                        }
                    }
                },
            ],
            "cardspec": {"dataBindings": []},
        },
    )
    usage = analyze_usage(tmp_path)
    assert usage.get("assets") == []
    assert usage.get("events") == []


def test_invalid_render_document_is_unknown_instead_of_unused(tmp_path):
    _write(tmp_path / "blocks.json", {"genui": "{}", "cardspec": ["invalid"]})
    usage = analyze_usage(tmp_path)
    assert usage.get("assets") is None
    assert usage.get("events") is None
    assert usage.get("data") is None


def test_sample_reads_all_requests_and_survives_broken_trace(tmp_path):
    _write(tmp_path / "attempt_000" / "result.json", {"elapsedMs": 10})
    _write(tmp_path / "attempt_000" / "trace/view.json", _view(["success"]))
    _write(tmp_path / "attempt_001" / "result.json", {"elapsedMs": 50})
    _write(tmp_path / "attempt_001" / "trace/view.json", [])
    result = process_sample({"sample": {"id": "Q001"}, "sampleDir": str(tmp_path)})
    assert result.get("status") == "partial"
    facts = result.get("facts", {})
    assert facts.get("requestCount") == 2
    assert facts.get("paddedCount") == 1
    artifacts = result.get("artifacts")
    assert isinstance(artifacts, list)
    analysis = artifacts[0].get("data", {})
    requests = analysis.get("requests")
    assert isinstance(requests, list)
    assert requests[1].get("elapsedSource") == "result.elapsedMs"


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        "bad",
        [],
        {
            "status": "invalid",
            "nodes": [
                {
                    "operation": "interface.attempt",
                    "attempts": {"interface": 1},
                    "status": "success",
                }
            ],
        },
    ],
)
def test_missing_trace_never_infers_first_success_from_saved_result(value):
    view = value if isinstance(value, dict) else {}
    result = analyze_request(view, {"status": "success"}, "attempt_000")
    assert result.get("pass1") is None
    assert result.get("pass2") is None
    assert result.get("weight") == 1
