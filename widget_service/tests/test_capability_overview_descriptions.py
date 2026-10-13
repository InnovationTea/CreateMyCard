# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest
from pydantic import ValidationError

from api.schemas import CapabilityOverviewRequest
from config.config import get_settings
from models.capability import AssetCapability
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient, IDSDeviceCapabilityState
from services.task_spec_builder import TaskSpecBuilder
from services.widget_generation_service import WidgetGenerationService

LEGACY_REGISTRY = "app-11.7.5.205_rom-6.0"
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


def test_legacy_overview_keeps_full_asset_descriptions(overview_request):
    request = overview_request.model_copy(update={"prdVer": "11.7.5.205"})
    registry = CapabilityRegistry(version=LEGACY_REGISTRY)
    assets = registry.list_asset_capabilities()
    response = WidgetGenerationService().get_widget_capability_overview(request)
    assert len(response.assetCandidates) == len(assets)
    for overview, asset in zip(response.assetCandidates, assets, strict=True):
        assert asset.overviewDescription is None
        assert overview.id == asset.id
        assert overview.description == asset.description


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
        "asset.emoji_activity": ("生日", "不用于运动", "普通会议"),
        "asset.emoji_clean": ("家居清扫", "不用于内存清理"),
        "asset.emoji_mobileNetwork": ("Wi-Fi", "蓝牙", "不支持流量网速"),
        "asset.emoji_note": ("静态待办", "不支持备忘读取"),
        "asset.emoji_heartRate": ("最近运动心率", "2x2 单业务标题主题图", "实时心率"),
        "asset.ic_public_connection_filled": ("标题主题图或正文辅助", "不代表连接成功"),
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
