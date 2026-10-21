"""显式插件重试恢复失败依赖链，同时保留可用历史。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import pytest_asyncio
from debug_tools.batch_testing.postprocess import PostprocessManager


class RetryGraph:
    def __init__(self, directory: Path):
        self.output = directory / "output"
        self.plugins = directory / "plugins"
        self.run_id = "run_retry"
        self.run_dir = self.output / self.run_id
        self.run_dir.mkdir(parents=True)
        self.write(self.run_dir / "summary.json", {"status": "completed", "samples": []})
        self.calls: list[str] = []
        self.failures: set[str] = set()
        self.configs: dict[str, dict] = {}
        self.upstreams: dict[str, list[dict]] = {}
        self.manager = PostprocessManager(self.output, self.plugins)
        self.add_plugin("root")
        self.add_plugin("middle", ["root"])
        self.add_plugin("stable")
        self.add_plugin("report", ["middle", "stable"])

    @staticmethod
    def write(path: Path, value: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def add_plugin(self, identifier: str, dependencies: list[str] | None = None):
        self.write(
            self.plugins / identifier / "plugin.json",
            {
                "id": identifier,
                "name": identifier,
                "version": "1",
                "apiVersion": "batch-postprocess-v2",
                "entrypoint": "builtin",
                "dependence": dependencies or [],
                "configSchema": {"type": "object", "additionalProperties": False},
                "outputs": [
                    {
                        "key": "summary",
                        "scope": "dataset",
                        "title": "汇总",
                        "dataType": "metrics",
                        "required": False,
                    }
                ],
            },
        )
        self.manager.builtin_runners[identifier] = self.runner(identifier)

    def update_manifest(self, identifier: str, **changes):
        path = self.plugins / identifier / "plugin.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.write(path, {**manifest, **changes})

    def runner(self, identifier: str):
        async def run(_run_id, _output_dir, config, *, upstream_results):
            self.calls.append(identifier)
            self.configs[identifier] = config
            self.upstreams[identifier] = upstream_results
            if identifier in self.failures:
                raise RuntimeError(f"{identifier} 执行失败")
            return {
                "status": "success",
                "sampleResults": [],
                "datasetResult": {
                    "status": "success",
                    "facts": {},
                    "artifacts": [],
                    "summary": f"{identifier}:{self.calls.count(identifier)}",
                },
            }

        return run

    async def execute(self, *identifiers: str, rerun: bool = False, configs: dict | None = None):
        state = self.manager.enqueue(self.run_id, list(identifiers), configs, rerun=rerun)
        await asyncio.wait_for(self.manager.queue.join(), timeout=5)
        execution_id = state.get("executionId")
        assert isinstance(execution_id, str)
        return self.manager.get_execution(self.run_id, execution_id)


@pytest_asyncio.fixture
async def graph(tmp_path):
    value = RetryGraph(tmp_path)
    await value.manager.start()
    try:
        yield value
    finally:
        await value.manager.close()


def _ids(state: dict) -> list[str]:
    result = []
    for plugin in state.get("plugins") or []:
        identifier = plugin.get("id")
        assert isinstance(identifier, str)
        result.append(identifier)
    return result


@pytest.mark.asyncio
async def test_retry_recovers_failed_chain_in_order_and_preserves_history(graph):
    graph.failures.add("root")
    first = await graph.execute("report")
    assert first.get("status") == "partial"
    first_id = first.get("executionId")
    assert isinstance(first_id, str)
    original_path = graph.run_dir / "postprocess" / first_id / "execution.json"
    original = original_path.read_bytes()
    graph.failures.clear()
    graph.calls.clear()

    retried = await graph.execute("report", rerun=True)

    assert _ids(retried) == ["root", "middle", "report"]
    assert graph.calls == ["root", "middle", "report"]
    assert retried.get("status") == "completed"
    assert retried.get("executionId") != first_id
    assert original_path.read_bytes() == original
    upstream = graph.upstreams.get("report")
    assert isinstance(upstream, list)
    assert [stage.get("id") for stage in upstream] == ["middle", "stable"]
    assert upstream[0].get("datasetResult", {}).get("summary") == "middle:1"


@pytest.mark.asyncio
async def test_failed_dependency_blocks_target_again_if_recovery_fails(graph):
    graph.failures.add("root")
    await graph.execute("report")
    graph.calls.clear()

    retried = await graph.execute("report", rerun=True)

    assert graph.calls == ["root"]
    assert _ids(retried) == ["root", "middle", "report"]
    assert retried.get("status") == "failed"
    plugins = retried.get("plugins")
    assert isinstance(plugins, list)
    assert plugins[-1].get("status") == "failed"
    assert "依赖执行失败" in plugins[-1].get("error", "")


@pytest.mark.asyncio
async def test_latest_success_is_reused_after_previous_failure(graph):
    graph.failures.add("root")
    await graph.execute("report")
    graph.failures.clear()
    await graph.execute("root", rerun=True)
    graph.calls.clear()

    retried = await graph.execute("report", rerun=True)

    assert _ids(retried) == ["middle", "report"]
    assert graph.calls == ["middle", "report"]
    assert graph.upstreams.get("middle", [])[0].get("datasetResult", {}).get("summary") == "root:2"


@pytest.mark.asyncio
async def test_latest_failure_wins_over_old_success(graph):
    await graph.execute("report")
    graph.failures.add("root")
    await graph.execute("root", rerun=True)
    graph.failures.clear()
    graph.calls.clear()

    retried = await graph.execute("middle", rerun=True)

    assert _ids(retried) == ["root", "middle"]
    assert graph.calls == ["root", "middle"]


@pytest.mark.asyncio
async def test_reusable_dependency_stops_expansion_into_its_own_failed_ancestor(graph):
    await graph.execute("report")
    graph.failures.add("root")
    await graph.execute("root", rerun=True)
    graph.calls.clear()

    retried = await graph.execute("report", rerun=True)

    assert _ids(retried) == ["report"]
    assert graph.calls == ["report"]
    assert retried.get("status") == "completed"


@pytest.mark.asyncio
async def test_shared_failed_dependency_runs_once(graph):
    graph.update_manifest("stable", dependence=["root"])
    graph.failures.add("root")
    await graph.execute("report")
    graph.failures.clear()
    graph.calls.clear()

    retried = await graph.execute("report", rerun=True)

    assert set(_ids(retried)) == {"root", "middle", "stable", "report"}
    assert graph.calls.count("root") == 1
    assert graph.calls[0] == "root"
    assert graph.calls[-1] == "report"
    assert retried.get("status") == "completed"


@pytest.mark.asyncio
async def test_automatically_retried_dependency_keeps_previous_config_and_applies_override(graph):
    graph.update_manifest(
        "root",
        configSchema={
            "type": "object",
            "required": ["targetId"],
            "additionalProperties": False,
            "properties": {"targetId": {"type": "string"}, "limit": {"type": "integer"}},
        },
    )
    graph.failures.add("root")
    await graph.execute("report", configs={"root": {"targetId": "device-one", "limit": 1}})
    graph.failures.clear()

    retried = await graph.execute("report", rerun=True, configs={"root": {"limit": 2}})

    assert retried.get("status") == "completed"
    assert graph.configs.get("root") == {"targetId": "device-one", "limit": 2}


@pytest.mark.asyncio
async def test_explicit_target_config_replaces_old_mutually_exclusive_options(graph):
    graph.update_manifest(
        "root",
        configSchema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"old": {"type": "boolean"}, "new": {"type": "boolean"}},
            "not": {"required": ["old", "new"]},
        },
    )
    await graph.execute("root", configs={"root": {"old": True}})

    retried = await graph.execute("root", rerun=True, configs={"root": {"new": True}})

    assert retried.get("status") == "completed"
    assert graph.configs.get("root") == {"new": True}


@pytest.mark.asyncio
async def test_explicit_target_without_config_reuses_its_last_configuration(graph):
    graph.update_manifest(
        "root",
        configSchema={
            "type": "object",
            "required": ["targetId"],
            "additionalProperties": False,
            "properties": {"targetId": {"type": "string"}},
        },
    )
    await graph.execute("root", configs={"root": {"targetId": "device-one"}})

    retried = await graph.execute("root", rerun=True)

    assert retried.get("status") == "completed"
    assert graph.configs.get("root") == {"targetId": "device-one"}


@pytest.mark.asyncio
async def test_interrupted_dependency_with_running_snapshot_is_retried(graph):
    await graph.execute("report")
    graph.write(
        graph.run_dir / "postprocess/exec_interrupted/execution.json",
        {
            "executionId": "exec_interrupted",
            "runId": graph.run_id,
            "status": "interrupted",
            "createdAt": "2099-01-01T00:00:00Z",
            "plugins": [{"id": "root", "status": "running", "config": {}}],
        },
    )
    graph.calls.clear()

    retried = await graph.execute("middle", rerun=True)

    assert _ids(retried) == ["root", "middle"]
    assert graph.calls == ["root", "middle"]


@pytest.mark.asyncio
async def test_normal_start_does_not_silently_retry_previously_failed_dependencies(graph):
    graph.failures.add("root")
    await graph.execute("report")
    graph.add_plugin("new-report", ["root"])
    graph.calls.clear()

    state = await graph.execute("new-report")

    assert _ids(state) == ["new-report"]
    assert graph.calls == []
    assert state.get("status") == "failed"


@pytest.mark.parametrize("status", ["success", "partial", "skipped"])
def test_reusable_statuses_do_not_requeue_dependency(status):
    manifests = {"root": {"dependence": []}, "report": {"dependence": ["root"]}}
    selected = PostprocessManager._retry_plugin_ids(
        ["report"],
        manifests,
        {"root": {"status": status}},
    )
    assert selected == {"report"}


def gate_runner(graph, identifier, started, release):
    original = graph.runner(identifier)

    async def run(run_id, output_dir, config, *, upstream_results):
        started.set()
        await release.wait()
        return await original(run_id, output_dir, config, upstream_results=upstream_results)

    graph.manager.builtin_runners[identifier] = run


async def wait_for_dispatch(graph, count):
    async def ready():
        while len(graph.manager.execution_resources) < count:
            await asyncio.sleep(0)

    await asyncio.wait_for(ready(), timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("rerun", [False, True])
async def test_separate_independent_executions_run_concurrently(graph, rerun):
    if rerun:
        await graph.execute("root", "stable")
    started = asyncio.Event()
    release = asyncio.Event()
    other_started = asyncio.Event()
    gate_runner(graph, "root", started, release)
    gate_runner(graph, "stable", other_started, release)
    graph.manager.enqueue(graph.run_id, ["root"], rerun=rerun)
    await asyncio.wait_for(started.wait(), timeout=5)
    graph.manager.enqueue(graph.run_id, ["stable"], rerun=rerun)
    await asyncio.wait_for(other_started.wait(), timeout=5)
    assert len(graph.manager.execution_resources) == 2
    release.set()
    await asyncio.wait_for(graph.manager.queue.join(), timeout=5)
    assert not graph.manager.execution_resources


@pytest.mark.asyncio
async def test_separate_reports_can_read_the_same_historical_dependency_concurrently(graph):
    graph.add_plugin("other-report", ["middle", "stable"])
    await graph.execute("report", "other-report")
    release = asyncio.Event()
    started = asyncio.Event()
    other_started = asyncio.Event()
    gate_runner(graph, "report", started, release)
    gate_runner(graph, "other-report", other_started, release)
    graph.manager.enqueue(graph.run_id, ["report"], rerun=True)
    graph.manager.enqueue(graph.run_id, ["other-report"], rerun=True)
    await asyncio.wait_for(started.wait(), timeout=5)
    await asyncio.wait_for(other_started.wait(), timeout=5)
    release.set()
    await asyncio.wait_for(graph.manager.queue.join(), timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("first,second", [("root", "root"), ("root", "middle"), ("middle", "root")])
async def test_conflicting_executions_wait_without_blocking_unrelated_work(graph, first, second):
    await graph.execute("report")
    graph.calls.clear()
    started = asyncio.Event()
    release = asyncio.Event()
    gate_runner(graph, first, started, release)
    graph.manager.enqueue(graph.run_id, [first], rerun=True)
    await asyncio.wait_for(started.wait(), timeout=5)
    pending = graph.manager.enqueue(graph.run_id, [second], rerun=True)
    await wait_for_dispatch(graph, 2)
    pending_id = pending.get("executionId")
    assert isinstance(pending_id, str)
    assert graph.manager.get_execution(graph.run_id, pending_id).get("status") == "queued"
    unrelated = graph.manager.enqueue(graph.run_id, ["stable"], rerun=True)
    unrelated_id = unrelated.get("executionId")
    assert isinstance(unrelated_id, str)

    async def wait_for_unrelated():
        state = graph.manager.get_execution(graph.run_id, unrelated_id)
        while state.get("status") in {"queued", "running"}:
            await asyncio.sleep(0)
            state = graph.manager.get_execution(graph.run_id, unrelated_id)
        return state

    unrelated = await asyncio.wait_for(wait_for_unrelated(), timeout=5)
    assert unrelated.get("status") == "completed"
    release.set()
    await asyncio.wait_for(graph.manager.queue.join(), timeout=5)
    assert graph.calls == ["stable", first, second]
    if first == "root" and second == "middle":
        upstream = graph.upstreams.get("middle")
        assert isinstance(upstream, list)
        assert upstream[0].get("datasetResult", {}).get("summary") == "root:1"


@pytest.mark.asyncio
async def test_shutdown_cancels_active_and_conflicting_waiting_executions(graph):
    await graph.execute("root")
    started = asyncio.Event()
    release = asyncio.Event()
    gate_runner(graph, "root", started, release)
    active = graph.manager.enqueue(graph.run_id, ["root"], rerun=True)
    await asyncio.wait_for(started.wait(), timeout=5)
    pending = graph.manager.enqueue(graph.run_id, ["root"], rerun=True)
    await wait_for_dispatch(graph, 2)
    await graph.manager.close()
    await asyncio.wait_for(graph.manager.queue.join(), timeout=5)
    for state in [active, pending]:
        execution_id = state.get("executionId")
        assert isinstance(execution_id, str)
        saved = graph.manager.get_execution(graph.run_id, execution_id)
        assert saved.get("status") == "interrupted"
    assert not graph.manager.execution_tasks
    assert not graph.manager.execution_resources


@pytest.mark.asyncio
async def test_shutdown_marks_not_yet_dispatched_execution_interrupted(graph):
    state = graph.manager.enqueue(graph.run_id, ["root"])
    await graph.manager.close()
    await asyncio.wait_for(graph.manager.queue.join(), timeout=5)
    execution_id = state.get("executionId")
    assert isinstance(execution_id, str)
    saved = graph.manager.get_execution(graph.run_id, execution_id)
    assert saved.get("status") == "interrupted"


@pytest.mark.asyncio
async def test_dispatch_failure_does_not_stop_other_executions(graph, monkeypatch):
    original = graph.manager._execution_access
    broken = graph.manager.enqueue(graph.run_id, ["root"])
    broken_id = broken.get("executionId")

    def access(run_id, execution_id):
        if execution_id == broken_id:
            raise ValueError("调度准备失败")
        return original(run_id, execution_id)

    monkeypatch.setattr(graph.manager, "_execution_access", access)
    healthy = await graph.execute("stable")
    assert isinstance(broken_id, str)
    failed = graph.manager.get_execution(graph.run_id, broken_id)
    assert failed.get("status") == "failed"
    assert "调度准备失败" in failed.get("error", "")
    assert healthy.get("status") == "completed"
