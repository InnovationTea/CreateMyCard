"""Deterministic planning between data-only Search and the second-layer LLM."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product

from models.generation import TaskSpec
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
)

from .models import (
    TemplateDefinition,
    TemplatePlan,
    TemplatePlanActionAssignment,
    TemplatePlanBusinessSlot,
)
from .prompt import action_binding_ids
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .template_retrieval import (
    TemplateBusinessCandidates,
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    TemplateSearchResult,
)

_MAX_PLANS = 3
_PILL_ACTION_TEMPLATE_ID = "PillAction@1"
_ICON_ACTION_TEMPLATE_ID = "IconAction@1"
_THEME_TERMS_BY_BUSINESS = {
    "ActivityOverview": ("sport", "activity", "运动", "步数"),
    "AppUsageOverview": ("app", "usage", "digital", "应用", "时长"),
    "BatteryOverview": ("battery", "device", "电量", "设备"),
    "BluetoothDeviceOverview": ("earphone", "audio", "battery", "耳机", "电量"),
    "CalendarOverview": ("calendar", "schedule", "meeting", "日历", "日程"),
    "CountdownOverview": ("countdown", "event", "倒计时"),
    "HeartRateOverview": ("sport", "heart", "rate", "运动", "心率"),
    "ResourceUsageOverview": ("device", "resource", "memory", "设备", "资源"),
    "SleepOverview": ("sleep", "睡眠"),
    "WeatherOverview": ("weather", "天气"),
    "WorkoutOverview": ("sport", "workout", "运动", "训练"),
}


@dataclass(frozen=True)
class _PlanDraft:
    plan: TemplatePlan
    score: tuple[int, ...]
    sequence: int


def plan_template_candidates(
    intent: TemplateSearchIntent,
    search_result: TemplateSearchResult,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[TemplatePlan, ...]:
    """Build at most three complete, atomic UI plans from Search candidates."""
    if search_result.card_size != task_spec.size:
        raise TemplateRetrievalMiss("Search result card size does not match TaskSpec")
    groups_by_capability = _groups_by_capability(search_result)
    requested_capabilities = tuple(intent.required_output_fields_by_capability)
    if any(capability_id not in groups_by_capability for capability_id in requested_capabilities):
        raise TemplateRetrievalMiss("Search result does not cover every requested capability")
    action_ids = _selected_action_ids(intent, task_spec)
    drafts: list[_PlanDraft] = []
    sequence = 0
    group_options = tuple(groups_by_capability[item] for item in requested_capabilities)
    for selected_groups in product(*group_options):
        if len(selected_groups) == 1:
            new_drafts = _single_business_drafts(
                selected_groups[0],
                action_ids,
                intent,
                task_spec,
                registry,
            )
        elif len(selected_groups) == 2:
            new_drafts = _dual_business_drafts(
                selected_groups,
                action_ids,
                intent,
                task_spec,
                registry,
            )
        else:
            new_drafts = ()
        for plan, score in new_drafts:
            drafts.append(_PlanDraft(plan=plan, score=score, sequence=sequence))
            sequence += 1
    if not drafts:
        raise TemplateRetrievalMiss("Search candidates cannot form a supported atomic plan")

    if len(requested_capabilities) == 1:
        focus = intent.primary_output_field_by_capability.get(requested_capabilities[0])
        focused = [
            draft
            for draft in drafts
            if focus in draft.plan.business_slots[0].primary_matched_fields
        ]
        if focused:
            drafts = focused
    drafts.sort(key=lambda item: (*tuple(-value for value in item.score), item.sequence))
    deduplicated = _deduplicate_drafts(drafts)
    top_theme = deduplicated[0].plan.theme_id
    same_theme = [item for item in deduplicated if item.plan.theme_id == top_theme]
    return tuple(
        item.plan.model_copy(update={"plan_id": f"plan-{index + 1}"})
        for index, item in enumerate(same_theme[:_MAX_PLANS])
    )


def planner_scope(plans: tuple[TemplatePlan, ...]) -> AdvancedScopeBrief:
    """Project Planner results to the legacy scope needed by trusted prompt builders."""
    if not plans:
        raise ValueError("Template Planner produced no plan")
    first = plans[0]
    business_ids = tuple(slot.business_id for slot in first.business_slots)
    plans_cover_same_businesses = all(
        _plan_business_ids(plan) == set(business_ids) for plan in plans
    )
    if not plans_cover_same_businesses:
        raise ValueError("Template Plans must cover the same businesses")
    if any(plan.theme_id != first.theme_id for plan in plans):
        raise ValueError("Template Plans must share one trusted Theme contract")
    return AdvancedScopeBrief(
        themeId=first.theme_id,
        advancedComponentIds=business_ids,
    )


def _plan_business_ids(plan: TemplatePlan) -> set[str]:
    return {slot.business_id for slot in plan.business_slots}


def planner_component_candidates(
    plans: tuple[TemplatePlan, ...],
) -> tuple[TemplateComponentCandidate, ...]:
    """Return the ordered candidate union used only to build prompt contracts."""
    scope = planner_scope(plans)
    template_ids_by_business: dict[str, list[str]] = {
        business_id: [] for business_id in scope.advanced_component_ids
    }
    for plan in plans:
        for slot in plan.business_slots:
            values = template_ids_by_business.get(slot.business_id)
            if values is None:
                raise ValueError("Template Plan contains an unknown business")
            if slot.template_id not in values:
                values.append(slot.template_id)
    candidates: list[TemplateComponentCandidate] = []
    for business_id in scope.advanced_component_ids:
        template_ids = template_ids_by_business.get(business_id)
        if template_ids is None:
            raise ValueError("Template Plan business has no candidate set")
        candidates.append(
            TemplateComponentCandidate(
                componentId=business_id,
                availableTemplateIds=tuple(template_ids),
            )
        )
    return tuple(candidates)


def planner_required_template_groups(
    plans: tuple[TemplatePlan, ...],
) -> tuple[tuple[str, ...], ...]:
    """Return one coverage group per business, never one group per field."""
    return tuple(
        candidate.available_template_ids for candidate in planner_component_candidates(plans)
    )


def _groups_by_capability(
    search_result: TemplateSearchResult,
) -> dict[str, tuple[TemplateBusinessCandidates, ...]]:
    grouped: dict[str, list[TemplateBusinessCandidates]] = {}
    for group in search_result.business_candidates:
        grouped.setdefault(group.capability_id, []).append(group)
    return {capability_id: tuple(groups) for capability_id, groups in grouped.items()}


def _selected_action_ids(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
) -> tuple[str, ...]:
    available_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if not set(intent.action_ids).issubset(available_ids):
        raise TemplateRetrievalMiss("Planner Action is outside TaskSpec.eventCandidates")
    selected_ids = set(intent.action_ids)
    selected_task_spec = task_spec.model_copy(
        update={
            "eventCandidates": [
                event for event in task_spec.eventCandidates if event.id in selected_ids
            ]
        }
    )
    return action_binding_ids(selected_task_spec)


def _single_business_drafts(
    group: TemplateBusinessCandidates,
    action_ids: tuple[str, ...],
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[tuple[TemplatePlan, tuple[int, ...]], ...]:
    if task_spec.size != "2x2":
        return ()
    layouts: tuple[tuple[str, str, str | None], ...]
    if not action_ids:
        layouts = (("SingleFocusLayout@1", "Full", None),)
    elif len(action_ids) == 1:
        values = [("HeroActionLayout@1", "Hero", _PILL_ACTION_TEMPLATE_ID)]
        if _has_semantic_action_icon(task_spec):
            values.append(("FullIconActionLayout@1", "Full", _ICON_ACTION_TEMPLATE_ID))
        layouts = tuple(values)
    elif len(action_ids) == 2:
        layouts = (("CompactTwoActionLayout@1", "Compact", _PILL_ACTION_TEMPLATE_ID),)
    else:
        return ()
    result: list[tuple[TemplatePlan, tuple[int, ...]]] = []
    for layout_template_id, role, action_template_id in layouts:
        for candidate in group.candidates:
            if provider_template_layout_kind(candidate.template_id) != role:
                continue
            definition = registry.require_template(candidate.template_id)
            slot = _business_slot(0, group, candidate.template_id, role, intent, definition)
            assignments = _root_action_assignments(action_ids, action_template_id)
            plan = _make_plan(
                layout_template_id,
                (slot,),
                assignments,
                registry,
            )
            if plan is not None:
                result.append((plan, _plan_score(plan, intent, registry)))
    return tuple(result)


def _dual_business_drafts(
    groups: tuple[TemplateBusinessCandidates, TemplateBusinessCandidates],
    action_ids: tuple[str, ...],
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[tuple[TemplatePlan, tuple[int, ...]], ...]:
    if task_spec.size != "2x2" or len(action_ids) > 2:
        return ()
    result: list[tuple[TemplatePlan, tuple[int, ...]]] = []
    ordered_groups = tuple(permutations(groups))
    if len(action_ids) == 1:
        for title_group, content_group in ordered_groups:
            title_ids = _template_ids_for_role(title_group, "HeroTitle")
            content_ids = _template_ids_for_role(content_group, "HeroContent")
            for title_id, content_id in product(title_ids, content_ids):
                slots = (
                    _business_slot(
                        0,
                        title_group,
                        title_id,
                        "HeroTitle",
                        intent,
                        registry.require_template(title_id),
                    ),
                    _business_slot(
                        1,
                        content_group,
                        content_id,
                        "HeroContent",
                        intent,
                        registry.require_template(content_id),
                    ),
                )
                plan = _make_plan(
                    "HeroTitleContentActionLayout@1",
                    slots,
                    _root_action_assignments(action_ids, _PILL_ACTION_TEMPLATE_ID),
                    registry,
                )
                if plan is not None:
                    result.append((plan, _plan_score(plan, intent, registry)))
    for first_group, second_group in ordered_groups:
        first_ids = _template_ids_for_role(first_group, "Support")
        second_ids = _template_ids_for_role(second_group, "Support")
        for first_id, second_id in product(first_ids, second_ids):
            slots = (
                _business_slot(
                    0,
                    first_group,
                    first_id,
                    "Support",
                    intent,
                    registry.require_template(first_id),
                ),
                _business_slot(
                    1,
                    second_group,
                    second_id,
                    "Support",
                    intent,
                    registry.require_template(second_id),
                ),
            )
            for assignments in _business_action_assignment_options(
                action_ids,
                slots,
                registry,
                task_spec.size,
            ):
                plan = _make_plan("TwoSupportLayout@1", slots, assignments, registry)
                if plan is not None:
                    result.append((plan, _plan_score(plan, intent, registry)))
    return tuple(result)


def _template_ids_for_role(
    group: TemplateBusinessCandidates,
    role: str,
) -> tuple[str, ...]:
    return tuple(
        candidate.template_id
        for candidate in group.candidates
        if provider_template_layout_kind(candidate.template_id) == role
    )


def _business_slot(
    position: int,
    group: TemplateBusinessCandidates,
    template_id: str,
    role: str,
    intent: TemplateSearchIntent,
    definition: TemplateDefinition,
) -> TemplatePlanBusinessSlot:
    candidate = next(item for item in group.candidates if item.template_id == template_id)
    focus = intent.primary_output_field_by_capability.get(group.capability_id)
    primary_matches = tuple(
        path
        for path in definition.primary_data
        if path in group.explicit_fields or path == focus
    )
    return TemplatePlanBusinessSlot(
        position=position,
        businessId=group.business_id,
        capabilityId=group.capability_id,
        templateId=template_id,
        layoutRole=role,
        coveredExplicitFields=candidate.covered_explicit_fields,
        primaryMatchedFields=primary_matches,
    )


def _root_action_assignments(
    action_ids: tuple[str, ...],
    action_template_id: str | None,
) -> tuple[TemplatePlanActionAssignment, ...]:
    if action_template_id is None:
        return ()
    return tuple(
        TemplatePlanActionAssignment(
            actionId=action_id,
            consumer="root-action",
            actionTemplateId=action_template_id,
        )
        for action_id in action_ids
    )


def _business_action_assignment_options(
    action_ids: tuple[str, ...],
    slots: tuple[TemplatePlanBusinessSlot, ...],
    registry: CardPlanRegistry,
    card_size: str,
) -> tuple[tuple[TemplatePlanActionAssignment, ...], ...]:
    if not action_ids:
        return ((),)
    eligible_positions = tuple(
        slot.position
        for slot in slots
        if _template_accepts_action(slot.template_id, registry, card_size)
    )
    if len(eligible_positions) < len(action_ids):
        return ()
    results: list[tuple[TemplatePlanActionAssignment, ...]] = []
    for positions in permutations(eligible_positions, len(action_ids)):
        results.append(
            tuple(
                TemplatePlanActionAssignment(
                    actionId=action_id,
                    consumer="business-template",
                    businessPosition=position,
                )
                for action_id, position in zip(action_ids, positions, strict=True)
            )
        )
    return tuple(results)


def _template_accepts_action(
    template_id: str,
    registry: CardPlanRegistry,
    card_size: str,
) -> bool:
    definition = registry.require_template(template_id)
    for variant in definition.variants:
        size_is_supported = not variant.supported_card_sizes
        size_is_supported = size_is_supported or card_size in variant.supported_card_sizes
        properties = variant.parameters_schema.get("properties", {})
        if size_is_supported and "actionId" in properties:
            return True
    return False


def _make_plan(
    layout_template_id: str,
    slots: tuple[TemplatePlanBusinessSlot, ...],
    assignments: tuple[TemplatePlanActionAssignment, ...],
    registry: CardPlanRegistry,
) -> TemplatePlan | None:
    layout_id = layout_template_id.removesuffix("@1")
    theme_id = _resolve_theme(layout_id, slots, registry)
    if theme_id is None:
        return None
    return TemplatePlan(
        planId="draft",
        themeId=theme_id,
        layoutTemplateId=layout_template_id,
        businessSlots=slots,
        actionAssignments=assignments,
    )


def _resolve_theme(
    layout_id: str,
    slots: tuple[TemplatePlanBusinessSlot, ...],
    registry: CardPlanRegistry,
) -> str | None:
    if layout_id == "TwoSupportLayout":
        capability_ids = tuple(slot.capability_id for slot in slots)
        return registry.require_layout_theme(layout_id, capability_ids)
    owner = slots[1] if layout_id == "HeroTitleContentActionLayout" else slots[0]
    theme_ids = registry.first_layer_theme_ids((owner.business_id,))
    definitions = tuple(registry.require_template(slot.template_id) for slot in slots)
    compatible_theme_ids: list[str] = []
    for theme_id in theme_ids:
        compatible = all(
            not definition.compatible_theme_profile_ids
            or theme_id in definition.compatible_theme_profile_ids
            for definition in definitions
        )
        if compatible:
            compatible_theme_ids.append(theme_id)
    if not compatible_theme_ids:
        return None
    return max(
        compatible_theme_ids,
        key=lambda theme_id: _theme_business_score(
            theme_id,
            owner.business_id,
            registry,
        ),
    )


def _theme_business_score(
    theme_id: str,
    business_id: str,
    registry: CardPlanRegistry,
) -> int:
    theme = registry.require_theme(theme_id)
    theme_text = " ".join(
        (theme.theme_profile_id, theme.description, *theme.palette_scene_ids)
    ).casefold()
    terms = _THEME_TERMS_BY_BUSINESS.get(business_id, (business_id.casefold(),))
    return sum(term.casefold() in theme_text for term in terms)


def _plan_score(
    plan: TemplatePlan,
    intent: TemplateSearchIntent,
    registry: CardPlanRegistry,
) -> tuple[int, ...]:
    explicit_primary_matches = 0
    primary_matches = 0
    secondary_matches = 0
    optional_only_matches = 0
    for slot in plan.business_slots:
        definition = registry.require_template(slot.template_id)
        explicit = set(slot.covered_explicit_fields)
        focus = intent.primary_output_field_by_capability.get(slot.capability_id)
        if focus is not None and focus in definition.primary_data:
            explicit_primary_matches += 1
        primary_matches += len(explicit.intersection(definition.primary_data))
        secondary_matches += len(explicit.intersection(definition.secondary_data))
        optional_only_matches += len(explicit.intersection(definition.optional_data))
    return (
        explicit_primary_matches,
        primary_matches,
        secondary_matches,
        -optional_only_matches,
    )


def _deduplicate_drafts(drafts: list[_PlanDraft]) -> list[_PlanDraft]:
    result: list[_PlanDraft] = []
    seen: set[tuple[object, ...]] = set()
    for draft in drafts:
        plan = draft.plan
        signature = (
            plan.theme_id,
            plan.layout_template_id,
            tuple(slot.template_id for slot in plan.business_slots),
            tuple(
                (
                    item.action_id,
                    item.consumer,
                    item.business_position,
                    item.action_template_id,
                )
                for item in plan.action_assignments
            ),
        )
        if signature in seen:
            continue
        seen.add(signature)
        result.append(draft)
    return result


def _has_semantic_action_icon(task_spec: TaskSpec) -> bool:
    keywords = {"action", "event", "shortcut", "动作", "操作", "入口", "快捷"}
    for candidate in task_spec.assetCandidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("src"), str):
            continue
        text_values = [str(candidate.get("description", ""))]
        for key in ("sceneTags", "semanticTags", "tags"):
            values = candidate.get(key, ())
            if isinstance(values, list):
                text_values.extend(str(item) for item in values)
        normalized = " ".join(text_values).casefold()
        if any(keyword in normalized for keyword in keywords):
            return True
    return False
