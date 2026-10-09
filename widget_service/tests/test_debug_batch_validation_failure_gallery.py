from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from debug_tools.postprocess_plugins.validation_failure_gallery import (
    ValidationFailureGalleryManager,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _blob(run_dir: Path, value: object, *, media_type: str = "application/json") -> dict:
    if isinstance(value, str):
        content = value.encode("utf-8")
    else:
        content = json.dumps(value, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    path = run_dir / "trace_blobs" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "path": f"artifacts/{digest}",
        "sha256": digest,
        "bytes": len(content),
        "mediaType": media_type,
        "role": "input",
    }


def _write_sample(
    run_dir: Path,
    sample_id: str,
    status: str,
    attempts: dict[int, list[dict]],
) -> None:
    _write_json(
        run_dir / sample_id / "result.json",
        {"finalAttempt": max(attempts), "status": status},
    )
    for attempt, records in attempts.items():
        trace_path = (
            run_dir
            / sample_id
            / f"attempt_{attempt:03d}"
            / "trace"
            / "source"
            / "trace.jsonl"
        )
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        trace_path.write_text(content + "\n", encoding="utf-8")


def _processing_evaluation(
    run_dir: Path,
    dsl: str,
    issues: list[dict],
    *,
    interface: int,
    validation: int,
    status: str,
) -> list[dict]:
    artifacts = {
        "dsl_processing_input": _blob(run_dir, dsl, media_type="text/plain"),
        "dsl_processing_issues": _blob(run_dir, issues),
    }
    attempts = {"interface": interface, "validation": validation}
    return [
        {
            "sequence": validation * 10,
            "operation": "dsl.processing",
            "status": status,
            "attempts": attempts,
            "artifacts": artifacts,
        },
        {
            "sequence": validation * 10 + 1,
            "operation": "validation.evaluate",
            "status": status,
            "attempts": attempts,
        },
    ]


def _write_run(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / run_id
    _write_json(
        run_dir / "summary.json",
        {
            "runId": run_id,
            "status": "completed",
            "samples": [
                {
                    "id": "Q001",
                    "title": "布局失败",
                    "query": "展示会议标题",
                    "size": "2x2",
                    "sequence": 1,
                    "status": "success",
                    "errorCode": "",
                },
                {
                    "id": "Q002",
                    "title": "单位失败",
                    "query": "展示倒计时",
                    "size": "2x4",
                    "sequence": 2,
                    "status": "failed",
                    "errorCode": "VALIDATION_FAILED",
                },
                {
                    "id": "Q003",
                    "title": "其它失败",
                    "query": "不应进入插件",
                    "size": "2x2",
                    "sequence": 3,
                    "status": "failed",
                    "errorCode": "MODEL_FAILED",
                },
            ],
        },
    )
    compact_dsl = '["root","Column",{"children":["title"]}]\n["title","Text",{"content":"会议"}]'
    coverage_issues = [
        {
            "code": "COMPACT_PLAN_COVERAGE_FAILED",
            "message": "Plan fact is missing from visible DSL: 会议标题。",
            "stage": "validation",
        }
    ]
    compact_issues = [
        {
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": "Text content is invalid.",
        }
    ]
    first_attempt = _processing_evaluation(
        run_dir,
        compact_dsl,
        coverage_issues,
        interface=1,
        validation=1,
        status="failed",
    )
    first_attempt.append(
        {
            "sequence": 20,
            "operation": "repair.attempt",
            "status": "success",
            "attempts": {"interface": 1, "qualityRepair": 1},
        }
    )
    first_attempt.extend(
        _processing_evaluation(
            run_dir,
            compact_dsl,
            compact_issues,
            interface=2,
            validation=1,
            status="failed",
        )
    )
    final_attempt = _processing_evaluation(
        run_dir,
        compact_dsl,
        [],
        interface=1,
        validation=1,
        status="success",
    )
    _write_sample(run_dir, "Q001", "success", {0: first_attempt, 1: final_attempt})
    genui = "\n".join(
        [
            '{"version":"v0.9","createSurface":{"surfaceId":"card"}}',
            '{"version":"v0.9","updateComponents":{"surfaceId":"card"}}',
            '{"version":"v0.9","updateDataModel":{"surfaceId":"card"}}',
        ]
    )
    validation_result = {
        "errors": ["DISPLAY_UNIT_MISSING: 缺少单位"],
        "promptContexts": [
            {
                "code": "DISPLAY_UNIT_MISSING",
                "message": "动态数值字段缺少单位。",
                "validatorStage": "semantic",
                "fileKind": "genui",
                "line": 2,
                "jsonPointer": "/value",
            }
        ],
    }
    artifact_attempt = _processing_evaluation(
        run_dir,
        compact_dsl,
        [],
        interface=1,
        validation=1,
        status="success",
    )
    artifact_attempt.insert(
        1,
        {
            "sequence": 20,
            "operation": "artifact_validation.completed",
            "status": "failed",
            "attempts": {"interface": 1, "validation": 1},
            "artifacts": {
                "artifact_validation_input": _blob(run_dir, {"genui": genui}),
                "artifact_validation_result": _blob(run_dir, validation_result),
            },
        },
    )
    artifact_attempt[-1]["status"] = "failed"
    _write_sample(run_dir, "Q002", "failed", {0: artifact_attempt})
    _write_sample(
        run_dir,
        "Q003",
        "failed",
        {0: [{"sequence": 1, "operation": "model.physical_call", "status": "failed"}]},
    )
    return run_dir


@pytest.mark.asyncio
async def test_validation_failure_gallery_extracts_trace_and_renders_only_target_samples(
    tmp_path: Path,
) -> None:
    run_id = "batch_20261009_validation_1234abcd"
    _write_run(tmp_path, run_id)

    async def capture(url: str, output_dir: Path) -> dict:
        assert url.endswith(f"/{run_id}/validation-failure-capture?offset=0&limit=20")
        for index in range(1, 4):
            (output_dir / f"{index:04d}.png").write_bytes(f"image-{index}".encode())
        return {
            "items": [
                {"id": "Q001-e1-i1-v1", "file": "0001.png", "error": ""},
                {"id": "Q001-e1-i2-v1", "file": "0002.png", "error": ""},
                {"id": "Q001-e2-i1-v1", "file": "0003.png", "error": ""},
                {"id": "Q002-e1-i1-v1", "file": "", "error": "JSON 无效"},
            ]
        }

    manager = ValidationFailureGalleryManager(
        tmp_path,
        "http://127.0.0.1:8888/debug",
        capture=capture,
    )
    items = manager.items(run_id)
    plugin_dir = tmp_path / run_id / "postprocess" / "exec_1" / "plugins" / (
        "validation-failure-gallery"
    )
    plugin_dir.mkdir(parents=True)
    result = await manager.run(run_id, plugin_dir)

    assert [item.get("id") for item in items] == ["Q001", "Q002"]
    assert items[0].get("finalStatus") == "success"
    assert items[0].get("interfaceRetryCount") == 1
    assert items[0].get("validationFailureCount") == 2
    assert items[0].get("repairAttemptCount") == 1
    assert len(items[0].get("validations", [])) == 3
    assert items[1].get("validations", [])[0].get("dsl", "").startswith(
        '{"version":"v0.9"'
    )
    sample_results = result.get("sampleResults")
    assert isinstance(sample_results, list)
    assert len(sample_results) == 2
    assert sample_results[0].get("status") == "success"
    assert sample_results[1].get("status") == "partial"
    first_artifacts = sample_results[0].get("artifacts")
    second_artifacts = sample_results[1].get("artifacts")
    assert isinstance(first_artifacts, list)
    assert isinstance(second_artifacts, list)
    issues = next(item for item in first_artifacts if item.get("key") == "validation-errors")
    assert all("stage" not in row for row in issues.get("data", []))
    assert issues.get("data", [])[0].get("接口调用") == "第 1 次（重试 0 次）"
    images = next(item for item in first_artifacts if item.get("key") == "validation-renders")
    assert len(images.get("data", [])) == 3
    failed_images = next(
        item for item in second_artifacts if item.get("key") == "validation-renders"
    )
    assert failed_images.get("data", [])[0].get("error") == "JSON 无效"
    assert result.get("status") == "partial"
    dataset_result = result.get("datasetResult")
    assert isinstance(dataset_result, dict)
    dataset_artifacts = dataset_result.get("artifacts")
    assert isinstance(dataset_artifacts, list)
    overview = next(
        item for item in dataset_artifacts if item.get("key") == "validation-overview"
    )
    assert overview.get("data") == [
        {"label": "执行成功率", "value": 33.33, "unit": "%"},
        {"label": "无校验失败比例", "value": 33.33, "unit": "%"},
        {"label": "平均修复 + 重试次数", "value": 0.67},
        {"label": "平均校验失败次数", "value": 1.0},
    ]
    distribution = next(
        item for item in dataset_artifacts if item.get("key") == "validation-error-types"
    )
    assert distribution.get("data") == [
        {"错误类型": "COMPACT_DSL_VALIDATION_FAILED", "出现次数": 1},
        {"错误类型": "COMPACT_PLAN_COVERAGE_FAILED", "出现次数": 1},
        {"错误类型": "DISPLAY_UNIT_MISSING", "出现次数": 1},
    ]
    image_path = plugin_dir / "samples" / "Q001" / "Q001-e1-i1-v1.png"
    assert image_path.read_bytes() == b"image-1"


def test_validation_failure_gallery_rejects_tampered_trace_blob(tmp_path: Path) -> None:
    run_id = "batch_20261009_validation_1234abcd"
    run_dir = _write_run(tmp_path, run_id)
    blob_path = next((run_dir / "trace_blobs").iterdir())
    blob_path.write_text("tampered", encoding="utf-8")
    manager = ValidationFailureGalleryManager(tmp_path, "http://127.0.0.1:8888/debug")

    with pytest.raises(ValueError, match="字节数不匹配|摘要校验失败"):
        manager.items(run_id)
