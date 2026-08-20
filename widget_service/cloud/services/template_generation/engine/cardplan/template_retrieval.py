"""Deterministic CardTpl Variant retrieval from LLM-extracted field requirements."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.data_shape import DataShape
from services.template_generation.engine.advanced.models import AdvancedScopeBrief

from .provider_bundle import provider_template_variant_admission
from .registry import CardPlanRegistry
from .retrieval_index import FieldToken, TemplateVariantSearchRecord


class TemplateRetrievalMiss(ValueError):
    """No single CardTpl Variant can satisfy the extracted requirement set."""


class TemplateRetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    route_version: str = Field(default="template-retrieval-query/1", alias="routeVersion")
    theme_id: str = Field(alias="themeId", min_length=1)
    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )

    @field_validator("required_output_fields_by_capability")
    @classmethod
    def valid_fields(cls, values: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        pattern = re.compile(r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
        for capability_id, paths in values.items():
            if not capability_id.strip() or not paths or len(paths) != len(set(paths)):
                raise ValueError("required output field groups must be non-empty and unique")
            if any(pattern.fullmatch(path) is None for path in paths):
                raise ValueError("required output fields must be JSON Pointers")
        return values


@dataclass(frozen=True)
class TemplateMatch:
    theme_id: str
    template_id: str
    variant_name: str


def adapt_template_match_to_scope(
    match: TemplateMatch,
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None,
) -> AdvancedScopeBrief:
    """Adapt retrieval output to the target branch's existing trusted scope contract."""
    from services.template_generation.engine.advanced.scope_planner import (
        resolve_available_capability_ids,
        validate_advanced_scope,
    )

    effective_ids = resolve_available_capability_ids(
        task_spec, registry, available_capability_ids
    )
    components = tuple(
        component
        for component in registry.ux_business_components.values()
        if match.template_id in component.local_template_ids
    )
    if len(components) != 1:
        raise TemplateRetrievalMiss("matched Template has no unique component adapter")
    component = components[0]
    compatible_themes = tuple(
        dict.fromkeys(
            theme_id
            for scene in component.palette_scenes
            for theme_id in registry.palette_scene_theme_ids[scene]
        )
    )
    if not compatible_themes:
        raise TemplateRetrievalMiss("matched component has no compatible Theme")
    theme_id = match.theme_id if match.theme_id in compatible_themes else compatible_themes[0]
    scope = AdvancedScopeBrief(
        themeId=theme_id,
        advancedComponentIds=(component.name,),
    )
    validate_advanced_scope(
        scope,
        task_spec,
        data_shape,
        registry,
        tuple(effective_ids),
    )
    return scope


