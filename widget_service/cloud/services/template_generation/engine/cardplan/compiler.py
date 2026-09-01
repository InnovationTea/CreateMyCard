"""Trusted Template expansion, Hybrid Contract checks, and A2UI lowering."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from jsonschema import Draft202012Validator

from models.generation import TaskSpec
from services.template_generation.engine.a2ui_expression import (
    A2UIExpressionError,
    normalize_tersel_expression,
)
from services.template_generation.engine.advanced.content_selectors import (
    ActivityOverviewFacts,
    AppUsageOverviewFacts,
    BatteryOverviewFacts,
    BluetoothDeviceOverviewFacts,
    DateOverviewFacts,
    ResourceUsageOverviewFacts,
    ScheduleOverviewFacts,
    SleepOverviewFacts,
    WorkoutLatestFacts,
    activity_overview_variants,
    advanced_component_data_admission_is_relaxed,
    approved_schedule_focus_action_ids,
    extract_activity_overview_facts,
    extract_app_usage_overview_facts,
    extract_battery_overview_facts,
    extract_bluetooth_device_overview_facts,
    extract_date_overview_facts,
    extract_heart_rate_overview_facts,
    extract_resource_usage_overview_facts,
    extract_schedule_overview_facts,
    extract_sleep_overview_facts,
    extract_weather_overview_facts,
    extract_workout_latest_facts,
    heart_rate_overview_is_eligible,
    relaxed_activity_overview_variants,
    relaxed_workout_overview_variants,
    schedule_query_requests_focus,
    sleep_overview_variants,
    workout_overview_variants,
)
from services.template_generation.engine.advanced.models import (
    UX_DIRECT_BUSINESS_COMPONENT_IDS,
    UX_LAYOUT_COMPONENT_IDS,
    UxLayoutComponentCapability,
)
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    TerselConversionError,
    convert_tersel_to_a2ui,
    serialize_task_spec_data,
)

from .fusion_ball_background import (
    FusionBallPalette,
    apply_fusion_ball_background,
)
from .models import (
    TEMPLATE_CHILD_SLOT_COMPONENT,
    ExpansionStats,
    HybridBodyContract,
    TemplateDefinition,
    TemplateNode,
    TemplateParameterRelation,
    TemplateValue,
    TemplateVariant,
)
from .parser import ParsedCall, parse_hybrid_card, parse_ux_layout_card
from .provider_bundle import provider_template_family_identity, provider_template_layout_kind
from .registry import CardPlanRegistry

_STANDARD_CONTAINERS = frozenset({"Row", "Column", "List", "Stack"})
_CONTAINERS = _STANDARD_CONTAINERS | UX_LAYOUT_COMPONENT_IDS
_SINGLE_TEMPLATE_CONDITIONS = frozenset(
    {"IfParam", "IfMissingParam", "IfBind", "IfMissingBind"}
)
_GROUPED_TEMPLATE_CONDITIONS = frozenset({"IfAllBind", "IfAnyMissingBind"})
_TEMPLATE_CONDITIONS = _SINGLE_TEMPLATE_CONDITIONS | _GROUPED_TEMPLATE_CONDITIONS
_UX_ACTION_COMPONENTS = frozenset({"PillAction", "IconAction", "ActionTile"})
_ACTION_TEMPLATE_COMPONENTS = {
    "PillAction@1": "PillAction",
    "IconAction@1": "IconAction",
}
_ACTION_PROVIDER_ID = "com.huawei.action.cli"
_UX_DIRECT_BUSINESS_COMPONENTS = UX_DIRECT_BUSINESS_COMPONENT_IDS
_DANGEROUS_EVENT_KEYS = frozenset({"onClick", "call", "args", "action"})
_SUNNY_WEATHER_ICON_COLOR = "#FFFFC300"
_FONT_PRIMARY = "#E6000000"
_FONT_SECONDARY = "#99000000"
_ICON_SECONDARY = "#99000000"
_TRACK_COLOR = "#1A000000"
_NORMAL_DATA_COLOR = "#FF64BB5C"
_WARNING_DATA_COLOR = "#FFF9A01E"
_LAYOUT_ALIASES = {
    ("Column", "card"): "section",
    ("Column", "section-relaxed"): "section",
    ("Column", "metric-stack"): "section",
    ("Column", "dense"): "compact",
    ("Column", "action-bottom-compact"): "compact",
    ("Row", "icon-control-group"): "between",
    ("Row", "inline"): "between",
    ("Row", "section"): "between",
    ("Row", "compact"): "between",
    ("Stack", "ux-ring-medium"): "overlay",
    ("Stack", "ux-ring-small"): "overlay",
}


def _a2ui_component_types(a2ui: str) -> frozenset[str]:
    """Return component discriminators without inspecting business data values."""
    component_types: set[str] = set()
    for line in a2ui.splitlines():
        message = json.loads(line)
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        components = update.get("components")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            component_type = component.get("component")
            if isinstance(component_type, str):
                component_types.add(component_type)
    return frozenset(component_types)


_DESIGN_ALIASES = {
    ("Text", "caption"): "subtitle",
    ("Text", "metric-hero"): "title",
    ("Text", "status-alert"): "warning",
    ("Text", "ux-status-alert"): "warning",
    ("Text", "ux-time-compact"): "subtitle",
    ("Text", "ux-title-compact"): "compact-title",
    ("Image", "ux-glyph-sm"): "icon",
    ("Image", "ux-glyph-xs"): "icon",
    ("Button", "action-frosted"): "primary",
}
_COLOR_MODE_LITERAL = re.compile(
    r"^\{\{\s*\$__colorMode\s*==\s*'dark'\s*\?\s*'([^']+)'\s*:\s*'([^']+)'\s*\}\}$"
)


@dataclass(frozen=True)
class HybridCompilation:
    raw_output: str
    effective_output: str
    a2ui: str
    stats: ExpansionStats
    fallback_used: bool = False


@dataclass
class _ExpansionState:
    template_ids: list[str]
    action_ids: list[str]
    action_occurrences: list[str]
    template_calls: int = 0
    template_variant_normalizations: int = 0
    template_provider_param_normalizations: int = 0
    template_relation_number_normalizations: int = 0
    expanded_components: int = 0


def compile_hybrid_card(
    source: str,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    protocol_profile: dict[str, Any],
    registry: CardPlanRegistry,
    card_spec: dict[str, Any] | None = None,
    enable_data_bindings: bool = False,
) -> HybridCompilation:
    composition = parse_hybrid_card(source)
    raw_card_params = composition.values[0]
    if not isinstance(raw_card_params, dict):
        raise TerselConversionError("card@1 params must be an object.")
    card_params = _normalize_card_params(raw_card_params)
    _validate_card_params(card_params, task_spec, contract)
    _validate_ux_layout_root(
        composition.children[0],
        contract,
        size=task_spec.size,
        registry=registry,
    )
    raw_count = _count_calls(composition.children[0])
    if raw_count > contract.limits.max_raw_components:
        raise TerselConversionError("Hybrid raw component budget exceeded.")
    _reject_direct_events(composition.children[0])
    _validate_raw_components(composition.children[0], contract)
    normalized_content, provider_param_normalizations = _normalize_template_provider_params(
        composition.children[0],
        task_spec,
        contract,
        registry,
    )
    normalized_content, relation_number_normalizations = _normalize_template_relation_numbers(
        normalized_content,
        contract,
        registry,
    )
    composition = ParsedCall(
        composition.kind,
        composition.name,
        composition.values,
        (normalized_content,),
        composition.span,
    )
    _validate_required_numbers(composition.children[0], contract, task_spec)
    content_call = _strip_direct_card_chrome_from_call(
        composition.children[0],
        card_params,
    )
    content_call = _normalize_recommended_variant_order(content_call, registry)
    state = _ExpansionState(
        template_ids=[],
        action_ids=[],
        action_occurrences=[],
        template_provider_param_normalizations=provider_param_normalizations,
        template_relation_number_normalizations=relation_number_normalizations,
    )
    content = _expand_call(
        content_call,
        parent="$root",
        contract=contract,
        registry=registry,
        state=state,
        task_spec=task_spec,
        provider_binding_roots=_provider_binding_roots(card_spec),
    )
    content = _lower_ux_layouts(
        content,
        size=task_spec.size,
        has_action="action" in card_params,
        registry=registry,
    )
    content = _lower_capsule_progress(content)
    card_params = _drop_redundant_card_chrome(card_params, content)
    content = _deduplicate_visible_text(content, task_spec)
    content = _append_missing_required_literals(
        content,
        contract,
        already_visible=tuple(
            item for item in _primitive_values(card_params) if isinstance(item, str)
        ),
    )
    # Missing facts appended above can make an earlier composite subtitle fully
    # redundant. Re-run chrome ownership before measuring the body budget.
    card_params = _drop_redundant_card_chrome(card_params, content)
    card_params = _reclaim_optional_chrome_for_content(
        card_params,
        content,
        contract,
        registry,
    )
    fusion_palette = _template_fusion_ball_palette(
        task_spec.size,
        contract,
        registry,
        tuple(state.template_ids),
    )
    content_height = _estimate_height(content)
    root = _compile_card_shell(card_params, content, contract, registry)
    root = _apply_theme_content_color(root, contract, registry)
    card_action = card_params.get("action")
    if isinstance(card_action, dict):
        if card_action["id"] not in state.action_ids:
            state.action_ids.append(card_action["id"])
        state.action_occurrences.append(card_action["id"])
    expected_content_actions = Counter({item: 1 for item in contract.content_action_ids})
    actual_content_actions = Counter(state.action_occurrences)
    if isinstance(card_action, dict):
        actual_content_actions.subtract({card_action["id"]: 1})
        actual_content_actions += Counter()
    if actual_content_actions != expected_content_actions:
        raise TerselConversionError("Hybrid content Actions do not match the contract.")
    count, depth = _shape(root)
    if count > contract.limits.max_expanded_components:
        raise TerselConversionError("Hybrid expanded component budget exceeded.")
    if depth > contract.limits.max_nesting_depth:
        raise TerselConversionError("Hybrid component depth budget exceeded.")
    _validate_expanded_tree(root, contract)
    body_budget = _body_budget(card_params, contract, registry)
    space_constrained = content_height > body_budget
    if space_constrained:
        content = _constrain_content_height(content, body_budget)
        root = _compile_card_shell(card_params, content, contract, registry)
        root = _apply_theme_content_color(root, contract, registry)
    root = apply_fusion_ball_background(
        root,
        size=task_spec.size,
        palette=fusion_palette,
    )
    effective = _serialize_effective_document(root, task_spec, enable_data_bindings)
    a2ui = convert_tersel_to_a2ui(
        effective,
        size=task_spec.size,
        protocol_profile=protocol_profile,
        task_spec=task_spec.model_dump(mode="json") if enable_data_bindings else None,
    )
    component_types = _a2ui_component_types(a2ui)
    if "Template" in component_types:
        raise TerselConversionError("Template leaked into final A2UI.")
    if component_types & UX_LAYOUT_COMPONENT_IDS:
        raise TerselConversionError("UX Layout leaked into final A2UI.")
    return HybridCompilation(
        raw_output=source,
        effective_output=effective,
        a2ui=a2ui,
        stats=ExpansionStats(
            template_call_count=state.template_calls + 1,
            template_used_ids=tuple(state.template_ids),
            template_variant_normalization_count=state.template_variant_normalizations,
            template_provider_param_normalization_count=(
                state.template_provider_param_normalizations
            ),
            template_relation_number_normalization_count=(
                state.template_relation_number_normalizations
            ),
            expanded_component_count=count,
            raw_component_count=raw_count,
            max_depth=depth,
            estimated_height_vp=content_height,
            vertical_budget_vp=body_budget,
            space_constrained=space_constrained,
            action_used_ids=tuple(state.action_ids),
        ),
    )


def compile_ux_layout_card(
    source: str,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    protocol_profile: dict[str, Any],
    registry: CardPlanRegistry,
    business_title: str | None = None,
    card_spec: dict[str, Any] | None = None,
    enable_data_bindings: bool = False,
) -> HybridCompilation:
    """Compile the fifth-interface layout root without invoking ``card@1``.

    The model chooses one approved UX Layout plus trusted local Templates and a
    bounded Action node. The service still owns root geometry, event binding,
    Theme lowering, validation, and the final standard A2UI conversion.
    """
    source = _normalize_resource_cleanup_layout_source(source, contract)
    composition = parse_ux_layout_card(source)
    composition = _normalize_resource_usage_optional_icon(composition, contract)
    composition = _normalize_single_resource_usage_title(composition, contract)
    composition = _normalize_trusted_composite_text_calls(composition, contract)
    _validate_ux_layout_root(
        composition,
        contract,
        size=task_spec.size,
        registry=registry,
        embedded_actions=True,
    )
    raw_count = _count_calls(composition)
    if raw_count > contract.limits.max_raw_components:
        raise TerselConversionError("Hybrid raw component budget exceeded.")
    _reject_direct_events(composition)
    _validate_raw_components(composition, contract)
    _validate_required_business_components(composition, contract)
    composition, provider_param_normalizations = _normalize_template_provider_params(
        composition,
        task_spec,
        contract,
        registry,
    )
    composition, relation_number_normalizations = _normalize_template_relation_numbers(
        composition,
        contract,
        registry,
    )
    _validate_required_numbers(composition, contract, task_spec)
    composition = _normalize_recommended_variant_order(composition, registry)
    state = _ExpansionState(
        template_ids=[],
        action_ids=[],
        action_occurrences=[],
        template_provider_param_normalizations=provider_param_normalizations,
        template_relation_number_normalizations=relation_number_normalizations,
    )
    expanded = _expand_call(
        composition,
        parent="$root",
        contract=contract,
        registry=registry,
        state=state,
        task_spec=task_spec,
        provider_binding_roots=_provider_binding_roots(card_spec),
    )
    _validate_required_template_groups(state, contract)
    layout_id = _parsed_layout_template_id(composition, registry)
    embedded_action_count = sum(
        _parsed_ux_action_component(child) is not None for child in composition.children
    )
    if layout_id != "TwoSupportLayout" and len(state.action_occurrences) != embedded_action_count:
        raise TerselConversionError(
            "UX Layout Actions must use the dedicated Action nodes."
        )
    if any(action_id not in contract.content_action_ids for action_id in state.action_occurrences):
        raise TerselConversionError("UX Layout used an unapproved Action.")
    actual_actions = Counter(state.action_occurrences)
    expected_actions = Counter({action_id: 1 for action_id in contract.content_action_ids})
    if actual_actions != expected_actions:
        raise TerselConversionError(
            "UX Layout Actions must consume each selected Action exactly once."
        )
    expanded = _append_missing_required_literals_to_ux_layout(expanded, contract)
    expanded = _inject_ux_business_title(expanded, business_title, contract)
    expanded = _strip_2x2_composite_headers(expanded, size=task_spec.size)
    expanded = _normalize_weather_condition_icons(expanded, contract)
    content = _lower_ux_layout_root(
        expanded,
        size=task_spec.size,
        contract=contract,
        registry=registry,
    )
    content = _inject_resource_battery_title(
        content,
        business_title,
        contract,
        registry,
        size=task_spec.size,
    )
    content = _inject_phone_earphone_title(content, contract, registry)
    content = _deduplicate_ux_business_title_fragments(content, business_title)
    content = _lower_capsule_progress(content)
    content = _deduplicate_visible_text(content, task_spec)
    content_height = _estimate_height(content)
    body_budget = _ux_layout_body_budget(registry)
    if content_height > body_budget:
        content = _constrain_content_height(content, body_budget)
    fusion_palette = _template_fusion_ball_palette(
        task_spec.size,
        contract,
        registry,
        tuple(state.template_ids),
    )
    root = _compile_ux_layout_shell(
        content,
        contract,
        registry,
    )
    root = _apply_theme_content_color(root, contract, registry)
    root = _strip_advanced_component_markers(root)
    count, depth = _shape(root)
    if count > contract.limits.max_expanded_components:
        raise TerselConversionError("Hybrid expanded component budget exceeded.")
    if depth > contract.limits.max_nesting_depth:
        raise TerselConversionError("Hybrid component depth budget exceeded.")
    _validate_expanded_tree(root, contract)
    root = apply_fusion_ball_background(
        root,
        size=task_spec.size,
        palette=fusion_palette,
    )
    effective = _serialize_effective_document(root, task_spec, enable_data_bindings)
    a2ui = convert_tersel_to_a2ui(
        effective,
        size=task_spec.size,
        protocol_profile=protocol_profile,
        task_spec=task_spec.model_dump(mode="json") if enable_data_bindings else None,
    )
    component_types = _a2ui_component_types(a2ui)
    if "Template" in component_types:
        raise TerselConversionError("Template leaked into final A2UI.")
    if component_types & UX_LAYOUT_COMPONENT_IDS:
        raise TerselConversionError("UX Layout leaked into final A2UI.")
    if component_types & _UX_ACTION_COMPONENTS:
        raise TerselConversionError("UX Action leaked into final A2UI.")
    if component_types & _UX_DIRECT_BUSINESS_COMPONENTS:
        raise TerselConversionError("UX Business Component leaked into final A2UI.")
    return HybridCompilation(
        raw_output=source,
        effective_output=effective,
        a2ui=a2ui,
        stats=ExpansionStats(
            template_call_count=state.template_calls,
            template_used_ids=tuple(state.template_ids),
            template_variant_normalization_count=state.template_variant_normalizations,
            template_provider_param_normalization_count=(
                state.template_provider_param_normalizations
            ),
            template_relation_number_normalization_count=(
                state.template_relation_number_normalizations
            ),
            expanded_component_count=count,
            raw_component_count=raw_count,
            max_depth=depth,
            estimated_height_vp=content_height,
            vertical_budget_vp=body_budget,
            space_constrained=content_height > body_budget,
            action_used_ids=tuple(state.action_ids),
        ),
    )


def _validate_required_template_groups(
    state: _ExpansionState,
    contract: HybridBodyContract,
) -> None:
    """Require one trusted content Template for each selected UX component."""
    used = set(state.template_ids)
    for group in contract.required_template_groups:
        if not used.intersection(group):
            choices = ", ".join(group)
            raise TerselConversionError(
                f"UX business component requires one trusted Template from: {choices}"
            )


def _validate_required_business_components(
    root: ParsedCall,
    contract: HybridBodyContract,
) -> None:
    counts = Counter(
        call.name
        for call in _walk_calls(root)
        if call.kind == "component" and call.name in _UX_DIRECT_BUSINESS_COMPONENTS
    )
    allowed = set(contract.allowed_business_component_ids)
    if set(counts) - allowed:
        raise TerselConversionError(
            "UX Business Component is outside the approved Advanced Scope."
        )
    for component_id in contract.required_business_component_ids:
        if counts[component_id] != 1:
            raise TerselConversionError(
                f"UX Business Component must appear exactly once: {component_id}"
            )


def _normalize_resource_cleanup_layout_source(
    source: str,
    contract: HybridBodyContract,
) -> str:
    """Recover the unique approved root when the model places it after its content."""
    matches_contract = (
        set(contract.allowed_business_component_ids) == {"ResourceUsageOverview"}
        and set(contract.content_action_ids) == {"event.clean.memory"}
    )
    has_required_children = all(
        component in source for component in ("ResourceUsageOverview", "PillAction@1")
    )
    has_expected_root = source.lstrip().startswith("HeroActionLayout")
    if matches_contract and has_required_children and not has_expected_root:
        return 'HeroActionLayout(ResourceUsageOverview({"variant":"memory","role":"hero"}),' + (
            'Template("PillAction@1",{"actionId":"event.clean.memory",'
            '"label":"一键清理"}));'
        )
    return source


def _normalize_resource_usage_optional_icon(
    call: ParsedCall,
    contract: HybridBodyContract,
) -> ParsedCall:
    """Drop an unrelated optional resource icon without altering an Action icon."""
    children = tuple(
        _normalize_resource_usage_optional_icon(child, contract) for child in call.children
    )
    normalized = ParsedCall(call.kind, call.name, call.values, children, call.span)
    if (
        call.name != "ResourceUsageOverview"
        or len(call.values) != 1
        or not isinstance(call.values[0], dict)
    ):
        return normalized
    params = dict(call.values[0])
    source = params.get("icon")
    if source is None:
        return normalized
    if not isinstance(source, str) or source not in contract.allowed_asset_sources:
        return normalized
    tags = set(contract.asset_semantic_tags_by_source.get(source, ()))
    if tags & {"memory", "resource"}:
        return normalized
    params.pop("icon", None)
    return ParsedCall(call.kind, call.name, (params,), children, call.span)


def _normalize_single_resource_usage_title(
    call: ParsedCall,
    contract: HybridBodyContract,
) -> ParsedCall:
    """Restore the required internal title for a single resource business card."""
    children = tuple(
        _normalize_single_resource_usage_title(child, contract) for child in call.children
    )
    normalized = ParsedCall(call.kind, call.name, call.values, children, call.span)
    requires_resource_usage = set(contract.required_business_component_ids) == {
        "ResourceUsageOverview"
    }
    is_resource_call = call.name == "ResourceUsageOverview" and len(call.values) == 1
    has_parameters = is_resource_call and isinstance(call.values[0], dict)
    hides_title = has_parameters and call.values[0].get("showTitle") is False
    if not requires_resource_usage or not hides_title:
        return normalized
    params = dict(call.values[0])
    params.pop("showTitle", None)
    return ParsedCall(call.kind, call.name, (params,), children, call.span)


def _walk_calls(root: ParsedCall) -> Iterator[ParsedCall]:
    yield root
    for child in root.children:
        yield from _walk_calls(child)


def _parsed_ux_action_component(node: ParsedCall) -> str | None:
    if node.kind == "component" and node.name in _UX_ACTION_COMPONENTS:
        return node.name
    if node.kind == "template":
        return _ACTION_TEMPLATE_COMPONENTS.get(node.name)
    return None


def _normalize_trusted_composite_text_calls(
    call: ParsedCall,
    contract: HybridBodyContract,
) -> ParsedCall:
    """Split only delimiter-joined Text values made entirely of trusted facts.

    Models commonly render high/low values as ``26°/16°``. The wire grammar
    intentionally forbids synthesized literals, but this exact decomposition
    is lossless and remains closed over the trusted literal allowlist.
    """
    children = tuple(
        _normalize_trusted_composite_text_calls(child, contract) for child in call.children
    )
    normalized = ParsedCall(call.kind, call.name, call.values, children, call.span)
    is_text_call = call.kind == "component" and call.name == "Text"
    has_two_values = len(call.values) == 2
    if not is_text_call or not has_two_values:
        return normalized
    text, design_token = call.values
    if (
        not isinstance(text, str)
        or text in contract.trusted_literals
        or not isinstance(design_token, str)
    ):
        return normalized
    parts = tuple(part.strip() for part in re.split(r"[|｜/·•]+", text))
    if not 2 <= len(parts) <= 4 or any(
        not part or part not in contract.trusted_literals for part in parts
    ):
        return normalized
    return ParsedCall(
        "component",
        "Row",
        ("between",),
        tuple(
            ParsedCall("component", "Text", (part, design_token), (), call.span) for part in parts
        ),
        call.span,
    )


def _validate_card_params(
    params: dict[str, Any],
    task_spec: TaskSpec,
    contract: HybridBodyContract,
) -> None:
    unknown = set(params) - {"title", "subtitle", "titleIcon", "action"}
    if unknown:
        raise TerselConversionError(f"Unknown card@1 params: {sorted(unknown)}")
    for key in ("title", "subtitle"):
        if key not in params:
            continue
        value = params[key]
        if not isinstance(value, str) or value not in contract.trusted_literals:
            raise TerselConversionError(f"card@1 {key} is not trusted.")
    if "titleIcon" in params and params["titleIcon"] not in contract.allowed_asset_sources:
        raise TerselConversionError("card@1 titleIcon is not approved.")
    action = params.get("action")
    if action is None:
        return
    if not isinstance(action, dict) or set(action) != {"label", "id"}:
        raise TerselConversionError("card@1 action must contain label and id.")
    pair = (action.get("label"), action.get("id"))
    approved = {(item.display_label, item.action_id) for item in contract.action_bindings}
    if pair not in approved:
        raise TerselConversionError("card@1 action label/id pair is not approved.")
    if action["id"] in contract.content_action_ids:
        raise TerselConversionError("content Action cannot be used by card@1.")
    event_ids = {item.id for item in task_spec.eventCandidates}
    selected_binding = next(
        item for item in contract.action_bindings if item.action_id == action["id"]
    )
    if selected_binding.event_id not in event_ids:
        raise TerselConversionError("card@1 action is not in TaskSpec.")


def _normalize_card_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params)
    if "icon" not in normalized:
        return normalized
    if "titleIcon" in normalized:
        raise TerselConversionError("card@1 cannot contain icon and titleIcon.")
    normalized["titleIcon"] = normalized.pop("icon")
    return normalized


def _expand_call(
    call: ParsedCall,
    *,
    parent: str,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    state: _ExpansionState,
    task_spec: TaskSpec,
    provider_binding_roots: dict[str, str],
    ux_layout_id: str | None = None,
) -> Nested2Node:
    if call.kind == "component":
        if call.name in _UX_ACTION_COMPONENTS:
            return _expand_ux_action_call(call, contract, state)
        if call.name == "ActivityOverview":
            return _expand_activity_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "WorkoutOverview":
            return _expand_workout_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "HeartRateOverview":
            return _expand_heart_rate_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "SleepOverview":
            return _expand_sleep_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "DateOverview":
            return _expand_date_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "AppUsageOverview":
            return _expand_app_usage_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
            )
        if call.name == "BatteryOverview":
            return _expand_battery_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
                layout_id=ux_layout_id,
            )
        if call.name == "BluetoothDeviceOverview":
            return _expand_bluetooth_device_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
                layout_id=ux_layout_id,
            )
        if call.name == "WeatherOverview":
            return _expand_weather_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
                layout_id=ux_layout_id,
            )
        if call.name == "ScheduleOverview":
            return _expand_schedule_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                registry=registry,
                layout_id=ux_layout_id,
            )
        if call.name == "ResourceUsageOverview":
            return _expand_resource_usage_overview_call(
                call,
                task_spec=task_spec,
                contract=contract,
                layout_id=ux_layout_id,
            )
        child_parent = "Column" if call.name in UX_LAYOUT_COMPONENT_IDS else call.name
        child_layout_id = call.name if call.name in UX_LAYOUT_COMPONENT_IDS else ux_layout_id
        children = tuple(
            _expand_call(
                child,
                parent=child_parent,
                contract=contract,
                registry=registry,
                state=state,
                task_spec=task_spec,
                provider_binding_roots=provider_binding_roots,
                ux_layout_id=child_layout_id,
            )
            for child in call.children
        )
        values = _normalize_component_values(call.name, call.values)
        if call.name in {"Column", "List"} and values and values[0] == "compact":
            children = tuple(
                child
                if contract.allowed_layout_component_ids and source.kind == "template"
                else _compact_text_roles(child)
                for source, child in zip(call.children, children, strict=True)
            )
        return Nested2Node(
            call.name,
            values,
            children,
        )
    wire_id = call.name
    if wire_id not in contract.allowed_template_ids:
        raise TerselConversionError(f"Template is not allowed: {wire_id}")
    definition = registry.require_template(wire_id)
    if definition.allowed_parent_components and parent not in definition.allowed_parent_components:
        raise TerselConversionError(f"Template parent is not allowed: {wire_id}/{parent}")
    if len(call.values) == 1 and isinstance(call.values[0], dict):
        size = "default"
        params = call.values[0]
        variant = definition.variants[0]
    elif len(call.values) == 2 and isinstance(call.values[1], dict):
        size, params = call.values
        try:
            variant = registry.require_variant(wire_id, str(size))
        except ValueError as exc:
            if len(definition.variants) != 1:
                raise TerselConversionError(
                    f"Template variant is not allowed: {wire_id}/{size}"
                ) from exc
            variant = definition.variants[0]
            state.template_variant_normalizations += 1
    else:
        raise TerselConversionError(f"Template props are invalid: {wire_id}")
    if bool(call.children) != definition.accepts_children:
        expected = "with children" if definition.accepts_children else "without children"
        raise TerselConversionError(f"Template must be called {expected}: {wire_id}")
    errors = sorted(Draft202012Validator(variant.parameters_schema).iter_errors(params), key=str)
    if errors:
        raise TerselConversionError(
            f"Template params are invalid for {wire_id}/{size}: {errors[0].message}"
        )
    params = _normalize_template_asset_params(
        params,
        definition.asset_parameter_semantic_tags,
        contract,
        required_parameters=frozenset(
            str(item) for item in variant.parameters_schema.get("required", ())
        ),
    )
    _validate_template_params(params, definition.asset_parameter_semantic_tags, contract)
    _validate_template_parameter_relations(params, variant.parameter_relations)
    if variant.supported_card_sizes and task_spec.size not in variant.supported_card_sizes:
        raise TerselConversionError(
            f"Provider Template does not support the card size: {wire_id}/{task_spec.size}"
        )
    _validate_provider_template_state(
        wire_id,
        str(size),
        task_spec,
        business_names=_contract_ux_business_component_names(contract, registry),
    )
    if (
        definition.source_format == "cardtpl/1"
        and definition.compatible_theme_profile_ids
        and contract.theme_profile_id not in definition.compatible_theme_profile_ids
    ):
        raise TerselConversionError(
            f"Provider Template does not support the theme: {wire_id}/{contract.theme_profile_id}"
        )
    binding_values = _provider_template_binding_values(
        definition,
        variant,
        task_spec,
        provider_binding_roots,
    )
    spread_parent = _template_spread_parent(variant.root)
    layout_template_id = (
        definition.template_id
        if definition.template_id in UX_LAYOUT_COMPONENT_IDS
        else None
    )
    child_parent = layout_template_id or spread_parent or parent
    child_layout_id = layout_template_id or (
        spread_parent if spread_parent in UX_LAYOUT_COMPONENT_IDS else ux_layout_id
    )
    expanded_children = tuple(
        _expand_call(
            child,
            parent=child_parent,
            contract=contract,
            registry=registry,
            state=state,
            task_spec=task_spec,
            provider_binding_roots=provider_binding_roots,
            ux_layout_id=child_layout_id,
        )
        for child in call.children
    )
    indexed_child_slots = _template_child_slot_indexes(variant.root)
    if indexed_child_slots and len(expanded_children) != len(indexed_child_slots):
        raise TerselConversionError(
            f"Template indexed child count is invalid: {wire_id}/{len(expanded_children)}"
        )
    if wire_id == "ux-bluetooth-overview@2" and ux_layout_id == "PeerPairLayout":
        root = _expand_bluetooth_battery_peer(params, registry)
    elif layout_template_id and variant.root.component not in UX_LAYOUT_COMPONENT_IDS:
        root = Nested2Node(
            layout_template_id,
            (dict(params),) if params else (),
            expanded_children,
        )
    else:
        root = _instantiate_blueprint(
            variant.root,
            params,
            binding_values,
            registry.theme_reference_values(contract.theme_profile_id),
            spread_children=expanded_children,
        )
    budget_root = root
    if definition.provider_id == _ACTION_PROVIDER_ID:
        root, action_ids = _wrap_action_template(
            root,
            wire_id=wire_id,
            params=params,
            contract=contract,
        )
    else:
        root, action_ids = _bind_template_actions(root, contract)
    budget_node_count, budget_depth = _shape(budget_root)
    if (
        not definition.accepts_children
        and (
            budget_node_count > variant.expanded_node_budget
            or budget_depth > variant.expanded_depth_budget
        )
    ):
        raise TerselConversionError(f"Template blueprint budget drift: {wire_id}/{size}")
    node_count, _ = _shape(root)
    state.template_calls += 1
    state.expanded_components += node_count
    if wire_id not in state.template_ids:
        state.template_ids.append(wire_id)
    for action_id in action_ids:
        state.action_occurrences.append(action_id)
        if action_id not in state.action_ids:
            state.action_ids.append(action_id)
    return root


def _wrap_action_template(
    root: Nested2Node,
    *,
    wire_id: str,
    params: dict[str, Any],
    contract: HybridBodyContract,
) -> tuple[Nested2Node, tuple[str, ...]]:
    action_component = _ACTION_TEMPLATE_COMPONENTS.get(wire_id)
    if action_component is None:
        raise TerselConversionError(f"Action Provider Template is unsupported: {wire_id}")
    if root.component_type != "Stack":
        raise TerselConversionError(
            f"Action Provider Template root must be Stack: {wire_id}"
        )
    action_id = params.get("actionId")
    if not isinstance(action_id, str):
        raise TerselConversionError(
            f"Action Provider Template actionId is invalid: {wire_id}"
        )
    binding = next(
        (item for item in contract.action_bindings if item.action_id == action_id),
        None,
    )
    if binding is None or action_id not in contract.content_action_ids:
        raise TerselConversionError(f"Action Provider Template is not approved: {wire_id}")
    if action_component == "PillAction" and params.get("label") != binding.display_label:
        raise TerselConversionError("PillAction label/actionId pair is not approved.")
    icon = params.get("icon")
    if icon is not None and (
        not isinstance(icon, str) or icon not in contract.allowed_asset_sources
    ):
        raise TerselConversionError(f"{action_component} icon is not approved.")
    if action_component == "IconAction" and not isinstance(icon, str):
        raise TerselConversionError("IconAction requires an approved icon.")
    bound_root, action_ids = _bind_template_actions(root, contract)
    if action_ids != (action_id,):
        raise TerselConversionError(
            f"Action Provider Template event declaration is invalid: {wire_id}"
        )
    return Nested2Node(action_component, (dict(params),), (bound_root,)), action_ids


def _validate_provider_template_state(
    wire_id: str,
    variant_name: str,
    task_spec: TaskSpec,
    *,
    business_names: set[str],
) -> None:
    identity = provider_template_family_identity(wire_id)
    if identity is not None:
        wire_id, variant_name = identity
    if wire_id == "BatteryOverview@1":
        state_independent_variants = {
            "compact",
            "chargingDiagnosticsHero",
            "chargingProgressHero",
            "full",
            "hero",
            "healthLevelHero",
            "percentRingHero",
            "progressCompact",
            "progressSupport",
            "statusIconCompact",
            "statusIconSupport",
            "temperatureIconCompact",
            "temperatureIconSupport",
            "wideFull",
        }
        if variant_name in state_independent_variants:
            return
        facts = extract_battery_overview_facts(task_spec.dataModelSchema)
        if facts is None:
            raise TerselConversionError(
                "Battery Provider Template variant does not match the trusted state."
            )
        if not variant_name.startswith(facts.state):
            raise TerselConversionError(
                "Battery Provider Template variant does not match the trusted state."
            )
        if business_names == {"BatteryOverview", "BluetoothDeviceOverview"}:
            expected = f"{facts.state}PhoneCompact"
            if variant_name != expected:
                raise TerselConversionError(
                    "Battery Provider Template variant does not match the phone-earphone layout."
                )
    if wire_id == "BluetoothDeviceOverview@1":
        facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
        if facts is None:
            raise TerselConversionError(
                "Bluetooth Provider Template has no trusted earphone facts."
            )
        if variant_name == "caseStatusCompact":
            if (
                facts.case_battery_level is None
                or facts.case_charging_status is None
            ):
                raise TerselConversionError(
                    "Bluetooth Provider Template variant does not match the trusted case status."
                )
            return
        has_left = facts.left_battery_level is not None
        has_right = facts.right_battery_level is not None
        has_case = facts.case_battery_level is not None
        if variant_name == "earbudsSupport":
            if not has_left or not has_right:
                raise TerselConversionError(
                    "Bluetooth Provider Template variant does not match the trusted data shape."
                )
            return
        if facts.is_connected is None or facts.earphone_name is None:
            raise TerselConversionError(
                "Bluetooth Provider Template has no trusted earphone identity."
            )
        if variant_name == "hero":
            return
        if variant_name == "earbudPairCompact":
            if not has_left or not has_right:
                raise TerselConversionError(
                    "Bluetooth Provider Template variant does not match the trusted data shape."
                )
            return
        if variant_name == "earbudPairFull":
            if not has_case or not has_left or not has_right:
                raise TerselConversionError(
                    "Bluetooth Provider Template variant does not match the trusted data shape."
                )
            return
        paired_with_phone = business_names == {
            "BatteryOverview",
            "BluetoothDeviceOverview",
        }
        phone_variants = {
            "earbudsPhoneWideFull",
            "completePhoneWideFull",
        }
        standalone_variants = {
            "earbudsDynamicWideFull",
            "completeWideFull",
        }
        if variant_name in phone_variants and not paired_with_phone:
            raise TerselConversionError(
                "Bluetooth Provider Template variant does not match the phone-earphone layout."
            )
        if variant_name in standalone_variants and paired_with_phone:
            raise TerselConversionError(
                "Bluetooth Provider Template variant does not match the phone-earphone layout."
            )
        if variant_name in phone_variants | standalone_variants:
            return
        raise TerselConversionError(
            "Bluetooth Provider Template variant does not match the trusted data shape."
        )


def _expand_ux_action_call(
    call: ParsedCall,
    contract: HybridBodyContract,
    state: _ExpansionState,
) -> Nested2Node:
    if call.name not in {"PillAction", "IconAction"}:
        raise TerselConversionError("UX template route Action type is not supported.")
    if len(call.values) != 1 or not isinstance(call.values[0], dict):
        raise TerselConversionError(f"{call.name} requires one object argument.")
    params = dict(call.values[0])
    expected_fields = {"actionId"} if call.name == "PillAction" else {"actionId", "icon"}
    if set(params) != expected_fields:
        raise TerselConversionError(f"{call.name} contains unknown fields.")
    action_id = params.get("actionId")
    if not isinstance(action_id, str):
        raise TerselConversionError(f"{call.name} actionId is invalid.")
    binding = next(
        (item for item in contract.action_bindings if item.action_id == action_id),
        None,
    )
    if binding is None or action_id not in contract.content_action_ids:
        raise TerselConversionError(f"{call.name} Action is not approved.")
    icon = params.get("icon")
    if call.name == "IconAction" and (
        not isinstance(icon, str) or icon not in contract.allowed_asset_sources
    ):
        raise TerselConversionError("IconAction icon is not approved.")
    if action_id not in state.action_ids:
        state.action_ids.append(action_id)
    state.action_occurrences.append(action_id)
    return Nested2Node(call.name, (params,), ())


def _expand_date_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("DateOverview is not approved by Advanced Scope.")
    facts = extract_date_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "DateOverview requires complete trusted date and weekday strings."
        )
    parameters = call.values[0]
    variant = str(parameters["variant"])
    theme = registry.require_theme(contract.theme_profile_id)
    highlight_color = theme.primary_color
    neutral_color = theme.support_content_color
    if variant == "compactDate":
        return _compact_date_overview(facts, highlight_color, neutral_color)
    return _hero_date_overview(facts, highlight_color, neutral_color, registry)


def _compact_date_overview(
    facts: DateOverviewFacts,
    highlight_color: str,
    neutral_color: str,
) -> Nested2Node:
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "_advancedComponent": "DateOverview",
                "width": "100%",
                "height": 20,
                "itemMargin": 6,
                "justifyContent": "start",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _date_text(
                facts.date,
                "compact-title",
                font_size=14,
                font_weight=700,
                font_color=highlight_color,
            ),
            _date_text(
                facts.weekday,
                "subtitle",
                font_size=12,
                font_weight=500,
                font_color=neutral_color,
            ),
        ),
    )


def _hero_date_overview(
    facts: DateOverviewFacts,
    highlight_color: str,
    neutral_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "DateOverview",
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "center",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _date_text(
                facts.date,
                "title",
                font_size=30,
                font_weight=800,
                font_color=highlight_color,
                min_font_size=30,
            ),
            _date_text(
                facts.weekday,
                "body",
                font_size=14,
                font_weight=500,
                font_color=neutral_color,
            ),
        ),
    )


def _date_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    font_color: str,
    min_font_size: int | None = None,
) -> Nested2Node:
    options: dict[str, Any] = {
        "fontSize": font_size,
        "fontWeight": font_weight,
        "fontColor": font_color,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if min_font_size is not None:
        options["minFontSize"] = min_font_size
    return Nested2Node("Text", (value, design, options), ())


def _expand_activity_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("ActivityOverview is not approved by Advanced Scope.")
    parameters = call.values[0]
    variant = str(parameters["variant"])
    variant_selector = (
        relaxed_activity_overview_variants
        if advanced_component_data_admission_is_relaxed()
        else activity_overview_variants
    )
    allowed_variants = set(variant_selector(task_spec, {"GetHealthAndSportSummary"}))
    if variant not in allowed_variants:
        raise TerselConversionError(
            "ActivityOverview variant is not backed by this query and trusted projection."
        )
    facts = extract_activity_overview_facts(task_spec.dataModelSchema)
    if facts is None or (variant == "dailySummary" and not facts.has_daily_summary):
        raise TerselConversionError(
            "ActivityOverview requires trusted fields for the selected variant."
        )
    role = str(parameters["role"])
    icons = {name: parameters.get(name) for name in ("stepsIcon", "caloriesIcon", "distanceIcon")}
    if role == "support":
        return _activity_support_overview(facts, icons, registry)
    return _activity_hero_overview(
        facts,
        icons,
        registry,
        wide=task_spec.size == "2x4",
        include_summary=variant == "dailySummary",
    )


def _activity_hero_overview(
    facts: ActivityOverviewFacts,
    icons: dict[str, Any],
    registry: CardPlanRegistry,
    *,
    wide: bool,
    include_summary: bool,
) -> Nested2Node:
    header = _overview_header("今日活动", icons["stepsIcon"], registry)
    metric = _overview_value_row(
        str(facts.daily_steps),
        "步",
        accent="#FFFF7A45",
        registry=registry,
        hero=True,
    )
    primary = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (header, metric),
    )
    if not include_summary:
        return _mark_advanced_component(primary, "ActivityOverview")
    calories_text = facts.calories_text
    distance_text = facts.distance_text
    if calories_text is None or distance_text is None:
        raise TerselConversionError("ActivityOverview dailySummary requires calories and distance.")
    secondary = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "center",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _overview_fact_row(
                calories_text,
                icons["caloriesIcon"],
                registry,
            ),
            _overview_fact_row(
                distance_text,
                icons["distanceIcon"],
                registry,
            ),
        ),
    )
    if wide:
        root = _weighted_row((primary, secondary), (58, 42), registry)
    else:
        root = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "width": "matchParent",
                    "height": "matchParent",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                    "justifyContent": "spaceBetween",
                    "alignItems": "start",
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (header, metric, _inline_overview_facts(secondary.children, registry)),
        )
    return _mark_advanced_component(root, "ActivityOverview")


def _activity_support_overview(
    facts: ActivityOverviewFacts,
    icons: dict[str, Any],
    registry: CardPlanRegistry,
) -> Nested2Node:
    root = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _overview_header("今日步数", icons["stepsIcon"], registry, compact=True),
            _overview_value_row(
                str(facts.daily_steps),
                "步",
                accent="#FFFF7A45",
                registry=registry,
                hero=False,
            ),
        ),
    )
    return _mark_advanced_component(root, "ActivityOverview")


def _expand_workout_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("WorkoutOverview is not approved by Advanced Scope.")
    parameters = call.values[0]
    variant = str(parameters["variant"])
    variant_selector = (
        relaxed_workout_overview_variants
        if advanced_component_data_admission_is_relaxed()
        else workout_overview_variants
    )
    allowed_variants = set(
        variant_selector(
            task_spec,
            {"GetHealthAndSportSummary"},
        )
    )
    if variant not in allowed_variants:
        raise TerselConversionError(
            "WorkoutOverview variant is not backed by this query and trusted projection."
        )
    source_icon = parameters.get("sourceIcon")
    calorie_icon = parameters.get("caloriesIcon")
    facts = extract_workout_latest_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "WorkoutOverview latest requires four trusted non-empty exercise fields."
        )
    return _workout_latest_overview(facts, source_icon, calorie_icon, registry)


def _workout_latest_overview(
    facts: WorkoutLatestFacts,
    source_icon: Any,
    calorie_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    root = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _overview_header("最近锻炼", source_icon, registry),
            _overview_text(facts.exercise_type_name, "compact-title", 20, 700),
            _overview_value_row(
                facts.duration_text,
                "",
                accent="#FFFF7A45",
                registry=registry,
                hero=True,
            ),
            _overview_fact_row(facts.calorie_text, calorie_icon, registry),
        ),
    )
    return _mark_advanced_component(root, "WorkoutOverview")


def _expand_heart_rate_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("HeartRateOverview is not approved by Advanced Scope.")
    if not advanced_component_data_admission_is_relaxed() and not heart_rate_overview_is_eligible(
        task_spec,
        {"GetHealthAndSportSummary"},
    ):
        raise TerselConversionError(
            "HeartRateOverview average is not backed by this query and trusted projection."
        )
    facts = extract_heart_rate_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "HeartRateOverview requires a trusted positive exercise average heart rate."
        )
    parameters = call.values[0]
    role = str(parameters["role"])
    source_icon = parameters.get("sourceIcon")
    children: list[Nested2Node] = [
        _overview_header(
            "运动平均心率",
            source_icon,
            registry,
            compact=role == "support",
        ),
        _overview_value_row(
            str(facts.average_bpm),
            "bpm",
            accent="#FFE84057",
            registry=registry,
            hero=role == "hero",
        ),
    ]
    if facts.updated_at is not None:
        children.append(_overview_text(facts.updated_at, "subtitle", 10, 400))
    root = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start" if role == "support" else "spaceBetween",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )
    return _mark_advanced_component(root, "HeartRateOverview")


def _expand_sleep_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("SleepOverview is not approved by Advanced Scope.")
    facts = extract_sleep_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "SleepOverview requires a losslessly renderable night duration."
        )
    parameters = call.values[0]
    variant = str(parameters["variant"])
    allowed_variants = set(sleep_overview_variants(task_spec, {"GetHealthAndSportSummary"}))
    if variant not in allowed_variants:
        raise TerselConversionError(
            "SleepOverview variant is not backed by this query and trusted projection."
        )
    role = str(parameters["role"])
    source_icon = parameters.get("sourceIcon")
    multi_business = len(contract.allowed_business_component_ids) > 1
    if multi_business:
        source_icon = None
    theme = registry.require_theme(contract.theme_profile_id)
    if role == "support":
        return _sleep_support_overview(
            facts,
            primary_color=theme.primary_color,
            support_content_color=theme.support_content_color,
            registry=registry,
        )
    return _sleep_hero_overview(
        facts,
        source_icon,
        wide=task_spec.size == "2x4",
        primary_color=theme.primary_color,
        support_content_color=theme.support_content_color,
        registry=registry,
    )


def _sleep_hero_overview(
    facts: SleepOverviewFacts,
    source_icon: Any,
    *,
    wide: bool,
    primary_color: str,
    support_content_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    secondary_color = support_content_color
    title = _sleep_title_row(
        source_icon,
        primary_color=primary_color,
        registry=registry,
    )
    duration = _sleep_duration_row(
        facts,
        value_size=30,
        unit_size=12,
        primary_color=primary_color,
        secondary_color=secondary_color,
    )
    status = (
        _sleep_text(
            facts.status,
            "subtitle",
            font_size=10,
            font_weight=400,
            font_color=secondary_color,
        )
        if facts.status is not None
        else None
    )
    # Group duration and status at bottom
    if status is not None:
        bottom_section = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "width": "matchParent",
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                    "justifyContent": "end",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (duration, status),
        )
        hero_children = (title, bottom_section)
    else:
        hero_children = (title, duration)
    hero = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        hero_children,
    )
    if not wide:
        return _mark_advanced_component(hero, "SleepOverview")
    support = _sleep_schedule_support(
        facts,
        primary_color=primary_color,
        secondary_color=secondary_color,
    )
    if support is None:
        return _mark_advanced_component(hero, "SleepOverview")
    root = _weighted_row((hero, support), (56, 44), registry)
    return _mark_advanced_component(root, "SleepOverview")


def _sleep_support_overview(
    facts: SleepOverviewFacts,
    *,
    primary_color: str,
    support_content_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    secondary_color = support_content_color
    root = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _sleep_text(
                "睡眠",
                "subtitle",
                font_size=10,
                font_weight=400,
                font_color=secondary_color,
            ),
            _sleep_duration_row(
                facts,
                value_size=20,
                unit_size=10,
                primary_color=primary_color,
                secondary_color=secondary_color,
            ),
        ),
    )
    return _mark_advanced_component(root, "SleepOverview")


def _sleep_title_row(
    source_icon: Any,
    *,
    primary_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    title = _merge_node_options(
        _sleep_text(
            "睡眠",
            "compact-title",
            font_size=12,
            font_weight=400,
            font_color=primary_color,
        ),
        {"layoutWeight": 1},
    )
    children = [title]
    if isinstance(source_icon, str):
        size = registry.ux_tokens["titleSourceIconSize"]
        children.append(
            Nested2Node(
                "Image",
                (
                    source_icon,
                    "icon",
                    {
                        "width": size,
                        "height": size,
                        "objectFit": "contain",
                        "flexShrink": 0,
                    },
                ),
                (),
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "height": 20,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "middle",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _sleep_duration_row(
    facts: SleepOverviewFacts,
    *,
    value_size: int,
    unit_size: int,
    primary_color: str,
    secondary_color: str,
) -> Nested2Node:
    parts = facts.duration
    groups = [
        _sleep_duration_group(
            parts.primary_value,
            parts.primary_unit,
            value_size=value_size,
            unit_size=unit_size,
            primary_color=primary_color,
            secondary_color=secondary_color,
        )
    ]
    if parts.secondary_value is not None:
        groups.append(
            _sleep_duration_group(
                parts.secondary_value,
                parts.secondary_unit or "",
                value_size=value_size,
                unit_size=unit_size,
                primary_color=primary_color,
                secondary_color=secondary_color,
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": 2,
                "justifyContent": "start",
                "alignItems": "bottom",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(groups),
    )


def _sleep_duration_group(
    value: str,
    unit: str,
    *,
    value_size: int,
    unit_size: int,
    primary_color: str,
    secondary_color: str,
) -> Nested2Node:
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "itemMargin": 0,
                "justifyContent": "start",
                "alignItems": "bottom",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _sleep_text(
                value,
                "title",
                font_size=value_size,
                font_weight=700,
                font_color=primary_color,
            ),
            _sleep_text(
                unit,
                "subtitle",
                font_size=unit_size,
                font_weight=400,
                font_color=secondary_color,
            ),
        ),
    )


def _sleep_schedule_support(
    facts: SleepOverviewFacts,
    *,
    primary_color: str,
    secondary_color: str,
) -> Nested2Node | None:
    items: list[Nested2Node] = []
    for label, value in (
        ("入睡", facts.fall_asleep_time),
        ("醒来", facts.wakeup_time),
    ):
        if value is None:
            continue
        items.append(
            Nested2Node(
                "Column",
                (
                    "compact",
                    {
                        "width": "matchParent",
                        "itemMargin": 4,
                        "alignItems": "start",
                    },
                ),
                (
                    _sleep_text(
                        label,
                        "subtitle",
                        font_size=10,
                        font_weight=400,
                        font_color=secondary_color,
                    ),
                    _sleep_text(
                        value,
                        "body",
                        font_size=14,
                        font_weight=500,
                        font_color=primary_color,
                    ),
                ),
            )
        )
    if not items and facts.status is not None:
        items.append(
            _sleep_text(
                facts.status,
                "subtitle",
                font_size=10,
                font_weight=400,
                font_color=secondary_color,
            )
        )
    if not items:
        return None
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 8,
                "borderRadius": 8,
                "backgroundColor": "#24FFFFFF",
                "itemMargin": 8,
                "justifyContent": "center",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(items),
    )


def _sleep_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    font_color: str,
) -> Nested2Node:
    return Nested2Node(
        "Text",
        (
            value,
            design,
            {
                "fontSize": font_size,
                "minFontSize": font_size,
                "fontWeight": font_weight,
                "fontColor": font_color,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (),
    )


def _overview_header(
    title: str,
    icon: Any,
    registry: CardPlanRegistry,
    *,
    compact: bool = False,
) -> Nested2Node:
    children: list[Nested2Node] = []
    if isinstance(icon, str):
        size = 16 if compact else registry.ux_tokens["businessIconSize"]
        children.append(
            Nested2Node(
                "Image",
                (
                    icon,
                    "icon",
                    {
                        "width": size,
                        "height": size,
                        "objectFit": "contain",
                        "flexShrink": 0,
                    },
                ),
                (),
            )
        )
    children.append(_overview_text(title, "subtitle", 10 if compact else 12, 500))
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "top",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _overview_value_row(
    value: str,
    unit: str,
    *,
    accent: str,
    registry: CardPlanRegistry,
    hero: bool,
) -> Nested2Node:
    children = [
        _overview_text(
            value,
            "title" if hero else "compact-title",
            38 if hero else 20,
            800 if hero else 700,
            color=accent,
            fill_width=False,
        )
    ]
    if unit:
        children.append(_overview_text(unit, "subtitle", 12, 500, fill_width=False))
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "bottom",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _overview_fact_row(
    value: str,
    icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    children: list[Nested2Node] = []
    if isinstance(icon, str):
        children.append(
            Nested2Node(
                "Image",
                (
                    icon,
                    "icon",
                    {"width": 16, "height": 16, "objectFit": "contain", "flexShrink": 0},
                ),
                (),
            )
        )
    children.append(_overview_text(value, "body", 12, 500))
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "top",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _inline_overview_facts(
    children: tuple[Nested2Node, ...],
    registry: CardPlanRegistry,
) -> Nested2Node:
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "center",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(_with_flex_weight(child, 1, axis="horizontal") for child in children),
    )


def _overview_text(
    value: str,
    design: str,
    font_size: int,
    font_weight: int,
    *,
    color: str = "#E6000000",
    fill_width: bool = True,
) -> Nested2Node:
    options: dict[str, Any] = {
        "fontSize": font_size,
        "fontWeight": font_weight,
        "fontColor": color,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if fill_width:
        options["width"] = "matchParent"
    return Nested2Node(
        "Text",
        (
            value,
            design,
            options,
        ),
        (),
    )


def _mark_advanced_component(node: Nested2Node, component_id: str) -> Nested2Node:
    return _merge_node_options(node, {"_advancedComponent": component_id})


def _expand_battery_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    layout_id: str | None,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("BatteryOverview is not approved by Advanced Scope.")
    facts = extract_battery_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "BatteryOverview requires one coherent trusted four-field phone battery projection."
        )
    parameters = call.values[0]
    if parameters.get("variant") != facts.state:
        raise TerselConversionError(
            "BatteryOverview variant does not match the trusted battery state."
        )
    battery_icon = parameters.get("batteryIcon")
    if battery_icon is not None:
        actual_tags = set(contract.asset_semantic_tags_by_source.get(str(battery_icon), ()))
        if not actual_tags & {"battery", "power", "phone", "phone-device"}:
            raise TerselConversionError(
                "BatteryOverview batteryIcon does not match TaskSpec battery semantics."
            )
    role = str(parameters["role"])
    show_title = parameters.get("showTitle", True)
    business_component_names = _contract_ux_business_component_names(contract, registry)
    paired_with_bluetooth = business_component_names == {
        "BatteryOverview",
        "BluetoothDeviceOverview",
    }
    if paired_with_bluetooth:
        return _battery_device_hero_overview(facts, battery_icon, registry)
    paired_with_weather = business_component_names == {
        "WeatherOverview",
        "BatteryOverview",
    }
    if paired_with_weather and task_spec.size == "2x2" and role == "support":
        return _battery_weather_support_overview(facts, battery_icon, registry)
    if role == "peer":
        return _battery_peer_overview(
            facts,
            battery_icon,
            registry,
            show_title=show_title,
        )
    if task_spec.size == "2x4" and role == "hero":
        return _battery_wide_overview(facts, battery_icon, registry)
    ring_size = registry.ux_tokens["ringMinimumSize"] if role == "support" else None
    del layout_id
    return _battery_compact_overview(facts, battery_icon, registry, ring_size=ring_size)


def _battery_weather_support_overview(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    summary_children: list[Nested2Node] = []
    if isinstance(battery_icon, str):
        summary_children.append(
            Nested2Node(
                "Image",
                (
                    battery_icon,
                    "icon",
                    {
                        "width": 14,
                        "height": 14,
                        "objectFit": "contain",
                        "flexShrink": 0,
                    },
                ),
                (),
            )
        )
    summary_children.extend(
        (
            _overview_text(
                facts.level_text,
                "compact-title",
                14,
                700,
                fill_width=False,
            ),
            _overview_text(
                facts.capacity_level,
                "subtitle",
                10,
                400,
                fill_width=False,
            ),
        )
    )
    summary = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(summary_children),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BatteryOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 2,
                "justifyContent": "center",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            summary,
            _overview_text(
                facts.charging_status,
                "subtitle",
                10,
                400,
                fill_width=False,
            ),
        ),
    )


def _battery_compact_overview(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
    *,
    ring_size: int | None,
) -> Nested2Node:
    bottom_region = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "matchParent",
                "height": "matchParent",
                "layoutWeight": 1,
                "alignContent": "bottomStart",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (_battery_ring(facts, battery_icon, registry, ring_size=ring_size),),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BatteryOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _battery_text("设备电量", "subtitle", 12, 500),
            _battery_text(
                facts.level_text,
                "body",
                12,
                400,
                max_lines=2,
            ),
            bottom_region,
        ),
    )


def _battery_wide_overview(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    details = Nested2Node(
        "Column",
        (
            "compact",
            {
                "layoutWeight": 1,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "center",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _battery_text(facts.level_text, "compact-title", 14, 700),
            _battery_text(facts.capacity_level, "body", 14, 400),
            _battery_text(facts.charging_status, "subtitle", 10, 400),
        ),
    )
    status = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "layoutWeight": 1,
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "start",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (_battery_ring(facts, battery_icon, registry), details),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BatteryOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (_battery_text("设备电量", "subtitle", 12, 500), status),
    )


def _battery_peer_overview(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
    *,
    show_title: bool,
) -> Nested2Node:
    children: list[Nested2Node] = []
    if show_title:
        children.append(_battery_text("设备电量", "subtitle", 12, 500))
    children.extend(
        (
            _battery_ring(facts, battery_icon, registry),
            _battery_text(
                facts.level_text,
                "compact-title",
                14,
                700,
                text_align="center",
            ),
            _battery_text(
                facts.capacity_level,
                "subtitle",
                10,
                400,
                text_align="center",
            ),
            _battery_text(
                facts.charging_status,
                "subtitle",
                10,
                400,
                text_align="center",
            ),
        )
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BatteryOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 2,
                "justifyContent": "center",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _battery_device_hero_overview(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BatteryOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 2,
                "justifyContent": "center",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _battery_ring(facts, battery_icon, registry, ring_size=56),
            _battery_text(facts.level_text, "compact-title", 16, 700),
            _battery_text("手机", "subtitle", 10, 400),
        ),
    )


def _battery_ring(
    facts: BatteryOverviewFacts,
    battery_icon: Any,
    registry: CardPlanRegistry,
    *,
    ring_size: int | None = None,
) -> Nested2Node:
    size = ring_size or registry.ux_tokens["ringDefaultSize"]
    ring_color = _WARNING_DATA_COLOR
    children: list[Nested2Node] = [
        Nested2Node(
            "Progress",
            (
                {
                    "value": facts.level_percent,
                    "total": 100,
                    "type": "ring",
                    "color": ring_color,
                    "backgroundColor": _TRACK_COLOR,
                    "width": size,
                    "height": size,
                    "strokeWidth": 6,
                },
            ),
            (),
        )
    ]
    if isinstance(battery_icon, str):
        icon_size = registry.ux_tokens["ringHeroIconSize"]
        children.append(
            Nested2Node(
                "Image",
                (
                    battery_icon,
                    "icon",
                    {
                        "width": icon_size,
                        "height": icon_size,
                        "objectFit": "contain",
                        "fillColor": _ICON_SECONDARY,
                    },
                ),
                (),
            )
        )
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": size,
                "height": size,
                "alignContent": "center",
                "flexShrink": 0,
            },
        ),
        tuple(children),
    )


def _expand_bluetooth_battery_peer(
    params: dict[str, Any],
    registry: CardPlanRegistry,
) -> Nested2Node:
    """Use one aggregate earphone Ring beside BatteryOverview in PeerPairLayout."""
    level = params["batteryLevel"]
    ring_color = _WARNING_DATA_COLOR if float(level) <= 20 else _NORMAL_DATA_COLOR
    size = registry.ux_tokens["ringDefaultSize"]
    ring = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": size,
                "height": size,
                "alignContent": "center",
                "flexShrink": 0,
            },
        ),
        (
            Nested2Node(
                "Progress",
                (
                    {
                        "value": level,
                        "total": 100,
                        "type": "ring",
                        "color": ring_color,
                        "backgroundColor": _TRACK_COLOR,
                        "width": size,
                        "height": size,
                        "strokeWidth": 6,
                    },
                ),
                (),
            ),
        ),
    )
    level_number = float(level)
    level_text = f"{int(level_number)}%" if level_number.is_integer() else f"{level_number:g}%"
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 2,
                "justifyContent": "center",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            ring,
            _battery_text(level_text, "compact-title", 14, 700),
            _battery_text(str(params["earphoneName"]), "subtitle", 10, 400),
        ),
    )


def _battery_text(
    value: str,
    design: str,
    font_size: int,
    font_weight: int,
    *,
    max_lines: int = 1,
    text_align: str | None = None,
) -> Nested2Node:
    options: dict[str, Any] = {
        "width": "matchParent",
        "fontSize": font_size,
        "fontWeight": font_weight,
        "fontColor": "#E6000000" if font_size >= 12 else "#99000000",
        "maxLines": max_lines,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if text_align is not None:
        options["textAlign"] = text_align
    return Nested2Node(
        "Text",
        (
            value,
            design,
            options,
        ),
        (),
    )


def _expand_bluetooth_device_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    layout_id: str | None,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError(
            "BluetoothDeviceOverview is not approved by Advanced Scope."
        )
    facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "BluetoothDeviceOverview requires one compatible trusted earphone entity."
        )
    parameters = call.values[0]
    if parameters.get("variant") != "earbuds":
        raise TerselConversionError(
            "BluetoothDeviceOverview currently supports the earbuds variant only."
        )
    for field in ("sourceIcon", "leftEarIcon", "rightEarIcon"):
        source = parameters.get(field)
        if source is None:
            continue
        tags = set(contract.asset_semantic_tags_by_source.get(str(source), ()))
        if not tags & {"audio", "earphone", "product"}:
            raise TerselConversionError(
                f"BluetoothDeviceOverview {field} does not match earphone semantics."
            )
    paired_with_phone = set(contract.allowed_business_component_ids) == {
        "BatteryOverview",
        "BluetoothDeviceOverview",
    }
    del layout_id
    if paired_with_phone:
        return _bluetooth_device_support_overview(
            facts,
            parameters,
            task_spec.size,
            registry,
        )
    return _bluetooth_single_overview(facts, parameters, task_spec.size, registry)


def _bluetooth_single_overview(
    facts: BluetoothDeviceOverviewFacts,
    parameters: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    header = _bluetooth_header(facts.earphone_name, parameters.get("sourceIcon"), registry)
    if not facts.is_connected:
        content = _bluetooth_text("未连接", "compact-title", 14, 500, align="start")
    else:
        content = _bluetooth_ear_metrics(
            facts,
            parameters,
            ring_size=40,
            icon_size=18,
            arrangement="row",
        )
    children = [header, content]
    if size == "2x4" and facts.case_battery_level is not None:
        children.append(
            _bluetooth_text(
                "充电盒 " + str(facts.case_battery_level) + "%",
                "subtitle",
                11,
                400,
                align="start",
            )
        )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BluetoothDeviceOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _bluetooth_device_support_overview(
    facts: BluetoothDeviceOverviewFacts,
    parameters: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    compact = size == "2x2"
    if not facts.is_connected:
        return Nested2Node(
            "Column",
            (
                "compact",
                {
                    "_advancedComponent": "BluetoothDeviceOverview",
                    "width": "matchParent",
                    "height": "matchParent",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (_bluetooth_text("未连接", "subtitle", 11, 400, align="center"),),
        )
    metrics = _bluetooth_ear_metrics(
        facts,
        parameters,
        ring_size=32 if compact else 40,
        icon_size=14 if compact else 18,
        arrangement="column" if compact else "row",
    )
    children: list[Nested2Node] = [metrics]
    if not compact:
        case_text = (
            " · 充电盒 " + str(facts.case_battery_level) + "%"
            if facts.case_battery_level is not None
            else ""
        )
        children.insert(
            0,
            _bluetooth_text(
                facts.earphone_name + case_text,
                "subtitle",
                11,
                400,
                align="start",
            ),
        )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "BluetoothDeviceOverview",
                "width": "matchParent",
                "height": "matchParent",
                "padding": 0 if compact else {"left": 8, "top": 6, "right": 8, "bottom": 6},
                "borderRadius": 0 if compact else 8,
                "backgroundColor": "#00000000" if compact else "#1A64BB5C",
                "itemMargin": 2 if compact else registry.ux_tokens["denseInnerGap"],
                "justifyContent": "center" if compact else "start",
                "alignItems": "center" if compact else "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _bluetooth_header(
    title: str,
    source_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    children: list[Nested2Node] = [
        _bluetooth_text(title, "subtitle", 12, 400, align="start", flex=True)
    ]
    if isinstance(source_icon, str):
        icon_size = registry.ux_tokens["titleSourceIconSize"]
        children.append(
            Nested2Node(
                "Image",
                (
                    source_icon,
                    "icon",
                    {
                        "width": icon_size,
                        "height": icon_size,
                        "borderRadius": 4,
                        "objectFit": "contain",
                        "fillColor": "#99000000",
                        "flexShrink": 0,
                    },
                ),
                (),
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "height": 20,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "top",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _bluetooth_ear_metrics(
    facts: BluetoothDeviceOverviewFacts,
    parameters: dict[str, Any],
    *,
    ring_size: int,
    icon_size: int,
    arrangement: Literal["row", "column"],
) -> Nested2Node:
    parts = tuple(
        (value, parameters.get(icon_field))
        for value, icon_field in (
            (facts.left_battery_level, "leftEarIcon"),
            (facts.right_battery_level, "rightEarIcon"),
        )
        if value is not None
    )
    if not parts and facts.case_battery_level is not None:
        parts = ((facts.case_battery_level, parameters.get("sourceIcon")),)
    metrics = tuple(
        _bluetooth_metric(value, icon, ring_size=ring_size, icon_size=icon_size)
        for value, icon in parts
    )
    component = "Row" if arrangement == "row" else "Column"
    return Nested2Node(
        component,
        (
            "between" if component == "Row" else "compact",
            {
                "width": "matchParent",
                "height": "matchParent" if component == "Column" else ring_size + 16,
                "itemMargin": 8 if component == "Row" else 2,
                "justifyContent": "center",
                "alignItems": "center",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        metrics,
    )


def _bluetooth_metric(
    value: int | float,
    icon: Any,
    *,
    ring_size: int,
    icon_size: int,
) -> Nested2Node:
    ring_color = _WARNING_DATA_COLOR if value <= 20 else _NORMAL_DATA_COLOR
    ring_children: list[Nested2Node] = [
        Nested2Node(
            "Progress",
            (
                {
                    "value": value,
                    "total": 100,
                    "type": "ring",
                    "color": ring_color,
                    "backgroundColor": _TRACK_COLOR,
                    "width": ring_size,
                    "height": ring_size,
                    "strokeWidth": 6,
                },
            ),
            (),
        )
    ]
    if isinstance(icon, str):
        ring_children.append(
            Nested2Node(
                "Image",
                (
                    icon,
                    "icon",
                    {
                        "width": icon_size,
                        "height": icon_size,
                        "objectFit": "contain",
                        "fillColor": _ICON_SECONDARY,
                    },
                ),
                (),
            )
        )
    ring = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": ring_size,
                "height": ring_size,
                "alignContent": "center",
                "flexShrink": 0,
            },
        ),
        tuple(ring_children),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "layoutWeight": 1,
                "itemMargin": 1,
                "justifyContent": "center",
                "alignItems": "center",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            ring,
            Nested2Node(
                "Row",
                (
                    "between",
                    {
                        "itemMargin": 1,
                        "justifyContent": "center",
                        "alignItems": "bottom",
                        "constraintSize": {"minWidth": 0, "minHeight": 0},
                    },
                ),
                (
                    _bluetooth_text(str(value), "subtitle", 12, 500, align="center"),
                    _bluetooth_text("%", "subtitle", 10, 400, align="center"),
                ),
            ),
        ),
    )


def _bluetooth_text(
    value: str,
    design: str,
    font_size: int,
    font_weight: int,
    *,
    align: Literal["start", "center"],
    flex: bool = False,
) -> Nested2Node:
    options: dict[str, Any] = {
        "width": "matchParent",
        "fontSize": font_size,
        "fontWeight": font_weight,
        "fontColor": _FONT_PRIMARY if font_weight >= 500 else _FONT_SECONDARY,
        "maxLines": 1,
        "textAlign": align,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if flex:
        options["layoutWeight"] = 1
    return Nested2Node("Text", (value, design, options), ())


def _expand_app_usage_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("AppUsageOverview is not approved by Advanced Scope.")
    facts = extract_app_usage_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "AppUsageOverview requires trusted single-app duration facts."
        )
    parameters = call.values[0]
    app_icon = parameters.get("appIcon")
    title = _app_usage_title_row(facts, app_icon, registry)
    duration = _app_usage_duration_row(facts)
    updated = (
        _app_usage_text(
            facts.updated_at,
            "subtitle",
            font_size=10,
            font_weight=400,
            font_color="#99000000",
        )
        if facts.updated_at is not None
        else None
    )
    if task_spec.size == "2x2":
        hero = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "layoutWeight": 1,
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                    "justifyContent": "center",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (duration,),
        )
        return Nested2Node(
            "Column",
            (
                "compact",
                {
                    "_advancedComponent": "AppUsageOverview",
                    "width": "matchParent",
                    "height": "matchParent",
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                    "justifyContent": "spaceBetween",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (title, hero, *((updated,) if updated is not None else ())),
        )
    duration_region = Nested2Node(
        "Column",
        (
            "compact",
            {
                "layoutWeight": 1,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "center",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (duration,),
    )
    hero = Nested2Node(
        "Column",
        (
            "compact",
            {
                "layoutWeight": 3,
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (title, duration_region),
    )
    support = (
        Nested2Node(
            "Column",
            (
                "compact",
                {
                    "layoutWeight": 2,
                    "padding": 8,
                    "borderRadius": 12,
                    "backgroundColor": "#0D000000",
                    "justifyContent": "center",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (updated,),
        )
        if updated is not None
        else None
    )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "_advancedComponent": "AppUsageOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "center",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (hero, *((support,) if support is not None else ())),
    )


def _app_usage_title_row(
    facts: AppUsageOverviewFacts,
    app_icon: Any,
    registry: CardPlanRegistry,
) -> Nested2Node:
    title = _app_usage_text(
        facts.app_name,
        "compact-title",
        font_size=12,
        font_weight=600,
        font_color="#E6000000",
    )
    children = [_merge_node_options(title, {"layoutWeight": 1})]
    if isinstance(app_icon, str):
        size = registry.ux_tokens["titleSourceIconSize"]
        children.append(
            Nested2Node(
                "Image",
                (
                    app_icon,
                    "icon",
                    {
                        "width": size,
                        "height": size,
                        "borderRadius": 4,
                        "objectFit": "contain",
                        "flexShrink": 0,
                    },
                ),
                (),
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "height": 20,
                "itemMargin": 4,
                "justifyContent": "spaceBetween",
                "alignItems": "top",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _app_usage_duration_row(facts: AppUsageOverviewFacts) -> Nested2Node:
    parts = facts.duration
    children = [
        _app_usage_text(
            parts.primary_value,
            "title",
            font_size=30,
            font_weight=700,
            font_color="#E6000000",
        ),
        _app_usage_text(
            parts.primary_unit,
            "subtitle",
            font_size=12,
            font_weight=400,
            font_color="#99000000",
        ),
    ]
    if parts.secondary_value is not None:
        children.extend(
            (
                _app_usage_text(
                    parts.secondary_value,
                    "title",
                    font_size=30,
                    font_weight=700,
                    font_color="#E6000000",
                ),
                _app_usage_text(
                    parts.secondary_unit or "",
                    "subtitle",
                    font_size=12,
                    font_weight=400,
                    font_color="#99000000",
                ),
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": 2,
                "justifyContent": "start",
                "alignItems": "bottom",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _app_usage_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    font_color: str,
) -> Nested2Node:
    return Nested2Node(
        "Text",
        (
            value,
            design,
            {
                "fontSize": font_size,
                "minFontSize": font_size,
                "fontWeight": font_weight,
                "fontColor": font_color,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (),
    )


def _expand_resource_usage_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    layout_id: str | None,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError(
            "ResourceUsageOverview is not approved by Advanced Scope."
        )
    facts = extract_resource_usage_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "ResourceUsageOverview requires complete trusted memory usage facts."
        )
    parameters = call.values[0]
    role = str(parameters["role"])
    icon = parameters.get("icon")
    show_title = parameters.get("showTitle", True)
    compact_peer = task_spec.size == "2x2" and layout_id == "PeerPairLayout"
    ring_size = 44 if compact_peer else 52
    ring = _resource_usage_ring(
        facts,
        ring_size=ring_size,
        icon=icon,
        show_center_percent=not isinstance(icon, str),
    )
    if role == "peer":
        children: list[Nested2Node] = []
        if show_title:
            children.append(
                _resource_usage_text(
                    "内存占用",
                    "compact-title",
                    font_size=12,
                    font_weight=600,
                )
            )
        children.append(ring)
        if isinstance(icon, str):
            children.append(
                _resource_usage_percent_row(
                    facts,
                    font_size=14,
                    width="matchParent",
                    justify_content="center",
                )
            )
        children.extend(
            (
                _resource_usage_text(
                    facts.available_mem_text,
                    "subtitle",
                    font_size=10,
                    font_weight=400,
                    fill_width=True,
                    text_align="center",
                ),
                _resource_usage_text(
                    facts.total_mem_text,
                    "subtitle",
                    font_size=10,
                    font_weight=400,
                    fill_width=True,
                    text_align="center",
                ),
            )
        )
        return Nested2Node(
            "Column",
            (
                "compact",
                {
                    "_advancedComponent": "ResourceUsageOverview",
                    "width": "matchParent",
                    "height": "matchParent",
                    "itemMargin": 2,
                    "justifyContent": "center",
                    "alignItems": "center",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            tuple(children),
        )
    details = Nested2Node(
        "Column",
        (
            "compact",
            {
                "layoutWeight": 1,
                "itemMargin": 4,
                "justifyContent": "center",
                "alignItems": "start",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _resource_usage_text(
                facts.available_mem_text,
                "body",
                font_size=14,
                font_weight=500,
            ),
            _resource_usage_text(
                facts.total_mem_text,
                "subtitle",
                font_size=10,
                font_weight=400,
            ),
        ),
    )
    content = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "layoutWeight": 1,
                "itemMargin": 8,
                "justifyContent": "start",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (ring, details),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "ResourceUsageOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 8,
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            _resource_usage_text(
                "内存占用",
                "compact-title",
                font_size=12,
                font_weight=600,
            ),
            content,
        ),
    )


def _resource_usage_ring(
    facts: ResourceUsageOverviewFacts,
    *,
    ring_size: int,
    icon: Any,
    show_center_percent: bool,
) -> Nested2Node:
    children: list[Nested2Node] = [
        Nested2Node(
            "Progress",
            (
                {
                    "value": facts.usage_percent,
                    "total": 100,
                    "type": "ring",
                    "width": ring_size,
                    "height": ring_size,
                    "strokeWidth": 6,
                    "color": _NORMAL_DATA_COLOR,
                    "backgroundColor": _TRACK_COLOR,
                },
            ),
            (),
        )
    ]
    if isinstance(icon, str):
        children.append(
            Nested2Node(
                "Image",
                (
                    icon,
                    "icon",
                    {
                        "width": 24,
                        "height": 24,
                        "objectFit": "contain",
                        "fillColor": _ICON_SECONDARY,
                    },
                ),
                (),
            )
        )
    elif show_center_percent:
        children.append(
            _resource_usage_percent_row(
                facts,
                font_size=14,
                width=ring_size,
                justify_content="center",
            )
        )
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": ring_size,
                "height": ring_size,
                "alignContent": "center",
                "flexShrink": 0,
            },
        ),
        tuple(children),
    )


def _resource_usage_percent_row(
    facts: ResourceUsageOverviewFacts,
    *,
    font_size: int,
    width: int | str | None = None,
    justify_content: str = "start",
) -> Nested2Node:
    number = str(facts.usage_percent)
    options: dict[str, Any] = {
        "itemMargin": 1,
        "justifyContent": justify_content,
        "alignItems": "bottom",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if width is not None:
        options["width"] = width
    return Nested2Node(
        "Row",
        (
            "between",
            options,
        ),
        (
            _resource_usage_text(
                number,
                "body",
                font_size=font_size,
                font_weight=600,
            ),
            _resource_usage_text("%", "subtitle", font_size=10, font_weight=400),
        ),
    )


def _resource_usage_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    fill_width: bool = False,
    text_align: str | None = None,
    font_color: str | None = None,
) -> Nested2Node:
    options: dict[str, Any] = {
        "fontSize": font_size,
        "minFontSize": font_size,
        "fontWeight": font_weight,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if fill_width:
        options["width"] = "matchParent"
    if text_align is not None:
        options["textAlign"] = text_align
    if font_color is not None:
        options["fontColor"] = font_color
    return Nested2Node(
        "Text",
        (
            value,
            design,
            options,
        ),
        (),
    )


def _expand_schedule_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    layout_id: str | None,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("ScheduleOverview is not approved by Advanced Scope.")
    facts = extract_schedule_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "ScheduleOverview requires one coherent trusted title and timeText."
        )
    parameters = call.values[0]
    variant = str(parameters["variant"])
    if variant == "meetingExpanded" and facts.location is None:
        variant = "meetingCompact"
    if variant == "focusContext":
        approved = set(approved_schedule_focus_action_ids(task_spec))
        content_event_ids = {
            binding.event_id
            for binding in contract.action_bindings
            if binding.action_id in contract.content_action_ids
        }
        focus_is_closed = schedule_query_requests_focus(task_spec.userQuery) and bool(
            approved & content_event_ids
        )
        if not focus_is_closed:
            raise TerselConversionError(
                "ScheduleOverview focusContext requires an approved focus Action."
            )
    parameters = _normalize_schedule_optional_asset_params(parameters, facts, contract)
    _validate_schedule_asset_params(parameters, facts, contract)
    del layout_id
    role = str(parameters["role"])
    is_2x2_support = task_spec.size == "2x2" and role == "support"
    font_sizes = (14, 12, 10) if is_2x2_support else (20, 14, 10)
    if task_spec.size == "2x4" and role == "support":
        font_sizes = (16, 14, 10)
    show_location = facts.location is not None and (
        role == "hero"
        or task_spec.size == "2x4"
        or "DateOverview" in contract.allowed_business_component_ids
    )
    return _schedule_overview_tree(
        facts,
        variant=variant,
        font_sizes=font_sizes,
        show_location=show_location,
        source_icon=parameters.get("sourceIcon"),
        time_icon=parameters.get("timeIcon"),
        location_icon=parameters.get("locationIcon"),
        primary_color=registry.require_theme(contract.theme_profile_id).primary_color,
        support_content_color=registry.require_theme(
            contract.theme_profile_id
        ).support_content_color,
        registry=registry,
    )


def _validate_schedule_asset_params(
    parameters: dict[str, Any],
    facts: ScheduleOverviewFacts,
    contract: HybridBodyContract,
) -> None:
    requirements = {
        "sourceIcon": {"calendar", "schedule"},
        "timeIcon": {"time"},
        "locationIcon": {"location"},
    }
    for field, expected_tags in requirements.items():
        source = parameters.get(field)
        if source is None:
            continue
        actual_tags = set(contract.asset_semantic_tags_by_source.get(str(source), ()))
        if not actual_tags & expected_tags:
            raise TerselConversionError(
                f"ScheduleOverview {field} does not match TaskSpec asset semantics."
            )
    if parameters.get("locationIcon") is not None and facts.location is None:
        raise TerselConversionError(
            "ScheduleOverview locationIcon requires a trusted location."
        )


def _normalize_schedule_optional_asset_params(
    parameters: dict[str, Any],
    facts: ScheduleOverviewFacts,
    contract: HybridBodyContract,
) -> dict[str, Any]:
    """Drop optional detail icons when the model reuses an unrelated approved asset."""
    normalized = dict(parameters)
    for field, expected_tags in (
        ("timeIcon", {"time"}),
        ("locationIcon", {"location"}),
    ):
        source = normalized.get(field)
        if source is None:
            continue
        actual_tags = set(contract.asset_semantic_tags_by_source.get(str(source), ()))
        if not actual_tags & expected_tags:
            normalized.pop(field, None)
    if facts.location is None:
        normalized.pop("locationIcon", None)
    return normalized


def _schedule_overview_tree(
    facts: ScheduleOverviewFacts,
    *,
    variant: str,
    font_sizes: tuple[int, int, int],
    show_location: bool,
    source_icon: Any,
    time_icon: Any,
    location_icon: Any,
    primary_color: str,
    support_content_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    secondary_color = support_content_color
    metadata_color = support_content_color
    accent_color = primary_color
    rail_color = _theme_color_with_alpha(primary_color, 0x52)
    text_column_children = [
        _schedule_text(
            facts.title,
            "title",
            font_size=font_sizes[0],
            font_weight=700,
            font_color=primary_color,
        ),
        _schedule_metadata(
            facts.time_text,
            time_icon,
            font_size=font_sizes[1],
            font_color=secondary_color,
        ),
    ]
    if show_location and facts.location is not None:
        text_column_children.append(
            _schedule_metadata(
                facts.location,
                location_icon,
                font_size=font_sizes[2],
                font_color=metadata_color,
            )
        )
    divider_height = (
        sum(font_sizes[: len(text_column_children)])
        + (registry.ux_tokens["denseInnerGap"] * (len(text_column_children) - 1))
        - 10
    )
    text_column = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "100%",
                "height": "100%",
                "layoutWeight": 1,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(text_column_children),
    )
    body = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "100%",
                "height": "100%",
                "layoutWeight": 1,
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "start",
                "alignItems": "center",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (_schedule_rail(accent_color, rail_color, divider_height), text_column),
    )
    children: list[Nested2Node] = []
    if variant == "nextEvent" or isinstance(source_icon, str):
        children.append(_schedule_header(source_icon, secondary_color, accent_color, registry))
    else:
        return _merge_node_options(body, {"_advancedComponent": "ScheduleOverview"})
    children.append(body)
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "ScheduleOverview",
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        tuple(children),
    )


def _schedule_header(
    source_icon: Any,
    secondary_color: str,
    accent_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    label = _schedule_text(
        "下一个日程",
        "subtitle",
        font_size=12,
        font_weight=400,
        font_color=secondary_color,
    )
    children: list[Nested2Node] = [_merge_node_options(label, {"layoutWeight": 1})]
    if isinstance(source_icon, str):
        size = 12
        children.append(
            Nested2Node(
                "Image",
                (
                    source_icon,
                    "icon",
                    {
                        "width": size,
                        "height": size,
                        "objectFit": "contain",
                        "fillColor": accent_color,
                    },
                ),
                (),
            )
        )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "100%",
                "height": 12,
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "top",
                "clip": True,
            },
        ),
        tuple(children),
    )


def _schedule_rail(
    accent_color: str,
    rail_color: str,
    divider_height: int,
) -> Nested2Node:
    invisible_fill = Nested2Node(
        "Divider",
        ({"width": 0, "height": 0, "strokeWidth": 0, "color": "#00FFFFFF"},),
        (),
    )
    dot = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": 8,
                "height": 8,
                "borderRadius": 4,
                "borderWidth": 2,
                "borderColor": accent_color,
                "backgroundColor": "#00FFFFFF",
                "alignContent": "center",
                "flexShrink": 0,
            },
        ),
        (invisible_fill,),
    )
    divider = Nested2Node(
        "Divider",
        (
            {
                "width": 1,
                "height": max(divider_height, 0),
                "strokeWidth": 1,
                "vertical": True,
                "color": rail_color,
            },
        ),
        (),
    )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": 8,
                "height": "100%",
                "itemMargin": 2,
                "justifyContent": "start",
                "alignItems": "center",
                "flexShrink": 0,
                "clip": True,
            },
        ),
        (dot, divider),
    )


def _schedule_metadata(
    value: str,
    icon: Any,
    *,
    font_size: int,
    font_color: str,
) -> Nested2Node:
    text = _schedule_text(
        value,
        "subtitle",
        font_size=font_size,
        font_weight=400,
        font_color=font_color,
    )
    if not isinstance(icon, str):
        return text
    image = Nested2Node(
        "Image",
        (icon, "icon", {"width": 12, "height": 12, "objectFit": "contain"}),
        (),
    )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "100%",
                "itemMargin": 4,
                "justifyContent": "start",
                "alignItems": "top",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (image, _merge_node_options(text, {"layoutWeight": 1})),
    )


def _schedule_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    font_color: str,
) -> Nested2Node:
    return Nested2Node(
        "Text",
        (
            value,
            design,
            {
                "width": "100%",
                "fontSize": font_size,
                "minFontSize": font_size,
                "fontWeight": font_weight,
                "fontColor": font_color,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (),
    )


def _expand_weather_overview_call(
    call: ParsedCall,
    *,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    layout_id: str | None,
) -> Nested2Node:
    if call.name not in contract.allowed_business_component_ids:
        raise TerselConversionError("WeatherOverview is not approved by Advanced Scope.")
    facts = extract_weather_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        raise TerselConversionError(
            "WeatherOverview requires five complete trusted string facts."
        )
    parameters = call.values[0]
    role = str(parameters["role"])
    compact = role != "hero" or (
        task_spec.size == "2x2" and layout_id in {"HeroSupportLayout", "HeroSupportActionLayout"}
    )
    icon_size = 20
    temperature_size = 30 if role in {"support", "peer"} else 38
    if task_spec.size == "2x2" and compact:
        temperature_size = 32
    primary_size = 12 if compact else 14
    range_size = 10 if compact else 12
    condition_icon = str(parameters["conditionIcon"])
    condition_icon_options: dict[str, Any] = {
        "width": icon_size,
        "height": icon_size,
        "objectFit": "contain",
        "flexShrink": 0,
    }
    if _weather_icon_is_sun(condition_icon, contract):
        condition_icon_options["fillColor"] = _SUNNY_WEATHER_ICON_COLOR
    else:
        icon_tags = set(contract.asset_semantic_tags_by_source.get(condition_icon, ()))
        if _weather_icon_is_multicolor(condition_icon):
            condition_icon_options["_preserveOriginalColor"] = True
        elif icon_tags & {"water", "rain", "drop", "cloud", "storm", "snow"}:
            condition_icon_options["fillColor"] = "#FFFFFFFF"
        else:
            condition_icon_options["fillColor"] = "#FFFFFFFF"
    title = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "height": 20,
                "padding": {"right": 12},
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "spaceBetween",
                "alignItems": "top",
                "clip": True,
            },
        ),
        (
            _weather_text(
                facts.city,
                "compact-title",
                font_size=12,
                font_weight=400,
                layout_weight=1,
            ),
            Nested2Node(
                "Image",
                (
                    condition_icon,
                    "icon",
                    condition_icon_options,
                ),
                (),
            ),
        ),
    )
    primary = Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "matchParent",
                "itemMargin": 0,
                "justifyContent": "start",
                "alignItems": "center",
            },
        ),
        (
            _weather_text(
                facts.condition,
                "body",
                font_size=primary_size,
                font_weight=500,
            ),
            _weather_text(
                "｜",
                "body",
                font_size=primary_size,
                font_weight=500,
            ),
            _weather_text(
                facts.air_quality,
                "body",
                font_size=primary_size,
                font_weight=500,
            ),
        ),
    )
    if task_spec.size == "2x2" and layout_id == "SingleFocusLayout" and role == "hero":
        temperature = _weather_text(
            facts.temperature,
            "title",
            font_size=temperature_size,
            font_weight=800,
            min_font_size=temperature_size,
        )
        range_text = _weather_text(
            facts.temperature_range,
            "subtitle",
            font_size=range_size,
            font_weight=400,
        )
        bottom = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "width": "matchParent",
                    "itemMargin": 4,
                    "alignItems": "start",
                },
            ),
            (primary, range_text),
        )
        return Nested2Node(
            "Column",
            (
                "compact",
                {
                    "_advancedComponent": "WeatherOverview",
                    "width": "matchParent",
                    "height": "matchParent",
                    "itemMargin": 4,
                    "justifyContent": "spaceBetween",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (title, temperature, bottom),
        )
    if task_spec.size == "2x4" and layout_id == "SingleFocusLayout" and role == "hero":
        top = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "width": "matchParent",
                    "itemMargin": 4,
                    "alignItems": "start",
                },
            ),
            (
                title,
                _weather_text(
                    facts.temperature,
                    "title",
                    font_size=temperature_size,
                    font_weight=800,
                    min_font_size=temperature_size,
                ),
            ),
        )
        wide_primary = Nested2Node(
            "Row",
            (
                "between",
                {
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                    "justifyContent": "start",
                    "alignItems": "center",
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            primary.children,
        )
        bottom = Nested2Node(
            "Row",
            (
                "between",
                {
                    "width": "matchParent",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                    "justifyContent": "spaceBetween",
                    "alignItems": "end",
                },
            ),
            (
                wide_primary,
                _weather_text(
                    facts.temperature_range,
                    "subtitle",
                    font_size=range_size,
                    font_weight=400,
                ),
            ),
        )
        return Nested2Node(
            "Column",
            (
                "compact",
                {
                    "_advancedComponent": "WeatherOverview",
                    "width": "matchParent",
                    "height": "matchParent",
                    "justifyContent": "spaceBetween",
                    "alignItems": "start",
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (top, bottom),
        )
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "_advancedComponent": "WeatherOverview",
                "width": "matchParent",
                "height": "matchParent",
                "itemMargin": 4,
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (
            title,
            _weather_text(
                facts.temperature,
                "title",
                font_size=temperature_size,
                font_weight=800,
                min_font_size=temperature_size,
            ),
            primary,
            _weather_text(
                facts.temperature_range,
                "subtitle",
                font_size=range_size,
                font_weight=400,
            ),
        ),
    )


def _weather_icon_is_sun(
    condition_icon: str,
    contract: HybridBodyContract,
) -> bool:
    icon_tags = set(contract.asset_semantic_tags_by_source.get(condition_icon, ()))
    return bool(icon_tags & {"sun", "sunny"})


def _weather_icon_is_multicolor(condition_icon: str) -> bool:
    """Recognize the bundled full-color weather artwork family.

    These SVGs contain several gradients but may still carry a cloud scene tag.
    Applying a monochrome fill to them turns the rendered artwork into a solid
    rectangle on device.
    """
    filename = condition_icon.rsplit("/", 1)[-1].casefold()
    return filename.startswith("icon_weather") or filename.startswith("weather_icon")


def _weather_text(
    value: str,
    design: str,
    *,
    font_size: int,
    font_weight: int,
    min_font_size: int | None = None,
    layout_weight: int | None = None,
) -> Nested2Node:
    options: dict[str, Any] = {
        "fontSize": font_size,
        "fontWeight": font_weight,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "constraintSize": {"minWidth": 0, "minHeight": 0},
    }
    if min_font_size is not None:
        options["minFontSize"] = min_font_size
    if layout_weight is not None:
        options["layoutWeight"] = layout_weight
    return Nested2Node("Text", (value, design, options), ())


def _validate_template_params(
    params: dict[str, Any],
    asset_tags: dict[str, tuple[str, ...]],
    contract: HybridBodyContract,
) -> None:
    for key, value in params.items():
        values = _primitive_values(value)
        is_asset_parameter = any(
            token in key.casefold() for token in ("icon", "image", "asset", "source", "src")
        )
        for item in values:
            if item == "":
                continue
            if isinstance(item, str) and is_asset_parameter:
                if item not in contract.allowed_asset_sources:
                    raise TerselConversionError(f"Template asset is not approved: {item}")
                required_tags = set(asset_tags.get(key, ()))
                actual_tags = set(contract.asset_semantic_tags_by_source.get(item, ()))
                if required_tags and not required_tags.issubset(actual_tags):
                    raise TerselConversionError(
                        f"Template asset semantics do not match {key}: {item}"
                    )
            elif isinstance(item, str) and not _is_trusted_template_literal(
                item,
                contract.trusted_literals,
            ):
                action_ids = {binding.action_id for binding in contract.action_bindings}
                if item not in action_ids:
                    raise TerselConversionError(f"Template literal is not trusted: {item}")
            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                if item not in contract.trusted_numbers and item not in {0, 1, 100}:
                    raise TerselConversionError(f"Template number is not trusted: {item}")


def _validate_template_parameter_relations(
    params: dict[str, Any],
    relations: tuple[TemplateParameterRelation, ...],
) -> None:
    for relation in relations:
        number = params[relation.number_parameter]
        text = params[relation.text_parameter]
        if relation.kind != "number-matches-text":
            raise TerselConversionError("Unknown Template parameter relation.")
        if not isinstance(number, (int, float)) or isinstance(number, bool):
            raise TerselConversionError("Template relation number is invalid.")
        if not isinstance(text, str):
            raise TerselConversionError("Template relation text is invalid.")
        canonical = str(int(number)) if float(number).is_integer() else str(number)
        candidates = {canonical + suffix for suffix in relation.allowed_suffixes}
        if text not in candidates:
            raise TerselConversionError(
                "Template number/text parameter relation does not match."
            )


def _is_trusted_template_literal(value: str, trusted_literals: tuple[str, ...]) -> bool:
    """允许模板把多个已信任的叶子字面量拼接为一个展示字符串。

    拼接必须完全由 Contract 已提供的非空原子覆盖；不允许从原字符串中
    任意截取，也不增加单位、标点或业务文案。这样可以安全表示例如
    ``"6" + "小时" + "45" + "分"`` 的紧凑组合，同时继续拒绝模型自行派生的文本。
    """
    if value in trusted_literals:
        return True
    atoms = tuple(
        sorted(
            {
                literal
                for literal in trusted_literals
                if literal and literal != value and len(literal) <= len(value)
            },
            key=lambda item: (-len(item), item),
        )
    )
    if not value or not atoms:
        return False
    reachable = {0}
    for index in range(len(value)):
        if index not in reachable:
            continue
        for atom in atoms:
            if value.startswith(atom, index):
                reachable.add(index + len(atom))
    return len(value) in reachable


def _normalize_template_asset_params(
    params: dict[str, Any],
    asset_tags: dict[str, tuple[str, ...]],
    contract: HybridBodyContract,
    *,
    required_parameters: frozenset[str],
) -> dict[str, Any]:
    normalized = dict(params)
    for key, value in params.items():
        is_asset_parameter = any(
            token in key.casefold() for token in ("icon", "image", "asset", "source", "src")
        )
        if not is_asset_parameter or not isinstance(value, str):
            continue
        if value == "":
            if key in required_parameters:
                raise TerselConversionError(
                    f"Required Template asset cannot be empty: {key}"
                )
            normalized.pop(key, None)
            continue
        if value not in contract.allowed_asset_sources:
            raise TerselConversionError(f"Template asset is not approved: {value}")
        required_tags = set(asset_tags.get(key, ()))
        actual_tags = set(contract.asset_semantic_tags_by_source.get(value, ()))
        if not required_tags or required_tags.issubset(actual_tags):
            continue
        candidates = [
            source
            for source in contract.allowed_asset_sources
            if required_tags.issubset(set(contract.asset_semantic_tags_by_source.get(source, ())))
        ]
        if len(candidates) != 1:
            raise TerselConversionError(
                f"Template asset semantics do not match {key}: {value}"
            )
        normalized[key] = candidates[0]
    return normalized


def _primitive_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        result: list[Any] = []
        for child in value.values():
            result.extend(_primitive_values(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(_primitive_values(child))
        return result
    return [value]


def _instantiate_blueprint(
    node: TemplateNode,
    params: dict[str, Any],
    bindings: dict[str, str] | None = None,
    theme_values: dict[str, object] | None = None,
    *,
    spread_children: tuple[Nested2Node, ...] = (),
) -> Nested2Node:
    binding_values = bindings or {}
    resolved_theme_values = theme_values or {}
    if node.component == TEMPLATE_CHILD_SLOT_COMPONENT:
        raise TerselConversionError(
            "Template child slot cannot be instantiated as a component root."
        )
    if node.component in _TEMPLATE_CONDITIONS:
        raise TerselConversionError(
            "Template conditional cannot be instantiated as a component root."
        )
    if node.component == "Text" and node.values and node.values[0].kind == "interpolation":
        return _instantiate_interpolated_text(
            node,
            params,
            binding_values,
            resolved_theme_values,
        )
    values = [
        _template_value(item, params, binding_values, resolved_theme_values)
        for item in node.values
    ]
    normalized = _normalize_blueprint_values(node.component, values)
    return Nested2Node(
        component_type=node.component,
        values=tuple(normalized),
        children=(
            *_instantiate_blueprint_children(
                node.children,
                params,
                binding_values,
                resolved_theme_values,
                spread_children=spread_children,
            ),
            *(spread_children if node.spread_children else ()),
        ),
    )


def _instantiate_blueprint_children(
    children: tuple[TemplateNode, ...],
    params: dict[str, Any],
    bindings: dict[str, str],
    theme_values: dict[str, object],
    *,
    spread_children: tuple[Nested2Node, ...] = (),
) -> tuple[Nested2Node, ...]:
    instantiated: list[Nested2Node] = []
    for child in children:
        child_slot_index = _template_child_slot_index(child)
        if child_slot_index is not None:
            if child_slot_index >= len(spread_children):
                raise TerselConversionError(
                    f"Template child slot is missing: children[{child_slot_index}]"
                )
            instantiated.append(spread_children[child_slot_index])
            continue
        if child.component in _TEMPLATE_CONDITIONS:
            should_render = _template_condition_should_render(child, params, bindings)
            if should_render:
                selected = child.children[0]
                if selected.component in _TEMPLATE_CONDITIONS:
                    instantiated.extend(
                        _instantiate_blueprint_children(
                            (selected,),
                            params,
                            bindings,
                            theme_values,
                            spread_children=spread_children,
                        )
                    )
                else:
                    instantiated.append(
                        _instantiate_blueprint(
                            selected,
                            params,
                            bindings,
                            theme_values,
                            spread_children=spread_children,
                        )
                    )
            continue
        instantiated.append(
            _instantiate_blueprint(
                child,
                params,
                bindings,
                theme_values,
                spread_children=spread_children,
            )
        )
    return tuple(instantiated)


def _template_condition_should_render(
    node: TemplateNode,
    params: dict[str, Any],
    bindings: dict[str, str],
) -> bool:
    if node.component in _GROUPED_TEMPLATE_CONDITIONS:
        binding_names = _template_condition_binding_names(node)
        all_present = all(name in bindings for name in binding_names)
        return all_present if node.component == "IfAllBind" else not all_present
    guard_name = node.values[0].value
    if not isinstance(guard_name, str):
        raise TerselConversionError("Template conditional guard must be a string.")
    if node.component in {"IfParam", "IfMissingParam"}:
        present = guard_name in params and params[guard_name] is not None
    else:
        present = guard_name in bindings
    return present if node.component in {"IfParam", "IfBind"} else not present


def _template_condition_binding_names(node: TemplateNode) -> tuple[str, str]:
    if len(node.values) != 1 or node.values[0].kind != "array":
        raise TerselConversionError(
            "Template grouped conditional requires two binding names."
        )
    items = node.values[0].items
    if len(items) != 2:
        raise TerselConversionError(
            "Template grouped conditional requires two binding names."
        )
    binding_names: list[str] = []
    for item in items:
        if item.kind != "literal" or not isinstance(item.value, str):
            raise TerselConversionError(
                "Template grouped conditional binding must be a string."
            )
        binding_names.append(item.value)
    return binding_names[0], binding_names[1]


def _template_child_slot_index(node: TemplateNode) -> int | None:
    if node.component != TEMPLATE_CHILD_SLOT_COMPONENT:
        return None
    value = node.values[0].value if len(node.values) == 1 else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TerselConversionError("Template contains an invalid child slot.")
    return value


def _template_child_slot_indexes(root: TemplateNode) -> tuple[int, ...]:
    indexes: list[int] = []

    def visit(node: TemplateNode) -> None:
        child_slot_index = _template_child_slot_index(node)
        if child_slot_index is not None:
            indexes.append(child_slot_index)
            return
        for child in node.children:
            visit(child)

    visit(root)
    return tuple(indexes)


def _template_spread_parent(root: TemplateNode) -> str | None:
    matches: list[str] = []

    def visit(node: TemplateNode) -> None:
        if node.spread_children:
            matches.append(node.component)
        for child in node.children:
            visit(child)

    visit(root)
    if len(matches) > 1:
        raise TerselConversionError("Template may contain only one children slot.")
    return matches[0] if matches else None


def _template_value(
    value: TemplateValue,
    params: dict[str, Any],
    bindings: dict[str, str],
    theme_values: dict[str, object],
) -> Any:
    resolved_value: Any
    if value.kind == "literal":
        resolved_value = value.value
    elif value.kind == "parameter":
        if value.name not in params:
            raise TerselConversionError(f"Template parameter is missing: {value.name}")
        resolved_value = params[value.name]
    elif value.kind == "optional-parameter":
        resolved_value = params.get(value.name)
    elif value.kind == "binding":
        if value.name not in bindings:
            raise TerselConversionError(f"Template binding is missing: {value.name}")
        resolved_value = bindings[value.name]
    elif value.kind == "theme":
        if value.name not in theme_values:
            raise TerselConversionError(
                f"Template Theme reference is unavailable: {value.name}"
            )
        resolved_value = theme_values[value.name]
    elif value.kind == "interpolation":
        raise TerselConversionError("Template interpolation must be the first Text value.")
    elif value.kind == "expression":
        resolved_value = _provider_runtime_expression(value, bindings)
    elif value.kind == "compile-time-conditional":
        resolved_value = _provider_compile_time_conditional(
            value,
            params,
            bindings,
            theme_values,
        )
    elif value.kind == "event-action":
        if len(value.items) != 1:
            raise TerselConversionError("Template EventAction is invalid.")
        parameter = value.items[0]
        if parameter.kind not in {"parameter", "optional-parameter"}:
            raise TerselConversionError("Template EventAction is invalid.")
        action_id = _template_value(parameter, params, bindings, theme_values)
        if action_id is None and parameter.kind == "optional-parameter":
            resolved_value = None
        else:
            if not isinstance(action_id, str):
                raise TerselConversionError("Template EventAction ID is invalid.")
            resolved_value = [
                {"call": "sendToAssistant", "args": {"eventName": action_id}}
            ]
    elif value.kind == "array":
        resolved_value = [
            _template_value(item, params, bindings, theme_values) for item in value.items
        ]
    else:
        properties: dict[str, Any] = {}
        for key, item in value.properties.items():
            resolved = _template_value(item, params, bindings, theme_values)
            if item.kind == "event-action" and resolved is None:
                continue
            properties[key] = resolved
        resolved_value = properties
    return resolved_value


def _provider_compile_time_conditional(
    value: TemplateValue,
    params: dict[str, Any],
    bindings: dict[str, str],
    theme_values: dict[str, object],
) -> Any:
    if len(value.items) != 3:
        raise TerselConversionError("Template compile-time conditional is invalid.")
    condition, present_value, fallback_value = value.items
    if condition.kind == "binding" and condition.name:
        present = condition.name in bindings
    elif condition.kind == "parameter" and condition.name:
        present = condition.name in params and params[condition.name] is not None
    else:
        raise TerselConversionError(
            "Template compile-time conditional condition must be data or props."
        )
    selected = present_value if present else fallback_value
    return _template_value(selected, params, bindings, theme_values)


def _instantiate_interpolated_text(
    node: TemplateNode,
    params: dict[str, Any],
    bindings: dict[str, str],
    theme_values: dict[str, object],
) -> Nested2Node:
    if node.children:
        raise TerselConversionError("Template interpolation Text cannot contain children.")
    expression = _provider_interpolation_expression(node.values[0], params, bindings)
    shared_values = [
        _template_value(item, params, bindings, theme_values) for item in node.values[1:]
    ]
    return Nested2Node(
        "Text",
        tuple(_normalize_blueprint_values("Text", [expression, *shared_values])),
        (),
    )


def _provider_interpolation_expression(
    value: TemplateValue,
    params: dict[str, Any],
    bindings: dict[str, str],
) -> str:
    if not any(item.kind == "binding" for item in value.items):
        return _provider_static_interpolation(value, params)
    operands: list[str] = []
    for item in value.items:
        if item.kind == "binding":
            placeholder = bindings.get(item.name or "")
            if placeholder is None:
                raise TerselConversionError(f"Template binding is missing: {item.name}")
            operands.append(_a2ui_expression_reference(placeholder))
            continue
        if item.kind == "parameter":
            parameter = params.get(item.name or "")
            if not isinstance(parameter, str):
                raise TerselConversionError(
                    f"Template interpolation prop must be a string: {item.name}"
                )
            operands.append(_a2ui_expression_string(parameter))
            continue
        if item.kind == "literal" and isinstance(item.value, str):
            operands.append(_a2ui_expression_string(item.value))
            continue
        raise TerselConversionError(
            "Template interpolation only supports string data, props and literals."
        )
    if not operands:
        raise TerselConversionError("Template interpolation cannot be empty.")
    try:
        return normalize_tersel_expression(" + ".join(operands)).value
    except A2UIExpressionError as exc:
        raise TerselConversionError(
            f"Template interpolation is not a valid A2UI expression: {exc}"
        ) from exc


def _provider_static_interpolation(
    value: TemplateValue,
    params: dict[str, Any],
) -> str:
    parts: list[str] = []
    for item in value.items:
        if item.kind == "parameter":
            parameter = params.get(item.name or "")
            if not isinstance(parameter, str):
                raise TerselConversionError(
                    f"Template interpolation prop must be a string: {item.name}"
                )
            parts.append(parameter)
            continue
        if item.kind == "literal" and isinstance(item.value, str):
            parts.append(item.value)
            continue
        raise TerselConversionError(
            "Static Template interpolation only supports string props and literals."
        )
    if not parts:
        raise TerselConversionError("Template interpolation cannot be empty.")
    return "".join(parts)


def _provider_runtime_expression(
    value: TemplateValue,
    bindings: dict[str, str],
) -> str:
    parts: list[str] = []
    for item in value.items:
        if item.kind == "binding":
            placeholder = bindings.get(item.name or "")
            if placeholder is None:
                raise TerselConversionError(f"Template binding is missing: {item.name}")
            parts.append(_a2ui_expression_reference(placeholder))
            continue
        if item.kind == "literal" and isinstance(item.value, str):
            parts.append(item.value)
            continue
        raise TerselConversionError(
            "Template Expr only supports binding placeholders and expression syntax."
        )
    body = "".join(parts).strip()
    if not body:
        raise TerselConversionError("Template Expr must contain a runtime data binding.")
    try:
        return normalize_tersel_expression(body).value
    except A2UIExpressionError as exc:
        raise TerselConversionError(
            f"Template Expr is not a valid A2UI expression: {exc}"
        ) from exc


def _a2ui_expression_reference(placeholder: str) -> str:
    match = re.fullmatch(r"\$\{(data(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\d+)+)\}", placeholder)
    if match is None:
        raise TerselConversionError(
            "Template interpolation binding is not a runtime data path."
        )
    return "${/" + match.group(1).replace(".", "/") + "}"


def _a2ui_expression_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f"'{escaped}'"


def _provider_binding_roots(card_spec: dict[str, Any] | None) -> dict[str, str]:
    if card_spec is None:
        return {}
    raw_bindings = card_spec.get("dataBindings")
    if not isinstance(raw_bindings, list):
        return {}
    roots: dict[str, str] = {}
    for raw_binding in raw_bindings:
        if not isinstance(raw_binding, dict):
            continue
        capability_id = raw_binding.get("capabilityId")
        root = raw_binding.get("writeResultTo")
        if not isinstance(capability_id, str) or not _valid_runtime_binding_root(root):
            continue
        existing = roots.get(capability_id)
        if existing is not None and existing != root:
            raise TerselConversionError(
                f"CardSpec has ambiguous data roots for capability: {capability_id}"
            )
        roots[capability_id] = root
    return roots


def _valid_runtime_binding_root(value: Any) -> bool:
    return isinstance(value, str) and (value == "/data" or value.startswith("/data/"))


def _provider_template_binding_values(
    definition: TemplateDefinition,
    variant: TemplateVariant,
    task_spec: TaskSpec,
    binding_roots: dict[str, str],
) -> dict[str, str]:
    if definition.source_format != "cardtpl/1":
        return {}
    if not definition.bindings:
        return {}
    capability_id = definition.capability_id
    if not capability_id or capability_id not in binding_roots:
        raise TerselConversionError(
            f"Provider Template requires CardSpec.dataBindings: {definition.wire_id}"
        )
    root = binding_roots[capability_id]
    if definition.data_domain is not None and root != definition.data_domain:
        raise TerselConversionError(
            f"Provider Template dataDomain does not match CardSpec: {definition.wire_id}"
        )
    values: dict[str, str] = {}
    for name in (*variant.required_bindings, *variant.optional_bindings):
        binding = definition.bindings[name]
        path = f"{root.rstrip('/')}{binding.path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, path)
        if leaf is None:
            if name in variant.optional_bindings:
                continue
            raise TerselConversionError(
                f"Provider Template binding is not declared by TaskSpec: {name}/{path}"
            )
        if not _binding_types_match(binding.data_type, leaf.get("type")):
            raise TerselConversionError(
                f"Provider Template binding is not declared by TaskSpec: {name}/{path}"
            )
        placeholder = _runtime_binding_placeholder(path)
        if placeholder is None:
            raise TerselConversionError(
                f"Provider Template binding path cannot be encoded: {name}/{path}"
            )
        values[name] = placeholder
    missing = set(variant.required_bindings) - set(values)
    if missing:
        raise TerselConversionError(
            f"Provider Template required bindings are missing: {sorted(missing)}"
        )
    return values


def _task_spec_schema_leaf(schema: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit() and current:
            index = int(part)
            current = current[index] if index < len(current) else current[0]
            continue
        return None
    if not isinstance(current, dict) or "type" not in current:
        return None
    return current


def _binding_types_match(expected: str, actual: Any) -> bool:
    numeric_types_match = isinstance(actual, str) and {
        expected,
        actual,
    } == {"integer", "number"}
    return actual == expected or numeric_types_match


def _runtime_binding_placeholder(path: str) -> str | None:
    parts = path.removeprefix("/").split("/")
    valid_parts = all(
        part.isdigit() or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts
    )
    if not parts or parts[0] != "data" or not valid_parts:
        return None
    return "${" + ".".join(parts) + "}"


def _normalize_blueprint_values(component: str, values: list[Any]) -> list[Any]:
    is_text_with_value = component == "Text" and bool(values)
    has_numeric_value = is_text_with_value and isinstance(values[0], (int, float))
    if has_numeric_value and not isinstance(values[0], bool):
        values[0] = str(values[0])
    normalized: list[Any] = []
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("styles"), dict):
            flattened = dict(value["styles"])
            flattened.update({key: child for key, child in value.items() if key != "styles"})
            normalized.append(flattened)
        else:
            normalized.append(value)
    return list(_normalize_component_values(component, tuple(normalized)))


def _bind_template_actions(
    node: Nested2Node,
    contract: HybridBodyContract,
) -> tuple[Nested2Node, tuple[str, ...]]:
    values = list(node.values)
    used: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        bound_action_id = value.get("_boundTemplateAction")
        if bound_action_id is not None:
            _validate_bound_template_action(value, bound_action_id, contract)
            continue
        action_id = _template_action_placeholder(value)
        if action_id is None:
            continue
        binding = next(
            (
                item
                for item in contract.action_bindings
                if item.action_id == action_id and item.action_id in contract.content_action_ids
            ),
            None,
        )
        if binding is None:
            raise TerselConversionError(f"Template Action is not approved: {action_id}")
        bound = dict(value)
        bound.pop("action", None)
        bound["onClick"] = [{"call": binding.call, "args": binding.args}]
        bound["_boundTemplateAction"] = action_id
        values[index] = bound
        used.append(action_id)
    children: list[Nested2Node] = []
    for child in node.children:
        bound_child, child_ids = _bind_template_actions(child, contract)
        children.append(bound_child)
        used.extend(child_ids)
    return Nested2Node(node.component_type, tuple(values), tuple(children)), tuple(used)


def _validate_bound_template_action(
    value: dict[str, Any],
    action_id: Any,
    contract: HybridBodyContract,
) -> None:
    if not isinstance(action_id, str):
        raise TerselConversionError("Bound Template Action ID is invalid.")
    binding = next(
        (
            item
            for item in contract.action_bindings
            if item.action_id == action_id and item.action_id in contract.content_action_ids
        ),
        None,
    )
    expected = [{"call": binding.call, "args": binding.args}] if binding is not None else None
    if expected is None or value.get("onClick") != expected:
        raise TerselConversionError("Bound Template Action is invalid.")


def _template_action_placeholder(value: dict[str, Any]) -> str | None:
    if "onClick" in value:
        handlers = value["onClick"]
        if not isinstance(handlers, list) or len(handlers) != 1:
            raise TerselConversionError("Template Action placeholder is invalid.")
        handler = handlers[0]
        args = handler.get("args") if isinstance(handler, dict) else None
        action_id = args.get("eventName") if isinstance(args, dict) else None
        has_event_name_argument = isinstance(args, dict) and set(args) == {"eventName"}
        has_supported_handler = (
            isinstance(handler, dict) and handler.get("call") == "sendToAssistant"
        )
        has_valid_action_id = isinstance(action_id, str)
        if not has_event_name_argument or not has_supported_handler or not has_valid_action_id:
            raise TerselConversionError("Template Action ID is invalid.")
        return action_id
    if "action" not in value:
        return None
    action = value["action"]
    event = action.get("event") if isinstance(action, dict) else None
    action_id = event.get("name") if isinstance(event, dict) else None
    has_event_wrapper = isinstance(action, dict) and set(action) == {"event"}
    has_name_wrapper = isinstance(event, dict) and set(event) == {"name"}
    if not has_event_wrapper or not has_name_wrapper or not isinstance(action_id, str):
        raise TerselConversionError("Template Action ID is invalid.")
    return action_id


def _compile_card_shell(
    params: dict[str, Any],
    content: Nested2Node,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    theme = registry.require_theme(contract.theme_profile_id)
    root_options = _normalize_theme_styles(theme.root_style)
    ux_mixed = bool(contract.allowed_layout_component_ids)
    if ux_mixed:
        root_options.setdefault("padding", registry.ux_tokens["safeInset"])
        root_options.setdefault("borderRadius", registry.ux_tokens["radius"])
        root_options.setdefault("itemMargin", registry.ux_tokens["sectionGap"])
    if "alignContent" in root_options:
        alignment = root_options.pop("alignContent")
        root_options["alignItems"] = _column_align_items(alignment)
    root_options.pop("width", None)
    root_options.pop("height", None)
    root_options["_id"] = "root"
    children: list[Nested2Node] = []
    header_children: list[Nested2Node] = []
    if "titleIcon" in params:
        title_icon_values: tuple[Any, ...] = (params["titleIcon"], "compact-icon")
        if ux_mixed:
            icon_size = registry.ux_tokens["titleSourceIconSize"]
            title_icon_values = (*title_icon_values, {"width": icon_size, "height": icon_size})
        header_children.append(Nested2Node("Image", title_icon_values, ()))
    header_text: list[Nested2Node] = []
    if "title" in params:
        header_text.append(Nested2Node("Text", (params["title"], "compact-title"), ()))
    if "subtitle" in params:
        header_text.append(Nested2Node("Text", (params["subtitle"], "subtitle"), ()))
    header_height = 34 if len(header_text) > 1 else 18
    if len(header_text) > 1:
        header_children.append(
            Nested2Node(
                "Column",
                (
                    "compact",
                    {
                        "height": 32,
                        "itemMargin": 0,
                        "justifyContent": "start",
                        "layoutWeight": 1,
                    },
                ),
                tuple(header_text),
            )
        )
    else:
        header_children.extend(header_text)
    if header_children:
        children.append(
            Nested2Node(
                "Row",
                (
                    "between",
                    {
                        "height": header_height,
                        "itemMargin": 4,
                        "justifyContent": "start",
                    },
                ),
                tuple(header_children),
            )
        )
    children.append(content)
    action = params.get("action")
    if isinstance(action, dict):
        binding = next(item for item in contract.action_bindings if item.action_id == action["id"])
        action_style = theme.action_style
        action_height = (
            registry.ux_tokens["pillActionHeight"]
            if ux_mixed
            else 30
        )
        options = {
            "width": "100%",
            "height": action_height,
            "padding": 2,
            "borderRadius": action_height / 2,
            "backgroundColor": (
                action_style.background_color if action_style is not None else "#24FFFFFF"
            ),
            "alignContent": "center",
            "onClick": [{"call": binding.call, "args": binding.args}],
        }
        label_values: tuple[Any, ...] = (binding.display_label, "compact-action")
        if action_style is not None:
            label_values = (
                *label_values,
                {
                    "fontColor": action_style.content_color,
                },
            )
        label = Nested2Node("Text", label_values, ())
        row = Nested2Node("Row", ("actions", {"justifyContent": "center"}), (label,))
        children.append(Nested2Node("Stack", ("overlay", options), (row,)))
    return Nested2Node("Column", ("card", root_options), tuple(children))


def _compile_ux_layout_shell(
    content: Nested2Node,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    theme = registry.require_theme(contract.theme_profile_id)
    root_options = _normalize_theme_styles(theme.root_style)
    root_options.setdefault("padding", registry.ux_tokens["safeInset"])
    root_options.setdefault("borderRadius", registry.ux_tokens["radius"])
    root_options.setdefault("itemMargin", registry.ux_tokens["sectionGap"])
    if "alignContent" in root_options:
        alignment = root_options.pop("alignContent")
        root_options["alignItems"] = _column_align_items(alignment)
    root_options.pop("width", None)
    root_options.pop("height", None)
    root_options["_id"] = "root"
    return Nested2Node("Column", ("card", root_options), (content,))


def _template_fusion_ball_palette(
    size: str,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    selected_template_ids: tuple[str, ...] = (),
) -> FusionBallPalette | None:
    """Resolve Theme-owned fusion balls for exactly one selected business."""
    if size != "2x2":
        return None
    theme = registry.require_theme(contract.theme_profile_id)
    fusion = theme.fusion_ball_style
    business_template_items = []
    for template_id in selected_template_ids:
        definition = registry.templates.get(template_id)
        if definition is None or definition.business_id is None:
            continue
        business_template_items.append(definition)
    business_templates = tuple(business_template_items)
    if fusion is None or len(business_templates) != 1:
        return None
    business_template = business_templates[0]
    if business_template.capability_id not in theme.supported_capability_ids:
        return None
    if business_template.business_id not in fusion.business_ids:
        return None
    layout_kind = provider_template_layout_kind(business_template.wire_id)
    if layout_kind not in {"Compact", "Full", "Hero"}:
        return None
    return FusionBallPalette(
        fusion.large_color,
        fusion.medium_color,
        fusion.small_color,
    )


def _apply_template_background(
    root: Nested2Node,
    size: str,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    selected_template_ids: tuple[str, ...] = (),
) -> Nested2Node:
    """Apply the gated Theme background to a root with one content skeleton."""
    palette = _template_fusion_ball_palette(
        size,
        contract,
        registry,
        selected_template_ids,
    )
    if palette is None:
        return root
    if len(root.children) != 1:
        raise ValueError("Fusion-ball template root must contain one content skeleton.")
    return apply_fusion_ball_background(root, size=size, palette=palette)


def _strip_direct_card_chrome_from_call(
    content: ParsedCall,
    params: dict[str, Any],
) -> ParsedCall:
    """Remove only model-authored duplicate Text; trusted Templates stay atomic."""
    chrome_literals = {
        value
        for key in ("title", "subtitle")
        if isinstance((value := params.get(key)), str) and value.strip()
    }
    action = params.get("action")
    if isinstance(action, dict):
        label = action.get("label")
        if isinstance(label, str) and label.strip():
            chrome_literals.add(label)
    if not chrome_literals:
        return content
    title = params.get("title")
    title_fragment = _semantic_text_fragment(title) if isinstance(title, str) else ""

    def visit(current: ParsedCall) -> ParsedCall | None:
        if current.kind == "template":
            return current
        is_text = current.name == "Text" and bool(current.values)
        has_text_value = is_text and isinstance(current.values[0], str)
        text_value = current.values[0] if has_text_value else ""
        text_fragment = _semantic_text_fragment(text_value)
        duplicates_chrome = has_text_value and text_value in chrome_literals
        duplicates_title = len(text_fragment) >= 2 and bool(title_fragment)
        duplicates_title = duplicates_title and text_fragment in title_fragment
        if duplicates_chrome or duplicates_title:
            return None
        children = tuple(child for item in current.children if (child := visit(item)) is not None)
        if current.children and not children and current.name in _CONTAINERS:
            return None
        return ParsedCall(current.kind, current.name, current.values, children, current.span)

    return visit(content) or ParsedCall(
        "component",
        "Column",
        ("section",),
        (),
        content.span,
    )


def _drop_redundant_card_chrome(
    params: dict[str, Any],
    content: Nested2Node,
) -> dict[str, Any]:
    """Let atomic local Templates own matching title facts and reclaim header space."""
    visible = tuple(
        node.values[0]
        for node in _walk_nodes(content)
        if node.component_type == "Text"
        and node.values
        and isinstance(node.values[0], str)
        and node.values[0].strip()
    )
    visible_blob = "".join(_semantic_text_fragment(item) for item in visible)
    normalized = dict(params)
    for key in ("title", "subtitle"):
        value = params.get(key)
        if not isinstance(value, str):
            continue
        fragments = tuple(
            _semantic_text_fragment(item)
            for item in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+|[%°]", value.casefold())
            if _semantic_text_fragment(item)
        )
        trusted_literal_is_visible = _is_trusted_template_literal(value, visible)
        whole_fragment_is_visible = _semantic_text_fragment(value) in visible_blob
        all_fragments_are_visible = bool(fragments) and all(
            fragment in visible_blob for fragment in fragments
        )
        covered = (
            trusted_literal_is_visible
            or whole_fragment_is_visible
            or all_fragments_are_visible
        )
        if covered:
            normalized.pop(key, None)
    return normalized


def _semantic_text_fragment(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9\u4e00-\u9fff°%]+", value.casefold()))


def _deduplicate_visible_text(node: Nested2Node, task_spec: TaskSpec) -> Nested2Node:
    """Remove model-created duplicate Text while preserving equal independent facts."""
    allowed = Counter(_string_fact_values(task_spec.dataModelSchema))
    seen: Counter[str] = Counter()

    def visit(
        current: Nested2Node,
        *,
        inside_advanced_component: bool = False,
        inside_action: bool = False,
    ) -> Nested2Node | None:
        is_advanced_component = inside_advanced_component or any(
            isinstance(value, dict) and isinstance(value.get("_advancedComponent"), str)
            for value in current.values
        )
        is_action = inside_action or any(
            isinstance(value, dict) and isinstance(value.get("_boundTemplateAction"), str)
            for value in current.values
        )
        is_text = current.component_type == "Text" and bool(current.values)
        has_text_value = is_text and isinstance(current.values[0], str)
        has_visible_text = has_text_value and bool(current.values[0].strip())
        if not is_advanced_component and not is_action and has_visible_text:
            literal = current.values[0]
            limit = max(1, allowed[literal])
            seen[literal] += 1
            if seen[literal] > limit:
                return None
        children = tuple(
            child
            for item in current.children
            if (
                child := visit(
                    item,
                    inside_advanced_component=is_advanced_component,
                    inside_action=is_action,
                )
            )
            is not None
        )
        if current.children and not children and current.component_type in _CONTAINERS:
            return None
        return Nested2Node(current.component_type, current.values, children)

    return visit(node) or Nested2Node("Column", ("compact",), ())


def _string_fact_values(value: Any) -> list[str]:
    if isinstance(value, dict) and "sampleValue" in value:
        sample = value["sampleValue"]
        return [sample] if isinstance(sample, str) and sample.strip() else []
    if isinstance(value, dict):
        return [item for child in value.values() for item in _string_fact_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _string_fact_values(child)]
    return []


def _append_missing_required_literals(
    content: Nested2Node,
    contract: HybridBodyContract,
    *,
    already_visible: tuple[str, ...] = (),
) -> Nested2Node:
    """Deterministically preserve mustKeep facts without a third model call."""
    visible_values = tuple(
        node.values[0]
        for node in _walk_nodes(content)
        if node.component_type == "Text" and node.values and isinstance(node.values[0], str)
    )
    visible = "\n".join(visible_values)
    visible_blob = "".join(_semantic_text_fragment(item) for item in visible_values)
    chrome_fragments = tuple(
        _semantic_text_fragment(item) for item in already_visible if _semantic_text_fragment(item)
    )
    missing = [
        literal
        for literal in contract.required_literals
        if literal not in visible
        and _semantic_text_fragment(literal) not in visible_blob
        and literal not in already_visible
        and not (
            len(_semantic_text_fragment(literal)) >= 2
            and any(
                _semantic_text_fragment(literal) in chrome_fragment
                for chrome_fragment in chrome_fragments
            )
        )
    ]
    if not missing:
        return content
    additions = tuple(Nested2Node("Text", (literal, "body"), ()) for literal in missing)
    if 2 <= len(additions) <= 4 and all(
        len(_semantic_text_fragment(literal)) <= 8 for literal in missing
    ):
        additions = (
            Nested2Node(
                "Row",
                (
                    "between",
                    {
                        "width": "100%",
                        "height": 18,
                        "itemMargin": 4,
                        "justifyContent": "spaceBetween",
                        "alignItems": "center",
                    },
                ),
                additions,
            ),
        )
    if content.component_type == "Column":
        return Nested2Node(content.component_type, content.values, (*content.children, *additions))
    return Nested2Node("Column", ("section",), (content, *additions))


def _reclaim_optional_chrome_for_content(
    params: dict[str, Any],
    content: Nested2Node,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> dict[str, Any]:
    """Drop only a non-required subtitle when it is stealing body space."""
    content_height = _estimate_height(content)
    normalized = dict(params)
    visible_blob = "".join(
        _semantic_text_fragment(node.values[0])
        for node in _walk_nodes(content)
        if node.component_type == "Text" and node.values and isinstance(node.values[0], str)
    )
    action = normalized.get("action")
    if isinstance(action, dict) and isinstance(action.get("label"), str):
        visible_blob += _semantic_text_fragment(action["label"])

    # The title remains owned by card@1. Only the secondary line is eligible
    # for deterministic reclamation; the model may omit an optional title at
    # generation time, but trusted compilation never silently removes one.
    for key in ("subtitle",):
        if content_height <= _body_budget(normalized, contract, registry):
            break
        value = normalized.get(key)
        if not isinstance(value, str):
            continue
        value_fragment = _semantic_text_fragment(value)
        owns_required_fact = any(
            (required_fragment := _semantic_text_fragment(required))
            and required_fragment in value_fragment
            and required_fragment not in visible_blob
            for required in contract.required_literals
        )
        if owns_required_fact:
            continue
        normalized.pop(key, None)
    return normalized


def _apply_theme_content_color(
    node: Nested2Node,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    preserve_original: bool = False,
    inside_action: bool = False,
) -> Nested2Node:
    """Fill only missing content colors while keeping Action and artwork ownership."""
    theme = registry.require_theme(contract.theme_profile_id)
    options = next((value for value in node.values if isinstance(value, dict)), {})
    preserve_here = preserve_original or options.get("_preserveOriginalColor") is True
    action_here = inside_action or isinstance(options.get("_boundTemplateAction"), str)
    children = tuple(
        _apply_theme_content_color(
            child,
            contract,
            registry,
            preserve_here,
            action_here,
        )
        for child in node.children
    )
    color_property = registry.content_color_properties.get(node.component_type)
    if preserve_here or action_here or color_property is None:
        return Nested2Node(node.component_type, node.values, children)
    values = list(node.values)
    options_index = next(
        (index for index, value in enumerate(values) if isinstance(value, dict)),
        None,
    )
    if options_index is None:
        values.append({color_property: theme.primary_color})
    else:
        styled = dict(values[options_index])
        styled.setdefault(color_property, theme.primary_color)
        values[options_index] = styled
    return Nested2Node(node.component_type, tuple(values), children)


def _theme_color_with_alpha(color: str, alpha: int) -> str:
    """Return one trusted ``#AARRGGBB`` Theme color with a different alpha."""
    return f"#{alpha:02X}{color[-6:]}"


