"""Search CardTpl candidates from first-layer LLM field requirements.

Search deliberately does not select a final template, layout, component composition,
card size, or theme compatibility. Those are second-layer responsibilities. The 2x2
route admits one business with zero to two root Actions, or exactly two businesses with
one root Action when HeroTitle/HeroContent coverage is complete.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.logger import json_for_log, logger
from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteSelection,
)

from .registry import CardPlanRegistry
from .retrieval_index import FieldToken, TemplateVariantSearchRecord

_MAX_COMPONENT_TEMPLATE_CANDIDATES = 24


class TemplateRetrievalMiss(ValueError):
    """No provider-backed component can cover the first-layer request."""


class TemplateRetrievalQuery(BaseModel):
    """The first-layer decision: theme, display demands, and explicit Action."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    theme_id: str = Field(alias="themeId", min_length=1)
    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="action", max_length=2)

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

    @field_validator("action_ids", mode="before")
    @classmethod
    def normalized_actions(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        values = (value,) if isinstance(value, str) else tuple(value)
        normalized = tuple(item.strip() for item in values if isinstance(item, str))
        if len(normalized) != len(values) or any(not item for item in normalized):
            raise ValueError("action must contain only non-empty eventIds")
        if len(normalized) != len(set(normalized)):
            raise ValueError("action eventIds must be unique")
        return normalized


def build_template_retrieval_prompt(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, str]]:
    """Build the first-layer marker prompt without exposing final UI choices."""
    _require_supported_search_size(task_spec)
    data_shape = extract_data_shape(task_spec)
    capability_ids = tuple(binding.capabilityId for binding in coverage_bindings)
    component_ids = _component_ids_for_capabilities(registry, capability_ids)
    theme_ids = registry.first_layer_theme_ids(component_ids)
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
        "themes": theme_ids,
        "actionCandidates": [
            {"eventId": event.id, "call": event.call}
            for event in task_spec.eventCandidates
            if event.id
        ],
        "providerFirstLayerRules": registry.provider_first_layer_rules(component_ids, data_roots),
        "themeFirstLayerRules": registry.theme_first_layer_rule_documents(theme_ids),
    }
    schema = TemplateRetrievalQuery.model_json_schema(by_alias=True)
    system = (
        "你是模板生成第一层。只输出 template-retrieval-query/1 JSON。"
        "themeId 必须从 themes 选择；themes 已由服务按当前业务确定性过滤，"
        "存在融球候选时不会再包含非融球主题。"
        "双业务单动作组合在 Search 确定 HeroContent 后，由服务端按该主业务对齐全局主题。"
        "requiredOutputFieldsByCapability 的 key 必须来自 "
        "candidateDataBindings。每个 value 仅保留 userQuery、title、description 或 taskSpec "
        "明确要求展示的字段，字段必须逐字来自 "
        "candidateOutputFieldsByCapability；不得按模板反推字段，"
        "也不得补全用户未要求展示的字段；"
        "事件参数（如 actionCandidates args 中用于跳转的 entityId）不是展示字段，"
        "不得加入 requiredOutputFieldsByCapability。"
        "不得为了迁就布局限制而省略用户明确要求的其他业务字段；"
        "2x2 模板 Search 接受一个可完整覆盖的业务，或恰好两个数据业务加一个显式 Action；"
        "双业务仅在服务端能够分别证明 HeroTitle 与 HeroContent 完整覆盖时适用，"
        "业务位置与布局由服务端确定，不得在本层输出。"
        "用户只要求某领域卡片、未明确字段时，该 capability 输出空数组。"
        "action 仅当用户明确要求点击、跳转或操作时才选择 actionCandidates 中"
        "语义一致的零到两个不重复 eventId；不能因候选事件存在而默认选择。"
        "不得输出组件、模板、Variant、尺寸、布局、Props 或理由。\n"
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
    *,
    preferred_template_ids: tuple[str, ...] = (),
) -> TemplateRouteSelection:
    """Return component candidate sets; never choose a final CardTpl variant."""
    _require_supported_search_size(task_spec)
    selected_theme = registry.require_theme(query.theme_id)
    if selected_theme.supported_layout_ids:
        raise TemplateRetrievalMiss("first-layer Theme must not be layout-scoped")
    _validate_selected_actions(query, task_spec)
    action_count = _selected_action_count(query, task_spec)
    if not query.required_output_fields_by_capability:
        raise TemplateRetrievalMiss("template retrieval has no requested capability")
    has_multiple_capabilities = len(query.required_output_fields_by_capability) > 1
    preferred_layout_suffix = None
    if not has_multiple_capabilities:
        preferred_layout_suffix = {1: "Hero", 2: "Compact"}.get(action_count)
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
        action_param_paths = _action_param_paths_to_drop(
            task_spec,
            registry,
            capability_id,
            data_root,
            paths,
        )
        if action_param_paths:
            _log_action_param_fields_dropped(capability_id, data_root, action_param_paths)
        query_tokens = frozenset(
            _task_spec_field_token(task_spec, data_root, capability_id, path)
            for path in paths
            if path not in action_param_paths
        )
        component_templates = _component_templates_for_capability(
            registry,
            capability_id,
            query_tokens,
            task_spec,
            card_spec,
            preferred_template_ids,
            preferred_layout_suffix,
            candidate_output_fields=candidate_paths,
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
    resolved_theme_id = query.theme_id
    if task_spec.size == "2x2":
        candidates, required_groups = _apply_2x2_combination_policy(
            candidates,
            action_count,
            required_groups,
        )
    else:
        if len(candidates) > 1:
            raise TemplateRetrievalMiss(
                "template Search supports one data business with optional Actions"
            )
        candidates = tuple(
            _candidate_with_complete_field_coverage(candidate, required_groups)
            for candidate in candidates
        )
        required_groups = [candidate.available_template_ids for candidate in candidates]
    selected_template_ids: list[str] = []
    for candidate in candidates:
        selected_template_ids.extend(candidate.available_template_ids)
    resolved_theme_id = (
        registry.hero_content_theme_id(tuple(selected_template_ids), query.theme_id)
        or resolved_theme_id
    )
    scope = AdvancedScopeBrief(
        themeId=resolved_theme_id,
        advancedComponentIds=tuple(candidate.component_id for candidate in candidates),
    )
    return TemplateRouteSelection(
        scope=scope,
        componentCandidates=candidates,
        actionIds=query.action_ids,
        requiredTemplateGroups=tuple(required_groups),
    )


def restrict_query_to_preferred_templates(
    query: TemplateRetrievalQuery,
    registry: CardPlanRegistry,
    preferred_template_ids: tuple[str, ...],
) -> TemplateRetrievalQuery:
    """Keep gallery-only field demand within its explicitly trusted templates."""
    if not preferred_template_ids:
        return query
    preferred_ids = set(preferred_template_ids)
    available_paths_by_capability: dict[str, set[str]] = {}
    matched_ids: set[str] = set()
    for record in registry.template_variant_search_records:
        if record.template_id not in preferred_ids:
            continue
        matched_ids.add(record.template_id)
        available_paths_by_capability.setdefault(record.capability_id, set()).update(
            record.available_paths
        )
    if matched_ids != preferred_ids:
        raise TemplateRetrievalMiss("trusted template candidate is outside Search records")
    required_fields = {
        capability_id: tuple(
            path
            for path in paths
            if path in available_paths_by_capability.get(capability_id, set())
        )
        for capability_id, paths in query.required_output_fields_by_capability.items()
    }
    return query.model_copy(
        update={"required_output_fields_by_capability": required_fields}
    )


def _require_supported_search_size(task_spec: TaskSpec) -> None:
    """Reject card sizes that are not yet supported by Provider Template Search."""
    if task_spec.size == "2x4":
        raise TemplateRetrievalMiss("template Search does not support 2x4 cards")


def _apply_2x2_combination_policy(
    candidates: tuple[TemplateComponentCandidate, ...],
    action_count: int,
    required_groups: list[tuple[str, ...]],
) -> tuple[tuple[TemplateComponentCandidate, ...], list[tuple[str, ...]]]:
    """Restrict 2x2 candidates to the business and Action capacity contract."""
    component_count = len(candidates)
    if component_count > 1:
        return _apply_2x2_dual_business_policy(
            candidates,
            action_count,
            required_groups,
        )
    if action_count >= 3:
        raise TemplateRetrievalMiss("2x2 template Search supports at most two Actions")
    if component_count == 1:
        layout_suffixes = {
            0: ("Full",),
            1: ("Hero", "Full"),
            2: ("Compact",),
        }[action_count]
    else:
        raise TemplateRetrievalMiss("template Search found no business component")

    business_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        business_candidates.append(
            {
                "businessId": candidate.component_id,
                "availableTemplateIds": list(candidate.available_template_ids),
            }
        )
    layout_label = "/".join(layout_suffixes)
    layout_diagnostics = {
        "businessCount": component_count,
        "actionCount": action_count,
        "requiredLayoutSuffixes": list(layout_suffixes),
        "requiredLayoutLabel": layout_label,
        "businessCandidates": business_candidates,
    }
    logger.info(
        "[Template Retrieval] layout_policy_selected "
        f"diagnostics={json_for_log(layout_diagnostics)}"
    )

    filtered_candidates = tuple(
        _candidate_with_layout_suffixes(candidate, layout_suffixes) for candidate in candidates
    )
    allowed_template_ids = {
        template_id
        for candidate in filtered_candidates
        for template_id in candidate.available_template_ids
    }
    filtered_groups = [
        tuple(template_id for template_id in group if template_id in allowed_template_ids)
        for group in required_groups
    ]
    if any(not group for group in filtered_groups):
        diagnostics = {
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredTemplateGroupsBeforeLayout": [list(group) for group in required_groups],
            "requiredTemplateGroupsAfterLayout": [list(group) for group in filtered_groups],
            "layoutCompatibleTemplateIds": sorted(allowed_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_field_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_label} templates cannot cover all requested fields"
        )
    for candidate in filtered_candidates:
        _require_single_template_coverage(candidate, filtered_groups, layout_label)
    return filtered_candidates, filtered_groups


def _apply_2x2_dual_business_policy(
    candidates: tuple[TemplateComponentCandidate, ...],
    action_count: int,
    required_groups: list[tuple[str, ...]],
) -> tuple[tuple[TemplateComponentCandidate, ...], list[tuple[str, ...]]]:
    """Resolve the only Search-supported dual-business shape and its slot order."""
    if len(candidates) != 2 or action_count != 1:
        raise TemplateRetrievalMiss(
            "2x2 template Search does not support multiple data businesses "
            "without exactly one Action"
        )
    for title_index, content_index in ((0, 1), (1, 0)):
        title_candidate = _candidate_with_optional_layout_suffix(
            candidates[title_index],
            "HeroTitle",
        )
        content_candidate = _candidate_with_optional_layout_suffix(
            candidates[content_index],
            "HeroContent",
        )
        if title_candidate is None or content_candidate is None:
            continue
        try:
            title_candidate = _candidate_with_complete_field_coverage(
                title_candidate,
                required_groups,
            )
            content_candidate = _candidate_with_complete_field_coverage(
                content_candidate,
                required_groups,
            )
        except TemplateRetrievalMiss:
            continue
        ordered_candidates = (title_candidate, content_candidate)
        ordered_groups = [
            title_candidate.available_template_ids,
            content_candidate.available_template_ids,
        ]
        diagnostics = {
            "businessCount": 2,
            "actionCount": 1,
            "layout": "HeroTitleContentActionLayout",
            "businessOrder": [
                {
                    "businessId": title_candidate.component_id,
                    "requiredLayoutSuffix": "HeroTitle",
                },
                {
                    "businessId": content_candidate.component_id,
                    "requiredLayoutSuffix": "HeroContent",
                },
            ],
        }
        logger.info(
            "[Template Retrieval] dual_business_layout_policy_selected "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        return ordered_candidates, ordered_groups
    raise TemplateRetrievalMiss(
        "2x2 template Search does not support multiple data businesses without complete "
        "HeroTitle and HeroContent coverage"
    )


def _candidate_with_optional_layout_suffix(
    candidate: TemplateComponentCandidate,
    layout_suffix: str,
) -> TemplateComponentCandidate | None:
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if _template_has_layout_suffix(template_id, layout_suffix)
    )
    if not template_ids:
        return None
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _selected_action_count(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> int:
    selected_action_ids = set(query.action_ids)
    count = 0
    for event in task_spec.eventCandidates:
        if event.id in selected_action_ids:
            count += 1
    return count


def _candidate_with_layout_suffixes(
    candidate: TemplateComponentCandidate,
    layout_suffixes: tuple[str, ...],
) -> TemplateComponentCandidate:
    matching_template_ids: list[str] = []
    for template_id in candidate.available_template_ids:
        has_layout_suffix = False
        for suffix in layout_suffixes:
            if _template_has_layout_suffix(template_id, suffix):
                has_layout_suffix = True
                break
        if has_layout_suffix:
            matching_template_ids.append(template_id)
    template_ids = tuple(matching_template_ids)
    if not template_ids:
        layout_label = "/".join(layout_suffixes)
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredLayoutLabel": layout_label,
            "availableTemplateIds": list(candidate.available_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_suffix_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 business {candidate.component_id} has no {layout_label} template"
        )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _require_single_template_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
    layout_suffix: str,
) -> None:
    """A 2x2 business slot must use one layout-compatible business template."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    if component_groups and not set.intersection(*component_groups):
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutLabel": layout_suffix,
            "availableTemplateIds": list(candidate.available_template_ids),
            "requiredTemplateGroups": [sorted(group) for group in component_groups],
        }
        logger.info(
            "[Template Retrieval] single_template_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_suffix} templates cannot cover one {candidate.component_id} slot"
        )


def _template_has_layout_suffix(template_id: str, layout_suffix: str) -> bool:
    """Match the declared business-template layout before its version suffix."""
    template_name, separator, version = template_id.rpartition("@")
    return bool(separator and version and template_name.endswith(layout_suffix))


def _candidate_with_complete_field_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
) -> TemplateComponentCandidate:
    """Keep only candidates that independently cover the first-layer display demand."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    complete_ids = set.intersection(*component_groups) if component_groups else candidate_ids
    if not complete_ids:
        raise TemplateRetrievalMiss(
            f"template candidates cannot cover one {candidate.component_id} slot"
        )
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if template_id in complete_ids
    )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _component_templates_for_capability(
    registry: CardPlanRegistry,
    capability_id: str,
    query_tokens: frozenset[FieldToken],
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
    candidate_output_fields: set[str] | None = None,
) -> dict[str, dict[str, frozenset[str]]]:
    result: dict[str, dict[str, frozenset[str]]] = {}
    data_root = _capability_data_root(card_spec, capability_id)
    provided_output_fields = candidate_output_fields or set()
    task_spec_available_fields = _task_spec_field_entries(task_spec, data_root)
    business_ids = {
        record.business_id
        for record in registry.template_variant_search_records
        if record.capability_id == capability_id
    }
    for business_id in sorted(business_ids):
        group = registry.ux_business_components[business_id]
        template_ids = set(registry.enabled_template_ids(group.local_template_ids))
        matches: dict[str, frozenset[str]] = {}
        evaluations: list[dict[str, Any]] = []
        for record in registry.template_variant_search_records:
            if record.capability_id != capability_id or record.business_id != business_id:
                continue
            evaluations.append(
                _template_record_evaluation(
                    record,
                    task_spec,
                    data_root,
                    query_tokens,
                    template_ids,
                )
            )
            if record.template_id not in template_ids:
                continue
            size_is_supported = not record.supported_card_sizes
            size_is_supported = size_is_supported or task_spec.size in record.supported_card_sizes
            if not size_is_supported:
                continue
            if not _template_required_fields_are_available(record, task_spec, card_spec):
                continue
            matches[record.template_id] = _record_available_query_paths(record, query_tokens)
        if query_tokens:
            matches = {template_id: paths for template_id, paths in matches.items() if paths}
        limited_matches: dict[str, frozenset[str]] = {}
        if matches:
            limited_matches = _limit_component_templates(
                matches,
                registry.enabled_template_ids(group.local_template_ids),
                query_tokens,
                preferred_template_ids,
                preferred_layout_suffix,
            )
            result[business_id] = limited_matches
        _log_template_candidate_evaluation(
            capability_id=capability_id,
            business_id=business_id,
            data_root=data_root,
            card_size=task_spec.size,
            user_required_fields=_field_entries_for_tokens(query_tokens),
            candidate_output_fields=provided_output_fields,
            task_spec_available_fields=task_spec_available_fields,
            disabled_provider_ids=set(getattr(registry, "disabled_provider_ids", ())),
            disabled_template_ids=set(getattr(registry, "disabled_template_ids", ())),
            evaluations=evaluations,
            matches=matches,
            limited_matches=limited_matches,
        )
    covered_paths: set[str] = set()
    for templates in result.values():
        for paths in templates.values():
            covered_paths.update(paths)
    if not {token.path for token in query_tokens}.issubset(covered_paths):
        return {}
    return result


