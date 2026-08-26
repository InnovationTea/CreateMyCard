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
    ProviderGalleryBatchRunner,
    load_gallery_input_manifest,
    write_gallery_input_dataset,
)


class _GalleryService:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: Any,
    ) -> GenerateWidgetCardResponse:
        self.requests.append(request)
        artifact = WidgetArtifact(
            genui=(
                '{"createSurface":{"surfaceId":"main","catalogId":'
                '"ohos.a2ui.extended.catalog.form"}}\n'
                '{"updateComponents":{"surfaceId":"main","components":[]}}\n'
                '{"updateDataModel":{"surfaceId":"main","path":"/","value":{}}}'
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


def _find_case(manifest: Any, business_id: str, scenario_id: str) -> Any:
    for provider in manifest.providers:
        for case in provider.cases:
            if case.businessId == business_id and case.scenarioId == scenario_id:
                return case
    raise AssertionError(f"case not found: {business_id}/{scenario_id}")


def test_gallery_inputs_cover_all_provider_business_scenarios(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    manifest = write_gallery_input_dataset(input_root)

    assert len(manifest.providers) == 8
    assert sum(len(provider.cases) for provider in manifest.providers) == 44
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
    battery_case = _find_case(manifest, "BatteryOverview", "single-two-actions")
    request = json.loads((input_root / battery_case.requestFile).read_text(encoding="utf-8"))
    binding = request["content"]["candidateDataBindings"][0]
    assert binding["candidateOutputFields"] == [
        "/batterySOC",
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batteryCapacityLevelDesc",
    ]
    assert len(request["content"]["candidateEventCandidates"]) == 2


def test_gallery_inputs_mark_missing_layout_families(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path / "inputs")

    countdown_compact = _find_case(
        manifest,
        "CountdownOverview",
        "single-two-actions",
    )
    calendar_hero = _find_case(
        manifest,
        "CalendarOverview",
        "single-one-action",
    )
    assert countdown_compact.missingReason == "缺失 Compact 模板"
    assert calendar_hero.missingReason == "缺失 Hero 模板"


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
    assert summary.success == 4
    assert summary.failed == 0
    assert len(service.requests) == 4
    assert sorted(len(request.candidateEventCandidates or []) for request in service.requests) == [
        0,
        0,
        1,
        2,
    ]
    output_manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert len(output_manifest["providers"]) == 1
    cases = output_manifest["providers"][0]["cases"]
    assert {case["status"] for case in cases} == {"success"}
    for case in cases:
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

    assert summary.total == 44
    assert summary.missing == 10
    assert summary.not_generated == 34
    assert service.requests == []
    reloaded = load_gallery_input_manifest(input_root)
    assert len(reloaded.providers) == 8
