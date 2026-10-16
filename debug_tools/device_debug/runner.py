"""A2UI_Render 构建、设备会话、终态解析与截图的共享核心。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from .commands import DeviceError, command, executable_command, install_ohpm_dependencies
from .config import Config, Project
from .devices import Devices, Target
from .locks import build_lock, device_lock

LogCallback = Callable[[str], Awaitable[None] | None]
TERMINAL_STATES = {"READY", "READY_WITH_WARNINGS", "FAILED"}
SIZE_VP = {"2x2": (150, 150), "2x4": (300, 150)}
SAMPLE_CHUNK_SIZE = 6_000
LOCKED_START_RETRY_DELAYS = (0.8, 1.2, 2.0)


@dataclass(frozen=True)
class CropPx:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class TerminalEvent:
    run_id: str
    state: str
    code: str
    message: str
    warnings: list[str]
    crop: CropPx | None


@dataclass(frozen=True)
class CaptureResult:
    run_id: str
    terminal: str
    code: str
    message: str
    warnings: list[str]
    crop_px: CropPx
    card_path: Path
    full_path: Path

    def public(self) -> dict[str, Any]:
        return {
            "deviceRunId": self.run_id,
            "terminal": self.terminal,
            "code": self.code,
            "message": self.message,
            "warnings": self.warnings,
            "cropPx": asdict(self.crop_px),
        }


class RenderFailure(DeviceError):
    def __init__(self, event: TerminalEvent) -> None:
        self.event = event
        detail = event.message or event.code or "App 渲染失败"
        super().__init__(f"A2UI_RUN {event.code or 'FAILED'}：{detail}")


def parse_terminal_events(text: str, run_id: str) -> list[TerminalEvent]:
    events: list[TerminalEvent] = []
    for match in re.finditer(r"A2UI_RUN\s+(\{.*\})", text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("runId") != run_id:
            continue
        state = payload.get("state")
        if state not in TERMINAL_STATES:
            continue
        warnings_value = payload.get("warnings", [])
        warnings = (
            [str(value) for value in warnings_value]
            if isinstance(warnings_value, list)
            else []
        )
        crop_value = payload.get("cropPx")
        crop = _parse_crop(crop_value) if crop_value is not None else None
        events.append(
            TerminalEvent(
                run_id=run_id,
                state=state,
                code=str(payload.get("code") or ""),
                message=str(payload.get("message") or ""),
                warnings=warnings,
                crop=crop,
            )
        )
    return events


def _parse_crop(value: Any) -> CropPx:
    if not isinstance(value, dict):
        raise DeviceError("App 返回的 cropPx 不是对象")
    names = ("left", "top", "width", "height")
    numbers: list[int] = []
    for name in names:
        item = value.get(name)
        if not isinstance(item, int) or isinstance(item, bool):
            raise DeviceError(f"App 返回的 cropPx.{name} 不是整数")
        numbers.append(item)
    crop = CropPx(*numbers)
    if crop.left < 0 or crop.top < 0 or crop.width <= 0 or crop.height <= 0:
        raise DeviceError("App 返回的 cropPx 包含负坐标或非正尺寸")
    return crop


def validate_crop(crop: CropPx, image_width: int, image_height: int) -> None:
    if crop.left < 0 or crop.top < 0 or crop.width <= 0 or crop.height <= 0:
        raise DeviceError("App 返回的 cropPx 包含负坐标或非正尺寸")
    if crop.left + crop.width > image_width or crop.top + crop.height > image_height:
        raise DeviceError(
            "App 返回的 cropPx 越过截图边界："
            f"{crop.left},{crop.top},{crop.width},{crop.height} / {image_width}x{image_height}"
        )


class RenderProject:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.path = config.project.resolve()
        self.info = Project.read(self.path)

    def _fingerprint(self) -> str:
        digest = hashlib.sha256()
        excluded = {"build", ".hvigor", ".preview", "oh_modules", "node_modules", "test-output"}
        for path in sorted(self.path.rglob("*")):
            relative_parts = path.relative_to(self.path).parts
            if not path.is_file() or any(part in excluded for part in relative_parts):
                continue
            relative = path.relative_to(self.path).as_posix()
            if relative in {"local.properties", ".gitignore"}:
                continue
            digest.update(relative.encode("utf-8"))
            digest.update(path.read_bytes())
        digest.update(str(self.config.sdk).encode("utf-8"))
        digest.update(str(self.config.hvigor).encode("utf-8"))
        return digest.hexdigest()

    async def build(self, target_kind: str, log: Path) -> Path:
        async with build_lock(str(self.path)):
            fingerprint = await asyncio.to_thread(self._fingerprint)
            cached = self._cached_hap(target_kind, fingerprint)
            if cached is not None:
                return cached
            dependency = self.path / "oh_modules/@arkui-genius/genui_form/Index.d.ets"
            if not dependency.is_file():
                await install_ohpm_dependencies(
                    ohpm=self.config.ohpm,
                    node=self.config.node,
                    cwd=self.path,
                    env=self.config.environment(),
                    timeout=self.config.build_timeout,
                    log=log,
                )
            if not self.config.hvigor.is_file():
                raise DeviceError(f"配置的 Hvigor 可执行文件不存在：{self.config.hvigor}")
            await command(
                [
                    *executable_command(self.config.hvigor, self.config.node),
                    "assembleHap",
                    "--mode",
                    "module",
                    "-p",
                    "product=default",
                    "-p",
                    "module=entry@default",
                    "-p",
                    "buildMode=debug",
                    "--no-daemon",
                ],
                cwd=self.path,
                env=self.config.environment(),
                timeout=self.config.build_timeout,
                log=log,
            )
            hap = self._select_hap(target_kind)
            marker = self.path / ".hvigor/debug-tools-build.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"fingerprint": fingerprint, "hap": str(hap)}, ensure_ascii=False),
                encoding="utf-8",
            )
            return hap

    def _cached_hap(self, target_kind: str, fingerprint: str) -> Path | None:
        marker = self.path / ".hvigor/debug-tools-build.json"
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("fingerprint") != fingerprint:
            return None
        hap_value = value.get("hap")
        if not isinstance(hap_value, str):
            return None
        hap = Path(hap_value)
        if not hap.is_file() or not hap.resolve().is_relative_to(self.path):
            return None
        if target_kind != "emulator" and hap.name.endswith("-unsigned.hap"):
            return None
        return hap

    def _select_hap(self, target_kind: str) -> Path:
        output = self.path / "entry/build/default/outputs/default"
        candidates = sorted(
            output.glob("*.hap"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        signed = [path for path in candidates if not path.name.endswith("-unsigned.hap")]
        unsigned = [path for path in candidates if path.name.endswith("-unsigned.hap")]
        if signed:
            return signed[0]
        if target_kind == "emulator" and unsigned:
            return unsigned[0]
        if unsigned:
            raise DeviceError("真机或未知目标必须使用 signed HAP，请先配置内置工程签名")
        raise DeviceError("Hvigor 未生成可安装 HAP")


class RenderSession:
    def __init__(
        self,
        config: Config,
        devices: Devices,
        target: Target,
        log: Path,
        notify: LogCallback | None = None,
    ) -> None:
        self.config = config
        self.devices = devices
        self.target = target
        self.log = log
        self.notify = notify
        self.project = RenderProject(config)
        self._lock: asyncio.Lock | None = None
        self._prepared = False
        self._sandbox_transport = False
        self._remote_files: set[str] = set()

    async def __aenter__(self) -> RenderSession:
        self._lock = device_lock(self.target.serial)
        await self._lock.acquire()
        try:
            current = await self.devices.target(self.target.id)
            if current.kind != self.target.kind:
                raise DeviceError("设备类型已经变化，请刷新后重新选择")
            await self._say("构建内置 A2UI_Render 工程")
            hap = await self.project.build(current.kind, self.log)
            await self._say(f"安装 {hap.name}")
            await self.devices.hdc(
                current.serial,
                ["install", "-r", str(hap)],
                timeout=120.0,
                log=self.log,
            )
            await self._start_app([])
            # The application sandbox is created asynchronously after the first
            # Ability launch. This also avoids racing HDC's debug-bundle lookup.
            await asyncio.sleep(0.8)
            self._sandbox_transport = await self._prepare_sandbox(current.serial)
            self._prepared = True
            return self
        except BaseException:
            self._release()
            raise

    async def __aexit__(self, _type, _value, _traceback) -> None:
        try:
            await self._cleanup_remote()
        finally:
            self._prepared = False
            self._release()

    def _release(self) -> None:
        if self._lock is not None and self._lock.locked():
            self._lock.release()
        self._lock = None

    async def render(
        self,
        source: Path,
        size: str,
        card_path: Path,
        full_path: Path,
        *,
        capture_delay_seconds: float = 0.0,
    ) -> CaptureResult:
        if not self._prepared:
            raise DeviceError("Render Session 尚未准备完成")
        dimensions = SIZE_VP.get(size)
        if dimensions is None:
            raise DeviceError(f"不支持的卡片尺寸：{size}")
        run_id = str(uuid.uuid4())
        sample_file = f"{run_id}.json"
        remote = f"data/storage/el2/base/files/a2ui/{sample_file}"
        await self._say(f"推送样本 {source.name}（{size}）")
        parameters = self._parameters(run_id, sample_file, *dimensions)
        if self._sandbox_transport:
            self._remote_files.add(remote)
            output = await self.devices.hdc(
                self.target.serial,
                ["file", "send", "-b", self.project.info.bundle, str(source), remote],
                log=self.log,
            )
            self._require_hdc_success(output, "推送应用沙箱样本")
            await self._start_app(parameters)
        else:
            await self._send_sample_chunks(source, parameters)
        terminal = await self._wait_terminal(run_id)
        if terminal.state == "FAILED":
            raise RenderFailure(terminal)
        if terminal.crop is None:
            raise DeviceError("READY 终态缺少 cropPx")
        if not await self._wait_foreground():
            raise DeviceError("App 在 READY 后未保持前台稳定")
        await self._capture(
            run_id, parameters, full_path, capture_delay_seconds=capture_delay_seconds
        )
        await asyncio.to_thread(self._crop, full_path, card_path, terminal.crop)
        return CaptureResult(
            run_id=run_id,
            terminal=terminal.state,
            code=terminal.code,
            message=terminal.message,
            warnings=terminal.warnings,
            crop_px=terminal.crop,
            card_path=card_path,
            full_path=full_path,
        )

    def _parameters(self, run_id: str, sample_file: str, width: int, height: int) -> list[str]:
        return [
            "--ps",
            "runId",
            run_id,
            "--ps",
            "sampleFile",
            sample_file,
            "--pi",
            "width",
            str(width),
            "--pi",
            "height",
            str(height),
        ]

    async def _start_app(self, parameters: list[str]) -> None:
        info = self.project.info
        arguments = [
            "shell",
            "aa",
            "start",
            "-a",
            info.ability,
            "-b",
            info.bundle,
            "-m",
            info.module,
            *parameters,
        ]
        for attempt in range(len(LOCKED_START_RETRY_DELAYS) + 1):
            output = await self.devices.hdc(
                self.target.serial,
                arguments,
                log=self.log,
            )
            if not self._hdc_failed(output):
                return
            retries_exhausted = attempt >= len(LOCKED_START_RETRY_DELAYS)
            if not self._screen_locked(output) or retries_exhausted:
                self._require_hdc_success(output, "启动 A2UI_Render Ability")
            await self._say(
                "设备屏幕锁定，等待自动解锁后重试"
                f"（{attempt + 1}/{len(LOCKED_START_RETRY_DELAYS)}）"
            )
            await asyncio.sleep(LOCKED_START_RETRY_DELAYS[attempt])

    async def _prepare_sandbox(self, serial: str) -> bool:
        probe = await self.devices.hdc(
            serial,
            ["shell", "-b", self.project.info.bundle, "pwd"],
            log=self.log,
        )
        if self._hdc_failed(probe):
            await self._say("HDC 无法访问应用沙箱，改用 Ability 分块推送样本")
            return False
        created = await self.devices.hdc(
            serial,
            [
                "shell",
                "-b",
                self.project.info.bundle,
                "mkdir",
                "-p",
                "data/storage/el2/base/files/a2ui",
            ],
            log=self.log,
        )
        if self._hdc_failed(created):
            await self._say("HDC 无法创建应用样本目录，改用 Ability 分块推送样本")
            return False
        return True

    async def _send_sample_chunks(self, source: Path, parameters: list[str]) -> None:
        encoded = base64.b64encode(await asyncio.to_thread(source.read_bytes)).decode("ascii")
        chunks = [
            encoded[offset:offset + SAMPLE_CHUNK_SIZE]
            for offset in range(0, len(encoded), SAMPLE_CHUNK_SIZE)
        ]
        if not chunks:
            raise DeviceError("A2UI 样本为空，无法推送到应用")
        for index, chunk in enumerate(chunks):
            chunk_parameters = [
                *parameters,
                "--ps",
                "sampleTransport",
                "base64-chunk",
                "--pi",
                "chunkIndex",
                str(index),
                "--pi",
                "chunkCount",
                str(len(chunks)),
                "--ps",
                "sampleChunk",
                chunk,
            ]
            await self._start_app(chunk_parameters)

    @staticmethod
    def _hdc_failed(output: str) -> bool:
        lowered = output.lower()
        return "[fail]" in lowered or "error code:" in lowered

    @staticmethod
    def _screen_locked(output: str) -> bool:
        return "10106102" in output

    @classmethod
    def _require_hdc_success(cls, output: str, action: str) -> None:
        if cls._hdc_failed(output):
            detail = output.strip() or "HDC 返回未知错误"
            raise DeviceError(f"{action}失败：{detail}")

    async def _wait_terminal(self, run_id: str) -> TerminalEvent:
        deadline = time.monotonic() + self.config.render_timeout
        while time.monotonic() < deadline:
            output = await self.devices.hdc(
                self.target.serial,
                ["shell", "hilog", "-x", "-T", "A2UIRunner", "-e", run_id, "-v", "wrap"],
                timeout=min(10.0, self.config.render_timeout),
                log=self.log,
            )
            events = parse_terminal_events(output, run_id)
            if events:
                return events[-1]
            await asyncio.sleep(0.35)
        return TerminalEvent(run_id, "FAILED", "TIMEOUT", "等待 A2UI_RUN 终态超时", [], None)

    async def _wait_foreground(self) -> bool:
        pattern = re.compile(
            rf"mission name.*{re.escape(self.project.info.bundle)}.*?state #FOREGROUND",
            re.DOTALL,
        )
        deadline = time.monotonic() + min(5.0, self.config.render_timeout)
        while time.monotonic() < deadline:
            first = await self.devices.hdc(self.target.serial, ["shell", "aa", "dump", "-a"])
            if pattern.search(first):
                await asyncio.sleep(0.25)
                second = await self.devices.hdc(self.target.serial, ["shell", "aa", "dump", "-a"])
                if pattern.search(second):
                    return True
            await asyncio.sleep(0.1)
        return False

    async def _capture(
        self, run_id: str, parameters: list[str], full_path: Path, *,
        capture_delay_seconds: float = 0.0,
    ) -> None:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        remote = f"/data/local/tmp/a2ui-{run_id}.jpeg"
        downloaded = full_path.with_suffix(".source.jpeg")
        try:
            for _attempt in range(self.config.capture_attempts):
                if capture_delay_seconds > 0:
                    await self._say(f"组件加载等待 {capture_delay_seconds:g} 秒后截图")
                    await asyncio.sleep(capture_delay_seconds)
                await self.devices.hdc(
                    self.target.serial,
                    ["shell", "snapshot_display", "-f", remote],
                    log=self.log,
                )
                await self.devices.hdc(
                    self.target.serial,
                    ["file", "recv", remote, str(downloaded)],
                    log=self.log,
                )
                await asyncio.to_thread(self._convert_png, downloaded, full_path)
                if await asyncio.to_thread(self._white_guard, full_path):
                    return
                await self._start_app(parameters)
                await self._wait_foreground()
            raise DeviceError("截图外围未显示 A2UI_Render 白色保护背景")
        finally:
            try:
                await self.devices.hdc(self.target.serial, ["shell", "rm", "-f", remote])
            except DeviceError as exc:
                await self._say(f"清理设备截图临时文件失败：{type(exc).__name__}: {exc}")
            downloaded.unlink(missing_ok=True)

    @staticmethod
    def _convert_png(source: Path, destination: Path) -> None:
        with Image.open(source) as image:
            image.convert("RGB").save(destination, format="PNG")

    @staticmethod
    def _white_guard(path: Path) -> bool:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            if width < 22 or height < 401:
                return False
            points = ((10, 200), (width - 11, 200), (10, height - 200), (width - 11, height - 200))
            return all(min(rgb.getpixel(point)) >= 240 for point in points)

    @staticmethod
    def _crop(source: Path, destination: Path, crop: CropPx) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            validate_crop(crop, *image.size)
            right = crop.left + crop.width
            bottom = crop.top + crop.height
            image.crop((crop.left, crop.top, right, bottom)).save(destination, format="PNG")

    async def _cleanup_remote(self) -> None:
        for remote in list(self._remote_files):
            try:
                await self.devices.hdc(
                    self.target.serial,
                    ["shell", "-b", self.project.info.bundle, "rm", "-f", remote],
                )
            except DeviceError as exc:
                await self._say(f"清理应用沙箱样本失败：{type(exc).__name__}: {exc}")
            self._remote_files.discard(remote)

    async def _say(self, message: str) -> None:
        if self.notify is None:
            return
        result = self.notify(message)
        if asyncio.iscoroutine(result):
            await result


class DeviceRenderer:
    def __init__(self, config: Config, devices: Devices) -> None:
        self.config = config
        self.devices = devices

    async def session(
        self,
        target_id: str,
        log: Path,
        notify: LogCallback | None = None,
    ) -> RenderSession:
        target = await self.devices.target(target_id)
        return RenderSession(self.config, self.devices, target, log, notify)
