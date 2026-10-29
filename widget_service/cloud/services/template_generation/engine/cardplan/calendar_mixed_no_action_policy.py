"""旧匹配失败后，仅补已登记的日程天气无动作双业务宽卡。"""

from __future__ import annotations

from typing import Any

from app.logger import logger
from models.generation import CandidateDataBinding, TaskSpec

from .calendar_field_paths import CALENDAR_CAPABILITY_ID
from .calendar_no_action_policy import (
    _ACTION_QUERY,
    _MULTIPLE_EVENTS_QUERY,
    _NEGATIVE_ACTION,
    CalendarNoActionFallback,
    _calendar_fail_single_query_allowed,
)
from .registry import CardPlanRegistry
from .template_plan_planner import plan_template_candidates
from .template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    search_template_variants,
)

_WEATHER = "ViewWeather"
_TARGET = "ScheduleOverviewDateTitleFull@1"
_FIELDS = frozenset({"/events/0/title", "/events/0/startDate"})
_LOCATION_TARGET = "ScheduleOverviewTitleLocationHero@1"
_LOCATION_FIELDS = frozenset({"/events/0/title", "/events/0/eventLocation"})


def plan_calendar_weather_no_action_fallback(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
    *,
    enable_fusion_ball: bool = False,
    trusted_template_candidate_ids: tuple[str, ...] = (),
    trusted_template_action_ids: tuple[str, ...] = (),
    trusted_template_layout_ids: tuple[str, ...] = (),
) -> CalendarNoActionFallback | None:
    """保留两业务全部字段，仅开放一个对应日程形态，仍由正式检索与规划验证。"""
    result: CalendarNoActionFallback | None = None
    if task_spec.size != "2x4" or not _calendar_weather_request(
        intent, coverage_bindings, card_spec
    ):
        return result
    if intent.action_ids or trusted_template_action_ids:
        return result
    query = _NEGATIVE_ACTION.sub("", task_spec.userQuery)
    if _ACTION_QUERY.search(query) or _MULTIPLE_EVENTS_QUERY.search(query):
        return result
    fields = intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    target: str | None = None
    if frozenset(fields) == _FIELDS:
        target = _TARGET
    elif frozenset(fields) == _LOCATION_FIELDS:
        weather_fields = intent.required_output_fields_by_capability.get(_WEATHER, ())
        if frozenset(weather_fields) == {"/current/condition"}:
            target = _LOCATION_TARGET
    if target is None or target not in registry.templates:
        return result
    if target == _LOCATION_TARGET and not _calendar_fail_single_query_allowed(query):
        return result
    # 可信范围含天气模板，不能像单业务后备那样要求只含日历目标。
    if trusted_template_candidate_ids and target not in trusted_template_candidate_ids:
        return result
    fallback_registry = CardPlanRegistry(
        source_root=registry.source_root,
        disabled_provider_ids=tuple(registry.disabled_provider_ids),
        disabled_template_ids=tuple(registry.disabled_template_ids),
        enable_fusion_ball=enable_fusion_ball,
        enabled_calendar_fallback_template_ids=(target,),
    )
    if not fallback_registry.template_is_enabled(target):
        return result
    try:
        found = search_template_variants(
            intent,
            task_spec,
            fallback_registry,
            coverage_bindings,
            card_spec,
            preferred_template_ids=trusted_template_candidate_ids,
        )
        plans = plan_template_candidates(
            intent,
            found,
            task_spec,
            fallback_registry,
            allowed_layout_ids=trusted_template_layout_ids,
        )
    except TemplateRetrievalMiss as exc:
        logger.info(
            "[Template Generation] calendar_weather_no_action_fallback selected=False "
            f"template_id={target} reason={exc}"
        )
        return result
    result = CalendarNoActionFallback(intent, fallback_registry, found, plans)
    return result


def _calendar_weather_request(
    intent: TemplateSearchIntent,
    bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
) -> bool:
    expected = {CALENDAR_CAPABILITY_ID, _WEATHER}
    if set(intent.required_output_fields_by_capability) != expected or len(bindings) != 2:
        return False
    if not intent.required_output_fields_by_capability.get(_WEATHER):
        return False
    expected_bindings = {(item.capabilityId, item.writeResultTo) for item in bindings}
    if {item.capabilityId for item in bindings} != expected:
        return False
    card_bindings = card_spec.get("dataBindings")
    if not isinstance(card_bindings, list) or len(card_bindings) != 2:
        return False
    actual_bindings: set[tuple[str, str]] = set()
    for item in card_bindings:
        if not isinstance(item, dict):
            return False
        capability = item.get("capabilityId")
        root = item.get("writeResultTo")
        if not isinstance(capability, str) or not isinstance(root, str):
            return False
        actual_bindings.add((capability, root))
    return actual_bindings == expected_bindings
