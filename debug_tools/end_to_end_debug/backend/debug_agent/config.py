from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic.aliases import AliasChoices

from debug_tools.batch_testing.managed_config import (
    canonical_name,
    read_configuration,
    runtime_values,
)
from debug_tools.paths import REPOSITORY_ROOT, WIDGET_SERVICE_ROOT


def _loopback(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class SkillProfile:
    name: str
    directory: Path
    display_name: str = ""
    description: str = ""
    system_prompt: Path | None = None


@dataclass(frozen=True)
class QuickPrompt:
    label: str
    prompt: str


@dataclass(frozen=True)
class DebugConfig:
    config_path: Path
    skill_root: Path
    profiles: dict[str, SkillProfile]
    default_profile: str
    system_prompt: Path | None = None
    quick_prompts: tuple[QuickPrompt, ...] = ()

    def profile(self, name: str | None = None) -> SkillProfile:
        selected = name or self.default_profile
        if selected not in self.profiles:
            raise ValueError(f"未知 Debug Skill profile: {selected}")
        return self.profiles[selected]

    def available_profiles(self) -> list[dict[str, str]]:
        return [
            {
                "id": key,
                "name": item.name,
                "displayName": item.directory.name,
                "description": item.description,
            }
            for key, item in self.profiles.items()
        ]


@dataclass(frozen=True)
class DebugSettings:
    host: str = "127.0.0.1"
    port: int = 8888
    upstream_base_url: str = "ws://127.0.0.1:8855"
    skill_name: str = "harmony-card-generation-online"
    skill_root: Path | None = None
    skill_directory: Path | None = None
    system_prompt_path: Path | None = None
    skill_profile: str = "online"
    skill_display_name: str = ""
    skill_version: str = ""
    bundle_name: str = "com.omega_w_0823.hmservice"
    default_uid: str = "debug-user"
    default_device_id: str = "debug-device"
    default_phone_type: str = "ALN-AL00"
    default_app_version: str = "11.9.9.342"
    default_rom_version: str = "ALN-AL00 7.0.0.100"
    default_locale: str = "zh-CN"
    default_country_code: str = "CN"
    max_steps: int = 20
    max_tokens: int = 8192
    request_timeout_seconds: float = 180.0
    skill_resource_max_bytes: int = 256 * 1024
    log_level: str = "INFO"
    log_trace: bool = False
    log_value_limit: int = 160
    available_profiles: tuple[dict[str, str], ...] = field(default_factory=tuple)
    quick_prompts: tuple[QuickPrompt, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not _loopback(self.host):
            raise ValueError("Debug 服务只允许绑定回环地址")
        if not 1 <= self.port <= 65535:
            raise ValueError("Debug 端口必须在 1 到 65535 之间")
        parsed = urlsplit(self.upstream_base_url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise ValueError("工具服务必须是有效的 WebSocket 地址")
        if self.max_steps < 1 or self.max_tokens < 1:
            raise ValueError("Debug 步骤数和模型输出上限必须为正数")

    @classmethod
    def from_config(
        cls,
        config: DebugConfig,
        production: Any,
        *,
        profile: str | None = None,
        port: int | None = None,
        log_level: str | None = None,
        trace: bool | None = None,
    ) -> DebugSettings:
        selected = config.profile(profile)
        raw = _read_yaml(config.config_path)
        platform = raw.get("platform", {})
        if not isinstance(platform, dict):
            raise ValueError("Debug platform 配置必须是对象")
        server = platform.get("server", {})
        defaults = raw.get("defaults", {})
        logging = raw.get("logging", {})
        return cls(
            host=str(server.get("host", "127.0.0.1")),
            port=port or int(server.get("port", 8888)),
            upstream_base_url=str(
                server.get("upstream_base_url", f"ws://127.0.0.1:{production.server_port}")
            ),
            skill_name=selected.name,
            skill_root=config.skill_root,
            skill_directory=selected.directory,
            system_prompt_path=selected.system_prompt,
            skill_profile=profile or config.default_profile,
            skill_display_name=selected.display_name,
            skill_version=selected.name,
            bundle_name=str(server.get("bundle_name", cls.bundle_name)),
            default_uid=str(defaults.get("uid", cls.default_uid)),
            default_device_id=str(defaults.get("device_id", cls.default_device_id)),
            default_phone_type=str(defaults.get("phone_type", cls.default_phone_type)),
            default_app_version=str(defaults.get("app_version", cls.default_app_version)),
            default_rom_version=str(defaults.get("rom_version", cls.default_rom_version)),
            default_locale=str(defaults.get("locale", cls.default_locale)),
            default_country_code=str(defaults.get("country_code", cls.default_country_code)),
            max_steps=int(server.get("max_steps", cls.max_steps)),
            max_tokens=int(server.get("max_tokens", cls.max_tokens)),
            request_timeout_seconds=float(
                server.get("request_timeout_seconds", cls.request_timeout_seconds)
            ),
            skill_resource_max_bytes=int(
                server.get("skill_resource_max_bytes", cls.skill_resource_max_bytes)
            ),
            log_level=log_level or str(logging.get("level", cls.log_level)),
            log_trace=trace if trace is not None else bool(logging.get("trace", False)),
            log_value_limit=int(logging.get("value_limit", cls.log_value_limit)),
            available_profiles=tuple(config.available_profiles()),
            quick_prompts=config.quick_prompts,
        )

    @classmethod
    def from_settings(cls, settings: Any | None = None) -> DebugSettings:
        from config.config import Settings

        path = _debug_config_path(REPOSITORY_ROOT)
        config = load_debug_config(path, REPOSITORY_ROOT)
        production = settings or load_main_agent_model_settings(config, Settings)
        return cls.from_config(config, production)


def load_debug_config(path: Path, repo_root: Path) -> DebugConfig:
    raw = _read_yaml(path)
    main_agent = raw.get("main_agent", {})
    if not isinstance(main_agent, dict):
        raise ValueError("Debug main_agent 配置必须是对象")
    shared_prompt = main_agent.get("system_prompt")
    prompt_path = None
    if shared_prompt:
        prompt_path = Path(shared_prompt)
        if not prompt_path.is_absolute():
            prompt_path = _resolve_repo_file(prompt_path, repo_root, path)
    skill_root = Path(main_agent.get("skill_root", "skills"))
    if not skill_root.is_absolute():
        skill_root = (repo_root / skill_root).resolve()
    profiles: dict[str, SkillProfile] = {}
    configured_profiles = main_agent.get("profiles") or {}
    if not isinstance(configured_profiles, dict):
        raise ValueError("Debug profiles 配置必须是对象")
    for key, value in configured_profiles.items():
        if not isinstance(value, dict):
            continue
        name = str(value.get("name", key))
        profiles[str(key)] = SkillProfile(
            name,
            (skill_root / name).resolve(),
            str(value.get("display_name", name)),
            str(value.get("description", "")),
            prompt_path,
        )
    if bool(main_agent.get("auto_discover_profiles", True)) and skill_root.is_dir():
        for directory in sorted(skill_root.iterdir(), key=lambda item: item.name.lower()):
            if not _is_debug_skill_directory(directory):
                continue
            if any(item.directory == directory.resolve() for item in profiles.values()):
                continue
            profiles.setdefault(
                directory.name,
                SkillProfile(
                    _skill_name_from_file(directory),
                    directory,
                    directory.name,
                ),
            )
    if not profiles:
        raise ValueError(f"Debug Skill 主目录不存在可用 Skill: {skill_root}")
    quick_prompts = _load_quick_prompts(main_agent.get("ui", {}))
    configured_default = str(main_agent.get("default_profile", ""))
    default_profile = configured_default if configured_default in profiles else next(iter(profiles))
    return DebugConfig(
        path.resolve(),
        skill_root,
        profiles,
        default_profile,
        prompt_path,
        quick_prompts,
    )


def load_main_agent_model_settings(
    config: DebugConfig,
    settings_type: type[Any],
    *,
    project_root: Path = WIDGET_SERVICE_ROOT,
) -> Any:
    """复用受管微服务配置来源、覆盖顺序和运行时值解析。"""

    configuration = read_configuration(project_root, debug_path=config.config_path)
    values = runtime_values(configuration)
    arguments: dict[str, Any] = {}
    for field_name, field_info in settings_type.model_fields.items():
        canonical = canonical_name(field_name)
        if canonical not in values:
            continue
        alias = field_info.validation_alias
        if isinstance(alias, AliasChoices):
            alias = alias.choices[0]
        key = alias if isinstance(alias, str) else field_name
        arguments[key] = values.get(canonical)
    return settings_type(_env_file=None, **arguments)


def _debug_config_path(repo_root: Path) -> Path:
    relative = Path("debug_tools/debug_tool.yaml")
    candidates = (
        repo_root / relative,
        repo_root / "widget_service" / relative,
        Path(__file__).resolve().parents[3] / "debug_tool.yaml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _resolve_repo_file(relative: Path, repo_root: Path, config_path: Path) -> Path:
    """解析外层仓库和 widget_service 内的相对配置路径。"""

    candidates = [(repo_root / relative).resolve()]
    project_root = config_path.resolve().parents[3]
    candidates.append((project_root / relative).resolve())
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _is_debug_skill_directory(directory: Path) -> bool:
    skill_file = directory / "SKILL.md"
    if not directory.is_dir() or not skill_file.is_file():
        return False
    try:
        content = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(re.search(r"^name:\s*[\"']?([^\"'\r\n]+)[\"']?\s*$", content, re.MULTILINE))


def _skill_name_from_file(directory: Path) -> str:
    try:
        content = (directory / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return directory.name
    name_match = re.search(
        r"^name:\s*[\"']?([^\"'\r\n]+)[\"']?\s*$", content, re.MULTILINE
    )
    return name_match.group(1).strip() if name_match else directory.name


def _load_quick_prompts(value: Any) -> tuple[QuickPrompt, ...]:
    if not isinstance(value, dict):
        return ()
    raw_prompts = value.get("quick_prompts")
    if not isinstance(raw_prompts, list):
        return ()
    prompts: list[QuickPrompt] = []
    for item in raw_prompts:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        prompt = item.get("prompt")
        if isinstance(label, str) and label.strip() and isinstance(prompt, str) and prompt.strip():
            prompts.append(QuickPrompt(label.strip(), prompt.strip()))
    return tuple(prompts)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logging.getLogger(__name__).warning(
            "本机配置不存在，使用默认配置继续启动；请在连接配置页查看配置说明：%s", path
        )
        content = ""
    value = yaml.safe_load(content) or {}
    if not isinstance(value, dict):
        raise ValueError("Debug 配置根节点必须是对象")
    return value