def build_template_retrieval_prompt(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, str]]:
    candidate_fields = {
        item.capabilityId: tuple(item.candidateOutputFields) for item in coverage_bindings
    }
    payload = {
        "userQuery": task_spec.userQuery,
        "size": task_spec.size,
        "candidateOutputFieldsByCapability": candidate_fields,
        "themes": tuple(registry.themes),
    }
    schema = TemplateRetrievalQuery.model_json_schema(by_alias=True)
    return [
        {
            "role": "system",
            "content": (
                "只输出 template-retrieval-query/1 JSON。themeId 从 themes 选择；"
                "requiredOutputFieldsByCapability 只保留用户明确要求展示的字段，"
                "字段必须逐字来自 candidateOutputFieldsByCapability。不得按模板反推字段。\n"
                + json.dumps(schema, ensure_ascii=False)
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def retrieve_template_variant(
    query: TemplateRetrievalQuery,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
) -> TemplateMatch:
    return retrieve_template_variants(
        query, task_spec, registry, coverage_bindings, card_spec
    )[0]


def retrieve_template_variants(
    query: TemplateRetrievalQuery,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
) -> tuple[TemplateMatch, ...]:
    registry.require_theme(query.theme_id)
    groups = query.required_output_fields_by_capability
    if len(groups) != 1:
        raise TemplateRetrievalMiss("template retrieval requires exactly one capability")
    capability_id, paths = next(iter(groups.items()))
    if not paths:
        raise TemplateRetrievalMiss("template retrieval requires non-empty output fields")
    if not set(paths).issubset(_candidate_paths(coverage_bindings, capability_id)):
        raise TemplateRetrievalMiss("required output fields must come from candidates")
    data_root = _capability_data_root(card_spec, capability_id)
    query_tokens = frozenset(
        _task_spec_field_token(task_spec, data_root, capability_id, path) for path in paths
    )
    preferred_template_ids = _preferred_template_ids(registry, capability_id, task_spec)
    matches = [
        record
        for record in registry.template_variant_search_records
        if _record_matches(
            record,
            query_tokens,
            task_spec,
            registry,
            card_spec,
            preferred_template_ids,
        )
    ]
    if not matches:
        raise TemplateRetrievalMiss("no CardTpl Variant contains every required output field")
    ordered = sorted(
        matches,
        key=lambda record: (
            len(record.required_paths - {token.path for token in query_tokens}),
            record.required_parameter_count,
            _template_preference_rank(preferred_template_ids, record.template_id),
            record.template_id,
            record.variant_name,
        ),
    )
    return tuple(
        TemplateMatch(query.theme_id, record.template_id, record.variant_name)
        for record in ordered
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
    leaf = _task_spec_schema_leaf(
        task_spec.dataModelSchema, f"{data_root.rstrip('/')}{relative_path}"
    )
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


def _record_matches(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    card_spec: dict[str, Any],
    preferred_template_ids: tuple[str, ...],
) -> bool:
    capability_matches = all(token.capability_id == record.capability_id for token in query_tokens)
    if not capability_matches or record.template_id not in preferred_template_ids:
        return False
    if record.supported_card_sizes and task_spec.size not in record.supported_card_sizes:
        return False
    if record.supported_roles and "hero" not in record.supported_roles:
        return False
    if not {token.path for token in query_tokens}.issubset(record.available_paths):
        return False
    typed_by_path = {token.path: token.data_type for token in record.field_tokens}
    query_type_mismatch = any(
        typed_by_path.get(token.path, token.data_type) != token.data_type
        for token in query_tokens
    )
    if query_type_mismatch:
        return False
    if not _template_required_fields_are_available(record, task_spec, card_spec):
        return False
    definition = registry.require_template(record.template_id)
    variant = registry.require_variant(record.template_id, record.variant_name)
    return provider_template_variant_admission(
        definition, variant, task_spec, card_spec
    ).admitted


def _template_required_fields_are_available(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
) -> bool:
    data_root = _capability_data_root(card_spec, record.capability_id)
    for path in record.required_paths:
        leaf = _task_spec_schema_leaf(
            task_spec.dataModelSchema, f"{data_root.rstrip('/')}{path}"
        )
        if leaf is None:
            return False
    for token in record.required_field_tokens:
        leaf = _task_spec_schema_leaf(
            task_spec.dataModelSchema, f"{data_root.rstrip('/')}{token.path}"
        )
        if leaf is None or leaf.get("type") != token.data_type:
            return False
    return True


def _preferred_template_ids(
    registry: CardPlanRegistry,
    capability_id: str,
    task_spec: TaskSpec,
) -> tuple[str, ...]:
    from services.template_generation.engine.advanced.scope_planner import scope_template_ids

    components = tuple(
        component
        for component in registry.ux_business_components.values()
        if any(
            registry.require_template(template_id).capability_id == capability_id
            for template_id in component.local_template_ids
        )
    )
    if len(components) != 1:
        return ()
    component = components[0]
    theme_id = next(
        theme_id
        for scene in component.palette_scenes
        for theme_id in registry.palette_scene_theme_ids[scene]
    )
    scope = AdvancedScopeBrief(
        themeId=theme_id,
        advancedComponentIds=(component.name,),
    )
    return scope_template_ids(scope, registry, task_spec)


def _template_preference_rank(
    preferred_template_ids: tuple[str, ...], template_id: str
) -> int:
    return preferred_template_ids.index(template_id)
