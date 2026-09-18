"""在数据检索后决定日历是否需要默认查看动作，不改变用户展示字段。"""

from __future__ import annotations

from models.generation import TaskSpec

from .business_actions import _matches_business_data
from .models import TemplateDefinition
from .prompt import action_bindings
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .template_retrieval import TemplateSearchIntent, TemplateSearchResult

_CALENDAR_CAPABILITY = "GetCalendarEvents"
_CALENDAR_BUSINESS = "CalendarOverview"
_VIEW_EVENT = "event.viewCalendarEvent"


def resolve_calendar_view_fallback(
    intent: TemplateSearchIntent,
    search_result: TemplateSearchResult,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> TemplateSearchIntent:
    """有 Full 保持无动作；仅有 Hero 时复用唯一且同对象的已批准查看事件。"""
    if not intent.allow_calendar_view_fallback or intent.action_ids:
        return intent
    if task_spec.size != "2x2" or search_result.card_size != task_spec.size:
        return intent
    if tuple(intent.required_output_fields_by_capability) != (_CALENDAR_CAPABILITY,):
        return intent
    if len(search_result.business_candidates) != 1:
        return intent
    group = search_result.business_candidates[0]
    if group.capability_id != _CALENDAR_CAPABILITY or group.business_id != _CALENDAR_BUSINESS:
        return intent

    heroes: list[TemplateDefinition] = []
    for candidate in group.candidates:
        role = provider_template_layout_kind(candidate.template_id)
        if role == "Full":
            return intent
        if role == "Hero":
            heroes.append(registry.require_template(candidate.template_id))
    if not heroes:
        return intent
    view_actions = [
        action for action in action_bindings(task_spec) if action.event_id == _VIEW_EVENT
    ]
    if len(view_actions) != 1:
        return intent
    action = view_actions[0]
    if not all(_matches_business_data(definition, action) for definition in heroes):
        return intent
    return intent.model_copy(update={"action_ids": (_VIEW_EVENT,)})
