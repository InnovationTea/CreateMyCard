"""Fail-closed deterministic second-layer Tersel composition."""

from __future__ import annotations

import json
from typing import Any

from services.template_generation.engine.cardplan.models import CARDTPL_SOURCE_FORMATS
from services.template_generation.engine.cardplan.prompt import _parameter_value_kind
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

from .ux_mixed_prompt import UxMixedPromptProjection


def compose_deterministic_tree(
    projection: UxMixedPromptProjection,
    registry: CardPlanRegistry,
) -> str | None:
    """Return a fully determined tree, or ``None`` to retain the LLM path."""
    if len(projection.template_plans) != 1:
        return None
    resolved = _single_plan_composition(projection)
    if resolved is None:
        return None
    layout_template_id, business_template_ids, action_calls = resolved
    # Planner action assignments identify the event, but do not yet carry the
    # complete visible Action props (notably an icon). Do not discard that
    # second-layer decision merely because the business template is unique.
    if action_calls:
        return None
    children: list[str] = []
    for template_id in business_template_ids:
        params = _deterministic_template_params(
            template_id,
            projection.contract,
            registry,
            card_title=projection.card_title,
        )
        if params is None:
            return None
        children.append(_template_call(template_id, params))
    children.extend(action_calls)
    return f'Template({json.dumps(layout_template_id)}, {{}}, ' + ", ".join(children) + ");"


def _single_plan_composition(
    projection: UxMixedPromptProjection,
) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    plan = projection.template_plans[0]
    if len(projection.layout_selection.layout_ids) != 1:
        return None
    if plan.layout_template_id != f"{projection.layout_selection.layout_ids[0]}@1":
        return None
    if any(item.consumer != "root-action" for item in plan.action_assignments):
        return None
    actions_by_id = {item["actionId"]: item for item in projection.selected_actions}
    if len(actions_by_id) != len(projection.selected_actions):
        return None
    action_calls: list[str] = []
    for assignment in plan.action_assignments:
        action = actions_by_id.get(assignment.action_id)
        if action is None or assignment.action_template_id is None:
            return None
        action_calls.append(_template_call(assignment.action_template_id, dict(action)))
    if len(action_calls) != len(projection.selected_actions):
        return None
    return (
        plan.layout_template_id,
        tuple(slot.template_id for slot in plan.business_slots),
        tuple(action_calls),
    )


def _deterministic_template_params(
    template_id: str,
    contract: Any,
    registry: CardPlanRegistry,
    *,
    card_title: str,
) -> dict[str, Any] | None:
    """Supply only an unambiguous asset when no literal decision is needed.

    Optional literal props are not safe to discard: the second-layer model may
    derive visible copy such as a card-title header from the request. Until
    those values have an explicit deterministic source, their presence keeps
    the request on the LLM path.
    """
    definition = registry.require_template(template_id)
    if definition.source_format not in CARDTPL_SOURCE_FORMATS or len(definition.variants) != 1:
        return None
    variant = definition.variants[0]
    properties = variant.parameters_schema.get("properties", {})
    required_names = set(variant.parameters_schema.get("required", ()))
    params: dict[str, Any] = {}
    for name, schema in properties.items():
        value_kind = _parameter_value_kind(name, schema)
        if value_kind != "asset-source":
            return None
        candidates = _asset_candidates(name, definition, contract)
        if len(candidates) == 1:
            params[name] = candidates[0]
        elif name in required_names:
            return None
    return params


def _asset_candidates(name: str, definition: Any, contract: Any) -> tuple[str, ...]:
    required_tags = set(definition.asset_parameter_semantic_tags.get(name, ()))
    if not required_tags:
        return tuple(contract.allowed_asset_sources)
    return tuple(
        source
        for source in contract.allowed_asset_sources
        if required_tags.issubset(set(contract.asset_semantic_tags_by_source.get(source, ())))
    )


def _template_call(template_id: str, params: dict[str, Any]) -> str:
    return f"Template({json.dumps(template_id)}, {json.dumps(params, ensure_ascii=False, separators=(',', ':'))})"
