"""Deterministically wrap one retrieved Template Variant in a trusted UX layout."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from models.generation import TaskSpec
from services.template_generation.engine.advanced.models import AdvancedScopeBrief
from services.template_generation.engine.advanced.ux_mixed_prompt import UxMixedPromptProjection

from .template_retrieval import TemplateMatch


class DirectTemplatePlanError(ValueError):
    """A retrieved Variant cannot be mapped to a safe deterministic layout."""


@dataclass(frozen=True)
class DirectTemplatePlan:
    source: str
    layout_id: str
    projection: UxMixedPromptProjection


def build_direct_template_plan(
    *,
    match: TemplateMatch,
    task_spec: TaskSpec,
    scope: AdvancedScopeBrief,
    projection: UxMixedPromptProjection,
) -> DirectTemplatePlan:
    if len(scope.advanced_component_ids) != 1:
        raise DirectTemplatePlanError("direct template plan requires one business component")
    if not projection.allowed_layout_ids:
        raise DirectTemplatePlanError("direct template plan has no compatible UX layout")
    if match.template_id not in projection.contract.allowed_template_ids:
        raise DirectTemplatePlanError("retrieved Template is outside the trusted contract")

    contract = projection.contract.model_copy(
        update={
            "allowed_template_ids": (match.template_id,),
            "allowed_template_variants": {match.template_id: (match.variant_name,)},
            "required_template_groups": ((match.template_id,),),
        }
    )
    locked_projection = replace(projection, contract=contract)
    layout_id = projection.allowed_layout_ids[0]
    template = _template_call(match)
    actions = _action_calls(
        layout_id=layout_id,
        task_spec=task_spec,
        component_id=scope.advanced_component_ids[0],
        action_ids=contract.content_action_ids,
        asset_tags=contract.asset_semantic_tags_by_source,
    )
    children = ",".join((template, *actions))
    return DirectTemplatePlan(
        source=f"{layout_id}({children});",
        layout_id=layout_id,
        projection=locked_projection,
    )


def _template_call(match: TemplateMatch) -> str:
    template_id = json.dumps(match.template_id, ensure_ascii=False)
    if match.variant_name != "default":
        variant_name = json.dumps(match.variant_name, ensure_ascii=False)
        return f"Template({template_id},{variant_name},{{}})"
    return f"Template({template_id},{{}})"


def _action_calls(
    *,
    layout_id: str,
    task_spec: TaskSpec,
    component_id: str,
    action_ids: tuple[str, ...],
    asset_tags: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    if not action_ids:
        return ()
    if layout_id == "ActionMatrixLayout":
        return tuple(_action_call("ActionTile", action_id) for action_id in action_ids)
    if len(action_ids) != 1:
        raise DirectTemplatePlanError("selected UX layout accepts only one Action")
    if component_id == "BatteryOverview" and task_spec.size == "2x2":
        icon = _unique_power_saving_icon(asset_tags)
        if icon is None:
            raise DirectTemplatePlanError("battery action has no unique approved icon")
        return (_action_call("IconAction", action_ids[0], icon),)
    return (_action_call("PillAction", action_ids[0]),)


def _action_call(component: str, action_id: str, icon: str | None = None) -> str:
    params = {"actionId": action_id}
    if icon is not None:
        params["icon"] = icon
    value = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    return f"{component}({value})"


def _unique_power_saving_icon(asset_tags: dict[str, tuple[str, ...]]) -> str | None:
    candidates = tuple(
        source
        for source, tags in asset_tags.items()
        if set(tags) & {"power-saving", "battery-saver", "saving", "leaf"}
    )
    return candidates[0] if len(candidates) == 1 else None
