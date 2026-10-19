"""Resolve local DevEco and Node.js tools for every debug workflow."""

from __future__ import annotations

import logging
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from debug_tools.paths import DEBUG_TOOLS_ROOT, REPOSITORY_ROOT

DEFAULT_CONFIG_PATH = DEBUG_TOOLS_ROOT / "debug_tool.yaml"
PATH_REFERENCE_PATTERN = re.compile(r"^\$\{environment\.([A-Za-z][A-Za-z0-9_]*)\}")


class ToolchainError(RuntimeError):
    """The configured local toolchain cannot be resolved safely."""


@dataclass(frozen=True)
class Toolchain:
    deveco_studio_home: Path | None
    node_executable: Path
    node_source: str
    java_home: Path | None
    sdk_home: Path | None
    hdc: Path | None
    hvigor: Path | None
    ohpm: Path | None
    emulator: Path | None
    path_variables: dict[str, Path] = field(default_factory=dict)

    @property
    def node_home(self) -> Path:
        return self.node_executable.parent

    def environment(self, base: dict[str, str] | None = None) -> dict[str, str]:
        environment = dict(base) if base is not None else os.environ.copy()
        environment["NODE_HOME"] = str(self.node_home)
        paths = [self.node_home]
        if self.java_home is not None:
            environment["JAVA_HOME"] = str(self.java_home)
            paths.append(self.java_home / "bin")
        if self.sdk_home is not None:
            environment["DEVECO_SDK_HOME"] = str(self.sdk_home)
        if self.hdc is not None:
            paths.append(self.hdc.parent)
        existing = environment.get("PATH", "")
        environment["PATH"] = os.pathsep.join([*(str(path) for path in paths), existing])
        return environment


def load_toolchain(config_path: Path | None = None) -> Toolchain:
    """Load shared paths from the unified debug configuration."""

    path = config_path or DEFAULT_CONFIG_PATH
    try:
        root = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ToolchainError(f"无法读取调试环境配置：{path}") from exc
    if not isinstance(root, dict):
        raise ToolchainError("debug_tool.yaml 根节点必须是对象")
    platform = _mapping(root.get("platform"), "platform")
    environment = _mapping(platform.get("environment"), "platform.environment")
    path_variables = _resolve_path_variables(environment)
    deveco_home = path_variables.get("deveco_studio_home")
    node_executable, node_source = _resolve_node(
        _first_text(environment.get("node_executable")),
        path_variables,
    )
    return Toolchain(
        deveco_studio_home=deveco_home,
        node_executable=node_executable,
        node_source=node_source,
        java_home=path_variables.get("java_home"),
        sdk_home=path_variables.get("sdk_home"),
        hdc=path_variables.get("hdc"),
        hvigor=path_variables.get("hvigor"),
        ohpm=path_variables.get("ohpm"),
        emulator=path_variables.get("emulator"),
        path_variables=path_variables,
    )


def load_optional_toolchain() -> Toolchain | None:
    """启动时检查可选工具链；功能执行时仍通过 load_toolchain 严格校验。"""
    toolchain: Toolchain | None = None
    try:
        toolchain = load_toolchain()
    except ToolchainError as exc:
        logging.getLogger(__name__).warning(
            "本机截图工具暂不可用，调试平台继续启动；使用前请完善配置：%s", exc
        )
    return toolchain


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ToolchainError(f"debug_tool.yaml 的 {name} 必须是对象")
    return value


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_config_path(
    value: str,
    *,
    variables: Mapping[str, Path] | None = None,
    deveco_home: Path | None = None,
    base: Path = REPOSITORY_ROOT,
) -> Path:
    """Resolve a path and a leading ``environment`` path reference."""

    expanded = value.strip()
    available = dict(variables or {})
    if deveco_home is not None:
        available.setdefault("deveco_studio_home", deveco_home)
    match = PATH_REFERENCE_PATTERN.match(expanded)
    if match is not None:
        name = match.group(1)
        referenced = available.get(name)
        if referenced is None:
            raise ToolchainError(f"路径引用了未配置的 environment.{name}")
        suffix = expanded[match.end():].lstrip("/\\")
        candidate = referenced / Path(suffix) if suffix else referenced
    elif "${environment." in expanded:
        raise ToolchainError(f"environment 路径变量只能用于路径开头：{value}")
    else:
        candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _node_candidate(path: Path) -> Path:
    if path.is_dir():
        executable_name = "node.exe" if os.name == "nt" else "node"
        return path / executable_name
    return path


def _resolve_path_variables(values: Mapping[str, Any]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    resolving: set[str] = set()

    def resolve(name: str) -> Path:
        cached = resolved.get(name)
        if cached is not None:
            return cached
        if name in resolving:
            raise ToolchainError(f"environment 路径变量循环引用：{name}")
        raw_value = values.get(name)
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ToolchainError(f"environment.{name} 必须是非空路径")
        resolving.add(name)
        expanded = raw_value.strip()
        match = PATH_REFERENCE_PATTERN.match(expanded)
        if match is not None:
            referenced = resolve(match.group(1))
            suffix = expanded[match.end():].lstrip("/\\")
            candidate = referenced / Path(suffix) if suffix else referenced
        elif "${environment." in expanded:
            raise ToolchainError(
                f"environment 路径变量只能用于路径开头：{raw_value}"
            )
        else:
            candidate = Path(expanded).expanduser()
            if not candidate.is_absolute():
                candidate = REPOSITORY_ROOT / candidate
        resolving.remove(name)
        result = candidate.resolve()
        resolved[name] = result
        return result

    for key, raw_value in values.items():
        if isinstance(key, str) and isinstance(raw_value, str) and raw_value.strip():
            resolve(key)
    return resolved


def _resolve_node(
    value: str | None,
    path_variables: Mapping[str, Path],
) -> tuple[Path, str]:
    if value is not None:
        configured = _node_candidate(
            resolve_config_path(value, variables=path_variables)
        )
        if not configured.is_file():
            raise ToolchainError(f"显式配置的 Node.js 不存在：{configured}")
        return configured, "configured"
    discovered = shutil.which("node")
    if discovered:
        return Path(discovered).resolve(), "path"
    raise ToolchainError("未配置 Node.js，且系统 PATH 中未找到 Node")
