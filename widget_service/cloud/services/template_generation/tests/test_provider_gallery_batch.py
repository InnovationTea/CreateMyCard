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
    DEFAULT_PRD_VERSION,
    FUSION_PRD_VERSION,
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

_FUSION_CAPABILITY_IDS = {
    "GetCalendarEvents",
    "GetEarphoneInfo",
    "GetHealthAndSportSummary",
    "GetPhoneBatteryInfo",
    "ViewWeather",
}


class _GalleryService:
    def __init__(self) -> None:
        self.requests: list[Any] = []
        self.template_candidate_ids: list[tuple[str, ...]] = []
        self.template_action_ids: list[tuple[str, ...]] = []
        self.template_sample_overrides: list[dict[str, object]] = []
        self.prd_versions: list[str] = []

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: Any,
        *,
        trusted_template_candidate_ids: tuple[str, ...] = (),
        trusted_template_action_ids: tuple[str, ...] = (),
        trusted_template_sample_overrides: dict[str, object] | None = None,
    ) -> GenerateWidgetCardResponse:
        self.requests.append(request)
        self.template_candidate_ids.append(trusted_template_candidate_ids)
        self.template_action_ids.append(trusted_template_action_ids)
        self.template_sample_overrides.append(
            dict(trusted_template_sample_overrides or {})
        )
        self.prd_versions.append(request.prdVer)
        action_count = len(request.candidateEventCandidates or [])
        components = [
            {
                "id": f"action-{index}",
                "component": "Text",
                "onClick": [{"call": "testAction", "args": {}}],
            }
            for index in range(action_count)
        ]
        capability_ids = {
            binding.capabilityId for binding in request.candidateDataBindings or []
        }
        supports_fusion = bool(_FUSION_CAPABILITY_IDS.intersection(capability_ids))
        template_suffixes = {
            template_id.split("@", maxsplit=1)[0]
            for template_id in trusted_template_candidate_ids
        }
        eligible_templates = {
            template_id
            for template_id in template_suffixes
            if template_id.endswith(("Compact", "Full", "Hero"))
        }
        is_single_business = len(trusted_template_candidate_ids) == 1
        fusion_enabled = request.prdVer == FUSION_PRD_VERSION and supports_fusion
        if fusion_enabled and is_single_business and eligible_templates:
            components.append(
                {
                    "id": "fusionBallBackground",
                    "component": "Stack",
                    "children": [],
                }
            )
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
            taskSpec={
                "userQuery": request.userQuery,
                "size": "2x2",
                "eventCandidates": [],
                "dataModelSchema": {"data": {}},
                "assetCandidates": [],
            },
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


class _FailOnceGalleryService(_GalleryService):
    def __init__(self) -> None:
        super().__init__()
        self.failed_once = False

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: Any,
        *,
        trusted_template_candidate_ids: tuple[str, ...] = (),
        trusted_template_action_ids: tuple[str, ...] = (),
        trusted_template_sample_overrides: dict[str, object] | None = None,
    ) -> GenerateWidgetCardResponse:
        if not self.failed_once:
            self.failed_once = True
            self.requests.append(request)
            return GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                errorCode="A2UI_GENERATION_FAILED",
                suggestSize="2x2",
                message="transient model failure",
            )
        return await super().generate_widget_card_terse_dsl_nested2(
            request,
            trusted_template_candidate_ids=trusted_template_candidate_ids,
            trusted_template_action_ids=trusted_template_action_ids,
            trusted_template_sample_overrides=trusted_template_sample_overrides,
        )


def _find_case(
    manifest: Any,
    business_id: str,
    scenario_id: str,
    target_template_id: str | None = None,
    appearance_id: str | None = None,
) -> Any:
    for provider in manifest.providers:
        for case in provider.cases:
            matches_business = case.businessId == business_id
            matches_scenario = case.scenarioId == scenario_id
            matches_template = (
                target_template_id is None or case.targetTemplateId == target_template_id
            )
            matches_appearance = (
                appearance_id is None or case.appearanceId == appearance_id
            )
            if matches_business and matches_scenario and matches_template:
                if not matches_appearance:
                    continue
                return case
    raise AssertionError(
        f"case not found: {business_id}/{scenario_id}/{target_template_id or '*'}"
    )


