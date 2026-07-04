from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import get_settings
from services.json_loader import load_json


@dataclass(frozen=True)
class IDSDeviceCapabilityState:
    """微服务内部使用的 IDS 能力状态快照。

    入参：
    - installed_apps：设备已安装应用，key 为包名，value 为版本号。
    - providers：设备当前可用的数据 provider ID 集合。
    - intent_targets：设备当前可用的意图入口 ID 集合。
    - permissions：设备权限状态，key 为权限名，value 为 GRANTED、DENIED 或 UNKNOWN。
    出参：不可变数据对象，供能力过滤流程读取。
    """

    installed_apps: dict[str, str] = field(default_factory=dict)
    providers: set[str] = field(default_factory=set)
    intent_targets: set[str] = field(default_factory=set)
    permissions: dict[str, str] = field(default_factory=dict)


class IDSClient:
    """IDS 查询客户端。

    当前阶段读取 mock IDS 响应文件；后续接入真实 IDS 时，只需要替换本类里的查询实现，
    `DeviceCapabilityResolver` 继续消费稳定的 `IDSDeviceCapabilityState` 即可。
    """

    def __init__(self, mock_response_path: Path | None = None) -> None:
        """初始化 IDS 客户端。

        入参：
        - mock_response_path：可选 mock IDS 响应路径；不传时读取全局配置。
        出参：无。
        """
        self.settings = get_settings()
        # 测试和本地调试可显式传入文件路径；线上接真实 IDS 后可以去掉这个分支。
        self.mock_response_path = (
            mock_response_path or self.settings.resolved_mock_ids_response_path
        )

    def get_device_capability_state(self) -> IDSDeviceCapabilityState:
        """获取设备能力状态。

        入参：无。
        出参：标准化后的 IDSDeviceCapabilityState，供数据能力和事件能力过滤使用。
        """
        # 当前 mock 文件不存在时返回空状态，避免本地环境缺文件直接中断服务启动。
        if not self.mock_response_path.exists():
            return IDSDeviceCapabilityState()

        # mock 文件沿用 docs/ids_res.txt 的原始 IDS JSON 结构。
        payload = load_json(self.mock_response_path)
        return self._parse_ids_payload(payload)

    def _parse_ids_payload(self, payload: dict[str, Any]) -> IDSDeviceCapabilityState:
        """解析 IDS 原始响应。

        入参：
        - payload：IDS 原始 JSON 响应。
        出参：转换后的设备能力状态。
        """
        installed_apps: dict[str, str] = {}
        providers: set[str] = set()
        intent_targets: set[str] = set()
        permissions: dict[str, str] = {}

        for namespace in payload.get("nameSpaces", []):
            # dataType 决定当前 namespace 存的是安装应用、provider、intent 还是权限。
            data_type = namespace.get("dataType", "")
            values = namespace.get("values", [])

            if data_type == "t_ids_kv_ohos_installed_apps":
                # 安装应用列表需要转成 packageName -> versionName，供依赖版本检查使用。
                installed_apps.update(self._collect_installed_apps(values))
            elif "provider" in data_type.lower():
                # provider ID 是数据能力可用性的关键依据。
                providers.update(self._collect_ids(values, "provider"))
            elif "intent" in data_type.lower():
                # intent target 是点击事件能力可用性的关键依据。
                intent_targets.update(self._collect_ids(values, "intent"))
            elif "permission" in data_type.lower():
                # 权限状态影响后续是否允许生成需要授权的数据能力。
                permissions.update(self._collect_permissions(values))

        return IDSDeviceCapabilityState(
            installed_apps=installed_apps,
            providers=providers | self._default_providers(),
            intent_targets=intent_targets | self._default_intents(),
            permissions=permissions,
        )

    def _collect_installed_apps(self, values: list[dict[str, Any]]) -> dict[str, str]:
        """从 IDS values 中收集已安装应用。

        入参：
        - values：安装应用 namespace 下的 values 列表。
        出参：包名到版本号的映射。
        """
        installed_apps: dict[str, str] = {}
        for value in values:
            data = value.get("data", {})
            bundle_name = data.get("bundleName")
            version_name = data.get("versionName", "0.0.0")
            if bundle_name:
                installed_apps[bundle_name] = version_name
        return installed_apps

    def _collect_permissions(self, values: list[dict[str, Any]]) -> dict[str, str]:
        """从 IDS values 中收集权限状态。

        入参：
        - values：权限 namespace 下的 values 列表。
        出参：权限名到权限状态的映射。
        """
        permissions: dict[str, str] = {}
        for value in values:
            data = value.get("data", {})
            permission = data.get("permission") or data.get("name")
            status = data.get("status")
            if permission and status:
                permissions[permission] = status
        return permissions

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
                # IDS 字段命名可能有 providerId、providerName、intentName 等差异，所以按关键词匹配。
                if key_hint.lower() in key.lower() and isinstance(item, str):
                    result.add(item)
        return result

    def _default_providers(self) -> set[str]:
        """获取 mock 阶段默认可用的一方 provider。

        入参：无。
        出参：默认 provider ID 集合。
        """
        # mock 数据不一定覆盖所有一方系统 provider，先补充一期链路需要的稳定 provider。
        return {
            "UG.weather.current",
            "UG.weather.forecast",
            "UG.calendar.events.search",
            "UG.system.battery.status",
            "UG.health.sleep.summary",
        }

    def _default_intents(self) -> set[str]:
        """获取 mock 阶段默认可用的一方 intent target。

        入参：无。
        出参：默认 intent target 集合。
        """
        # mock 数据不一定覆盖所有一方系统入口，先补充一期链路需要的稳定入口。
        return {
            "OpenWeather",
            "ViewCalendarEvent",
            "StartNavigate",
            "SetSettingSwitch",
            "OpenPowerSaving",
            "OpenHealth",
        }
