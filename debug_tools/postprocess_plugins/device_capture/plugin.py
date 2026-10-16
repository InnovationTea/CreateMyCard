"""真机截图 v2 插件：只负责编排，共享 device_debug 渲染核心。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...device_debug.commands import DeviceError
from ...device_debug.config import Config
from ...device_debug.devices import Devices
from ...device_debug.runner import DeviceRenderer, RenderFailure

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class DeviceCaptureManager:
    """共享渲染核心的宿主，并为旧产物提供只读兼容。"""

    def __init__(
        self,
        output_root: Path,
        *,
        renderer: DeviceRenderer | Any | None = None,
    ) -> None:
        self.output_root = output_root.resolve()
        self.config: Config | None = None
        self.configuration_error: str | None = None
        if renderer is None:
            try:
                self.config = Config.load()
            except DeviceError as exc:
                self.configuration_error = str(exc)
                logging.getLogger(__name__).warning(
                    "设备截图暂不可用，调试平台继续启动；使用前请完善配置：%s", exc
                )
        self.devices = Devices(self.config) if self.config is not None else None
        self.renderer = renderer
        if self.config is not None:
            self.renderer = DeviceRenderer(self.config, self.devices)

    async def start(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        if self.devices is not None:
            await self.devices.close()

    async def availability(self) -> dict[str, Any]:
        if self.configuration_error is not None:
            return {
                "available": False,
                "checks": [{"name": "工具链配置", "ok": False, "detail": self.configuration_error}],
                "targets": [],
                "error": self.configuration_error,
            }
        if self.config is None:
            method = getattr(self.renderer, "availability", None)
            return await method() if method is not None else {"available": True, "checks": []}
        checks = await asyncio.to_thread(self.config.checks)
        try:
            targets = await self.devices.refresh() if self.devices is not None else []
            error = ""
        except Exception as exc:
            targets = []
            error = str(exc)
        return {
            "available": all(bool(item.get("ok")) for item in checks[:7]) and bool(targets),
            "checks": checks,
            "targets": [
                {"id": target.id, "name": target.name, "kind": target.kind} for target in targets
            ],
            "error": error,
        }

    def status(self, run_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        run_dir = (self.output_root / run_id).resolve()
        if not run_dir.is_relative_to(self.output_root) or not run_dir.is_dir():
            return {"status": "not_requested"}
        path = run_dir / "device_capture.json"
        if not path.is_file():
            return {"status": "not_requested"}
        return self._read_json(path)

    def sample(self, run_id: str, sample_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(sample_id):
            raise KeyError(sample_id)
        items = self.status(run_id).get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id") == sample_id:
                    return dict(item)
        return {"id": sample_id, "status": "not_requested", "error": ""}

    def image_path(self, run_id: str, sample_id: str, kind: str) -> Path:
        if not _SAFE_ID.fullmatch(sample_id) or kind not in {"card", "full"}:
            raise KeyError(sample_id)
        run_dir = self._legacy_run_dir(run_id)
        suffix = ".png" if kind == "card" else ".jpeg"
        path = (run_dir / "device_capture" / kind / f"{sample_id}{suffix}").resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise KeyError(sample_id)
        return path

    def gallery_path(self, run_id: str) -> Path:
        run_dir = self._legacy_run_dir(run_id)
        path = (run_dir / "device_gallery.html").resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise KeyError(run_id)
        return path

    def _legacy_run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        path = (self.output_root / run_id).resolve()
        if not path.is_relative_to(self.output_root) or not path.is_dir():
            raise KeyError(run_id)
        return path

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"JSON 根节点不是对象：{path.name}")
        return value

    @staticmethod
    def resolve_size(run_dir: Path, sample: dict[str, Any]) -> str:
        sample_id = str(sample.get("id") or "")
        result_path = run_dir / sample_id / "result.json"
        if result_path.is_file():
            result = DeviceCaptureManager._read_json(result_path)
            final_attempt = result.get("finalAttempt")
            if isinstance(final_attempt, int):
                blocks_path = run_dir / sample_id / f"attempt_{final_attempt:03d}" / "blocks.json"
                if blocks_path.is_file():
                    blocks = DeviceCaptureManager._read_json(blocks_path)
                    cardspec = blocks.get("cardSpec") or blocks.get("cardspec")
                    if isinstance(cardspec, dict):
                        suggested = str(cardspec.get("suggestSize") or "").lower()
                        if suggested in {"2x2", "2x4"}:
                            return suggested
        query = str(sample.get("query") or "").lower()
        matches = re.findall(r"(?<!\d)2\s*[x×*]\s*([24])(?!\d)", query)
        if matches:
            return f"2x{matches[-1]}"
        stored = str(sample.get("size") or "").lower()
        return stored if stored in {"2x2", "2x4"} else "2x2"


async def run_builtin(
    manager: DeviceCaptureManager,
    run_id: str,
    output_dir: Path,
    config: dict[str, Any],
    checkpoint: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """用一次 Render Session 串行处理整批样本。"""

    target_id = config.get("targetId")
    if not isinstance(target_id, str) or not target_id:
        raise ValueError("真机截图必须选择当前在线设备")
    device_config = getattr(manager, "config", None)
    capture_delay = device_config.capture_delay_seconds if device_config is not None else 1.0
    if not hasattr(manager, "renderer"):
        return await _run_legacy_host(manager, run_id)
    if manager.renderer is None:
        raise DeviceError(manager.configuration_error or "设备工具未配置", 503)
    run_dir = manager._legacy_run_dir(run_id)
    summary = manager._read_json(run_dir / "summary.json")
    samples_value = summary.get("samples", [])
    samples = [item for item in samples_value if isinstance(item, dict)]
    output_dir.mkdir(parents=True, exist_ok=True)
    log = output_dir / "device.log"
    session = await manager.renderer.session(target_id, log)
    sample_results: list[dict[str, Any]] = []
    warning_count = 0
    async with session:
        for index, sample in enumerate(samples):
            sample_id = str(sample.get("id") or "")
            size = manager.resolve_size(run_dir, sample)
            result = await _capture_sample(
                session, run_dir, output_dir, sample_id, size, capture_delay
            )
            sample_results.append(result)
            warnings = result.get("facts", {}).get("warnings", [])
            if isinstance(warnings, list) and warnings:
                warning_count += 1
            if checkpoint is not None:
                checkpoint_result = checkpoint(_checkpoint(sample_results, index + 1, len(samples)))
                if inspect.isawaitable(checkpoint_result):
                    await checkpoint_result
    succeeded = sum(1 for item in sample_results if item.get("status") == "success")
    failed = sum(1 for item in sample_results if item.get("status") == "failed")
    skipped = len(sample_results) - succeeded - failed
    status = "success" if failed == 0 and skipped == 0 else "partial"
    return {
        "status": status,
        "sampleResults": sample_results,
        "datasetResult": {
            "status": status,
            "summary": f"真机截图已完成：成功 {succeeded}，失败 {failed}，跳过 {skipped}",
            "facts": {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "warningSamples": warning_count,
                "targetId": target_id,
                "captureDelaySeconds": capture_delay,
            },
            "artifacts": [
                {
                    "key": "capture-summary",
                    "data": [
                        {"label": "成功", "value": succeeded},
                        {"label": "警告", "value": warning_count},
                        {"label": "失败", "value": failed},
                        {"label": "跳过", "value": skipped},
                    ],
                },
            ],
        },
    }


async def _capture_sample(
    session: Any,
    run_dir: Path,
    output_dir: Path,
    sample_id: str,
    size: str,
    capture_delay_seconds: float,
) -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(sample_id):
        return {"sampleId": sample_id, "status": "failed", "summary": "样本标识无效"}
    result_path = run_dir / sample_id / "result.json"
    if not result_path.is_file():
        return {"sampleId": sample_id, "status": "skipped", "summary": "样本没有最终结果"}
    result = DeviceCaptureManager._read_json(result_path)
    final_attempt = result.get("finalAttempt")
    if not isinstance(final_attempt, int):
        return {"sampleId": sample_id, "status": "skipped", "summary": "样本没有最终 attempt"}
    genui = run_dir / sample_id / f"attempt_{final_attempt:03d}" / "genui.jsonl"
    if not genui.is_file():
        return {"sampleId": sample_id, "status": "skipped", "summary": "样本没有可渲染的 GenUI"}
    card = output_dir / "card" / f"{sample_id}.png"
    full = output_dir / "full" / f"{sample_id}.png"
    try:
        capture = await session.render(
            genui, size, card, full, capture_delay_seconds=capture_delay_seconds
        )
    except asyncio.CancelledError:
        raise
    except RenderFailure as exc:
        return {
            "sampleId": sample_id,
            "status": "failed",
            "summary": str(exc),
            "facts": {
                "captureStatus": "failed",
                "size": size,
                "terminal": exc.event.state,
                "code": exc.event.code,
                "warnings": exc.event.warnings,
            },
            "artifacts": [],
        }
    except Exception as exc:
        return {
            "sampleId": sample_id,
            "status": "failed",
            "summary": f"{type(exc).__name__}: {exc}",
            "facts": {"captureStatus": "failed", "size": size},
            "artifacts": [],
        }
    metadata = capture.public()
    metadata["captureDelaySeconds"] = capture_delay_seconds
    facts = dict(metadata)
    facts.pop("cropPx", None)
    facts.update(captureStatus="success", size=size)
    return {
        "sampleId": sample_id,
        "status": "success",
        "summary": "真机截图已生成",
        "facts": facts,
        "artifacts": [
            {"key": "device-capture-metadata", "data": metadata},
            {
                "key": "device-capture",
                "path": f"card/{sample_id}.png",
                "alt": f"{sample_id} 真机截图",
            },
            {
                "key": "device-full-capture",
                "path": f"full/{sample_id}.png",
                "alt": f"{sample_id} 设备全屏原图",
            },
        ],
    }


def _checkpoint(results: list[dict[str, Any]], completed: int, total: int) -> dict[str, Any]:
    return {
        "status": "partial",
        "sampleResults": results,
        "datasetResult": {
            "status": "skipped",
            "summary": f"正在截图 {completed}/{total}",
            "facts": {},
            "artifacts": [],
        },
        "progress": {
            "phase": "samples",
            "completed": completed,
            "total": total,
            "message": f"正在截图 {completed}/{total}",
        },
    }


async def _run_legacy_host(manager: Any, run_id: str) -> dict[str, Any]:
    """仅适配外部注入的旧宿主；内置实现不会进入此分支。"""

    await manager.require_available()
    manager.enqueue(run_id, retry=True)
    queue = getattr(manager, "queue", None)
    if queue is not None:
        await queue.join()
    return {
        "status": "success",
        "sampleResults": [],
        "datasetResult": {
            "status": "success",
            "summary": "旧宿主截图已完成",
            "facts": {},
            "artifacts": [{"key": "capture-summary", "data": []}],
        },
    }
