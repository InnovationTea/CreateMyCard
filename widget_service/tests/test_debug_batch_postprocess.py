from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing.postprocess import PostprocessManager


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_run(output_root: Path, run_id: str) -> None:
    run_dir = output_root / run_id
    _write_json(
        run_dir / "summary.json",
        {
            "runId": run_id,
            "status": "completed",
            "samples": [{"id": "Q001", "status": "success", "sequence": 1}],
        },
    )
    _write_json(run_dir / "Q001" / "result.json", {"finalAttempt": 0})
    (run_dir / "Q001" / "attempt_000").mkdir(parents=True)


def _write_plugin(plugins_root: Path, plugin_id: str, source: str) -> None:
    plugin_root = plugins_root / plugin_id
    _write_json(
        plugin_root / "plugin.json",
        {
            "apiVersion": "batch-postprocess-v1",
            "id": plugin_id,
            "name": plugin_id,
            "version": "1.0.0",
            "entrypoint": "plugin.py",
            "configSchema": {"type": "object", "additionalProperties": False},
        },
    )
    (plugin_root / "plugin.py").write_text(source, encoding="utf-8")


def _write_v2_plugin(plugins_root: Path, plugin_id: str, source: str) -> None:
    plugin_root = plugins_root / plugin_id
    _write_json(
        plugin_root / "plugin.json",
        {
            "apiVersion": "batch-postprocess-v2",
            "id": plugin_id,
            "name": plugin_id,
            "version": "2.0.0",
            "entrypoint": "plugin.py",
            "outputs": [
                {
                    "key": "detail",
                    "scope": "sample",
                    "title": "明细",
                    "dataType": "records",
                    "renderer": "table",
                    "required": True,
                },
                {
                    "key": "summary",
                    "scope": "dataset",
                    "title": "汇总",
                    "dataType": "metrics",
                    "renderer": "kpi",
                    "required": True,
                },
            ],
            "presentation": {
                "defaultView": "table",
                "sampleFields": [
                    {
                        "key": "score",
                        "label": "得分",
                        "type": "number",
                        "sortable": True,
                    }
                ],
            },
            "configSchema": {"type": "object", "additionalProperties": False},
        },
    )
    (plugin_root / "plugin.py").write_text(source, encoding="utf-8")


def _write_builtin_plugin(
    plugins_root: Path,
    plugin_id: str,
    dependence: list[str] | None = None,
) -> None:
    plugin_root = plugins_root / plugin_id
    _write_json(
        plugin_root / "plugin.json",
        {
            "apiVersion": "batch-postprocess-v2",
            "id": plugin_id,
            "name": plugin_id,
            "version": "2.0.0",
            "entrypoint": "builtin",
            "dependence": dependence or [],
            "outputs": [
                {
                    "key": "summary",
                    "scope": "dataset",
                    "title": "汇总",
                    "dataType": "metrics",
                    "required": False,
                }
            ],
            "configSchema": {"type": "object", "additionalProperties": False},
        },
    )