def _lower_capsule_progress(node: Nested2Node) -> Nested2Node:
    children = tuple(_lower_capsule_progress(child) for child in node.children)
    if node.component_type != "Progress" or not node.values:
        return Nested2Node(node.component_type, node.values, children)
    options = next((value for value in node.values if isinstance(value, dict)), None)
    if options is None or options.get("type") != "capsule":
        return Nested2Node(node.component_type, node.values, children)
    total = options.get("total")
    value = options.get("value")
    if not isinstance(total, (int, float)) or total <= 0 or not isinstance(value, (int, float)):
        return Nested2Node(node.component_type, node.values, children)
    ratio = max(0.0, min(1.0, value / total))
    height = options.get("height", options.get("strokeWidth", 8))
    width = options.get("width", "100%")
    fill_width: int | float | str
    if isinstance(width, (int, float)):
        fill_width = round(width * ratio, 2)
    else:
        fill_width = f"{round(ratio * 100, 2)}%"
    fill = Nested2Node(
        "Text",
        (
            " ",
            {
                "width": fill_width,
                "height": height,
                "backgroundColor": options.get("color"),
                "borderRadius": height / 2 if isinstance(height, (int, float)) else 4,
                "maxLines": 1,
            },
        ),
        (),
    )
    return Nested2Node(
        "Row",
        (
            {
                "width": width,
                "height": height,
                "justifyContent": "start",
                "alignItems": "center",
            },
        ),
        (fill,),
    )


