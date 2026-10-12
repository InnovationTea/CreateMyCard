"""Build a deterministic A2UI gallery dataset from Provider Templates."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from models.generation import TaskSpec
from services.capability_registry import CapabilityRegistry
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    convert_tersel_to_a2ui,
)

from .compiler import (
    _bind_template_actions,
    _expand_health_metric_generic_template,
    _instantiate_blueprint,
    _serialize_effective_document,
    _strip_advanced_component_markers,
)
from .models import (
    ActionBinding,
    HybridBodyContract,
    TemplateBinding,
    TemplateDefinition,
    ThemeDefinition,
)
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry

TemplateLayoutKind = Literal[
    "HeroTitle",
    "HeroContent",
    "Support",
    "Compact",
    "Hero",
    "Full",
    "WideHero",
    "WideFull",
    "WideHalf",
]

_LAYOUT_ORDER = {
    "HeroTitle": 0,
    "HeroContent": 1,
    "Support": 2,
    "Compact": 3,
    "Hero": 4,
    "Full": 5,
    "WideHero": 6,
    "WideFull": 7,
    "WideHalf": 8,
}
_SIZE_BY_LAYOUT: dict[TemplateLayoutKind, Literal["2x2", "2x4"]] = {
    "HeroTitle": "2x2",
    "HeroContent": "2x2",
    "Support": "2x2",
    "Compact": "2x2",
    "Hero": "2x2",
    "Full": "2x2",
    "WideHero": "2x4",
    "WideFull": "2x4",
    "WideHalf": "2x4",
}
_CONTENT_HEIGHT_BY_LAYOUT: dict[TemplateLayoutKind, int] = {
    "HeroTitle": 24,
    "HeroContent": 54,
    "Support": 68,
    "Compact": 68,
    "Hero": 124,
    "Full": 136,
    "WideHero": 124,
    "WideFull": 136,
    "WideHalf": 68,
}
_ASSET_BY_PARAMETER = {
    "actionIcon": "resources/base/media/figure_run.svg",
    "alertIcon": "resources/base/media/bell_fill.svg",
    "appIcon": "resources/base/media/icon_tiktok.png",
    "batteryIcon": "resources/base/media/battery_leaf_fill.svg",
    "bellIcon": "resources/base/media/bell_fill.svg",
    "calendarIcon": "resources/base/media/calendar_fill.svg",
    "caseIcon": "resources/base/media/earphone_case_16644.svg",
    "countdownIcon": "resources/base/media/icon_timing.svg",
    "earphoneIcon": "resources/base/media/icon_earphone.svg",
    "healthIcon": "resources/base/media/battery_leaf_fill.svg",
    "heartIcon": "resources/base/media/heart_fill.svg",
    "deviceIcon": "resources/base/media/earphone_case_16644.svg",
    "caloriesIcon": "resources/base/media/flame_fill.svg",
    "distanceIcon": "resources/base/media/location_north_up_right_fill.svg",
    "icon": "resources/base/media/externaldrive_fill.svg",
    "leftEarIcon": "resources/base/media/l_circle_fill.svg",
    "locationIcon": "resources/base/media/location_north_up_right_fill.svg",
    "meetingIcon": "resources/base/media/icon_meeting.svg",
    "musicIcon": "resources/base/media/music_fill.svg",
    "rainIcon": "resources/base/media/drop_1.svg",
    "rightEarIcon": "resources/base/media/r_circle_fill.svg",
    "stepsIcon": "resources/base/media/figure_run.svg",
    "temperatureIcon": "resources/base/media/heat_generation.svg",
    "timeIcon": "resources/base/media/clock_fill.svg",
    "uvIcon": "resources/base/media/sun_max.svg",
}
_SOURCE_ICON_BY_BUSINESS = {
    "BluetoothDeviceOverview": "resources/base/media/icon_earphone.svg",
    "HeartRateOverview": "resources/base/media/heart_fill.svg",
    "GenericMetricOverview": "resources/base/media/figure_run.svg",
    "CalendarOverview": "resources/base/media/calendar_fill.svg",
    "SleepOverview": "resources/base/media/moon_z_fill_1.svg",
    "WorkoutOverview": "resources/base/media/figure_run.svg",
}
_GENERIC_PREVIEW_VALUES = {
    "/dailySteps": {"type": "integer", "description": "步数", "sampleValue": 6200},
    "/exerciseHeartRateAvg": {"type": "integer", "description": "平均心率", "sampleValue": 88},
}
_TEXT_BY_TEMPLATE_PARAMETER = {
    ("GenericMetricOverviewCompact@1", "title"): "步数",
    ("GenericMetricOverviewCompact@1", "valuePath"): "/dailySteps",
    ("GenericMetricOverviewDualCompact@1", "firstTitle"): "步数",
    ("GenericMetricOverviewDualCompact@1", "firstValuePath"): "/dailySteps",
    ("GenericMetricOverviewDualCompact@1", "secondTitle"): "平均心率",
    ("GenericMetricOverviewDualCompact@1", "secondValuePath"): "/exerciseHeartRateAvg",
    ("BluetoothDeviceOverviewHero@1", "title"): "耳机听歌入口",
    ("WeatherOverviewAirQualityHero@1", "location"): "青浦区",
    ("WeatherOverviewHumidityFull@1", "location"): "青浦区",
    ("WeatherOverviewUvFull@1", "location"): "青浦区",
    ("ActivityOverviewTrainingSummaryFull@1", "title"): "训练总结",
    ("BluetoothDeviceOverviewMusicCompact@1", "actionId"): "event.open.music.daily",
    ("BluetoothDeviceOverviewEarbudsChargingWideFull@1", "actionId"):
        "event.open.settings.bluetooth",
    ("CountdownOverviewDepartureHero@1", "title"): "北京出差",
    ("CountdownOverviewTargetDetailFull@1", "targetDate"): "2026-11-15",
    ("CountdownOverviewTravelSupport@1", "title"): "国庆回家",
    ("ScheduleOverviewMeetingSenderFull@1", "title"): "UI需求评审会",
    ("WeatherOverviewDestinationDayFull@1", "targetDate"): "8月22日",
}
# 单业务多云样例没有匹配状态素材，省略图标；Support 可使用表达气温的温度计。
_SUPPORT_PREVIEW_ASSET_OVERRIDES: dict[tuple[str, str], str | None] = {
    ("BluetoothDeviceOverviewEarphoneHero@1", "deviceIcon"):
        "resources/base/media/icon_earphone.svg",
    ("BluetoothDeviceOverviewEarbudsSupport@1", "deviceIcon"):
        "resources/base/media/icon_earphone.svg",
    ("BluetoothDeviceOverviewConnectionSupport@1", "deviceIcon"):
        "resources/base/media/icon_earphone.svg",
    ("BluetoothDeviceOverviewMusicCompact@1", "musicIcon"):
        "resources/base/media/music_fill.svg",
    ("BatteryOverviewSupport@1", "batteryIcon"):
        None,
    ("WeatherOverviewTemperatureSupport@1", "conditionIcon"):
        "resources/base/media/icon_weather_thermometer.svg",
    ("WeatherOverviewDaily2TravelSupport@1", "conditionIcon"):
        "resources/base/media/icon_weather_thermometer.svg",
    ("WeatherOverviewTravelSupport@1", "conditionIcon"):
        "resources/base/media/icon_weather_thermometer.svg",
}
# 当前素材版本已移除手机设备图标，不能把电池或电话听筒图标作为替代。
_UNAVAILABLE_PREVIEW_TEMPLATES = {
    "BatteryOverviewSupportHero@1": "缺少模板必需的已注册手机设备图标",
    "BatteryOverviewChargeStatusHero@1": "缺少模板必需的已注册手机设备图标",
}
# 预览用可选文本参数按业务取真实样例值；模板间需要差异时用 _TEXT_BY_TEMPLATE_PARAMETER 覆盖。
_TEXT_BY_BUSINESS_PARAMETER = {
    ("CalendarOverview", "headerLabel"): "今天",
    ("CountdownOverview", "title"): "产品发布会",
    ("WeatherOverview", "location"): "青浦区",
}
_SAMPLE_BY_BUSINESS_BINDING: dict[tuple[str, str], Any] = {
    ("ActivityOverview", "averageHeartRate"): 135,
    ("ActivityOverview", "calories"): "420 千卡",
    ("ActivityOverview", "distance"): "4.6 公里",
    ("ActivityOverview", "duration"): "40分",
    ("ActivityOverview", "heartRate"): 135,
    ("ActivityOverview", "heartRateAvg"): 135,
    ("ActivityOverview", "heartRateMin"): 112,
    ("ActivityOverview", "score"): 82,
    ("ActivityOverview", "steps"): 6200,
    ("ActivityOverview", "targetDate"): "今天",
    ("ActivityOverview", "type"): "户外跑步",
    ("ActivityOverview", "updatedAt"): "今天 09:00",
    ("BluetoothDeviceOverview", "battery"): 80,
    ("BluetoothDeviceOverview", "case"): 65,
    ("BluetoothDeviceOverview", "caseCharge"): "充电中",
    ("BluetoothDeviceOverview", "charging"): "充电中",
    ("BluetoothDeviceOverview", "percent"): 80,
    ("BluetoothDeviceOverview", "chargingStatus"): "充电中",
    ("BluetoothDeviceOverview", "left"): 76,
    ("BluetoothDeviceOverview", "leftCharge"): "未充电",
    ("BluetoothDeviceOverview", "leftChargingStatus"): "未充电",
    ("BluetoothDeviceOverview", "leftDesc"): "未充电",
    ("BluetoothDeviceOverview", "name"): "FreeBuds Pro",
    ("BluetoothDeviceOverview", "right"): 78,
    ("BluetoothDeviceOverview", "rightCharge"): "充电中",
    ("BluetoothDeviceOverview", "rightChargingStatus"): "充电中",
    ("BluetoothDeviceOverview", "rightDesc"): "充电中",
    ("BluetoothDeviceOverview", "status"): "充电中",
    ("BluetoothDeviceOverview", "updated"): "今天 09:00",
    ("CountdownOverview", "days"): 28,
    ("CalendarOverview", "allDay"): True,
    ("CalendarOverview", "description"): "评审本周 UI 交付方案",
    ("CalendarOverview", "end"): "15:30",
    ("CalendarOverview", "countdown"): 3,
    ("CalendarOverview", "date"): "8月19日",
    ("CalendarOverview", "eventCount"): 1,
    ("CalendarOverview", "firstLocation"): "深圳市龙岗区五和大道",
    ("CalendarOverview", "firstStart"): "14:00",
    ("CalendarOverview", "firstTitle"): "UI需求评审会",
    ("CalendarOverview", "importance"): 2,
    ("CalendarOverview", "location"): "深圳市龙岗区五和大道",
    ("CalendarOverview", "reminder"): "15",
    ("CalendarOverview", "secondLocation"): "A3会议室",
    ("CalendarOverview", "secondStart"): "16:30",
    ("CalendarOverview", "secondTitle"): "华东渠道策略会",
    ("CalendarOverview", "sender"): "李娜",
    ("CalendarOverview", "start"): "14:00",
    ("CalendarOverview", "startDate"): "8月19日",
    ("CalendarOverview", "thirdLocation"): "B1会议室",
    ("CalendarOverview", "thirdStart"): "19:00",
    ("CalendarOverview", "thirdTitle"): "版本交付排期会",
    ("CalendarOverview", "timeZone"): "GMT+8",
    ("CalendarOverview", "title"): "UI需求评审会",
    ("CalendarOverview", "updated"): "今天 09:00",
    ("CalendarOverview", "updatedAt"): "今天 09:00",
    ("HeartRateOverview", "average"): 135,
    ("HeartRateOverview", "max"): 168,
    ("HeartRateOverview", "min"): 112,
    ("HeartRateOverview", "updatedAt"): "今天 09:00",
    ("ResourceUsageOverview", "available"): "5.2 GB",
    ("ResourceUsageOverview", "total"): "12 GB",
    ("ResourceUsageOverview", "usage"): 56.7,
    ("SleepOverview", "asleep"): "23:15",
    ("SleepOverview", "deepDuration"): "1小时42分",
    ("SleepOverview", "duration"): "7小时1分",
    ("SleepOverview", "endTime"): "07:30",
    ("SleepOverview", "napDuration"): "26分",
    ("SleepOverview", "score"): 82,
    ("SleepOverview", "startTime"): "23:15",
    ("SleepOverview", "steps"): 6200,
    ("SleepOverview", "status"): "良好",
    ("SleepOverview", "type"): "夜间睡眠",
    ("SleepOverview", "wakeup"): "07:30",
    ("WeatherOverview", "airQuality"): "良",
    ("WeatherOverview", "alertLevel"): "黄色",
    ("WeatherOverview", "city"): "青浦区",
    ("WeatherOverview", "coldLevel"): "低",
    ("WeatherOverview", "condition"): "多云",
    ("WeatherOverview", "currentCondition"): "多云",
    ("WeatherOverview", "currentTemperature"): 29.0,
    ("WeatherOverview", "daily4Condition"): "小雨",
    ("WeatherOverview", "daily4RainProbability"): "60%",
    ("WeatherOverview", "daily4TemperatureRange"): "22° / 28°",
    ("WeatherOverview", "date"): "8月20日",
    ("WeatherOverview", "district"): "青浦区",
    ("WeatherOverview", "feelsLike"): 31.0,
    ("WeatherOverview", "feelsLikeC"): 31.0,
    ("WeatherOverview", "firstCity"): "成都市",
    ("WeatherOverview", "firstCondition"): "多云",
    ("WeatherOverview", "firstDate"): "8月19日",
    ("WeatherOverview", "firstRainProbability"): "10%",
    ("WeatherOverview", "firstTemperature"): 29.0,
    ("WeatherOverview", "firstTemperatureRange"): "24° / 31°",
    ("WeatherOverview", "firstWeekday"): "周三",
    ("WeatherOverview", "humidity"): 70.0,
    ("WeatherOverview", "rainProbability"): "30%",
    ("WeatherOverview", "secondCity"): "上海市",
    ("WeatherOverview", "secondCondition"): "晴",
    ("WeatherOverview", "secondDate"): "8月20日",
    ("WeatherOverview", "secondRainProbability"): "30%",
    ("WeatherOverview", "secondTemperature"): 32.0,
    ("WeatherOverview", "secondTemperatureRange"): "25° / 33°",
    ("WeatherOverview", "secondWeekday"): "周四",
    ("WeatherOverview", "temperature"): "29°C",
    ("WeatherOverview", "temperatureC"): 29.0,
    ("WeatherOverview", "temperatureRange"): "25° / 32°",
    ("WeatherOverview", "temperatureText"): "29°C",
    ("WeatherOverview", "thirdCondition"): "小雨",
    ("WeatherOverview", "thirdDate"): "8月21日",
    ("WeatherOverview", "thirdRainProbability"): "40%",
    ("WeatherOverview", "thirdTemperatureRange"): "25° / 32°",
    ("WeatherOverview", "thirdWeekday"): "周五",
    ("WeatherOverview", "todayAirQuality"): "良",
    ("WeatherOverview", "todayCondition"): "多云",
    ("WeatherOverview", "tomorrowAirQuality"): "优",
    ("WeatherOverview", "tomorrowCondition"): "阴",
    ("WeatherOverview", "updatedAt"): "今天 09:00",
    ("WeatherOverview", "uvIndex"): "中等",
    ("WeatherOverview", "weekday"): "周四",
    ("WeatherOverview", "windDirection"): "东南风",
    ("WeatherOverview", "windLevel"): 3,
    ("WorkoutOverview", "duration"): "40分",
    ("WorkoutOverview", "endTime"): "19:10",
    ("WorkoutOverview", "heartRateAvg"): 135,
    ("WorkoutOverview", "heartRateMax"): 168,
    ("WorkoutOverview", "heartRateMin"): 112,
    ("WorkoutOverview", "startTime"): "18:30",
    ("WorkoutOverview", "workoutCalories"): "260 千卡",
    ("WorkoutOverview", "workoutDate"): "8月19日",
    ("WorkoutOverview", "workoutType"): "户外跑步",
}
_FALLBACK_SAMPLE_BY_TYPE: dict[str, Any] = {
    "string": "示例数据",
    "integer": 68,
    "number": 68.0,
    "boolean": True,
}


@dataclass(frozen=True)
class TemplatePreviewCase:
    case_id: str
    template_id: str
    business_id: str
    provider_id: str
    capability_id: str
    description: str
    layout_kind: TemplateLayoutKind
    size: Literal["2x2", "2x4"]
    content_height_vp: int
    primary_data: tuple[str, ...]
    secondary_data: tuple[str, ...]
    optional_data: tuple[str, ...]
    file_name: str
    messages: tuple[dict[str, Any], ...]

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "templateId": self.template_id,
            "businessId": self.business_id,
            "providerId": self.provider_id,
            "capabilityId": self.capability_id,
            "description": self.description,
            "layoutKind": self.layout_kind,
            "size": self.size,
            "contentHeightVp": self.content_height_vp,
            "primaryData": list(self.primary_data),
            "secondaryData": list(self.secondary_data),
            "optionalData": list(self.optional_data),
            "file": self.file_name,
        }


@dataclass(frozen=True)
class _PreviewDataset:
    cases: tuple[TemplatePreviewCase, ...]
    missing_templates: tuple[dict[str, str], ...]


def build_template_preview_cases() -> tuple[TemplatePreviewCase, ...]:
    """Expand available business Provider Templates into local A2UI previews."""
    return _build_preview_dataset().cases


def _build_preview_dataset() -> _PreviewDataset:
    registry = CardPlanRegistry(
        disabled_provider_ids=(),
        disabled_template_ids=(),
        enable_fusion_ball=True,
    )
    definitions = [
        registry.require_template(template_id)
        for template_id in registry.provider_template_ids
        if registry.require_template(template_id).capability_id is not None
    ]
    definitions.sort(key=_definition_sort_key)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    capability_registry = CapabilityRegistry(version="app-11.7.5.205_rom-6.0")
    data_capability_ids = {item.id for item in capability_registry.list_data_capabilities()}
    cases: list[TemplatePreviewCase] = []
    missing_templates: list[dict[str, str]] = []
    for index, definition in enumerate(definitions, start=1):
        case_id = f"T{index:03d}"
        reason = _UNAVAILABLE_PREVIEW_TEMPLATES.get(definition.wire_id)
        if definition.capability_id not in data_capability_ids:
            reason = "数据能力当前未注册或已禁用"
        if reason is not None:
            missing_templates.append(
                {"id": case_id, "templateId": definition.wire_id, "reason": reason}
            )
            continue
        cases.append(_build_case(case_id, definition, profile, registry))
    return _PreviewDataset(tuple(cases), tuple(missing_templates))


def write_template_preview_dataset(output_dir: Path) -> dict[str, Any]:
    """Write one A2UI array per template and return the generated manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = _build_preview_dataset()
    cases = dataset.cases
    expected_files = {case.file_name for case in cases}
    for stale in output_dir.glob("T*.json"):
        if stale.name not in expected_files:
            stale.unlink()
    for case in cases:
        _write_json(output_dir / case.file_name, list(case.messages))
    layout_counts = Counter(case.layout_kind for case in cases)
    size_counts = Counter(case.size for case in cases)
    manifest = {
        "datasetVersion": "provider-template-gallery/1",
        "templateCount": len(cases),
        "sourceTemplateCount": len(cases) + len(dataset.missing_templates),
        "missingTemplates": list(dataset.missing_templates),
        "countsByLayout": dict(
            sorted(layout_counts.items(), key=lambda item: _LAYOUT_ORDER[item[0]])
        ),
        "countsBySize": {size: size_counts[size] for size in ("2x2", "2x4")},
        "cases": [case.manifest_entry() for case in cases],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _build_case(
    case_id: str,
    definition: TemplateDefinition,
    protocol_profile: dict[str, Any],
    registry: CardPlanRegistry,
) -> TemplatePreviewCase:
    layout_kind = provider_template_layout_kind(definition.wire_id)
    size = _SIZE_BY_LAYOUT[layout_kind]
    content_height = _CONTENT_HEIGHT_BY_LAYOUT[layout_kind]
    data_schema = _build_data_schema(definition)
    task_spec = TaskSpec(
        userQuery=f"预览模板 {definition.wire_id}",
        size=size,
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema=data_schema,
    )
    variant = definition.variants[0]
    bindings = {
        name: _binding_placeholder(definition, binding)
        for name, binding in definition.bindings.items()
    }
    theme = _preview_theme(definition, registry)
    parameters = _template_parameters(definition)
    if definition.business_id == "GenericMetricOverview":
        if definition.data_domain is None:
            raise ValueError("Generic preview requires a provider data domain")
        content = _expand_health_metric_generic_template(
            definition.wire_id,
            parameters,
            task_spec=task_spec,
            provider_binding_roots={"GetHealthAndSportSummary": (definition.data_domain,)},
            theme_values=theme.reference_values,
        )
    else:
        content = _instantiate_blueprint(
            variant.root,
            parameters,
            bindings,
            theme.reference_values,
        )
    action_id = parameters.get("actionId")
    if action_id is not None:
        event = CapabilityRegistry(version="app-11.7.5.205_rom-6.0").get_event_capability(action_id)
        if event is None:
            raise ValueError(f"Preview event is not registered: {action_id}")
        binding = ActionBinding(
            action_id=action_id, event_id=event.id, display_label=event.description,
            call=event.actionTemplate.call, args=event.actionTemplate.args,
        )
        contract = HybridBodyContract.model_construct(
            action_bindings=(binding,), content_action_ids=(action_id,),
        )
        content, _ = _bind_template_actions(content, contract)
    content = _strip_advanced_component_markers(content)
    root = _preview_root(content, content_height, theme.root_style)
    effective = _serialize_effective_document(root, task_spec, True)
    a2ui = convert_tersel_to_a2ui(
        effective,
        size=size,
        protocol_profile=protocol_profile,
        task_spec=task_spec.model_dump(mode="json"),
    )
    messages = tuple(json.loads(line) for line in a2ui.splitlines() if line.strip())
    return TemplatePreviewCase(
        case_id=case_id,
        template_id=definition.wire_id,
        business_id=definition.business_id or "",
        provider_id=definition.provider_id or "",
        capability_id=definition.capability_id or "",
        description=definition.description,
        layout_kind=layout_kind,
        size=size,
        content_height_vp=content_height,
        primary_data=definition.primary_data,
        secondary_data=definition.secondary_data,
        optional_data=definition.optional_data,
        file_name=f"{case_id}.json",
        messages=messages,
    )


def _preview_theme(
    definition: TemplateDefinition,
    registry: CardPlanRegistry,
) -> ThemeDefinition:
    if definition.capability_id == "ViewWeather":
        theme = registry.themes.get("fusion-weather-blue")
        if theme is None:
            raise ValueError(f"No compatible preview theme: {definition.wire_id}")
        return theme

    compatible_themes = tuple(
        item
        for item in registry.themes.values()
        if definition.capability_id in item.supported_capability_ids
    )
    theme = next(
        (
            item
            for item in compatible_themes
            if item.fusion_ball_style is None and not item.supported_layout_ids
        ),
        None,
    )
    if theme is None:
        theme = next(
            (item for item in compatible_themes if item.fusion_ball_style is None),
            None,
        )
    if theme is None:
        theme = next(iter(compatible_themes), None)
    if theme is None:
        raise ValueError(f"No compatible preview theme: {definition.wire_id}")
    return theme


def _definition_sort_key(definition: TemplateDefinition) -> tuple[str, str, int, str]:
    layout_kind = provider_template_layout_kind(definition.wire_id)
    return (
        definition.provider_id or "",
        definition.business_id or "",
        _LAYOUT_ORDER[layout_kind],
        definition.wire_id,
    )


def _template_parameters(definition: TemplateDefinition) -> dict[str, str]:
    properties = definition.variants[0].parameters_schema.get("properties", {})
    parameters: dict[str, str] = {}
    for name in properties:
        key = (definition.wire_id, name)
        if key in _SUPPORT_PREVIEW_ASSET_OVERRIDES:
            asset = _SUPPORT_PREVIEW_ASSET_OVERRIDES.get(key)
            if asset is not None:
                parameters[name] = asset
            continue
        text = _TEXT_BY_TEMPLATE_PARAMETER.get((definition.wire_id, name))
        if text is not None:
            parameters[name] = text
        elif name == "sourceIcon":
            parameters[name] = _SOURCE_ICON_BY_BUSINESS.get(
                definition.business_id or "",
                "resources/base/media/icon_id.svg",
            )
        elif name in _ASSET_BY_PARAMETER:
            parameters[name] = _ASSET_BY_PARAMETER[name]
        elif name == "actionId":
            # 独立预览省略可选交互；必选操作在上方显式样例映射中提供。
            continue
        else:
            business_text = _TEXT_BY_BUSINESS_PARAMETER.get(
                (definition.business_id or "", name)
            )
            if business_text is not None:
                parameters[name] = business_text
    required = definition.variants[0].parameters_schema.get("required", [])
    missing = [name for name in required if name not in parameters]
    if missing:
        raise ValueError(f"Preview asset mapping is missing: {definition.wire_id}/{missing}")
    return parameters


def _build_data_schema(definition: TemplateDefinition) -> dict[str, Any]:
    schema: dict[str, Any] = {"data": {}}
    if definition.business_id == "GenericMetricOverview":
        for parameter, path in _template_parameters(definition).items():
            if not parameter.endswith("Path"):
                continue
            sample = _GENERIC_PREVIEW_VALUES.get(path)
            if sample is None:
                raise ValueError(f"Generic preview sample is missing: {path}")
            _set_path(schema, definition.data_domain.rstrip("/") + path, dict(sample))
    for name, binding in definition.bindings.items():
        full_path = f"{definition.data_domain.rstrip('/')}{binding.path}"
        leaf = {
            "type": binding.data_type,
            "description": f"{definition.business_id}.{name} 模板预览数据",
            "sampleValue": _sample_value(definition, name, binding.data_type),
        }
        _set_path(schema, full_path, leaf)
    return schema


def _sample_value(definition: TemplateDefinition, name: str, data_type: str) -> Any:
    if definition.business_id == "BatteryOverview":
        return _battery_sample(definition.wire_id, name, data_type)
    if definition.business_id == "BluetoothDeviceOverview" and name == "connected":
        return "Disconnected" not in definition.wire_id
    key = (definition.business_id or "", name)
    if key in _SAMPLE_BY_BUSINESS_BINDING:
        return _SAMPLE_BY_BUSINESS_BINDING[key]
    return _fallback_sample(data_type)


def _battery_sample(template_id: str, name: str, data_type: str) -> Any:
    if "Charging" in template_id:
        values: dict[str, Any] = {
            "percent": 84,
            "percentText": "84%",
            "charging": "正在充电",
            "chargingStatus": "正在充电",
            "current": "1.5 A",
            "health": "良好",
            "level": "正常电量",
            "temperature": "29.0 ℃",
            "plugged": "已插入",
            "pluggedType": "快充充电器",
            "present": "已识别",
            "status": "正在充电",
            "updatedAt": "今天 09:00",
            "voltage": "4.4 V",
        }
    elif "Low" in template_id:
        values = {
            "percent": 16,
            "percentText": "16%",
            "charging": "未充电",
            "chargingStatus": "未充电",
            "current": "0 A",
            "health": "良好",
            "level": "电量低",
            "plugged": "未插入",
            "pluggedType": "普通充电器",
            "present": "已识别",
            "status": "电量低",
            "updatedAt": "今天 09:00",
            "voltage": "3.8 V",
        }
    else:
        values = {
            "percent": 68,
            "percentText": "68%",
            "charging": "未充电",
            "chargingStatus": "未充电",
            "current": "0 A",
            "health": "良好",
            "level": "正常电量",
            "plugged": "未插入",
            "pluggedType": "普通充电器",
            "present": "已识别",
            "status": "未充电",
            "temperature": "29.0 ℃",
            "updatedAt": "今天 09:00",
            "voltage": "3.9 V",
        }
    return values.get(name, _fallback_sample(data_type))


def _fallback_sample(data_type: str) -> Any:
    return _FALLBACK_SAMPLE_BY_TYPE.get(data_type)


def _set_path(root: dict[str, Any], path: str, value: dict[str, Any]) -> None:
    tokens = [token for token in path.split("/") if token]
    current: dict[str, Any] | list[Any] = root
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_is_index = not is_last and tokens[index + 1].isdigit()
        if isinstance(current, list):
            list_index = int(token)
            while len(current) <= list_index:
                current.append({})
            if is_last:
                current[list_index] = value
            else:
                expected: dict[str, Any] | list[Any] = [] if next_is_index else {}
                if not isinstance(current[list_index], type(expected)):
                    current[list_index] = expected
                current = current[list_index]
            continue
        if is_last:
            current[token] = value
        else:
            expected = [] if next_is_index else {}
            if token not in current:
                current[token] = expected
            current = current[token]


def _binding_placeholder(definition: TemplateDefinition, binding: TemplateBinding) -> str:
    path = f"{definition.data_domain.rstrip('/')}{binding.path}"
    dotted = path.strip("/").replace("/", ".")
    return "${" + dotted + "}"


def _preview_root(
    content: Nested2Node,
    content_height: int,
    theme_root_style: dict[str, Any],
) -> Nested2Node:
    slot_options = {
        "width": "matchParent",
        "height": content_height,
        "justifyContent": "start",
        "alignItems": "start",
        "clip": True,
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    # Theme roots may carry container-specific positioning (for example
    # Stack.alignContent).  The gallery wrapper is always a Column, so only copy
    # the visual root properties here and let the wrapper own its layout.
    visual_root_style = {
        key: value
        for key, value in theme_root_style.items()
        if key != "alignContent"
    }
    root_options = {
        "_id": "root",
        **visual_root_style,
        "justifyContent": "start",
        "alignItems": "start",
    }
    slot_options["_id"] = "template_root"
    slot = Nested2Node("Column", ("section", slot_options), (content,))
    return Nested2Node("Column", ("card", root_options), (slot,))


def _write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def validate_preview_asset_paths(cases: tuple[TemplatePreviewCase, ...]) -> frozenset[str]:
    """Collect literal media paths so the HAP importer can verify bundled assets."""
    paths: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str) and value.startswith("resources/base/media/"):
            paths.add(value)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list | tuple):
            for child in value:
                visit(child)

    for case in cases:
        for message in case.messages:
            visit(message)
    return frozenset(paths)