def test_postprocess_can_wait_for_run_completion(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261005_early_1234abcd"
    _write_plugin(
        plugins_root,
        "metrics",
        "def process_sample(context):\n"
        "    return {'status': 'success', 'summary': 'ok', 'blocks': []}\n",
    )
    manager = PostprocessManager(output_root, plugins_root)

    waiting = manager.enqueue(run_id, ["metrics"])

    assert waiting.get("status") == "waiting"
    assert manager.queue.qsize() == 0

    _write_run(output_root, run_id)
    activated = manager.activate_waiting(run_id)

    assert len(activated) == 1
    assert activated[0].get("status") == "queued"
    assert manager.queue.qsize() == 1


def test_waiting_postprocess_configuration_can_be_updated(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261005_update_1234abcd"
    for plugin_id in ("metrics", "gallery"):
        _write_plugin(
            plugins_root,
            plugin_id,
            "def process_sample(context):\n"
            "    return {'status': 'success', 'summary': 'ok', 'blocks': []}\n",
        )
    manager = PostprocessManager(output_root, plugins_root)

    original = manager.enqueue(run_id, ["metrics"])
    updated = manager.enqueue(run_id, ["gallery", "metrics"])

    assert updated.get("executionId") == original.get("executionId")
    assert updated.get("status") == "waiting"
    assert [plugin.get("id") for plugin in updated.get("plugins", [])] == [
        "gallery",
        "metrics",
    ]
    assert len(manager.executions(run_id)) == 1
    assert manager.queue.qsize() == 0


@pytest.mark.asyncio
async def test_postprocess_runs_script_plugin_and_persists_both_scopes(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261005_000000_1234abcd"
    _write_run(output_root, run_id)
    _write_plugin(
        plugins_root,
        "metrics",
        "from pathlib import Path\n"
        "def process_sample(context):\n"
        "    Path(context['outputDir'], 'note.txt').write_text('ok', encoding='utf-8')\n"
        "    return {'status': 'success', 'summary': context['sample']['id'], "
        "'blocks': [{'type': 'file', 'title': 'note', 'path': 'note.txt'}]}\n"
        "def process_dataset(context):\n"
        "    return {'status': 'success', 'summary': str(len(context['sampleResults'])), "
        "'blocks': [{'type': 'text', 'text': 'done'}]}\n",
    )
    manager = PostprocessManager(output_root, plugins_root)
    await manager.start()
    queued = manager.enqueue(run_id, ["metrics"])
    await manager.queue.join()
    result = manager.get_execution(run_id, str(queued.get("executionId")))
    await manager.close()

    assert result.get("status") == "completed"
    plugins = result.get("plugins")
    assert isinstance(plugins, list)
    stage = plugins[0]
    assert stage.get("datasetResult", {}).get("summary") == "1"
    dashboard = manager.dashboard(run_id, str(queued.get("executionId")), "metrics")
    assert dashboard.get("samples", [])[0].get("sampleId") == "Q001"
    sample = manager.sample_result(run_id, str(queued.get("executionId")), "metrics", "Q001")
    block = sample.get("blocks", [])[0]
    assert block.get("url", "").endswith("/assets/metrics/samples/Q001/note.txt")
    assert manager.asset_path(
        run_id,
        str(queued.get("executionId")),
        "metrics",
        "samples/Q001/note.txt",
    ).read_text(encoding="utf-8") == "ok"


@pytest.mark.asyncio
async def test_postprocess_continues_after_failed_plugin(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261005_000001_1234abcd"
    _write_run(output_root, run_id)
    _write_plugin(
        plugins_root,
        "broken",
        "def process_sample(context):\n    raise RuntimeError('bad')\n",
    )
    _write_plugin(
        plugins_root,
        "next",
        "def process_sample(context):\n"
        "    return {'status': 'success', 'summary': 'ok', 'blocks': []}\n",
    )
    manager = PostprocessManager(output_root, plugins_root)
    await manager.start()
    queued = manager.enqueue(run_id, ["broken", "next"])
    await manager.queue.join()
    result = manager.get_execution(run_id, str(queued.get("executionId")))
    await manager.close()

    stages = result.get("plugins")
    assert isinstance(stages, list)
    assert [stage.get("id") for stage in stages] == ["broken", "next"]
    assert stages[0].get("status") == "partial"
    assert stages[1].get("status") == "success"
    assert result.get("status") == "partial"


@pytest.mark.asyncio
async def test_independent_plugins_run_in_parallel(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261008_parallel_1234abcd"
    _write_run(output_root, run_id)
    _write_builtin_plugin(plugins_root, "first")
    _write_builtin_plugin(plugins_root, "second")
    started: set[str] = set()
    both_started = asyncio.Event()
    release = asyncio.Event()

    def runner(plugin_id: str):
        async def run(_run_id: str, _output_dir: Path, _config: dict) -> dict:
            started.add(plugin_id)
            if len(started) == 2:
                both_started.set()
            await release.wait()
            return {
                "status": "success",
                "sampleResults": [],
                "datasetResult": {
                    "status": "success",
                    "summary": plugin_id,
                    "facts": {},
                    "artifacts": [],
                },
            }

        return run

    manager = PostprocessManager(
        output_root,
        plugins_root,
        builtin_runners={"first": runner("first"), "second": runner("second")},
    )
    await manager.start()
    queued = manager.enqueue(run_id, ["first", "second"])
    await asyncio.wait_for(both_started.wait(), timeout=2.0)
    release.set()
    await manager.queue.join()
    result = manager.get_execution(run_id, str(queued.get("executionId")))
    await manager.close()

    assert str(queued.get("executionId")).startswith("exec_")
    assert started == {"first", "second"}
    assert result.get("status") == "completed"


@pytest.mark.asyncio
async def test_dependencies_are_added_and_finish_before_plugin(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261008_dependency_1234abcd"
    _write_run(output_root, run_id)
    _write_builtin_plugin(plugins_root, "prepare")
    _write_builtin_plugin(plugins_root, "report", ["prepare"])
    order: list[str] = []

    async def prepare(_run_id: str, _output_dir: Path, _config: dict) -> dict:
        order.append("prepare")
        return {
            "status": "success",
            "sampleResults": [],
            "datasetResult": {
                "status": "success",
                "summary": "prepare",
                "facts": {},
                "artifacts": [],
            },
        }

    async def report(_run_id: str, _output_dir: Path, _config: dict) -> dict:
        order.append("report")
        return {
            "status": "success",
            "sampleResults": [],
            "datasetResult": {
                "status": "success",
                "summary": "report",
                "facts": {},
                "artifacts": [],
            },
        }

    manager = PostprocessManager(
        output_root,
        plugins_root,
        builtin_runners={"prepare": prepare, "report": report},
    )
    await manager.start()
    queued = manager.enqueue(run_id, ["report"])
    await manager.queue.join()
    result = manager.get_execution(run_id, str(queued.get("executionId")))
    await manager.close()

    assert [plugin.get("id") for plugin in result.get("plugins", [])] == [
        "prepare",
        "report",
    ]
    assert order == ["prepare", "report"]


@pytest.mark.asyncio
async def test_start_only_runs_new_plugins_and_reuses_completed_dependency(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261008_new_only_1234abcd"
    _write_run(output_root, run_id)
    _write_builtin_plugin(plugins_root, "prepare")
    _write_builtin_plugin(plugins_root, "report", ["prepare"])
    calls = {"prepare": 0, "report": 0}

    def runner(plugin_id: str):
        async def run(_run_id: str, _output_dir: Path, _config: dict) -> dict:
            calls[plugin_id] += 1
            return {
                "status": "success",
                "sampleResults": [],
                "datasetResult": {
                    "status": "success",
                    "summary": plugin_id,
                    "facts": {},
                    "artifacts": [],
                },
            }

        return run

    manager = PostprocessManager(
        output_root,
        plugins_root,
        builtin_runners={"prepare": runner("prepare"), "report": runner("report")},
    )
    await manager.start()
    first = manager.enqueue(run_id, ["prepare"])
    await manager.queue.join()
    second = manager.enqueue(run_id, ["prepare", "report"])
    await manager.queue.join()
    result = manager.get_execution(run_id, str(second.get("executionId")))
    await manager.close()

    assert first.get("executionId") != second.get("executionId")
    assert [plugin.get("id") for plugin in result.get("plugins", [])] == ["report"]
    assert calls == {"prepare": 1, "report": 1}


@pytest.mark.asyncio
async def test_completed_plugin_requires_explicit_rerun(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261008_rerun_1234abcd"
    _write_run(output_root, run_id)
    _write_builtin_plugin(plugins_root, "metrics")
    call_count = 0

    async def metrics(_run_id: str, _output_dir: Path, _config: dict) -> dict:
        nonlocal call_count
        call_count += 1
        return {
            "status": "success",
            "sampleResults": [],
            "datasetResult": {
                "status": "success",
                "summary": str(call_count),
                "facts": {},
                "artifacts": [],
            },
        }

    manager = PostprocessManager(
        output_root,
        plugins_root,
        builtin_runners={"metrics": metrics},
    )
    await manager.start()
    manager.enqueue(run_id, ["metrics"])
    await manager.queue.join()
    with pytest.raises(ValueError, match="再次运行"):
        manager.enqueue(run_id, ["metrics"])
    rerun = manager.enqueue(run_id, ["metrics"], rerun=True)
    await manager.queue.join()
    await manager.close()

    assert call_count == 2
    assert len(manager.executions(run_id)) == 2
    assert [plugin.get("id") for plugin in rerun.get("plugins", [])] == ["metrics"]


def test_dependency_cycle_is_rejected(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261008_cycle_1234abcd"
    _write_run(output_root, run_id)
    _write_builtin_plugin(plugins_root, "first", ["second"])
    _write_builtin_plugin(plugins_root, "second", ["first"])
    manager = PostprocessManager(output_root, plugins_root)

    with pytest.raises(ValueError, match="依赖存在循环"):
        manager.enqueue(run_id, ["first"])


@pytest.mark.asyncio
async def test_v2_persists_dashboard_and_supports_paged_fact_filtering(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    plugins_root = tmp_path / "plugins"
    run_id = "batch_20261005_000002_1234abcd"
    _write_run(output_root, run_id)
    _write_v2_plugin(
        plugins_root,
        "quality",
        "def process_sample(context):\n"
        "    return {'status': 'success', 'summary': 'ok', 'facts': {'score': 80}, "
        "'artifacts': [{'key': 'detail', 'data': [{'name': 'layout'}]}]}\n"
        "def process_dataset(context):\n"
        "    return {'status': 'success', 'summary': 'done', 'facts': {}, "
        "'artifacts': [{'key': 'summary', 'data': [{'label': '平均', 'value': 80}]}]}\n",
    )
    manager = PostprocessManager(output_root, plugins_root)
    await manager.start()
    queued = manager.enqueue(run_id, ["quality"])
    await manager.queue.join()
    execution_id = str(queued.get("executionId"))
    execution = manager.get_execution(run_id, execution_id)
    dashboard = manager.dashboard(run_id, execution_id, "quality")
    page = manager.samples(
        run_id,
        execution_id,
        "quality",
        fact_key="score",
        fact_value="80",
    )
    sample = manager.sample_result(run_id, execution_id, "quality", "Q001")
    await manager.close()

    assert execution.get("schemaVersion") == "batch-postprocess-execution-v2"
    assert "sampleResults" not in execution.get("plugins", [])[0]
    assert dashboard.get("schemaVersion") == "batch-postprocess-dashboard-v2"
    assert dashboard.get("datasetResult", {}).get("artifacts", [])[0].get("key") == "summary"
    assert page.get("total") == 1
    assert sample.get("facts", {}).get("score") == 80
    result_path = (
        output_root
        / run_id
        / "postprocess"
        / execution_id
        / "plugins"
        / "quality"
        / "samples"
        / "Q001"
        / "result.json"
    )
    assert result_path.is_file()


@pytest.mark.parametrize(
    ("manifest_update", "message"),
    [
        (
            {
                "outputs": [
                    {"key": "x", "scope": "sample", "title": "x", "dataType": "video"}
                ]
            },
            "dataType",
        ),
        (
            {
                "outputs": [
                    {
                        "key": "x",
                        "scope": "sample",
                        "title": "x",
                        "dataType": "image",
                        "renderer": "bar",
                    }
                ]
            },
            "renderer",
        ),
        ({"presentation": {"defaultView": "custom", "sampleFields": []}}, "defaultView"),
    ],
)
def test_v2_manifest_rejects_unknown_types_and_hints(
    tmp_path: Path,
    manifest_update: dict,
    message: str,
) -> None:
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin.py").write_text(
        "def process_sample(context): return {}\n",
        encoding="utf-8",
    )
    manifest = {
        "apiVersion": "batch-postprocess-v2",
        "id": "invalid",
        "name": "invalid",
        "version": "1.0.0",
        "entrypoint": "plugin.py",
        "outputs": [
            {"key": "x", "scope": "sample", "title": "x", "dataType": "json"}
        ],
        "presentation": {"defaultView": "table", "sampleFields": []},
    }
    manifest.update(manifest_update)

    with pytest.raises(ValueError, match=message):
        PostprocessManager._validate_manifest(manifest, plugin_root)


def test_v2_result_rejects_missing_required_artifact_and_path_escape(tmp_path: Path) -> None:
    manifest = {
        "apiVersion": "batch-postprocess-v2",
        "outputs": [
            {
                "key": "file",
                "scope": "sample",
                "title": "文件",
                "dataType": "file",
                "required": True,
            }
        ],
    }
    with pytest.raises(ValueError, match="缺少必选"):
        PostprocessManager._normalize_result(
            {"status": "success", "facts": {}, "artifacts": []},
            manifest=manifest,
            scope="sample",
            asset_root=tmp_path,
        )
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="越界"):
        PostprocessManager._normalize_result(
            {
                "status": "success",
                "facts": {},
                "artifacts": [{"key": "file", "path": "../outside.txt"}],
            },
            manifest=manifest,
            scope="sample",
            asset_root=tmp_path,
        )


@pytest.mark.asyncio
async def test_complete_showcase_plugin_covers_all_renderers(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    plugins_root = Path(__file__).resolve().parents[2] / "debug_tools" / "postprocess_plugins"
    run_id = "batch_20261007_showcase_1234abcd"
    _write_run(output_root, run_id)
    manager = PostprocessManager(output_root, plugins_root)
    await manager.start()
    queued = manager.enqueue(run_id, ["complete-showcase"])
    await manager.queue.join()
    execution_id = str(queued.get("executionId"))
    dashboard = manager.dashboard(run_id, execution_id, "complete-showcase")
    sample = manager.sample_result(
        run_id,
        execution_id,
        "complete-showcase",
        "Q001",
    )
    await manager.close()

    dataset_artifacts = dashboard.get("datasetResult", {}).get("artifacts", [])
    sample_artifacts = sample.get("artifacts", [])
    artifacts = dataset_artifacts + sample_artifacts
    data_types = {artifact.get("dataType") for artifact in artifacts}
    renderers = {artifact.get("renderer") for artifact in artifacts}

    assert dashboard.get("status") == "success"
    assert data_types == {
        "metrics",
        "records",
        "matrix",
        "image",
        "json",
        "text",
        "code",
        "diff",
        "issues",
        "file",
        "link",
    }
    assert renderers == {
        None,
        "kpi",
        "table",
        "bar",
        "line",
        "pie",
        "heatmap",
        "gallery",
        "tree",
        "code",
        "diff",
        "issues",
        "download",
        "link",
    }
    path_artifacts = [artifact for artifact in sample_artifacts if artifact.get("path")]
    assert len(path_artifacts) == 5
    assert all(
        str(artifact.get("url", "")).startswith("/debug/batch/")
        for artifact in path_artifacts
    )
    image_artifact = next(
        artifact for artifact in sample_artifacts if artifact.get("dataType") == "image"
    )
    image_path = manager.asset_path(
        run_id,
        execution_id,
        "complete-showcase",
        f"samples/Q001/{image_artifact.get('path')}",
    )
    image_content = image_path.read_text(encoding="utf-8")
    assert 'width="640" height="240"' in image_content
    assert "样本得分概览" in image_content
