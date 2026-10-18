"""Precomputed CardTpl Variant records for exact in-memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .models import CARDTPL_SOURCE_FORMATS, TemplateDefinition, TemplateVariant


@dataclass(frozen=True, order=True)
class FieldToken:
    capability_id: str
    path: str
    data_type: str


@dataclass(frozen=True)
class TemplateVariantSearchRecord:
    capability_id: str
    business_id: str
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
    binding_count: int = 1
    required_any_of: tuple[tuple[str, ...], ...] = ()
    display_together: tuple[tuple[str, ...], ...] = ()


def build_template_variant_search_records(
    templates: dict[str, TemplateDefinition],
) -> tuple[TemplateVariantSearchRecord, ...]:
    records: list[TemplateVariantSearchRecord] = []
    for definition in templates.values():
        capability_id = definition.capability_id
        business_id = definition.business_id
        if definition.source_format not in CARDTPL_SOURCE_FORMATS:
            continue
        if capability_id is None or business_id is None:
            continue
        for variant in definition.variants:
            records.append(_build_record(definition, variant, capability_id, business_id))
    return tuple(records)


def _build_record(
    definition: TemplateDefinition,
    variant: TemplateVariant,
    capability_id: str,
    business_id: str,
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
        business_id=business_id,
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
        binding_count=definition.binding_count,
        required_any_of=definition.required_any_of,
        display_together=definition.display_together,
    )


def missing_any_of_groups(
    record: TemplateVariantSearchRecord, available: set[str],
) -> tuple[tuple[str, ...], ...]:
    return tuple(group for group in record.required_any_of if not available.intersection(group))


def effective_display_record(
    record: TemplateVariantSearchRecord, available: set[str],
) -> TemplateVariantSearchRecord:
    """仅将本轮实际可显示的字段计入覆盖；不改变原始注册记录。"""
    if not record.display_together:
        return record
    displayed = set(record.available_paths).intersection(available)
    for group in record.display_together:
        if not set(group).issubset(available):
            displayed.difference_update(group)
    return replace(record, available_paths=frozenset(displayed))
