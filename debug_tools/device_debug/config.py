"""解析本机工具链和 Debug Tools 内置 ArkTS 工程。"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json5
import yaml

from debug_tools.paths import DEBUG_TOOLS_ROOT
from debug_tools.runtime_environment import (
    ToolchainError,
    load_toolchain,
    resolve_config_path,
)

from .commands import DeviceError


def read_object(path: Path) -> dict[str, Any]:
    value = json5.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise DeviceError(f"配置应为对象：{path.name}", 503)
    return value


@dataclass(frozen=True)
class Config:
    hdc: Path
    project: Path
    sdk: Path
    java: Path
    node: Path
    hvigor: Path
    ohpm: Path
    emulator: Path
    instances: Path
    images: Path
    output: Path
    build_timeout: float = 300.0
    render_timeout: float = 30.0
    capture_attempts: int = 6
    capture_delay_seconds: float = 1.0
    start_timeout: float = 120.0
    start_poll: float = 2.0
    node_source: str = "configured"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        config_path = path or (DEBUG_TOOLS_ROOT / "debug_tool.yaml")
        try:
            content = config_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise DeviceError(
                f"本机配置不存在，请在连接配置页查看配置说明：{config_path}", 503
            ) from exc
        root = yaml.safe_load(content)
        platform = root.get("platform", {}) if isinstance(root, dict) else {}
        if not isinstance(platform, dict):
            raise DeviceError("platform 配置必须是对象", 503)
        values = platform.get("device_capture", {})
        if not isinstance(values, dict):
            raise DeviceError("设备配置必须是对象", 503)
        capture_delay = values.get("capture_delay_seconds", 1.0)
        valid_delay_type = (
            isinstance(capture_delay, (int, float)) and not isinstance(capture_delay, bool)
        )
        if not valid_delay_type:
            raise DeviceError("capture_delay_seconds 必须为 0 到 30 秒的数值", 503)
        if not math.isfinite(capture_delay) or not 0.0 <= capture_delay <= 30.0:
            raise DeviceError("capture_delay_seconds 必须为 0 到 30 秒的数值", 503)
        try:
            toolchain = load_toolchain(config_path)
        except ToolchainError as exc:
            raise DeviceError(str(exc), 503) from exc

        def configured(key: str, default: Path | None) -> Path:
            value = values.get(key)
            if isinstance(value, str) and value:
                try:
                    return resolve_config_path(
                        value,
                        variables=toolchain.path_variables,
                    )
                except ToolchainError as exc:
                    raise DeviceError(str(exc), 503) from exc
            if default is None:
                raise DeviceError(f"未配置 DevEco 工具：{key}", 503)
            return default

        return cls(
            hdc=configured("hdc", toolchain.hdc),
            project=DEBUG_TOOLS_ROOT / "a2ui_render",
            sdk=configured("deveco_sdk_home", toolchain.sdk_home),
            java=configured("java_home", toolchain.java_home),
            node=toolchain.node_executable,
            hvigor=configured("hvigor", toolchain.hvigor),
            ohpm=configured("ohpm", toolchain.ohpm),
            emulator=configured("emulator", toolchain.emulator),
            instances=configured("emulator_instance_root", None),
            images=configured("emulator_image_root", None),
            output=configured("output_root", None),
            build_timeout=float(values.get("command_timeout_seconds", 300.0)),
            render_timeout=float(values.get("render_timeout_seconds", 30.0)),
            capture_attempts=max(1, int(values.get("capture_attempts", 6))),
            capture_delay_seconds=float(capture_delay),
            start_timeout=float(values.get("emulator_start_timeout_seconds", 120.0)),
            start_poll=max(0.2, float(values.get("emulator_poll_seconds", 2.0))),
            node_source=toolchain.node_source,
        )

    def environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(JAVA_HOME=str(self.java), DEVECO_SDK_HOME=str(self.sdk))
        env["NODE_HOME"] = str(self.node.parent)
        env["PATH"] = os.pathsep.join(
            [
                str(self.node.parent),
                str(self.java / "bin"),
                str(self.hdc.parent),
                env.get("PATH", ""),
            ]
        )
        return env

    def checks(self) -> list[dict[str, Any]]:
        checks = []
        for name, path in (
            ("HDC", self.hdc),
            ("Node", self.node),
            ("JBR", self.java / "bin/java.exe"),
            ("Hvigor", self.hvigor),
            ("Ohpm", self.ohpm),
            ("SDK", self.sdk),
            ("工程", self.project / "build-profile.json5"),
            ("虚拟机目录", self.instances),
            ("模拟器", self.emulator),
        ):
            checks.append({"name": name, "ok": path.exists(), "detail": str(path)})
        for item in checks:
            if item.get("name") == "Node":
                item["detail"] = f"{item.get('detail')}（来源：{self.node_source}）"
        try:
            project = Project.read(self.project)
            checks.append(
                {
                    "name": "真机签名",
                    "ok": project.signed,
                    "detail": (
                        "已配置（构建时验证有效性）"
                        if project.signed
                        else "未配置签名；仅模拟器可使用 unsigned HAP"
                    ),
                }
            )
        except (OSError, ValueError, DeviceError) as exc:
            checks.append({"name": "工程配置", "ok": False, "detail": str(exc)})
        return checks

    @staticmethod
    def status_items(
        checks: list[dict[str, Any]],
        physical_count: int,
        emulator_count: int,
        unknown_count: int,
        startable_count: int,
        discovery_error: str,
    ) -> list[dict[str, Any]]:
        by_name = {str(item.get("name")): item for item in checks}
        tool_names = ("HDC", "Node", "JBR", "Hvigor", "Ohpm", "SDK")
        tool_checks = [by_name.get(name, {}) for name in tool_names]
        tool_ok = all(bool(item.get("ok")) for item in tool_checks)
        tool_detail = "；".join(
            f"{name}: {by_name.get(name, {}).get('detail', '未检查')}" for name in tool_names
        )
        project = by_name.get("工程", {})
        signing = by_name.get("真机签名", by_name.get("工程配置", {}))
        physical_available = physical_count > 0 or unknown_count > 0
        physical_detail = f"在线 {physical_count} 台"
        if unknown_count:
            physical_detail += f"，另有 {unknown_count} 台类型待确认"
        if discovery_error:
            physical_detail = discovery_error
        emulator_available = emulator_count > 0 or startable_count > 0
        emulator_detail = f"在线 {emulator_count} 台，可启动 {startable_count} 个"
        return [
            {"id": "toolchain", "label": "DevEco 工具链", "ok": tool_ok, "detail": tool_detail},
            {
                "id": "project",
                "label": "渲染工程",
                "ok": bool(project.get("ok")),
                "detail": str(project.get("detail") or "未配置"),
            },
            {
                "id": "signing",
                "label": "工程签名",
                "ok": bool(signing.get("ok")),
                "detail": str(signing.get("detail") or "未配置"),
            },
            {
                "id": "physical",
                "label": "真机",
                "ok": physical_available,
                "detail": physical_detail,
            },
            {
                "id": "emulator",
                "label": "模拟器",
                "ok": emulator_available,
                "detail": emulator_detail,
            },
        ]


@dataclass(frozen=True)
class Project:
    bundle: str
    module: str
    ability: str
    signed: bool

    @classmethod
    def read(cls, path: Path) -> Project:
        app = read_object(path / "AppScope/app.json5").get("app", {})
        module = read_object(path / "entry/src/main/module.json5").get("module", {})
        profile = read_object(path / "build-profile.json5").get("app", {})
        if not all(isinstance(value, dict) for value in (app, module, profile)):
            raise DeviceError("工程 app/module 配置无效", 503)
        bundle = app.get("bundleName")
        name = module.get("name")
        ability = module.get("mainElement")
        for value in (bundle, name, ability):
            if not isinstance(value, str) or not value:
                raise DeviceError("工程缺少应用、模块或 Ability 名称", 503)
            if not all(char.isalnum() or char in "._" for char in value):
                raise DeviceError("工程标识包含不支持的字符", 503)
        configs = profile.get("signingConfigs", [])
        products = profile.get("products", [])
        if not isinstance(configs, list) or not isinstance(products, list):
            raise DeviceError("工程签名和产品配置必须是数组", 503)
        signed = False
        for product in products:
            if not isinstance(product, dict) or product.get("name") != "default":
                continue
            signing = product.get("signingConfig")
            for config in configs:
                if isinstance(config, dict) and config.get("name") == signing:
                    signed = bool(config.get("material"))
        return cls(bundle, name, ability, signed)
