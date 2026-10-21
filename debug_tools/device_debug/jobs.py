"""设备渲染任务：输入转换、共享 Session 调用和可恢复结果。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from debug_tools.postprocess_plugins._io import atomic_write_json

from .commands import DeviceError, redact
from .config import Config
from .conversion import convert
from .devices import Devices
from .runner import DeviceRenderer, RenderFailure

LOGGER = logging.getLogger(__name__)
TERMINAL = {"success", "failed", "cancelled", "interrupted"}


class Jobs:
    def __init__(
        self,
        config: Config,
        devices: Devices,
        renderer: DeviceRenderer | None = None,
    ) -> None:
        self.config = config
        self.devices = devices
        self.renderer = renderer or DeviceRenderer(config, devices)
        self.states: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        self.config.output.mkdir(parents=True, exist_ok=True)
        for path in self.config.output.glob("*/state.json"):
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(state, dict) or state.get("id") != path.parent.name:
                    continue
                job_id = path.parent.name
                if state.get("status") not in TERMINAL:
                    state.update(status="interrupted", error="后端重启，任务已中断，请重新提交")
                    atomic_write_json(path, state)
                self.states[job_id] = state
            except (OSError, ValueError) as exc:
                LOGGER.warning("读取设备任务失败 %s: %s", type(exc).__name__, exc)

    def get(self, job_id: str) -> dict[str, Any]:
        state = self.states.get(job_id)
        if state is None:
            raise DeviceError("任务不存在", 404)
        return state

    def update(self, job_id: str, **values: Any) -> None:
        state = self.get(job_id)
        state.update(values, updatedAt=datetime.now(UTC).isoformat())
        atomic_write_json(self.config.output / job_id / "state.json", state)

    async def submit(
        self,
        target_id: str,
        source: str,
        input_format: str,
        size: str,
        *,
        capture_mode: str = "preview",
        prepare_only: bool = False,
    ) -> dict:
        target = await self.devices.target(target_id)
        converted = None
        if not prepare_only:
            converted = await asyncio.to_thread(convert, source, input_format, size)
        job_id = uuid.uuid4().hex
        directory = self.config.output / job_id
        directory.mkdir(parents=True)
        (directory / "input.txt").write_text(source, encoding="utf-8")
        if converted is not None:
            (directory / "a2ui.jsonl").write_text(converted.text, encoding="utf-8")
        state = {
            "id": job_id,
            "targetId": target.id,
            "device": target.name,
            "size": size,
            "format": converted.format if converted is not None else "a2ui",
            "prepareOnly": prepare_only,
            "captureMode": capture_mode,
            "status": "queued",
            "stage": "排队",
            "error": None,
            "installed": False,
            "terminal": None,
            "warnings": [],
            "cropPx": None,
            "cardImageUrl": None,
            "fullImageUrl": None,
        }
        self.states[job_id] = state
        self.update(job_id)
        self.tasks[job_id] = asyncio.create_task(self._execute(job_id))
        return state

    async def _execute(self, job_id: str) -> None:
        directory = self.config.output / job_id

        async def notify(stage: str) -> None:
            self.update(job_id, status="running", stage=stage)

        try:
            options = {}
            if self.get(job_id).get("captureMode", "preview") == "desktop":
                options["capture_mode"] = "desktop"
            session = await self.renderer.session(
                str(self.get(job_id).get("targetId")),
                directory / "build.log",
                notify,
                **options,
            )
            async with session:
                self.update(job_id, installed=True, stage="渲染与截图")
                if self.get(job_id).get("prepareOnly"):
                    self.update(
                        job_id,
                        status="success",
                        stage=(
                            "编译安装完成，请添加 2x2、2x4 卡片，"
                            "并将两张卡片与应用入口放在同一桌面页"
                        ),
                    )
                    return
                result = await session.render(
                    directory / "a2ui.jsonl",
                    str(self.get(job_id).get("size")),
                    directory / "card.png",
                    directory / "full.png",
                )
            values = result.public()
            values.update(
                status="success",
                stage="完成",
                cardImageUrl=f"/debug/device/runs/{job_id}/images/card",
                fullImageUrl=f"/debug/device/runs/{job_id}/images/full",
            )
            self.update(job_id, **values)
        except asyncio.CancelledError:
            if self.get(job_id).get("status") != "interrupted":
                self.update(job_id, status="cancelled", error="任务已取消")
            raise
        except RenderFailure as exc:
            self.update(
                job_id,
                status="failed",
                stage="失败",
                error=redact(str(exc)),
                terminal=exc.event.state,
                code=exc.event.code,
                warnings=exc.event.warnings,
            )
        except Exception as exc:
            LOGGER.exception("设备任务失败：%s", job_id)
            self.update(job_id, status="failed", stage="失败", error=redact(str(exc)))

    def image_path(self, job_id: str, kind: str) -> Path:
        self.get(job_id)
        names = {"card": "card.png", "full": "full.png"}
        name = names.get(kind)
        if name is None:
            raise DeviceError("不支持的截图类型", 404)
        root = self.config.output.resolve()
        path = (root / job_id / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise DeviceError("截图不存在", 404)
        return path

    async def cancel(self, job_id: str) -> dict[str, Any]:
        state = self.get(job_id)
        task = self.tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if state.get("status") not in TERMINAL:
                self.update(job_id, status="cancelled", error="任务已取消")
        return state

    def logs(self, job_id: str, offset: int) -> dict[str, Any]:
        self.get(job_id)
        path = self.config.output / job_id / "build.log"
        data = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        value = data[offset : offset + 32000]
        return {"text": value, "offset": offset + len(value)}

    async def close(self) -> None:
        for job_id, task in self.tasks.items():
            if not task.done():
                self.update(job_id, status="interrupted", error="后端关闭，任务已中断")
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
