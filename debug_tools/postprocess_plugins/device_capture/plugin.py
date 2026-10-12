"""真机截图后处理插件实现。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml
from PIL import Image

from .._io import atomic_write_json

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_TERMINAL = {"ready", "partial", "failed", "interrupted", "not_requested"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DeviceCaptureConfig:
    hdc: str = "hdc"
    device_sn: str | None = None
    render_project: Path | None = None
    deveco_sdk_home: Path | None = None
    java_home: Path | None = None
    hvigor: Path | None = None
    signed_hap_name: str = "entry-default-signed.hap"
    bundle_name: str = "com.example.myapplication"
    ability_name: str = "EntryAbility"
    module_name: str = "entry"
    rawfile_target: Path = Path("entry/src/main/resources/rawfile/test.json")
    hap_output_dir: Path = Path("entry/build/default/outputs/default")
    render_wait_seconds: float = 8.0
    command_timeout_seconds: float = 300.0
    crop_config: Path | None = None
    auto_start_emulator: bool = False
    emulator: Path | None = None
    emulator_name: str | None = None
    emulator_instance_root: Path | None = None
    emulator_image_root: Path | None = None
    emulator_start_timeout_seconds: float = 120.0
    emulator_poll_seconds: float = 2.0

    @classmethod
    def from_debug_agent(cls, path: Path | None = None) -> DeviceCaptureConfig:
        config_path = path or (
            Path(__file__).resolve().parents[2]
            / "end_to_end_debug"
            / "backend"
            / "debug_agent.yaml"
        )
        try:
            root = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise DeviceCaptureError("无法读取 debug_agent.yaml 中的真机截图配置") from exc
        if not isinstance(root, dict):
            raise DeviceCaptureError("debug_agent.yaml 根节点必须是对象")
        raw_config = root.get("device_capture")
        if raw_config is None:
            raw_config = {}
        if not isinstance(raw_config, dict):
            raise DeviceCaptureError("debug_agent.yaml 的 device_capture 必须是对象")
        project_root = Path(__file__).resolve().parents[3]

        def configured_path(name: str) -> Path | None:
            value = raw_config.get(name)
            if not isinstance(value, str) or not value.strip():
                return None
            candidate = Path(value.strip()).expanduser()
            return candidate if candidate.is_absolute() else project_root / candidate

        return cls(
            hdc=str(raw_config.get("hdc") or "hdc"),
            device_sn=str(raw_config.get("device_sn") or "").strip() or None,
            render_project=configured_path("render_project"),
            deveco_sdk_home=configured_path("deveco_sdk_home"),
            java_home=configured_path("java_home"),
            hvigor=configured_path("hvigor"),
            signed_hap_name=str(
                raw_config.get("signed_hap_name") or "entry-default-signed.hap"
            ),
            bundle_name=str(raw_config.get("bundle_name") or "com.example.myapplication"),
            ability_name=str(raw_config.get("ability_name") or "EntryAbility"),
            module_name=str(raw_config.get("module_name") or "entry"),
            rawfile_target=Path(
                str(
                    raw_config.get("rawfile_target")
                    or "entry/src/main/resources/rawfile/test.json"
                )
            ),
            hap_output_dir=Path(
                str(
                    raw_config.get("hap_output_dir")
                    or "entry/build/default/outputs/default"
                )
            ),
            render_wait_seconds=float(raw_config.get("render_wait_seconds", 8.0)),
            command_timeout_seconds=float(raw_config.get("command_timeout_seconds", 300.0)),
            crop_config=configured_path("crop_config"),
            auto_start_emulator=bool(raw_config.get("auto_start_emulator", False)),
            emulator=configured_path("emulator"),
            emulator_name=str(raw_config.get("emulator_name") or "").strip() or None,
            emulator_instance_root=configured_path("emulator_instance_root"),
            emulator_image_root=configured_path("emulator_image_root"),
            emulator_start_timeout_seconds=float(
                raw_config.get("emulator_start_timeout_seconds", 120.0)
            ),
            emulator_poll_seconds=float(raw_config.get("emulator_poll_seconds", 2.0)),
        )


class DeviceCaptureError(RuntimeError):
    """真机截图配置或执行失败。"""


class DeviceRenderer:
    """把单份 GenUI 编译进 ArkTS 工程并在 HarmonyOS 设备上截图。"""

    def __init__(self, config: DeviceCaptureConfig) -> None:
        self.config = config
        self._active_process: asyncio.subprocess.Process | None = None
        self._emulator_process: asyncio.subprocess.Process | None = None
        self._emulator_lock = asyncio.Lock()
        self._emulator_log_offset = 0
        self._resolved_sn: str | None = None

    async def availability(self) -> dict[str, Any]:
        try:
            self._validate_static_config()
        except Exception as exc:
            return {"configured": False, "available": False, "reason": str(exc)}
        try:
            targets = await self._list_targets()
            if not targets and self.config.auto_start_emulator:
                await self._ensure_emulator_started()
                targets = await self._list_targets()
            selected = self._select_target(targets)
        except Exception as exc:
            return {"configured": True, "available": False, "reason": str(exc)}
        return {
            "configured": True,
            "available": True,
            "reason": "",
            "device": self._mask_device(selected),
        }

    async def require_available(self) -> None:
        result = await self.availability()
        if not result.get("available"):
            raise DeviceCaptureError(str(result.get("reason") or "真机截图环境不可用"))

    async def render(
        self,
        genui_path: Path,
        size: str,
        work_dir: Path,
        full_output: Path,
        card_output: Path,
        log_path: Path,
    ) -> None:
        self._validate_static_config()
        targets = await self._list_targets(log_path)
        self._resolved_sn = self._select_target(targets)
        project = work_dir / "render_project"
        await asyncio.to_thread(self._prepare_workspace, project)
        await asyncio.to_thread(self._write_genui, genui_path, project)
        environment = self._build_environment()
        await self._run_hvigor(project, "assembleHap", environment, log_path)
        hap_path = project / self.config.hap_output_dir / self.config.signed_hap_name
        if not hap_path.is_file():
            raise DeviceCaptureError(f"未生成已签名 HAP：{self.config.signed_hap_name}")
        remote_suffix = datetime.now().strftime("%H%M%S%f")
        remote_dir = f"/data/local/tmp/widget_debug_{os.getpid()}_{remote_suffix}"
        remote_hap = f"{remote_dir}/{hap_path.name}"
        remote_image = f"{remote_dir}/display.jpeg"
        try:
            await self._hdc(["shell", "mkdir", "-p", remote_dir], log_path)
            await self._hdc(["file", "send", str(hap_path), remote_hap], log_path)
            await self._hdc(
                ["shell", "aa", "force-stop", self.config.bundle_name],
                log_path,
                check=False,
            )
            await self._hdc(
                ["shell", "bm", "uninstall", "-n", self.config.bundle_name],
                log_path,
                check=False,
            )
            install = await self._hdc(
                ["shell", "bm", "install", "-p", remote_dir], log_path
            )
            if "error" in install.lower() or "failed" in install.lower():
                raise DeviceCaptureError("真机安装 HAP 失败")
            await self._hdc(
                [
                    "shell",
                    "aa",
                    "start",
                    "-a",
                    self.config.ability_name,
                    "-b",
                    self.config.bundle_name,
                    "-m",
                    self.config.module_name,
                ],
                log_path,
            )
            await asyncio.sleep(self.config.render_wait_seconds)
            await self._capture(remote_image, full_output, log_path)
            await asyncio.to_thread(self._crop, full_output, card_output, size)
        finally:
            await self._hdc(
                ["shell", "rm", "-rf", remote_dir], log_path, check=False
            )

    async def stop(self) -> None:
        process = self._active_process
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        emulator = self._emulator_process
        if emulator is not None and emulator.returncode is None:
            await self._stop_emulator()

    async def _ensure_emulator_started(self) -> None:
        async with self._emulator_lock:
            targets = await self._list_targets()
            if targets:
                return
            self._validate_emulator_config()
            process = self._emulator_process
            if process is None or process.returncode is not None:
                self._emulator_log_offset = self._emulator_log_size()
                process = await self._launch_emulator()
                self._emulator_process = process
            deadline = time.monotonic() + self.config.emulator_start_timeout_seconds
            while time.monotonic() < deadline:
                await asyncio.sleep(self.config.emulator_poll_seconds)
                targets = await self._list_targets()
                if targets:
                    return
                detail = self._emulator_failure_detail()
                if detail:
                    await self._stop_emulator()
                    raise DeviceCaptureError(detail)
                if process.returncode is not None:
                    raise DeviceCaptureError("虚拟器进程在 HDC 上线前退出")
            await self._stop_emulator()
            raise DeviceCaptureError("虚拟器启动超时，HDC 设备仍未上线")

    def _validate_emulator_config(self) -> None:
        emulator = self.config.emulator
        if emulator is None or not emulator.is_file():
            raise DeviceCaptureError("未配置有效的 DevEco Emulator 启动器")
        if not self.config.emulator_name:
            raise DeviceCaptureError("未配置 DevEco 虚拟器实例名称")
        instance_root = self.config.emulator_instance_root
        if instance_root is None or not instance_root.is_dir():
            raise DeviceCaptureError("未配置有效的 DevEco 虚拟器实例目录")
        image_root = self.config.emulator_image_root
        if image_root is None or not image_root.is_dir():
            raise DeviceCaptureError("未配置有效的 DevEco 虚拟器镜像目录")
        if self.config.emulator_start_timeout_seconds <= 0:
            raise DeviceCaptureError("虚拟器启动超时必须大于 0 秒")
        if self.config.emulator_poll_seconds <= 0:
            raise DeviceCaptureError("虚拟器检查间隔必须大于 0 秒")

    async def _launch_emulator(self) -> asyncio.subprocess.Process:
        emulator = self.config.emulator
        instance_root = self.config.emulator_instance_root
        image_root = self.config.emulator_image_root
        if emulator is None or instance_root is None or image_root is None:
            raise DeviceCaptureError("DevEco 虚拟器配置不完整")
        return await asyncio.create_subprocess_exec(
            str(emulator),
            "-hvd",
            str(self.config.emulator_name),
            "-path",
            str(instance_root),
            "-imageRoot",
            str(image_root),
            cwd=str(emulator.parent),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def _stop_emulator(self) -> None:
        process = self._emulator_process
        if process is None:
            return
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=10.0)
            except TimeoutError:
                process.kill()
                await process.wait()
        self._emulator_process = None

    def _emulator_log_path(self) -> Path | None:
        instance_root = self.config.emulator_instance_root
        name = self.config.emulator_name
        if instance_root is None or not name:
            return None
        return instance_root / name / "Emulator.log"

    def _emulator_log_size(self) -> int:
        log_path = self._emulator_log_path()
        if log_path is None:
            return 0
        try:
            return log_path.stat().st_size
        except OSError:
            return 0

    def _emulator_failure_detail(self) -> str | None:
        log_path = self._emulator_log_path()
        if log_path is None:
            return None
        try:
            with log_path.open("rb") as stream:
                stream.seek(self._emulator_log_offset)
                text = stream.read().decode("utf-8", errors="replace")
        except OSError:
            return None
        if "Commit charge is not enough" in text:
            return "虚拟器启动失败：系统提交内存不足，请增加可用内存或页面文件"
        return None

    def _validate_static_config(self) -> None:
        project = self.config.render_project
        if project is None:
            raise DeviceCaptureError("debug_agent.yaml 未配置 device_capture.render_project")
        if not project.is_dir():
            raise DeviceCaptureError("真机渲染工程不存在")
        if self._find_executable(self.config.hdc) is None:
            raise DeviceCaptureError("未找到 HDC 可执行文件")
        if self.config.java_home is None or not (self.config.java_home / "bin").is_dir():
            raise DeviceCaptureError("未配置有效的 DevEco JDK")
        if self.config.deveco_sdk_home is None or not self.config.deveco_sdk_home.is_dir():
            raise DeviceCaptureError("未配置有效的 DevEco SDK")
        self._validate_project_relative_path(self.config.rawfile_target, "rawfile_target")
        self._validate_project_relative_path(self.config.hap_output_dir, "hap_output_dir")
        self._resolve_hvigor(project)

    @staticmethod
    def _validate_project_relative_path(path: Path, name: str) -> None:
        if path.is_absolute() or ".." in path.parts:
            raise DeviceCaptureError(f"debug_agent.yaml 中的 {name} 必须是工程内相对路径")

    async def _list_targets(self, log_path: Path | None = None) -> list[str]:
        output = await self._run(
            [self.config.hdc, "list", "targets"],
            log_path,
            timeout_seconds=min(15.0, self.config.command_timeout_seconds),
        )
        targets: list[str] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or "empty" in line.lower() or "list of" in line.lower():
                continue
            target = line.split()[0]
            if target not in targets:
                targets.append(target)
        return targets

    def _select_target(self, targets: list[str]) -> str:
        configured = self.config.device_sn
        if configured:
            if configured not in targets:
                raise DeviceCaptureError("配置的真机当前不在线")
            return configured
        if len(targets) != 1:
            raise DeviceCaptureError("未指定设备时必须且只能连接一台 HDC 设备")
        return targets[0]

    @staticmethod
    def _mask_device(device: str) -> str:
        if len(device) <= 6:
            return "***"
        return f"{device[:3]}***{device[-3:]}"

    def _prepare_workspace(self, target: Path) -> None:
        source = self.config.render_project
        if source is None:
            raise DeviceCaptureError("真机渲染工程未配置")
        resolved_target = target.resolve()
        resolved_parent = target.parent.resolve()
        if resolved_target.parent != resolved_parent or resolved_target.name != "render_project":
            raise DeviceCaptureError("真机渲染工作目录无效")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(
                "build", ".hvigor", ".idea", ".gradle", "node_modules"
            ),
        )

    def _write_genui(self, source: Path, project: Path) -> None:
        text = source.read_text(encoding="utf-8")
        try:
            value = json.loads(text)
            records = value if isinstance(value, list) else [value]
        except json.JSONDecodeError:
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not records or not all(isinstance(item, dict) for item in records):
            raise DeviceCaptureError("GenUI 不是有效的 JSON 数组或 JSONL")
        normalized: list[dict[str, Any]] = []
        for item in records:
            copied = dict(item)
            surface = copied.get("createSurface")
            legacy_catalog = "ohos.a2ui.extended.catalog"
            if isinstance(surface, dict) and surface.get("catalogId") == legacy_catalog:
                copied["createSurface"] = {
                    **surface,
                    "catalogId": "ohos.a2ui.extended.catalog.form",
                }
            normalized.append(copied)
        target = project / self.config.rawfile_target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _build_environment(self) -> dict[str, str]:
        if self.config.java_home is None or self.config.deveco_sdk_home is None:
            raise DeviceCaptureError("DevEco 环境未配置")
        environment = os.environ.copy()
        environment["JAVA_HOME"] = str(self.config.java_home)
        environment["DEVECO_SDK_HOME"] = str(self.config.deveco_sdk_home)
        java_bin = str(self.config.java_home / "bin")
        toolchains = str(self.config.deveco_sdk_home / "toolchains")
        environment["PATH"] = os.pathsep.join(
            [java_bin, toolchains, environment.get("PATH", "")]
        )
        return environment

    async def _run_hvigor(
        self,
        project: Path,
        action: str,
        environment: dict[str, str],
        log_path: Path,
    ) -> None:
        executable = self._resolve_hvigor(project)
        command = [str(executable), action]
        if os.name == "nt" and str(executable).lower().endswith((".bat", ".cmd")):
            command = ["cmd", "/c", "call", str(executable), action]
        await self._run(command, log_path, cwd=project, environment=environment)

    def _resolve_hvigor(self, project: Path) -> Path | str:
        if self.config.hvigor is not None:
            if not self.config.hvigor.is_file():
                raise DeviceCaptureError("配置的 Hvigor 可执行文件不存在")
            return self.config.hvigor
        for name in ("hvigorw.bat", "hvigorw", "hvigor.bat", "hvigor"):
            candidate = project / name
            if candidate.is_file():
                return candidate
            resolved = shutil.which(name)
            if resolved:
                return resolved
        raise DeviceCaptureError("未找到 Hvigor 可执行文件")

    async def _hdc(
        self,
        arguments: Sequence[str],
        log_path: Path,
        *,
        check: bool = True,
    ) -> str:
        command = [self.config.hdc]
        if self._resolved_sn:
            command.extend(["-t", self._resolved_sn])
        command.extend(arguments)
        return await self._run(command, log_path, check=check)

    async def _capture(self, remote_path: str, output: Path, log_path: Path) -> None:
        result = await self._hdc(
            ["shell", "snapshot_display", "-f", remote_path], log_path, check=False
        )
        if "error" in result.lower() or "failed" in result.lower():
            await self._hdc(["shell", "snapshot_display", remote_path], log_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        await self._hdc(["file", "recv", remote_path, str(temporary)], log_path)
        if not temporary.is_file() or temporary.stat().st_size < 1000:
            temporary.unlink(missing_ok=True)
            raise DeviceCaptureError("真机截图文件无效")
        os.replace(temporary, output)

    def _crop(self, source: Path, output: Path, size: str) -> None:
        boxes = {"2x2": [364, 96, 920, 576], "2x4": [95, 96, 1192, 576]}
        if self.config.crop_config is not None:
            value = json.loads(self.config.crop_config.read_text(encoding="utf-8-sig"))
            if isinstance(value, dict):
                for key in boxes:
                    candidate = value.get(key) or value.get(f"crop_box_{key}")
                    if isinstance(candidate, list) and len(candidate) == 4:
                        boxes[key] = [int(item) for item in candidate]
                    elif isinstance(candidate, dict):
                        boxes[key] = [
                            int(candidate.get(name, 0)) for name in ("x1", "y1", "x2", "y2")
                        ]
        selected = boxes["2x4" if size == "2x4" else "2x2"]
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            width, height = image.size
            left = max(0, min(selected[0], width - 1))
            top = max(0, min(selected[1], height - 1))
            right = max(left + 1, min(selected[2], width))
            bottom = max(top + 1, min(selected[3], height))
            temporary = output.with_suffix(output.suffix + ".tmp")
            image.crop((left, top, right, bottom)).save(temporary, format="PNG")
        os.replace(temporary, output)

    async def _run(
        self,
        command: Sequence[str],
        log_path: Path | None,
        *,
        cwd: Path | None = None,
        environment: dict[str, str] | None = None,
        check: bool = True,
        timeout_seconds: float | None = None,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd is not None else None,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._active_process = process
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds or self.config.command_timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise DeviceCaptureError("真机渲染命令执行超时") from exc
        finally:
            self._active_process = None
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(f"$ {' '.join(command)}\n{output}{error}\n")
        if check and process.returncode != 0:
            detail = error.strip() or output.strip()
            raise DeviceCaptureError(detail or f"命令失败，退出码 {process.returncode}")
        return "\n".join(part for part in (output, error) if part)

    @staticmethod
    def _find_executable(value: str) -> str | None:
        path = Path(value)
        if path.is_file():
            return str(path)
        return shutil.which(value)


class DeviceCaptureManager:
    """持久化并串行执行批跑真机截图后处理。"""

    def __init__(
        self,
        output_root: Path,
        *,
        renderer: DeviceRenderer | None = None,
        on_terminal: Callable[[str], None] | None = None,
    ) -> None:
        self.output_root = output_root.resolve()
        self.renderer = renderer or DeviceRenderer(DeviceCaptureConfig.from_debug_agent())
        self.on_terminal = on_terminal
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.queued: set[str] = set()
        self.worker: asyncio.Task[None] | None = None
        self.active_run_id: str | None = None
        self.closing = False

    async def start(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        for path in self.output_root.glob("*/device_capture.json"):
            state = self._read_state(path)
            if state.get("status") in {"queued", "running"}:
                state["status"] = "interrupted"
                state["finishedAt"] = _now()
                state["error"] = "调试后端重启导致真机截图中断"
                atomic_write_json(path, state)
        if self.worker is None:
            self.worker = asyncio.create_task(self._worker_loop())

    async def close(self) -> None:
        self.closing = True
        await self.renderer.stop()
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)

    async def availability(self) -> dict[str, Any]:
        return await self.renderer.availability()

    async def require_available(self) -> None:
        await self.renderer.require_available()

    def not_requested(self, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        state = {
            "status": "not_requested",
            "total": 0,
            "completed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "items": [],
            "error": "",
        }
        atomic_write_json(run_dir / "device_capture.json", state)
        return state

    def enqueue(self, run_id: str, *, retry: bool = False) -> dict[str, Any]:
        run_dir = self._run_dir(run_id)
        current = self.status(run_id)
        if run_id in self.queued or self.active_run_id == run_id:
            return current
        if not retry and current.get("status") in {"ready", "partial"}:
            return current
        summary = self._read_json(run_dir / "summary.json")
        samples = summary.get("samples")
        total = len(samples) if isinstance(samples, list) else 0
        state = {
            "status": "queued",
            "createdAt": current.get("createdAt") or _now(),
            "startedAt": None,
            "finishedAt": None,
            "total": total,
            "completed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "items": current.get("items") if retry else [],
            "error": "",
        }
        atomic_write_json(run_dir / "device_capture.json", state)
        self.queued.add(run_id)
        self.queue.put_nowait(run_id)
        return self._public_state(run_id, state)

    def status(self, run_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        run_dir = (self.output_root / run_id).resolve()
        if not run_dir.is_relative_to(self.output_root) or not run_dir.is_dir():
            return {"status": "not_requested"}
        path = run_dir / "device_capture.json"
        if not path.is_file():
            return {"status": "not_requested"}
        return self._public_state(run_id, self._read_state(path))

    def sample(self, run_id: str, sample_id: str) -> dict[str, Any]:
        if not _SAFE_ID.fullmatch(sample_id):
            raise KeyError(sample_id)
        state = self.status(run_id)
        items = state.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id") == sample_id:
                    return dict(item)
        return {"id": sample_id, "status": "not_requested", "error": ""}

    def image_path(self, run_id: str, sample_id: str, kind: str) -> Path:
        if not _SAFE_ID.fullmatch(sample_id) or kind not in {"card", "full"}:
            raise KeyError(sample_id)
        run_dir = self._run_dir(run_id)
        suffix = ".png" if kind == "card" else ".jpeg"
        path = (run_dir / "device_capture" / kind / f"{sample_id}{suffix}").resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise KeyError(sample_id)
        return path

    def build_gallery(self, run_id: str) -> dict[str, Any]:
        """基于已生成的真机截图写入独立离线画廊。"""

        from ..gallery.plugin import BatchGalleryManager

        run_dir = self._run_dir(run_id)
        summary = self._read_json(run_dir / "summary.json")
        status = self.status(run_id)
        captures: list[dict[str, Any]] = []
        for item in list(status.get("items") or []):
            if not isinstance(item, dict):
                continue
            sample_id = str(item.get("id") or "")
            capture: dict[str, Any] = {
                "id": sample_id,
                "size": str(item.get("size") or ""),
                "error": str(item.get("error") or ""),
            }
            if item.get("status") == "success" and _SAFE_ID.fullmatch(sample_id):
                capture["file"] = f"{sample_id}.png"
            captures.append(capture)
        document = BatchGalleryManager.build_html(
            summary,
            {"items": captures},
            run_dir / "device_capture" / "card",
            gallery_title="真机截图画廊",
            gallery_subtitle="HarmonyOS 真机或模拟器调试渲染，不替代正式验收",
            image_alt_suffix="真机卡片截图",
            missing_title="无真机截图",
            missing_message="该样本没有可用的真机截图",
        )
        temporary_path = run_dir / "device_gallery.html.tmp"
        temporary_path.write_text(document, encoding="utf-8")
        os.replace(temporary_path, run_dir / "device_gallery.html")
        return {
            "url": self.gallery_url(run_id),
            "captured": len(captures),
        }

    def gallery_path(self, run_id: str) -> Path:
        run_dir = self._run_dir(run_id)
        path = (run_dir / "device_gallery.html").resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise KeyError(run_id)
        return path

    @staticmethod
    def gallery_url(run_id: str) -> str:
        return f"/debug/batch/runs/{quote(run_id, safe='')}/device-gallery.html"

    async def _worker_loop(self) -> None:
        while True:
            run_id = await self.queue.get()
            self.queued.discard(run_id)
            self.active_run_id = run_id
            try:
                await self._execute(run_id)
            finally:
                self.active_run_id = None
                self.queue.task_done()

    async def _execute(self, run_id: str) -> None:
        run_dir = self._run_dir(run_id)
        path = run_dir / "device_capture.json"
        state = self._read_state(path)
        state.update({"status": "running", "startedAt": _now(), "error": ""})
        atomic_write_json(path, state)
        work_root = run_dir / "device_capture" / "work"
        try:
            await self.renderer.require_available()
            summary = self._read_json(run_dir / "summary.json")
            samples = summary.get("samples")
            sample_list = samples if isinstance(samples, list) else []
            previous_items = state.get("items")
            previous = {
                str(item.get("id")): item
                for item in previous_items
                if isinstance(item, dict) and item.get("status") == "success"
            } if isinstance(previous_items, list) else {}
            items: list[dict[str, Any]] = []
            for sample in sample_list:
                if not isinstance(sample, dict):
                    continue
                sample_id = str(sample.get("id") or "")
                existing = previous.get(sample_id)
                if existing is not None and self._has_card(run_dir, sample_id):
                    items.append(dict(existing))
                    self._update_counts(state, items, len(sample_list))
                    atomic_write_json(path, state)
                    continue
                item = await self._capture_sample(run_dir, work_root, sample)
                items.append(item)
                state["items"] = items
                self._update_counts(state, items, len(sample_list))
                atomic_write_json(path, state)
            failures = int(state.get("failed", 0))
            successes = int(state.get("succeeded", 0))
            state["status"] = "ready" if failures == 0 else "partial" if successes else "failed"
        except asyncio.CancelledError:
            state["status"] = "interrupted"
            state["error"] = "调试后端关闭导致真机截图中断"
            raise
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            state["finishedAt"] = _now()
            atomic_write_json(path, state)
            device_root = (run_dir / "device_capture").resolve()
            safe_work_root = work_root.resolve()
            if safe_work_root.is_relative_to(device_root) and work_root.is_dir():
                await asyncio.to_thread(shutil.rmtree, work_root, True)
            if state.get("status") in _TERMINAL and self.on_terminal is not None:
                self.on_terminal(run_id)

    async def _capture_sample(
        self,
        run_dir: Path,
        work_root: Path,
        sample: dict[str, Any],
    ) -> dict[str, Any]:
        sample_id = str(sample.get("id") or "")
        if not _SAFE_ID.fullmatch(sample_id):
            return {"id": sample_id, "status": "failed", "error": "样本标识无效"}
        result_path = run_dir / sample_id / "result.json"
        if not result_path.is_file():
            return {"id": sample_id, "status": "skipped", "error": "样本没有最终结果"}
        result = self._read_json(result_path)
        final_attempt = result.get("finalAttempt")
        if not isinstance(final_attempt, int):
            return {"id": sample_id, "status": "skipped", "error": "样本没有最终 attempt"}
        attempt_dir = run_dir / sample_id / f"attempt_{final_attempt:03d}"
        genui = attempt_dir / "genui.jsonl"
        if not genui.is_file():
            return {"id": sample_id, "status": "skipped", "error": "样本没有可渲染的 GenUI"}
        size = self._resolve_size(attempt_dir, sample)
        full = run_dir / "device_capture" / "full" / f"{sample_id}.jpeg"
        card = run_dir / "device_capture" / "card" / f"{sample_id}.png"
        log = run_dir / "device_capture" / "logs" / f"{sample_id}.log"
        sample_work = work_root / sample_id
        try:
            await self.renderer.render(genui, size, sample_work, full, card, log)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return {
                "id": sample_id,
                "status": "failed",
                "size": size,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "id": sample_id,
            "status": "success",
            "size": size,
            "error": "",
            "cardUrl": self._image_url(run_dir.name, sample_id, "card"),
            "fullUrl": self._image_url(run_dir.name, sample_id, "full"),
        }

    @staticmethod
    def _resolve_size(attempt_dir: Path, sample: dict[str, Any]) -> str:
        blocks_path = attempt_dir / "blocks.json"
        if blocks_path.is_file():
            try:
                blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                blocks = {}
            if isinstance(blocks, dict):
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

    @staticmethod
    def _update_counts(
        state: dict[str, Any], items: list[dict[str, Any]], total: int
    ) -> None:
        state["items"] = items
        state["total"] = total
        state["completed"] = len(items)
        state["succeeded"] = sum(1 for item in items if item.get("status") == "success")
        state["failed"] = sum(1 for item in items if item.get("status") == "failed")
        state["skipped"] = sum(1 for item in items if item.get("status") == "skipped")

    @staticmethod
    def _has_card(run_dir: Path, sample_id: str) -> bool:
        return (run_dir / "device_capture" / "card" / f"{sample_id}.png").is_file()

    def _run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        path = (self.output_root / run_id).resolve()
        if not path.is_relative_to(self.output_root) or not path.is_dir():
            raise KeyError(run_id)
        return path

    def _public_state(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        result = dict(state)
        raw_items = state.get("items")
        items: list[dict[str, Any]] = []
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                item = dict(raw_item)
                sample_id = str(item.get("id") or "")
                if item.get("status") == "success" and self._has_card(
                    self._run_dir(run_id), sample_id
                ):
                    item["cardUrl"] = self._image_url(run_id, sample_id, "card")
                    item["fullUrl"] = self._image_url(run_id, sample_id, "full")
                items.append(item)
        result["items"] = items
        return result

    @staticmethod
    def _image_url(run_id: str, sample_id: str, kind: str) -> str:
        return f"/debug/batch/runs/{run_id}/device-captures/{sample_id}/{kind}"

    @staticmethod
    def _read_state(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "failed", "error": "真机截图状态文件损坏", "items": []}
        return value if isinstance(value, dict) else {"status": "failed", "items": []}

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"JSON 根节点不是对象：{path.name}")
        return value


async def run_builtin(
    manager: DeviceCaptureManager,
    run_id: str,
    _output_dir: Path,
    _config: dict[str, Any],
) -> dict[str, Any]:
    """按统一插件结果协议执行真机截图。"""

    await manager.require_available()
    manager.enqueue(run_id, retry=True)
    queue = getattr(manager, "queue", None)
    if queue is not None:
        await queue.join()
    status = manager.status(run_id)
    gallery = manager.build_gallery(run_id)
    sample_results: list[dict[str, Any]] = []
    for item in list(status.get("items") or []):
        if not isinstance(item, dict):
            continue
        sample_status = "success" if item.get("status") == "success" else "failed"
        artifacts: list[dict[str, Any]] = []
        if sample_status == "success":
            artifacts.append(
                {
                    "key": "device-capture",
                    "url": item.get("cardUrl", ""),
                    "fullUrl": item.get("fullUrl", ""),
                    "alt": f"{item.get('id', '')} 真机卡片截图",
                }
            )
        sample_results.append(
            {
                "sampleId": item.get("id", ""),
                "status": sample_status,
                "summary": str(item.get("error") or "真机截图已生成"),
                "facts": {
                    "captureStatus": str(item.get("status") or "failed"),
                    "size": str(item.get("size") or ""),
                },
                "artifacts": artifacts,
            }
        )
    succeeded = int(status.get("succeeded") or 0)
    failed = int(status.get("failed") or 0)
    skipped = int(status.get("skipped") or 0)
    result_status = "success" if status.get("status") == "ready" else "partial"
    return {
        "status": result_status,
        "sampleResults": sample_results,
        "datasetResult": {
            "status": result_status,
            "summary": f"真机画廊已生成：成功 {succeeded}，失败 {failed}，跳过 {skipped}",
            "facts": {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
            },
            "artifacts": [
                {
                    "key": "capture-summary",
                    "data": [
                        {"label": "成功", "value": succeeded},
                        {"label": "失败", "value": failed},
                        {"label": "跳过", "value": skipped},
                    ],
                },
                {
                    "key": "device-gallery",
                    "label": "打开真机截图画廊",
                    "url": gallery.get("url", ""),
                },
            ],
        },
    }
