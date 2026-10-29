# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest
from pydantic import ValidationError

from api.schemas import CapabilityOverviewRequest, DataCapabilitySchemasRequest
from config.config import get_settings
from models.capability import AssetCapability
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient, IDSDeviceCapabilityState
from services.task_spec_builder import TaskSpecBuilder
from services.widget_generation_service import WidgetGenerationService

CURRENT_REGISTRY = "app-11.7.7.300_rom-7.0"


@pytest.fixture
def overview_request(monkeypatch):
    """保留实际设备过滤，只替换 IDS 安装快照，避免访问外部服务。"""
    installed = set(get_settings().ids_installation_filter_package_names)

    def installed_state(_client, _device, _request_id):
        return IDSDeviceCapabilityState(installed_apps=installed)

    monkeypatch.setattr(IDSClient, "get_device_capability_state", installed_state)
    return CapabilityOverviewRequest(
        uid="overview-test",
        prdVer="11.7.7.330",
        device={"romVersion": "7.0"},
    )


def test_overview_uses_short_assets_and_keeps_event_contract(overview_request):
    registry = CapabilityRegistry(version=CURRENT_REGISTRY)
    assets = registry.list_asset_capabilities()
    events = registry.list_event_capabilities()
    response = WidgetGenerationService().get_widget_capability_overview(overview_request)
    payload = response.model_dump(mode="json", exclude_none=True)
    asset_rows = payload.get("assetCandidates")
    event_rows = payload.get("eventCapabilities")
    assert isinstance(asset_rows, list)
    assert isinstance(event_rows, list)
    assert len(asset_rows) == len(assets)
    assert len(event_rows) == len(events)
    for row, asset in zip(asset_rows, assets, strict=True):
        assert asset.overviewDescription is not None
        assert row == {"id": asset.id, "description": asset.overviewDescription}
        assert len(asset.overviewDescription) < len(asset.description)
    for row, event in zip(event_rows, events, strict=True):
        assert set(row) == {"id", "description", "actionTemplate", "dynamicArguments"}
        assert row.get("id") == event.id
        assert row.get("description") == event.description
        assert row.get("actionTemplate") == event.actionTemplate.model_dump(mode="json")
        expected_arguments = []
        for argument in event.dynamicArguments:
            expected_arguments.append(argument.model_dump(mode="json", exclude_none=True))
        assert row.get("dynamicArguments") == expected_arguments


def test_weather_overview_preserves_description_and_schema_defines_forecast_start(overview_request):
    service = WidgetGenerationService()
    overview = service.get_widget_capability_overview(overview_request)
    weather = next(item for item in overview.dataCapabilities if item.id == "ViewWeather")
    registered = CapabilityRegistry(version=CURRENT_REGISTRY).get_data_capability("ViewWeather")
    assert registered is not None
    assert weather.description == registered.description
    request = DataCapabilitySchemasRequest(
        **overview_request.model_dump(), dataCapabilityIds=["ViewWeather"]
    )
    response = service.get_data_capability_schemas(request)
    assert not response.missingCapabilityIds
    assert len(response.dataCapabilities) == 1
    definition = response.dataCapabilities[0]
    properties = definition.inputSchema.get("properties")
    assert isinstance(properties, dict)
    forecast = properties.get("forecastDays")
    assert isinstance(forecast, dict)
    assert "不是目标日期偏移" in forecast.get("description", "")
    output = definition.outputSchema.get("properties")
    assert isinstance(output, dict)
    daily = output.get("daily")
    assert isinstance(daily, dict)
    assert "daily[0]为明天，daily[1]为后天" in daily.get("description", "")


def test_legacy_request_falls_back_to_current_asset_descriptions(monkeypatch, overview_request):
    monkeypatch.setattr(get_settings(), "enable_default_capability_registry_fallback", True)
    request = overview_request.model_copy(update={"prdVer": "11.7.5.205"})
    registry = CapabilityRegistry(version=CURRENT_REGISTRY)
    assets = registry.list_asset_capabilities()
    response = WidgetGenerationService().get_widget_capability_overview(request)
    assert len(response.assetCandidates) == len(assets)
    for overview, asset in zip(response.assetCandidates, assets, strict=True):
        assert overview.id == asset.id
        assert overview.description == (asset.overviewDescription or asset.description)


def test_overview_falls_back_for_current_assets_without_short_description(
    monkeypatch, overview_request
):
    asset = AssetCapability(id="asset.test", description="完整说明", src="resources/test.svg")
    monkeypatch.setattr(CapabilityRegistry, "list_asset_capabilities", lambda _registry: [asset])
    response = WidgetGenerationService().get_widget_capability_overview(overview_request)
    assert len(response.assetCandidates) == 1
    assert response.assetCandidates[0].description == "完整说明"
    assert asset.description == "完整说明"


def test_generation_keeps_all_full_asset_descriptions(overview_request):
    assets = CapabilityRegistry(version=CURRENT_REGISTRY).list_asset_capabilities()
    response = WidgetGenerationService().get_widget_capability_overview(overview_request)
    task = TaskSpecBuilder().build("素材回归", "2x2", [], [], [], assets)
    assert len(task.assetCandidates) == len(assets)
    for candidate, asset, overview in zip(
        task.assetCandidates, assets, response.assetCandidates, strict=True
    ):
        assert candidate == {"id": asset.id, "src": asset.src, "description": asset.description}
        assert candidate.get("description") != overview.description


@pytest.mark.parametrize("description", ["", " ", "\n\t"])
def test_blank_short_description_is_rejected(description):
    with pytest.raises(ValidationError):
        AssetCapability(
            id="asset.test",
            description="完整说明",
            src="resources/test.svg",
            overviewDescription=description,
        )


def test_short_description_preserves_selection_boundaries():
    registry = CapabilityRegistry(version=CURRENT_REGISTRY)
    restrictions = {
        "asset.emoji_heartRate": ("最近运动心率", "实时心率", "不表示当前健康状态"),
        "asset.ic_public_connection_filled": ("合法图标位", "不代表", "Wi-Fi", "蓝牙"),
        "asset.ic_purification": ("空气质量", "不代表等级"),
        "asset.ic_weatherWarning": ("气象预警", "无预警不显示"),
    }
    for asset_id, expected_phrases in restrictions.items():
        asset = registry.get_asset_capability(asset_id)
        assert asset is not None
        assert asset.overviewDescription is not None
        for phrase in expected_phrases:
            assert phrase in asset.overviewDescription


def test_short_descriptions_reduce_asset_payload_by_at_least_one_third(overview_request):
    assets = CapabilityRegistry(version=CURRENT_REGISTRY).list_asset_capabilities()
    full_rows = []
    for asset in assets:
        full_rows.append({"id": asset.id, "description": asset.description})
    response = WidgetGenerationService().get_widget_capability_overview(overview_request)
    payload = response.model_dump(mode="json", exclude_none=True)
    short_rows = payload.get("assetCandidates")
    assert isinstance(short_rows, list)
    full_chars = len(json.dumps(full_rows, ensure_ascii=False, separators=(",", ":")))
    short_chars = len(json.dumps(short_rows, ensure_ascii=False, separators=(",", ":")))
    assert short_chars < full_chars * 2 / 3
