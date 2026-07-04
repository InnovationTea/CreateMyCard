import re
from typing import Any

from jsonschema import Draft202012Validator
from packaging.version import InvalidVersion, Version

from core.config import get_settings
from core.errors import ErrorCode
from models.capability import DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, EventAction
from services.capability_registry import CapabilityRegistry
from services.json_loader import load_json


class DeviceCapabilityResolver:
    """基于 IDS 状态和注册表依赖解析候选能力。"""

    def __init__(self, registry: CapabilityRegistry) -> None:
        """初始化设备能力解析器。

        入参：
        - registry：当前版本能力注册表。
        出参：无。
        """
        self.registry = registry
        self.settings = get_settings()

    def resolve_data_bindings(
        self,
        candidate_bindings: list[CandidateDataBinding],
        rom_version: str,
        app_version: str,
        xiaoyi_version: str,
    ) -> tuple[list[CandidateDataBinding], list[DataCapability], list[RemovedCapability]]:
        """过滤候选数据绑定。

        入参：
        - candidate_bindings：主 Agent 传入的候选数据绑定。
        - rom_version：当前设备 ROM 版本。
        - app_version：当前宿主 App 版本。
        - xiaoyi_version：当前小艺版本。
        出参：有效数据绑定、有效数据能力定义、被移除能力列表。
        """
        ids_state = self._load_ids_state()
        effective_bindings: list[CandidateDataBinding] = []
        effective_capabilities: list[DataCapability] = []
        removed: list[RemovedCapability] = []

        for binding in candidate_bindings:
            # 未注册或不可用的能力不能进入最终 CardSpec。
            capability = self.registry.get_data_capability(binding.capabilityId)
            if capability is None:
                removed.append(self._removed(binding.capabilityId, ErrorCode.UNKNOWN_CAPABILITY))
                continue

            reason = self._check_common_dependencies(
                capability, rom_version, app_version, xiaoyi_version, ids_state
            )
            if reason is not None:
                removed.append(self._removed(binding.capabilityId, reason))
                continue

            if not self._valid_arguments(binding.arguments, capability.inputSchema):
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue

            write_result_to = binding.writeResultTo or capability.defaultWriteResultTo
            # CardSpec 数据写入路径必须位于 /data/ 下，方便 DSL 绑定路径可追踪。
            if write_result_to is None or not write_result_to.startswith("/data/"):
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue

            effective_bindings.append(
                CandidateDataBinding(
                    capabilityId=binding.capabilityId,
                    arguments=binding.arguments,
                    writeResultTo=write_result_to,
                )
            )
            effective_capabilities.append(capability)

        conflict_id = self._find_write_result_conflict(effective_bindings)
        if conflict_id:
            effective_bindings = [
                item for item in effective_bindings if item.capabilityId != conflict_id
            ]
            effective_capabilities = [
                item for item in effective_capabilities if item.id != conflict_id
            ]
            removed.append(self._removed(conflict_id, ErrorCode.WRITE_RESULT_CONFLICT))

        return effective_bindings, effective_capabilities, removed

    def resolve_event_candidates(
        self,
        candidates: list[EventAction],
        rom_version: str,
        app_version: str,
        xiaoyi_version: str,
    ) -> tuple[list[EventAction], list[RemovedCapability]]:
        """过滤候选事件动作。

        入参：
        - candidates：候选事件动作列表。
        - rom_version：当前设备 ROM 版本。
        - app_version：当前宿主 App 版本。
        - xiaoyi_version：当前小艺版本。
        出参：有效事件动作列表、被移除事件能力列表。
        """
        ids_state = self._load_ids_state()
        removed: list[RemovedCapability] = []
        effective: list[EventAction] = []

        for candidate in candidates:
            capability_id = candidate.id
            if capability_id:
                event_capability = self.registry.get_event_capability(capability_id)
                if event_capability is None:
                    removed.append(
                        self._removed(capability_id, ErrorCode.UNKNOWN_CAPABILITY, "event")
                    )
                    continue
                reason = self._check_common_dependencies(
                    event_capability, rom_version, app_version, xiaoyi_version, ids_state
                )
                if reason is not None:
                    removed.append(self._removed(capability_id, reason, "event"))
                    continue
            effective.append(candidate)
        return effective, removed

    def _load_ids_state(self) -> dict[str, Any]:
        """读取并转换 IDS mock 响应。

        入参：无。
        出参：包含已安装应用、provider、intent 和权限状态的内部结构。
        """
        # docs/ids_res.txt 是模拟 IDS 响应；后续接真实 IDS 时可替换这里并保持返回结构稳定。
        path = self.settings.resolved_mock_ids_response_path
        if not path.exists():
            return {
                "installed_apps": {},
                "providers": set(),
                "intent_targets": set(),
                "permissions": {},
            }

        payload = load_json(path)
        installed_apps: dict[str, str] = {}
        providers: set[str] = set()
        intent_targets: set[str] = set()
        permissions: dict[str, str] = {}

        for namespace in payload.get("nameSpaces", []):
            data_type = namespace.get("dataType", "")
            values = namespace.get("values", [])
            if data_type == "t_ids_kv_ohos_installed_apps":
                for value in values:
                    data = value.get("data", {})
                    bundle_name = data.get("bundleName")
                    version_name = data.get("versionName", "0.0.0")
                    if bundle_name:
                        installed_apps[bundle_name] = version_name
            elif "provider" in data_type.lower():
                providers.update(self._collect_ids(values, "provider"))
            elif "intent" in data_type.lower():
                intent_targets.update(self._collect_ids(values, "intent"))
            elif "permission" in data_type.lower():
                for value in values:
                    data = value.get("data", {})
                    permission = data.get("permission") or data.get("name")
                    status = data.get("status")
                    if permission and status:
                        permissions[permission] = status

        default_providers = {
            # 模拟阶段默认认为一方应用和系统能力提供方可用。
            "UG.weather.current",
            "UG.weather.forecast",
            "UG.calendar.events.search",
            "UG.system.battery.status",
            "UG.health.sleep.summary",
        }
        default_intents = {
            "OpenWeather",
            "ViewCalendarEvent",
            "StartNavigate",
            "SetSettingSwitch",
            "OpenPowerSaving",
            "OpenHealth",
        }
        return {
            "installed_apps": installed_apps,
            "providers": providers | default_providers,
            "intent_targets": intent_targets | default_intents,
            "permissions": permissions,
        }

    def _collect_ids(self, values: list[dict[str, Any]], key_hint: str) -> set[str]:
        """从 IDS values 中按字段名特征收集 ID。

        入参：
        - values：IDS 命名空间下的 values 列表。
        - key_hint：字段名关键词，例如 provider 或 intent。
        出参：收集到的 ID 集合。
        """
        result: set[str] = set()
        for value in values:
            data = value.get("data", {})
            for key, item in data.items():
                if key_hint.lower() in key.lower() and isinstance(item, str):
                    result.add(item)
        return result

    def _check_common_dependencies(
        self,
        capability: Any,
        rom_version: str,
        app_version: str,
        xiaoyi_version: str,
        ids_state: dict[str, Any],
    ) -> ErrorCode | None:
        """检查能力通用依赖。

        入参：
        - capability：数据能力或事件能力定义。
        - rom_version：当前设备 ROM 版本。
        - app_version：当前宿主 App 版本。
        - xiaoyi_version：当前小艺版本。
        - ids_state：转换后的 IDS 状态。
        出参：不可用原因错误码；全部满足时返回 None。
        """
        dependencies = capability.dependencies
        if dependencies.minRomVersion and not self._version_gte(
            rom_version, dependencies.minRomVersion
        ):
            return ErrorCode.ROM_VERSION_UNSUPPORTED
        if dependencies.minAppVersion and not self._version_gte(
            app_version, dependencies.minAppVersion
        ):
            return ErrorCode.APP_VERSION_UNSUPPORTED
        if dependencies.minXiaoyiVersion and not self._version_gte(
            xiaoyi_version, dependencies.minXiaoyiVersion
        ):
            return ErrorCode.APP_VERSION_UNSUPPORTED

        installed_apps = ids_state["installed_apps"]
        for package in dependencies.requiredPackages:
            installed_version = installed_apps.get(package.packageName)
            if installed_version is None:
                return ErrorCode.PACKAGE_NOT_INSTALLED
            if package.minVersion and not self._version_gte(installed_version, package.minVersion):
                return ErrorCode.PACKAGE_VERSION_TOO_LOW

        providers = ids_state["providers"]
        for provider in dependencies.requiredProviders:
            if provider not in providers:
                return ErrorCode.PROVIDER_NOT_FOUND

        intent_targets = ids_state["intent_targets"]
        for target in dependencies.requiredIntentTargets:
            if target not in intent_targets:
                return ErrorCode.INTENT_TARGET_NOT_FOUND

        permissions = ids_state["permissions"]
        for permission in dependencies.requiredPermissions:
            status = permissions.get(permission, "GRANTED")
            if status == "DENIED":
                return ErrorCode.PERMISSION_DENIED
            if status == "UNKNOWN":
                return ErrorCode.PERMISSION_UNKNOWN

        return None

    def _valid_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> bool:
        """校验能力参数是否符合 inputSchema。

        入参：
        - arguments：候选数据绑定参数。
        - schema：能力注册表里的 JSON Schema。
        出参：参数合法返回 True，否则返回 False。
        """
        if not schema:
            return True
        validator = Draft202012Validator(schema)
        return not list(validator.iter_errors(arguments))

    def _find_write_result_conflict(self, bindings: list[CandidateDataBinding]) -> str | None:
        """检查 writeResultTo 是否冲突。

        入参：
        - bindings：已通过基础过滤的数据绑定列表。
        出参：发生冲突的能力 ID；无冲突时返回 None。
        """
        # 相同路径或父子路径会在 DataModel 中互相覆盖。
        paths = [(item.capabilityId, item.writeResultTo or "") for item in bindings]
        for index, (capability_id, path) in enumerate(paths):
            normalized = path.rstrip("/")
            for other_id, other_path in paths[index + 1 :]:
                other_normalized = other_path.rstrip("/")
                if (
                    normalized == other_normalized
                    or normalized.startswith(other_normalized + "/")
                    or other_normalized.startswith(normalized + "/")
                ):
                    return other_id or capability_id
        return None

    def _version_gte(self, current: str, minimum: str) -> bool:
        """比较版本号是否满足最低要求。

        入参：
        - current：当前版本。
        - minimum：最低版本。
        出参：当前版本大于等于最低版本时返回 True。
        """
        current = self._extract_version(current)
        minimum = self._extract_version(minimum)
        try:
            return Version(current) >= Version(minimum)
        except InvalidVersion:
            return current >= minimum

    def _extract_version(self, value: str) -> str:
        """从复杂版本字符串中提取数字版本。

        入参：
        - value：原始版本字符串。
        出参：数字版本字符串；无法提取时返回 `0`。
        """
        match = re.search(r"\d+(?:\.\d+)*", value or "")
        return match.group(0) if match else "0"

    def _removed(
        self,
        capability_id: str,
        reason: ErrorCode,
        capability_type: str = "data",
    ) -> RemovedCapability:
        """构造被移除能力对象。

        入参：
        - capability_id：能力 ID。
        - reason：移除原因错误码。
        - capability_type：能力类型，默认 data。
        出参：包含内部原因和用户可读原因的 RemovedCapability。
        """
        readable = {
            ErrorCode.UNKNOWN_CAPABILITY: "能力未注册",
            ErrorCode.ROM_VERSION_UNSUPPORTED: "系统版本不支持",
            ErrorCode.APP_VERSION_UNSUPPORTED: "应用版本不支持",
            ErrorCode.PACKAGE_NOT_INSTALLED: "依赖应用未安装",
            ErrorCode.PACKAGE_VERSION_TOO_LOW: "依赖应用版本过低",
            ErrorCode.PROVIDER_NOT_FOUND: "当前设备未提供对应数据源",
            ErrorCode.INTENT_TARGET_NOT_FOUND: "当前设备未提供对应入口",
            ErrorCode.PERMISSION_DENIED: "权限未开启",
            ErrorCode.PERMISSION_UNKNOWN: "权限状态未知",
            ErrorCode.INVALID_ARGUMENTS: "参数不合法",
            ErrorCode.WRITE_RESULT_CONFLICT: "数据写入路径冲突",
        }.get(reason, "能力不可用")
        return RemovedCapability(
            id=capability_id,
            type=capability_type,
            reason=reason.value,
            userReadableReason=readable,
        )
