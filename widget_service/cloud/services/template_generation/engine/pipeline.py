"""严格的两层模板路由与模板展开。"""

from __future__ import annotations

import inspect
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.logger import logger
from models.generation import CandidateDataBinding, TaskSpec
from services.card_validation.base import expression_references
from services.protocol_registry import (
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation.controls import load_template_controls
from services.template_generation.engine.advanced.content_selectors import (
    apply_content_selectors,
    project_content_component_facts,
)
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
)
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
    plan_template_route_with_llm,
    resolve_available_capability_ids,
    task_spec_with_selected_action,
)
from services.template_generation.engine.advanced.ux_mixed_framer import (
    frame_ux_layout_root_children,
)
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    build_ux_mixed_prompt,
    build_ux_mixed_validation_retry_prompt,
)
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateRetrievalQuery,
    build_template_retrieval_prompt,
    retrieve_template_variants,
)
from services.template_generation.engine.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
)

_MODULE = "[Template Generation]"
_MAX_BODY_REPAIRS = 2


class TemplateGenerationError(RuntimeError):
    """第一层已确认模板可用后，模板生成或展开失败。"""


@dataclass(frozen=True)
class TemplateEngineOutput:
    a2ui: str
    terse_dsl_nested2: str
    projected_task_spec: TaskSpec
    template_ids: tuple[str, ...]
    trusted_internal_asset_sources: tuple[str, ...]
    expanded_component_count: int
    theme_id: str


