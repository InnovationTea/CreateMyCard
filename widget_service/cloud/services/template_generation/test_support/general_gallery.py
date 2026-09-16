"""为通用模板构造独立端到端画廊，保持正式 Search 的专用候选优先规则。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from services.template_generation.engine.cardplan.general_semantics import (
    field_presentation,
    general_field_is_allowed,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.tools.audit_general_template_coverage import schema_leaves

GENERAL_PROVIDER_ID = "gallery.general-templates"
GENERAL_PROVIDER_NAME = "通用模板"
_SLUG = "general-templates"
_KINDS = {"number": "数值", "text": "文字", "pair": "双值"}
_SCENARIOS = {
    "Full": "single-content", "Hero": "single-one-action",
    "Compact": "single-two-actions", "Support": "dual-support-content",
}
_BUSINESS_ICONS = {
    "BatteryOverview": "asset.battery_leaf_fill",
    "CalendarOverview": "asset.calendar_fill",
    "CountdownOverview": "asset.icon_timing",
    "BluetoothDeviceOverview": "asset.icon_earphone",
    "ActivityOverview": "asset.figure_run",
    "WorkoutOverview": "asset.figure_run",
    "HeartRateOverview": "asset.heart_fill",
    "SleepOverview": "asset.moon_z_fill_1",
    "WeatherOverview": "asset.icon_weather_thermometer",
}
# 每个业务自己的主指标；文字族允许把数值组成带名称的自然语言说明。
_MAIN_FIELDS = {
    "WeatherOverview": ("/current/humidityPercent", "/current/coldLevel"),
    "AppUsageOverview": ("/appUsage/durationText", "/appUsage/durationText"),
    "BatteryOverview": ("/voltageText", "/healthStatusDesc"),
    "CalendarOverview": ("/events/0/countdownDays", "/events/0/description"),
    "CountdownOverview": ("/countdownDays", "/countdownDays"),
    "BluetoothDeviceOverview": ("/leftBatteryLevel", "/leftChargingStatusDesc"),
    "ActivityOverview": ("/dailySteps", "/dailyTotalCaloriesText"),
    "WorkoutOverview": ("/exerciseDurationText", "/exerciseTypeName"),
    "HeartRateOverview": ("/exerciseHeartRateAvg", "/exerciseTypeName"),
    "SleepOverview": ("/sleepScore", "/sleepTypeDesc"),
    "ResourceUsageOverview": ("/usagePercent", "/availableMemText"),
}


@dataclass(frozen=True)
class GeneralGalleryContext:
    registry: CardPlanRegistry
    businesses: dict[str, gallery.BusinessDefinition]
    events: dict[str, dict[str, Any]]
    assets: dict[str, dict[str, Any]]
    capability_ids: set[str]
    fusion_businesses: set[str]


def _display_fields(definition: TemplateDefinition) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    for pattern, field in schema_leaves(definition.data_source_schema):
        path = pattern.replace("*", "0")
        if general_field_is_allowed(definition, path):
            fields[path] = field
    return fields


def select_general_fields(
    definition: TemplateDefinition, registry: CardPlanRegistry,
) -> tuple[tuple[str, ...], str]:
    """寻找最多四个展示字段的真实兜底组合；无法触发时明确保留不可用原因。"""
    preferred = _MAIN_FIELDS.get(definition.business_id or "")
    if preferred is None:
        raise ValueError(f"通用画廊缺少业务主指标配置：{definition.business_id}")
    fields = _display_fields(definition)
    primary = preferred[0] if definition.general_content_kind == "number" else preferred[1]
    if primary not in fields:
        raise ValueError(f"通用画廊主指标未声明：{definition.wire_id}/{primary}")
    records = []
    for record in registry.template_variant_search_records:
        if record.business_id != definition.business_id or record.fallback_only:
            continue
        if "2x2" not in record.supported_card_sizes or record.binding_count != 1:
            continue
        if registry.template_is_enabled(record.template_id):
            records.append(record)
    others = [path for path in fields if path != primary]
    # 优先业务数据，再补名称、日期等上下文，避免所有卡片都只展示更新时间。
    others.sort(key=lambda path: field_presentation(path, fields.get(path, {})) == "context")
    minimum = 1 if definition.general_content_kind == "pair" else 0
    for extra_count in range(minimum, min(3, len(others)) + 1):
        for extra in combinations(others, extra_count):
            selected = (primary, *extra)
            if not any(set(selected).issubset(record.available_paths) for record in records):
                return selected, ""
    selected = (primary, *others[:3])
    return selected, "当前字段组合均有专用模板候选，按专用优先规则不可选择通用模板"


def _selection(
    definition: TemplateDefinition, context: GeneralGalleryContext,
) -> tuple[gallery.GalleryTemplateSelection, str]:
    business = context.businesses.get(definition.business_id or "")
    if business is None:
        raise ValueError(f"通用画廊缺少业务定义：{definition.business_id}")
    fields, reason = select_general_fields(definition, context.registry)
    if definition.capability_id not in context.capability_ids:
        reason = "数据能力当前未注册"
    if not context.registry.template_is_enabled(definition.wire_id):
        reason = "业务或模板当前已禁用"
    kind = _KINDS.get(definition.general_content_kind or "")
    if kind is None:
        raise ValueError("通用画廊模板缺少内容族")
    template = gallery.ProviderTemplateDefinition(
        template_id=definition.wire_id,
        description=f"{business.business_name} · {kind}概览",
        suffix=gallery._template_suffix(definition.wire_id),
        fields=fields,
        supported_event_ids=definition.supported_event_ids,
    )
    return gallery.GalleryTemplateSelection(business, template), reason


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"通用画廊请求缺少对象：{key}")
    return value


def _configure_request(
    payload: dict[str, Any],
    selections: tuple[gallery.GalleryTemplateSelection, ...],
    context: GeneralGalleryContext,
) -> None:
    content = _object(payload, "content")
    bindings = content.get("candidateDataBindings")
    if not isinstance(bindings, list) or len(bindings) != len(selections):
        raise ValueError("通用画廊数据绑定与模板数量不一致")
    descriptions: list[str] = []
    samples: dict[str, Any] = {}
    assets = list(content.get("candidateAssetIds", []))
    for selection, binding in zip(selections, bindings, strict=True):
        if not isinstance(binding, dict):
            raise ValueError("通用画廊数据绑定必须是对象")
        definition = context.registry.require_template(selection.template.template_id)
        icon = _BUSINESS_ICONS.get(definition.business_id or "")
        if icon in context.assets and icon not in assets:
            assets.append(icon)
        fields = selection.template.fields
        binding["candidateOutputFields"] = list(fields)
        descriptions.append(
            f"{selection.business.business_name}必须显示全部字段 {', '.join(fields)}；"
            f"主指标为 {fields[0]}，其它字段放在标题或辅助信息中"
        )
        for path, field in _display_fields(definition).items():
            if path in fields and "sampleValue" in field:
                samples[selection.business.data_domain + path] = field.get("sampleValue")
    query = content.get("userQuery")
    if not isinstance(query, str):
        raise ValueError("通用画廊缺少需求文本")
    query += "。".join(descriptions) + "。所有字段随数据刷新，数值保留单位。"
    content.update(
        userQuery=query, title=selections[0].business.business_name,
        description="演示数据端到端验证",
        candidateAssetIds=assets,
    )
    payload["utterance"] = {"original": query, "type": "text"}
    payload["galleryTest"] = {"sampleOverrides": samples}


def _case(
    definition: TemplateDefinition, context: GeneralGalleryContext, input_root: Path,
) -> gallery.GalleryInputCase:
    selection, missing = _selection(definition, context)
    suffix = selection.template.suffix
    scenario = _SCENARIOS.get(suffix)
    if scenario is None:
        raise ValueError(f"通用画廊不支持布局：{suffix}")
    appearance = gallery._GALLERY_APPEARANCES[0]
    partner_id = ""
    selections = (selection,)
    if suffix == "Support":
        partner_business = (
            "BatteryOverview" if definition.business_id == "WeatherOverview" else "WeatherOverview"
        )
        partner_id = partner_business + "GeneralTextSupport@1"
        partner, partner_missing = _selection(
            context.registry.require_template(partner_id), context,
        )
        missing = missing or partner_missing
        selections = (selection, partner)
        pair = gallery.GalleryTemplatePair(title=selection, content=partner)
        payload = gallery._support_request_envelope(
            pair, scenario, appearance, context.events, context.assets,
        )
    else:
        payload = gallery._request_envelope(
            selection.business, selection.template, scenario, appearance,
            context.events, context.assets,
        )
    _configure_request(payload, selections, context)
    slug = gallery._kebab_case(definition.wire_id)
    relative = f"providers/{_SLUG}/{slug}.json"
    path = input_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scenario_name, layout, _expected_suffix = gallery._scenario_metadata(scenario)
    fusion = gallery._expects_fusion_ball(
        selection.business, selection.template, appearance, context.fusion_businesses,
    )
    return gallery.GalleryInputCase(
        caseId="general__" + slug,
        providerId=GENERAL_PROVIDER_ID, providerName=GENERAL_PROVIDER_NAME, providerSlug=_SLUG,
        businessId=selection.business.business_id, businessName=selection.template.description,
        scenarioId=scenario, scenarioName="高版本 · " + scenario_name,
        appearanceId=appearance.appearance_id,
        appearanceName="融球" if fusion else "高版本（非融球）",
        prdVer=appearance.prd_ver, expectsFusionBall=fusion,
        expectedLayout=layout, expectedTemplateSuffix=suffix,
        targetTemplateId=definition.wire_id, targetTemplateDescription=definition.description,
        partnerTemplateId=partner_id, requestFile=relative, missingReason=missing,
    )


def append_general_templates(input_root: Path) -> gallery.GalleryInputManifest:
    """重复生成只替换通用分组；不可用模板保留记录，不修改生产管控配置。"""
    manifest = gallery.load_gallery_input_manifest(input_root)
    controls = gallery.load_template_controls()
    registry = CardPlanRegistry(
        disabled_provider_ids=controls.disabled_provider_ids,
        disabled_template_ids=controls.disabled_template_ids,
        enable_fusion_ball=True,
    )
    businesses = {}
    for business in gallery._load_business_definitions(gallery._PROVIDER_ROOT):
        businesses[business.business_id] = business
    context = GeneralGalleryContext(
        registry=registry, businesses=businesses,
        events=gallery._load_event_capabilities(gallery._CAPABILITY_ROOT),
        assets=gallery._load_asset_capabilities(gallery._CAPABILITY_ROOT),
        capability_ids=gallery._load_data_capability_ids(gallery._CAPABILITY_ROOT),
        fusion_businesses=gallery._load_fusion_business_ids(gallery._THEME_ROOT),
    )
    cases = []
    for definition in registry.templates.values():
        if definition.fallback_only:
            cases.append(_case(definition, context, input_root))
    manifest.providers = [
        provider for provider in manifest.providers if provider.providerId != GENERAL_PROVIDER_ID
    ]
    manifest.providers.append(gallery.GalleryInputProvider(
        providerId=GENERAL_PROVIDER_ID, providerName=GENERAL_PROVIDER_NAME,
        providerSlug=_SLUG, cases=cases,
    ))
    (input_root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8",
    )
    return manifest
