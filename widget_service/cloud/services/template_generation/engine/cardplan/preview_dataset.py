"""Build a deterministic A2UI gallery dataset from Provider Templates."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from models.generation import TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    convert_tersel_to_a2ui,
)

from .compiler import (
    _instantiate_blueprint,
    _serialize_effective_document,
    _strip_advanced_component_markers,
)
from .models import TemplateBinding, TemplateDefinition
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry

TemplateLayoutKind = Literal[
    "Support",
    "Compact",
    "Hero",
    "Full",
    "WideHero",
    "WideFull",
]

_LAYOUT_ORDER = {
    "Support": 0,
    "Compact": 1,
    "Hero": 2,
    "Full": 3,
    "WideHero": 4,
    "WideFull": 5,
}
_SIZE_BY_LAYOUT: dict[TemplateLayoutKind, Literal["2x2", "2x4"]] = {
    "Support": "2x2",
    "Compact": "2x2",
    "Hero": "2x2",
    "Full": "2x2",
    "WideHero": "2x4",
    "WideFull": "2x4",
}
_CONTENT_HEIGHT_BY_LAYOUT: dict[TemplateLayoutKind, int] = {
    "Support": 68,
    "Compact": 68,
    "Hero": 124,
    "Full": 136,
    "WideHero": 124,
    "WideFull": 136,
}
_ASSET_BY_PARAMETER = {
    "appIcon": "resources/base/media/icon_tiktok.png",
    "batteryIcon": "resources/base/media/battery_leaf_fill.svg",
    "deviceIcon": "resources/base/media/earphone_case_16644.svg",
    "caloriesIcon": "resources/base/media/flame_fill.svg",
    "conditionIcon": "resources/base/media/icon_weather1.svg",
    "distanceIcon": "resources/base/media/location_north_up_right_fill.svg",
    "icon": "resources/base/media/externaldrive_fill.svg",
    "leftEarIcon": "resources/base/media/l_circle_fill.svg",
    "locationIcon": "resources/base/media/location_north_up_right_fill.svg",
    "rightEarIcon": "resources/base/media/r_circle_fill.svg",
    "stepsIcon": "resources/base/media/figure_run.svg",
    "timeIcon": "resources/base/media/clock_fill.svg",
}
_SOURCE_ICON_BY_BUSINESS = {
    "AppUsageOverview": "resources/base/media/icon_tiktok.png",
    "BluetoothDeviceOverview": "resources/base/media/icon_earphone.svg",
    "HeartRateOverview": "resources/base/media/heart_fill.svg",
    "CalendarOverview": "resources/base/media/calendar_fill.svg",
    "SleepOverview": "resources/base/media/moon_z_fill_1.svg",
    "WorkoutOverview": "resources/base/media/figure_run.svg",
}
_TEXT_BY_TEMPLATE_PARAMETER = {
    ("BluetoothDeviceOverviewHero@1", "title"): "耳机听歌入口",
    ("WeatherOverviewAirQualityHero@1", "location"): "青浦区",
    ("WeatherOverviewHumidityFull@1", "location"): "青浦区",
    ("WeatherOverviewUvFull@1", "location"): "青浦区",
}
_SAMPLE_BY_BUSINESS_BINDING: dict[tuple[str, str], Any] = {
    ("ActivityOverview", "calories"): "420 千卡",
    ("ActivityOverview", "distance"): "4.6 公里",
    ("ActivityOverview", "steps"): 6200,
    ("AppUsageOverview", "appName"): "短视频",
    ("AppUsageOverview", "duration"): "1小时26分",
    ("AppUsageOverview", "updatedAt"): "今天 09:00",
    ("BluetoothDeviceOverview", "battery"): 80,
    ("BluetoothDeviceOverview", "chargingStatus"): "充电中",
    ("BluetoothDeviceOverview", "left"): 76,
    ("BluetoothDeviceOverview", "leftChargingStatus"): "未充电",
    ("BluetoothDeviceOverview", "name"): "FreeBuds Pro",
    ("BluetoothDeviceOverview", "right"): 78,
    ("BluetoothDeviceOverview", "rightChargingStatus"): "充电中",
    ("CountdownOverview", "days"): 28,
    ("CalendarOverview", "description"): "评审本周 UI 交付方案",
    ("CalendarOverview", "end"): "15:30",
    ("CalendarOverview", "eventCount"): 1,
    ("CalendarOverview", "location"): "深圳市龙岗区五和大道",
    ("CalendarOverview", "start"): "14:00",
    ("CalendarOverview", "startDate"): "8月19日",
    ("CalendarOverview", "title"): "UI需求评审会",
    ("CalendarOverview", "updatedAt"): "今天 09:00",
    ("HeartRateOverview", "average"): 135,
    ("HeartRateOverview", "updatedAt"): "今天 09:00",
    ("ResourceUsageOverview", "available"): "5.2 GB",
    ("ResourceUsageOverview", "total"): "12 GB",
    ("ResourceUsageOverview", "usage"): 56.7,
    ("SleepOverview", "asleep"): "23:15",
    ("SleepOverview", "duration"): "7小时1分",
    ("SleepOverview", "score"): 82,
    ("SleepOverview", "status"): "良好",
    ("SleepOverview", "wakeup"): "07:30",
    ("WeatherOverview", "airQuality"): "良",
    ("WeatherOverview", "city"): "青浦区",
    ("WeatherOverview", "coldLevel"): "低",
    ("WeatherOverview", "condition"): "多云",
    ("WeatherOverview", "humidity"): 70.0,
    ("WeatherOverview", "temperature"): "29°C",
    ("WeatherOverview", "temperatureRange"): "25° / 32°",
    ("WeatherOverview", "uvIndex"): "中等",
    ("WorkoutOverview", "duration"): "40分",
    ("WorkoutOverview", "endTime"): "19:10",
    ("WorkoutOverview", "workoutCalories"): "260 千卡",
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


def build_template_preview_cases() -> tuple[TemplatePreviewCase, ...]:
    """Expand every business Provider Template into a local A2UI preview case."""
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    definitions = [
        registry.require_template(template_id)
        for template_id in registry.provider_template_ids
        if registry.require_template(template_id).capability_id is not None
    ]
    definitions.sort(key=_definition_sort_key)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    cases: list[TemplatePreviewCase] = []
    for index, definition in enumerate(definitions, start=1):
        case_id = f"T{index:03d}"
        cases.append(_build_case(case_id, definition, profile, registry))
    return tuple(cases)


def write_template_preview_dataset(output_dir: Path) -> dict[str, Any]:
    """Write one A2UI array per template and return the generated manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = build_template_preview_cases()
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
    content = _instantiate_blueprint(
        variant.root,
        _template_parameters(definition),
        bindings,
        _preview_theme_values(definition, registry),
    )
    content = _strip_advanced_component_markers(content)
    root = _preview_root(content, content_height)
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