async def generate_template_a2ui(
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    coverage_bindings: tuple[CandidateDataBinding, ...],
    model_client: Any,
) -> TemplateEngineOutput:
    """先做 LLM 全量覆盖判断，再用受信模板确定性展开为 A2UI。"""
    task_spec_payload = task_spec.model_dump(mode="json")
    task_spec_message = (
        f"{_MODULE} task_spec_received "
        f"payload={json.dumps(task_spec_payload, ensure_ascii=False, separators=(',', ':'))}"
    )
    print(task_spec_message, flush=True)
    logger.info(task_spec_message)
    try:
        registry = get_cardplan_registry()
        controls = load_template_controls()
        available_capability_ids = _card_spec_capability_ids(card_spec)
        effective_capability_ids = resolve_available_capability_ids(
            task_spec,
            registry,
            available_capability_ids,
        )
        selected_task_spec = apply_content_selectors(task_spec, effective_capability_ids)
        data_shape = extract_data_shape(selected_task_spec)
        selected_task_spec_payload = json.dumps(
            selected_task_spec.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        selected_task_spec_message = (
            f"{_MODULE} task_spec_after_content_selectors "
            f"payload={selected_task_spec_payload}"
        )
        print(selected_task_spec_message, flush=True)
        logger.info(selected_task_spec_message)
    except ValueError as exc:
        raise TemplateRouteNotApplicable("template registry is unavailable") from exc

    async def generate_json(
        prompt: list[dict[str, str]],
        phase: str,
    ) -> dict[str, Any]:
        return await model_client.generate_json(prompt, phase=phase)

    try:
        if controls.first_layer_component_selector == "llm":
            selection = await plan_template_route_with_llm(
                selected_task_spec,
                data_shape,
                generate_json,
                registry,
                coverage_bindings,
                available_capability_ids,
                card_spec,
            )
        else:
            prompt = build_template_retrieval_prompt(
                selected_task_spec,
                registry,
                coverage_bindings,
            )
            raw_query = await generate_json(prompt, "template-retrieval-query")
            query = TemplateRetrievalQuery.model_validate(raw_query)
            selection = retrieve_template_variants(
                query,
                selected_task_spec,
                registry,
                coverage_bindings,
                card_spec,
            )
            logger.info(
                f"{_MODULE} template_retrieval matched=True "
                f"component_count={len(selection.component_candidates)}"
            )
    except TemplateRouteNotApplicable:
        raise
    except TemplateRetrievalMiss as exc:
        logger.info(f"{_MODULE} template_retrieval matched=False reason={exc}")
        raise TemplateRouteNotApplicable(str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise TemplateRouteNotApplicable(
            f"template first-layer decision failed: {exc}"
        ) from exc

    try:
        scope = selection.scope
        selected_task_spec = task_spec_with_selected_action(
            selected_task_spec,
            selection.action_id,
        )
        return await _generate_selected_templates(
            source_task_spec=selected_task_spec,
            card_spec=card_spec,
            effective_capability_ids=effective_capability_ids,
            scope=scope,
            component_candidates=selection.component_candidates,
            required_template_groups=selection.required_template_groups,
            registry=registry,
            model_client=model_client,
        )
    except TemplateGenerationError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise TemplateGenerationError("selected template generation failed") from exc


async def _generate_selected_templates(
    *,
    source_task_spec: TaskSpec,
    card_spec: dict[str, Any],
    effective_capability_ids: set[str],
    scope: AdvancedScopeBrief,
    component_candidates: tuple[TemplateComponentCandidate, ...],
    required_template_groups: tuple[tuple[str, ...], ...],
    registry: CardPlanRegistry,
    model_client: Any,
) -> TemplateEngineOutput:
    projected_task_spec = project_content_component_facts(
        source_task_spec,
        effective_capability_ids,
        scope.advanced_component_ids,
    )
    projected_task_spec = _with_provider_template_binding_projection(
        source_task_spec,
        projected_task_spec,
        card_spec,
        scope.advanced_component_ids,
        registry,
    )
    projection = build_ux_mixed_prompt(
        task_spec=projected_task_spec,
        card_spec=card_spec,
        scope=scope,
        component_candidates=component_candidates,
        required_template_groups=required_template_groups,
        registry=registry,
    )
    protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
    messages = projection.messages
    repair_count = 0
    while True:
        phase = "advanced-mixed-body" if repair_count == 0 else "advanced-mixed-body-repair"
        raw_output = await _generate_hybrid_body(model_client, messages, phase=phase)
        try:
            framed_output, _ = frame_ux_layout_root_children(
                raw_output,
                size=projected_task_spec.size,
                registry=registry,
                allowed_layout_ids=projection.allowed_layout_ids,
            )
            compilation = compile_ux_layout_card(
                framed_output,
                task_spec=projected_task_spec,
                contract=projection.contract,
                protocol_profile=protocol_profile,
                registry=registry,
                business_title=str(card_spec.get("title") or "") or None,
                card_spec=card_spec,
                enable_data_bindings=True,
            )
            break
        except TerseDslNested2ConversionError as exc:
            if repair_count >= _MAX_BODY_REPAIRS:
                raise TemplateGenerationError("template body validation failed") from exc
            repair_count += 1
            messages = build_ux_mixed_validation_retry_prompt(
                projection.messages,
                raw_output,
                exc,
            )

    requested_asset_sources = {
        source
        for item in projected_task_spec.assetCandidates
        if isinstance(item, dict)
        for source in (item.get("src"),)
        if isinstance(source, str)
    }
    trusted_sources = tuple(
        source
        for source in projection.contract.allowed_asset_sources
        if source not in requested_asset_sources and source in compilation.a2ui
    )
    logger.info(
        f"{_MODULE} selected_templates_generated "
        f"template_count={compilation.stats.template_call_count} "
        f"expanded_component_count={compilation.stats.expanded_component_count} "
        f"repair_count={repair_count}"
    )
    return TemplateEngineOutput(
        a2ui=compilation.a2ui,
        terse_dsl_nested2=compilation.effective_output,
        projected_task_spec=projected_task_spec,
        template_ids=tuple(compilation.stats.template_used_ids),
        trusted_internal_asset_sources=trusted_sources,
        expanded_component_count=compilation.stats.expanded_component_count,
        theme_id=projection.theme_id,
    )


async def _generate_hybrid_body(
    model_client: Any,
    messages: list[dict[str, str]],
    *,
    phase: str,
) -> str:
    profile = {"id": TERSE_DSL_NESTED2_PROFILE_ID, "format": "hybrid-card"}
    generate = model_client.generate
    parameters = inspect.signature(generate).parameters
    accepts_keywords = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    kwargs = {"phase": phase, "suppress_prompt_log": True} if accepts_keywords else {}
    result = generate(messages, profile, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _with_provider_template_binding_projection(
    source: TaskSpec,
    projected: TaskSpec,
    card_spec: dict[str, Any],
    component_ids: tuple[str, ...],
    registry: CardPlanRegistry,
) -> TaskSpec:
    schema = deepcopy(projected.dataModelSchema)
    changed = False
    for component_id in component_ids:
        capability = registry.require_ux_business_component(component_id)
        if capability.implementation != "template":
            continue
        for template_id in registry.enabled_template_ids(capability.local_template_ids):
            definition = registry.require_template(template_id)
            if definition.source_format != "cardtpl/1" or not definition.capability_id:
                continue
            root = _provider_binding_root(card_spec, definition.capability_id)
            if root is None:
                continue
            data = schema.get("data")
            component_projection = (
                data.pop(component_id, None) if isinstance(data, dict) else None
            )
            if isinstance(component_projection, dict):
                projection_path = (
                    f"{root.rstrip('/')}/_templateProjection/{component_id}"
                )
                _set_pointer_value(schema, projection_path, component_projection)
                changed = True
            provider_paths = tuple(
                dict.fromkeys(
                    (
                        *definition.required_data,
                        *definition.optional_data,
                        *(binding.path for binding in definition.bindings.values()),
                    )
                )
            )
            for relative_path in provider_paths:
                path = f"{root.rstrip('/')}{relative_path}"
                value = _pointer_value(source.dataModelSchema, path)
                if value is None:
                    continue
                _set_pointer_value(schema, path, deepcopy(value))
                changed = True
    for path in _event_binding_paths(source):
        value = _pointer_value(source.dataModelSchema, path)
        if value is None:
            continue
        _set_pointer_value(schema, path, deepcopy(value))
        changed = True
    if not changed:
        return projected
    return projected.model_copy(update={"dataModelSchema": schema})


def _event_binding_paths(task_spec: TaskSpec) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            path
            for event in task_spec.eventCandidates
            for path in _value_binding_paths(event.args)
            if path == "/data" or path.startswith("/data/")
        )
    )


def _value_binding_paths(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(expression_references(value))
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            return (value["path"],)
        return tuple(
            path
            for child in value.values()
            for path in _value_binding_paths(child)
        )
    if isinstance(value, list):
        return tuple(path for child in value for path in _value_binding_paths(child))
    return ()


def _provider_binding_root(
    card_spec: dict[str, Any],
    capability_id: str,
) -> str | None:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return None
    roots = {
        item.get("writeResultTo")
        for item in bindings
        if isinstance(item, dict)
        and item.get("capabilityId") == capability_id
        and _valid_provider_binding_root(item.get("writeResultTo"))
    }
    return next(iter(roots)) if len(roots) == 1 else None


def _valid_provider_binding_root(value: Any) -> bool:
    return isinstance(value, str) and (value == "/data" or value.startswith("/data/"))


def _pointer_value(value: Any, pointer: str) -> Any | None:
    current = value
    for part in _pointer_parts(pointer):
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
            continue
        return None
    return current


def _set_pointer_value(root: dict[str, Any], pointer: str, value: Any) -> None:
    _set_pointer_parts(root, _pointer_parts(pointer), value)


def _set_pointer_parts(current: Any, parts: tuple[str, ...], value: Any) -> None:
    part = parts[0]
    if isinstance(current, dict):
        if len(parts) == 1:
            current[part] = value
            return
        expected_type = list if parts[1].isdigit() else dict
        child = current.get(part)
        if not isinstance(child, expected_type):
            child = expected_type()
            current[part] = child
        _set_pointer_parts(child, parts[1:], value)
        return
    if not isinstance(current, list) or not part.isdigit():
        return
    index = int(part)
    while len(current) <= index:
        current.append(None)
    if len(parts) == 1:
        current[index] = value
        return
    expected_type = list if parts[1].isdigit() else dict
    child = current[index]
    if not isinstance(child, expected_type):
        child = expected_type()
        current[index] = child
    _set_pointer_parts(child, parts[1:], value)


def _pointer_parts(pointer: str) -> tuple[str, ...]:
    return tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.removeprefix("/").split("/")
    )


def _card_spec_capability_ids(card_spec: dict[str, Any]) -> tuple[str, ...]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return ()
    return tuple(
        capability_id
        for binding in bindings
        if isinstance(binding, dict)
        for capability_id in (binding.get("capabilityId"),)
        if isinstance(capability_id, str)
    )
