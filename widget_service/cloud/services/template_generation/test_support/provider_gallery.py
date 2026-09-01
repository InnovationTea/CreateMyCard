"""Provider 模板画廊输入构建与端到端批量生成，仅供开发测试使用。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

from api.schemas import (
    GenerateWidgetCardRequest,
    GenerateWidgetCardResponse,
    ToolRequestEnvelope,
)
from core.errors import ErrorCode, GenerationStatus
from custom.model_runtime import ModelExecutionRuntime
from models.artifact import WidgetArtifact
from models.generation import ModelRequestContext
from models.service import ArtifactSaveResult
from services.artifact_store import ArtifactStore
from services.template_generation.controls import load_template_controls
from services.widget_generation_service import WidgetGenerationService

INPUT_SCHEMA_VERSION = "provider-template-gallery-input/4"
OUTPUT_SCHEMA_VERSION = "provider-template-gallery-output/2"
DEFAULT_PRD_VERSION = "11.7.5.205"
FUSION_PRD_VERSION = "11.7.5.206"
DEFAULT_ROM_VERSION = "6.0"
DEFAULT_BUNDLE_NAME = "com.huawei.genui.evaluation"

_TEMPLATE_GENERATION_ROOT = Path(__file__).resolve().parents[1]
_PROVIDER_ROOT = _TEMPLATE_GENERATION_ROOT / "resources" / "source" / "providers"
_THEME_ROOT = _TEMPLATE_GENERATION_ROOT / "resources" / "source" / "themes"
_CAPABILITY_ROOT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "capabilities"
    / "app-11.7.5.205_rom-6.0"
)
_CURRENT_CASE_ID: ContextVar[str] = ContextVar("provider_gallery_case_id", default="")


def _clear_generated_gallery_files(root: Path) -> None:
    """移除上一次画廊运行留下的受管文件，避免失效场景继续被端侧打包。"""
    providers_root = root / "providers"
    if providers_root.is_symlink() or providers_root.is_file():
        providers_root.unlink()
    elif providers_root.is_dir():
        shutil.rmtree(providers_root)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or manifest_path.is_file():
        manifest_path.unlink()

_PROVIDER_NAMES = {
    "app-usage": "应用时长",
    "battery": "设备电量",
    "calendar": "日历日程",
    "countdown": "倒计时",
    "earphone": "蓝牙耳机",
    "health-sport": "运动健康",
    "system-memory": "系统内存",
    "weather": "天气",
}

_BUSINESS_DESCRIPTIONS = {
    "ActivityOverview": ("每日活动", "展示今天的步数、热量和距离"),
    "AppUsageOverview": ("应用时长", "展示示例应用今天的使用时长"),
    "BatteryOverview": ("设备电量", "展示手机剩余电量和充电状态"),
    "BluetoothDeviceOverview": ("蓝牙耳机", "展示耳机连接状态和左右耳电量"),
    "CalendarOverview": ("日历日程", "展示下一项日程"),
    "CountdownOverview": ("倒计时", "展示距离元旦还有多少天"),
    "HeartRateOverview": ("运动心率", "展示最近一次运动的平均心率"),
    "ResourceUsageOverview": ("系统内存", "展示内存占用率和可用内存"),
    "SleepOverview": ("睡眠情况", "展示昨晚睡眠情况的时长、得分和状态"),
    "WeatherOverview": ("天气", "展示上海青浦当前温度、天气和空气质量"),
    "WorkoutOverview": ("运动记录", "展示最近一次运动的类型、时长和热量"),
}

_CAPABILITY_ARGUMENTS = {
    "GetAppUsageDuration": {"appBundleName": "com.example.demo"},
    "GetCalendarEvents": {"futureDays": 7},
    "GetCountdownDays": {"targetDate": "2027-01-01"},
    "GetEarphoneInfo": {},
    "GetHealthAndSportSummary": {"targetDayOffset": 0},
    "GetPhoneBatteryInfo": {},
    "GetSystemMemInfo": {},
    "ViewWeather": {
        "districtName": "青浦区",
        "forecastDays": 1,
        "prefectureName": "上海市",
    },
}

_ACTION_IDS_BY_BUSINESS = {
    "ActivityOverview": ("event.open.health.sport", "event.open.settings.dnd"),
    "AppUsageOverview": (
        "event.open.settings.parentControl",
        "event.open.settings.dnd",
    ),
    "BatteryOverview": (
        "event.open.settings.battery",
        "event.setPowerSavingMode",
    ),
    "BluetoothDeviceOverview": (
        "event.open.settings.bluetooth",
        "event.open.music.daily",
    ),
    "CalendarOverview": ("event.viewCalendarEvent", "event.enter.meeting"),
    "CountdownOverview": ("event.open.clock.alarm", "event.open.settings.dnd"),
    "HeartRateOverview": ("event.open.health.sport", "event.open.settings.dnd"),
    "ResourceUsageOverview": (
        "event.clean.memory",
        "event.open.settings.storage",
    ),
    "SleepOverview": ("event.open.health.sleep", "event.open.settings.dnd"),
    "WeatherOverview": ("event.open.weather", "event.startNavigate"),
    "WorkoutOverview": ("event.open.health.sport", "event.open.settings.dnd"),
}

_ACTION_QUERIES_BY_BUSINESS = {
    "ActivityOverview": ("查看运动健康详情", "打开免打扰设置"),
    "AppUsageOverview": ("打开家长控制设置", "打开免打扰设置"),
    "BatteryOverview": ("打开电池设置", "开启省电模式"),
    "BluetoothDeviceOverview": ("打开蓝牙设置", "打开每日音乐"),
    "CalendarOverview": ("查看日程详情", "进入会议"),
    "CountdownOverview": ("打开闹钟", "打开免打扰设置"),
    "HeartRateOverview": ("查看运动健康详情", "打开免打扰设置"),
    "ResourceUsageOverview": ("一键清理内存", "打开存储设置"),
    "SleepOverview": ("查看睡眠详情", "打开免打扰设置"),
    "WeatherOverview": ("打开当前城市天气详情", "导航回家"),
    "WorkoutOverview": ("查看运动健康详情", "打开免打扰设置"),
}

_ASSET_IDS_BY_TEMPLATE_PREFIX = {
    "BatteryOverview": ("asset.battery_leaf_fill",),
    "BluetoothDeviceOverviewCaseStatus": ("asset.earphone_case_16644",),
    "HeartRateOverviewIcon": ("asset.heart_fill",),
    "HeartRateOverviewUpdatedIcon": ("asset.heart_fill",),
    "ScheduleOverviewNextEventHero": ("asset.calendar_fill",),
    "ScheduleOverviewDatedMeetingHero": (
        "asset.calendar_fill",
        "asset.icon_meeting",
    ),
    "ScheduleOverviewNextEventLocationFull": (
        "asset.calendar_fill",
    ),
    "ScheduleOverviewMeetingSourceWideFull": (
        "asset.calendar_fill",
        "asset.clock",
        "asset.location_north_up_right_fill",
        "asset.icon_meeting",
    ),
    "ScheduleOverviewMeetingWideFull": (
        "asset.calendar_fill",
        "asset.clock",
        "asset.location_north_up_right_fill",
        "asset.icon_meeting",
    ),
    "BluetoothDeviceOverviewCaseStatusCompact": (
        "asset.earphone_case_16644",
    ),
    "BluetoothDeviceOverviewEarbudsSupport": (
        "asset.icon_earphone",
    ),
    "BluetoothDeviceOverviewEarbudPair": (
        "asset.earphone_case_16644",
        "asset.l_circle_fill",
        "asset.r_circle_fill",
    ),
}

_ASSET_SEARCH_TERMS_BY_TEMPLATE_PREFIX = {
    "WeatherOverview": ("weather", "天气"),
}

_CALENDAR_NEXT_EVENT_RUNTIME_FIELDS = ("/events/0/dtStart",)
_WORKOUT_RUNTIME_FIELDS = ("/exerciseEndTimeText",)
_BATTERY_FACT_FIELDS = frozenset(("/batterySOC", "/batterySOCText"))
_BATTERY_FACT_FALLBACK_EXEMPT_TEMPLATE_IDS = frozenset(
    {"BatteryOverviewHealthLevelHero@1"}
)


class GalleryInputCase(BaseModel):
    """输入清单中的一个业务场景。"""

    model_config = ConfigDict(extra="forbid")

    caseId: str
    providerId: str
    providerName: str
    providerSlug: str
    businessId: str
    businessName: str
    scenarioId: str
    scenarioName: str
    appearanceId: str
    appearanceName: str
    prdVer: str
    expectsFusionBall: bool
    expectedLayout: str
    expectedTemplateSuffix: str
    targetTemplateId: str = ""
    targetTemplateDescription: str = ""
    requestFile: str
    missingReason: str = ""


class GalleryInputProvider(BaseModel):
    """按 Provider 领域分组的输入用例。"""

    model_config = ConfigDict(extra="forbid")

    providerId: str
    providerName: str
    providerSlug: str
    cases: list[GalleryInputCase] = Field(default_factory=list)


class GalleryInputManifest(BaseModel):
    """可由 AI Agent 直接读取和批跑的输入清单。"""

    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = INPUT_SCHEMA_VERSION
    operation: str = "generate_widget_card_terse_dsl_nested2"
    cardSize: str = "2x2"
    providers: list[GalleryInputProvider] = Field(default_factory=list)


@dataclass(frozen=True)
class ProviderTemplateDefinition:
    """Provider 中一个可单独检查的业务模板。"""

    template_id: str
    description: str
    suffix: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class BusinessDefinition:
    """从 Provider 配置派生的业务及其全部模板。"""

    provider_id: str
    provider_name: str
    provider_slug: str
    business_id: str
    business_name: str
    capability_id: str
    data_domain: str
    templates: tuple[ProviderTemplateDefinition, ...]

    @property
    def fallback_fields(self) -> tuple[str, ...]:
        values = [field for template in self.templates for field in template.fields]
        return _ordered_unique(values)


@dataclass(frozen=True)
class GalleryRunSummary:
    """一次批跑的结果摘要。"""

    manifest_path: Path
    total: int
    success: int
    failed: int
    missing: int
    not_generated: int


@dataclass(frozen=True)
class GalleryAppearance:
    """由 TaskSpec 端侧版本裁决的一种画廊外观。"""

    appearance_id: str
    appearance_name: str
    prd_ver: str
    fusion_enabled: bool


_GALLERY_APPEARANCES = (
    GalleryAppearance(
        appearance_id="standard",
        appearance_name="非融球",
        prd_ver=DEFAULT_PRD_VERSION,
        fusion_enabled=False,
    ),
    GalleryAppearance(
        appearance_id="fusion",
        appearance_name="融球",
        prd_ver=FUSION_PRD_VERSION,
        fusion_enabled=True,
    ),
)


class GalleryGenerationService(Protocol):
    """批跑依赖的正式生成入口协议。"""

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: GenerateWidgetCardRequest,
        *,
        trusted_template_candidate_ids: tuple[str, ...] = (),
        trusted_template_action_ids: tuple[str, ...] = (),
        trusted_template_sample_overrides: dict[str, object] | None = None,
    ) -> GenerateWidgetCardResponse:
        ...


class _ArtifactCapture:
    """替代远端 Artifact 保存，仅捕获真实生成链路的最终产物。"""

    def __init__(self) -> None:
        self.artifacts: dict[str, WidgetArtifact] = {}
        self.design_sources: dict[str, str] = {}

    async def save(
        self,
        store: ArtifactStore,
        artifact: WidgetArtifact,
    ) -> ArtifactSaveResult:
        case_id = _CURRENT_CASE_ID.get()
        if not case_id:
            raise RuntimeError("Provider gallery artifact has no active case ID")
        self.artifacts[case_id] = artifact
        if store.design_token is not None:
            self.design_sources[case_id] = store.design_token
        payload = artifact.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
        return ArtifactSaveResult(
            artifactUrl=f"gallery-capture://{case_id}",
            artifactDigest=digest,
        )


def _kebab_case(value: str) -> str:
    with_boundaries = re.sub(r"(?<!^)(?=[A-Z])", "-", value)
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", with_boundaries)
    return normalized.strip("-").lower()


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _template_suffix(template_id: str) -> str:
    local_id = template_id.split("@", maxsplit=1)[0]
    for suffix in (
        "WideHero",
        "WideFull",
        "Support",
        "Compact",
        "Hero",
        "Full",
        "Compat",
    ):
        if local_id.endswith(suffix):
            return suffix
    return ""


def _load_business_definitions(provider_root: Path) -> list[BusinessDefinition]:
    definitions: list[BusinessDefinition] = []
    for manifest_path in sorted(provider_root.glob("*/provider.json")):
        provider_slug = manifest_path.parent.name
        provider_name = _PROVIDER_NAMES.get(provider_slug)
        if provider_name is None:
            continue
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        provider_id = str(payload["providerId"])
        data_domains = {
            str(item["capabilityId"]): str(item["dataDomain"])
            for item in payload.get("capabilities", [])
        }
        grouped: dict[str, list[dict[str, Any]]] = {}
        for template in payload.get("templates", []):
            business_id = template.get("businessId")
            if isinstance(business_id, str) and business_id:
                grouped.setdefault(business_id, []).append(template)
        for business_id, templates in sorted(grouped.items()):
            business_meta = _BUSINESS_DESCRIPTIONS.get(business_id)
            if business_meta is None:
                continue
            capability_id = str(templates[0]["capabilityId"])
            definitions.append(
                BusinessDefinition(
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_slug=provider_slug,
                    business_id=business_id,
                    business_name=business_meta[0],
                    capability_id=capability_id,
                    data_domain=data_domains[capability_id],
                    templates=tuple(_template_definition(item) for item in templates),
                )
            )
    return definitions


def _template_definition(template: dict[str, Any]) -> ProviderTemplateDefinition:
    template_id = str(template["templateId"])
    fields = [
        *template.get("primaryData", []),
        *template.get("secondaryData", []),
        *template.get("optionalData", []),
    ]
    return ProviderTemplateDefinition(
        template_id=template_id,
        description=str(template.get("description") or "").strip(),
        suffix=_template_suffix(template_id),
        fields=_ordered_unique([str(item) for item in fields]),
    )


def _templates_for_suffix(
    definition: BusinessDefinition,
    suffix: str,
) -> tuple[ProviderTemplateDefinition, ...]:
    return tuple(template for template in definition.templates if template.suffix == suffix)


def _load_event_capabilities(capability_root: Path) -> dict[str, dict[str, Any]]:
    path = capability_root / "event_capabilities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in payload}


def _load_data_capability_ids(capability_root: Path) -> set[str]:
    path = capability_root / "data_capabilities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item["id"])
        for item in payload
        if isinstance(item, dict) and item.get("enabled", True) is not False
    }


def _load_asset_capabilities(
    capability_root: Path,
) -> dict[str, dict[str, Any]]:
    path = capability_root / "asset_capabilities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item["id"]): item
        for item in payload
        if isinstance(item, dict) and item.get("enabled", True) is not False
    }


def _load_fusion_business_ids(theme_root: Path) -> set[str]:
    business_ids: set[str] = set()
    for path in sorted(theme_root.glob("*/theme.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        fusion_style = payload.get("fusionBallStyle")
        if not isinstance(fusion_style, dict):
            continue
        values = fusion_style.get("businessIds")
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value:
                business_ids.add(value)
    return business_ids


def _normalize_action_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_action_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_action_value(item) for item in value]
    if isinstance(value, str):
        normalized = value.replace("events/i/", "events/0/")
        normalized = normalized.replace("events/i}", "events/0}")
        if normalized == "":
            return normalized
        return normalized
    return value


def _event_candidate(
    event_capabilities: dict[str, dict[str, Any]],
    capability_id: str,
) -> dict[str, Any]:
    capability = event_capabilities[capability_id]
    action = _normalize_action_value(deepcopy(capability["actionTemplate"]))
    if capability_id == "event.startNavigate":
        action["args"]["params"]["dstLocation"]["location"] = "home"
    return {"capabilityId": capability_id, "action": action}


def _data_binding(
    definition: BusinessDefinition,
    template: ProviderTemplateDefinition | None,
) -> dict[str, Any]:
    configured_fields = template.fields if template is not None else definition.fallback_fields
    fields = configured_fields
    template_id = template.template_id if template is not None else ""
    needs_battery_fact_fallback = (
        definition.business_id == "BatteryOverview"
        and template_id not in _BATTERY_FACT_FALLBACK_EXEMPT_TEMPLATE_IDS
    )
    if needs_battery_fact_fallback:
        fields = _ordered_unique(
            [*configured_fields, "/batterySOC", "/batterySOCText"]
        )
    if template is not None and template.template_id.startswith("ScheduleOverviewNextEvent"):
        fields = _ordered_unique([*configured_fields, *_CALENDAR_NEXT_EVENT_RUNTIME_FIELDS])
    if definition.business_id == "WorkoutOverview":
        fields = _ordered_unique([*fields, *_WORKOUT_RUNTIME_FIELDS])
    if definition.business_id == "BluetoothDeviceOverview":
        fields = _ordered_unique([*fields, "/isConnected", "/earphoneName"])
    return {
        "arguments": deepcopy(_CAPABILITY_ARGUMENTS[definition.capability_id]),
        "candidateOutputFields": list(fields),
        "capabilityId": definition.capability_id,
        "writeResultTo": definition.data_domain,
    }


def _candidate_asset_ids(
    target_template: ProviderTemplateDefinition | None,
    asset_capabilities: dict[str, dict[str, Any]],
) -> list[str]:
    template_ids = [
        template.template_id
        for template in (target_template,)
        if template is not None
    ]
    candidate_asset_ids: list[str] = []
    for template_id in template_ids:
        for prefix, asset_ids in _ASSET_IDS_BY_TEMPLATE_PREFIX.items():
            if not template_id.startswith(prefix):
                continue
            for asset_id in asset_ids:
                if asset_id in asset_capabilities:
                    candidate_asset_ids.append(asset_id)
        for prefix, terms in _ASSET_SEARCH_TERMS_BY_TEMPLATE_PREFIX.items():
            if template_id.startswith(prefix):
                candidate_asset_ids.extend(
                    _asset_ids_matching_terms(asset_capabilities, terms)
                )
    return list(dict.fromkeys(candidate_asset_ids))


def _asset_ids_matching_terms(
    asset_capabilities: dict[str, dict[str, Any]],
    terms: tuple[str, ...],
) -> list[str]:
    if not terms:
        return []
    normalized_terms = tuple(term.casefold() for term in terms)
    matches: list[str] = []
    for asset_id, capability in asset_capabilities.items():
        search_values = (
            asset_id,
            capability.get("src", ""),
            capability.get("description", ""),
            *capability.get("sceneTags", []),
        )
        searchable = " ".join(str(value) for value in search_values).casefold()
        if any(term in searchable for term in normalized_terms):
            matches.append(asset_id)
    return matches


def _gallery_sample_overrides(
    target_template: ProviderTemplateDefinition | None,
) -> dict[str, Any]:
    templates = tuple(
        template
        for template in (target_template,)
        if template is not None
    )
    sample_overrides: dict[str, Any] = {}
    earphone_template = next(
        (
            template
            for template in templates
            if template.template_id.startswith("BluetoothDeviceOverview")
        ),
        None,
    )
    if earphone_template is not None:
        sample_overrides["/data/earphone/isConnected"] = (
            "Disconnected" not in earphone_template.template_id
        )
    weather_template = next(
        (
            template
            for template in templates
            if template.template_id.startswith("WeatherOverview")
        ),
        None,
    )
    weather_displays_temperature = (
        weather_template is not None
        and "/current/temperatureText" in weather_template.fields
    )
    if weather_displays_temperature:
        sample_overrides["/data/weather/current/temperatureText"] = "29°"
    battery_template = next(
        (
            template
            for template in templates
            if template.template_id.startswith("BatteryOverview")
        ),
        None,
    )
    if battery_template is None:
        return sample_overrides
    template_id = battery_template.template_id
    battery_overrides: dict[str, Any] = {}
    if "BatteryOverviewCharging" in template_id:
        battery_overrides = {
            "/data/phoneBattery/batterySOC": 68,
            "/data/phoneBattery/batterySOCText": "68%",
            "/data/phoneBattery/chargingStatusDesc": "正在充电",
            "/data/phoneBattery/batteryCapacityLevelDesc": "正常电量",
        }
    available_fields = set(battery_template.fields)
    if not _BATTERY_FACT_FIELDS.intersection(available_fields):
        available_fields.add("/batterySOCText")
    sample_overrides.update(
        {
            path: value
            for path, value in battery_overrides.items()
            if path.removeprefix("/data/phoneBattery") in available_fields
        }
    )
    return sample_overrides


def _request_envelope(
    definition: BusinessDefinition,
    target_template: ProviderTemplateDefinition | None,
    scenario_id: str,
    appearance: GalleryAppearance,
    event_capabilities: dict[str, dict[str, Any]],
    asset_capabilities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    business_description = _BUSINESS_DESCRIPTIONS[definition.business_id][1]
    template_description = (
        target_template.description if target_template is not None else business_description
    )
    data_bindings = [_data_binding(definition, target_template)]
    action_count = 0
    if scenario_id == "single-two-actions":
        action_count = 2
        action_queries = _ACTION_QUERIES_BY_BUSINESS[definition.business_id]
        user_query = (
            f"生成一个2×2卡片，只用一块紧凑内容按“{template_description}”展示，"
            f"并提供两个独立按钮，分别用于“{action_queries[0]}”和“{action_queries[1]}”。"
        )
    elif scenario_id == "single-one-action":
        action_count = 1
        action_query = _ACTION_QUERIES_BY_BUSINESS[definition.business_id][0]
        user_query = (
            f"生成一个2×2卡片，主视觉内容按“{template_description}”展示，"
            f"底部提供一个用于“{action_query}”的按钮。"
        )
    else:
        user_query = (
            f"生成一个2×2完整信息卡片，按“{template_description}”展示，"
            "不显示操作按钮。"
        )
    action_ids = _ACTION_IDS_BY_BUSINESS[definition.business_id][:action_count]
    event_candidates = [
        _event_candidate(event_capabilities, action_id) for action_id in action_ids
    ]
    content = {
        "bundleName": DEFAULT_BUNDLE_NAME,
        "candidateAssetIds": _candidate_asset_ids(
            target_template,
            asset_capabilities,
        ),
        "candidateDataBindings": data_bindings,
        "candidateEventCandidates": event_candidates,
        "description": f"{definition.business_name}模板画廊端到端验证",
        "size": "2x2",
        "title": f"{definition.business_name}模板画廊",
        "userQuery": user_query,
    }
    target_name = (
        target_template.template_id.split("@", maxsplit=1)[0]
        if target_template is not None
        else f"Missing{_scenario_metadata(scenario_id)[2]}"
    )
    target_slug = _kebab_case(target_name)
    case_suffix = scenario_id.replace("-", "_")
    return {
        "bundleName": DEFAULT_BUNDLE_NAME,
        "content": content,
        "deviceInfo": {
            "countryCode": "CN",
            "deviceFormation": "Tablet",
            "deviceType": 0,
            "locale": "zh-CN",
            "phoneType": "GENUI-GALLERY",
            "prdVer": appearance.prd_ver,
            "romVersion": DEFAULT_ROM_VERSION,
            "sysVer": "HarmonyOS NEXT",
            "time": "20260826000000000",
        },
        "pagination": {"limit": 5, "start": ""},
        "galleryTest": {
            "sampleOverrides": _gallery_sample_overrides(
                target_template,
            )
        },
        "session": {
            "interactionId": "1",
            "isNew": True,
            "sessionId": (
                f"gallery-{definition.provider_slug}-"
                f"{_kebab_case(definition.business_id)}-{target_slug}-{case_suffix}-"
                f"{appearance.appearance_id}"
            ),
        },
        "userAuth": {"user": {"userId": "template-gallery"}},
        "utterance": {"original": user_query, "type": "text"},
        "version": "1.0",
    }


def _scenario_metadata(scenario_id: str) -> tuple[str, str, str]:
    metadata = {
        "single-two-actions": (
            "单内容 + 2 个 Action",
            "Compact + 2 × PillAction",
            "Compact",
        ),
        "single-one-action": (
            "单内容 + 1 个 Action",
            "Hero + PillAction",
            "Hero",
        ),
        "single-content": ("单内容", "Full", "Full"),
    }
    scenario_metadata = metadata.get(scenario_id)
    if scenario_metadata is None:
        raise ValueError(f"unknown gallery scenario: {scenario_id}")
    return scenario_metadata


def _missing_reason(
    target_template: ProviderTemplateDefinition | None,
    scenario_id: str,
    *,
    capability_available: bool,
    provider_disabled: bool,
    template_disabled: bool,
) -> str:
    suffix = _scenario_metadata(scenario_id)[2]
    if target_template is None:
        return f"缺失 {suffix} 模板"
    if provider_disabled:
        return "Provider 当前已禁用"
    if not capability_available:
        return "数据能力当前未注册"
    if template_disabled:
        return "模板当前已禁用"
    return ""


def _expects_fusion_ball(
    definition: BusinessDefinition,
    target_template: ProviderTemplateDefinition | None,
    appearance: GalleryAppearance,
    fusion_business_ids: set[str],
) -> bool:
    if not appearance.fusion_enabled or target_template is None:
        return False
    eligible_layout = target_template.suffix in {"Compact", "Full", "Hero"}
    business_matches = definition.business_id in fusion_business_ids
    return eligible_layout and business_matches


def write_gallery_input_dataset(
    output_root: Path,
    *,
    provider_root: Path = _PROVIDER_ROOT,
    capability_root: Path = _CAPABILITY_ROOT,
    theme_root: Path = _THEME_ROOT,
) -> GalleryInputManifest:
    """根据当前 Provider 和能力注册表为每个模板构建适用的 2x2 模拟输入。"""
    definitions = _load_business_definitions(provider_root)
    data_capability_ids = _load_data_capability_ids(capability_root)
    asset_capabilities = _load_asset_capabilities(capability_root)
    controls = load_template_controls()
    event_capabilities = _load_event_capabilities(capability_root)
    fusion_business_ids = _load_fusion_business_ids(theme_root)
    _clear_generated_gallery_files(output_root)
    providers: list[GalleryInputProvider] = []
    for provider_slug in sorted({item.provider_slug for item in definitions}):
        provider_definitions = [
            item for item in definitions if item.provider_slug == provider_slug
        ]
        first = provider_definitions[0]
        cases: list[GalleryInputCase] = []
        for definition in provider_definitions:
            for scenario_id in (
                "single-two-actions",
                "single-one-action",
                "single-content",
            ):
                scenario_name, expected_layout, expected_suffix = _scenario_metadata(
                    scenario_id
                )
                templates = _templates_for_suffix(definition, expected_suffix)
                targets: tuple[ProviderTemplateDefinition | None, ...] = (
                    templates if templates else (None,)
                )
                for target_template in targets:
                    target_name = (
                        target_template.template_id.split("@", maxsplit=1)[0]
                        if target_template is not None
                        else f"Missing{expected_suffix}"
                    )
                    target_slug = _kebab_case(target_name)
                    business_slug = _kebab_case(definition.business_id)
                    missing_reason = _missing_reason(
                        target_template,
                        scenario_id,
                        capability_available=(
                            definition.capability_id in data_capability_ids
                        ),
                        provider_disabled=(
                            definition.provider_id in controls.disabled_provider_ids
                        ),
                        template_disabled=(
                            target_template is not None
                            and target_template.template_id
                            in controls.disabled_template_ids
                        ),
                    )
                    for appearance in _GALLERY_APPEARANCES:
                        case_id = (
                            f"{provider_slug}__{business_slug}__{target_slug}__"
                            f"{scenario_id}__{appearance.appearance_id}"
                        )
                        request_relative_path = (
                            Path("providers")
                            / provider_slug
                            / business_slug
                            / target_slug
                            / appearance.appearance_id
                            / f"{scenario_id}.json"
                        )
                        request_payload = _request_envelope(
                            definition,
                            target_template,
                            scenario_id,
                            appearance,
                            event_capabilities,
                            asset_capabilities,
                        )
                        request_path = output_root / request_relative_path
                        request_path.parent.mkdir(parents=True, exist_ok=True)
                        request_path.write_text(
                            json.dumps(request_payload, ensure_ascii=False, indent=2)
                            + "\n",
                            encoding="utf-8",
                        )
                        cases.append(
                            GalleryInputCase(
                                caseId=case_id,
                                providerId=definition.provider_id,
                                providerName=definition.provider_name,
                                providerSlug=provider_slug,
                                businessId=definition.business_id,
                                businessName=definition.business_name,
                                scenarioId=scenario_id,
                                scenarioName=(
                                    f"{appearance.appearance_name} · {scenario_name}"
                                ),
                                appearanceId=appearance.appearance_id,
                                appearanceName=appearance.appearance_name,
                                prdVer=appearance.prd_ver,
                                expectsFusionBall=_expects_fusion_ball(
                                    definition,
                                    target_template,
                                    appearance,
                                    fusion_business_ids,
                                ),
                                expectedLayout=expected_layout,
                                expectedTemplateSuffix=expected_suffix,
                                targetTemplateId=(
                                    target_template.template_id
                                    if target_template is not None
                                    else ""
                                ),
                                targetTemplateDescription=(
                                    target_template.description
                                    if target_template is not None
                                    else ""
                                ),
                                requestFile=request_relative_path.as_posix(),
                                missingReason=missing_reason,
                            )
                        )
        providers.append(
            GalleryInputProvider(
                providerId=first.provider_id,
                providerName=first.provider_name,
                providerSlug=provider_slug,
                cases=cases,
            )
        )
    manifest = GalleryInputManifest(providers=providers)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_gallery_input_manifest(input_root: Path) -> GalleryInputManifest:
    """读取并严格校验画廊输入清单。"""
    payload = json.loads((input_root / "manifest.json").read_text(encoding="utf-8"))
    manifest = GalleryInputManifest.model_validate(payload)
    if manifest.schemaVersion != INPUT_SCHEMA_VERSION:
        raise ValueError(f"unsupported gallery input schema: {manifest.schemaVersion}")
    return manifest


def _request_from_envelope(payload: dict[str, Any]) -> GenerateWidgetCardRequest:
    envelope = ToolRequestEnvelope.model_validate(payload)
    device_info = envelope.deviceInfo
    content = dict(envelope.content)
    content.pop("bundleName", None)
    request = GenerateWidgetCardRequest(
        **content,
        uid=envelope.userAuth.user.userId or "template-gallery",
        locale=device_info.locale or "zh-CN",
        prdVer=device_info.prdVer,
        device={
            "deviceId": device_info.deviceId,
            "deviceName": device_info.deviceFormation,
            "deviceType": device_info.phoneType or str(device_info.deviceType or ""),
            "marketingName": device_info.marketingName or device_info.phoneType,
            "romVersion": device_info.romVersion or DEFAULT_ROM_VERSION,
            "sysVersion": device_info.sysVer,
            "udid": device_info.udid,
        },
    )
    session_id = envelope.session.sessionId or "template-gallery"
    interaction_id = envelope.session.interactionId or "1"
    request._model_request_context = ModelRequestContext(
        session_id=session_id,
        interaction_id=interaction_id,
        device_id=device_info.deviceId or "template-gallery-device",
        country_code=device_info.countryCode or "CN",
        app_version=device_info.prdVer or DEFAULT_PRD_VERSION,
        app_name=envelope.bundleName or DEFAULT_BUNDLE_NAME,
    )
    return request


def _gallery_sample_overrides_from_envelope(payload: dict[str, Any]) -> dict[str, object]:
    gallery_test = payload.get("galleryTest")
    if gallery_test is None:
        return {}
    if not isinstance(gallery_test, dict):
        raise ValueError("galleryTest must be an object")
    sample_overrides = gallery_test.get("sampleOverrides", {})
    if not isinstance(sample_overrides, dict):
        raise ValueError("galleryTest.sampleOverrides must be an object")
    return dict(sample_overrides)


def _safe_request_path(input_root: Path, request_file: str) -> Path:
    root = input_root.resolve()
    path = (root / request_file).resolve()
    if root != path and root not in path.parents:
        raise ValueError(f"gallery request path escapes input root: {request_file}")
    return path


def _parse_genui_messages(genui: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for line_number, line in enumerate(genui.splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"genui line {line_number} is not an object")
        messages.append(payload)
    if not messages:
        raise ValueError("generated genui is empty")
    return messages


def _count_a2ui_actions(messages: list[dict[str, Any]]) -> int:
    count = 0
    for message in messages:
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        components = update.get("components")
        if not isinstance(components, list):
            continue
        count += sum(
            isinstance(component, dict)
            and isinstance(component.get("onClick"), list)
            and bool(component["onClick"])
            for component in components
        )
    return count


def _has_fusion_ball(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        components = update.get("components")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            if component.get("id") == "fusionBallBackground":
                return True
    return False


def _expected_action_count(scenario_id: str) -> int:
    return {
        "single-two-actions": 2,
        "single-one-action": 1,
        "single-content": 0,
    }[scenario_id]


class ProviderGalleryBatchRunner:
    """通过正式 Terse DSL Nested-2 服务入口生成 Provider 画廊数据。"""

    def __init__(self, service: GalleryGenerationService) -> None:
        self.service = service

    async def run(
        self,
        input_root: Path,
        output_root: Path,
        *,
        concurrency: int = 1,
        provider_ids: set[str] | None = None,
        dry_run: bool = False,
        model_failure_attempts: int = 2,
    ) -> GalleryRunSummary:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if model_failure_attempts < 1:
            raise ValueError("model_failure_attempts must be at least 1")
        manifest = load_gallery_input_manifest(input_root)
        _clear_generated_gallery_files(output_root)
        selected_providers = [
            provider
            for provider in manifest.providers
            if provider_ids is None or provider.providerId in provider_ids
        ]
        capture = _ArtifactCapture()
        semaphore = asyncio.Semaphore(concurrency)
        provider_results: dict[str, list[dict[str, Any]]] = {
            provider.providerId: [] for provider in selected_providers
        }

        async def execute_case(case: GalleryInputCase) -> dict[str, Any]:
            if case.missingReason:
                return self._base_result(case, "missing", case.missingReason)
            if dry_run:
                return self._base_result(case, "not_generated", "尚未执行端到端批跑")
            async with semaphore:
                result: dict[str, Any] = {}
                for _attempt in range(model_failure_attempts):
                    result = await self._generate_case(
                        case,
                        input_root,
                        output_root,
                        capture,
                    )
                    retryable = result.get("status") == "failed"
                    retryable = retryable and result.get("errorCode") == (
                        ErrorCode.A2UI_GENERATION_FAILED.value
                    )
                    if not retryable:
                        break
                return result

        async def capture_save(
            store: ArtifactStore,
            artifact: WidgetArtifact,
        ) -> ArtifactSaveResult:
            return await capture.save(store, artifact)

        with patch.object(ArtifactStore, "save", new=capture_save):
            for provider in selected_providers:
                results = await asyncio.gather(
                    *(execute_case(case) for case in provider.cases)
                )
                provider_results[provider.providerId].extend(results)

        output_root.mkdir(parents=True, exist_ok=True)
        output_manifest = self._output_manifest(selected_providers, provider_results)
        manifest_path = output_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(output_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        counts = output_manifest["counts"]
        return GalleryRunSummary(
            manifest_path=manifest_path,
            total=counts["total"],
            success=counts["success"],
            failed=counts["failed"],
            missing=counts["missing"],
            not_generated=counts["notGenerated"],
        )

    async def _generate_case(
        self,
        case: GalleryInputCase,
        input_root: Path,
        output_root: Path,
        capture: _ArtifactCapture,
    ) -> dict[str, Any]:
        request_path = _safe_request_path(input_root, case.requestFile)
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        request = _request_from_envelope(payload)
        trusted_template_candidate_ids = (
            (case.targetTemplateId,) if case.targetTemplateId else ()
        )
        trusted_template_action_ids = tuple(
            candidate.capabilityId for candidate in request.candidateEventCandidates or []
        )
        trusted_template_sample_overrides = _gallery_sample_overrides_from_envelope(
            payload
        )
        token = _CURRENT_CASE_ID.set(case.caseId)
        try:
            response = await self.service.generate_widget_card_terse_dsl_nested2(
                request,
                trusted_template_candidate_ids=trusted_template_candidate_ids,
                trusted_template_action_ids=trusted_template_action_ids,
                trusted_template_sample_overrides=trusted_template_sample_overrides,
            )
        except Exception as exc:
            return self._base_result(
                case,
                "failed",
                f"{type(exc).__name__}: {exc}",
            )
        finally:
            _CURRENT_CASE_ID.reset(token)
        artifact = capture.artifacts.pop(case.caseId, None)
        successful_status = response.status in {
            GenerationStatus.SUCCESS,
            GenerationStatus.DEGRADED,
        }
        if not successful_status or artifact is None:
            message = response.message or "生成接口未返回 A2UI Artifact"
            return self._base_result(
                case,
                "failed",
                message,
                error_code=response.errorCode,
                generation_status=response.status.value,
            )
        messages = _parse_genui_messages(artifact.genui)
        expected_action_count = _expected_action_count(case.scenarioId)
        actual_action_count = _count_a2ui_actions(messages)
        if actual_action_count != expected_action_count:
            return self._base_result(
                case,
                "failed",
                (
                    "布局校验失败："
                    f"期望 {expected_action_count} 个 Action，实际 {actual_action_count} 个"
                ),
                generation_status=response.status.value,
            )
        fusion_ball_rendered = _has_fusion_ball(messages)
        if fusion_ball_rendered != case.expectsFusionBall:
            return self._base_result(
                case,
                "failed",
                (
                    "融球版本校验失败："
                    f"期望 {case.expectsFusionBall}，实际 {fusion_ball_rendered}"
                ),
                generation_status=response.status.value,
            )
        target_slug = _kebab_case(
            case.targetTemplateId.split("@", maxsplit=1)[0] or "missing-template"
        )
        relative_path = (
            Path("providers")
            / case.providerSlug
            / _kebab_case(case.businessId)
            / target_slug
            / case.appearanceId
            / f"{case.scenarioId}.json"
        )
        output_path = output_root / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self._base_result(
            case,
            "success",
            "",
            generation_status=response.status.value,
        )
        result["a2uiFile"] = relative_path.as_posix()
        result["artifactDigest"] = response.artifactDigest
        result["messageCount"] = len(messages)
        result["fusionBallRendered"] = fusion_ball_rendered
        return result

    @staticmethod
    def _base_result(
        case: GalleryInputCase,
        status: str,
        error_message: str,
        *,
        error_code: str = "",
        generation_status: str = "",
    ) -> dict[str, Any]:
        return {
            "caseId": case.caseId,
            "providerId": case.providerId,
            "providerName": case.providerName,
            "providerSlug": case.providerSlug,
            "businessId": case.businessId,
            "businessName": case.businessName,
            "scenarioId": case.scenarioId,
            "scenarioName": case.scenarioName,
            "appearanceId": case.appearanceId,
            "appearanceName": case.appearanceName,
            "prdVer": case.prdVer,
            "appVersion": case.prdVer,
            "expectsFusionBall": case.expectsFusionBall,
            "expectedLayout": case.expectedLayout,
            "expectedTemplateSuffix": case.expectedTemplateSuffix,
            "targetTemplateId": case.targetTemplateId,
            "targetTemplateDescription": case.targetTemplateDescription,
            "partnerTemplateId": "",
            "requestFile": case.requestFile,
            "status": status,
            "generationStatus": generation_status,
            "a2uiFile": "",
            "artifactDigest": "",
            "messageCount": 0,
            "fusionBallRendered": False,
            "errorCode": error_code,
            "errorMessage": error_message,
        }

    @staticmethod
    def _output_manifest(
        providers: list[GalleryInputProvider],
        provider_results: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        output_providers = []
        all_results: list[dict[str, Any]] = []
        for provider in providers:
            cases = provider_results[provider.providerId]
            all_results.extend(cases)
            output_providers.append(
                {
                    "providerId": provider.providerId,
                    "providerName": provider.providerName,
                    "providerSlug": provider.providerSlug,
                    "cases": cases,
                }
            )
        return {
            "schemaVersion": OUTPUT_SCHEMA_VERSION,
            "operation": "generate_widget_card_terse_dsl_nested2",
            "cardSize": "2x2",
            "counts": {
                "total": len(all_results),
                "success": sum(item["status"] == "success" for item in all_results),
                "failed": sum(item["status"] == "failed" for item in all_results),
                "missing": sum(item["status"] == "missing" for item in all_results),
                "notGenerated": sum(
                    item["status"] == "not_generated" for item in all_results
                ),
            },
            "providers": output_providers,
        }


async def generate_provider_gallery(
    input_root: Path,
    output_root: Path,
    *,
    concurrency: int = 1,
    provider_ids: set[str] | None = None,
    dry_run: bool = False,
    model_failure_attempts: int = 2,
) -> GalleryRunSummary:
    """创建共享模型运行时并执行一次完整 Provider 画廊批跑。"""
    runtime = ModelExecutionRuntime()
    try:
        service = WidgetGenerationService(model_runtime=runtime)
        runner = ProviderGalleryBatchRunner(service)
        return await runner.run(
            input_root,
            output_root,
            concurrency=concurrency,
            provider_ids=provider_ids,
            dry_run=dry_run,
            model_failure_attempts=model_failure_attempts,
        )
    finally:
        await runtime.aclose()