def _preview_theme_values(
    definition: TemplateDefinition,
    registry: CardPlanRegistry,
) -> dict[str, str]:
    compatible_themes = tuple(
        item
        for item in registry.themes.values()
        if definition.capability_id in item.supported_capability_ids
    )
    theme = next(
        (
            item
            for item in compatible_themes
            if item.fusion_ball_style is None
        ),
        None,
    )
    if theme is None:
        theme = next(iter(compatible_themes), None)
    if theme is None:
        theme = registry.require_theme("digital-wellbeing-neutral-dark")
    return registry.theme_reference_values(theme.theme_profile_id)


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
    required = definition.variants[0].parameters_schema.get("required", [])
    missing = [name for name in required if name not in parameters]
    if missing:
        raise ValueError(f"Preview asset mapping is missing: {definition.wire_id}/{missing}")
    return parameters


def _build_data_schema(definition: TemplateDefinition) -> dict[str, Any]:
    schema: dict[str, Any] = {"data": {}}
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
            "level": "正常电量",
        }
    elif "Low" in template_id:
        values = {
            "percent": 16,
            "percentText": "16%",
            "charging": "未充电",
            "level": "电量低",
        }
    else:
        values = {
            "percent": 68,
            "percentText": "68%",
            "charging": "未充电",
            "level": "正常电量",
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


def _preview_root(content: Nested2Node, content_height: int) -> Nested2Node:
    slot_options = {
        "width": "matchParent",
        "height": content_height,
        "justifyContent": "start",
        "alignItems": "start",
        "clip": True,
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    root_options = {
        "_id": "root",
        "padding": 12,
        "borderRadius": 20,
        "backgroundColor": "#FFFFFFFF",
        "justifyContent": "start",
        "alignItems": "start",
        "clip": True,
    }
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
