"""画廊补充上下文通过正式数据提取和素材准入，且不修改线上最小输入契约。"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from models.capability import AssetCapability, DataCapability
from models.generation import TaskSpec
from services.task_spec_builder import TaskSpecBuilder
from services.template_generation.engine.advanced.content_selectors import (
    apply_content_selectors,
    project_content_component_facts,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    template_required_assets_are_available,
)
from services.template_generation.engine.pipeline import _with_trusted_sample_overrides
from services.template_generation.test_support import provider_gallery as gallery


@dataclass(frozen=True)
class GalleryContext:
    case: gallery.GalleryInputCase
    request: GenerateWidgetCardRequest
    task: TaskSpec
    overrides: dict[str, Any]


@pytest.fixture(scope="module")
def contexts(tmp_path_factory: pytest.TempPathFactory) -> list[GalleryContext]:
    root = tmp_path_factory.mktemp("gallery-context")
    manifest = gallery.write_gallery_input_dataset(
        root, card_sizes=("2x2", "2x4"), appearances=("fusion", "plain"),
    )
    data_path = gallery._CAPABILITY_ROOT / "data_capabilities.json"
    data = [DataCapability.model_validate(item) for item in json.loads(data_path.read_text())]
    asset_path = gallery._CAPABILITY_ROOT / "asset_capabilities.json"
    assets = [AssetCapability.model_validate(item) for item in json.loads(asset_path.read_text())]
    results: list[GalleryContext] = []
    for provider in manifest.providers:
        for case in provider.cases:
            payload = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
            request = gallery._request_from_envelope(payload)
            selected_assets = []
            for asset in assets:
                if asset.id in (request.candidateAssetIds or []):
                    selected_assets.append(asset)
            task = TaskSpecBuilder().build(
                request.userQuery, request.size, request.candidateDataBindings or [],
                data, [], selected_assets, app_version=case.prdVer,
            )
            overrides = gallery._gallery_sample_overrides_from_envelope(payload)
            results.append(GalleryContext(case, request, task, overrides))
    return results


@pytest.mark.parametrize("appearance", ["fusion", "plain"])
@pytest.mark.parametrize(
    ("template_id", "display_field", "context_fields"),
    [
        (
            "ScheduleOverviewReminderCompact@1", "/events/0/remindTime/0",
            ("/events/0/title", "/events/0/dtStart"),
        ),
        ("SleepOverviewScoreCompact@1", "/sleepScore", ("/nightSleepDurationText",)),
    ],
)
def test_runtime_context_unblocks_existing_projection(
    contexts: list[GalleryContext], appearance: str, template_id: str,
    display_field: str, context_fields: tuple[str, ...],
) -> None:
    context = next(
        item for item in contexts
        if (item.case.targetTemplateId, item.case.appearanceId) == (template_id, appearance)
    )
    bindings = context.request.candidateDataBindings
    assert bindings is not None and len(bindings) == 1
    fields = bindings[0].candidateOutputFields
    assert display_field in fields
    assert set(context_fields).issubset(fields)
    assert len(fields) == len(set(fields))
    original = deepcopy(context.task.dataModelSchema)
    capabilities = {bindings[0].capabilityId}
    selected = apply_content_selectors(context.task, capabilities)
    projected = project_content_component_facts(
        selected, capabilities, (context.case.businessId,),
    )
    assert projected.dataModelSchema
    assert context.task.dataModelSchema == original
    assert context.case.expectedLayout == "Compact + 2 × PillAction"
    assert len(context.request.candidateEventCandidates or []) == 2


@pytest.mark.parametrize("appearance", ["fusion", "plain"])
@pytest.mark.parametrize(
    ("template_id", "asset_id"),
    [
        ("BluetoothDeviceOverviewMusicCompact@1", "asset.music_fill"),
        ("BluetoothDeviceOverviewCaseConnectionHero@1", "asset.earphone_case_16644"),
        ("WeatherOverviewFeelsLikeWindSupport@1", "asset.icon_weather_thermometer"),
    ],
)
def test_required_assets_pass_formal_template_admission(
    contexts: list[GalleryContext], appearance: str, template_id: str, asset_id: str,
) -> None:
    context = next(
        item for item in contexts
        if (item.case.targetTemplateId, item.case.appearanceId) == (template_id, appearance)
    )
    assert asset_id in (context.request.candidateAssetIds or [])
    definition = get_cardplan_registry().require_template(template_id)
    assert template_required_assets_are_available(definition, context.task)
    without_assets = context.task.model_copy(update={"assetCandidates": []})
    assert not template_required_assets_are_available(definition, without_assets)


@pytest.mark.parametrize("appearance", ["fusion", "plain"])
@pytest.mark.parametrize("scenario", ["dual-support-content", "dual-support-one-action"])
@pytest.mark.parametrize(
    ("template_id", "expected_overrides"),
    [
        (
            "WeatherOverviewDaily2TravelSupport@1",
            {"/data/weather/daily/2/condition": "多云"},
        ),
        ("WeatherOverviewFeelsLikeWindSupport@1", {}),
    ],
)
def test_support_weather_overrides_only_existing_fields(
    contexts: list[GalleryContext], appearance: str, scenario: str,
    template_id: str, expected_overrides: dict[str, str],
) -> None:
    for context in contexts:
        identity = (
            context.case.targetTemplateId, context.case.appearanceId, context.case.scenarioId,
        )
        if identity == (template_id, appearance, scenario):
            break
    else:
        pytest.fail("未生成指定天气组合用例")
    assert context.overrides == expected_overrides
    original = deepcopy(context.task.dataModelSchema)
    selected = _with_trusted_sample_overrides(context.task, context.overrides)
    assert selected.dataModelSchema
    assert context.task.dataModelSchema == original


def test_all_gallery_overrides_resolve_without_creating_fields(
    contexts: list[GalleryContext],
) -> None:
    assert len(contexts) == 424
    for context in contexts:
        original = deepcopy(context.task.dataModelSchema)
        selected = _with_trusted_sample_overrides(context.task, context.overrides)
        assert selected.dataModelSchema
        assert context.task.dataModelSchema == original


def test_travel_support_preserves_current_weather_sample(contexts: list[GalleryContext]) -> None:
    cases = []
    for context in contexts:
        if context.case.targetTemplateId == "WeatherOverviewTravelSupport@1":
            cases.append(context)
    assert len(cases) == 6
    for context in cases:
        assert context.overrides == {"/data/weather/current/condition": "多云"}