def _walk_nodes(node: Nested2Node) -> Iterator[Nested2Node]:
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _reject_direct_events(node: ParsedCall) -> None:
    for value in node.values:
        if isinstance(value, dict) and _contains_key(value, _DANGEROUS_EVENT_KEYS):
            raise TerselConversionError("Direct events are forbidden in Hybrid content.")
    for child in node.children:
        _reject_direct_events(child)


def _validate_raw_components(node: ParsedCall, contract: HybridBodyContract) -> None:
    if node.kind == "template":
        if node.name not in contract.allowed_template_ids:
            raise TerselConversionError(f"Template is not allowed: {node.name}")
        for child in node.children:
            _validate_raw_components(child, contract)
        return
    if contract.template_only_composition:
        raise TerselConversionError(
            "Second-layer composition accepts only approved Template calls."
        )
    if node.name not in contract.allowed_components:
        raise TerselConversionError(f"Raw component is not allowed: {node.name}")
    if node.name in _UX_ACTION_COMPONENTS:
        _validate_raw_ux_action(node, contract)
        return
    if node.name in _UX_DIRECT_BUSINESS_COMPONENTS:
        _validate_raw_ux_business_component(node, contract)
        return
    if node.name in _CONTAINERS and not node.children:
        raise TerselConversionError(
            f"Raw container must contain at least one child: {node.name}"
        )
    if node.name == "Button":
        raise TerselConversionError("Direct Buttons are forbidden in Hybrid content.")
    approved_strings = {
        *contract.trusted_literals,
        *contract.allowed_design_tokens,
        *contract.allowed_layout_tokens,
        *contract.allowed_asset_sources,
    }
    approved_numbers = {*contract.trusted_numbers, 0, 1, 100}
    # Layout configuration is validated against the closed, versioned Registry
    # schema before this generic literal pass. Its enum strings and small
    # integer choices are control-plane values, not business literals.
    values = () if node.name in UX_LAYOUT_COMPONENT_IDS else node.values
    for value in values:
        for item in _primitive_values(value):
            if isinstance(item, str) and item not in approved_strings:
                raise TerselConversionError(f"Raw literal is not trusted: {item}")
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                if item not in approved_numbers:
                    raise TerselConversionError(f"Raw number is not trusted: {item}")
    for child in node.children:
        _validate_raw_components(child, contract)