def test_gallery_inputs_cover_all_provider_business_scenarios(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    stale_input = input_root / "providers" / "weather" / "stale.json"
    stale_input.parent.mkdir(parents=True)
    stale_input.write_text('{"asset":"asset.icon_weather1"}\n', encoding="utf-8")
    manifest = write_gallery_input_dataset(input_root)

    assert not stale_input.exists()
    assert len(manifest.providers) == 8
    assert sum(len(provider.cases) for provider in manifest.providers) == 108
    scenario_ids = {
        case.scenarioId
        for provider in manifest.providers
        for case in provider.cases
    }
    assert scenario_ids == {
        "single-two-actions",
        "single-one-action",
        "single-content",
    }
    battery_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewCompact@1",
    )
    request = json.loads((input_root / battery_case.requestFile).read_text(encoding="utf-8"))
    assert battery_case.appearanceId == "standard"
    assert battery_case.appearanceName == "非融球"
    assert battery_case.prdVer == DEFAULT_PRD_VERSION
    assert not battery_case.expectsFusionBall
    battery_fusion_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewCompact@1",
        "fusion",
    )
    battery_fusion_request = json.loads(
        (input_root / battery_fusion_case.requestFile).read_text(encoding="utf-8")
    )
    assert battery_fusion_case.appearanceName == "融球"
    assert battery_fusion_case.prdVer == FUSION_PRD_VERSION
    assert battery_fusion_case.expectsFusionBall
    battery_full_fusion_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-content",
        "BatteryOverviewFull@1",
        "fusion",
    )
    assert battery_full_fusion_case.expectsFusionBall
    assert request["deviceInfo"]["prdVer"] == DEFAULT_PRD_VERSION
    assert battery_fusion_request["deviceInfo"]["prdVer"] == FUSION_PRD_VERSION
    binding = request["content"]["candidateDataBindings"][0]
    assert binding["candidateOutputFields"] == [
        "/batterySOCText",
        "/batteryCapacityLevelDesc",
        "/chargingStatusDesc",
        "/batterySOC",
    ]
    assert len(request["content"]["candidateEventCandidates"]) == 2
    assert "打开电池设置" in request["content"]["userQuery"]
    assert "开启省电模式" in request["content"]["userQuery"]

    battery_health = _find_case(
        manifest,
        "BatteryOverview",
        "single-one-action",
        "BatteryOverviewHealthLevelHero@1",
    )
    battery_health_request = json.loads(
        (input_root / battery_health.requestFile).read_text(encoding="utf-8")
    )
    assert battery_health_request["content"]["candidateDataBindings"][0][
        "candidateOutputFields"
    ] == ["/healthStatusDesc", "/batteryCapacityLevelDesc"]

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
    ] == [
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    ]

    targeted_cases = []
    for provider in manifest.providers:
        for case in provider.cases:
            if case.targetTemplateId:
                targeted_cases.append(case)
    assert len(targeted_cases) == 100
    battery_full_ids = {
        case.targetTemplateId
        for case in targeted_cases
        if case.businessId == "BatteryOverview" and case.scenarioId == "single-content"
    }
    assert battery_full_ids == {
        "BatteryOverviewFull@1",
    }
    battery_charging = _find_case(
        manifest,
        "BatteryOverview",
        "single-one-action",
        "BatteryOverviewChargingProgressHero@1",
    )
    charging_request = json.loads(
        (input_root / battery_charging.requestFile).read_text(encoding="utf-8")
    )
    assert charging_request["galleryTest"]["sampleOverrides"] == {
        "/data/phoneBattery/batterySOC": 68,
        "/data/phoneBattery/chargingStatusDesc": "正在充电",
    }
    battery_compact = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewCompact@1",
    )
    compact_request = json.loads(
        (input_root / battery_compact.requestFile).read_text(encoding="utf-8")
    )
    assert compact_request["galleryTest"]["sampleOverrides"] == {}
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
    assert weather_request["galleryTest"]["sampleOverrides"] == {
        "/data/weather/current/temperatureText": "29°"
    }
    weather_uv = _find_case(
        manifest,
        "WeatherOverview",
        "single-two-actions",
        "WeatherOverviewUvCompact@1",
    )
    weather_uv_request = json.loads(
        (input_root / weather_uv.requestFile).read_text(encoding="utf-8")
    )
    assert weather_uv_request["content"]["candidateAssetIds"] == _WEATHER_ASSET_IDS
    weather_air_quality = _find_case(
        manifest,
        "WeatherOverview",
        "single-one-action",
        "WeatherOverviewAirQualityHero@1",
    )
    weather_air_quality_request = json.loads(
        (input_root / weather_air_quality.requestFile).read_text(encoding="utf-8")
    )
    assert weather_air_quality_request["galleryTest"]["sampleOverrides"] == {}
    assert all(
        "asset.icon_weather1" not in request_path.read_text(encoding="utf-8")
        for request_path in input_root.glob("providers/**/*.json")
    )
    calendar_date = _find_case(
        manifest,
        "CalendarOverview",
        "single-content",
        "ScheduleOverviewDateFull@1",
    )
    calendar_date_request = json.loads(
        (input_root / calendar_date.requestFile).read_text(encoding="utf-8")
    )
    assert calendar_date_request["content"]["candidateAssetIds"] == []
    earphone_case_status = _find_case(
        manifest,
        "BluetoothDeviceOverview",
        "single-two-actions",
        "BluetoothDeviceOverviewCaseStatusCompact@1",
    )
    earphone_case_status_request = json.loads(
        (input_root / earphone_case_status.requestFile).read_text(encoding="utf-8")
    )
    assert earphone_case_status_request["content"]["candidateAssetIds"] == [
        "asset.earphone_case_16644"
    ]


