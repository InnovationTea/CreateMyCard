"""Provider 模板画廊输入构建与端到端批量生成，仅供开发测试使用。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
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
from core.errors import GenerationStatus
from custom.model_runtime import ModelExecutionRuntime
from models.artifact import WidgetArtifact
from models.generation import ModelRequestContext
from models.service import ArtifactSaveResult
from services.artifact_store import ArtifactStore
from services.widget_generation_service import WidgetGenerationService

INPUT_SCHEMA_VERSION = "provider-template-gallery-input/1"
OUTPUT_SCHEMA_VERSION = "provider-template-gallery-output/1"
DEFAULT_APP_VERSION = "11.7.5.205"
DEFAULT_ROM_VERSION = "6.0"
DEFAULT_BUNDLE_NAME = "com.huawei.genui.evaluation"

_TEMPLATE_GENERATION_ROOT = Path(__file__).resolve().parents[1]
_PROVIDER_ROOT = _TEMPLATE_GENERATION_ROOT / "resources" / "source" / "providers"
_CAPABILITY_ROOT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "capabilities"
    / "app-11.7.5.205_rom-6.0"
)
_CURRENT_CASE_ID: ContextVar[str] = ContextVar("provider_gallery_case_id", default="")

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
    "CalendarOverview": ("日历日程", "展示今天日期和下一项日程"),
    "CountdownOverview": ("倒计时", "展示距离元旦还有多少天"),
    "HeartRateOverview": ("运动心率", "展示最近一次运动的平均心率"),
    "ResourceUsageOverview": ("系统内存", "展示内存占用率和可用内存"),
    "SleepOverview": ("睡眠", "展示昨晚睡眠时长、得分和状态"),
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
    expectedLayout: str
    expectedTemplateSuffix: str
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
class BusinessDefinition:
    """从 Provider 配置派生的业务模板组。"""

    provider_id: str
    provider_name: str
    provider_slug: str
    business_id: str
    business_name: str
    capability_id: str
    data_domain: str
    fields_by_suffix: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class GalleryRunSummary:
    """一次批跑的结果摘要。"""

    manifest_path: Path
    total: int
    success: int
    failed: int
    missing: int
    not_generated: int


class GalleryGenerationService(Protocol):
    """批跑依赖的正式生成入口协议。"""

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: GenerateWidgetCardRequest,
    ) -> GenerateWidgetCardResponse: ...


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
    for suffix in ("WideHero", "WideFull", "Compact", "Hero", "Full", "Compat"):
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
            fields_by_suffix = _fields_by_suffix(templates)
            definitions.append(
                BusinessDefinition(
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_slug=provider_slug,
                    business_id=business_id,
                    business_name=business_meta[0],
                    capability_id=capability_id,
                    data_domain=data_domains[capability_id],
                    fields_by_suffix=fields_by_suffix,
                )
            )
    return definitions


def _fields_by_suffix(templates: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    fields: dict[str, list[str]] = {}
    fallback_fields: list[str] = []
    for template in templates:
        template_fields = [
            *template.get("primaryData", []),
            *template.get("secondaryData", []),
        ]
        fallback_fields.extend(str(item) for item in template_fields)
        suffix = _template_suffix(str(template["templateId"]))
        if suffix:
            fields.setdefault(suffix, []).extend(str(item) for item in template_fields)
    result = {key: _ordered_unique(value) for key, value in fields.items()}
    result["fallback"] = _ordered_unique(fallback_fields)
    return result


def _load_event_capabilities(capability_root: Path) -> dict[str, dict[str, Any]]:
    path = capability_root / "event_capabilities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in payload}


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
    suffix: str,
) -> dict[str, Any]:
    fields = definition.fields_by_suffix.get(suffix)
    if not fields:
        fields = definition.fields_by_suffix["fallback"]
    return {
        "arguments": deepcopy(_CAPABILITY_ARGUMENTS[definition.capability_id]),
        "candidateOutputFields": list(fields),
        "capabilityId": definition.capability_id,
        "writeResultTo": definition.data_domain,
    }


def _partner_by_business(
    definitions: list[BusinessDefinition],
) -> dict[str, BusinessDefinition]:
    compact_definitions = [
        item for item in definitions if "Compact" in item.fields_by_suffix
    ]
    partners: dict[str, BusinessDefinition] = {}
    for definition in definitions:
        different_providers = [
            item
            for item in compact_definitions
            if item.provider_id != definition.provider_id
        ]
        if different_providers:
            offset = definitions.index(definition) % len(different_providers)
            partners[definition.business_id] = different_providers[offset]
    return partners


def _request_envelope(
    definition: BusinessDefinition,
    partner: BusinessDefinition,
    scenario_id: str,
    event_capabilities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    business_description = _BUSINESS_DESCRIPTIONS[definition.business_id][1]
    partner_description = _BUSINESS_DESCRIPTIONS[partner.business_id][1]
    suffix = {
        "single-two-actions": "Compact",
        "two-contents": "Compact",
        "single-one-action": "Hero",
        "single-content": "Full",
    }[scenario_id]
    data_bindings = [_data_binding(definition, suffix)]
    action_count = 0
    if scenario_id == "two-contents":
        data_bindings.append(_data_binding(partner, "Compact"))
        user_query = (
            f"生成一个2×2组合卡片，一块内容{business_description}，"
            f"另一块内容{partner_description}，两块内容同等重要，不显示操作按钮。"
        )
    elif scenario_id == "single-two-actions":
        action_count = 2
        user_query = (
            f"生成一个2×2卡片，只用一块紧凑内容{business_description}，"
            "底部提供两个可点击操作。"
        )
    elif scenario_id == "single-one-action":
        action_count = 1
        user_query = (
            f"生成一个2×2卡片，用主视觉内容{business_description}，"
            "底部提供一个可点击操作。"
        )
    else:
        user_query = f"生成一个2×2完整信息卡片，{business_description}，不显示操作按钮。"
    action_ids = _ACTION_IDS_BY_BUSINESS[definition.business_id][:action_count]
    event_candidates = [
        _event_candidate(event_capabilities, action_id) for action_id in action_ids
    ]
    content = {
        "bundleName": DEFAULT_BUNDLE_NAME,
        "candidateAssetIds": [],
        "candidateDataBindings": data_bindings,
        "candidateEventCandidates": event_candidates,
        "description": f"{definition.business_name}模板画廊端到端验证",
        "size": "2x2",
        "title": f"{definition.business_name}模板画廊",
        "userQuery": user_query,
    }
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
            "prdVer": DEFAULT_APP_VERSION,
            "romVersion": DEFAULT_ROM_VERSION,
            "sysVer": "HarmonyOS NEXT",
            "time": "20260826000000000",
        },
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": "1",
            "isNew": True,
            "sessionId": (
                f"gallery-{definition.provider_slug}-"
                f"{_kebab_case(definition.business_id)}-{case_suffix}"
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
        "two-contents": ("2 个内容", "2 × Compact", "Compact"),
        "single-one-action": (
            "单内容 + 1 个 Action",
            "Hero + PillAction",
            "Hero",
        ),
        "single-content": ("单内容", "Full", "Full"),
    }
    return metadata[scenario_id]


def _missing_reason(
    definition: BusinessDefinition,
    partner: BusinessDefinition,
    scenario_id: str,
) -> str:
    suffix = _scenario_metadata(scenario_id)[2]
    if suffix not in definition.fields_by_suffix:
        return f"缺失 {suffix} 模板"
    partner_has_compact = "Compact" in partner.fields_by_suffix
    if scenario_id == "two-contents" and not partner_has_compact:
        return "缺失可配对的 Compact 模板"
    return ""


def write_gallery_input_dataset(
    output_root: Path,
    *,
    provider_root: Path = _PROVIDER_ROOT,
    capability_root: Path = _CAPABILITY_ROOT,
) -> GalleryInputManifest:
    """根据当前 Provider 和能力注册表构建四类 2x2 模拟输入。"""
    definitions = _load_business_definitions(provider_root)
    partners = _partner_by_business(definitions)
    event_capabilities = _load_event_capabilities(capability_root)
    providers: list[GalleryInputProvider] = []
    for provider_slug in sorted({item.provider_slug for item in definitions}):
        provider_definitions = [
            item for item in definitions if item.provider_slug == provider_slug
        ]
        first = provider_definitions[0]
        cases: list[GalleryInputCase] = []
        for definition in provider_definitions:
            partner = partners[definition.business_id]
            for scenario_id in (
                "single-two-actions",
                "two-contents",
                "single-one-action",
                "single-content",
            ):
                scenario_name, expected_layout, expected_suffix = _scenario_metadata(
                    scenario_id
                )
                business_slug = _kebab_case(definition.business_id)
                case_id = f"{provider_slug}__{business_slug}__{scenario_id}"
                request_relative_path = (
                    Path("providers")
                    / provider_slug
                    / business_slug
                    / f"{scenario_id}.json"
                )
                request_payload = _request_envelope(
                    definition,
                    partner,
                    scenario_id,
                    event_capabilities,
                )
                request_path = output_root / request_relative_path
                request_path.parent.mkdir(parents=True, exist_ok=True)
                request_path.write_text(
                    json.dumps(request_payload, ensure_ascii=False, indent=2) + "\n",
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
                        scenarioName=scenario_name,
                        expectedLayout=expected_layout,
                        expectedTemplateSuffix=expected_suffix,
                        requestFile=request_relative_path.as_posix(),
                        missingReason=_missing_reason(
                            definition,
                            partner,
                            scenario_id,
                        ),
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
        prdVer=device_info.prdVer or DEFAULT_APP_VERSION,
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
        app_version=device_info.prdVer or DEFAULT_APP_VERSION,
        app_name=envelope.bundleName or DEFAULT_BUNDLE_NAME,
    )
    return request


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
    ) -> GalleryRunSummary:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        manifest = load_gallery_input_manifest(input_root)
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
                return await self._generate_case(
                    case,
                    input_root,
                    output_root,
                    capture,
                )

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
        token = _CURRENT_CASE_ID.set(case.caseId)
        try:
            response = await self.service.generate_widget_card_terse_dsl_nested2(request)
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
        relative_path = (
            Path("providers")
            / case.providerSlug
            / _kebab_case(case.businessId)
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
            "expectedLayout": case.expectedLayout,
            "expectedTemplateSuffix": case.expectedTemplateSuffix,
            "requestFile": case.requestFile,
            "status": status,
            "generationStatus": generation_status,
            "a2uiFile": "",
            "artifactDigest": "",
            "messageCount": 0,
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
        )
    finally:
        await runtime.aclose()