def _validate_raw_ux_business_component(
    node: ParsedCall,
    contract: HybridBodyContract,
) -> None:
    if node.name not in contract.allowed_business_component_ids:
        raise TerselConversionError(f"UX Business Component is not approved: {node.name}")
    if node.children or len(node.values) != 1 or not isinstance(node.values[0], dict):
        raise TerselConversionError(f"{node.name} must be one leaf configuration call.")
    parameters = node.values[0]
    required_fields = {"variant", "role"}
    optional_fields: set[str] = set()
    if node.name == "WeatherOverview":
        required_fields.add("conditionIcon")
    elif node.name == "ActivityOverview":
        optional_fields = {"stepsIcon", "caloriesIcon", "distanceIcon"}
    elif node.name == "WorkoutOverview":
        optional_fields = {"sourceIcon", "caloriesIcon"}
    elif node.name == "HeartRateOverview":
        optional_fields = {"sourceIcon"}
    elif node.name == "SleepOverview":
        optional_fields = {"sourceIcon"}
    elif node.name == "BatteryOverview":
        optional_fields = {"batteryIcon", "showTitle"}
    elif node.name == "BluetoothDeviceOverview":
        optional_fields = {"sourceIcon", "leftEarIcon", "rightEarIcon"}
    elif node.name == "ScheduleOverview":
        optional_fields = {"sourceIcon", "timeIcon", "locationIcon"}
    elif node.name == "ResourceUsageOverview":
        optional_fields = {"icon", "showTitle"}
    elif node.name == "AppUsageOverview":
        optional_fields = {"appIcon"}
    if not required_fields.issubset(parameters) or set(parameters) - (
        required_fields | optional_fields
    ):
        raise TerselConversionError(f"{node.name} configuration fields are invalid.")
    variants = {
        "ActivityOverview": {"steps", "dailySummary"},
        "BatteryOverview": {"normal", "charging", "low"},
        "BluetoothDeviceOverview": {"earbuds"},
        "DateOverview": {"compactDate", "dateHero"},
        "HeartRateOverview": {"average"},
        "SleepOverview": {"duration", "insufficient", "schedule"},
        "ScheduleOverview": {
            "nextEvent",
            "meetingCompact",
            "meetingExpanded",
            "focusContext",
        },
        "ResourceUsageOverview": {"memory"},
        "AppUsageOverview": {"singleApp"},
        "WeatherOverview": {"current", "commute"},
        "WorkoutOverview": {"latest"},
    }[node.name]
    roles = {
        "ActivityOverview": {"hero", "support"},
        "BatteryOverview": {"hero", "support", "peer"},
        "BluetoothDeviceOverview": {"hero", "support", "peer"},
        "DateOverview": {"hero", "support"},
        "HeartRateOverview": {"hero", "support"},
        "SleepOverview": {"hero", "support"},
        "ScheduleOverview": {"hero", "support"},
        "ResourceUsageOverview": {"hero", "peer"},
        "AppUsageOverview": {"hero"},
        "WeatherOverview": {"hero", "support", "peer"},
        "WorkoutOverview": {"hero"},
    }[node.name]
    if parameters["variant"] not in variants:
        raise TerselConversionError(f"{node.name} variant is not supported.")
    if parameters["role"] not in roles:
        raise TerselConversionError(f"{node.name} role is not supported.")
    show_title = parameters.get("showTitle")
    if show_title is not None and not isinstance(show_title, bool):
        raise TerselConversionError(f"{node.name} showTitle must be a Boolean.")
    if node.name == "WeatherOverview":
        condition_icon = parameters["conditionIcon"]
        if (
            not isinstance(condition_icon, str)
            or condition_icon not in contract.allowed_asset_sources
        ):
            raise TerselConversionError(
                "WeatherOverview conditionIcon is not an approved second-step asset input."
            )
    if node.name == "ActivityOverview":
        _validate_optional_semantic_assets(
            node.name,
            parameters,
            {
                "stepsIcon": {"activity", "steps", "sport"},
                "caloriesIcon": {"calories", "energy"},
                "distanceIcon": {"distance", "route"},
            },
            contract,
        )
    if node.name == "WorkoutOverview":
        _validate_optional_semantic_assets(
            node.name,
            parameters,
            {
                "sourceIcon": {"workout", "sport", "run"},
                "caloriesIcon": {"calories", "energy"},
            },
            contract,
        )
    if node.name == "HeartRateOverview":
        _validate_optional_semantic_assets(
            node.name,
            parameters,
            {"sourceIcon": {"heart", "heart-rate", "pulse"}},
            contract,
        )
    if node.name == "SleepOverview":
        _validate_optional_semantic_assets(
            node.name,
            parameters,
            {"sourceIcon": {"sleep", "moon", "alarm"}},
            contract,
        )
    if node.name == "ScheduleOverview":
        for field in optional_fields:
            source = parameters.get(field)
            if source is not None and (
                not isinstance(source, str) or source not in contract.allowed_asset_sources
            ):
                raise TerselConversionError(
                    f"ScheduleOverview {field} is not an approved TaskSpec asset."
                )
    if node.name == "BatteryOverview":
        source = parameters.get("batteryIcon")
        if source is not None and (
            not isinstance(source, str) or source not in contract.allowed_asset_sources
        ):
            raise TerselConversionError(
                "BatteryOverview batteryIcon is not an approved TaskSpec asset."
            )
    if node.name == "BluetoothDeviceOverview":
        _validate_optional_semantic_assets(
            node.name,
            parameters,
            {
                "sourceIcon": {"audio", "earphone", "product"},
                "leftEarIcon": {"audio", "earphone", "product"},
                "rightEarIcon": {"audio", "earphone", "product"},
            },
            contract,
        )
    if node.name == "ResourceUsageOverview":
        source = parameters.get("icon")
        if source is not None:
            if not isinstance(source, str) or source not in contract.allowed_asset_sources:
                raise TerselConversionError(
                    "ResourceUsageOverview icon is not an approved TaskSpec asset."
                )
            tags = set(contract.asset_semantic_tags_by_source.get(source, ()))
            if not tags & {"memory", "resource"}:
                raise TerselConversionError(
                    "ResourceUsageOverview icon does not match memory/resource semantics."
                )
    if node.name == "AppUsageOverview":
        source = parameters.get("appIcon")
        if source is not None:
            if not isinstance(source, str) or source not in contract.allowed_asset_sources:
                raise TerselConversionError(
                    "AppUsageOverview appIcon is not an approved TaskSpec asset."
                )
            tags = set(contract.asset_semantic_tags_by_source.get(source, ()))
            if not tags & {"app", "application"}:
                raise TerselConversionError(
                    "AppUsageOverview appIcon does not match app semantics."
                )


