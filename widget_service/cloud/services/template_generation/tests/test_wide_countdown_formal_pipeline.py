"""2x4 倒计时样例经过正式 Search → Planner → FillData 的回归。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    UxMixedPromptProjection,
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.models import TemplatePlan
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    TemplateSearchResult,
    search_template_variants,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_wide_countdown_case_routing import (
    _calendar_countdown_case,
    _destination_weather_case,
    _health_countdown_case,
    _three_day_weather_case,
    _WideCase,
)


@dataclass(frozen=True)
class _FormalRoute:
    search_result: TemplateSearchResult
    plans: tuple[TemplatePlan, ...]
    projection: UxMixedPromptProjection


def _intent(case: _WideCase) -> TemplateSearchIntent:
    return TemplateSearchIntent(
        requiredOutputFieldsByCapability=case.query.required_output_fields_by_capability,
        action=case.query.action_ids,
    )


def _formal_route(case: _WideCase) -> _FormalRoute:
    registry = get_cardplan_registry()
    intent = _intent(case)
    search_result = search_template_variants(
        intent,
        case.task_spec,
        registry,
        case.bindings,
        case.card_spec,
    )
    plans = plan_template_candidates(intent, search_result, case.task_spec, registry)
    projection = build_ux_mixed_prompt(
        task_spec=case.task_spec,
        card_spec=case.card_spec,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    return _FormalRoute(search_result, plans, projection)


@pytest.mark.parametrize(
    ("case_factory", "layout_id", "template_ids", "action_consumer"),
    (
        (
            _calendar_countdown_case,
            "WideTwoFullLayout@1",
            (
                "CountdownOverviewTargetDetailFull@1",
                "ScheduleOverviewEventCountTwoEventsFull@1",
            ),
            "business-template",
        ),
        (
            _three_day_weather_case,
            "WideHeroActionFullLayout@1",
            (
                "WeatherOverviewThreeDayForecastFull@1",
                "CountdownOverviewEventHero@1",
            ),
            "root-action",
        ),
        (
            _destination_weather_case,
            "WideHeroActionFullLayout@1",
            (
                "WeatherOverviewDestinationDayFull@1",
                "CountdownOverviewDepartureHero@1",
            ),
            "root-action",
        ),
        (
            _health_countdown_case,
            "WideFullTwoCompactLayout@1",
            (
                "ActivityOverviewTrainingSummaryFull@1",
                "CountdownOverviewTargetCompact@1",
            ),
            "root-action",
        ),
    ),
)
def test_formal_planner_prefers_complete_case_layouts(
    case_factory: Callable[[], _WideCase],
    layout_id: str,
    template_ids: tuple[str, ...],
    action_consumer: str,
) -> None:
    case = case_factory()
    routed = _formal_route(case)

    assert routed.plans
    top_plan = routed.plans[0]
    assert top_plan.layout_template_id == layout_id
    assert tuple(slot.template_id for slot in top_plan.business_slots) == template_ids
    assert len(top_plan.action_assignments) == 1
    assert top_plan.action_assignments[0].consumer == action_consumer
    assert routed.projection.contract.allowed_template_plans == routed.plans


def test_q072_search_covers_every_requested_weather_field() -> None:
    case = _three_day_weather_case()
    routed = _formal_route(case)
    requested_fields = case.query.required_output_fields_by_capability["ViewWeather"]
    assert len(requested_fields) == 15

    weather_group = next(
        group
        for group in routed.search_result.business_candidates
        if group.business_id == "WeatherOverview"
    )
    assert weather_group.explicit_fields == requested_fields
    three_day = next(
        candidate
        for candidate in weather_group.candidates
        if candidate.template_id == "WeatherOverviewThreeDayForecastFull@1"
    )
    assert set(three_day.covered_explicit_fields) == set(requested_fields)

    weather_slot = next(
        slot
        for slot in routed.plans[0].business_slots
        if slot.template_id == "WeatherOverviewThreeDayForecastFull@1"
    )
    assert set(weather_slot.covered_explicit_fields) == set(requested_fields)
    weather_template = get_cardplan_registry().require_template(weather_slot.template_id)
    binding_paths = {binding.path for binding in weather_template.bindings.values()}
    for day_index in range(3):
        assert f"/daily/{day_index}/weekday" in binding_paths
        assert f"/daily/{day_index}/rainProbabilityPercent" in binding_paths

    action = action_bindings(case.task_spec)[0]
    action_props = json.dumps(
        {"actionId": action.action_id, "label": action.display_label},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    source = (
        'Template("WideHeroActionFullLayout@1",{},'
        'Template("WeatherOverviewThreeDayForecastFull@1",{}),'
        'Template("CountdownOverviewEventHero@1",{}),'
        f'Template("PillAction@1",{action_props}));'
    )
    title = case.card_spec.get("title")
    assert isinstance(title, str)
    compilation = compile_ux_layout_card(
        source,
        task_spec=case.task_spec,
        contract=routed.projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=get_cardplan_registry(),
        business_title=title,
        card_spec=case.card_spec,
        enable_data_bindings=True,
    )
    for day_index in range(3):
        assert f"/daily/{day_index}/weekday" in compilation.a2ui
        assert f"/daily/{day_index}/rainProbabilityPercent" in compilation.a2ui


@pytest.mark.parametrize(
    "case_factory",
    (_calendar_countdown_case, _three_day_weather_case, _destination_weather_case),
)
def test_iconless_cases_never_offer_compact_action(
    case_factory: Callable[[], _WideCase],
) -> None:
    case = case_factory()
    assert not case.task_spec.assetCandidates
    routed = _formal_route(case)

    for plan in routed.plans:
        for assignment in plan.action_assignments:
            assert assignment.action_template_id != "CompactAction@1"
    assert "CompactAction@1" not in routed.projection.contract.allowed_template_ids


class _CalendarPipelineModel:
    def __init__(self, case: _WideCase) -> None:
        self.case = case
        self.phases: list[str] = []

    async def generate_json(
        self,
        _prompt: list[dict[str, str]],
        *,
        phase: str,
    ) -> dict[str, Any]:
        self.phases.append(phase)
        return {
            "requiredOutputFieldsByCapability": (
                self.case.query.required_output_fields_by_capability
            ),
            "action": self.case.query.action_ids,
        }

    async def generate(
        self,
        _prompt: list[dict[str, str]],
        _profile: dict[str, str],
        **kwargs: Any,
    ) -> str:
        phase = kwargs.get("phase")
        assert isinstance(phase, str)
        assert kwargs.get("suppress_prompt_log") is True
        self.phases.append(phase)
        action = action_bindings(self.case.task_spec)[0]
        props = json.dumps({"actionId": action.action_id}, separators=(",", ":"))
        return (
            'Template("WideTwoFullLayout@1",{},'
            'Template("CountdownOverviewTargetDetailFull@1",{}),'
            f'Template("ScheduleOverviewEventCountTwoEventsFull@1",{props}));'
        )


@pytest.mark.asyncio
async def test_calendar_case_reaches_second_layer_and_compiles_through_public_entry() -> None:
    case = _calendar_countdown_case()
    model = _CalendarPipelineModel(case)

    result = await generate_template_a2ui(
        case.task_spec,
        case.card_spec,
        case.bindings,
        model,
    )

    assert model.phases == ["template-retrieval-query", "advanced-mixed-body"]
    assert "WideTwoFullLayout@1" in result.template_ids
    assert "CountdownOverviewTargetDetailFull@1" in result.template_ids
    assert "ScheduleOverviewEventCountTwoEventsFull@1" in result.template_ids
    assert result.a2ui
