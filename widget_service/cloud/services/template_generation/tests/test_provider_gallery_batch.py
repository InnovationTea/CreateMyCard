"""Provider 模板画廊批跑测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardResponse
from core.errors import GenerationStatus
from models.artifact import WidgetArtifact
from services.artifact_store import ArtifactStore
from services.template_generation.test_support.provider_gallery import (
    MULTI_BUSINESS_UNSUPPORTED_ERROR,
    MULTI_BUSINESS_UNSUPPORTED_REASON,
    ProviderGalleryBatchRunner,
    load_gallery_input_manifest,
    write_gallery_input_dataset,
)

_WEATHER_ASSET_IDS = [
    "asset.drop_1",
    "asset.sun_max",
    "asset.sun_min",
    "asset.icon_weather_temperature1",
    "asset.icon_weather_thermometer_medium",
    "asset.icon_weather_thermometer",
    "asset.icon_weather_wind",
]


class _GalleryService:
    def __init__(self) -> None:
        self.requests: list[Any] = []
        self.template_candidate_ids: list[tuple[str, ...]] = []
        self.template_action_ids: list[tuple[str, ...]] = []
        self.template_sample_overrides: list[dict[str, object]] = []
        self.fusion_ball_flags: list[bool] = []

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: Any,
        *,
        enable_fusion_ball: bool = False,
        trusted_template_candidate_ids: tuple[str, ...] = (),
        trusted_template_action_ids: tuple[str, ...] = (),
        trusted_template_sample_overrides: dict[str, object] | None = None,
    ) -> GenerateWidgetCardResponse:
        self.requests.append(request)
        self.fusion_ball_flags.append(enable_fusion_ball)
        self.template_candidate_ids.append(trusted_template_candidate_ids)
        self.template_action_ids.append(trusted_template_action_ids)
        self.template_sample_overrides.append(
            dict(trusted_template_sample_overrides or {})
        )
        action_count = len(request.candidateEventCandidates or [])
        components = [
            {
                "id": f"action-{index}",
                "component": "Text",
                "onClick": [{"call": "testAction", "args": {}}],
            }
            for index in range(action_count)
        ]
        artifact = WidgetArtifact(
            genui=(
                '{"createSurface":{"surfaceId":"main","catalogId":'
                '"ohos.a2ui.extended.catalog.form"}}\n'
                + json.dumps(
                    {
                        "updateComponents": {
                            "surfaceId": "main",
                            "components": components,
                        }
                    }
                )
                + "\n"
                + '{"updateDataModel":{"surfaceId":"main","path":"/","value":{}}}'
            ),
            cardSpec={"title": request.title, "suggestSize": "2x2"},
            taskSpec={"userQuery": request.userQuery, "size": "2x2"},
            effectiveCapabilities={},
            meta={
                "protocolProfileId": "a2ui-form-rom6.0-v1",
                "capabilityRegistryVersion": "test",
                "artifactId": f"gallery-test-{len(self.requests)}",
                "createdAt": 0,
            },
        )
        saved = await ArtifactStore().save(artifact)
        return GenerateWidgetCardResponse(
            status=GenerationStatus.SUCCESS,
            artifactUrl=saved.artifactUrl,
            artifactDigest=saved.artifactDigest,
            suggestSize="2x2",
            message="ok",
        )


def _find_case(
    manifest: Any,
    business_id: str,
    scenario_id: str,
    target_template_id: str | None = None,
) -> Any:
    for provider in manifest.providers:
        for case in provider.cases:
            matches_business = case.businessId == business_id
            matches_scenario = case.scenarioId == scenario_id
            matches_template = (
                target_template_id is None or case.targetTemplateId == target_template_id
            )
            if matches_business and matches_scenario and matches_template:
                return case
    raise AssertionError(
        f"case not found: {business_id}/{scenario_id}/{target_template_id or '*'}"
    )


def test_gallery_inputs_cover_all_provider_business_scenarios(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    manifest = write_gallery_input_dataset(input_root)

    assert len(manifest.providers) == 8
    assert sum(len(provider.cases) for provider in manifest.providers) == 103
    scenario_ids = {
        case.scenarioId
        for provider in manifest.providers
        for case in provider.cases
    }
    assert scenario_ids == {
        "single-two-actions",
        "two-contents",
        "single-one-action",
        "single-content",
    }
    battery_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewNormalWeatherCompact@1",
    )
    request = json.loads((input_root / battery_case.requestFile).read_text(encoding="utf-8"))
    binding = request["content"]["candidateDataBindings"][0]
    assert binding["candidateOutputFields"] == [
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc",
    ]
    assert len(request["content"]["candidateEventCandidates"]) == 2
    assert "打开电池设置" in request["content"]["userQuery"]
    assert "开启省电模式" in request["content"]["userQuery"]

    calendar_hero_case = _find_case(
        manifest,
        "CalendarOverview",
        "single-one-action",
        "ScheduleOverviewNextEventHero@1",
    )
    calendar_hero_request = json.loads(
        (input_root / calendar_hero_case.requestFile).read_text(encoding="utf-8")
    )
    assert calendar_hero_request["content"]["candidateAssetIds"] == [
        "asset.calendar_fill"
    ]
    assert calendar_hero_request["content"]["candidateDataBindings"][0][
        "candidateOutputFields"
    ] == ["/events/0/title", "/events/0/dtStart"]

    targeted_cases = []
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId:
                targeted_cases.append(case)
    assert len(targeted_cases) == 96
    battery_full_ids = {
        case.targetTemplateId
        for case in targeted_cases
        if case.businessId == "BatteryOverview" and case.scenarioId == "single-content"
    }
    assert battery_full_ids == {
        "BatteryOverviewNormalFull@1",
        "BatteryOverviewChargingFull@1",
        "BatteryOverviewLowFull@1",
    }
    battery_charging = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewChargingWeatherCompact@1",
    )
    charging_request = json.loads(
        (input_root / battery_charging.requestFile).read_text(encoding="utf-8")
    )
    assert charging_request["galleryTest"]["sampleOverrides"] == {
        "/data/phoneBattery/batterySOCText": "68%",
        "/data/phoneBattery/chargingStatusDesc": "正在充电",
        "/data/phoneBattery/batteryCapacityLevelDesc": "正常电量",
    }
    battery_low = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewLowWeatherCompact@1",
    )
    low_request = json.loads(
        (input_root / battery_low.requestFile).read_text(encoding="utf-8")
    )
    assert low_request["galleryTest"]["sampleOverrides"] == {
        "/data/phoneBattery/batterySOCText": "15%",
        "/data/phoneBattery/chargingStatusDesc": "未充电",
        "/data/phoneBattery/batteryCapacityLevelDesc": "低电量",
    }
    battery_low_full = _find_case(
        manifest,
        "BatteryOverview",
        "single-content",
        "BatteryOverviewLowFull@1",
    )
    low_full_request = json.loads(
        (input_root / battery_low_full.requestFile).read_text(encoding="utf-8")
    )
    assert low_full_request["galleryTest"]["sampleOverrides"] == {
        "/data/phoneBattery/batterySOC": 15,
        "/data/phoneBattery/batterySOCText": "15%",
        "/data/phoneBattery/chargingStatusDesc": "未充电",
        "/data/phoneBattery/batteryCapacityLevelDesc": "低电量",
    }
    weather_icon = _find_case(
        manifest,
        "WeatherOverview",
        "single-two-actions",
        "WeatherOverviewCompact@1",
    )
    weather_request = json.loads(
        (input_root / weather_icon.requestFile).read_text(encoding="utf-8")
    )
    assert weather_request["content"]["candidateAssetIds"] == _WEATHER_ASSET_IDS
    weather_temperature_icon = _find_case(
        manifest,
        "WeatherOverview",
        "single-two-actions",
        "WeatherOverviewTemperatureIconCompact@1",
    )
    weather_temperature_request = json.loads(
        (input_root / weather_temperature_icon.requestFile).read_text(encoding="utf-8")
    )
    assert (
        weather_temperature_request["content"]["candidateAssetIds"]
        == _WEATHER_ASSET_IDS
    )
    for template_id in (
        "WeatherOverviewTemperatureAlertUvIconCompact@1",
        "WeatherOverviewTemperatureUvIconCompact@1",
    ):
        weather_uv_icon = _find_case(
            manifest,
            "WeatherOverview",
            "single-two-actions",
            template_id,
        )
        weather_uv_icon_request = json.loads(
            (input_root / weather_uv_icon.requestFile).read_text(encoding="utf-8")
        )
        assert (
            weather_uv_icon_request["content"]["candidateAssetIds"]
            == _WEATHER_ASSET_IDS
        )
    battery_temperature_icon = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewNormalPowerTemperatureIconCompact@1",
    )
    battery_temperature_icon_request = json.loads(
        (input_root / battery_temperature_icon.requestFile).read_text(encoding="utf-8")
    )
    assert battery_temperature_icon_request["content"]["candidateDataBindings"][0][
        "candidateOutputFields"
    ] == ["/batterySOC", "/batteryTemperatureText"]
    battery_icon = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewTemperatureIconCompact@1",
    )
    battery_icon_request = json.loads(
        (input_root / battery_icon.requestFile).read_text(encoding="utf-8")
    )
    assert battery_icon_request["content"]["candidateDataBindings"][0][
        "candidateOutputFields"
    ] == ["/batteryTemperatureText", "/batterySOCText"]
    calendar_location_source = _find_case(
        manifest,
        "CalendarOverview",
        "single-two-actions",
        "ScheduleOverviewMeetingLocationSourceCompact@1",
    )
    calendar_location_request = json.loads(
        (input_root / calendar_location_source.requestFile).read_text(encoding="utf-8")
    )
    assert calendar_location_request["content"]["candidateAssetIds"] == [
        "asset.calendar_fill",
        "asset.clock",
        "asset.location_north_up_right_fill",
        "asset.icon_meeting",
    ]
    calendar_meeting_source = _find_case(
        manifest,
        "CalendarOverview",
        "single-two-actions",
        "ScheduleOverviewMeetingSourceCompact@1",
    )
    calendar_meeting_request = json.loads(
        (input_root / calendar_meeting_source.requestFile).read_text(encoding="utf-8")
    )
    assert calendar_meeting_request["content"]["candidateAssetIds"] == [
        "asset.calendar_fill",
        "asset.clock",
        "asset.icon_meeting",
    ]
    calendar_pair = _find_case(
        manifest,
        "CalendarOverview",
        "two-contents",
        "ScheduleOverviewMeetingLocationSourceCompact@1",
    )
    assert calendar_pair.partnerTemplateId == "WeatherOverviewCompact@1"
    weather_pair = _find_case(
        manifest,
        "WeatherOverview",
        "two-contents",
        "WeatherOverviewCompact@1",
    )
    assert not weather_pair.partnerTemplateId.startswith(("Date", "Schedule", "Bluetooth"))


def test_gallery_inputs_mark_missing_layout_families(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path / "inputs")

    countdown_compact = _find_case(
        manifest,
        "CountdownOverview",
        "single-two-actions",
    )
    assert countdown_compact.missingReason == ""
    calendar_hero_ids = set()
    for provider in manifest.providers:
        for case in provider.cases:
            is_calendar = case.businessId == "CalendarOverview"
            is_hero = case.scenarioId == "single-one-action"
            if is_calendar and is_hero:
                calendar_hero_ids.add(case.targetTemplateId)
    assert calendar_hero_ids == {
        "ScheduleOverviewDatedMeetingHero@1",
        "ScheduleOverviewNextEventHero@1",
        "ScheduleOverviewReminderHero@1",
    }
    calendar_full = _find_case(
        manifest,
        "CalendarOverview",
        "single-content",
        "DateOverviewFull@1",
    )
    assert calendar_full.missingReason == ""
    system_memory = _find_case(
        manifest,
        "ResourceUsageOverview",
        "single-content",
        "ResourceUsageOverviewFull@1",
    )
    assert system_memory.missingReason == "数据能力当前未注册"


@pytest.mark.asyncio
async def test_gallery_runner_calls_public_service_and_groups_a2ui_by_provider(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "output"
    manifest = write_gallery_input_dataset(input_root)
    app_usage_provider = next(
        provider
        for provider in manifest.providers
        if provider.providerSlug == "app-usage"
    )
    service = _GalleryService()
    runner = ProviderGalleryBatchRunner(service)

    summary = await runner.run(
        input_root,
        output_root,
        concurrency=2,
        provider_ids={app_usage_provider.providerId},
    )

    assert summary.total == 4
    assert summary.success == 3
    assert summary.failed == 1
    assert len(service.requests) == 3
    assert service.fusion_ball_flags == [False] * 3
    assert all(service.template_candidate_ids)
    assert all(isinstance(item, dict) for item in service.template_sample_overrides)
    assert sorted(len(item) for item in service.template_action_ids) == [0, 1, 2]
    assert sorted(len(request.candidateEventCandidates or []) for request in service.requests) == [
        0,
        1,
        2,
    ]
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert len(output_manifest["providers"]) == 1
    cases = output_manifest["providers"][0]["cases"]
    assert {case["status"] for case in cases} == {"failed", "success"}
    multi_business = next(case for case in cases if case["scenarioId"] == "two-contents")
    assert multi_business["errorCode"] == MULTI_BUSINESS_UNSUPPORTED_ERROR
    assert multi_business["errorMessage"] == MULTI_BUSINESS_UNSUPPORTED_REASON
    for case in cases:
        if case["status"] == "failed":
            assert case["a2uiFile"] == ""
            continue
        a2ui_path = output_root / case["a2uiFile"]
        assert a2ui_path.is_file()
        assert len(json.loads(a2ui_path.read_text(encoding="utf-8"))) == 3


@pytest.mark.asyncio
async def test_gallery_dry_run_emits_missing_and_not_generated_results(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "output"
    write_gallery_input_dataset(input_root)
    service = _GalleryService()
    runner = ProviderGalleryBatchRunner(service)

    summary = await runner.run(input_root, output_root, dry_run=True)

    assert summary.total == 103
    assert summary.failed == 32
    assert summary.missing == 21
    assert summary.not_generated == 50
    assert service.requests == []
    reloaded = load_gallery_input_manifest(input_root)
    assert len(reloaded.providers) == 8