def _validate_optional_semantic_assets(
    component_id: str,
    parameters: dict[str, Any],
    fields: dict[str, set[str]],
    contract: HybridBodyContract,
) -> None:
    for field, expected_tags in fields.items():
        source = parameters.get(field)
        if source is None:
            continue
        if not isinstance(source, str) or source not in contract.allowed_asset_sources:
            raise TerselConversionError(
                f"{component_id} {field} is not an approved TaskSpec asset."
            )
        actual_tags = set(contract.asset_semantic_tags_by_source.get(source, ()))
        if not actual_tags & expected_tags:
            raise TerselConversionError(
                f"{component_id} {field} does not match its business semantics."
            )


def _validate_raw_ux_action(node: ParsedCall, contract: HybridBodyContract) -> None:
    if node.name not in {"PillAction", "IconAction"}:
        raise TerselConversionError("UX template route Action type is not supported.")
    if node.children or len(node.values) != 1 or not isinstance(node.values[0], dict):
        raise TerselConversionError(f"{node.name} must be one leaf object call.")
    params = node.values[0]
    expected_fields = {"actionId"} if node.name == "PillAction" else {"actionId", "icon"}
    if set(params) != expected_fields:
        raise TerselConversionError(f"{node.name} contains unknown fields.")
    action_id = params.get("actionId")
    approved_ids = set(contract.content_action_ids)
    if not isinstance(action_id, str) or action_id not in approved_ids:
        raise TerselConversionError(f"{node.name} Action is not approved.")
    icon = params.get("icon")
    if node.name == "IconAction" and (
        not isinstance(icon, str) or icon not in contract.allowed_asset_sources
    ):
        raise TerselConversionError("IconAction icon is not approved.")


def _ux_business_component_name(
    node: ParsedCall,
    registry: CardPlanRegistry,
    contract: HybridBodyContract,
) -> str | None:
    if node.kind == "component" and node.name in registry.ux_business_components:
        return node.name
    if node.kind != "template":
        return None
    required_template_ids = {
        template_id for group in contract.required_template_groups for template_id in group
    }
    if node.name not in required_template_ids:
        return None
    owners = tuple(
        component.name
        for component in registry.ux_business_components.values()
        if node.name in component.local_template_ids
    )
    return owners[0] if len(owners) == 1 else None


