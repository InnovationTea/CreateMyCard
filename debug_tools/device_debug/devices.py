"""HDC 目标、本地虚拟机与单设备共享截图采集器。"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
from PIL import Image

from .commands import DeviceError, command
from .config import Config
from .locks import device_lock

LOGGER = logging.getLogger(__name__)


def identity(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class Target:
    id: str
    serial: str
    name: str
    kind: str


@dataclass(frozen=True)
class Emulator:
    id: str
    name: str
    path: str
    ready: bool
    serial: str | None = None


class Devices:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.targets: dict[str, Target] = {}
        self.operations: dict[str, dict[str, Any]] = {}
        self.launch_tasks: set[asyncio.Task] = set()
        self.collectors: dict[str, Screen] = {}

    async def hdc(self, serial: str, args: list[str], **kwargs: Any) -> str:
        return await command([str(self.config.hdc), "-t", serial, *args], **kwargs)

    async def refresh(self) -> list[Target]:
        if not self.config.hdc.is_file():
            raise DeviceError("未找到 HDC，请检查本机配置", 503)
        output = await command([str(self.config.hdc), "list", "targets"])
        serials: list[str] = []
        for line in output.splitlines():
            serial = line.strip()
            if not serial or "empty" in serial.lower():
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.:\-]+", serial):
                continue
            if serial not in serials:
                serials.append(serial)

        async def inspect(serial: str) -> Target:
            name = serial
            kind = "unknown"
            try:
                model, product = await asyncio.gather(
                    self.hdc(serial, ["shell", "param", "get", "const.product.model"]),
                    self.hdc(serial, ["shell", "param", "get", "const.product.name"]),
                )
                model = model.strip()
                if model:
                    name = model
                if "emulator" in product.lower() or "emulator" in model.lower():
                    kind = "emulator"
                elif self._emulator_serial(serial):
                    kind = "emulator"
                else:
                    kind = "physical"
            except (DeviceError, TimeoutError, OSError) as exc:
                LOGGER.info("设备信息查询失败 %s: %s", type(exc).__name__, exc)
            return Target(identity(serial), serial, name, kind)

        inspected = await asyncio.gather(*(inspect(serial) for serial in serials))
        found = {target.id: target for target in inspected}
        self.targets = found
        return list(found.values())

    def _emulator_serial(self, serial: str) -> bool:
        # 实例运行配置中的 HDC 端口可证明关联；不按 IP 外观猜测模拟器。
        for emulator in self.emulators():
            path = Path(emulator.path) / "hardware-qemu.ini"
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"(?m)^hw\.hdc\.port\s*=\s*(\d+)\s*$", text)
            if match and serial == f"127.0.0.1:{match.group(1)}":
                return True
        return False

    def emulators(self) -> list[Emulator]:
        path = self.config.instances / "lists.json"
        if not path.is_file():
            return []
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list):
            raise DeviceError("虚拟机清单格式错误", 503)
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name, location = row.get("name"), row.get("path")
            if not isinstance(name, str) or not isinstance(location, str):
                continue
            instance = Path(location).resolve()
            if not instance.is_relative_to(self.config.instances.resolve()):
                continue
            image = row.get("imageDir")
            ready = False
            if isinstance(image, str):
                image_path = (self.config.images / image).resolve()
                within_root = image_path.is_relative_to(self.config.images.resolve())
                ready = within_root and (image_path / "system.img").is_file()
            serial = None
            hdc_path = instance / "hardware-qemu.ini"
            if hdc_path.is_file():
                text = hdc_path.read_text(encoding="utf-8", errors="replace")
                match = re.search(r"(?m)^hw\.hdc\.port\s*=\s*(\d+)\s*$", text)
                if match:
                    serial = f"127.0.0.1:{match.group(1)}"
            result.append(Emulator(identity(str(instance)), name, str(instance), ready, serial))
        return result

    async def target(self, target_id: str) -> Target:
        await self.refresh()
        target = self.targets.get(target_id)
        if target is None:
            raise DeviceError("所选设备已离线，请刷新后重新选择")
        return target

    async def start(self, emulator_id: str) -> dict[str, Any]:
        existing = self.operations.get(emulator_id)
        if existing and existing.get("status") == "running":
            return existing
        selected = None
        for emulator in self.emulators():
            if emulator.id == emulator_id:
                selected = emulator
        if selected is None:
            raise DeviceError("虚拟机不存在", 404)
        initial_targets = await self.refresh()
        online = self._target_for_emulator(selected, initial_targets)
        if online is not None:
            operation = self._successful_operation(emulator_id, online, "模拟器已在线")
            self.operations[emulator_id] = operation
            return operation
        if not selected.ready:
            raise DeviceError("虚拟机镜像不存在，请检查镜像目录", 503)
        if not self.config.emulator.is_file():
            raise DeviceError("模拟器启动程序不存在", 503)
        already_running = self._is_running(selected)
        message = "正在等待运行中的模拟器连接 HDC" if already_running else "正在启动本地模拟器"
        operation: dict[str, Any] = {
            "id": emulator_id,
            "status": "running",
            "message": message,
            "targetId": None,
            "serial": selected.serial,
        }
        self.operations[emulator_id] = operation
        initial_serials = {target.serial for target in initial_targets}
        task = asyncio.create_task(
            self._launch(selected, operation, already_running, initial_serials)
        )
        self.launch_tasks.add(task)
        task.add_done_callback(self.launch_tasks.discard)
        return operation

    @staticmethod
    def _target_for_emulator(emulator: Emulator, targets: list[Target]) -> Target | None:
        if emulator.serial is None:
            return None
        for target in targets:
            if target.serial == emulator.serial:
                return target
        return None

    @staticmethod
    def _successful_operation(emulator_id: str, target: Target, message: str) -> dict[str, Any]:
        return {
            "id": emulator_id,
            "status": "success",
            "message": message,
            "targetId": target.id,
            "serial": target.serial,
        }

    def _is_running(self, emulator: Emulator) -> bool:
        expected = self.config.emulator.resolve()
        for process in psutil.process_iter(["exe", "cmdline"]):
            try:
                executable = process.info.get("exe")
                arguments = process.info.get("cmdline") or []
                if not executable or Path(executable).resolve() != expected:
                    continue
                for index, argument in enumerate(arguments[:-1]):
                    if argument == "-hvd" and arguments[index + 1] == emulator.name:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                LOGGER.debug("跳过不可查询的进程 %s: %s", type(exc).__name__, exc)
        return False

    async def _launch(
        self,
        emulator: Emulator,
        operation: dict[str, Any],
        already_running: bool,
        initial_serials: set[str],
    ) -> None:
        try:
            process = None
            if not already_running:
                options = {}
                if os.name == "nt":
                    options["creationflags"] = subprocess.CREATE_NO_WINDOW
                process = await asyncio.create_subprocess_exec(
                    str(self.config.emulator),
                    "-hvd",
                    emulator.name,
                    "-path",
                    str(self.config.instances),
                    "-imageRoot",
                    str(self.config.images),
                    cwd=self.config.emulator.parent,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    **options,
                )
            deadline = time.monotonic() + self.config.start_timeout
            while time.monotonic() < deadline:
                await asyncio.sleep(self.config.start_poll)
                targets = await self.refresh()
                current = next(
                    (item for item in self.emulators() if item.id == emulator.id),
                    emulator,
                )
                target = self._target_for_emulator(current, targets)
                if target is None and current.serial is None:
                    new_emulators = [
                        item
                        for item in targets
                        if item.serial not in initial_serials and item.kind == "emulator"
                    ]
                    if len(new_emulators) == 1:
                        target = new_emulators[0]
                if target is not None:
                    operation.update(
                        self._successful_operation(
                            emulator.id,
                            target,
                            "模拟器已连接 HDC，可以开始截图",
                        )
                    )
                    return
                process_exited = process is not None and process.returncode is not None
                if process_exited:
                    raise DeviceError(f"模拟器在连接 HDC 前退出：{process.returncode}")
            raise DeviceError("等待模拟器连接 HDC 超时，请检查模拟器日志、内存及 HDC 端口")
        except asyncio.CancelledError:
            operation.update(status="interrupted", message="后端关闭，启动等待已中断")
            raise
        except (DeviceError, TimeoutError, OSError, ValueError) as exc:
            operation.update(status="failed", message=str(exc))

    def screen(self, target: Target) -> Screen:
        screen = self.collectors.get(target.id)
        if screen is None:
            screen = Screen(self, target)
            self.collectors[target.id] = screen
        return screen

    async def close(self) -> None:
        tasks = list(self.launch_tasks)
        for task in tasks:
            task.cancel()
        for screen in self.collectors.values():
            if screen.task is not None:
                screen.task.cancel()
                tasks.append(screen.task)
        await asyncio.gather(*tasks, return_exceptions=True)


class Screen:
    def __init__(self, devices: Devices, target: Target) -> None:
        self.devices = devices
        self.target = target
        self.listeners: set[asyncio.Queue] = set()
        self.task: asyncio.Task | None = None

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self.listeners.add(queue)
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._collect())
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.listeners.discard(queue)
        if not self.listeners and self.task is not None:
            task = self.task
            self.task = None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def publish(self, info: dict[str, Any], data: bytes | None = None) -> None:
        for queue in self.listeners:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait((info, data))

    async def capture(self, local: Path, remote: str) -> bytes:
        async with device_lock(self.target.serial):
            error: Exception | None = None
            for attempt in range(2):
                local.unlink(missing_ok=True)
                try:
                    result = await self.devices.hdc(
                        self.target.serial,
                        ["shell", "snapshot_display", "-f", remote],
                        timeout=5.0,
                    )
                    if "error" in result.lower() or "failed" in result.lower():
                        raise DeviceError(f"设备截图失败：{result.strip()}")
                    await self.devices.hdc(
                        self.target.serial,
                        ["file", "recv", remote, str(local)],
                        timeout=5.0,
                    )
                    error = None
                    break
                except (DeviceError, TimeoutError, OSError) as exc:
                    error = exc
                    if attempt == 0:
                        await asyncio.sleep(0.2)
            if error is not None:
                raise error
        data = local.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return data

    async def _collect(self) -> None:
        directory = self.devices.config.output / "screens"
        directory.mkdir(parents=True, exist_ok=True)
        capture_id = uuid.uuid4().hex
        local = directory / f"{capture_id}.jpeg"
        remote = f"/data/local/tmp/widget_screen_{capture_id}.jpeg"
        sequence = 0
        previous: float | None = None
        try:
            while self.listeners:
                started = time.monotonic()
                if device_lock(self.target.serial).locked():
                    self.publish({"status": "waiting", "message": "设备正在部署，预览暂缓"})
                    await asyncio.sleep(1.0)
                    continue
                try:
                    data = await asyncio.wait_for(self.capture(local, remote), timeout=5.0)
                    now = time.monotonic()
                    sequence += 1
                    fps = 0.0 if previous is None else 1.0 / max(now - previous, 0.001)
                    previous = now
                    with Image.open(io.BytesIO(data)) as image:
                        width, height = image.size
                    self.publish(
                        {
                            "status": "frame",
                            "sequence": sequence,
                            "fps": round(fps, 2),
                            "capturedAt": datetime.now(UTC).isoformat(),
                            "width": width,
                            "height": height,
                        },
                        data,
                    )
                except (DeviceError, TimeoutError, OSError, ValueError) as exc:
                    self.publish({"status": "error", "message": str(exc) or "采集超时，旧帧已过期"})
                    try:
                        targets = await self.devices.refresh()
                        online = any(target.id == self.target.id for target in targets)
                        if not online:
                            self.publish({"status": "error", "message": "设备已断开，请重新连接"})
                            break
                    except (DeviceError, TimeoutError, OSError) as discovery_error:
                        LOGGER.info("截图失败后设备查询失败：%s", discovery_error)
                await asyncio.sleep(max(0.0, 1.0 - (time.monotonic() - started)))
        finally:
            local.unlink(missing_ok=True)
            try:
                await self.devices.hdc(
                    self.target.serial,
                    ["shell", "rm", "-f", remote],
                    timeout=2.0,
                )
            except (DeviceError, TimeoutError, OSError) as exc:
                LOGGER.info("截图临时文件清理失败 %s: %s", type(exc).__name__, exc)
