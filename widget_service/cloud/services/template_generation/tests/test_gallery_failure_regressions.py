"""2026-10 画廊失败的输入与最小字段回归。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from models.generation import TaskSpec
from services.capability_registry import CapabilityRegistry
from services.template_generation.engine.advanced.content_selectors import (
    project_content_component_facts,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    _ACTION_QUERY,
    _NEGATIVE_ACTION,
)
from services.template_generation.engine.cardplan.compiler import (
    _validate_provider_template_state,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    template_required_assets_are_available,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.test_support.gallery_case_contracts import (
    REQUIRED_ASSET_IDS,
    THREE_DAY_COUNTDOWN_TEMPLATE,
    THREE_DAY_LAYOUT,
    THREE_DAY_WEATHER_TEMPLATE,
    gallery_display_description,
)
from services.template_generation.test_support.provider_gallery import (
    _CAPABILITY_ROOT,
    _PROVIDER_ROOT,
    DEFAULT_ROM_VERSION,
    FUSION_PRD_VERSION,
    _candidate_asset_ids,
    _load_asset_capabilities,
    _load_business_definitions,
    write_gallery_input_dataset,
)


@pytest.mark.parametrize(("query", "has_action"), [
    ("无按钮", False), ("不显示操作按钮", False), ("无需任何操作按钮", False),
    ("无按钮，但点击打开日历", True), ("不要按钮，但点按查看详情", True),
    ("显示按钮", True), ("无法打开日历，需要按钮", True),
])
def test_calendar_negative_action_consumes_complete_phrase(
    query: str, has_action: bool,
) -> None:
    assert bool(_ACTION_QUERY.search(_NEGATIVE_ACTION.sub("", query))) is has_action


@pytest.mark.parametrize("score", [0, 82, 100])
def test_score_only_projection_preserves_field(score: int) -> None:
    field = {"type": "integer", "sampleValue": score, "description": "睡眠分数"}
    task = TaskSpec(
        userQuery="只展示睡眠分数", size="2x2",
        dataModelSchema={"data": {"healthSport": {"sleepScore": field}}},
    )
    before = deepcopy(task.dataModelSchema)
    projected = project_content_component_facts(
        task, {"GetHealthAndSportSummary"}, ("SleepOverview",),
    )
    assert projected.dataModelSchema == {"data": {"SleepOverview": {"sleepScore": field}}}
    assert task.dataModelSchema == before


@pytest.mark.parametrize(("data_type", "sample"), [
    ("string", "82"), ("integer", True), ("integer", -1), ("integer", 101),
])
def test_score_only_invalid_field_still_rejects(data_type: str, sample: object) -> None:
    task = TaskSpec(
        userQuery="睡眠分数", size="2x2", dataModelSchema={"data": {"healthSport": {
            "sleepScore": {"type": data_type, "sampleValue": sample},
        }}},
    )
    with pytest.raises(ValueError, match="no renderable provider facts"):
        project_content_component_facts(task, {"GetHealthAndSportSummary"}, ("SleepOverview",))


@pytest.mark.parametrize("reminder", ["0", "15"])
def test_reminder_only_projection_preserves_field(reminder: str) -> None:
    field = {"type": "string", "sampleValue": reminder, "description": "提前提醒分钟数"}
    task = TaskSpec(
        userQuery="只展示提前提醒", size="2x2",
        dataModelSchema={"data": {"calendar": {"events": [{"remindTime": [field]}]}}},
    )
    projected = project_content_component_facts(task, {"GetCalendarEvents"}, ("CalendarOverview",))
    assert projected.dataModelSchema == {"data": {"CalendarOverview": {"remindTime": field}}}


def test_gallery_versions_select_weather_numeric_contract() -> None:
    registry = CapabilityRegistry(
        app_version=FUSION_PRD_VERSION, device_rom_version=DEFAULT_ROM_VERSION,
    )
    assert registry.version == "app-11.7.7.300_rom-7.0"


@pytest.mark.parametrize("template_id", REQUIRED_ASSET_IDS)
def test_required_gallery_assets_are_registered_and_semantic(template_id: str) -> None:
    registry = CapabilityRegistry(
        app_version=FUSION_PRD_VERSION, device_rom_version=DEFAULT_ROM_VERSION,
    )
    assets_by_id = {asset.id: asset for asset in registry.list_asset_capabilities()}
    ids = REQUIRED_ASSET_IDS.get(template_id)
    assert ids is not None
    candidates = []
    for asset_id in ids:
        asset = assets_by_id.get(asset_id)
        assert asset is not None
        candidates.append({"id": asset.id, "src": asset.src, "description": asset.description})
    task = TaskSpec(
        userQuery="素材回归", size="2x2", dataModelSchema={}, assetCandidates=candidates,
    )
    assert template_required_assets_are_available(
        CardPlanRegistry().require_template(template_id), task,
    )


@pytest.mark.parametrize("template_id", [
    "BatteryOverviewSupportHero@1", "BatteryOverviewChargeStatusHero@1",
])
@pytest.mark.parametrize("version", ["app-11.7.5.205_rom-6.0", "app-11.7.7.300_rom-7.0"])
def test_battery_leaf_replaces_missing_phone_icon(template_id: str, version: str) -> None:
    assets = _load_asset_capabilities(_CAPABILITY_ROOT.parent / version)
    assert "asset.icon_phone" not in assets
    templates = {}
    for business in _load_business_definitions(_PROVIDER_ROOT):
        for template in business.templates:
            templates[template.template_id] = template
    template = templates.get(template_id)
    assert template is not None
    assert _candidate_asset_ids(template, assets) == ["asset.battery_leaf_fill"]
    candidates = []
    for asset_id in _candidate_asset_ids(template, assets):
        asset = assets.get(asset_id)
        assert asset is not None
        candidates.append(asset)
    task = TaskSpec(
        userQuery="展示手机电量", size="2x2", dataModelSchema={}, assetCandidates=candidates,
    )
    assert template_required_assets_are_available(
        CardPlanRegistry().require_template(template_id), task,
    )


@pytest.mark.parametrize("template_id", [
    "BatteryOverviewSupportHero@1", "BatteryOverviewChargeStatusHero@1",
])
@pytest.mark.parametrize("asset_id", ["asset.phone_fill", "asset.ic_phone", "asset.emoji_phone1"])
def test_battery_leaf_contract_rejects_phone_call_icons(template_id: str, asset_id: str) -> None:
    assets = _load_asset_capabilities(_CAPABILITY_ROOT.parent / "app-11.7.7.300_rom-7.0")
    asset = assets.get(asset_id)
    assert asset is not None
    task = TaskSpec(
        userQuery="展示手机电量", size="2x2", dataModelSchema={}, assetCandidates=[asset],
    )
    assert not template_required_assets_are_available(
        CardPlanRegistry().require_template(template_id), task,
    )


def test_three_day_gallery_uses_complete_wide_composition(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    assert manifest.cardSize == "mixed"
    found = []
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId == THREE_DAY_WEATHER_TEMPLATE:
                found.append(case)
    assert len(found) == 1
    case = found[0]
    assert case.cardSize == "2x4"
    assert case.partnerTemplateId == THREE_DAY_COUNTDOWN_TEMPLATE
    assert case.expectedLayout == THREE_DAY_LAYOUT
    request = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
    content = request.get("content")
    assert isinstance(content, dict)
    assert content.get("size") == "2x4"
    bindings = content.get("candidateDataBindings")
    assert isinstance(bindings, list)
    assert {binding.get("capabilityId") for binding in bindings} == {
        "ViewWeather", "GetCountdownDays",
    }
    weather_bindings = [
        binding for binding in bindings if binding.get("capabilityId") == "ViewWeather"
    ]
    assert len(weather_bindings) == 1
    arguments = weather_bindings[0].get("arguments")
    assert isinstance(arguments, dict)
    assert arguments.get("forecastDays") == 3


def test_gallery_description_removes_implementation_notes() -> None:
    result = gallery_display_description(
        "展示总数及首项备注，不代表逐条展示所有日程，无按钮。仅用于旧匹配失败后的兜底。"
    )
    assert result == "展示总数及首项备注，仅展示首项日程摘要，无按钮。"


@pytest.mark.parametrize("template_id", [
    "BluetoothDeviceOverviewEarbudsPhoneWideFull@1",
    "BluetoothDeviceOverviewCompletePhoneWideFull@1",
])
@pytest.mark.parametrize("paired", [False, True])
def test_canonical_earphone_wide_accepts_declared_businesses(
    template_id: str, paired: bool,
) -> None:
    task = _earphone_wide_task()
    businesses = {"BluetoothDeviceOverview"}
    if paired:
        businesses.add("BatteryOverview")
    _validate_provider_template_state(template_id, "default", task, business_names=businesses)


@pytest.mark.parametrize(("template_id", "variant", "businesses", "size"), [
    ("BluetoothDeviceOverview@1", "earbudsPhoneWideFull", {"BluetoothDeviceOverview"}, "2x4"),
    ("BluetoothDeviceOverview@1", "completePhoneWideFull", {"BluetoothDeviceOverview"}, "2x4"),
    (
        "BluetoothDeviceOverviewEarbudsPhoneWideFull@1", "default",
        {"BluetoothDeviceOverview"}, "2x2",
    ),
    (
        "BluetoothDeviceOverviewCompletePhoneWideFull@1", "default",
        {"BluetoothDeviceOverview"}, "2x2",
    ),
    (
        "BluetoothDeviceOverviewEarbudsPhoneWideFull@1", "default",
        {"BluetoothDeviceOverview", "WeatherOverview"}, "2x4",
    ),
    (
        "BluetoothDeviceOverviewCompleteWideFull@1", "default",
        {"BluetoothDeviceOverview", "BatteryOverview"}, "2x4",
    ),
])
def test_earphone_wide_preserves_invalid_combination_rejection(
    template_id: str, variant: str, businesses: set[str], size: str,
) -> None:
    task = _earphone_wide_task().model_copy(update={"size": size})
    with pytest.raises(TerselConversionError, match="phone-earphone layout"):
        _validate_provider_template_state(template_id, variant, task, business_names=businesses)


def _earphone_wide_task() -> TaskSpec:
    return TaskSpec(
        userQuery="展示耳机连接和电量", size="2x4", dataModelSchema={"data": {"earphone": {
            "isConnected": {"type": "boolean", "sampleValue": False},
            "earphoneName": {"type": "string", "sampleValue": "FreeBuds"},
            "batteryLevel": {"type": "integer", "sampleValue": 0},
            "leftBatteryLevel": {"type": "integer", "sampleValue": 0},
            "rightBatteryLevel": {"type": "integer", "sampleValue": 80},
        }}},
    )
