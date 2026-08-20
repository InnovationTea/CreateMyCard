"""Precomputed CardTpl Variant records for exact in-memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from .models import TemplateDefinition, TemplateVariant


@dataclass(frozen=True, order=True)
class FieldToken:
    capability_id: str
    path: str
    data_type: str


@dataclass(frozen=True)
class TemplateVariantSearchRecord:
    capability_id: str
    compatible_theme_ids: frozenset[str]
    template_id: str
    variant_name: str
    supported_card_sizes: frozenset[str]
    supported_roles: frozenset[str]
    available_paths: frozenset[str]
    required_paths: frozenset[str]
    field_tokens: frozenset[FieldToken]
    required_field_tokens: frozenset[FieldToken]
    required_parameter_count: int


def build_template_variant_search_records(
    templates: dict[str, TemplateDefinition],
) -> tuple[TemplateVariantSearchRecord, ...]:
    records: list[TemplateVariantSearchRecord] = []
    for definition in templates.values():
        capability_id = definition.capability_id
        if definition.source_format != "cardtpl/1" or capability_id is None:
            continue
        for variant in definition.variants:
            records.append(_build_record(definition, variant, capability_id))
    return tuple(records)


def _build_record(
    definition: TemplateDefinition,
    variant: TemplateVariant,
    capability_id: str,
) -> TemplateVariantSearchRecord:
    required_paths = set(definition.required_data)
    required_paths.update(
        definition.bindings[name].path
        for name in variant.required_bindings
        if name in definition.bindings
    )
    required_tokens = frozenset(
        FieldToken(capability_id, field.path, field.data_type)
        for field in definition.required_data_fields
    )
    all_fields = (*definition.required_data_fields, *definition.optional_data_fields)
    return TemplateVariantSearchRecord(
        capability_id=capability_id,
        compatible_theme_ids=frozenset(definition.compatible_theme_profile_ids),
        template_id=definition.wire_id,
        variant_name=variant.size,
        supported_card_sizes=frozenset(variant.supported_card_sizes),
        supported_roles=frozenset(variant.supported_roles),
        available_paths=frozenset((*definition.required_data, *definition.optional_data)),
        required_paths=frozenset(required_paths),
        field_tokens=frozenset(
            FieldToken(capability_id, field.path, field.data_type) for field in all_fields
        ),
        required_field_tokens=required_tokens,
        required_parameter_count=len(variant.parameters_schema.get("required", ())),
    )
