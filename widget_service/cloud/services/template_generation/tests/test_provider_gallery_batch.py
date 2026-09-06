"""Provider 模板画廊批跑测试。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardResponse
from core.errors import GenerationStatus
from models.artifact import WidgetArtifact
from services.artifact_store import ArtifactStore
from services.template_generation.controls import TemplateControls
from services.template_generation.test_support import provider_gallery
from services.template_generation.test_support.provider_gallery import (
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
    "GetCountdownDays",
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
        single_fusion = is_single_business and bool(eligible_templates)
        paired_fusion = trusted_template_candidate_ids == (
            "WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"
        )
        eligible_fusion = single_fusion or paired_fusion
        if fusion_enabled and eligible_fusion:
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
    assert len(manifest.providers) == 10
    all_cases = [case for provider in manifest.providers for case in provider.cases]
    assert len(all_cases) == 121
    assert {case.appearanceId for case in all_cases} == {"fusion"}
    assert {case.prdVer for case in all_cases} == {FUSION_PRD_VERSION}
    for case in all_cases:
        if not case.missingReason:
            assert case.expectsFusionBall is (case.providerSlug != "two-support")
    scenario_ids = {
        case.scenarioId
        for provider in manifest.providers
        for case in provider.cases
    }
    assert scenario_ids == {
        "single-two-actions",
        "single-one-action",
        "single-content",
        "dual-one-action",
        "dual-support-content",
        "dual-support-one-action",
        "dual-support-two-actions",
    }
    battery_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-two-actions",
        "BatteryOverviewCompact@1",
    )
    request = json.loads((input_root / battery_case.requestFile).read_text(encoding="utf-8"))
    assert battery_case.appearanceId == "fusion"
    assert battery_case.appearanceName == "融球"
    assert battery_case.prdVer == FUSION_PRD_VERSION
    assert battery_case.expectsFusionBall
    battery_full_fusion_case = _find_case(
        manifest,
        "BatteryOverview",
        "single-content",
        "BatteryOverviewFull@1",
        "fusion",
    )
    assert battery_full_fusion_case.expectsFusionBall
    assert request["deviceInfo"]["prdVer"] == FUSION_PRD_VERSION
    binding = request["content"]["candidateDataBindings"][0]
    assert binding["candidateOutputFields"] == [
        "/batterySOC",
        "/chargingStatusDesc",
        "/batterySOCText",
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
    assert len(targeted_cases) == 118
    battery_full_ids = {
        case.targetTemplateId
        for case in targeted_cases
        if case.businessId == "BatteryOverview" and case.scenarioId == "single-content"
    }
    assert battery_full_ids == {
        "BatteryOverviewChargingProgressFull@1",
        "BatteryOverviewFull@1",
        "BatteryOverviewTemperatureFull@1",
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
        "/data/phoneBattery/batterySOCText": "68%",
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


def test_countdown_gallery_inputs_use_only_high_version_fusion(
    tmp_path: Path,
) -> None:
    manifest = write_gallery_input_dataset(tmp_path / "inputs")
    case = _find_case(
        manifest,
        "CountdownOverview",
        "single-content",
        "CountdownOverviewFull@1",
        "fusion",
    )

    assert case.missingReason == ""
    assert case.prdVer == FUSION_PRD_VERSION
    assert case.expectsFusionBall


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
        "ScheduleOverviewDatedAllDayHero@1",
        "ScheduleOverviewDatedMeetingHero@1",
        "ScheduleOverviewEventCountDetailsHero@1",
        "ScheduleOverviewLocationHero@1",
        "ScheduleOverviewNextEventHero@1",
        "ScheduleOverviewReminderDetailsHero@1",
        "ScheduleOverviewReminderHero@1",
        "ScheduleOverviewTitleHero@1",
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
    assert summary.total == 3
    assert summary.success == 2
    assert summary.failed == 0
    assert summary.missing == 1
    assert len(service.requests) == 2
    assert service.prd_versions.count(FUSION_PRD_VERSION) == 2
    assert all(service.template_candidate_ids)
    assert all(isinstance(item, dict) for item in service.template_sample_overrides)
    assert sorted(len(item) for item in service.template_action_ids) == [0, 1]
    assert sorted(len(request.candidateEventCandidates or []) for request in service.requests) == [
        0,
        1,
    ]
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert len(output_manifest["providers"]) == 1
    cases = output_manifest["providers"][0]["cases"]
    assert {case["status"] for case in cases} == {"missing", "success"}
    assert {case["appearanceId"] for case in cases} == {"fusion"}
    for case in cases:
        if case["status"] != "success":
            assert case["a2uiFile"] == ""
            continue
        a2ui_path = output_root / case["a2uiFile"]
        assert a2ui_path.is_file()
        assert len(json.loads(a2ui_path.read_text(encoding="utf-8"))) == 3
        assert case.get("expectsFusionBall") is True
        assert case.get("fusionBallRendered") is True


@pytest.mark.asyncio
async def test_gallery_runner_generates_only_high_version_fusion(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    output_root = tmp_path / "output"
    manifest = write_gallery_input_dataset(input_root)
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
    weather_provider.cases = [fusion_case]
    manifest.providers = [weather_provider]
    (input_root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    service = _FailOnceGalleryService()
    runner = ProviderGalleryBatchRunner(service)

    summary = await runner.run(input_root, output_root)

    assert summary.total == 1
    assert summary.success == 1
    assert len(service.requests) == 2
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert output_manifest["schemaVersion"] == "provider-template-gallery-output/2"
    cases = output_manifest["providers"][0]["cases"]
    assert [case["appearanceId"] for case in cases] == ["fusion"]
    assert [case["fusionBallRendered"] for case in cases] == [True]
    assert [case["appVersion"] for case in cases] == [FUSION_PRD_VERSION]
    assert [case["partnerTemplateId"] for case in cases] == [""]


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

    assert summary.total == 121
    assert summary.failed == 0
    assert summary.missing == 14
    assert summary.not_generated == 107
    assert service.requests == []
    reloaded = load_gallery_input_manifest(input_root)
    assert len(reloaded.providers) == 10


def test_gallery_paired_inputs_preserve_both_businesses_and_one_action(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    paired = next(item for item in manifest.providers if item.providerSlug == "cross-business")
    assert paired.providerName == "跨业务组合"
    assert len(paired.cases) == 1
    assert [case.prdVer for case in paired.cases] == [FUSION_PRD_VERSION]
    for case in paired.cases:
        assert case.targetTemplateId == "WeatherOverviewHeroTitle@1"
        assert case.partnerTemplateId == "ScheduleOverviewHeroContent@1"
        assert case.expectedLayout == "HeroTitle + HeroContent + PillAction"
        assert case.missingReason == ""
        assert case.expectsFusionBall
        assert case.appearanceName == "高版本（融球）"
        payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
        content = payload.get("content")
        assert isinstance(content, dict)
        bindings = content.get("candidateDataBindings")
        assert isinstance(bindings, list)
        assert [binding.get("capabilityId") for binding in bindings] == [
            "ViewWeather", "GetCalendarEvents"
        ]
        assert bindings[0].get("candidateOutputFields") == [
            "/location/prefectureName", "/location/districtName",
            "/current/temperatureText", "/current/condition"
        ]
        assert bindings[1].get("candidateOutputFields") == [
            "/events/0/title", "/events/0/dtStart", "/events/0/dtEnd", "/events/0/eventLocation"
        ]
        events = content.get("candidateEventCandidates")
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].get("capabilityId") == "event.viewCalendarEvent"
        query = content.get("userQuery")
        assert isinstance(query, str)
        assert "查看日程详情" in query
        assert payload.get("utterance") == {"original": query, "type": "text"}
        assert payload.get("galleryTest") == {
            "sampleOverrides": {"/data/weather/current/temperatureText": "29°"}
        }


@pytest.mark.asyncio
async def test_gallery_paired_runner_passes_ordered_templates_to_public_service(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    write_gallery_input_dataset(input_root)
    service = _GalleryService()
    summary = await ProviderGalleryBatchRunner(service).run(
        input_root, tmp_path / "output", provider_ids={"gallery.cross-business"}, concurrency=2
    )
    assert summary.total == summary.success == 1
    assert summary.failed == summary.missing == 0
    assert service.template_candidate_ids == [
        ("WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"),
    ]
    assert service.template_action_ids == [("event.viewCalendarEvent",)]
    output = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    providers = output.get("providers")
    assert isinstance(providers, list)
    cases = providers[0].get("cases")
    assert isinstance(cases, list)
    paths: set[str] = set()
    for case in cases:
        assert case.get("partnerTemplateId") == "ScheduleOverviewHeroContent@1"
        assert case.get("fusionBallRendered") is (case.get("appVersion") == FUSION_PRD_VERSION)
        path = case.get("a2uiFile")
        assert isinstance(path, str)
        assert "schedule-overview-hero-content-1" in path
        assert (summary.manifest_path.parent / path).is_file()
        paths.add(path)
    assert len(paths) == 1


@pytest.mark.parametrize("disabled_template", [
    "WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"
])
@pytest.mark.asyncio
async def test_gallery_disabled_pair_member_never_calls_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, disabled_template: str
) -> None:
    controls = TemplateControls(
        schemaVersion="template-controls/1", disabledTemplateIds=[disabled_template]
    )
    monkeypatch.setattr(provider_gallery, "load_template_controls", lambda: controls)
    manifest = write_gallery_input_dataset(tmp_path / "inputs")
    paired = next(item for item in manifest.providers if item.providerSlug == "cross-business")
    assert all(disabled_template in case.missingReason for case in paired.cases)
    service = _GalleryService()
    summary = await ProviderGalleryBatchRunner(service).run(
        tmp_path / "inputs", tmp_path / "output", provider_ids={paired.providerId}
    )
    assert summary.total == summary.missing == 1
    assert service.requests == []


@pytest.mark.parametrize("conflict", ["same-capability", "same-root", "nested-root"])
def test_gallery_pairs_reject_overlapping_business_data(conflict: str) -> None:
    definitions = provider_gallery._load_business_definitions(provider_gallery._PROVIDER_ROOT)
    original = provider_gallery._gallery_template_pairs(definitions)
    assert len(original) == 1
    pair = original[0]
    content = pair.content.business
    if conflict == "same-capability":
        content = replace(content, capability_id=pair.title.business.capability_id)
    elif conflict == "same-root":
        content = replace(content, data_domain=pair.title.business.data_domain)
    else:
        content = replace(content, data_domain=pair.title.business.data_domain + "/nested")
    assert provider_gallery._gallery_template_pairs([pair.title.business, content]) == []


def test_support_inputs_cover_every_template_and_three_action_counts(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    provider = next(item for item in manifest.providers if item.providerSlug == "two-support")
    definitions = provider_gallery._load_business_definitions(provider_gallery._PROVIDER_ROOT)
    expected_templates: set[str] = set()
    for definition in definitions:
        for template in definition.templates:
            if template.suffix == "Support":
                expected_templates.add(template.template_id)
    assert {case.targetTemplateId for case in provider.cases} == expected_templates
    assert len(provider.cases) == len(expected_templates) * 3 == 51
    assert len({case.caseId for case in provider.cases}) == 51
    for case in provider.cases:
        assert not case.expectsFusionBall
        assert case.expectedLayout == "TwoSupportLayout"
        payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
        content = payload.get("content")
        assert isinstance(content, dict)
        bindings = content.get("candidateDataBindings")
        assert isinstance(bindings, list)
        assert len(bindings) == 2
        assert bindings[0].get("capabilityId") != bindings[1].get("capabilityId")
        assert bindings[0].get("writeResultTo") != bindings[1].get("writeResultTo")
        events = content.get("candidateEventCandidates")
        assert isinstance(events, list)
        assert len(events) == provider_gallery._expected_action_count(case.scenarioId)
        assert len({event.get("capabilityId") for event in events}) == len(events)


@pytest.mark.asyncio
async def test_support_runner_preserves_targets_actions_and_missing_members(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    write_gallery_input_dataset(input_root)
    service = _GalleryService()
    summary = await ProviderGalleryBatchRunner(service).run(
        input_root, tmp_path / "output", provider_ids={"gallery.two-support"}, concurrency=2,
    )
    assert summary.total == 51
    assert summary.success == 45
    assert summary.missing == 6
    assert summary.failed == summary.not_generated == 0
    assert len(service.requests) == 45
    assert {len(actions) for actions in service.template_action_ids} == {0, 1, 2}
    for template_ids in service.template_candidate_ids:
        assert len(template_ids) == 2
        assert all(template_id.endswith("Support@1") for template_id in template_ids)
    output = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    providers = output.get("providers")
    assert isinstance(providers, list)
    cases = providers[0].get("cases")
    assert isinstance(cases, list)
    for case in cases:
        if case.get("status") != "success":
            continue
        assert case.get("fusionBallRendered") is False
        path = case.get("a2uiFile")
        assert isinstance(path, str)
        assert (summary.manifest_path.parent / path).is_file()
