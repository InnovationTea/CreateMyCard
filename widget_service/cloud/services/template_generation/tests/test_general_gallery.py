"""通用画廊的正常准入、独立分组及批跑状态回归。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.general_templates import parameter_data_paths
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    restrict_search_intent_to_preferred_templates,
    search_template_variants,
)
from services.template_generation.engine.pipeline import (
    _project_selected_template_facts,
    _with_provider_template_runtime_data,
)
from services.template_generation.test_support.general_gallery import (
    GENERAL_PROVIDER_ID,
    append_general_templates,
    select_general_fields,
)
from services.template_generation.test_support.provider_gallery import (
    GalleryInputProvider,
    ProviderGalleryBatchRunner,
    write_gallery_input_dataset,
)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, GalleryInputProvider]:
    root = tmp_path_factory.mktemp("general-gallery")
    write_gallery_input_dataset(root)
    manifest = append_general_templates(root)
    group = next(item for item in manifest.providers if item.providerId == GENERAL_PROVIDER_ID)
    return root, group


def _task_schema(schema: dict[str, Any]) -> Any:
    result: Any
    if schema.get("type") == "object":
        result = {}
        for name, value in schema.get("properties", {}).items():
            result[name] = _task_schema(value)
    elif schema.get("type") == "array":
        result = [_task_schema(schema.get("items", {}))]
    else:
        result = {"type": schema.get("type")}
    return result


def test_general_gallery_is_complete_and_idempotent(
    dataset: tuple[Path, GalleryInputProvider],
) -> None:
    root, group = dataset
    before = json.loads((root / "manifest.json").read_text())
    after = append_general_templates(root).model_dump()
    assert after == before
    assert group.providerName == "通用模板"
    assert len(group.cases) == 128
    assert len({case.targetTemplateId for case in group.cases}) == 128
    assert sum(bool(case.missingReason) for case in group.cases) == 32
    for case in group.cases:
        if case.businessId == "CountdownOverview":
            assert "专用" in case.missingReason
        elif case.businessId in {"ResourceUsageOverview", "AppUsageOverview"}:
            assert "未注册" in case.missingReason
        else:
            assert not case.missingReason
        if case.expectedTemplateSuffix == "Support":
            assert case.partnerTemplateId.endswith("GeneralTextSupport@1")
            assert not case.expectsFusionBall


def test_every_available_general_case_is_retrievable_without_disabling_specialized(
    dataset: tuple[Path, GalleryInputProvider],
) -> None:
    root, group = dataset
    registry = CardPlanRegistry(enable_fusion_ball=True)
    assert not registry.disabled_template_ids
    checked = 0
    for case in group.cases:
        if case.missingReason:
            continue
        payload = json.loads((root / case.requestFile).read_text())
        content = payload.get("content")
        assert isinstance(content, dict)
        bindings = content.get("candidateDataBindings")
        assert isinstance(bindings, list)
        for index, template_id in enumerate((case.targetTemplateId, case.partnerTemplateId)):
            if not template_id:
                continue
            definition = registry.require_template(template_id)
            binding = CandidateDataBinding.model_validate(bindings[index])
            fields = tuple(binding.candidateOutputFields or ())
            assert fields
            capability_id = definition.capability_id
            domain = definition.data_domain
            assert capability_id is not None and domain is not None
            schema = _task_schema(definition.data_source_schema)
            for part in reversed(domain.removeprefix("/").split("/")):
                schema = {part: schema}
            task = TaskSpec(userQuery="通用画廊", size="2x2", dataModelSchema=schema)
            card = {"dataBindings": [{"capabilityId": capability_id, "writeResultTo": domain}]}
            intent = TemplateSearchIntent(
                requiredOutputFieldsByCapability={capability_id: fields},
                primaryOutputFieldByCapability={capability_id: fields[0]},
            )
            restricted = restrict_search_intent_to_preferred_templates(
                intent, registry, (template_id,),
            )
            assert restricted == intent
            result = search_template_variants(
                restricted, task, registry, (binding,), card,
                preferred_template_ids=(template_id,),
            )
            candidate_ids: set[str] = set()
            for business in result.business_candidates:
                for candidate in business.candidates:
                    candidate_ids.add(candidate.template_id)
            assert template_id in candidate_ids, (template_id, fields)
        checked += 1
    assert checked == 96


@pytest.mark.asyncio
async def test_general_gallery_dry_run_does_not_claim_model_success(
    dataset: tuple[Path, GalleryInputProvider], tmp_path: Path,
) -> None:
    class NoModelService:
        async def generate_widget_card_terse_dsl_nested2(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("dry run must not call model")

    root, _group = dataset
    summary = await ProviderGalleryBatchRunner(NoModelService()).run(
        root, tmp_path, provider_ids={GENERAL_PROVIDER_ID}, dry_run=True,
    )
    assert (summary.total, summary.success, summary.failed) == (128, 0, 0)
    assert (summary.missing, summary.not_generated) == (32, 96)


@pytest.mark.parametrize("template_id", [
    "WeatherOverviewGeneralTextFull@1",
    "BatteryOverviewGeneralNumberFull@1",
    "ScheduleOverviewGeneralPairFull@1",
    "SleepOverviewGeneralTextFull@1",
    "HeartRateOverviewGeneralTextFull@1",
    "ActivityOverviewGeneralTextFull@1",
    "BluetoothDeviceOverviewGeneralTextFull@1",
])
def test_second_layer_retains_only_planned_general_data(template_id: str) -> None:
    registry = CardPlanRegistry()
    definition = registry.require_template(template_id)
    fields, missing = select_general_fields(definition, registry)
    assert not missing
    capability_id = definition.capability_id
    domain = definition.data_domain
    assert capability_id is not None and domain is not None
    schema = _task_schema(definition.data_source_schema)
    for part in reversed(domain.removeprefix("/").split("/")):
        schema = {part: schema}
    task = TaskSpec(userQuery="显示所有选中字段", size="2x2", dataModelSchema=schema)
    card = {"dataBindings": [{"capabilityId": capability_id, "writeResultTo": domain}]}
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={capability_id: fields},
        primaryOutputFieldByCapability={capability_id: fields[0]},
    )
    binding = CandidateDataBinding(
        capabilityId=capability_id, writeResultTo=domain, candidateOutputFields=fields,
    )
    search = search_template_variants(
        intent, task, registry, (binding,), card, preferred_template_ids=(template_id,),
    )
    plans = plan_template_candidates(intent, search, task, registry)
    projected = _project_selected_template_facts(
        task, {capability_id}, planner_scope(plans).advanced_component_ids,
        planner_component_candidates(plans), registry,
    )
    restored = _with_provider_template_runtime_data(
        task, projected, card, planner_scope(plans).advanced_component_ids,
        planner_component_candidates(plans), registry, template_plans=plans,
    )
    assert set(parameter_data_paths(definition, restored)) == set(fields)
    assert projected.dataModelSchema == {"data": {}}
    prompt = build_ux_mixed_prompt(
        task_spec=restored, card_spec=card, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )
    assert template_id in prompt.requested_template_ids
