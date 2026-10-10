"""评分工作流：配置选择、只读方案、可比性、HTTP 和新执行隔离。"""

import copy
import json
from pathlib import Path

import debug_tools
import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.batch_testing.quality import _model, compare, evaluation
from debug_tools.batch_testing.runner import atomic_write_json
from debug_tools.batch_testing.task_manager import BatchTaskManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

PLUGINS = Path(debug_tools.__file__).resolve().parent / "postprocess_plugins"


def write_run(root: Path, run_id: str = "run") -> dict:
    summary = {
        "runId": run_id, "status": "completed", "total": 3,
        "samples": [
            {"id": "a", "query": "展示天气", "size": "2x2", "status": "success"},
            {"id": "b", "query": "展示日程", "size": "2x4", "status": "success"},
            {"id": "c", "query": "展示电量", "size": "2x2", "status": "failed"},
        ],
    }
    atomic_write_json(root / run_id / "summary.json", summary)
    return summary


@pytest.mark.parametrize("config", [
    {"sampleIds": []}, {"sampleIds": ["a", "a"]}, {"sampleIds": ["unknown"]},
    {"sampleIds": ["../a"]}, {"count": 0}, {"count": True}, {"count": 1.5},
    {"count": 4}, {"count": 1, "sampleIds": ["a"]}, {"unknown": True},
])
def test_bad_selection_rejected_before_execution(tmp_path: Path, config: dict) -> None:
    write_run(tmp_path)
    manager = PostprocessManager(tmp_path, PLUGINS)
    with pytest.raises(ValueError):
        manager.enqueue("run", ["quality-score"], {"quality-score": config})
    assert manager.executions("run") == []
    assert manager.queue.empty()


def test_schema_and_policy_have_one_parameter_source() -> None:
    manifest = json.loads((PLUGINS / "quality-score/plugin.json").read_text(encoding="utf-8"))
    schema = manifest.get("configSchema")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate({"sampleIds": ["a", "b"]})
    model = _model()
    current = evaluation()
    assert current.get("policy") == model.load_policy()
    assert current.get("policySha256") == model.policy_digest()
    markdown = current.get("markdown", "")
    assert "scoring-policy:start" not in markdown
    for category, weight in model.WEIGHTS.items():
        assert f"（{category}） | {weight}" in markdown
    changed = model.policy()
    changed.get("weights", {})["function"] = 0
    assert model.policy().get("weights", {}).get("function") == 0.5


@pytest.mark.asyncio
async def test_subset_executes_only_selected_and_keeps_history(tmp_path: Path) -> None:
    write_run(tmp_path)

    async def gallery(_run: str, _output: Path, _config: dict) -> dict:
        # 无截图的测试依赖；评分必须待评，不能凭空给分。
        return {"status": "success", "sampleResults": [],
                "datasetResult": {"status": "skipped", "artifacts": []}}

    manager = PostprocessManager(tmp_path, PLUGINS, builtin_runners={"browser-gallery": gallery})
    await manager.start()
    try:
        first = manager.enqueue("run", ["quality-score"], {"quality-score": {"count": 1}})
        await manager.queue.join()
        first_id = first.get("executionId")
        assert isinstance(first_id, str)
        first_dashboard = manager.dashboard("run", first_id, "quality-score")
        assert first_dashboard.get("selection") == {"sampleIds": ["a"]}
        assert first_dashboard.get("totalSamples") == 1
        assert first_dashboard.get("sourceTotalSamples") == 3
        assert manager.sample_result("run", first_id, "quality-score", "a").get(
            "facts", {}
        ).get("score") is None
        with pytest.raises(KeyError):
            manager.sample_result("run", first_id, "quality-score", "b")
        second = manager.enqueue(
            "run", ["quality-score"], {"quality-score": {"sampleIds": ["c", "b"]}}, rerun=True
        )
        await manager.queue.join()
        second_id = second.get("executionId")
        assert isinstance(second_id, str)
        assert first_id != second_id
        dashboard = manager.dashboard("run", second_id, "quality-score")
        assert dashboard.get("selection") == {"sampleIds": ["b", "c"]}
        assert len(dashboard.get("samples", [])) == 2
        assert dashboard.get("datasetResult", {}).get("facts", {}).get("total") == 2
        assert manager.dashboard("run", first_id, "quality-score") == first_dashboard
    finally:
        await manager.close()


