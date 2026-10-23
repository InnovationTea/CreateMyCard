"""复用用户手动添加的两套桌面卡片，只更新内容并截图。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from debug_tools.postprocess_plugins._io import atomic_write_json

from .commands import DeviceError
from .desktop_ui import DesktopDriver, DesktopEnvironmentError, Rect
from .locks import device_lock
from .runner import (
    CaptureResult,
    CropPx,
    RenderFailure,
    RenderSession,
    TerminalEvent,
    validate_crop,
)

DIMENSIONS = {"2x2": 2, "2x4": 3}
PREPARATION_MESSAGE = (
    "请先在设备调试模块编译安装项目，再在设备上长按应用，通过卡片菜单各添加一张 2x2 和 2x4 卡片，"
    "并将应用入口与两张卡片放在同一个桌面页面，停留该页后重试"
)


class DesktopCommandError(DesktopEnvironmentError):
    def __init__(self, code: Any, message: Any) -> None:
        self.code = code
        super().__init__(f"手机桌面命令失败（{code}）：{message}")


def desktop_envelope(source: str, run_id: str, sample_id: str, revision: int, size: str) -> dict:
    if size not in DIMENSIONS:
        raise DeviceError("桌面卡片只支持 2x2 和 2x4")
    return {
        "runId": run_id,
        "sampleId": sample_id,
        "revision": revision,
        "size": size,
        "digest": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "dsl": source,
    }


def parse_desktop_events(output: str) -> list[dict[str, Any]]:
    events = []
    for line in output.splitlines():
        if "A2UI_DESKTOP {" not in line:
            continue
        content = line.split("A2UI_DESKTOP ", 1)[1]
        try:
            event = json.loads(content)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def physical_rect(reply: dict[str, Any]) -> Rect:
    density = reply.get("density")
    value = reply.get("rectVp")
    valid_density = isinstance(density, (float, int)) and not isinstance(density, bool)
    if not valid_density or not math.isfinite(density) or density <= 0:
        raise DesktopEnvironmentError("手机未返回有效显示密度")
    if not isinstance(value, dict):
        raise DesktopEnvironmentError("手机未返回真实卡片边界")
    values = []
    for key in ("left", "top", "width", "height"):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise DesktopEnvironmentError(f"卡片边界 {key} 不是数值")
        if not math.isfinite(number):
            raise DesktopEnvironmentError("卡片边界不是有限数值")
        values.append(round(number * density))
    rect = Rect(*values)
    width = reply.get("displayWidth")
    height = reply.get("displayHeight")
    if not isinstance(width, int) or not isinstance(height, int):
        raise DesktopEnvironmentError("手机未返回有效屏幕尺寸")
    validate_crop(CropPx(**rect.__dict__), width, height)
    return rect


class DesktopCaptureResult:
    def __init__(self, capture: CaptureResult, evidence: dict[str, Any]) -> None:
        self.capture = capture
        self.evidence = evidence

    def public(self) -> dict[str, Any]:
        return {**self.capture.public(), **self.evidence, "captureMode": "desktop"}


class DesktopRenderSession(RenderSession):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.driver: DesktopDriver | None = None
        self.instances: dict[str, dict[str, Any]] = {}
        self.instance: dict[str, Any] | None = None
        self.form_rects: dict[str, Rect] = {}
        self.marker: str | None = None
        self.run_id = uuid.uuid4().hex
        self.revision = 0
        self.current_envelope: dict[str, Any] | None = None
        self.workspace: dict[str, Any] = {}
        self.screen_signature: tuple[Any, ...] | None = None
        self.app_version = ""
        self.renderer_digest: str | None = None

    async def __aenter__(self) -> DesktopRenderSession:
        self._lock = device_lock(self.target.serial)
        await self._lock.acquire()
        try:
            await self._process_lock.acquire()
            await self.devices.target(self.target.id)
            await self._say("检查已编译项目及应用入口、两套卡片是否位于同一桌面页")
            path = self.config.output / "prepared" / f"{self.target.id}.json"
            if not path.is_file():
                raise DesktopEnvironmentError(PREPARATION_MESSAGE)
            prepared = json.loads(path.read_text(encoding="utf-8"))
            fingerprint = await asyncio.to_thread(self.project._fingerprint)
            if not isinstance(prepared, dict) or prepared.get("fingerprint") != fingerprint:
                raise DesktopEnvironmentError(
                    f"调试工程已变化，需要重新编译。{PREPARATION_MESSAGE}"
                )
            self.renderer_digest = hashlib.sha256(
                (self.config.project / "genui_form.har").read_bytes()
            ).hexdigest()
            self._sandbox_transport = await self._prepare_sandbox(self.target.serial)
            environment = await self.bridge("environment")
            if environment.get("desktopProtocolVersion") != 3:
                raise DesktopEnvironmentError(f"设备上的调试应用版本不兼容。{PREPARATION_MESSAGE}")
            if environment.get("desktopBatchUpdate") is not True:
                raise DesktopEnvironmentError(
                    f"设备应用不支持合并更新，请重新编译安装。{PREPARATION_MESSAGE}"
                )
            width, height = environment.get("displayWidth"), environment.get("displayHeight")
            if not isinstance(width, int) or not isinstance(height, int):
                raise DesktopEnvironmentError("无法识别设备屏幕尺寸")
            self.driver = DesktopDriver(self, Rect(0, 0, width, height))
            await self.reconcile()
            for instance in self.instances.values():
                self.instance = instance
                rect = physical_rect(await self.bridge("rect"))
                self.form_rects[str(instance.get("formId"))] = rect
            for instance in self.instances.values():
                self.instance = instance
                self.driver.card = self.form_rects.get(str(instance.get("formId")))
                await self.driver.navigate_and_inspect()
            self._prepared = True
            return self
        except BaseException:
            await super().__aexit__(None, None, None)
            raise

    def require_driver(self) -> DesktopDriver:
        if self.driver is None:
            raise DesktopEnvironmentError("桌面定位尚未准备")
        return self.driver

    async def bridge(self, operation: str, envelope: dict | None = None) -> dict[str, Any]:
        try:
            return await self._command(operation, envelope)
        except DesktopCommandError as exc:
            if exc.code == 16500100:
                raise DesktopEnvironmentError(f"无法查询已加桌卡片。{PREPARATION_MESSAGE}") from exc
            raise

    async def _command(self, operation: str, envelope: dict | None = None) -> dict[str, Any]:
        command_id = uuid.uuid4().hex
        command: dict[str, Any] = {"commandId": command_id, "operation": operation}
        if envelope is not None:
            command["envelope"] = envelope
        if self.instance is not None:
            command["formId"] = self.instance.get("formId")
        if operation == "replace":
            expected_forms = []
            for size in ("2x2", "2x4"):
                form = self.instances.get(size)
                if form is None:
                    raise DesktopEnvironmentError("合并更新缺少已确认的卡片实例")
                expected_forms.append(form)
            command["expectedForms"] = expected_forms
            expected = self.form_rects.get(str(command.get("formId")))
            if expected is None or self.screen_signature is None:
                raise DesktopEnvironmentError("合并更新缺少已确认的边界或显示配置")
            command["expectedRectPx"] = expected.__dict__
            command["expectedDisplay"] = list(self.screen_signature)
        local = self.log.parent / f"desktop-{command_id}.json"
        sample_file = f"desktop-{command_id}.json"
        remote = f"data/storage/el2/base/files/a2ui/{sample_file}"
        parameters = ["--ps", "runId", command_id, "--ps", "sampleFile", sample_file]
        parameters.extend(("--pb", "desktopOperation", "true"))
        try:
            atomic_write_json(local, command)
            if self._sandbox_transport:
                self._remote_files.add(remote)
                output = await self.devices.hdc(
                    self.target.serial,
                    ["file", "send", "-b", self.project.info.bundle, str(local), remote],
                    log=self.log,
                )
                self._require_hdc_success(output, "推送桌面命令")
                await self._start_app(parameters)
            else:
                await self._send_sample_chunks(local, parameters)
            deadline = time.monotonic() + self.config.render_timeout
            while time.monotonic() < deadline:
                events = await self.events(command_id)
                for event in events:
                    if event.get("commandId") != command_id:
                        continue
                    if event.get("state") != "OK":
                        raise DesktopCommandError(event.get("code"), event.get("message"))
                    self.validate_screen(event)
                    if operation != "environment":
                        await self.reconcile(event)
                    return event
                await asyncio.sleep(0.25)
            raise DesktopEnvironmentError(f"等待手机桌面命令超时：{operation}")
        finally:
            local.unlink(missing_ok=True)

    def validate_screen(self, reply: dict[str, Any]) -> None:
        signature = (
            reply.get("displayWidth"),
            reply.get("displayHeight"),
            reply.get("density"),
            reply.get("rotation"),
        )
        if self.screen_signature is None:
            self.screen_signature = signature
        elif self.screen_signature != signature:
            raise DesktopEnvironmentError("显示配置发生变化，请重新准备设备")
        version = reply.get("appVersion")
        if isinstance(version, str):
            if self.app_version and version != self.app_version:
                raise DesktopEnvironmentError("设备上的调试应用版本发生变化，请重新开始截图")
            self.app_version = version

    async def events(self, identity: str) -> list[dict[str, Any]]:
        if identity == self.run_id and self.instance is not None:
            if self._sandbox_transport:
                receipt = await self.read_receipt()
            else:
                reply = await self.bridge("receipt")
                receipt = reply.get("receipt")
            return [receipt] if isinstance(receipt, dict) else []
        output = await self.devices.hdc(
            self.target.serial,
            ["shell", "hilog", "-x", "-T", "A2UIDesktop", "-e", identity, "-v", "wrap"],
            timeout=10.0,
            log=self.log,
        )
        return parse_desktop_events(output)

    async def read_receipt(self) -> dict[str, Any] | None:
        identity = self.instance.get("formId") if self.instance is not None else None
        if not isinstance(identity, str) or re.fullmatch(r"-?\d{1,30}", identity) is None:
            raise DesktopEnvironmentError("卡片实例标识不能用于读取持久化回执")
        remote = f"data/storage/el2/base/files/desktop/receipt-{identity}.json"
        output = await self.devices.hdc(
            self.target.serial,
            ["shell", "-b", self.project.info.bundle, "cat", remote],
            log=self.log,
        )
        self._require_hdc_success(output, "读取桌面卡片回执")
        missing = "No such file or directory" in output and remote in output
        receipt: dict[str, Any] | None = None
        if not missing:
            try:
                value = json.loads(output)
            except ValueError as exc:
                raise DesktopEnvironmentError("桌面卡片持久化回执不是有效 JSON") from exc
            if not isinstance(value, dict):
                raise DesktopEnvironmentError("桌面卡片持久化回执不是对象")
            receipt = value
        return receipt

    async def reconcile(self, status: dict[str, Any] | None = None) -> None:
        reply = status if status is not None else await self.bridge("status")
        forms = reply.get("forms")
        if not isinstance(forms, list):
            raise DesktopEnvironmentError("手机未返回有效的桌面卡片列表")
        selected: dict[str, dict[str, Any]] = {}
        identities: set[str] = set()
        for form in forms:
            if not isinstance(form, dict) or not isinstance(form.get("formId"), str):
                raise DesktopEnvironmentError("手机返回的卡片实例无效")
            identity = form.get("formId")
            if not identity or identity in identities:
                raise DesktopEnvironmentError("手机返回的卡片实例标识为空或重复")
            identities.add(identity)
            size = next(
                (key for key, value in DIMENSIONS.items() if value == form.get("dimension")), None
            )
            if size is None or size in selected:
                raise DesktopEnvironmentError(f"每种规格只允许一张测试卡片。{PREPARATION_MESSAGE}")
            selected[size] = form
        if len(selected) != 2:
            raise DesktopEnvironmentError(f"缺少 2x2 或 2x4 桌面卡片。{PREPARATION_MESSAGE}")
        if self.instances:
            for size, previous in self.instances.items():
                current = selected.get(size)
                if current is None or current.get("formId") != previous.get("formId"):
                    raise DesktopEnvironmentError("运行期间桌面卡片被删除或替换，请重新开始截图")
        self.instances = selected

    async def wait_applied(self, envelope: dict[str, Any]) -> list[str]:
        driver = self.require_driver()
        marker = f"A2UI_DESKTOP:{self.run_id}:{envelope.get('revision')}:{envelope.get('digest')}"
        deadline = time.monotonic() + self.config.render_timeout
        while time.monotonic() < deadline:
            await driver.navigate()
            events = await self.events(self.run_id)
            for event in reversed(events):
                if self.instance is None or event.get("formId") != self.instance.get("formId"):
                    continue
                if event.get("runId") != self.run_id:
                    continue
                if event.get("revision") != envelope.get("revision"):
                    continue
                if event.get("digest") != envelope.get("digest"):
                    continue
                if event.get("state") == "FAILED":
                    raise RenderFailure(
                        TerminalEvent(
                            self.run_id,
                            "FAILED",
                            "DESKTOP_RENDER_FAILED",
                            str(event.get("message")),
                            [],
                            None,
                        )
                    )
                if event.get("state") == "APPLIED":
                    self.marker = marker
                    if self._sandbox_transport:
                        self.workspace = await driver.inspect(marker=marker)
                    else:
                        self.workspace = await driver.navigate_and_inspect(marker=marker)
                    warnings = event.get("warnings", [])
                    if not isinstance(warnings, list):
                        raise DesktopEnvironmentError("渲染警告格式无效")
                    return warnings
            await asyncio.sleep(0.25)
        raise DesktopEnvironmentError("卡片未确认本轮 DSL 或桌面版本标记不可见")

    async def render(
        self,
        source: Path,
        size: str,
        card_path: Path,
        full_path: Path,
        *,
        capture_delay_seconds: float = 0.0,
    ) -> DesktopCaptureResult:
        from .conversion import convert

        if not self._prepared:
            raise DesktopEnvironmentError("桌面会话尚未准备")
        # 输入错误只影响样本；真实桌面 I/O、定位和状态错误必须终止会话。
        convert(await asyncio.to_thread(source.read_text, encoding="utf-8"), "a2ui", size)
        try:
            return await self._render_desktop(
                source, size, card_path, full_path, capture_delay_seconds=capture_delay_seconds
            )
        except RenderFailure:
            raise
        except (DeviceError, OSError, ValueError) as exc:
            raise DesktopEnvironmentError(str(exc)) from exc

    async def _render_desktop(
        self,
        source: Path,
        size: str,
        card_path: Path,
        full_path: Path,
        *,
        capture_delay_seconds: float = 0.0,
    ) -> DesktopCaptureResult:
        text = await asyncio.to_thread(source.read_text, encoding="utf-8")
        # 在触碰桌面前排除非法 JSON/消息，失败只影响当前样本。
        from .conversion import convert

        convert(text, "a2ui", size)
        self.revision += 1
        attempt = source.parent.name.removeprefix("attempt_")
        sample_id = source.parent.parent.name if attempt.isdigit() else source.stem
        envelope = desktop_envelope(text, self.run_id, sample_id, self.revision, size)
        self.instance = self.instances.get(size)
        if self.instance is None:
            raise DesktopEnvironmentError(f"缺少 {size} 桌面卡片")
        driver = self.require_driver()
        expected = self.form_rects.get(str(self.instance.get("formId")))
        driver.card = expected
        await driver.navigate_and_inspect()
        await self._say("集中检查实例、边界并提交本轮内容")
        await self._say(f"更新已加桌的 {size} 卡片内容")
        reply = await self.bridge("replace", envelope)
        await self.reconcile(reply)
        for key in ("runId", "revision", "digest"):
            if reply.get(key) != envelope.get(key):
                raise DesktopEnvironmentError("合并更新回包与本轮样本不一致")
        for key in ("beforeRectVp", "stagedRectVp", "updatedRectVp", "rectVp"):
            checked = {**reply, "rectVp": reply.get(key)}
            if physical_rect(checked) != expected:
                raise DesktopEnvironmentError("桌面卡片位置或尺寸发生变化，请重新开始截图")
        self.current_envelope = envelope
        driver.card = expected
        await self._say("返回同页桌面并等待本轮渲染回执")
        warnings = await self.wait_applied(envelope)
        await self._say("等待桌面画面稳定并截图")
        rect = await self.capture_stable(card_path, full_path, capture_delay_seconds)
        capture = CaptureResult(
            run_id=self.run_id,
            terminal="READY_WITH_WARNINGS" if warnings else "READY",
            code="",
            message="",
            warnings=warnings,
            crop_px=CropPx(**rect.__dict__),
            card_path=card_path,
            full_path=full_path,
        )
        driver = self.require_driver()
        evidence = {
            "formId": self.instance.get("formId") if self.instance is not None else None,
            "size": size,
            "revision": self.revision,
            "sampleDigest": envelope.get("digest"),
            "sampleId": envelope.get("sampleId"),
            "adapterId": driver.id,
            "adapterVersion": driver.version,
            "appVersion": self.app_version,
            "rendererDigest": self.renderer_digest,
            "workspace": self.workspace,
            "screen": self.screen_signature,
            "validationLevel": "existing_forms",
        }
        return DesktopCaptureResult(capture, evidence)

    async def snapshot(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        remote = f"/data/local/tmp/a2ui-desktop-{uuid.uuid4().hex}.jpeg"
        downloaded = destination.with_suffix(".source.jpeg")
        try:
            for args in (
                ["shell", "snapshot_display", "-f", remote],
                ["file", "recv", remote, str(downloaded)],
            ):
                output = await self.devices.hdc(self.target.serial, args, log=self.log)
                self._require_hdc_success(output, "桌面截图")
            await asyncio.to_thread(self._convert_png, downloaded, destination)
        finally:
            downloaded.unlink(missing_ok=True)
            await self.devices.hdc(self.target.serial, ["shell", "rm", "-f", remote])

    @staticmethod
    def pixels_close(first: Image.Image, second: Image.Image) -> bool:
        if first.size != second.size:
            return False
        difference = ImageStat.Stat(ImageChops.difference(first, second)).mean
        return max(difference) <= 0.5

    async def capture_stable(self, card_path: Path, full_path: Path, delay: float) -> Rect:
        driver = self.require_driver()
        first = driver.card
        if first is None:
            raise DesktopEnvironmentError("截图前未确认实际卡片边界")
        previous = None
        stable = 0
        succeeded = False
        try:
            for _attempt in range(max(3, self.config.capture_attempts)):
                # 采样期间仅检查桌面节点和像素，不调用会拉起应用的命令。
                await driver.inspect(marker=self.marker)
                await self.snapshot(full_path)
                await driver.inspect(marker=self.marker)
                await asyncio.to_thread(self._crop, full_path, card_path, CropPx(**first.__dict__))
                with Image.open(card_path) as image:
                    current = image.convert("RGB").copy()
                if previous is not None and self.pixels_close(previous, current):
                    stable += 1
                else:
                    stable = 0
                if previous is not None:
                    previous.close()
                previous = current
                if stable >= 2:
                    if delay > 0:
                        await asyncio.sleep(delay)
                    await driver.inspect(marker=self.marker)
                    await self.snapshot(full_path)
                    await driver.inspect(marker=self.marker)
                    await asyncio.to_thread(
                        self._crop, full_path, card_path, CropPx(**first.__dict__)
                    )
                    with Image.open(card_path) as image:
                        final = image.convert("RGB").copy()
                    final_stable = self.pixels_close(previous, final)
                    previous.close()
                    previous = final
                    if final_stable:
                        # 最终图片已完成；只在这一阶段集中做一次手机端核验，再返回桌面。
                        await self._say("图片采集完成，集中核验实际边界和渲染回执")
                        after_rect = physical_rect(await self.bridge("rect"))
                        if after_rect != first:
                            raise DesktopEnvironmentError("截图后实际卡片边界发生变化")
                        await self.require_no_render_failure()
                        succeeded = True
                        return first
                    stable = 0
                await asyncio.sleep(0.25)
            raise DesktopEnvironmentError("桌面画面或边界未稳定，未产出成功截图")
        finally:
            if previous is not None:
                previous.close()
            if not succeeded:
                card_path.unlink(missing_ok=True)
                full_path.unlink(missing_ok=True)

    async def require_no_render_failure(self) -> None:
        envelope = self.current_envelope
        if envelope is None:
            raise DesktopEnvironmentError("截图缺少当前样本身份")
        applied = False
        for event in await self.events(self.run_id):
            if self.instance is None or event.get("formId") != self.instance.get("formId"):
                continue
            same_run = event.get("runId") == self.run_id
            same_revision = event.get("revision") == envelope.get("revision")
            same_digest = event.get("digest") == envelope.get("digest")
            if not (same_run and same_revision and same_digest):
                continue
            if event.get("state") == "FAILED":
                raise RenderFailure(
                    TerminalEvent(
                        self.run_id,
                        "FAILED",
                        "DESKTOP_RENDER_FAILED",
                        str(event.get("message")),
                        [],
                        None,
                    )
                )
            if event.get("state") == "APPLIED":
                applied = True
        if not applied:
            raise DesktopEnvironmentError("截图后缺少本轮有效渲染回执")
        driver = self.require_driver()
        await driver.navigate_and_inspect(marker=self.marker)
