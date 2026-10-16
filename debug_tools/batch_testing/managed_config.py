"""受管配置的字段目录、文件来源和保留格式的保存实现。"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml as pyyaml
from dotenv import dotenv_values
from dotenv.parser import parse_stream
from ruamel.yaml import YAML

ALIASES = {
    "asset.src.url.mapping": "asset_src_url_mapping",
    "edit.system.prompt": "edit_system_prompt",
    "obs.expire.time": "obs_expire_time",
    "obs.use.edge": "obs_use_edge",
    "repair.system.prompt": "repair_system_prompt",
    "sts_serverdomain": "sts_server",
    "system.prompt": "system_prompt",
    "system_prompt_file": "system_prompt",
    "edit_system_prompt_file": "edit_system_prompt",
    "repair_system_prompt_file": "repair_system_prompt",
}
PLATFORM_FIELDS = {"server_host", "server_port", "local_flag", "project_root", "config"}
SECRET_FIELDS = {"hag_osms_ak", "ids_sign_secret", "ids_access_key", "deepseek_user"}
_SAVE_LOCK = threading.Lock()


def canonical_name(name: str) -> str:
    normalized = name.lower().removeprefix("widget_service_")
    return ALIASES.get(normalized, normalized.replace(".", "_"))


def sensitive(name: str) -> bool:
    return name in SECRET_FIELDS or bool(
        re.search(
            r"api_?key|access_?key|secret|password|credential|authorization|"
            r"(?:^|_)(?:key|token)(?:_|$)",
            name,
        )
    )


def alias_priority(name: str) -> int:
    normalized = name.upper()
    return 2 * int(normalized.startswith("WIDGET_SERVICE_")) + int(normalized.endswith("_FILE"))


def config_path(root: Path) -> Path:
    relative = Path("debug_tools/debug_tool.yaml")
    for candidate in (root.parent / relative, root / relative):
        if candidate.is_file():
            return candidate
    return root.parent / relative


def yaml_document(path: Path) -> Any:
    yaml = YAML()
    yaml.preserve_quotes = True
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        if path.name == "default_config.yaml":
            # 与微服务 ConfigHelper 保持一致，兼容既有默认文件的重复键后值语义。
            document = pyyaml.safe_load(content)
        else:
            document = yaml.load(content)
    except Exception as exc:
        raise ValueError(f"配置文件解析失败: {path.name} ({type(exc).__name__})") from None
    if not isinstance(document, dict):
        raise ValueError(f"配置文件根节点必须是对象: {path.name}")
    return document


def mapping(value: Any, description: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{description} 必须是对象")
    return value


def field_types(root: Path) -> dict[str, str]:
    """只解析字段声明，不导入带网络、日志及配置初始化副作用的服务模块。"""
    path = root / "cloud/config/config.py"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "widget_service/cloud/config/config.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    result: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Settings":
            continue
        pending = list(node.body)
        while pending:
            member = pending.pop(0)
            if isinstance(member, ast.If):
                pending.extend(member.body)
                pending.extend(member.orelse)
            if not isinstance(member, ast.AnnAssign):
                continue
            if isinstance(member.target, ast.Name):
                annotation = ast.unparse(member.annotation).split("[", maxsplit=1)[0]
                result[canonical_name(member.target.id)] = annotation
    return result


def read_dotenv(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    for binding in parse_stream(io.StringIO(text)):
        if binding.error:
            raise ValueError(f".env 第 {binding.original.line} 行格式错误")
    return dict(dotenv_values(stream=io.StringIO(text), interpolate=False))


def typed_value(name: str, value: Any, kind: str) -> Any:
    result: Any = value
    try:
        if kind == "bool":
            if isinstance(value, bool):
                result = value
            elif isinstance(value, str) and value.lower() in {
                "true",
                "false",
                "1",
                "0",
                "yes",
                "no",
                "on",
                "off",
                "y",
                "n",
                "t",
                "f",
            }:
                result = value.lower() in {"true", "1", "yes", "on", "y", "t"}
            else:
                raise ValueError("必须为布尔值")
        elif kind in {"int", "float"}:
            if isinstance(value, bool) or value is None:
                raise ValueError("必须为数值")
            if kind == "int" and isinstance(value, float):
                raise ValueError("必须为整数")
            if kind == "int" and isinstance(value, str):
                numeric = Decimal(value)
                if not numeric.is_finite() or numeric != numeric.to_integral_value():
                    raise ValueError("必须为整数")
                result = int(numeric)
            else:
                result = int(value) if kind == "int" else float(value)
            if kind == "float" and not math.isfinite(result):
                raise ValueError("必须为有限数值")
        elif kind in {"dict", "list", "tuple"}:
            result = json.loads(value) if isinstance(value, str) else value
            expected = dict if kind == "dict" else (list, tuple)
            if not isinstance(result, expected):
                raise ValueError("结构类型错误")
        elif kind in {"str", "Path"}:
            if not isinstance(value, str):
                raise ValueError("必须为字符串")
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        raise ValueError(f"{name.upper()} 配置类型错误，应为 {kind}") from None
    return result


@dataclass
class Configuration:
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    directories: dict[str, Path] = field(default_factory=dict)
    exposed: list[str] = field(default_factory=list)
    types: dict[str, str] = field(default_factory=dict)
    version: str = ""
    local_config_exists: bool = False

    def editable(self, name: str) -> bool:
        return name in self.types and name not in PLATFORM_FIELDS and not sensitive(name)

    def public(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        fields: list[dict[str, Any]] = []
        for name, value in self.values.items():
            secret = sensitive(name)
            reason = ""
            if secret:
                reason = "敏感配置仅在服务端管理"
            elif name in {"server_host", "server_port"}:
                reason = "由平台管理，监听地址和端口在启动时自动分配"
            elif name in PLATFORM_FIELDS:
                reason = "由微服务运行环境管理"
            elif name not in self.types:
                reason = "当前微服务未识别此字段"
            if not secret:
                values[name] = value
            fields.append(
                {
                    "name": name,
                    "displayName": name.upper(),
                    "type": self.types.get(name, "unknown"),
                    "source": self.sources.get(name),
                    "group": "exposed" if name in self.exposed else "defaults",
                    "sensitive": secret,
                    "editable": self.editable(name),
                    "readOnlyReason": reason,
                }
            )
        return {
            "values": values,
            "sources": self.sources,
            "fields": fields,
            "exposedKeys": self.exposed,
            "version": self.version,
            "localConfigExists": self.local_config_exists,
        }


def read_configuration(root: Path, *, debug_path: Path | None = None) -> Configuration:
    debug_path = debug_path if debug_path is not None else config_path(root)
    default_path = root / "cloud/config/default_config.yaml"
    env_path = root / ".env"
    config = Configuration(types=field_types(root), local_config_exists=debug_path.is_file())
    digest = hashlib.sha256()
    for path in (default_path, env_path, debug_path):
        digest.update(path.name.encode())
        digest.update(path.read_bytes() if path.is_file() else b"missing")
    config.version = digest.hexdigest()
    for name, value in sorted(os.environ.items(), key=lambda item: alias_priority(item[0])):
        canonical = canonical_name(name)
        if canonical in config.types:
            config.values[canonical] = value
            config.sources[canonical] = "environment"
            config.directories[canonical] = root
    layers = [
        (yaml_document(default_path), "default_config.yaml", default_path.parent),
        (
            read_dotenv(env_path),
            ".env",
            root,
        ),
    ]
    backend = mapping(yaml_document(debug_path).get("widget_backend"), "widget_backend")
    declared: set[str] = set()
    for section in ("defaults", "exposed"):
        entries = mapping(backend.get(section), f"widget_backend.{section}")
        for key in entries:
            name = canonical_name(str(key))
            if name in declared:
                raise ValueError(f"widget_backend 参数重复: {name}")
            declared.add(name)
            if section == "exposed":
                config.exposed.append(name)
        layers.append((entries, "debug_tool.yaml", debug_path.parent))
    for entries, source, directory in layers:
        ordered = sorted(entries.items(), key=lambda item: alias_priority(str(item[0])))
        for key, value in ordered:
            name = canonical_name(str(key))
            config.values[name] = value
            config.sources[name] = source
            config.directories[name] = directory
    for name, value in config.values.items():
        kind = config.types.get(name, "unknown")
        if name == "asset_src_url_mapping" and value == "":
            value = {}
        config.values[name] = typed_value(name, value, kind)
    return config


def validate_changes(
    config: Configuration, changes: dict[str, Any], *, exposed: bool
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_name, value in changes.items():
        name = canonical_name(raw_name)
        allowed = config.editable(name) and name in config.values
        if exposed:
            allowed = allowed and name in config.exposed
        if not allowed:
            raise ValueError(f"不允许修改配置项: {name.upper()}")
        if name in result:
            raise ValueError(f"配置项重复: {name.upper()}")
        converted = typed_value(name, value, config.types.get(name, "unknown"))
        result[name] = converted
        if name.endswith(("_attempts", "_count")):
            if isinstance(converted, (int, float)) and converted < 0:
                raise ValueError(f"{name.upper()} 不能为负数")
        if name in {"openai_master_client", "openai_fallback_client"}:
            if value not in {"mep", "llmclient", "deepseek_platform", "deepseek_official_http"}:
                raise ValueError(f"{name.upper()} 模型类型无效")
    return result


def runtime_values(config: Configuration) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in config.values.items():
        if name not in config.types or name in PLATFORM_FIELDS:
            continue
        directory = config.directories.get(name)
        if directory is None:
            raise ValueError(f"配置来源目录缺失: {name}")
        if isinstance(value, str) and value.startswith("@file:"):
            value = (directory / value.removeprefix("@file:").strip()).read_text(encoding="utf-8")
        elif isinstance(value, str) and value.startswith("@prompt:"):
            from debug_tools.paths import ensure_cloud_import_path

            ensure_cloud_import_path()
            from services.compact_prompt_loader import assemble_prompts

            reference = value.removeprefix("@prompt:")
            prompt_dir, separator, prompt_name = reference.partition("#")
            if not separator:
                raise ValueError(f"提示词引用格式错误: {name}")
            prompts = assemble_prompts(directory / prompt_dir)
            value = prompts.get(prompt_name)
            if value is None:
                raise ValueError(f"提示词名称不存在: {name}")
        elif name.endswith("system_prompt") and isinstance(value, str):
            if "\n" not in value:
                path = directory / value
                if path.is_file():
                    value = path.read_text(encoding="utf-8")
        result[name] = value
    base_url = result.get("hag_slb_url")
    if isinstance(base_url, str):
        for name in ("osms_prepare_url", "osms_complete_url", "osms_query_url", "osms_delete_url"):
            value = result.get(name)
            if isinstance(value, str):
                result[name] = urljoin(base_url, value)
    selected_default = config.sources.get("deepseek_platform_model_name") == "default_config.yaml"
    if result.get("deepseek_platform_model_select") is True and selected_default:
        thinking_name = config.values.get("deepseek_platform_thinking_model_name")
        if isinstance(thinking_name, str):
            result["deepseek_platform_model_name"] = thinking_name
    return result


class ConfigConflict(ValueError):
    """配置已被另一位编辑者修改。"""


def save_configuration(root: Path, changes: dict[str, Any], version: str) -> dict[str, Any]:
    with _SAVE_LOCK:
        config = read_configuration(root)
        if config.version != version:
            raise ConfigConflict("配置文件已变化，请重新加载后再保存")
        updates = validate_changes(config, changes, exposed=False)
        updates = {
            name: value for name, value in updates.items() if value != config.values.get(name)
        }
        if not updates:
            return config.public()
        path = config_path(root)
        document = yaml_document(path)
        backend = mapping(document.get("widget_backend"), "widget_backend")
        document["widget_backend"] = backend
        for name, value in updates.items():
            target = mapping(backend.get("defaults"), "widget_backend.defaults")
            backend["defaults"] = target
            target_key = name
            for section in ("defaults", "exposed"):
                entries = mapping(backend.get(section), section)
                for key in entries:
                    if canonical_name(str(key)) == name:
                        target = entries
                        target_key = key
            target[target_key] = value
            config.values[name] = value
            config.directories[name] = path.parent
            config.sources[name] = "debug_tool.yaml"
        # 引用文件错误也必须在原文件被替换前报告。
        runtime_values(config)
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 120
        stream = io.StringIO()
        yaml.dump(document, stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".debug-config-", dir=path.parent)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(stream.getvalue())
                handle.flush()
                os.fsync(handle.fileno())
            if read_configuration(root).version != version:
                raise ConfigConflict("配置文件已变化，请重新加载后再保存")
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return read_configuration(root).public()