def _contract_ux_business_component_names(
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> set[str]:
    names = set(contract.allowed_business_component_ids)
    required_template_ids = {
        template_id for group in contract.required_template_groups for template_id in group
    }
    names.update(
        component.name
        for component in registry.ux_business_components.values()
        if required_template_ids & set(component.local_template_ids)
    )
    return names


def _contains_ux_business_component(
    node: ParsedCall,
    component_name: str,
    registry: CardPlanRegistry,
    contract: HybridBodyContract,
) -> bool:
    return any(
        _ux_business_component_name(call, registry, contract) == component_name
        for call in _walk_calls(node)
    )


_PROVIDER_TEMPLATE_DIRECT_VARIANTS = {
    "ScheduleOverview@1": {
        "nextEventHero": "nextEvent",
        "reminderHero": "nextEvent",
        "timezoneFull": "nextEvent",
        "dateFull": "nextEvent",
        "datedMeetingHero": "nextEvent",
        "nextEventLocationFull": "nextEvent",
        "meetingWideFull": "meetingExpanded",
        "meetingSourceWideFull": "meetingExpanded",
    },
    "BatteryOverview@1": {
        "normalFull": "normal",
        "normalHero": "normal",
        "chargingFull": "charging",
        "lowFull": "low",
        "normalWideFull": "normal",
        "chargingWideFull": "charging",
        "lowWideFull": "low",
        "normalCompact": "normal",
        "chargingCompact": "charging",
        "lowCompact": "low",
        "normalPhoneCompact": "normal",
        "chargingPhoneCompact": "charging",
        "lowPhoneCompact": "low",
        "normalWeatherCompact": "normal",
        "chargingWeatherCompact": "charging",
        "lowWeatherCompact": "low",
        "chargingDiagnosticsHero": "chargingDiagnostics",
        "chargingProgressHero": "chargingProgress",
        "healthLevelHero": "healthLevel",
        "percentRingHero": "percentRing",
    },
    "ResourceUsageOverview@1": {"full": "memory", "compact": "memory"},
    "AppUsageOverview@1": {
        "full": "singleApp",
        "hero": "singleApp",
        "wideFull": "singleApp",
        "wideHero": "singleApp",
    },
    "ActivityOverview@1": {
        "stepsFull": "steps",
        "stepsCompact": "steps",
        "dailySummaryFull": "dailySummary",
        "dailySummaryWideFull": "dailySummary",
    },
    "WorkoutOverview@1": {"full": "latest"},
    "SleepOverview@1": {
        "durationFull": "duration",
        "durationDetailedFull": "duration",
        "durationCompact": "duration",
        "durationDetailedCompact": "duration",
        "durationScoreFull": "duration",
        "durationScoreDetailedFull": "duration",
        "durationScoreCompact": "duration",
        "insufficientFull": "insufficient",
        "insufficientDetailedFull": "insufficient",
        "scheduleWideFull": "schedule",
        "scheduleDetailedWideFull": "schedule",
        "scheduleStatusWideFull": "schedule",
        "scheduleDetailedStatusWideFull": "schedule",
    },
    "BluetoothDeviceOverview@1": {
        "hero": "earbuds",
        "caseStatusCompact": "earbuds",
        "earbudsPhoneWideFull": "earbuds",
        "earbudsDynamicWideFull": "earbuds",
        "earbudsSupport": "earbuds",
        "earbudPairFull": "earbuds",
        "completeWideFull": "earbuds",
        "earbudPairCompact": "earbuds",
        "completePhoneWideFull": "earbuds",
    },
}


def _provider_template_business_validation_proxy(
    node: ParsedCall,
    *,
    index: int,
    count: int,
    layout_id: str,
    size: Literal["2x2", "2x4"],
    business_names: set[str],
    registry: CardPlanRegistry,
    contract: HybridBodyContract,
) -> ParsedCall:
    if node.kind != "template":
        return node
    identity = provider_template_family_identity(node.name)
    base_wire_id = identity[0] if identity is not None else node.name
    variant = identity[1] if identity is not None else (node.values[0] if node.values else None)
    if base_wire_id not in _PROVIDER_TEMPLATE_DIRECT_VARIANTS:
        return node
    component_name = _ux_business_component_name(node, registry, contract)
    if component_name is None or not isinstance(variant, str):
        return node
    direct_variant = _PROVIDER_TEMPLATE_DIRECT_VARIANTS[base_wire_id].get(variant)
    if direct_variant is None:
        return node
    role = _provider_template_validation_role(
        component_name,
        index=index,
        count=count,
        layout_id=layout_id,
        size=size,
        business_names=business_names,
    )
    template_variant = registry.require_variant(
        node.name,
        "default" if identity is not None else variant,
    )
    if template_variant.supported_roles and role not in template_variant.supported_roles:
        raise TerselConversionError(
            f"Provider Template does not support the placement role: {node.name}/{variant}/{role}"
        )
    parameters: dict[str, Any] = {"variant": direct_variant, "role": role}
    peer_resource_pair = size == "2x2" and business_names == {
        "BatteryOverview",
        "ResourceUsageOverview",
    }
    if component_name in {"BatteryOverview", "ResourceUsageOverview"}:
        parameters["showTitle"] = not peer_resource_pair
    return ParsedCall(
        "component",
        component_name,
        (parameters,),
        node.children,
        node.span,
    )


def _provider_template_validation_role(
    component_name: str,
    *,
    index: int,
    count: int,
    layout_id: str,
    size: Literal["2x2", "2x4"],
    business_names: set[str],
) -> str:
    if component_name == "DateOverview":
        return "support" if count > 1 and size == "2x2" else "hero"
    if component_name == "ScheduleOverview" and "DateOverview" in business_names:
        return "support"
    phone_earphone = business_names == {
        "BatteryOverview",
        "BluetoothDeviceOverview",
    }
    if phone_earphone:
        return "hero" if component_name == "BatteryOverview" else "support"
    if layout_id in {"PeerPairLayout", "EqualItemsLayout"}:
        return "peer"
    return "hero" if count == 1 or index == 0 else "support"


def _validate_ux_layout_root(
    node: ParsedCall,
    contract: HybridBodyContract,
    *,
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
    embedded_actions: bool = False,
) -> None:
    allowed = set(contract.allowed_layout_component_ids)
    if not allowed:
        return
    layout_id = _parsed_layout_template_id(node, registry)
    if layout_id not in allowed:
        raise TerselConversionError(
            "UX Mixed content root must be one approved Layout Template."
        )
    layout = registry.require_ux_layout_component(layout_id)
    if size not in layout.supported_card_sizes:
        raise TerselConversionError("UX Layout does not support the target card size.")
    if len(node.values) > 1 or (node.values and not isinstance(node.values[0], dict)):
        raise TerselConversionError(
            "UX Layout configuration must be one optional object argument."
        )
    parameters = node.values[0] if node.values else {}
    parameter_errors = sorted(
        Draft202012Validator(layout.parameters_schema).iter_errors(parameters),
        key=str,
    )
    if parameter_errors:
        raise TerselConversionError(
            f"UX Layout parameters are invalid for {layout_id}: {parameter_errors[0].message}"
        )
    maximum = layout.max_children_by_size[size]
    action_children = tuple(
        child
        for child in node.children
        if _parsed_ux_action_component(child) is not None
    )
    content_children = tuple(child for child in node.children if child not in action_children)
    _validate_provider_template_layout_action_requirements(
        layout_id,
        content_children,
        action_children,
        size,
    )
    counted_children = content_children if embedded_actions else node.children
    minimum = layout.minimum_children(size)
    if not minimum <= len(counted_children) <= maximum:
        raise TerselConversionError(
            f"UX Layout child count is invalid: {layout_id}/{len(counted_children)}"
        )
    if embedded_actions:
        _validate_ux_layout_action_slot(node, layout, size, action_children)
    _validate_ux_business_component_placement(
        layout_id,
        content_children,
        size=size,
        contract=contract,
        registry=registry,
    )

    def reject_nested_layout(current: ParsedCall) -> None:
        for child in current.children:
            if child.kind == "component" and child.name in UX_LAYOUT_COMPONENT_IDS:
                raise TerselConversionError("UX Layout Components cannot be nested.")
            reject_nested_layout(child)

    reject_nested_layout(node)


def _validate_provider_template_layout_action_requirements(
    layout_id: str,
    content_children: tuple[ParsedCall, ...],
    action_children: tuple[ParsedCall, ...],
    size: Literal["2x2", "2x4"],
) -> None:
    layout_kind_items: list[str] = []
    for child in content_children:
        for call in _walk_calls(child):
            if call.kind != "template":
                continue
            layout_kind = provider_template_layout_kind(call.name)
            if layout_kind is not None:
                layout_kind_items.append(layout_kind)
    layout_kinds = tuple(layout_kind_items)
    if not layout_kinds:
        return
    layout_is_wide = layout_id.startswith("Wide")
    if layout_is_wide != (size == "2x4"):
        raise TerselConversionError(
            "UX Layout Wide marker does not match the target card size."
        )
    wide = any(kind.startswith("Wide") for kind in layout_kinds)
    if wide != (size == "2x4"):
        raise TerselConversionError(
            "Provider Template layout suffix mismatches card size."
        )
    action_names = tuple(
        action_name
        for child in action_children
        if (action_name := _parsed_ux_action_component(child)) is not None
    )
    if len(layout_kinds) == 2 and set(layout_kinds) == {"Support"} and not action_names:
        if layout_id != "TwoSupportLayout":
            raise TerselConversionError(
                "Two Support Provider Templates require TwoSupportLayout."
            )
        return
    if len(layout_kinds) != 1:
        raise TerselConversionError("Provider Template layout combination is invalid.")
    layout_kind = layout_kinds[0]
    if layout_kind == "Full":
        valid_full_combinations = {
            ("SingleFocusLayout", ()),
            ("FullIconActionLayout", ("IconAction",)),
        }
        if (layout_id, action_names) not in valid_full_combinations:
            raise TerselConversionError(
                f"Full Provider Template Action combination is invalid: {action_names}."
            )
        return
    expected_actions = {
        "Compact": ("PillAction", "PillAction"),
        "Hero": ("PillAction",),
        "WideHero": ("PillAction",),
        "WideFull": (),
    }[layout_kind]
    if action_names != expected_actions:
        raise TerselConversionError(
            f"{layout_kind} Provider Template Action combination is invalid: {action_names}."
        )
    expected_layout_id = {
        "Compact": "CompactTwoActionLayout",
        "Hero": "HeroActionLayout",
        "WideHero": "WideSingleFocusLayout",
        "WideFull": "WideSingleFocusLayout",
    }[layout_kind]
    if layout_id != expected_layout_id:
        raise TerselConversionError(
            f"{layout_kind} Provider Template requires {expected_layout_id}."
        )


def _parsed_layout_template_id(
    node: ParsedCall,
    registry: CardPlanRegistry,
) -> str:
    if node.kind == "component" and node.name in UX_LAYOUT_COMPONENT_IDS:
        return node.name
    if node.kind != "template" or not node.name.endswith("@1"):
        return ""
    layout_id = node.name.removesuffix("@1")
    if layout_id not in UX_LAYOUT_COMPONENT_IDS:
        return ""
    definition = registry.require_template(node.name)
    if not definition.accepts_children or definition.provider_id != "com.huawei.layout.cli":
        return ""
    return layout_id


def _validate_ux_business_component_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> None:
    contains_provider_template = any(
        call.kind == "template" and provider_template_layout_kind(call.name) is not None
        for child in content
        for call in _walk_calls(child)
    )
    if contains_provider_template:
        return
    business_names = _contract_ux_business_component_names(contract, registry)
    validation_content = tuple(
        _provider_template_business_validation_proxy(
            child,
            index=index,
            count=len(content),
            layout_id=layout_id,
            size=size,
            business_names=business_names,
            registry=registry,
            contract=contract,
        )
        for index, child in enumerate(content)
    )
    validation_contract = contract.model_copy(
        update={"allowed_business_component_ids": tuple(sorted(business_names))}
    )
    _validate_activity_overview_placement(
        layout_id,
        validation_content,
        size=size,
        contract=validation_contract,
        registry=registry,
    )
    _validate_workout_overview_placement(layout_id, validation_content)
    _validate_heart_rate_overview_placement(
        layout_id,
        validation_content,
        contract=validation_contract,
        registry=registry,
    )
    _validate_sleep_overview_placement(
        layout_id,
        validation_content,
        size=size,
        contract=validation_contract,
    )
    _validate_weather_overview_placement(
        layout_id,
        validation_content,
        size=size,
        registry=registry,
        contract=validation_contract,
    )
    _validate_date_overview_placement(layout_id, validation_content, size=size)
    _validate_schedule_overview_placement(layout_id, validation_content, size=size)
    _validate_battery_overview_placement(
        layout_id,
        validation_content,
        size=size,
        registry=registry,
        contract=validation_contract,
    )
    _validate_bluetooth_device_overview_placement(
        layout_id,
        validation_content,
        size=size,
    )
    _validate_resource_usage_overview_placement(
        layout_id,
        validation_content,
        size=size,
    )
    _validate_app_usage_overview_placement(
        layout_id,
        validation_content,
        size=size,
    )


def _validate_activity_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> None:
    indexes = tuple(
        index for index, child in enumerate(content) if child.name == "ActivityOverview"
    )
    if not indexes:
        if any(call.name == "ActivityOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("ActivityOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("ActivityOverview must appear exactly once.")
    index = indexes[0]
    role = content[index].values[0].get("role")
    business_ids = _contract_ux_business_component_names(contract, registry)
    if business_ids == {"ActivityOverview"} and len(content) == 1:
        if layout_id != "SingleFocusLayout" or index != 0 or role != "hero":
            raise TerselConversionError(
                "Single ActivityOverview requires one leading hero in SingleFocusLayout."
            )
        return
    if business_ids == {"ActivityOverview"} and len(content) == 2 and content[1].kind == "template":
        if layout_id != "HeroSupportLayout" or index != 0 or role != "hero":
            raise TerselConversionError(
                "ActivityOverview must lead its approved Sleep support composition."
            )
        return
    if business_ids == {"ActivityOverview", "WorkoutOverview"}:
        if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
            raise TerselConversionError(
                "Workout plus ActivityOverview requires a HeroSupport layout."
            )
        if index != 1 or role != "support":
            raise TerselConversionError(
                "ActivityOverview must be the support after WorkoutOverview."
            )
        return
    if business_ids == {"ActivityOverview", "SleepOverview"}:
        allowed_layouts = {"HeroSupportLayout"}
        if size == "2x4":
            allowed_layouts.add("SequentialSummaryLayout")
        expected_role = "hero" if index == 0 else "support"
        if layout_id not in allowed_layouts or role != expected_role:
            raise TerselConversionError(
                "ActivityOverview role must match its Sleep composition position."
            )
        if size == "2x2" and index != 0:
            raise TerselConversionError("ActivityOverview must lead SleepOverview on 2x2.")
        return
    if business_ids == {"ActivityOverview", "HeartRateOverview"}:
        if layout_id != "HeroSupportLayout" or index != 0 or role != "hero":
            raise TerselConversionError(
                "ActivityOverview must lead its approved health support composition."
            )
        return
    raise TerselConversionError(
        "ActivityOverview multi-business composition is not approved."
    )


def _validate_workout_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
) -> None:
    indexes = tuple(index for index, child in enumerate(content) if child.name == "WorkoutOverview")
    if not indexes:
        if any(call.name == "WorkoutOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("WorkoutOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("WorkoutOverview must appear exactly once.")
    index = indexes[0]
    role = content[index].values[0].get("role")
    if index != 0 or role != "hero":
        raise TerselConversionError("WorkoutOverview must be the leading hero business.")
    if len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"}:
            raise TerselConversionError(
                "Single WorkoutOverview requires SingleFocus or HeroAction layout."
            )
        return
    if len(content) != 2 or content[1].name != "ActivityOverview":
        raise TerselConversionError(
            "WorkoutOverview only supports ActivityOverview as its companion."
        )
    if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
        raise TerselConversionError(
            "Workout plus ActivityOverview requires a HeroSupport layout."
        )


def _validate_heart_rate_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> None:
    indexes = tuple(
        index
        for index, child in enumerate(content)
        if _ux_business_component_name(child, registry, contract) == "HeartRateOverview"
    )
    if not indexes:
        if any(
            _contains_ux_business_component(child, "HeartRateOverview", registry, contract)
            for child in content
        ):
            raise TerselConversionError("HeartRateOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("HeartRateOverview must appear exactly once.")
    index = indexes[0]
    heart_rate = content[index]
    if heart_rate.kind == "component" and isinstance(heart_rate.values[0], dict):
        role = heart_rate.values[0].get("role")
    elif heart_rate.kind == "template":
        layout_kind = provider_template_layout_kind(heart_rate.name)
        role = "support" if layout_kind == "Compact" else "hero"
    else:
        raise TerselConversionError("HeartRateOverview must be a direct layout child.")
    business_ids = _contract_ux_business_component_names(contract, registry)
    if business_ids == {"HeartRateOverview"}:
        if layout_id != "SingleFocusLayout" or index != 0 or role != "hero":
            raise TerselConversionError(
                "Single HeartRateOverview requires one leading hero."
            )
        return
    if business_ids != {"ActivityOverview", "HeartRateOverview"}:
        raise TerselConversionError(
            "HeartRateOverview is only an approved support for ActivityOverview."
        )
    if layout_id != "HeroSupportLayout" or index != 1 or role != "support":
        raise TerselConversionError(
            "HeartRateOverview must be the fixed support after ActivityOverview."
        )


def _validate_sleep_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
) -> None:
    indexes = tuple(index for index, child in enumerate(content) if child.name == "SleepOverview")
    if not indexes:
        if any(call.name == "SleepOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("SleepOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("SleepOverview must appear exactly once.")
    index = indexes[0]
    parameters = content[index].values[0]
    role = parameters.get("role")
    variant = parameters.get("variant")
    business_ids = set(contract.allowed_business_component_ids)
    if business_ids == {"SleepOverview"} and len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"}:
            raise TerselConversionError(
                "Single SleepOverview requires SingleFocus or HeroAction layout."
            )
        if index != 0 or role != "hero":
            raise TerselConversionError(
                "Single SleepOverview must be the leading hero business."
            )
        if size == "2x2" and variant == "schedule":
            raise TerselConversionError("SleepOverview schedule is only available on 2x4.")
        return
    allowed_layouts = {"HeroSupportLayout"}
    if size == "2x4":
        allowed_layouts.add("SequentialSummaryLayout")
    expected_role = "hero" if index == 0 else "support"
    if layout_id not in allowed_layouts or role != expected_role:
        raise TerselConversionError(
            "SleepOverview role must match its Activity composition position."
        )
    if size == "2x2" and index != 1:
        raise TerselConversionError(
            "SleepOverview must be the compact support after ActivityOverview on 2x2."
        )


def _validate_weather_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
    contract: HybridBodyContract,
) -> None:
    weather_indexes = tuple(
        index
        for index, child in enumerate(content)
        if _ux_business_component_name(child, registry, contract) == "WeatherOverview"
    )
    if not weather_indexes:
        if any(
            _contains_ux_business_component(child, "WeatherOverview", registry, contract)
            for child in content
        ):
            raise TerselConversionError("WeatherOverview must be a direct layout child.")
        return
    if len(weather_indexes) != 1:
        raise TerselConversionError("WeatherOverview must appear exactly once.")
    weather_index = weather_indexes[0]
    weather = content[weather_index]
    if not weather.values:
        raise TerselConversionError("WeatherOverview must be a direct layout child.")
    if weather.kind == "component" and isinstance(weather.values[0], dict):
        role = weather.values[0].get("role")
        variant = None
    elif weather.kind == "template" and isinstance(weather.values[0], str):
        role = None
        variant = weather.values[0]
    elif weather.kind == "template":
        role = None
        variant = provider_template_layout_kind(weather.name)
    else:
        raise TerselConversionError("WeatherOverview must be a direct layout child.")
    if layout_id == "WeatherNowForecastLayout":
        raise TerselConversionError(
            "WeatherNowForecastLayout requires a forecast business component."
        )
    if size == "2x2":
        if weather_index != 0 or (role is not None and role != "hero"):
            raise TerselConversionError(
                "WeatherOverview must be the leading hero business on 2x2."
            )
        if len(content) > 1 and layout_id not in {
            "HeroSupportLayout",
            "HeroSupportActionLayout",
        }:
            raise TerselConversionError(
                "WeatherOverview multi-business 2x2 requires a HeroSupport layout."
            )
        uses_compact_action_matrix = layout_id == "ActionMatrixLayout"
        expected_variants = (
            {"Compact"}
            if len(content) > 1 or uses_compact_action_matrix
            else {"Full", "Hero"}
        )
        if variant is not None and variant not in expected_variants:
            raise TerselConversionError(
                "WeatherOverview Template variant does not match the 2x2 composition."
            )
        return
    expected_role = "hero"
    if layout_id in {"HeroSupportLayout", "HeroSupportActionLayout"} and weather_index == 1:
        expected_role = "support"
    elif layout_id == "EqualItemsLayout":
        expected_role = "peer"
    if role is not None and role != expected_role:
        raise TerselConversionError(
            f"WeatherOverview role does not match {layout_id}: expected {expected_role}."
        )
    expected_variants = (
        {"Full", "Hero", "WideFull", "WideHero"}
        if expected_role == "hero"
        else {"Compact"}
    )
    if variant is not None and variant not in expected_variants:
        raise TerselConversionError(
            f"WeatherOverview Template variant does not match {layout_id}."
        )


def _validate_date_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
) -> None:
    date_indexes = tuple(
        index for index, child in enumerate(content) if child.name == "DateOverview"
    )
    if not date_indexes:
        if any(call.name == "DateOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("DateOverview must be a direct layout child.")
        return
    if len(date_indexes) != 1:
        raise TerselConversionError("DateOverview must appear exactly once.")
    date_index = date_indexes[0]
    date = content[date_index]
    if date.kind != "component" or not date.values or not isinstance(date.values[0], dict):
        raise TerselConversionError("DateOverview must be a direct layout child.")
    variant = date.values[0].get("variant")
    role = date.values[0].get("role")
    if len(content) == 1:
        if layout_id != "SingleFocusLayout" or (variant, role) != ("dateHero", "hero"):
            raise TerselConversionError(
                "Single-business DateOverview requires SingleFocus dateHero+hero."
            )
        return
    if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
        raise TerselConversionError(
            "Multi-business DateOverview requires a HeroSupport layout."
        )
    if date_index != 0:
        raise TerselConversionError(
            "DateOverview must be the leading date context in multi-business layouts."
        )
    expected = ("compactDate", "support") if size == "2x2" else ("dateHero", "hero")
    if (variant, role) != expected:
        raise TerselConversionError(
            "DateOverview variant and role do not match the card size and composition."
        )


def _validate_schedule_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
) -> None:
    indexes = tuple(
        index for index, child in enumerate(content) if child.name == "ScheduleOverview"
    )
    if not indexes:
        if any(call.name == "ScheduleOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("ScheduleOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("ScheduleOverview must appear exactly once.")
    index = indexes[0]
    schedule = content[index]
    if not schedule.values or not isinstance(schedule.values[0], dict):
        raise TerselConversionError("ScheduleOverview must be a direct layout child.")
    variant = schedule.values[0].get("variant")
    role = schedule.values[0].get("role")
    if len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"} or role != "hero":
            raise TerselConversionError(
                "Single-business ScheduleOverview requires a hero SingleFocus/HeroAction layout."
            )
        if size == "2x4" and variant == "nextEvent":
            raise TerselConversionError(
                "Single-business 2x4 ScheduleOverview requires a meeting variant."
            )
        return
    if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
        raise TerselConversionError(
            "ScheduleOverview support requires a HeroSupport layout."
        )
    if "DateOverview" in {item.name for item in content}:
        if role != "support":
            raise TerselConversionError(
                "Date + Schedule requires ScheduleOverview to use the support role."
            )
        if index != 1:
            raise TerselConversionError(
                "DateOverview + ScheduleOverview requires date first and schedule second."
            )
        expected = (
            {"meetingCompact"}
            if size == "2x2"
            else {
                "meetingCompact",
                "meetingExpanded",
            }
        )
        if variant not in expected:
            raise TerselConversionError(
                "Date + Schedule variant does not match the target size."
            )
        return
    if role == "support":
        expected = (
            {"meetingCompact"}
            if size == "2x2"
            else {
                "meetingCompact",
                "meetingExpanded",
            }
        )
        if variant not in expected:
            raise TerselConversionError(
                "ScheduleOverview support variant does not match the target size."
            )
    elif role != "hero":
        raise TerselConversionError(
            "Multi-business ScheduleOverview requires a hero or support role."
        )


def _validate_battery_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
    contract: HybridBodyContract,
) -> None:
    indexes = tuple(index for index, child in enumerate(content) if child.name == "BatteryOverview")
    if not indexes:
        if any(call.name == "BatteryOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("BatteryOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("BatteryOverview must appear exactly once.")
    index = indexes[0]
    battery = content[index]
    if not battery.values or not isinstance(battery.values[0], dict):
        raise TerselConversionError("BatteryOverview must be a direct layout child.")
    role = battery.values[0].get("role")
    show_title = battery.values[0].get("showTitle", True)
    if not isinstance(show_title, bool):
        raise TerselConversionError("BatteryOverview showTitle must be a Boolean.")
    if len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"} or role != "hero":
            raise TerselConversionError(
                "Single-business BatteryOverview requires a hero SingleFocus/HeroAction layout."
            )
        if show_title is not True:
            raise TerselConversionError(
                "Single-business BatteryOverview must keep its internal title."
            )
        return
    names = {
        business_name
        for child in content
        if (business_name := _ux_business_component_name(child, registry, contract)) is not None
    }
    if "BluetoothDeviceOverview" in names:
        expected_layout = "PeerPairLayout" if size == "2x2" else "HeroSupportLayout"
        if layout_id != expected_layout or index != 0 or role != "hero":
            raise TerselConversionError(
                "Phone + earphone composition requires BatteryOverview hero first in the "
                f"{expected_layout}."
            )
        return
    if "ResourceUsageOverview" in names:
        if size == "2x2":
            if layout_id != "PeerPairLayout" or role != "peer" or show_title is not False:
                raise TerselConversionError(
                    "Battery + resource usage on 2x2 requires PeerPairLayout+peer+showTitle=false."
                )
            return
        if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
            raise TerselConversionError(
                "Battery + resource usage on 2x4 requires a HeroSupport layout."
            )
        if index != 1 or role != "support":
            raise TerselConversionError(
                "Battery must be the support business after resource usage on 2x4."
            )
        return
    if "WeatherOverview" in names:
        if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
            raise TerselConversionError("Weather + Battery requires a HeroSupport layout.")
        if index != 1 or role != "support":
            raise TerselConversionError(
                "Battery must be the support business after WeatherOverview."
            )
        return
    if len(content) > 2 and layout_id == "EqualItemsLayout" and role == "peer":
        return
    if layout_id != "PeerPairLayout" or role != "peer":
        raise TerselConversionError(
            "BatteryOverview multi-business phone/device composition requires PeerPairLayout+peer."
        )


def _validate_bluetooth_device_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
) -> None:
    indexes = tuple(
        index for index, child in enumerate(content) if child.name == "BluetoothDeviceOverview"
    )
    if not indexes:
        if any(
            call.name == "BluetoothDeviceOverview"
            for child in content
            for call in _walk_calls(child)
        ):
            raise TerselConversionError(
                "BluetoothDeviceOverview must be a direct layout child."
            )
        return
    if len(indexes) != 1:
        raise TerselConversionError("BluetoothDeviceOverview must appear exactly once.")
    index = indexes[0]
    overview = content[index]
    if not overview.values or not isinstance(overview.values[0], dict):
        raise TerselConversionError(
            "BluetoothDeviceOverview must be a direct layout child."
        )
    role = overview.values[0].get("role")
    if len(content) == 1:
        allowed_layouts = {"SingleFocusLayout", "HeroActionLayout", "ActionMatrixLayout"}
        if layout_id not in allowed_layouts or role != "hero":
            raise TerselConversionError(
                "Single-business BluetoothDeviceOverview requires a hero single/action layout."
            )
        return
    names = {child.name for child in content}
    if names != {"BatteryOverview", "BluetoothDeviceOverview"}:
        raise TerselConversionError(
            "BluetoothDeviceOverview multi-business currently supports phone battery only."
        )
    expected_layout = "PeerPairLayout" if size == "2x2" else "HeroSupportLayout"
    if layout_id != expected_layout or index != 1 or role != "support":
        raise TerselConversionError(
            "Phone + earphone composition requires BluetoothDeviceOverview support second in "
            f"the {expected_layout}."
        )


def _validate_resource_usage_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
) -> None:
    indexes = tuple(
        index for index, child in enumerate(content) if child.name == "ResourceUsageOverview"
    )
    if not indexes:
        if any(
            call.name == "ResourceUsageOverview" for child in content for call in _walk_calls(child)
        ):
            raise TerselConversionError(
                "ResourceUsageOverview must be a direct layout child."
            )
        return
    if len(indexes) != 1:
        raise TerselConversionError("ResourceUsageOverview must appear exactly once.")
    index = indexes[0]
    resource = content[index]
    if not resource.values or not isinstance(resource.values[0], dict):
        raise TerselConversionError("ResourceUsageOverview must be a direct layout child.")
    variant = resource.values[0].get("variant")
    role = resource.values[0].get("role")
    show_title = resource.values[0].get("showTitle", True)
    if not isinstance(show_title, bool):
        raise TerselConversionError("ResourceUsageOverview showTitle must be a Boolean.")
    if variant != "memory":
        raise TerselConversionError(
            "ResourceUsageOverview only enables the memory variant."
        )
    if len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"} or role != "hero":
            raise TerselConversionError(
                "Single-business ResourceUsageOverview requires a hero "
                "SingleFocus/HeroAction layout."
            )
        if show_title is not True:
            raise TerselConversionError(
                "Single-business ResourceUsageOverview must keep its internal title."
            )
        return
    if {child.name for child in content} != {
        "BatteryOverview",
        "ResourceUsageOverview",
    }:
        raise TerselConversionError(
            "Multi-business ResourceUsageOverview currently supports BatteryOverview only."
        )
    if size == "2x2":
        if layout_id != "PeerPairLayout" or role != "peer" or show_title is not False:
            raise TerselConversionError(
                "Multi-business 2x2 ResourceUsageOverview requires "
                "PeerPairLayout+peer+showTitle=false."
            )
        return
    if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
        raise TerselConversionError(
            "Multi-business 2x4 ResourceUsageOverview requires a HeroSupport layout."
        )
    if index != 0 or role != "hero":
        raise TerselConversionError(
            "Multi-business 2x4 ResourceUsageOverview must be the leading hero."
        )


def _validate_app_usage_overview_placement(
    layout_id: str,
    content: tuple[ParsedCall, ...],
    *,
    size: Literal["2x2", "2x4"],
) -> None:
    indexes = tuple(
        index for index, child in enumerate(content) if child.name == "AppUsageOverview"
    )
    if not indexes:
        if any(call.name == "AppUsageOverview" for child in content for call in _walk_calls(child)):
            raise TerselConversionError("AppUsageOverview must be a direct layout child.")
        return
    if len(indexes) != 1:
        raise TerselConversionError("AppUsageOverview must appear exactly once.")
    index = indexes[0]
    app_usage = content[index]
    if not app_usage.values or not isinstance(app_usage.values[0], dict):
        raise TerselConversionError("AppUsageOverview must be a direct layout child.")
    if app_usage.values[0].get("variant") != "singleApp":
        raise TerselConversionError("AppUsageOverview only enables the singleApp variant.")
    if len(content) == 1:
        if layout_id not in {"SingleFocusLayout", "HeroActionLayout"}:
            raise TerselConversionError(
                "Single-business AppUsageOverview requires SingleFocus/HeroAction layout."
            )
        return
    if {item.name for item in content} != {"AppUsageOverview", "SystemModeOverview"}:
        raise TerselConversionError(
            "Multi-business AppUsageOverview only supports trusted SystemModeOverview."
        )
    if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
        raise TerselConversionError(
            "AppUsageOverview + SystemModeOverview requires a HeroSupport layout."
        )
    if index != 0:
        raise TerselConversionError(
            "AppUsageOverview must be the leading hero in multi-business layouts."
        )


def _validate_ux_layout_action_slot(
    node: ParsedCall,
    layout: UxLayoutComponentCapability,
    size: Literal["2x2", "2x4"],
    action_children: tuple[ParsedCall, ...],
) -> None:
    minimum = layout.min_action_children_by_size[size]
    maximum = layout.max_action_children_by_size[size]
    if not minimum <= len(action_children) <= maximum:
        if minimum == maximum == 1 and not action_children:
            raise TerselConversionError("UX Layout requires one embedded Action.")
        if maximum == 0 and action_children:
            raise TerselConversionError("UX Layout does not accept an Action.")
        raise TerselConversionError(
            f"UX Layout Action count is invalid: {layout.name}/{len(action_children)}"
        )
    trailing_children = node.children[slice(-len(action_children), None)]
    if action_children and trailing_children != action_children:
        raise TerselConversionError("UX Layout Actions must be contiguous final children.")
    action_ids = tuple(
        child.values[0].get("actionId")
        for child in action_children
        if child.values and isinstance(child.values[0], dict)
    )
    if len(action_ids) != len(set(action_ids)):
        raise TerselConversionError("UX Layout cannot repeat the same Action.")
    matrix_has_invalid_action = layout.name == "ActionMatrixLayout" and any(
        _parsed_ux_action_component(child) not in {"ActionTile", "PillAction"}
        for child in action_children
    )
    if matrix_has_invalid_action:
        raise TerselConversionError(
            "ActionMatrixLayout requires ActionTile or PillAction controls."
        )


def _lower_ux_layouts(
    node: Nested2Node,
    *,
    size: Literal["2x2", "2x4"],
    has_action: bool,
    registry: CardPlanRegistry,
) -> Nested2Node:
    children = tuple(
        _lower_ux_layouts(
            child,
            size=size,
            has_action=has_action,
            registry=registry,
        )
        for child in node.children
    )
    if node.component_type not in UX_LAYOUT_COMPONENT_IDS:
        return Nested2Node(node.component_type, node.values, children)
    layout = registry.require_ux_layout_component(node.component_type)
    if size not in layout.supported_card_sizes:
        raise TerselConversionError("UX Layout does not support the target card size.")
    maximum = layout.max_children_by_size[size]
    # The raw tree already passed the strict layout contract. Trusted chrome
    # de-duplication may remove one child before lowering, but cannot add or
    # reorder business content.
    minimum = layout.minimum_children(size)
    if not minimum <= len(children) <= maximum:
        raise TerselConversionError(
            f"UX Layout child count is invalid: {node.component_type}/{len(children)}"
        )
    if layout.action_policy == "required" and not has_action:
        raise TerselConversionError("UX Layout requires the card@1 primary Action.")
    gap = registry.ux_tokens["moduleGap"]
    direction = layout.lowering_by_size[size]
    if direction == "column":
        token = "compact" if len(children) == 1 else "section"
        options = {"itemMargin": registry.ux_tokens["denseInnerGap"] if len(children) == 1 else gap}
        return Nested2Node("Column", (token, options), children)
    weighted_children = tuple(
        Nested2Node(
            "Column",
            ("compact", {"layoutWeight": 1, "itemMargin": 0}),
            (child,),
        )
        for child in children
    )
    return Nested2Node(
        "Row",
        ("between", {"itemMargin": gap, "alignItems": "center"}),
        weighted_children,
    )


