"""Search CardTpl candidates from first-layer LLM field requirements.

Search deliberately does not select a final template, layout, component composition,
card size, or theme compatibility.  Those are second-layer responsibilities.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteSelection,
)

from .registry import CardPlanRegistry
from .retrieval_index import FieldToken, TemplateVariantSearchRecord


class TemplateRetrievalMiss(ValueError):
    """No provider-backed component can cover the first-layer request."""


class TemplateRetrievalQuery(BaseModel):
    """The first-layer decision: theme, display demands, and explicit Action."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    theme_id: str = Field(alias="themeId", min_length=1)
    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )
    action_id: str | None = Field(default=None, alias="action")

    @field_validator("required_output_fields_by_capability")
    @classmethod
    def valid_fields(cls, values: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        pattern = re.compile(r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
        for capability_id, paths in values.items():
            if not capability_id.strip() or len(paths) != len(set(paths)):
                raise ValueError("capability IDs and output fields must be unique")
            if any(pattern.fullmatch(path) is None for path in paths):
                raise ValueError("required output fields must be JSON Pointers")
        return values

    @field_validator("action_id")
    @classmethod
    def normalized_action(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("action must be null or a non-empty eventId")
        return normalized


def build_template_retrieval_prompt(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, str]]:
    """Build the first-layer marker prompt without exposing final UI choices."""
    data_shape = extract_data_shape(task_spec)
    capability_ids = tuple(binding.capabilityId for binding in coverage_bindings)
    component_ids = _component_ids_for_capabilities(registry, capability_ids)
    data_roots = {binding.capabilityId: binding.writeResultTo for binding in coverage_bindings}
    payload = {
        "userQuery": task_spec.userQuery,
        "taskSpec": task_spec.model_dump(mode="json"),
        "taskSpecDataFields": [
            {
                "path": field.path,
                "name": field.name,
                "dataType": field.data_type,
                "description": field.description,
                "roles": field.roles,
            }
            for field in data_shape.fields
        ],
        "candidateDataBindings": [binding.model_dump(mode="json") for binding in coverage_bindings],
        "candidateOutputFieldsByCapability": {
            binding.capabilityId: tuple(binding.candidateOutputFields)
            for binding in coverage_bindings
        },
        "themes": tuple(registry.themes),
        "actionCandidates": [
            {"eventId": event.id, "call": event.call}
            for event in task_spec.eventCandidates
            if event.id
        ],
        "providerFirstLayerRules": registry.provider_first_layer_rules(component_ids, data_roots),
        "themeFirstLayerRules": registry.theme_first_layer_rule_documents(tuple(registry.themes)),
    }
    schema = TemplateRetrievalQuery.model_json_schema(by_alias=True)
    system = (
        "你是模板生成第一层。只输出 template-retrieval-query/1 JSON。"
        "themeId 必须从 themes 选择；requiredOutputFieldsByCapability 的 key 必须来自 "
        "candidateDataBindings。每个 value 仅保留用户明确要求展示的字段，字段必须逐字来自 "
        "candidateOutputFieldsByCapability；不得按模板反推字段，也不得补全用户未要求展示的字段。"
        "用户只要求某领域卡片、未明确字段时，该 capability 输出空数组。"
        "action 仅当用户明确要求点击、跳转或操作时才选择 actionCandidates 中语义一致的 eventId；"
        "不能因候选事件存在而默认选择。不得输出组件、模板、Variant、尺寸、布局、Props 或理由。\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def retrieve_template_variants(
    query: TemplateRetrievalQuery,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
) -> TemplateRouteSelection:
    """Return component candidate sets; never choose a final CardTpl variant."""
    registry.require_theme(query.theme_id)
    _validate_selected_action(query, task_spec)
    if not query.required_output_fields_by_capability:
        raise TemplateRetrievalMiss("template retrieval has no requested capability")
    candidate_ids = {binding.capabilityId for binding in coverage_bindings}
    if not set(query.required_output_fields_by_capability).issubset(candidate_ids):
        raise TemplateRetrievalMiss("requested capability is outside candidate data bindings")

    by_component: dict[str, set[str]] = {}
    required_groups: list[tuple[str, ...]] = []
    for capability_id, paths in query.required_output_fields_by_capability.items():
        candidate_paths = _candidate_paths(coverage_bindings, capability_id)
        if not set(paths).issubset(candidate_paths):
            raise TemplateRetrievalMiss("required output fields must come from candidates")
        data_root = _capability_data_root(card_spec, capability_id)
        query_tokens = frozenset(
            _task_spec_field_token(task_spec, data_root, capability_id, path) for path in paths
        )
        component_templates = _component_templates_for_capability(
            registry,
            capability_id,
            query_tokens,
            task_spec,
            card_spec,
        )
        if not component_templates:
            raise TemplateRetrievalMiss(
                f"no provider template covers capability {capability_id} and its requested fields"
            )
        required_groups.extend(_required_field_template_groups(query_tokens, component_templates))
        for component_id, template_paths in component_templates.items():
            by_component.setdefault(component_id, set()).update(template_paths)

    candidates = tuple(
        TemplateComponentCandidate(
            componentId=component_id,
            availableTemplateIds=tuple(sorted(template_ids)),
        )
        for component_id, template_ids in sorted(by_component.items())
    )
    scope = AdvancedScopeBrief(
        themeId=query.theme_id,
        advancedComponentIds=tuple(candidate.component_id for candidate in candidates),
    )
    return TemplateRouteSelection(
        scope=scope,
        componentCandidates=candidates,
        action_id=query.action_id,
        requiredTemplateGroups=tuple(required_groups),
    )


def _component_templates_for_capability(
    registry: CardPlanRegistry,
    capability_id: str,
    query_tokens: frozenset[FieldToken],
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
) -> dict[str, dict[str, frozenset[str]]]:
    result: dict[str, dict[str, frozenset[str]]] = {}
    for component in registry.ux_business_components.values():
        template_ids = set(registry.enabled_template_ids(component.local_template_ids))
        matches = {
            record.template_id: _record_available_query_paths(record, query_tokens)
            for record in registry.template_variant_search_records
            if record.capability_id == capability_id
            and record.template_id in template_ids
            and _template_required_fields_are_available(record, task_spec, card_spec)
        }
        if query_tokens:
            matches = {template_id: paths for template_id, paths in matches.items() if paths}
        if matches:
            result[component.name] = _limit_component_templates(
                matches,
                registry.enabled_template_ids(component.local_template_ids),
                query_tokens,
            )
    covered_paths = {
        path for templates in result.values() for paths in templates.values() for path in paths
    }
    if not {token.path for token in query_tokens}.issubset(covered_paths):
        return {}
    return result


def _limit_component_templates(
    matches: dict[str, frozenset[str]],
    declared_template_ids: tuple[str, ...],
    query_tokens: frozenset[FieldToken],
) -> dict[str, frozenset[str]]:
    """Keep the upstream candidate bound without dropping field coverage."""
    selected: list[str] = []
    for token in sorted(query_tokens):
        template_id = next(
            (
                item
                for item in declared_template_ids
                if item in matches and token.path in matches[item]
            ),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    selected.extend(
        template_id
        for template_id in declared_template_ids
        if template_id in matches and template_id not in selected
    )
    return {template_id: matches[template_id] for template_id in selected[:12]}


def _required_field_template_groups(
    query_tokens: frozenset[FieldToken],
    component_templates: dict[str, dict[str, frozenset[str]]],
) -> tuple[tuple[str, ...], ...]:
    if not query_tokens:
        template_ids = {
            template_id for templates in component_templates.values() for template_id in templates
        }
        return (tuple(sorted(template_ids)),)
    return tuple(
        tuple(
            sorted(
                template_id
                for templates in component_templates.values()
                for template_id, paths in templates.items()
                if token.path in paths
            )
        )
        for token in sorted(query_tokens)
    )


def _component_ids_for_capabilities(
    registry: CardPlanRegistry,
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    wanted = set(capability_ids)
    return tuple(
        component.name
        for component in registry.ux_business_components.values()
        if wanted.intersection(component.data_capability_ids)
    )


def _candidate_paths(
    coverage_bindings: tuple[CandidateDataBinding, ...], capability_id: str
) -> set[str]:
    matching = [item for item in coverage_bindings if item.capabilityId == capability_id]
    if len(matching) != 1:
        raise TemplateRetrievalMiss("template retrieval requires one binding per capability")
    return set(matching[0].candidateOutputFields)


def _capability_data_root(card_spec: dict[str, Any], capability_id: str) -> str:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        raise TemplateRetrievalMiss("CardSpec data bindings are unavailable")
    roots = {
        item.get("writeResultTo")
        for item in bindings
        if isinstance(item, dict) and item.get("capabilityId") == capability_id
    }
    valid = {root for root in roots if isinstance(root, str) and root.startswith("/data")}
    if len(valid) != 1:
        raise TemplateRetrievalMiss("capability data root is unavailable or ambiguous")
    return next(iter(valid))


def _task_spec_field_token(
    task_spec: TaskSpec, data_root: str, capability_id: str, relative_path: str
) -> FieldToken:
    pointer = f"{data_root.rstrip('/')}{relative_path}"
    leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
    if leaf is None or not isinstance(leaf.get("type"), str):
        raise TemplateRetrievalMiss(
            f"required output field is absent or untyped in TaskSpec: {relative_path}"
        )
    return FieldToken(capability_id, relative_path, str(leaf["type"]))


def _task_spec_schema_leaf(schema: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part == "0" and current:
            current = current[0]
        else:
            return None
    return current if isinstance(current, dict) else None


def _record_available_query_paths(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> frozenset[str]:
    typed_by_path = {token.path: token.data_type for token in record.field_tokens}
    return frozenset(
        token.path
        for token in query_tokens
        if token.path in record.available_paths
        and typed_by_path.get(token.path, token.data_type) == token.data_type
    )


def _validate_selected_action(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> None:
    if query.action_id is None:
        return
    action_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if query.action_id not in action_ids:
        raise TemplateRetrievalMiss("selected Action is outside TaskSpec.eventCandidates")


def _template_required_fields_are_available(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
) -> bool:
    data_root = _capability_data_root(card_spec, record.capability_id)
    for path in record.required_paths:
        pointer = f"{data_root.rstrip('/')}{path}"
        if _task_spec_schema_leaf(task_spec.dataModelSchema, pointer) is None:
            return False
    for token in record.required_field_tokens:
        pointer = f"{data_root.rstrip('/')}{token.path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None or leaf.get("type") != token.data_type:
            return False
    return True