def test_gallery_inputs_mark_missing_layout_families(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path / "inputs")

    countdown_compact = _find_case(
        manifest,
        "CountdownOverview",
        "single-two-actions",
    )
    assert countdown_compact.missingReason == "缺失 Compact 模板"
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
        "ScheduleOverviewDateFull@1",
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
    countdown_provider = next(
        provider
        for provider in manifest.providers
        if provider.providerSlug == "countdown"
    )
    service = _GalleryService()
    runner = ProviderGalleryBatchRunner(service)
    stale_output = output_root / "providers" / "weather" / "stale.json"
    stale_output.parent.mkdir(parents=True)
    stale_output.write_text("{}\n", encoding="utf-8")

    summary = await runner.run(
        input_root,
        output_root,
        concurrency=2,
        provider_ids={countdown_provider.providerId},
    )

    assert not stale_output.exists()
    assert summary.total == 6
    assert summary.success == 2
    assert summary.failed == 0
    assert summary.missing == 4
    assert len(service.requests) == 2
    assert service.prd_versions.count(DEFAULT_PRD_VERSION) == 1
    assert service.prd_versions.count(FUSION_PRD_VERSION) == 1
    assert all(service.template_candidate_ids)
    assert all(isinstance(item, dict) for item in service.template_sample_overrides)
    assert sorted(len(item) for item in service.template_action_ids) == [0, 0]
    assert sorted(len(request.candidateEventCandidates or []) for request in service.requests) == [
        0,
        0,
    ]
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert len(output_manifest["providers"]) == 1
    cases = output_manifest["providers"][0]["cases"]
    assert {case["status"] for case in cases} == {"missing", "success"}
    assert {case["appearanceId"] for case in cases} == {"standard", "fusion"}
    for case in cases:
        if case["status"] != "success":
            assert case["a2uiFile"] == ""
            continue
        a2ui_path = output_root / case["a2uiFile"]
        assert a2ui_path.is_file()
        assert len(json.loads(a2ui_path.read_text(encoding="utf-8"))) == 3


@pytest.mark.asyncio
async def test_gallery_runner_generates_fusion_and_standard_in_the_same_provider(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "output"
    manifest = write_gallery_input_dataset(input_root)
    standard_case = _find_case(
        manifest,
        "WeatherOverview",
        "single-content",
        "WeatherOverviewFull@1",
        "standard",
    )
    fusion_case = _find_case(
        manifest,
        "WeatherOverview",
        "single-content",
        "WeatherOverviewFull@1",
        "fusion",
    )
    weather_provider = next(
        provider for provider in manifest.providers if provider.providerSlug == "weather"
    )
    weather_provider.cases = [standard_case, fusion_case]
    manifest.providers = [weather_provider]
    (input_root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    service = _FailOnceGalleryService()
    runner = ProviderGalleryBatchRunner(service)

    summary = await runner.run(input_root, output_root)

    assert summary.total == 2
    assert summary.success == 2
    assert len(service.requests) == 3
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert output_manifest["schemaVersion"] == "provider-template-gallery-output/2"
    cases = output_manifest["providers"][0]["cases"]
    assert [case["appearanceId"] for case in cases] == ["standard", "fusion"]
    assert [case["fusionBallRendered"] for case in cases] == [False, True]
    assert [case["appVersion"] for case in cases] == [
        DEFAULT_PRD_VERSION,
        FUSION_PRD_VERSION,
    ]
    assert [case["partnerTemplateId"] for case in cases] == ["", ""]


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

    assert summary.total == 108
    assert summary.failed == 0
    assert summary.missing == 18
    assert summary.not_generated == 90
    assert service.requests == []
    reloaded = load_gallery_input_manifest(input_root)
    assert len(reloaded.providers) == 8