def _append_missing_required_literals_to_ux_layout(
    node: Nested2Node,
    contract: HybridBodyContract,
) -> Nested2Node:
    content, actions = _split_ux_layout_children(node)
    if not content:
        return node
    already_visible = tuple(
        descendant.values[0]
        for child in content[:-1]
        for descendant in _walk_nodes(child)
        if descendant.component_type == "Text"
        and descendant.values
        and isinstance(descendant.values[0], str)
    )
    completed = _append_missing_required_literals(
        content[-1],
        contract,
        already_visible=already_visible,
    )
    return Nested2Node(
        node.component_type,
        node.values,
        (*content[:-1], completed, *actions),
    )


def _split_ux_layout_children(
    node: Nested2Node,
) -> tuple[tuple[Nested2Node, ...], tuple[Nested2Node, ...]]:
    actions = tuple(
        child for child in node.children if child.component_type in _UX_ACTION_COMPONENTS
    )
    content = tuple(
        child for child in node.children if child.component_type not in _UX_ACTION_COMPONENTS
    )
    return content, actions


def _strip_2x2_composite_headers(
    node: Nested2Node,
    *,
    size: Literal["2x2", "2x4"],
) -> Nested2Node:
    """Remove redundant provider title rows from compact multi-region cards."""
    if size != "2x2" or node.component_type not in {
        "HeroSupportLayout",
        "HeroSupportActionLayout",
    }:
        return node
    content, actions = _split_ux_layout_children(node)
    if len(content) < 2:
        return node
    compact_content = tuple(_strip_redundant_component_header(item) for item in content)
    return Nested2Node(node.component_type, node.values, (*compact_content, *actions))


def _strip_redundant_component_header(node: Nested2Node) -> Nested2Node:
    if not _is_advanced_component_region(node) or len(node.children) < 2:
        return node
    header = node.children[0]
    if not _is_literal_component_header(header):
        return node
    return Nested2Node(node.component_type, node.values, node.children[1:])


def _is_literal_component_header(node: Nested2Node) -> bool:
    if node.component_type == "Text":
        return bool(node.values) and _is_plain_literal_text(node.values[0])
    if node.component_type != "Row" or not node.children:
        return False
    if any(child.component_type not in {"Image", "Text"} for child in node.children):
        return False
    text_values = [
        child.values[0]
        for child in node.children
        if child.component_type == "Text" and child.values
    ]
    return bool(text_values) and all(_is_plain_literal_text(value) for value in text_values)


def _is_plain_literal_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "${" not in value


def _inject_ux_business_title(
    node: Nested2Node,
    title: str | None,
    contract: HybridBodyContract,
) -> Nested2Node:
    """Project the trusted CardSpec title into the business region when useful."""
    if contract.required_business_component_ids or _is_advanced_component_region(node):
        return node
    if not isinstance(title, str) or not title.strip() or title not in contract.trusted_literals:
        return node
    normalized_title = _semantic_text_fragment(title)
    visible = tuple(
        descendant.values[0]
        for descendant in _walk_nodes(node)
        if descendant.component_type == "Text"
        and descendant.values
        and isinstance(descendant.values[0], str)
    )
    visible_blob = "".join(_semantic_text_fragment(item) for item in visible)
    if normalized_title and normalized_title in visible_blob:
        return node
    content, actions = _split_ux_layout_children(node)
    if not content:
        return node
    title_font_size = 10 if len(normalized_title) > 8 else 14
    title_node = Nested2Node(
        "Text",
        (
            title,
            "compact-title",
            {
                "width": "100%",
                "fontSize": title_font_size,
                "minFontSize": 9,
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        ),
        (),
    )
    first = content[0]
    if first.component_type in {"Column", "List"}:
        first = Nested2Node(first.component_type, first.values, (title_node, *first.children))
    else:
        first = Nested2Node("Column", ("compact",), (title_node, first))
    return Nested2Node(node.component_type, node.values, (first, *content[1:], *actions))


def _inject_phone_earphone_title(
    node: Nested2Node,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if _contract_ux_business_component_names(contract, registry) != {
        "BatteryOverview",
        "BluetoothDeviceOverview",
    }:
        return node
    title = _bluetooth_text("设备电量", "subtitle", 12, 400, align="start")
    body = _with_flex_weight(node, 1, axis="vertical")
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
            },
        ),
        (title, body),
    )


def _inject_resource_battery_title(
    node: Nested2Node,
    title: str | None,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    *,
    size: Literal["2x2", "2x4"],
) -> Nested2Node:
    """Place one trusted title above the titleless 2x2 peer chart group."""
    if size != "2x2" or _contract_ux_business_component_names(contract, registry) != {
        "BatteryOverview",
        "ResourceUsageOverview",
    }:
        return node
    if not isinstance(title, str) or not title.strip() or title not in contract.trusted_literals:
        raise TerselConversionError(
            "Resource and battery 2x2 peer composition requires one trusted outer title."
        )
    title_node = _resource_usage_text(
        title,
        "compact-title",
        font_size=12,
        font_weight=400,
        font_color="#99182431",
    )
    body = _with_flex_weight(node, 1, axis="vertical")
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": "start",
                "alignItems": "start",
                "clip": True,
            },
        ),
        (title_node, body),
    )


def _deduplicate_ux_business_title_fragments(
    node: Nested2Node,
    title: str | None,
) -> Nested2Node:
    """Let one visible business title own its later literal fragments."""
    if not isinstance(title, str) or not title.strip():
        return node
    title_fragment = _semantic_text_fragment(title)
    has_title = any(
        descendant.component_type == "Text" and descendant.values and descendant.values[0] == title
        for descendant in _walk_nodes(node)
    )
    if not has_title:
        return node

    def visit(current: Nested2Node) -> Nested2Node | None:
        is_text = current.component_type == "Text" and bool(current.values)
        has_text_value = is_text and isinstance(current.values[0], str)
        if has_text_value and current.values[0] != title:
            fragment = _semantic_text_fragment(current.values[0])
            if len(fragment) >= 2 and fragment in title_fragment:
                return None
        children = tuple(child for item in current.children if (child := visit(item)) is not None)
        if current.children and not children and current.component_type in _CONTAINERS:
            return None
        return Nested2Node(current.component_type, current.values, children)

    return visit(node) or node


def _lower_ux_layout_root(
    node: Nested2Node,
    *,
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if node.component_type not in UX_LAYOUT_COMPONENT_IDS:
        raise TerselConversionError("UX Mixed root is not a Layout Component.")
    layout = registry.require_ux_layout_component(node.component_type)
    configuration = dict(node.values[0]) if node.values else {}
    content, actions = _split_ux_layout_children(node)
    lowered_content = tuple(
        _lower_ux_layouts(
            child,
            size=size,
            has_action=False,
            registry=registry,
        )
        for child in content
    )
    lowered_actions = tuple(
        _lower_ux_action(
            child,
            size=size,
            contract=contract,
            registry=registry,
            allow_action_tile_2x2=node.component_type == "ActionMatrixLayout",
            action_tile_orientation=(
                "vertical" if node.component_type == "ActionMatrixLayout" else "horizontal"
            ),
        )
        for child in actions
    )
    if (
        not layout.minimum_children(size)
        <= len(lowered_content)
        <= layout.max_children_by_size[size]
    ):
        raise TerselConversionError("UX Layout content budget changed during expansion.")
    lowered = _lower_registered_ux_layout(
        node.component_type,
        lowered_content,
        lowered_actions,
        configuration=configuration,
        size=size,
        contract=contract,
        registry=registry,
    )
    if any(_is_weather_region(item) for item in lowered_content):
        return _normalize_weather_fill_parent_dimensions(lowered)
    return lowered


def _lower_registered_ux_layout(
    layout_id: str,
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    *,
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    provider_layout = _instantiate_provider_layout_blueprint(
        layout_id,
        content,
        actions,
        params=configuration,
        contract=contract,
        registry=registry,
    )
    if provider_layout is not None:
        return provider_layout
    if layout_id == "SingleFocusLayout":
        return _lower_single_focus_layout(content, actions, configuration, size, registry)
    if layout_id == "HeroActionLayout":
        return _lower_hero_action_layout(content, actions, configuration, size, registry)
    if layout_id == "HeroSupportLayout":
        return _lower_hero_support_layout(
            content,
            configuration,
            size,
            _ux_support_surface_color(contract, registry),
            registry,
        )
    if layout_id == "HeroSupportActionLayout":
        return _lower_hero_support_action_layout(
            content,
            actions,
            configuration,
            size,
            _ux_support_surface_color(contract, registry),
            contract,
            registry,
        )
    if layout_id == "PeerPairLayout":
        return _lower_peer_pair_layout(content, actions, configuration, size, registry)
    if layout_id == "SequentialSummaryLayout":
        return _lower_sequential_summary_layout(
            content,
            configuration,
            size,
            _ux_support_surface_color(contract, registry),
            registry,
        )
    if layout_id == "EqualItemsLayout":
        return _lower_equal_items_layout(content, configuration, size, registry)
    if layout_id == "ListActionLayout":
        return _lower_list_action_layout(content, actions, configuration, size, registry)
    if layout_id == "ActionMatrixLayout":
        return _lower_action_matrix_layout(content, actions, configuration, size, registry)
    if layout_id == "WeatherNowForecastLayout":
        return _lower_weather_now_forecast_layout(
            content,
            actions,
            size,
            _ux_support_surface_color(contract, registry),
            registry,
        )
    raise TerselConversionError(f"Unsupported UX Layout lowering: {layout_id}")


def _instantiate_provider_layout_blueprint(
    layout_id: str,
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    *,
    params: dict[str, Any],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node | None:
    definition_items = []
    for wire_id in contract.allowed_template_ids:
        definition = registry.require_template(wire_id)
        if definition.template_id != layout_id or definition.source_format != "cardtpl/1":
            continue
        definition_items.append(definition)
    definitions = tuple(definition_items)
    if not definitions:
        return None
    if len(definitions) > 1:
        raise TerselConversionError(
            f"Provider Layout Template is ambiguous: {layout_id}"
        )
    definition = definitions[0]
    variant = definition.variants[0]
    if variant.root.component in UX_LAYOUT_COMPONENT_IDS:
        return None
    if definition.bindings:
        raise TerselConversionError(
            "Provider Layout Template cannot declare data bindings."
        )
    children = (*content, *actions)
    indexed_child_slots = _template_child_slot_indexes(variant.root)
    if indexed_child_slots and len(children) != len(indexed_child_slots):
        raise TerselConversionError(
            f"Provider Layout Template child count is invalid: {definition.wire_id}"
        )
    return _instantiate_blueprint(
        variant.root,
        params,
        theme_values=registry.theme_reference_values(contract.theme_profile_id),
        spread_children=children,
    )


def _lower_single_focus_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    align = configuration.get("contentAlign", "topStart")
    justify = {"topStart": "start", "centerStart": "center", "bottomStart": "end"}[align]
    base = Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": justify,
                "alignItems": "start",
                "clip": True,
            },
        ),
        content,
    )
    return _place_optional_layout_action(base, actions, size=size, registry=registry)


def _lower_hero_action_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    placement = configuration.get("actionPlacement", "bottom")
    if size == "2x2" and placement == "end":
        raise TerselConversionError(
            "HeroActionLayout actionPlacement=end is only available for 2x4."
        )

    # For 2x4 layouts with wide hero split structure (Row with hero+support columns),
    # place the PillAction in the right half at bottom instead of full width at bottom
    # This applies to all WideHero layouts, not just specific component types
    if size == "2x4" and actions and _is_wide_hero_split_structure(content[0]):
        hero = content[0].children[0]
        support = content[0].children[1]
        # Create support+action column (stacked vertically, right half)
        support_action = Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                    "justifyContent": "spaceBetween",
                },
            ),
            (support, actions[0]),
        )
        # Create weighted row with hero (left 50%) and support+action (right 50%)
        return _weighted_row((hero, support_action), (50, 50), registry)

    base = _single_region(content[0], justify="start", registry=registry)
    return _place_optional_layout_action(
        base,
        actions,
        size=size,
        registry=registry,
        placement=placement,
    )


def _lower_hero_support_layout(
    content: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    support_surface_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if size == "2x2" and _is_date_region(content[0]):
        date_context = _merge_node_options(content[0], {"height": 20, "clip": True})
        schedule = _with_flex_weight(content[1], 1, axis="vertical")
        return Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                },
            ),
            (date_context, schedule),
        )
    default_ratio = "balanced" if size == "2x4" else "heroWide"
    ratio = configuration.get("ratio", default_ratio)
    direction = configuration.get("direction", "auto")
    if size == "2x2":
        direction = "vertical"
    elif direction == "auto":
        direction = "horizontal" if size == "2x4" else _auto_pair_direction(content)
    weights = {
        "balanced": (50, 50),
        "heroWide": (56, 44),
        "supportWide": (44, 56),
    }[ratio]
    if size == "2x2" and _is_weather_region(content[0]):
        weights = (76, 24)
    if size == "2x4" and _is_resource_usage_region(content[0]):
        weights = (56, 44)
    support = content[1]
    if size == "2x4" and _is_resource_usage_region(content[0]):
        support = _normalize_ring_geometry(support, ring_size=44)
    if size == "2x4" and _is_textual_region(support):
        support = _support_panel(support, support_surface_color, registry)
    regions = (content[0], support)
    if direction == "horizontal":
        return _weighted_row(regions, weights, registry)
    return _weighted_column(regions, weights, registry)


def _lower_hero_support_action_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    support_surface_color: str,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> Nested2Node:
    if size == "2x2":
        if _is_date_region(content[0]):
            date_context = _merge_node_options(content[0], {"height": 20, "clip": True})
            schedule = _with_flex_weight(content[1], 1, axis="vertical")
            base = Nested2Node(
                "Column",
                (
                    "section",
                    {
                        "width": "100%",
                        "height": "100%",
                        "itemMargin": registry.ux_tokens["moduleGap"],
                    },
                ),
                (date_context, schedule),
            )
            return _place_optional_layout_action(
                base,
                actions,
                size=size,
                registry=registry,
            )
        if not _is_advanced_component_region(content[1]) and _compact_support_overflows(
            content[0], content[1], actions[0], registry
        ):
            required = set(contract.required_literals)
            support_literals = {
                str(item.values[0])
                for item in _walk_nodes(content[1])
                if item.component_type == "Text" and item.values
            }
            if required & support_literals:
                raise TerselConversionError(
                    "HeroSupportActionLayout cannot drop required Support content on 2x2."
                )
            hero = _single_region(content[0], justify="start", registry=registry)
            return _place_optional_layout_action(
                hero,
                actions,
                size=size,
                registry=registry,
            )
        hero = _with_flex_weight(content[0], 1, axis="vertical")
        support_height = 28 if _is_weather_region(content[0]) else 36
        if _is_weather_region(content[0]) and _is_battery_region(content[1]):
            support_height = 36
        support = _merge_node_options(
            content[1],
            {"height": support_height, "clip": True},
        )
        base = Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                },
            ),
            (hero, support),
        )
        return _place_optional_layout_action(base, actions, size=size, registry=registry)
    ratio = configuration.get("heroRatio", "wide")
    # For 2x4 layouts, use 50/50 weights to give the PillAction 50% width at the bottom right
    weights = (50, 50) if size == "2x4" else ((56, 44) if ratio == "wide" else (50, 50))
    support = content[1]
    if _is_resource_usage_region(content[0]):
        support = _normalize_ring_geometry(support, ring_size=44)
    if _is_textual_region(support):
        support = _support_panel(support, support_surface_color, registry)
    support = _with_flex_weight(support, 1, axis="vertical")
    support_action = Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "spaceBetween",
            },
        ),
        (support, actions[0]),
    )
    return _weighted_row((content[0], support_action), weights, registry)


def _compact_support_overflows(
    hero: Nested2Node,
    support: Nested2Node,
    action: Nested2Node,
    registry: CardPlanRegistry,
) -> bool:
    support_line_count = sum(item.component_type == "Text" for item in _walk_nodes(support))
    if support_line_count > 2:
        return True
    support_limit = 28 if _is_weather_region(hero) else registry.ux_tokens["pillActionHeight"]
    support_height = min(_estimate_height(support), support_limit)
    if _is_icon_action_node(action, registry):
        action_height = 0
        gap_count = 1
    else:
        action_height = registry.ux_tokens["pillActionHeight"]
        gap_count = 2
    required_height = (
        _estimate_height(hero)
        + support_height
        + action_height
        + registry.ux_tokens["moduleGap"] * gap_count
    )
    return required_height > _ux_layout_body_budget(registry)


def _lower_peer_pair_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    compact_resource_pair = size == "2x2" and any(
        _is_resource_usage_region(item) for item in content
    )
    if compact_resource_pair:
        content = tuple(_normalize_ring_geometry(item, ring_size=44) for item in content)
    orientation = configuration.get("orientation", "auto")
    if compact_resource_pair:
        # Resource and battery peers each need their full compact metric height.
        # A model-requested row stack clips the capacity lines in a 160 vp card.
        orientation = "columns"
    elif actions and size == "2x2":
        orientation = "columns"
    elif orientation == "auto":
        orientation = "columns" if size == "2x4" else _auto_peer_orientation(content)
    if orientation == "columns":
        base = _weighted_row(content, (50, 50), registry)
    else:
        base = _weighted_column(content, (50, 50), registry)
    return _place_optional_layout_action(base, actions, size=size, registry=registry)


def _lower_sequential_summary_layout(
    content: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    support_surface_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    primary = _with_flex_weight(content[0], 1, axis="vertical")
    details = tuple(_support_panel(item, support_surface_color, registry) for item in content[1:])
    requested_columns = configuration.get("detailColumns", len(details))
    column_limit = 2 if size == "2x2" else 4
    columns = min(requested_columns, column_limit, len(details))
    detail_grid = _equal_grid(details, columns=max(1, columns), registry=registry)
    detail_grid = _with_flex_weight(detail_grid, 1, axis="vertical")
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
            },
        ),
        (primary, detail_grid),
    )


def _lower_equal_items_layout(
    content: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    arrangement = configuration.get("arrangement", "auto")
    if arrangement == "auto":
        arrangement = "grid" if size == "2x4" and len(content) == 4 else "row"
    modules = tuple(_equal_item_panel(item, registry) for item in content)
    columns = 2 if arrangement == "grid" else len(modules)
    return _equal_grid(modules, columns=columns, registry=registry)


def _lower_list_action_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    placement = configuration.get("actionPlacement", "bottom")
    if size == "2x2" and placement == "end":
        raise TerselConversionError(
            "ListActionLayout actionPlacement=end is only available for 2x4."
        )
    base = _single_region(content[0], justify="start", registry=registry)
    return _place_optional_layout_action(
        base,
        actions,
        size=size,
        registry=registry,
        placement=placement,
    )


def _lower_action_matrix_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    configuration: dict[str, Any],
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    primary_index = configuration.get("primaryActionIndex", 0)
    if not 0 <= primary_index < len(actions):
        raise TerselConversionError(
            "ActionMatrixLayout primaryActionIndex exceeds the Action count."
        )
    ordered = actions
    if primary_index != 0:
        primary = actions[primary_index]
        ordered = (primary, *(item for index, item in enumerate(actions) if index != primary_index))
    matrix = _action_matrix_grid(ordered, size=size, registry=registry)
    if not content:
        return matrix
    summary = _single_region(content[0], justify="end", registry=registry)
    if size == "2x2":
        summary = _with_flex_weight(summary, 1, axis="vertical")
        matrix = _with_flex_weight(matrix, 2, axis="vertical")
        return Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                },
            ),
            (summary, matrix),
        )
    return _weighted_row((summary, matrix), (56, 44), registry)


def _lower_weather_now_forecast_layout(
    content: tuple[Nested2Node, ...],
    actions: tuple[Nested2Node, ...],
    size: Literal["2x2", "2x4"],
    support_surface_color: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    current = _single_region(content[0], justify="start", registry=registry)
    if size == "2x2":
        return _place_optional_layout_action(current, actions, size=size, registry=registry)
    if len(content) == 1:
        base = current
    else:
        forecast_items = tuple(
            _support_panel(item, support_surface_color, registry) for item in content[1:]
        )
        forecast_row = _equal_grid(
            forecast_items,
            columns=len(forecast_items),
            registry=registry,
        )
        current = _with_flex_weight(current, 3, axis="vertical")
        forecast_row = _with_flex_weight(forecast_row, 2, axis="vertical")
        base = Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                },
            ),
            (current, forecast_row),
        )
    return _place_optional_layout_action(base, actions, size=size, registry=registry)


def _single_region(
    child: Nested2Node,
    *,
    justify: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    return Nested2Node(
        "Column",
        (
            "compact",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["denseInnerGap"],
                "justifyContent": justify,
                "alignItems": "start",
                "clip": True,
                "constraintSize": {"minWidth": 0, "minHeight": 0},
            },
        ),
        (child,),
    )


def _weighted_row(
    children: tuple[Nested2Node, ...],
    weights: tuple[int, ...],
    registry: CardPlanRegistry,
) -> Nested2Node:
    regions = tuple(
        Nested2Node(
            "Column",
            (
                "compact",
                {
                    "layoutWeight": weight,
                    "itemMargin": 0,
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (child,),
        )
        for child, weight in zip(children, weights, strict=True)
    )
    return Nested2Node(
        "Row",
        (
            "between",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "alignItems": "center",
            },
        ),
        regions,
    )


def _weighted_column(
    children: tuple[Nested2Node, ...],
    weights: tuple[int, ...],
    registry: CardPlanRegistry,
) -> Nested2Node:
    regions = tuple(
        Nested2Node(
            "Column",
            (
                "compact",
                {
                    "layoutWeight": weight,
                    "itemMargin": 0,
                    "clip": True,
                    "constraintSize": {"minWidth": 0, "minHeight": 0},
                },
            ),
            (child,),
        )
        for child, weight in zip(children, weights, strict=True)
    )
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
            },
        ),
        regions,
    )


def _support_panel(
    child: Nested2Node,
    background: str,
    registry: CardPlanRegistry,
) -> Nested2Node:
    padding = registry.ux_tokens["moduleGap"]
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "100%",
                "height": "100%",
                "padding": {
                    "left": 12,
                    "top": padding,
                    "right": 12,
                    "bottom": padding,
                },
                "borderRadius": 8,
                "backgroundColor": background,
                "alignContent": "topStart",
                "clip": True,
            },
        ),
        (child,),
    )


def _equal_item_panel(child: Nested2Node, registry: CardPlanRegistry) -> Nested2Node:
    padding = registry.ux_tokens["moduleGap"]
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "100%",
                "height": "100%",
                "padding": padding,
                "borderRadius": 8,
                "alignContent": "center",
                "clip": True,
            },
        ),
        (child,),
    )


def _equal_grid(
    children: tuple[Nested2Node, ...],
    *,
    columns: int,
    registry: CardPlanRegistry,
) -> Nested2Node:
    rows: list[Nested2Node] = []
    for start in range(0, len(children), columns):
        row_children = children[slice(start, start + columns)]
        weights = tuple(1 for _item in row_children)
        rows.append(_weighted_row(row_children, weights, registry))
    if len(rows) == 1:
        return rows[0]
    weighted_rows = tuple(_with_flex_weight(row, 1, axis="vertical") for row in rows)
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
            },
        ),
        weighted_rows,
    )


def _action_matrix_grid(
    actions: tuple[Nested2Node, ...],
    *,
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
) -> Nested2Node:
    if len(actions) == 3:
        secondary = _equal_grid(actions[1:], columns=2, registry=registry)
        primary = _with_flex_weight(actions[0], 1, axis="vertical")
        secondary = _with_flex_weight(secondary, 1, axis="vertical")
        return Nested2Node(
            "Column",
            (
                "section",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": registry.ux_tokens["moduleGap"],
                },
            ),
            (primary, secondary),
        )
    columns = 2 if len(actions) == 4 else len(actions)
    if size == "2x2":
        # For 2x2 with 2 actions, use vertical layout (columns=1) instead of horizontal
        columns = 1 if len(actions) == 2 else 2
    return _equal_grid(actions, columns=columns, registry=registry)


def _place_optional_layout_action(
    base: Nested2Node,
    actions: tuple[Nested2Node, ...],
    *,
    size: Literal["2x2", "2x4"],
    registry: CardPlanRegistry,
    placement: str = "bottom",
) -> Nested2Node:
    if not actions:
        return base
    action = actions[0]
    if _is_icon_action_node(action, registry):
        return _overlay_icon_action(base, action, registry)
    if size == "2x4" and placement == "end":
        action_region = Nested2Node(
            "Column",
            (
                "compact",
                {
                    "width": "100%",
                    "height": "100%",
                    "itemMargin": 0,
                    "justifyContent": "end",
                    "alignItems": "start",
                },
            ),
            (action,),
        )
        return _weighted_row((base, action_region), (60, 40), registry)
    if size == "2x2":
        base = _compact_2x2_action_content(base, registry)
    base = _with_flex_weight(base, 1, axis="vertical")
    return Nested2Node(
        "Column",
        (
            "section",
            {
                "width": "100%",
                "height": "100%",
                "itemMargin": registry.ux_tokens["moduleGap"],
                "justifyContent": "spaceBetween",
            },
        ),
        (base, action),
    )


def _is_icon_action_node(action: Nested2Node, registry: CardPlanRegistry) -> bool:
    if action.component_type != "Stack":
        return False
    options = next((value for value in action.values if isinstance(value, dict)), {})
    return options.get("width") == registry.ux_tokens["iconActionSize"]


def _auto_pair_direction(children: tuple[Nested2Node, ...]) -> str:
    return "horizontal" if any(_contains_visual_region(item) for item in children) else "vertical"


def _auto_peer_orientation(children: tuple[Nested2Node, ...]) -> str:
    return "columns" if any(_contains_visual_region(item) for item in children) else "rows"


def _contains_visual_region(node: Nested2Node) -> bool:
    return any(item.component_type in {"Image", "Progress"} for item in _walk_nodes(node))


def _has_layout_weight(node: Nested2Node) -> bool:
    """Check if a node has layoutWeight property (used for weighted row/column layouts)."""
    return any(
        isinstance(value, dict) and "layoutWeight" in value
        for value in node.values
    )


def _is_wide_hero_split_structure(node: Nested2Node) -> bool:
    """Check if node is a wide hero split structure: a split structure with/without title"""
    if node.component_type == "Column" and len(node.children) == 2:
        return _is_split_structure(node.children[1])
    return _is_split_structure(node)


def _is_split_structure(node: Nested2Node) -> bool:
    """Check if node is a split structure: Row with 2 Column children, each with layoutWeight."""
    if node.component_type != "Row" or len(node.children) != 2:
        return False
    if not all(child.component_type == "Column" for child in node.children):
        return False
    # Both columns should have layoutWeight for proper 50/50 split
    return all(_has_layout_weight(child) for child in node.children)


def _is_weather_region(node: Nested2Node) -> bool:
    return any(
        any(
            isinstance(value, dict) and value.get("_advancedComponent") == "WeatherOverview"
            for value in item.values
        )
        for item in _walk_nodes(node)
    )


def _is_advanced_component_region(node: Nested2Node) -> bool:
    return any(
        any(
            isinstance(value, dict) and isinstance(value.get("_advancedComponent"), str)
            for value in item.values
        )
        for item in _walk_nodes(node)
    )


def _is_resource_usage_region(node: Nested2Node) -> bool:
    return any(
        any(
            isinstance(value, dict) and value.get("_advancedComponent") == "ResourceUsageOverview"
            for value in item.values
        )
        for item in _walk_nodes(node)
    )


def _is_battery_region(node: Nested2Node) -> bool:
    return any(
        any(
            isinstance(value, dict) and value.get("_advancedComponent") == "BatteryOverview"
            for value in item.values
        )
        for item in _walk_nodes(node)
    )


def _normalize_ring_geometry(node: Nested2Node, *, ring_size: int) -> Nested2Node:
    children = tuple(
        _normalize_ring_geometry(child, ring_size=ring_size) for child in node.children
    )
    values = list(node.values)
    options_index = next(
        (index for index, value in enumerate(values) if isinstance(value, dict)),
        None,
    )
    options = dict(values[options_index]) if options_index is not None else {}
    is_ring_progress = node.component_type == "Progress" and options.get("type") == "ring"
    contains_direct_ring = node.component_type == "Stack" and any(
        child.component_type == "Progress"
        and any(isinstance(value, dict) and value.get("type") == "ring" for value in child.values)
        for child in children
    )
    if is_ring_progress:
        options.update({"width": ring_size, "height": ring_size, "strokeWidth": 6})
    elif contains_direct_ring:
        options.update({"width": ring_size, "height": ring_size})
    else:
        return Nested2Node(node.component_type, node.values, children)
    if options_index is None:
        values.append(options)
    else:
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), children)


def _normalize_weather_fill_parent_dimensions(node: Nested2Node) -> Nested2Node:
    """Use the renderer's fill-parent token instead of percentage-like literals."""
    children = tuple(_normalize_weather_fill_parent_dimensions(child) for child in node.children)
    if node.component_type not in _STANDARD_CONTAINERS:
        return Nested2Node(node.component_type, node.values, children)
    values: list[Any] = []
    for value in node.values:
        if not isinstance(value, dict):
            values.append(value)
            continue
        options = dict(value)
        for dimension in ("width", "height"):
            if options.get(dimension) == "100%":
                options[dimension] = "matchParent"
        values.append(options)
    return Nested2Node(node.component_type, tuple(values), children)


