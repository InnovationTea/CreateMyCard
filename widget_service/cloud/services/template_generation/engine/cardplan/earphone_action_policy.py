"""按耳机候选动作数量依次选择 Compact、Hero、Full。"""

from __future__ import annotations

from itertools import combinations

from models.generation import TaskSpec

from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .template_plan_planner import plan_template_candidates
from .template_retrieval import TemplateRetrievalMiss, TemplateSearchIntent, TemplateSearchResult


def resolve_earphone_candidate_actions(
    intent: TemplateSearchIntent,
    search_result: TemplateSearchResult,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> TemplateSearchIntent:
    """仅处理未明确选择动作且允许交互的 2×2 单耳机场景。"""
    if task_spec.size != "2x2" or intent.action_ids:
        return intent
    if not intent.allow_earphone_candidate_actions:
        return intent
    if tuple(intent.required_output_fields_by_capability) != ("GetEarphoneInfo",):
        return intent
    event_ids: list[str] = []
    for event in task_spec.eventCandidates:
        if event.id not in event_ids:
            event_ids.append(event.id)
    if not event_ids:
        return intent
    action_counts = (2, 1) if len(event_ids) >= 2 else (1,)
    for action_count in action_counts:
        preferred_search = restrict_earphone_action_role(search_result, action_count)
        candidates: list[TemplateSearchIntent] = []
        for event_ids_group in combinations(event_ids, action_count):
            candidate = intent.model_copy(update={"action_ids": event_ids_group})
            try:
                plan_template_candidates(candidate, preferred_search, task_spec, registry)
            except TemplateRetrievalMiss:
                continue
            candidates.append(candidate)
        if candidates:
            return candidates[0]
    return intent


def restrict_earphone_action_role(
    search_result: TemplateSearchResult, action_count: int,
) -> TemplateSearchResult:
    """让后续规划保持已验证的 Hero/Compact 角色，不重新选回图标 Full。"""
    role = "Hero" if action_count == 1 else "Compact"
    groups = []
    for group in search_result.business_candidates:
        candidates = tuple(
            candidate for candidate in group.candidates
            if provider_template_layout_kind(candidate.template_id) == role
        )
        groups.append(group.model_copy(update={"candidates": candidates}))
    return search_result.model_copy(update={"business_candidates": tuple(groups)})
