"""批跑后处理插件发现、依赖图调度、持久化与结果校验。"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jsonschema import Draft202012Validator

from .runner import atomic_write_json, utc_now

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_RESULT_STATUSES = {"success", "partial", "failed", "skipped"}
_BLOCK_TYPES = {"metrics", "table", "text", "issues", "image", "link", "file"}
_DATA_TYPES = {
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
_RENDERERS_BY_DATA_TYPE = {
    "metrics": {"kpi", "table"},
    "records": {"table", "bar", "line", "pie"},
    "matrix": {"heatmap", "table"},
    "image": {"gallery"},
    "json": {"tree"},
    "text": set(),
    "code": {"code"},
    "diff": {"diff"},
    "issues": {"issues", "table"},
    "file": {"download"},
    "link": {"link"},
}
_FACT_TYPES = (str, int, float, bool)
BuiltinRunner = Callable[[str, Path, dict[str, Any]], Awaitable[dict[str, Any]]]


class PostprocessManager:
    """以独立队列执行后处理插件依赖图。"""

    def __init__(
        self,
        output_root: Path,
        plugins_root: Path,
        *,
        builtin_runners: dict[str, BuiltinRunner] | None = None,
        timeout_seconds: float = 900.0,
    ) -> None:
        self.output_root = output_root.resolve()
        self.plugins_root = plugins_root.resolve()
        self.builtin_runners = builtin_runners or {}
        self.timeout_seconds = timeout_seconds
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.worker: asyncio.Task[None] | None = None
        self.closing = False

    async def start(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        for path in self.output_root.glob("*/postprocess/*/execution.json"):
            state = self._read_json(path)
            if state.get("status") in {"queued", "running"}:
                state["status"] = "interrupted"
                state["finishedAt"] = utc_now()
                state["error"] = "调试后端重启导致后处理中断"
                atomic_write_json(path, state)
            elif state.get("status") == "waiting":
                summary_path = path.parents[2] / "summary.json"
                summary_completed = summary_path.is_file() and (
                    self._read_json(summary_path).get("status") == "completed"
                )
                if summary_completed:
                    state["status"] = "queued"
                    atomic_write_json(path, state)
                    run_id = str(state.get("runId") or "")
                    execution_id = str(state.get("executionId") or "")
                    self.queue.put_nowait((run_id, execution_id))
        if self.worker is None:
            self.worker = asyncio.create_task(self._worker_loop())

    async def close(self) -> None:
        self.closing = True
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)

    def plugins(self) -> list[dict[str, Any]]:
        manifests: list[dict[str, Any]] = []
        if not self.plugins_root.is_dir():
            return manifests
        for path in sorted(self.plugins_root.glob("*/plugin.json")):
            try:
                manifest = self._validate_manifest(self._read_json(path), path.parent)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            manifests.append(self._public_manifest(manifest))
        return manifests

    def enqueue(
        self,
        run_id: str,
        plugin_ids: list[str],
        configs: dict[str, Any] | None = None,
        *,
        rerun: bool = False,
    ) -> dict[str, Any]:
        run_dir = self._ensure_run_dir(run_id)
        summary_path = run_dir / "summary.json"
        run_completed = summary_path.is_file() and (
            self._read_json(summary_path).get("status") == "completed"
        )
        manifests = self._manifests()
        available = {item["id"]: item for item in manifests}
        expanded_ids = self._expand_dependencies(plugin_ids, available)
        requested_ids = set(plugin_ids)
        executed_plugin_ids = self._executed_plugin_ids(run_id)
        selected: list[dict[str, Any]] = []
        for plugin_id in expanded_ids:
            explicitly_requested = plugin_id in requested_ids
            already_completed = plugin_id in executed_plugin_ids
            should_rerun = rerun and explicitly_requested
            if already_completed and not should_rerun:
                continue
            manifest = available.get(plugin_id)
            if manifest is None:
                raise ValueError(f"后处理插件不存在: {plugin_id}")
            config = (configs or {}).get(plugin_id, {})
            if not isinstance(config, dict):
                raise ValueError(f"插件配置必须是对象: {plugin_id}")
            schema = manifest.get("configSchema", {"type": "object"})
            errors = list(Draft202012Validator(schema).iter_errors(config))
            if errors:
                raise ValueError(f"插件配置无效: {plugin_id}: {errors[0].message}")
            selected.append(
                {
                    "id": plugin_id,
                    "name": str(manifest.get("name") or plugin_id),
                    "version": str(manifest.get("version") or ""),
                    "apiVersion": str(manifest.get("apiVersion") or ""),
                    "dependence": list(manifest.get("dependence") or []),
                    "config": config,
                }
            )
        if not selected:
            raise ValueError("所选插件均已运行，请使用“再次运行”")
        waiting_executions = [
            item for item in self.executions(run_id) if item.get("status") == "waiting"
        ]
        existing = waiting_executions[0] if not run_completed and waiting_executions else None
        execution_id = (
            str(existing.get("executionId") or "")
            if existing is not None
            else f"exec_{uuid.uuid4().hex[:12]}"
        )
        execution_dir = run_dir / "postprocess" / execution_id
        execution_dir.mkdir(parents=True, exist_ok=existing is not None)
        now = utc_now()
        state = {
            "schemaVersion": "batch-postprocess-execution-v2",
            "executionId": execution_id,
            "runId": run_id,
            "status": "queued" if run_completed else "waiting",
            "createdAt": existing.get("createdAt") if existing is not None else now,
            "updatedAt": now,
            "startedAt": None,
            "finishedAt": None,
            "plugins": selected,
            "error": "",
        }
        atomic_write_json(execution_dir / "execution.json", state)
        for stale in waiting_executions[1:]:
            stale_execution_id = str(stale.get("executionId") or "")
            stale["status"] = "replaced"
            stale["finishedAt"] = now
            atomic_write_json(
                self._execution_dir(run_id, stale_execution_id) / "execution.json",
                stale,
            )
        if run_completed:
            self.queue.put_nowait((run_id, execution_id))
        return state

    def activate_waiting(self, run_id: str) -> list[dict[str, Any]]:
        activated: list[dict[str, Any]] = []
        for state in self.executions(run_id):
            if state.get("status") != "waiting":
                continue
            execution_id = str(state.get("executionId") or "")
            state["status"] = "queued"
            execution_dir = self._execution_dir(run_id, execution_id)
            atomic_write_json(execution_dir / "execution.json", state)
            self.queue.put_nowait((run_id, execution_id))
            activated.append(state)
        return activated

    def executions(self, run_id: str) -> list[dict[str, Any]]:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        run_dir = (self.output_root / run_id).resolve()
        if not run_dir.is_relative_to(self.output_root):
            raise KeyError(run_id)
        if not run_dir.is_dir():
            return []
        root = run_dir / "postprocess"
        if not root.is_dir():
            return []
        values: list[dict[str, Any]] = []
        for path in root.glob("*/execution.json"):
            try:
                values.append(self._read_json(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(values, key=lambda item: str(item.get("createdAt", "")), reverse=True)

    def get_execution(self, run_id: str, execution_id: str) -> dict[str, Any]:
        return self._read_json(self._execution_dir(run_id, execution_id) / "execution.json")

    def dashboard(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
    ) -> dict[str, Any]:
        plugin_dir = self._plugin_dir(run_id, execution_id, plugin_id)
        path = plugin_dir / "dashboard.json"
        if path.is_file():
            return self._read_json(path)
        return self._legacy_dashboard(run_id, execution_id, plugin_id)

    def samples(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        query: str = "",
        status: str = "",
        sort: str = "sequence",
        order: str = "asc",
        fact_key: str = "",
        fact_value: str = "",
    ) -> dict[str, Any]:
        dashboard = self.dashboard(run_id, execution_id, plugin_id)
        raw_items = dashboard.get("samples")
        items = [item for item in raw_items if isinstance(item, dict)] if isinstance(
            raw_items, list
        ) else []
        normalized_query = query.strip().casefold()
        filtered: list[dict[str, Any]] = []
        for item in items:
            if status and item.get("status") != status:
                continue
            searchable = " ".join(
                str(item.get(key) or "") for key in ("sampleId", "title", "summary")
            ).casefold()
            if normalized_query and normalized_query not in searchable:
                continue
            facts = item.get("facts")
            if fact_key and isinstance(facts, dict):
                candidate = facts.get(fact_key)
                values = candidate if isinstance(candidate, list) else [candidate]
                if fact_value and all(str(value) != fact_value for value in values):
                    continue
            elif fact_key:
                continue
            filtered.append(item)
        reverse = order == "desc"
        if sort == "status":
            filtered.sort(key=lambda item: str(item.get("status") or ""), reverse=reverse)
        elif sort.startswith("fact:"):
            key = sort.removeprefix("fact:")
            filtered.sort(
                key=lambda item: self._sortable_fact(item.get("facts"), key),
                reverse=reverse,
            )
        else:
            filtered.sort(key=lambda item: int(item.get("sequence") or 0), reverse=reverse)
        safe_offset = max(0, offset)
        safe_limit = max(1, min(limit, 200))
        return {
            "items": filtered[safe_offset:safe_offset + safe_limit],
            "total": len(filtered),
            "offset": safe_offset,
            "limit": safe_limit,
        }

    def sample_result(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(sample_id):
            raise KeyError(sample_id)
        plugin_dir = self._plugin_dir(run_id, execution_id, plugin_id)
        path = plugin_dir / "samples" / sample_id / "result.json"
        if path.is_file():
            return self._read_json(path)
        dashboard = self._legacy_dashboard(run_id, execution_id, plugin_id)
        raw_items = dashboard.get("samples")
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict) and item.get("sampleId") == sample_id:
                    return item
        raise KeyError(sample_id)

    def asset_path(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
        relative_path: str,
    ) -> Path:
        if not _SAFE_ID.fullmatch(plugin_id):
            raise KeyError(plugin_id)
        plugin_root = (self._execution_dir(run_id, execution_id) / "plugins" / plugin_id).resolve()
        path = (plugin_root / relative_path).resolve()
        if not path.is_relative_to(plugin_root) or not path.is_file():
            raise KeyError(relative_path)
        return path

    async def _worker_loop(self) -> None:
        while True:
            run_id, execution_id = await self.queue.get()
            try:
                await self._execute(run_id, execution_id)
            finally:
                self.queue.task_done()

    async def _execute(self, run_id: str, execution_id: str) -> None:
        execution_dir = self._execution_dir(run_id, execution_id)
        state_path = execution_dir / "execution.json"
        state = self._read_json(state_path)
        state.update({"status": "running", "startedAt": utc_now()})
        atomic_write_json(state_path, state)
        manifests = {item["id"]: item for item in self._manifests()}
        completed_results = self._latest_plugin_results(run_id)
        selections = list(state.get("plugins") or [])
        state["plugins"] = [
            {**selection, "status": "queued"}
            for selection in selections
            if isinstance(selection, dict)
        ]
        atomic_write_json(state_path, state)
        tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
        state_lock = asyncio.Lock()

        async def execute_plugin(selection: dict[str, Any]) -> dict[str, Any]:
            plugin_id = str(selection.get("id") or "")
            manifest = manifests.get(plugin_id)
            if manifest is None:
                raise ValueError(f"后处理插件不存在: {plugin_id}")
            dependencies = list(manifest.get("dependence") or [])
            upstream: list[dict[str, Any]] = []
            for dependency_id in dependencies:
                dependency_task = tasks.get(dependency_id)
                if dependency_task is not None:
                    dependency_result = await dependency_task
                else:
                    dependency_result = completed_results.get(dependency_id)
                    if dependency_result is None:
                        raise ValueError(f"后处理插件依赖尚未执行: {dependency_id}")
                upstream.append(dependency_result)
            plugin_dir = execution_dir / "plugins" / plugin_id
            plugin_dir.mkdir(parents=True, exist_ok=True)
            try:
                if plugin_id in self.builtin_runners:
                    result = await self.builtin_runners[plugin_id](
                        run_id,
                        plugin_dir,
                        dict(selection.get("config") or {}),
                    )
                else:
                    result = await self._run_script_plugin(
                        run_id,
                        manifest,
                        plugin_dir,
                        dict(selection.get("config") or {}),
                        upstream,
                    )
                normalized = self._normalize_stage(plugin_id, result, manifest)
            except Exception as exc:
                normalized = {
                    "id": plugin_id,
                    "status": "failed",
                    "sampleResults": [],
                    "datasetResult": {
                        "status": "failed",
                        "summary": f"{type(exc).__name__}: {exc}",
                        "facts": {},
                        "artifacts": [],
                    },
                }
            summary = self._persist_stage(
                run_id,
                execution_id,
                plugin_dir,
                manifest,
                normalized,
            )
            async with state_lock:
                for index, plugin_state in enumerate(state["plugins"]):
                    if plugin_state.get("id") == plugin_id:
                        state["plugins"][index] = summary
                        break
                state["updatedAt"] = utc_now()
                atomic_write_json(state_path, state)
            return normalized

        try:
            for selection in selections:
                if not isinstance(selection, dict):
                    continue
                plugin_id = str(selection.get("id") or "")
                tasks[plugin_id] = asyncio.create_task(execute_plugin(selection))
            await asyncio.gather(*tasks.values())
            plugin_states = [
                plugin for plugin in state["plugins"] if isinstance(plugin, dict)
            ]
            statuses = {item.get("status") for item in plugin_states}
            state["status"] = "completed" if statuses <= {"success", "skipped"} else "partial"
        except asyncio.CancelledError:
            state["status"] = "interrupted"
            state["error"] = "调试后端关闭导致后处理中断"
            raise
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            state["finishedAt"] = utc_now()
            atomic_write_json(state_path, state)

    async def _run_script_plugin(
        self,
        run_id: str,
        manifest: dict[str, Any],
        plugin_dir: Path,
        config: dict[str, Any],
        upstream: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        summary = self._read_json(run_dir / "summary.json")
        execution_id = plugin_dir.parent.parent.name
        plugin_id = str(manifest.get("id") or "")
        asset_base_url = (
            f"/debug/batch/runs/{quote(run_id, safe='')}/postprocess/"
            f"{quote(execution_id, safe='')}/assets/{quote(plugin_id, safe='')}"
        )
        sample_results: list[dict[str, Any]] = []
        for sample in list(summary.get("samples") or []):
            if not isinstance(sample, dict):
                continue
            sample_id = str(sample.get("id") or "")
            output_dir = plugin_dir / "samples" / sample_id
            output_dir.mkdir(parents=True, exist_ok=True)
            sample_state_path = run_dir / sample_id / "result.json"
            sample_state = self._read_json(sample_state_path) if sample_state_path.is_file() else {}
            final_attempt = sample_state.get("finalAttempt")
            final_attempt_dir = None
            if isinstance(final_attempt, int) and final_attempt >= 0:
                final_attempt_dir = run_dir / sample_id / f"attempt_{final_attempt:03d}"
            context = {
                "apiVersion": str(manifest.get("apiVersion") or ""),
                "scope": "sample",
                "runId": run_id,
                "sample": sample,
                "runDir": str(run_dir),
                "sampleDir": str(run_dir / sample_id),
                "finalAttemptDir": str(final_attempt_dir) if final_attempt_dir else None,
                "outputDir": str(output_dir),
                "config": config,
                "upstreamResults": [self._sample_upstream(item, sample_id) for item in upstream],
            }
            try:
                result = await self._invoke_subprocess(
                    manifest,
                    "process_sample",
                    context,
                    output_dir,
                )
                normalized = self._normalize_result(
                    result,
                    manifest=manifest,
                    scope="sample",
                    asset_root=output_dir,
                    asset_base_url=(
                        f"{asset_base_url}/samples/{quote(sample_id, safe='')}"
                    ),
                )
            except Exception as exc:
                normalized = {
                    "status": "failed",
                    "summary": f"{type(exc).__name__}: {exc}",
                    "facts": {},
                    "artifacts": [],
                }
            sample_results.append({"sampleId": sample_id, **normalized})
        dataset_dir = plugin_dir / "dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        dataset_context = {
            "apiVersion": str(manifest.get("apiVersion") or ""),
            "scope": "dataset",
            "runId": run_id,
            "run": summary,
            "runDir": str(run_dir),
            "outputDir": str(dataset_dir),
            "config": config,
            "sampleResults": sample_results,
            "upstreamResults": upstream,
        }
        try:
            dataset_value = await self._invoke_subprocess(
                manifest,
                "process_dataset",
                dataset_context,
                dataset_dir,
            )
            dataset_result = self._normalize_result(
                dataset_value,
                manifest=manifest,
                scope="dataset",
                asset_root=dataset_dir,
                asset_base_url=f"{asset_base_url}/dataset",
            )
        except Exception as exc:
            dataset_result = {
                "status": "failed",
                "summary": f"{type(exc).__name__}: {exc}",
                "facts": {},
                "artifacts": [],
            }
        statuses = {item.get("status") for item in sample_results}
        statuses.add(dataset_result.get("status"))
        stage_status = "success"
        if "failed" in statuses:
            stage_status = "partial"
        return {
            "status": stage_status,
            "sampleResults": sample_results,
            "datasetResult": dataset_result,
        }

    async def _invoke_subprocess(
        self,
        manifest: dict[str, Any],
        hook: str,
        context: dict[str, Any],
        output_dir: Path,
    ) -> dict[str, Any]:
        context_path = output_dir / f".{hook}.context.json"
        result_path = output_dir / f".{hook}.result.json"
        atomic_write_json(context_path, context)
        worker = Path(__file__).with_name("plugin_worker.py")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(worker),
            "--entrypoint",
            str(manifest["entrypointPath"]),
            "--hook",
            hook,
            "--context",
            str(context_path),
            "--result",
            str(result_path),
            cwd=output_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=float(manifest.get("timeoutSeconds") or self.timeout_seconds),
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise RuntimeError(f"插件函数执行超时: {hook}") from exc
        (output_dir / f"{hook}.stdout.log").write_bytes(stdout)
        (output_dir / f"{hook}.stderr.log").write_bytes(stderr)
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"插件进程退出码 {process.returncode}")
        return self._read_json(result_path)

    def _manifests(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for path in sorted(self.plugins_root.glob("*/plugin.json")):
            values.append(self._validate_manifest(self._read_json(path), path.parent))
        return values

    @staticmethod
    def _validate_manifest(value: dict[str, Any], root: Path) -> dict[str, Any]:
        plugin_id = value.get("id")
        api_version = value.get("apiVersion")
        if api_version not in {"batch-postprocess-v1", "batch-postprocess-v2"}:
            raise ValueError("插件 apiVersion 不受支持")
        if not isinstance(plugin_id, str) or not _SAFE_ID.fullmatch(plugin_id):
            raise ValueError("插件 id 无效")
        entrypoint = value.get("entrypoint")
        if entrypoint == "builtin":
            entrypoint_path: Path | None = None
        elif isinstance(entrypoint, str):
            entrypoint_path = (root / entrypoint).resolve()
            if not entrypoint_path.is_relative_to(root.resolve()) or not entrypoint_path.is_file():
                raise ValueError("插件入口不存在或越界")
        else:
            raise ValueError("插件入口无效")
        result = dict(value)
        result["entrypointPath"] = entrypoint_path
        dependence = result.setdefault("dependence", [])
        if not isinstance(dependence, list):
            raise ValueError("插件 dependence 必须是数组")
        for dependency_id in dependence:
            if not isinstance(dependency_id, str) or not _SAFE_ID.fullmatch(dependency_id):
                raise ValueError("插件 dependence 包含无效插件名称")
            if dependency_id == plugin_id:
                raise ValueError("插件不能依赖自身")
        if len(dependence) != len(set(dependence)):
            raise ValueError("插件 dependence 不得重复")
        result.setdefault("configSchema", {"type": "object", "additionalProperties": False})
        if api_version == "batch-postprocess-v2":
            PostprocessManager._validate_outputs(result.get("outputs"))
            PostprocessManager._validate_presentation(result.get("presentation"))
        return result

    @staticmethod
    def _expand_dependencies(
        plugin_ids: list[str],
        manifests: dict[str, dict[str, Any]],
    ) -> list[str]:
        expanded: list[str] = []
        completed: set[str] = set()
        visiting: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in completed:
                return
            manifest = manifests.get(plugin_id)
            if manifest is None:
                raise ValueError(f"后处理插件不存在: {plugin_id}")
            if plugin_id in visiting:
                raise ValueError(f"后处理插件依赖存在循环: {plugin_id}")
            visiting.add(plugin_id)
            for dependency_id in list(manifest.get("dependence") or []):
                visit(str(dependency_id))
            visiting.remove(plugin_id)
            completed.add(plugin_id)
            expanded.append(plugin_id)

        for plugin_id in plugin_ids:
            visit(plugin_id)
        return expanded

    def _latest_plugin_results(self, run_id: str) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for execution in self.executions(run_id):
            execution_id = str(execution.get("executionId") or "")
            for plugin in list(execution.get("plugins") or []):
                if not isinstance(plugin, dict):
                    continue
                plugin_id = str(plugin.get("id") or "")
                status = str(plugin.get("status") or "")
                if not plugin_id or plugin_id in results:
                    continue
                if status in {"", "waiting", "queued", "running"}:
                    continue
                result = self._stored_plugin_result(run_id, execution_id, plugin_id)
                if result is not None:
                    results[plugin_id] = result
        return results

    def _executed_plugin_ids(self, run_id: str) -> set[str]:
        plugin_ids: set[str] = set()
        for execution in self.executions(run_id):
            for plugin in list(execution.get("plugins") or []):
                if not isinstance(plugin, dict):
                    continue
                plugin_id = str(plugin.get("id") or "")
                status = str(plugin.get("status") or "")
                if plugin_id and status not in {"", "waiting", "queued", "running"}:
                    plugin_ids.add(plugin_id)
        return plugin_ids

    def _stored_plugin_result(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
    ) -> dict[str, Any] | None:
        try:
            dashboard = self.dashboard(run_id, execution_id, plugin_id)
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            return None
        sample_results: list[dict[str, Any]] = []
        for sample in list(dashboard.get("samples") or []):
            if not isinstance(sample, dict):
                continue
            sample_id = str(sample.get("sampleId") or "")
            if not sample_id:
                continue
            try:
                result = self.sample_result(run_id, execution_id, plugin_id, sample_id)
            except (KeyError, OSError, ValueError, json.JSONDecodeError):
                result = sample
            sample_results.append(result)
        return {
            "id": plugin_id,
            "status": str(dashboard.get("status") or "failed"),
            "sampleResults": sample_results,
            "datasetResult": dict(dashboard.get("datasetResult") or {}),
        }

    @staticmethod
    def _validate_outputs(value: object) -> None:
        if not isinstance(value, list) or not value:
            raise ValueError("v2 插件必须声明 outputs")
        seen: set[tuple[str, str]] = set()
        for output in value:
            if not isinstance(output, dict):
                raise ValueError("插件 outputs 项必须是对象")
            allowed_keys = {"key", "scope", "title", "dataType", "renderer", "required"}
            if set(output) - allowed_keys:
                raise ValueError("插件 outputs 包含不支持的字段")
            key = output.get("key")
            scope = output.get("scope")
            title = output.get("title")
            data_type = output.get("dataType")
            renderer = output.get("renderer")
            if not isinstance(key, str) or not _SAFE_ID.fullmatch(key):
                raise ValueError("插件 output key 无效")
            if scope not in {"sample", "dataset"}:
                raise ValueError(f"插件 output scope 无效: {key}")
            if data_type not in _DATA_TYPES:
                raise ValueError(f"插件 output dataType 无效: {key}")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"插件 output title 无效: {key}")
            allowed_renderers = _RENDERERS_BY_DATA_TYPE.get(str(data_type), set())
            if renderer is not None and renderer not in allowed_renderers:
                raise ValueError(f"插件 output renderer 无效: {key}")
            if "required" in output and not isinstance(output.get("required"), bool):
                raise ValueError(f"插件 output required 无效: {key}")
            identity = (scope, key)
            if identity in seen:
                raise ValueError(f"插件 output 重复: {scope}/{key}")
            seen.add(identity)

    @staticmethod
    def _validate_presentation(value: object) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            raise ValueError("插件 presentation 必须是对象")
        if set(value) - {"defaultView", "sampleFields"}:
            raise ValueError("插件 presentation 包含不支持的字段")
        if value.get("defaultView", "table") not in {"table", "gallery"}:
            raise ValueError("插件 presentation.defaultView 无效")
        fields = value.get("sampleFields", [])
        if not isinstance(fields, list):
            raise ValueError("插件 presentation.sampleFields 必须是数组")
        seen: set[str] = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("插件 sampleFields 项必须是对象")
            allowed_keys = {"key", "label", "type", "format", "sortable", "filterable"}
            if set(field) - allowed_keys:
                raise ValueError("插件 sampleFields 包含不支持的字段")
            key = field.get("key")
            label = field.get("label")
            field_type = field.get("type")
            if not isinstance(key, str) or not _SAFE_ID.fullmatch(key) or key in seen:
                raise ValueError("插件 sampleFields key 无效或重复")
            if field_type not in {"string", "number", "boolean", "string-list"}:
                raise ValueError(f"插件 sampleFields type 无效: {key}")
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"插件 sampleFields label 无效: {key}")
            if field.get("format") not in {None, "percent", "number", "boolean", "text"}:
                raise ValueError(f"插件 sampleFields format 无效: {key}")
            seen.add(key)

    @staticmethod
    def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in manifest.items() if key != "entrypointPath"}

    @classmethod
    def _normalize_stage(
        cls,
        plugin_id: str,
        value: dict[str, Any],
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        status = value.get("status")
        if status not in _RESULT_STATUSES:
            raise ValueError(f"插件 {plugin_id} 返回了无效状态")
        sample_results: list[dict[str, Any]] = []
        for item in list(value.get("sampleResults") or []):
            if not isinstance(item, dict):
                raise ValueError(f"插件 {plugin_id} 样本结果无效")
            sample_id = str(item.get("sampleId") or "")
            if not _SAFE_ID.fullmatch(sample_id):
                raise ValueError(f"插件 {plugin_id} 样本标识无效")
            if manifest.get("entrypoint") == "builtin":
                normalized = cls._normalize_result(
                    item,
                    manifest=manifest,
                    scope="sample",
                )
            else:
                normalized = dict(item)
            sample_results.append({"sampleId": sample_id, **normalized})
        dataset_value = dict(value.get("datasetResult") or {})
        if manifest.get("entrypoint") == "builtin":
            dataset_result = cls._normalize_result(
                dataset_value,
                manifest=manifest,
                scope="dataset",
            )
        else:
            dataset_result = dataset_value
        return {
            "id": plugin_id,
            "status": status,
            "sampleResults": sample_results,
            "datasetResult": dataset_result,
        }

    @classmethod
    def _normalize_result(
        cls,
        value: dict[str, Any],
        *,
        manifest: dict[str, Any],
        scope: str,
        asset_root: Path | None = None,
        asset_base_url: str = "",
    ) -> dict[str, Any]:
        status = value.get("status", "success")
        if status not in _RESULT_STATUSES:
            raise ValueError("插件结果 status 无效")
        if manifest.get("apiVersion") == "batch-postprocess-v1":
            return cls._normalize_v1_result(
                value,
                asset_root=asset_root,
                asset_base_url=asset_base_url,
            )
        facts = cls._normalize_facts(value.get("facts", {}))
        artifacts = value.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("插件结果 artifacts 必须是数组")
        output_map = cls._output_map(manifest, scope)
        normalized_artifacts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ValueError("插件 artifact 必须是对象")
            key = artifact.get("key")
            output = output_map.get(str(key))
            if output is None:
                raise ValueError(f"插件 artifact 未在清单声明: {key}")
            if key in seen:
                raise ValueError(f"插件 artifact 重复: {key}")
            seen.add(str(key))
            normalized = dict(artifact)
            normalized.update(
                {
                    "key": str(key),
                    "title": str(output.get("title") or key),
                    "dataType": str(output.get("dataType")),
                }
            )
            renderer = output.get("renderer")
            if renderer is not None:
                normalized["renderer"] = renderer
            cls._normalize_artifact_path(normalized, asset_root, asset_base_url)
            try:
                json.dumps(normalized, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"插件 artifact 不可 JSON 序列化: {key}") from exc
            normalized_artifacts.append(normalized)
        if status in {"success", "partial"}:
            for key, output in output_map.items():
                if output.get("required") is True and key not in seen:
                    raise ValueError(f"插件缺少必选 artifact: {scope}/{key}")
        return {
            "status": status,
            "summary": str(value.get("summary") or ""),
            "facts": facts,
            "artifacts": normalized_artifacts,
        }

    @staticmethod
    def _normalize_v1_result(
        value: dict[str, Any],
        *,
        asset_root: Path | None,
        asset_base_url: str,
    ) -> dict[str, Any]:
        status = value.get("status", "success")
        blocks = value.get("blocks", [])
        if not isinstance(blocks, list):
            raise ValueError("插件结果 blocks 必须是数组")
        normalized_blocks: list[dict[str, Any]] = []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") not in _BLOCK_TYPES:
                raise ValueError("插件结果块类型无效")
            normalized_block = dict(block)
            relative_path = normalized_block.get("path")
            if relative_path is not None:
                if not isinstance(relative_path, str) or asset_root is None:
                    raise ValueError("插件结果块 path 无效")
                resolved = (asset_root / relative_path).resolve()
                if not resolved.is_relative_to(asset_root.resolve()) or not resolved.is_file():
                    raise ValueError("插件结果块文件不存在或路径越界")
                safe_relative = resolved.relative_to(asset_root.resolve()).as_posix()
                normalized_block["path"] = safe_relative
                normalized_block["url"] = f"{asset_base_url}/{quote(safe_relative, safe='/')}"
            normalized_blocks.append(normalized_block)
        return {
            "status": status,
            "summary": str(value.get("summary") or ""),
            "blocks": normalized_blocks,
        }

    @staticmethod
    def _normalize_facts(value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("插件结果 facts 必须是对象")
        facts: dict[str, Any] = {}
        for key, fact in value.items():
            if not isinstance(key, str) or not _SAFE_ID.fullmatch(key):
                raise ValueError("插件 fact key 无效")
            if isinstance(fact, _FACT_TYPES) or fact is None:
                facts[key] = fact
                continue
            if isinstance(fact, list) and all(isinstance(item, str) for item in fact):
                facts[key] = list(fact)
                continue
            raise ValueError(f"插件 fact 值无效: {key}")
        return facts

    @staticmethod
    def _output_map(manifest: dict[str, Any], scope: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for output in list(manifest.get("outputs") or []):
            if isinstance(output, dict) and output.get("scope") == scope:
                result[str(output.get("key") or "")] = output
        return result

    @staticmethod
    def _normalize_artifact_path(
        artifact: dict[str, Any],
        asset_root: Path | None,
        asset_base_url: str,
    ) -> None:
        relative_path = artifact.get("path")
        if relative_path is None:
            return
        if not isinstance(relative_path, str) or asset_root is None:
            raise ValueError("插件 artifact path 无效")
        resolved = (asset_root / relative_path).resolve()
        if not resolved.is_relative_to(asset_root.resolve()) or not resolved.is_file():
            raise ValueError("插件 artifact 文件不存在或路径越界")
        safe_relative = resolved.relative_to(asset_root.resolve()).as_posix()
        artifact["path"] = safe_relative
        artifact["url"] = f"{asset_base_url}/{quote(safe_relative, safe='/')}"

    def _persist_stage(
        self,
        run_id: str,
        execution_id: str,
        plugin_dir: Path,
        manifest: dict[str, Any],
        stage: dict[str, Any],
    ) -> dict[str, Any]:
        sample_results = [
            item for item in list(stage.get("sampleResults") or []) if isinstance(item, dict)
        ]
        dataset_result = dict(stage.get("datasetResult") or {})
        counts = {status: 0 for status in _RESULT_STATUSES}
        for item in sample_results:
            sample_status = str(item.get("status") or "failed")
            if sample_status in counts:
                counts[sample_status] += 1
            sample_id = str(item.get("sampleId") or "")
            if _SAFE_ID.fullmatch(sample_id):
                atomic_write_json(plugin_dir / "samples" / sample_id / "result.json", item)
        atomic_write_json(plugin_dir / "dataset" / "result.json", dataset_result)
        summary = {
            "id": str(stage.get("id") or manifest.get("id") or ""),
            "name": str(manifest.get("name") or manifest.get("id") or ""),
            "version": str(manifest.get("version") or ""),
            "apiVersion": str(manifest.get("apiVersion") or ""),
            "status": str(stage.get("status") or "failed"),
            "sampleCount": len(sample_results),
            "counts": counts,
            "datasetResult": self._result_summary(dataset_result),
        }
        atomic_write_json(plugin_dir / "result.json", summary)
        dashboard = self._build_dashboard(
            run_id,
            execution_id,
            manifest,
            stage,
            counts,
        )
        atomic_write_json(plugin_dir / "dashboard.json", dashboard)
        return summary

    def _build_dashboard(
        self,
        run_id: str,
        execution_id: str,
        manifest: dict[str, Any],
        stage: dict[str, Any],
        counts: dict[str, int],
    ) -> dict[str, Any]:
        run = self._read_json(self._run_dir(run_id) / "summary.json")
        sample_meta = {
            str(item.get("id") or ""): item
            for item in list(run.get("samples") or [])
            if isinstance(item, dict)
        }
        samples: list[dict[str, Any]] = []
        for item in list(stage.get("sampleResults") or []):
            if not isinstance(item, dict):
                continue
            sample_id = str(item.get("sampleId") or "")
            meta = sample_meta.get(sample_id, {})
            samples.append(
                {
                    "sampleId": sample_id,
                    "title": str(meta.get("title") or sample_id),
                    "sequence": int(meta.get("sequence") or len(samples) + 1),
                    "status": str(item.get("status") or "failed"),
                    "summary": str(item.get("summary") or ""),
                    "facts": dict(item.get("facts") or {}),
                    "artifacts": self._artifact_summaries(item),
                }
            )
        return {
            "schemaVersion": "batch-postprocess-dashboard-v2",
            "runId": run_id,
            "executionId": execution_id,
            "plugin": {
                "id": str(manifest.get("id") or ""),
                "name": str(manifest.get("name") or manifest.get("id") or ""),
                "version": str(manifest.get("version") or ""),
                "apiVersion": str(manifest.get("apiVersion") or ""),
            },
            "status": str(stage.get("status") or "failed"),
            "presentation": dict(manifest.get("presentation") or {"defaultView": "table"}),
            "outputs": list(manifest.get("outputs") or []),
            "datasetResult": dict(stage.get("datasetResult") or {}),
            "counts": counts,
            "totalSamples": int(run.get("total") or len(samples)),
            "samples": samples,
        }

    @staticmethod
    def _artifact_summaries(result: dict[str, Any]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for artifact in list(result.get("artifacts") or []):
            if not isinstance(artifact, dict):
                continue
            summary = {key: value for key, value in artifact.items() if key != "data"}
            if artifact.get("dataType") == "image" and "url" in artifact:
                summary["url"] = artifact.get("url")
            summaries.append(summary)
        return summaries

    @staticmethod
    def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(result.get("status") or "failed"),
            "summary": str(result.get("summary") or ""),
            "facts": dict(result.get("facts") or {}),
            "artifactCount": len(list(result.get("artifacts") or result.get("blocks") or [])),
        }

    def _legacy_dashboard(
        self,
        run_id: str,
        execution_id: str,
        plugin_id: str,
    ) -> dict[str, Any]:
        execution = self.get_execution(run_id, execution_id)
        for stage in list(execution.get("plugins") or []):
            if not isinstance(stage, dict) or stage.get("id") != plugin_id:
                continue
            raw_samples = stage.get("sampleResults")
            samples: list[dict[str, Any]] = []
            for sequence, item in enumerate(
                raw_samples if isinstance(raw_samples, list) else [], start=1
            ):
                if not isinstance(item, dict):
                    continue
                samples.append(
                    {
                        "sampleId": str(item.get("sampleId") or ""),
                        "title": str(item.get("sampleId") or ""),
                        "sequence": sequence,
                        "status": str(item.get("status") or "failed"),
                        "summary": str(item.get("summary") or ""),
                        "facts": {},
                        "artifacts": self._legacy_artifacts(item.get("blocks")),
                        "blocks": list(item.get("blocks") or []),
                    }
                )
            dataset_result = dict(stage.get("datasetResult") or {})
            return {
                "schemaVersion": "batch-postprocess-dashboard-v2",
                "legacy": True,
                "runId": run_id,
                "executionId": execution_id,
                "plugin": {
                    "id": plugin_id,
                    "name": plugin_id,
                    "version": "1",
                    "apiVersion": "batch-postprocess-v1",
                },
                "status": str(stage.get("status") or "failed"),
                "presentation": {"defaultView": "table", "sampleFields": []},
                "outputs": [],
                "datasetResult": {
                    **dataset_result,
                    "facts": {},
                    "artifacts": self._legacy_artifacts(dataset_result.get("blocks")),
                },
                "counts": {},
                "totalSamples": len(samples),
                "samples": samples,
            }
        raise KeyError(plugin_id)

    @staticmethod
    def _legacy_artifacts(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        mapping = {"table": "records"}
        artifacts: list[dict[str, Any]] = []
        for index, block in enumerate(value):
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "json")
            artifact = dict(block)
            artifact["key"] = f"legacy-{index}"
            artifact["dataType"] = mapping.get(block_type, block_type)
            artifacts.append(artifact)
        return artifacts

    @staticmethod
    def _sortable_fact(value: object, key: str) -> tuple[int, float | str]:
        fact = value.get(key) if isinstance(value, dict) else None
        if isinstance(fact, bool):
            return 0, 1.0 if fact else 0.0
        if isinstance(fact, (int, float)):
            return 0, float(fact)
        return 1, str(fact or "")

    @staticmethod
    def _sample_upstream(stage: dict[str, Any], sample_id: str) -> dict[str, Any]:
        for item in list(stage.get("sampleResults") or []):
            if isinstance(item, dict) and item.get("sampleId") == sample_id:
                return {"pluginId": stage.get("id"), "result": item}
        return {"pluginId": stage.get("id"), "result": None}

    def _plugin_dir(self, run_id: str, execution_id: str, plugin_id: str) -> Path:
        if not _SAFE_ID.fullmatch(plugin_id):
            raise KeyError(plugin_id)
        execution_dir = self._execution_dir(run_id, execution_id)
        path = (execution_dir / "plugins" / plugin_id).resolve()
        if not path.is_relative_to(execution_dir) or not path.is_dir():
            raise KeyError(plugin_id)
        return path

    def _execution_dir(self, run_id: str, execution_id: str) -> Path:
        if not _SAFE_ID.fullmatch(execution_id):
            raise KeyError(execution_id)
        root = (self._run_dir(run_id) / "postprocess").resolve()
        path = (root / execution_id).resolve()
        if not path.is_relative_to(root) or not path.is_dir():
            raise KeyError(execution_id)
        return path

    def _run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        path = (self.output_root / run_id).resolve()
        if not path.is_relative_to(self.output_root) or not path.is_dir():
            raise KeyError(run_id)
        return path

    def _ensure_run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        path = (self.output_root / run_id).resolve()
        if not path.is_relative_to(self.output_root):
            raise KeyError(run_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"JSON 文件不是对象: {path.name}")
        return value