def _normalize_weather_condition_icons(
    node: Nested2Node,
    contract: HybridBodyContract,
    *,
    weather_region: bool = False,
) -> Nested2Node:
    """Apply the existing weather icon color policy to direct and Template regions."""
    options_index = next(
        (index for index, value in enumerate(node.values) if isinstance(value, dict)),
        None,
    )
    options = dict(node.values[options_index]) if options_index is not None else {}
    inside_weather = weather_region or options.get("_advancedComponent") == "WeatherOverview"
    children = tuple(
        _normalize_weather_condition_icons(child, contract, weather_region=inside_weather)
        for child in node.children
    )
    if not inside_weather or node.component_type != "Image" or not node.values:
        return Nested2Node(node.component_type, node.values, children)
    source = node.values[0]
    if not isinstance(source, str):
        return Nested2Node(node.component_type, node.values, children)
    icon_tags = set(contract.asset_semantic_tags_by_source.get(source, ()))
    if _weather_icon_is_sun(source, contract):
        options.pop("_preserveOriginalColor", None)
        options["fillColor"] = _SUNNY_WEATHER_ICON_COLOR
    elif _weather_icon_is_multicolor(source):
        options.pop("fillColor", None)
        options["_preserveOriginalColor"] = True
    elif icon_tags & {"water", "rain", "drop", "cloud", "storm", "snow"}:
        options.pop("_preserveOriginalColor", None)
        options["fillColor"] = "#FFFFFFFF"
    else:
        options.pop("_preserveOriginalColor", None)
        options.setdefault("fillColor", "#FFFFFFFF")
    values = list(node.values)
    if options_index is None:
        values.append(options)
    else:
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), children)


def _is_date_region(node: Nested2Node) -> bool:
    return any(
        any(
            isinstance(value, dict) and value.get("_advancedComponent") == "DateOverview"
            for value in item.values
        )
        for item in _walk_nodes(node)
    )


def _strip_advanced_component_markers(node: Nested2Node) -> Nested2Node:
    children = tuple(_strip_advanced_component_markers(child) for child in node.children)
    values: list[Any] = []
    marker_keys = {
        "_boundTemplateAction",
        "_advancedComponent",
        "_preserveOriginalColor",
        "_layoutActionBackgroundOpacity",
    }
    for value in node.values:
        if isinstance(value, dict) and not marker_keys.isdisjoint(value):
            cleaned = dict(value)
            cleaned.pop("_boundTemplateAction", None)
            cleaned.pop("_advancedComponent", None)
            cleaned.pop("_preserveOriginalColor", None)
            cleaned.pop("_layoutActionBackgroundOpacity", None)
            values.append(cleaned)
        else:
            values.append(value)
    return Nested2Node(node.component_type, tuple(values), children)


def _is_textual_region(node: Nested2Node) -> bool:
    return not _contains_visual_region(node)


def _ux_support_surface_color(
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> str:
    theme = registry.require_theme(contract.theme_profile_id)
    return _theme_color_with_alpha(theme.primary_color, 0x24)


def _merge_node_options(node: Nested2Node, additions: dict[str, Any]) -> Nested2Node:
    values = list(node.values)
    options_index = next(
        (index for index, value in enumerate(values) if isinstance(value, dict)),
        None,
    )
    options = dict(values[options_index]) if options_index is not None else {}
    options.update(additions)
    if options_index is None:
        values.append(options)
    else:
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), node.children)


def _with_flex_weight(
    node: Nested2Node,
    weight: int,
    *,
    axis: Literal["horizontal", "vertical"],
) -> Nested2Node:
    values = list(node.values)
    options_index = next(
        (index for index, value in enumerate(values) if isinstance(value, dict)),
        None,
    )
    options = dict(values[options_index]) if options_index is not None else {}
    options.pop("width" if axis == "horizontal" else "height", None)
    options.update(
        {
            "layoutWeight": weight,
            "clip": True,
            "constraintSize": {"minWidth": 0, "minHeight": 0},
        }
    )
    if options_index is None:
        values.append(options)
    else:
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), node.children)


def _is_numeric_text_node(node: Nested2Node) -> bool:
    is_text = node.component_type == "Text" and bool(node.values)
    if not is_text or not isinstance(node.values[0], str):
        return False
    return re.fullmatch(r"[+-]?\d+(?:\.\d+)?", node.values[0].strip()) is not None


def _is_short_unit_text_node(node: Nested2Node) -> bool:
    is_text = node.component_type == "Text" and bool(node.values)
    has_design_token = len(node.values) > 1 and node.values[1] in {"body", "subtitle"}
    if not is_text or not has_design_token or not isinstance(node.values[0], str):
        return False
    fragment = _semantic_text_fragment(node.values[0])
    return re.search(r"\d", node.values[0]) is None and 1 <= len(fragment) <= 3


def _is_compact_text_row(node: Nested2Node) -> bool:
    is_short_row = node.component_type == "Row" and 1 <= len(node.children) <= 3
    if not is_short_row:
        return False
    return all(_is_short_compact_text(item) for item in node.children)


def _is_short_compact_text(node: Nested2Node) -> bool:
    is_text = node.component_type == "Text" and bool(node.values)
    if not is_text or not isinstance(node.values[0], str):
        return False
    return len(_semantic_text_fragment(node.values[0])) <= 6


def _compact_2x2_action_content(
    node: Nested2Node,
    registry: CardPlanRegistry,
) -> Nested2Node:
    """Compact generic metric rows before reserving the fixed Action slot.

    This is deliberately structural: it does not inspect fixture IDs, business
    domains, labels, or literal values. Adjacent short text-only rows represent
    one inline metric group in the UX grammar and otherwise waste the limited
    vertical budget when emitted as separate rows by a model.
    """
    children = tuple(_compact_2x2_action_content(child, registry) for child in node.children)
    current = Nested2Node(node.component_type, node.values, children)
    if current.component_type not in {"Column", "List"}:
        return current
    normalized_children = list(current.children)
    for index, child in enumerate(normalized_children):
        if not _is_numeric_text_node(child):
            continue
        unit_index = next(
            (
                candidate_index
                for candidate_index in range(index + 1, len(normalized_children))
                for candidate in (normalized_children[candidate_index],)
                if _is_short_unit_text_node(candidate)
            ),
            None,
        )
        if unit_index is None:
            continue
        unit = normalized_children.pop(unit_index)
        normalized_children[index] = Nested2Node(
            "Row",
            (
                "between",
                {
                    "width": "100%",
                    "height": 24,
                    "itemMargin": registry.ux_tokens["denseInnerGap"],
                    "alignItems": "bottom",
                },
            ),
            (child, unit),
        )
        break
    merged: list[Nested2Node] = []
    pending_rows: list[Nested2Node] = []

    def flush_rows() -> None:
        if len(pending_rows) < 2:
            merged.extend(pending_rows)
        else:
            merged.append(
                Nested2Node(
                    "Row",
                    (
                        "between",
                        {
                            "width": "100%",
                            "height": 24,
                            "itemMargin": registry.ux_tokens["denseInnerGap"],
                            "alignItems": "bottom",
                        },
                    ),
                    tuple(child for row in pending_rows for child in row.children),
                )
            )
        pending_rows.clear()

    for child in normalized_children:
        if _is_compact_text_row(child):
            pending_rows.append(child)
            continue
        flush_rows()
        merged.append(child)
    flush_rows()
    compacted = (
        current
        if tuple(merged) == current.children
        else Nested2Node(current.component_type, current.values, tuple(merged))
    )
    return _merge_node_options(
        compacted,
        {"itemMargin": registry.ux_tokens["denseInnerGap"]},
    )


def _overlay_icon_action(
    content: Nested2Node,
    action: Nested2Node,
    registry: CardPlanRegistry,
) -> Nested2Node:
    reserved = registry.ux_tokens["iconActionSize"] + registry.ux_tokens["moduleGap"]
    if _is_weather_region(content):
        reserved_content = _reserve_weather_icon_action_corner(content, reserved)
    elif _is_battery_region(content):
        # BatteryOverview owns the bottom-left Ring while IconAction owns the
        # bottom-right corner. They are disjoint fixed anchors, so padding the
        # whole business region would incorrectly lift the Ring upward.
        reserved_content = content
    else:
        reserved_content = _merge_node_options(
            content,
            {
                "padding": {"right": reserved, "bottom": reserved},
                "clip": True,
            },
        )
    content_layer = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "100%",
                "height": "100%",
                "alignContent": "topStart",
            },
        ),
        (reserved_content,),
    )
    action_layer = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "100%",
                "height": "100%",
                "alignContent": "bottomEnd",
            },
        ),
        (action,),
    )
    return Nested2Node(
        "Stack",
        ("overlay", {"width": "100%", "height": "100%"}),
        (content_layer, action_layer),
    )


def _reserve_weather_icon_action_corner(node: Nested2Node, reserved: int) -> Nested2Node:
    """Reserve only the weather region that can overlap the bottom-right action."""
    children = tuple(
        _reserve_weather_icon_action_corner(child, reserved) for child in node.children
    )
    current = Nested2Node(node.component_type, node.values, children)
    options = next((value for value in current.values if isinstance(value, dict)), {})
    is_weather_root = options.get("_advancedComponent") == "WeatherOverview"
    is_layered_weather_root = current.component_type in {"Stack", "Column"}
    if is_weather_root and is_layered_weather_root and len(current.children) >= 3:
        weather_children = list(current.children)
        weather_children[-1] = _merge_node_options(
            weather_children[-1],
            {
                "padding": {
                    "left": 0,
                    "top": 0,
                    "right": reserved,
                    "bottom": 0,
                }
            },
        )
        return Nested2Node(current.component_type, current.values, tuple(weather_children))
    weather_leads_multi_region = (
        current.component_type == "Column"
        and len(current.children) >= 2
        and _is_weather_region(current.children[0])
    )
    if weather_leads_multi_region:
        region_children = list(current.children)
        region_children[-1] = _merge_node_options(
            region_children[-1],
            {
                "padding": {
                    "left": 0,
                    "top": 0,
                    "right": reserved,
                    "bottom": 0,
                }
            },
        )
        return Nested2Node(current.component_type, current.values, tuple(region_children))
    return current


def _lower_ux_action(
    node: Nested2Node,
    *,
    size: Literal["2x2", "2x4"],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    allow_action_tile_2x2: bool = False,
    action_tile_orientation: Literal["horizontal", "vertical"] = "horizontal",
) -> Nested2Node:
    if len(node.values) != 1 or not isinstance(node.values[0], dict):
        raise TerselConversionError("UX Action parameters are invalid.")
    params = node.values[0]
    action_id = params.get("actionId")
    binding = next(
        (item for item in contract.action_bindings if item.action_id == action_id),
        None,
    )
    if binding is None:
        raise TerselConversionError("UX Action binding is unavailable.")
    theme_action = registry.require_theme(contract.theme_profile_id).action_style
    background = theme_action.background_color if theme_action else "#1A0A59F7"
    foreground = theme_action.content_color if theme_action else "#FF0A59F7"
    background = _provider_layout_action_background(
        contract,
        registry,
        foreground=foreground,
        default=background,
    )
    icon = params.get("icon")
    if node.component_type == "IconAction":
        if not isinstance(icon, str):
            raise TerselConversionError("IconAction requires an approved icon.")
        if re.search(r"(?:^|[_-])white(?:[_.-]|$)", icon.casefold()):
            background, foreground = foreground, "#FFFFFFFF"
        return _lower_action_template_tree(
            node,
            background=background,
            foreground=foreground,
        )
    if node.component_type == "ActionTile":
        if size != "2x4" and not allow_action_tile_2x2:
            raise TerselConversionError("ActionTile is only available for 2x4.")
        return _lower_action_tile(
            binding.display_label,
            icon,
            background,
            foreground,
            [{"call": binding.call, "args": binding.args}],
            orientation=action_tile_orientation,
        )
    return _lower_action_template_tree(
        node,
        background=background,
        foreground=foreground,
    )


def _provider_layout_action_background(
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    *,
    foreground: str,
    default: str,
) -> str:
    """Resolve a single-business Provider Template Action background override."""
    if len(_contract_ux_business_component_names(contract, registry)) != 1:
        return default
    opacities = {
        definition.layout_action_style.background_opacity
        for wire_id in contract.allowed_template_ids
        if (definition := registry.templates.get(wire_id)) is not None
        and definition.source_format == "cardtpl/1"
        and definition.layout_action_style is not None
    }
    if len(opacities) != 1:
        return default
    if not foreground.startswith("#") or len(foreground) != 9:
        return "#1A000000"
    alpha = int(255 * opacities.pop())
    return f"#{alpha:02X}{foreground[-6:]}"


def _lower_action_template_tree(
    node: Nested2Node,
    *,
    background: str,
    foreground: str,
) -> Nested2Node:
    if len(node.children) != 1 or node.children[0].component_type != "Stack":
        raise TerselConversionError("UX Action must contain one trusted Action Template.")

    def apply_foreground(current: Nested2Node) -> Nested2Node:
        children = tuple(apply_foreground(child) for child in current.children)
        styled = Nested2Node(current.component_type, current.values, children)
        if current.component_type == "Text":
            return _merge_node_options(styled, {"fontColor": foreground})
        if current.component_type == "Image":
            return _merge_node_options(styled, {"fillColor": foreground})
        return styled

    content = apply_foreground(node.children[0])
    root_options = next((value for value in content.values if isinstance(value, dict)), None)
    if root_options is None or "onClick" not in root_options:
        raise TerselConversionError("UX Action Template must declare onClick.")
    return _merge_node_options(content, {"backgroundColor": background})


def _lower_action_tile(
    label: str,
    icon: Any,
    background: str,
    foreground: str,
    event: list[dict[str, Any]],
    *,
    orientation: Literal["horizontal", "vertical"],
) -> Nested2Node:
    children: list[Nested2Node] = []
    if isinstance(icon, str):
        children.append(
            Nested2Node(
                "Image",
                (
                    icon,
                    "icon",
                    {
                        "width": 16,
                        "height": 16,
                        "objectFit": "contain",
                        "fillColor": foreground,
                    },
                ),
                (),
            )
        )
    children.append(
        Nested2Node(
            "Text",
            (
                label,
                "compact-action",
                {"fontColor": foreground, "fontSize": 12, "fontWeight": 500},
            ),
            (),
        )
    )
    container = "Column" if orientation == "vertical" else "Row"
    inner_layout = "compact" if orientation == "vertical" else "actions"
    height: int | str = "100%" if orientation == "vertical" else 36
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "width": "100%",
                "height": height,
                "padding": 8,
                "borderRadius": 8,
                "backgroundColor": background,
                "alignContent": "center",
                "onClick": event,
            },
        ),
        (
            Nested2Node(
                container,
                (inner_layout, {"itemMargin": 4 if orientation == "vertical" else 8}),
                tuple(children),
            ),
        ),
    )


def _contains_key(value: Any, keys: frozenset[str]) -> bool:
    if isinstance(value, dict):
        return any(key in keys or _contains_key(child, keys) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_key(child, keys) for child in value)
    return False


def _validate_expanded_tree(root: Nested2Node, contract: HybridBodyContract) -> None:
    seen_assets: set[str] = set()
    visible_strings: list[str] = []

    def visit(node: Nested2Node, trusted_blueprint: bool = False) -> None:
        if node.component_type not in contract.allowed_components:
            raise TerselConversionError(
                f"Expanded component is not allowed: {node.component_type}"
            )
        if node.component_type in _CONTAINERS and not node.children:
            raise TerselConversionError(
                f"Expanded container must contain at least one child: {node.component_type}"
            )
        if node.component_type == "Image" and node.values:
            source = node.values[0]
            if source not in contract.allowed_asset_sources:
                raise TerselConversionError(f"Image source is not approved: {source}")
            seen_assets.add(str(source))
        if node.component_type == "Text" and node.values and isinstance(node.values[0], str):
            visible_strings.append(node.values[0])
        for child in node.children:
            visit(child, trusted_blueprint)

    visit(root)
    missing_assets = set(contract.required_asset_sources) - seen_assets
    if missing_assets:
        raise TerselConversionError(
            f"Required assets are missing: {sorted(missing_assets)}"
        )
    visible = "\n".join(visible_strings)
    visible_blob = "".join(_semantic_text_fragment(item) for item in visible_strings)
    missing_literals = [
        item
        for item in contract.required_literals
        if item not in visible and _semantic_text_fragment(item) not in visible_blob
    ]
    if missing_literals:
        raise TerselConversionError(
            f"Required literals are missing: {missing_literals[:3]}"
        )


def _count_calls(node: ParsedCall) -> int:
    return 1 + sum(_count_calls(child) for child in node.children)


def _parsed_template_shape_params(call: ParsedCall) -> tuple[str, dict[str, Any], bool]:
    if len(call.values) == 1 and isinstance(call.values[0], dict):
        return "default", call.values[0], True
    if (
        len(call.values) == 2
        and isinstance(call.values[0], str)
        and isinstance(call.values[1], dict)
    ):
        return call.values[0], call.values[1], False
    raise TerselConversionError(f"Template props are invalid: {call.name}")


def _normalize_template_provider_params(
    content: ParsedCall,
    _task_spec: TaskSpec,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> tuple[ParsedCall, int]:
    """Fill only missing asset params on an already selected trusted Template."""

    def visit(call: ParsedCall) -> tuple[ParsedCall, int]:
        children: list[ParsedCall] = []
        normalization_count = 0
        for child in call.children:
            normalized_child, child_count = visit(child)
            children.append(normalized_child)
            normalization_count += child_count
        if call.kind != "template" or call.name not in contract.allowed_template_ids:
            return (
                ParsedCall(call.kind, call.name, call.values, tuple(children), call.span),
                normalization_count,
            )
        size, raw_params, ui_syntax = _parsed_template_shape_params(call)
        params = dict(raw_params)
        definition = registry.require_template(call.name)
        try:
            variant = registry.require_variant(call.name, str(size))
        except ValueError:
            if len(definition.variants) != 1:
                return call, normalization_count
            variant = definition.variants[0]
        required = variant.parameters_schema.get("required", [])
        properties = variant.parameters_schema.get("properties", {})
        for parameter_name in required:
            if parameter_name in params or parameter_name not in properties:
                continue
            candidates: list[object]
            if parameter_name in definition.asset_parameter_semantic_tags:
                required_tags = set(definition.asset_parameter_semantic_tags[parameter_name])
                candidates = [
                    source
                    for source in contract.allowed_asset_sources
                    if required_tags.issubset(
                        contract.asset_semantic_tags_by_source.get(source, ())
                    )
                ]
            else:
                continue
            unique_candidates = list(dict.fromkeys(candidates))
            if len(unique_candidates) != 1:
                continue
            params[parameter_name] = unique_candidates[0]
            normalization_count += 1
        return (
            ParsedCall(
                call.kind,
                call.name,
                (params,) if ui_syntax else (size, params),
                tuple(children),
                call.span,
            ),
            normalization_count,
        )

    return visit(content)


def _normalize_template_relation_numbers(
    content: ParsedCall,
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> tuple[ParsedCall, int]:
    """Recover a missing numeric relation only from a unique trusted fact.

    This is Registry-driven and scenario-agnostic: the text side must already
    be trusted, the Template must declare ``number-matches-text``, and exactly
    one required number must satisfy the declared suffix relation.
    """
    children: list[ParsedCall] = []
    normalization_count = 0
    for child in content.children:
        normalized_child, child_count = _normalize_template_relation_numbers(
            child,
            contract,
            registry,
        )
        children.append(normalized_child)
        normalization_count += child_count
    if content.kind != "template":
        return (
            ParsedCall(
                content.kind,
                content.name,
                content.values,
                tuple(children),
                content.span,
            ),
            normalization_count,
        )

    size, raw_params, ui_syntax = _parsed_template_shape_params(content)
    params = dict(raw_params)
    if content.name not in contract.allowed_template_ids:
        return (
            ParsedCall(
                content.kind,
                content.name,
                content.values,
                tuple(children),
                content.span,
            ),
            normalization_count,
        )
    definition = registry.require_template(content.name)
    try:
        variant = registry.require_variant(content.name, str(size))
    except ValueError:
        if len(definition.variants) != 1:
            return content, normalization_count
        variant = definition.variants[0]
    required_numbers = tuple(
        number
        for number in contract.required_numbers
        if isinstance(number, (int, float)) and not isinstance(number, bool)
    )
    for relation in variant.parameter_relations:
        current = params.get(relation.number_parameter)
        text = params.get(relation.text_parameter)
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            continue
        if not isinstance(text, str) or text not in contract.trusted_literals:
            continue
        matches = {
            number
            for number in required_numbers
            if text in {_canonical_number(number) + suffix for suffix in relation.allowed_suffixes}
        }
        if len(matches) != 1:
            continue
        params[relation.number_parameter] = matches.pop()
        normalization_count += 1
    return (
        ParsedCall(
            content.kind,
            content.name,
            (params,) if ui_syntax else (size, params),
            tuple(children),
            content.span,
        ),
        normalization_count,
    )


def _canonical_number(number: int | float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _validate_required_numbers(
    content: ParsedCall,
    contract: HybridBodyContract,
    task_spec: TaskSpec,
) -> None:
    required = Counter(contract.required_numbers)
    if not required:
        return
    actual: Counter[int | float] = Counter()

    def visit(call: ParsedCall) -> None:
        if call.kind == "template":
            _size, params, _ui_syntax = _parsed_template_shape_params(call)
            actual.update(
                item
                for item in _primitive_values(params)
                if isinstance(item, (int, float)) and not isinstance(item, bool)
            )
        elif call.name == "Progress":
            for value in call.values:
                if not isinstance(value, dict):
                    continue
                progress_value = value.get("value")
                if isinstance(progress_value, (int, float)) and not isinstance(
                    progress_value, bool
                ):
                    actual[progress_value] += 1
        elif call.name == "ResourceUsageOverview":
            facts = extract_resource_usage_overview_facts(task_spec.dataModelSchema)
            if facts is not None:
                actual[facts.usage_percent] += 1
        elif call.name == "BatteryOverview":
            facts = extract_battery_overview_facts(task_spec.dataModelSchema)
            if facts is not None:
                actual[facts.level_percent] += 1
        elif call.name == "BluetoothDeviceOverview":
            facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
            if facts is not None:
                actual.update(
                    value
                    for value in (
                        facts.left_battery_level,
                        facts.right_battery_level,
                        facts.case_battery_level,
                    )
                    if value is not None
                )
        elif call.name == "ActivityOverview":
            facts = extract_activity_overview_facts(task_spec.dataModelSchema)
            if facts is not None:
                actual[facts.daily_steps] += 1
        elif call.name == "HeartRateOverview":
            facts = extract_heart_rate_overview_facts(task_spec.dataModelSchema)
            if facts is not None:
                actual[facts.average_bpm] += 1
        for child in call.children:
            visit(child)

    visit(content)
    missing = required - actual
    if missing:
        raise TerselConversionError(
            f"Hybrid content is missing required numeric facts: {list(missing.elements())}"
        )


def _normalize_recommended_variant_order(
    content: ParsedCall,
    registry: CardPlanRegistry,
) -> ParsedCall:
    """Apply Registry multi-size ordering without fixing any business layout."""
    children = tuple(
        _normalize_recommended_variant_order(child, registry) for child in content.children
    )
    if content.kind != "component" or len(children) < 2:
        return ParsedCall(content.kind, content.name, content.values, children, content.span)

    groups: dict[str, list[tuple[int, int]]] = {}
    for index, child in enumerate(children):
        calls = _descendant_template_variants(child)
        families = {wire_id for wire_id, _size in calls}
        if len(families) != 1:
            continue
        wire_id = next(iter(families))
        order = registry.require_template(wire_id).recommended_variant_order
        if not order:
            continue
        ranks = [order.index(size) for _wire_id, size in calls if size in order]
        if len(ranks) != len(calls):
            continue
        groups.setdefault(wire_id, []).append((index, min(ranks)))

    normalized = list(children)
    for units in groups.values():
        if len(units) < 2:
            continue
        positions = [index for index, _rank in units]
        ordered = [
            children[index] for index, _rank in sorted(units, key=lambda item: (item[1], item[0]))
        ]
        for position, child in zip(positions, ordered, strict=True):
            normalized[position] = child
    return ParsedCall(
        content.kind,
        content.name,
        content.values,
        tuple(normalized),
        content.span,
    )


def _descendant_template_variants(content: ParsedCall) -> list[tuple[str, str]]:
    if content.kind == "template":
        size = content.values[0]
        return [(content.name, str(size))]
    return [item for child in content.children for item in _descendant_template_variants(child)]


def _shape(node: Nested2Node) -> tuple[int, int]:
    if not node.children:
        return 1, 1
    child_shapes = [_shape(child) for child in node.children]
    return 1 + sum(item[0] for item in child_shapes), 1 + max(item[1] for item in child_shapes)


def _body_budget(
    params: dict[str, Any],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
) -> int:
    theme = registry.require_theme(contract.theme_profile_id)
    padding = (
        registry.ux_tokens["safeInset"]
        if contract.allowed_layout_component_ids
        else theme.root_style.get("padding", 12)
    )
    if isinstance(padding, (int, float)):
        vertical_padding = int(padding) * 2
    elif isinstance(padding, dict):
        top = padding.get("top", 0)
        bottom = padding.get("bottom", 0)
        vertical_padding = int(top if isinstance(top, (int, float)) else 0) + int(
            bottom if isinstance(bottom, (int, float)) else 0
        )
    else:
        vertical_padding = 24
    if "title" in params and "subtitle" in params:
        header = 34
    else:
        header = 18 if any(key in params for key in ("title", "subtitle", "titleIcon")) else 0
    action = (
        registry.ux_tokens["pillActionHeight"]
        if "action" in params and contract.allowed_layout_component_ids
        else 30
        if "action" in params
        else 0
    )
    chrome_count = int(header > 0) + int(action > 0)
    root_gap = 8 * chrome_count
    return max(24, 160 - vertical_padding - header - action - root_gap)


def _ux_layout_body_budget(registry: CardPlanRegistry) -> int:
    return 160 - registry.ux_tokens["safeInset"] * 2


def _estimate_height(node: Nested2Node) -> int:
    options = next((value for value in node.values if isinstance(value, dict)), {})
    explicit = options.get("height")
    if isinstance(explicit, (int, float)):
        return int(explicit)
    child_heights = [_estimate_height(child) for child in node.children]
    if node.component_type in {"Row", "Stack"}:
        return max(child_heights, default=24)
    if node.component_type in {"Column", "List"}:
        margin = options.get("itemMargin", options.get("space", 4))
        margin_value = margin if isinstance(margin, int) else 4
        margin_total = max(0, len(child_heights) - 1) * margin_value
        return sum(child_heights) + margin_total
    return {"Text": 20, "Image": 24, "Progress": 40, "Button": 32}.get(node.component_type, 20)


def _constrain_content_height(node: Nested2Node, budget: int) -> Nested2Node:
    values = list(node.values)
    options_index = next(
        (index for index, value in enumerate(values) if isinstance(value, dict)),
        None,
    )
    options = dict(values[options_index]) if options_index is not None else {}
    options["height"] = budget
    options["clip"] = True
    if options_index is None:
        values.append(options)
    else:
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), node.children)


def _normalize_component_values(
    component: str,
    values: tuple[Any, ...],
) -> tuple[Any, ...]:
    normalized = values
    if values and isinstance(values[0], dict):
        first = dict(values[0])
        layout = first.pop("layout", None)
        if isinstance(layout, str):
            remainder = (first,) if first else ()
            normalized = (layout, *remainder, *values[1:])
    if normalized and isinstance(normalized[0], str):
        alias = _LAYOUT_ALIASES.get((component, normalized[0]))
        if alias is not None:
            return (alias, *normalized[1:])
    if len(normalized) > 1 and isinstance(normalized[1], str):
        alias = _DESIGN_ALIASES.get((component, normalized[1]))
        if alias is not None:
            return (normalized[0], alias, *normalized[2:])
    return normalized


def _compact_text_roles(node: Nested2Node) -> Nested2Node:
    children = tuple(_compact_text_roles(child) for child in node.children)
    if node.component_type != "Text":
        return Nested2Node(node.component_type, node.values, children)
    values = list(node.values)
    if len(values) > 1 and values[1] == "title":
        values[1] = "compact-title"
    return Nested2Node(node.component_type, tuple(values), children)


def _normalize_theme_styles(styles: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in styles.items():
        if isinstance(value, str):
            match = _COLOR_MODE_LITERAL.fullmatch(value)
            normalized[key] = match.group(2) if match is not None else value
        else:
            normalized[key] = value
    return normalized


def _column_align_items(value: Any) -> Any:
    """Map a Stack two-dimensional alignment to Column's horizontal axis."""
    if not isinstance(value, str):
        return value
    if value.endswith("Start"):
        return "start"
    if value.endswith("End"):
        return "end"
    if value in {"top", "center", "bottom"}:
        return "center"
    return value


def _serialize_effective_document(
    root: Nested2Node,
    task_spec: TaskSpec,
    enable_data_bindings: bool,
) -> str:
    component_tree = _serialize_node(root) + ";"
    if not enable_data_bindings:
        return component_tree
    data = serialize_task_spec_data(task_spec.model_dump(mode="json"))
    return f"{component_tree}\ndata = {data}"


def _serialize_node(node: Nested2Node) -> str:
    arguments = [_serialize_value(value) for value in node.values]
    arguments.extend(_serialize_node(child) for child in node.children)
    return f"{node.component_type}({', '.join(arguments)})"


def _serialize_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