def _limit_component_templates(
    matches: dict[str, frozenset[str]],
    declared_template_ids: tuple[str, ...],
    query_tokens: frozenset[FieldToken],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
) -> dict[str, frozenset[str]]:
    """Keep the upstream candidate bound without dropping field coverage."""
    selected = [
        template_id
        for template_id in preferred_template_ids
        if template_id in matches
    ]
    layout_matches: list[str] = []
    if preferred_layout_suffix is not None:
        for template_id in declared_template_ids:
            if template_id not in matches:
                continue
            if not _template_has_layout_suffix(template_id, preferred_layout_suffix):
                continue
            layout_matches.append(template_id)
    for token in sorted(query_tokens):
        template_id = next(
            (item for item in layout_matches if token.path in matches[item]),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    if not query_tokens and layout_matches:
        selected.append(layout_matches[0])
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
    selected = selected[:_MAX_COMPONENT_TEMPLATE_CANDIDATES]
    return {template_id: matches[template_id] for template_id in selected}


def _template_record_evaluation(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    data_root: str,
    query_tokens: frozenset[FieldToken],
    enabled_template_ids: set[str],
) -> dict[str, Any]:
    """构造单模板的字段覆盖诊断，不记录用户数据值。"""
    missing_required_fields: list[str] = []
    required_type_mismatches: list[dict[str, str]] = []
    required_types = {token.path: token.data_type for token in record.required_field_tokens}
    for path in sorted(record.required_paths):
        pointer = f"{data_root.rstrip('/')}{path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None:
            missing_required_fields.append(path)
            continue
        expected_type = required_types.get(path)
        actual_type = leaf.get("type")
        if expected_type is None or actual_type == expected_type:
            continue
        required_type_mismatches.append(
            {
                "path": path,
                "expectedType": expected_type,
                "actualType": actual_type if isinstance(actual_type, str) else "",
            }
        )

    matched_user_fields = _record_available_query_paths(record, query_tokens)
    unmatched_user_fields = sorted(token.path for token in query_tokens)
    unmatched_user_fields = [
        path for path in unmatched_user_fields if path not in matched_user_fields
    ]
    user_type_mismatches = _user_required_type_mismatches(record, query_tokens)
    rejection_reasons: list[str] = []
    if record.template_id not in enabled_template_ids:
        rejection_reasons.append("template_disabled")
    size_is_supported = not record.supported_card_sizes
    size_is_supported = size_is_supported or task_spec.size in record.supported_card_sizes
    if not size_is_supported:
        rejection_reasons.append("card_size_not_supported")
    if missing_required_fields:
        rejection_reasons.append("user_provided_data_missing_template_required_fields")
    if required_type_mismatches:
        rejection_reasons.append("user_provided_data_type_mismatch")
    if query_tokens and not matched_user_fields:
        rejection_reasons.append("user_required_data_not_covered")

    return {
        "templateId": record.template_id,
        "templateEnabled": record.template_id in enabled_template_ids,
        "supportedCardSizes": sorted(record.supported_card_sizes),
        "matchedUserRequiredFields": sorted(matched_user_fields),
        "unmatchedUserRequiredFields": unmatched_user_fields,
        "missingTemplateRequiredFields": missing_required_fields,
        "templateRequiredFieldTypeMismatches": required_type_mismatches,
        "userRequiredFieldTypeMismatches": user_type_mismatches,
        "userRequiredDataFullyCovered": not unmatched_user_fields,
        "userProvidedDataSatisfiesTemplateRequirements": (
            not missing_required_fields and not required_type_mismatches
        ),
        "rejectionReasons": rejection_reasons,
    }


def _user_required_type_mismatches(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> list[dict[str, str]]:
    template_types = {token.path: token.data_type for token in record.field_tokens}
    mismatches: list[dict[str, str]] = []
    for token in sorted(query_tokens):
        expected_type = template_types.get(token.path)
        if expected_type is None or expected_type == token.data_type:
            continue
        mismatches.append(
            {
                "path": token.path,
                "templateType": expected_type,
                "userDataType": token.data_type,
            }
        )
    return mismatches


def _field_entries_for_tokens(tokens: frozenset[FieldToken]) -> list[dict[str, str]]:
    return [{"path": token.path, "type": token.data_type} for token in sorted(tokens)]


def _task_spec_field_entries(task_spec: TaskSpec, data_root: str) -> list[dict[str, str]]:
    prefix = f"{data_root.rstrip('/')}/"
    entries: list[dict[str, str]] = []
    for field in extract_data_shape(task_spec).fields:
        if not field.path.startswith(prefix):
            continue
        relative_path = f"/{field.path.removeprefix(prefix)}"
        entries.append({"path": relative_path, "type": field.data_type})
    return sorted(entries, key=lambda item: item.get("path", ""))


def _log_template_candidate_evaluation(
    *,
    capability_id: str,
    business_id: str,
    data_root: str,
    card_size: str,
    user_required_fields: list[dict[str, str]],
    candidate_output_fields: set[str],
    task_spec_available_fields: list[dict[str, str]],
    disabled_provider_ids: set[str],
    disabled_template_ids: set[str],
    evaluations: list[dict[str, Any]],
    matches: dict[str, frozenset[str]],
    limited_matches: dict[str, frozenset[str]],
) -> None:
    eligible_ids = list(matches)
    selected_ids = list(limited_matches)
    selected_set = set(selected_ids)
    dropped_ids = [template_id for template_id in eligible_ids if template_id not in selected_set]
    for evaluation in evaluations:
        template_id = evaluation.get("templateId")
        is_eligible = isinstance(template_id, str) and template_id in matches
        is_selected = isinstance(template_id, str) and template_id in limited_matches
        evaluation.update(
            {
                "eligibleBeforeCandidateLimit": is_eligible,
                "selectedAfterCandidateLimit": is_selected,
            }
        )
        if not is_eligible or is_selected:
            continue
        reasons = evaluation.get("rejectionReasons")
        if isinstance(reasons, list):
            reasons.append("candidate_limit_exceeded")

    diagnostics = {
        "capabilityId": capability_id,
        "businessId": business_id,
        "dataRoot": data_root,
        "cardSize": card_size,
        "userRequiredFields": user_required_fields,
        "candidateOutputFields": sorted(candidate_output_fields),
        "taskSpecAvailableFields": task_spec_available_fields,
        "disabledProviderIds": sorted(disabled_provider_ids),
        "disabledTemplateIds": sorted(disabled_template_ids),
        "eligibleTemplateIdsBeforeLimit": eligible_ids,
        "selectedTemplateIdsAfterLimit": selected_ids,
        "droppedByCandidateLimit": dropped_ids,
        "templates": evaluations,
    }
    logger.info(
        "[Template Retrieval] candidate_evaluation "
        f"diagnostics={json_for_log(diagnostics)}"
    )


def _required_field_template_groups(
    query_tokens: frozenset[FieldToken],
    component_templates: dict[str, dict[str, frozenset[str]]],
) -> tuple[tuple[str, ...], ...]:
    if not query_tokens:
        template_ids: set[str] = set()
        for templates in component_templates.values():
            template_ids.update(templates)
        return (tuple(sorted(template_ids)),)
    groups: list[tuple[str, ...]] = []
    for token in sorted(query_tokens):
        matching_template_ids: list[str] = []
        for templates in component_templates.values():
            for template_id, paths in templates.items():
                if token.path in paths:
                    matching_template_ids.append(template_id)
        groups.append(tuple(sorted(matching_template_ids)))
    return tuple(groups)


def _component_ids_for_capabilities(
    registry: CardPlanRegistry,
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    wanted = set(capability_ids)
    return tuple(
        business_id
        for business_id, component in registry.ux_business_components.items()
        if wanted.intersection(component.data_capability_ids)
    )


def _candidate_paths(
    coverage_bindings: tuple[CandidateDataBinding, ...], capability_id: str
) -> set[str]:
    matching = [item for item in coverage_bindings if item.capabilityId == capability_id]
    if len(matching) != 1:
        raise TemplateRetrievalMiss("template retrieval requires one binding per capability")
    return set(matching[0].candidateOutputFields)


_ACTION_ARG_PATH_PATTERN = re.compile(r"\$\{\s*(/[^{}]+?)\s*\}")


def _action_param_paths_to_drop(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    capability_id: str,
    data_root: str,
    required_paths: tuple[str, ...],
) -> set[str]:
    """识别不应阻塞模板覆盖门禁的事件参数字段。

    第一层可能在 requiredOutputFieldsByCapability 中误列事件 args 引用的字段
    （如跳转参数 entityId）；展开时 compiler 只逐字复制 args，模板永远不渲染
    这些字段，因此当没有任何模板可展示它们时不让覆盖门禁失败。
    """
    action_bound_paths = _action_bound_relative_paths(task_spec, data_root)
    candidates = action_bound_paths.intersection(required_paths)
    if not candidates:
        return set()
    displayable_paths: set[str] = set()
    for record in registry.template_variant_search_records:
        if record.capability_id != capability_id:
            continue
        for path in record.available_paths:
            displayable_paths.add(path)
    return {path for path in candidates if path not in displayable_paths}


def _action_bound_relative_paths(task_spec: TaskSpec, data_root: str) -> set[str]:
    prefix = f"{data_root.rstrip('/')}/"
    relative_paths: set[str] = set()
    for event in task_spec.eventCandidates:
        for value in _action_arg_string_values(event.args):
            for match in _ACTION_ARG_PATH_PATTERN.finditer(value):
                pointer = match.group(1)
                if pointer.startswith(prefix):
                    relative_paths.add(f"/{pointer.removeprefix(prefix)}")
    return relative_paths


def _action_arg_string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _action_arg_string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _action_arg_string_values(item)


def _log_action_param_fields_dropped(
    capability_id: str,
    data_root: str,
    dropped_paths: set[str],
) -> None:
    logger.info(
        "[Template Retrieval] action_param_fields_dropped "
        f"diagnostics={json_for_log(
            {
                'capabilityId': capability_id,
                'dataRoot': data_root,
                'droppedFields': sorted(dropped_paths),
                'reason': 'event args bind these fields; templates never render them',
            }
        )}"
    )


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
    available_paths: set[str] = set()
    for token in query_tokens:
        if token.path not in record.available_paths:
            continue
        expected_type = typed_by_path.get(token.path, token.data_type)
        if expected_type == token.data_type:
            available_paths.add(token.path)
    return frozenset(available_paths)


def _validate_selected_actions(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> None:
    if not query.action_ids:
        return
    action_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if not set(query.action_ids).issubset(action_ids):
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