def save_scores(
    manager: PostprocessManager, run_id: str, scores: dict, *,
    execution_id: str = "exec_1", policy: dict | None = None, query: str = "展示天气",
) -> None:
    write_run(manager.output_root, run_id)
    policy = policy or _model().policy()
    manifest = json.loads((PLUGINS / "quality-score/plugin.json").read_text(encoding="utf-8"))
    output = manager.output_root / run_id / "postprocess" / execution_id / "plugins/quality-score"
    output.mkdir(parents=True)
    results = []
    for sample_id, score in scores.items():
        issue = [{"规则": "GEOMETRY.CLIP_TEXT", "状态": "确认"}] if score == 85 else []
        result = {
            "sampleId": sample_id, "status": "success", "summary": "测试评分快照",
            "facts": {"score": score, "scoreLow": score,
                      "verdict": "范围内未扣分" if score == 100 else "存在确认问题"},
            "artifacts": [
                {"key": "issues", "data": issue + issue},
                {"key": "detail", "data": {"policy": policy, "evidence": {
                    "schemaVersion": "web-quality-v1",
                    "renderContext": {"query": query, "size": "2x2"},
                }}},
            ],
        }
        results.append(result)
    manager._persist_stage(run_id, execution_id, output, manifest, {
        "id": "quality-score", "status": "success", "sampleResults": results,
        "datasetResult": {"status": "success", "artifacts": [{"key": "policy", "data": policy}]},
    })
    atomic_write_json(output.parents[1] / "execution.json", {
        "runId": run_id, "executionId": execution_id, "status": "completed",
        "createdAt": execution_id, "plugins": [{"id": "quality-score", "status": "success"}],
    })


def test_compare_deltas_rates_and_deduplication(tmp_path: Path) -> None:
    manager = PostprocessManager(tmp_path, PLUGINS)
    save_scores(manager, "left", {"a": 85, "b": 100, "c": None})
    save_scores(manager, "right", {"a": 100, "b": 100, "c": None})
    result = compare(manager, "left", "right")
    assert result.get("comparable") is True
    assert result.get("passRateDelta") == 33.33
    assert result.get("left", {}).get("scored") == 2
    assert result.get("rows", [])[0].get("scoreDelta") == 15
    assert result.get("rows", [])[2].get("scoreDelta") is None
    assert result.get("issueDistribution") == [
        {"code": "GEOMETRY.CLIP_TEXT", "left": 1, "right": 0, "delta": -1}
    ]
    reverse = compare(manager, "right", "left")
    assert reverse.get("rows", [])[0].get("scoreDelta") == -15
    assert manager.queue.empty()


@pytest.mark.parametrize("mismatch", ["context", "policy", "subset"])
def test_compare_rejects_misleading_overall_improvement(tmp_path: Path, mismatch: str) -> None:
    manager = PostprocessManager(tmp_path, PLUGINS)
    save_scores(manager, "left", {"a": 85})
    policy = copy.deepcopy(_model().policy())
    if mismatch == "policy":
        policy.get("weights", {})["function"] = 0.6
    save_scores(manager, "right", {"a": 100, "b": 100} if mismatch == "subset" else {"a": 100},
                policy=policy, query="不同需求" if mismatch == "context" else "展示天气")
    result = compare(manager, "left", "right")
    assert result.get("comparable") is False
    assert result.get("passRateDelta") is None
    assert result.get("warnings")
    if mismatch != "subset":
        assert result.get("rows", [])[0].get("scoreDelta") is None


def test_latest_and_explicit_history_do_not_overwrite(tmp_path: Path) -> None:
    manager = PostprocessManager(tmp_path, PLUGINS)
    save_scores(manager, "left", {"a": 85}, execution_id="exec_1")
    save_scores(manager, "left", {"a": 100}, execution_id="exec_2")
    save_scores(manager, "right", {"a": 100})
    assert compare(manager, "left", "right").get("rows", [])[0].get("scoreDelta") == 0
    assert compare(manager, "left", "right", "exec_1").get("rows", [])[0].get("scoreDelta") == 15
    with pytest.raises(ValueError, match="尚无"):
        compare(manager, "missing", "right")
    with pytest.raises(KeyError):
        compare(manager, "../left", "right")


def test_read_only_http_and_invalid_config(tmp_path: Path) -> None:
    task_manager = BatchTaskManager(
        tmp_path / "Datasets", tmp_path / "output", tmp_path / "traces", tmp_path / "cloud"
    )
    manager = task_manager.postprocess_manager
    save_scores(manager, "left", {"a": 85})
    save_scores(manager, "right", {"a": 100})
    app = FastAPI()
    register_batch_routes(app, task_manager=task_manager)
    client = TestClient(app)
    assert client.get("/debug/batch/quality/evaluation").status_code == 200
    runs = client.get("/debug/batch/runs").json().get("items")
    assert len(runs) == 2
    response = client.get("/debug/batch/quality/compare?leftRunId=left&rightRunId=right")
    assert response.status_code == 200
    assert response.json().get("rows", [])[0].get("scoreDelta") == 15
    assert manager.queue.empty()
    bad = client.post("/debug/batch/runs/left/postprocess", json={
        "pluginIds": ["quality-score"], "rerun": True,
        "configs": {"quality-score": {"sampleIds": ["unknown"]}},
    })
    assert bad.status_code == 409
    assert manager.queue.empty()
