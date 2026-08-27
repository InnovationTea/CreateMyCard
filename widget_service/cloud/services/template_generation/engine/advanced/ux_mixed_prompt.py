"""第二层高级组件与基础组件混合生成 Prompt。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.generated.prompts import (
    UX_MIXED_SYSTEM_PROMPT_KERNEL,
)
from services.template_generation.engine.cardplan.models import (
    BusinessTemplateGroup,
    Fact,
    HybridBodyContract,
)
from services.template_generation.engine.cardplan.prompt import (
    build_hybrid_prompt,
    build_template_prompt_contracts,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

from .content_selectors import (
    extract_app_usage_overview_facts,
    extract_bluetooth_device_overview_facts,
    extract_heart_rate_overview_facts,
    extract_schedule_overview_facts,
    extract_sleep_overview_facts,
    extract_weather_overview_facts,
)
from .models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
)
from .scope_planner import (
    resolve_scope_layout_ids,
    scope_template_ids,
    task_spec_with_selected_action,
)

_WEATHER_BUILTIN_ASSETS = (
    "resources/base/media/icon_weather1.svg",
    "resources/base/media/sun_max.svg",
    "resources/base/media/cold.svg",
)
_MAX_UX_MIXED_PROMPT_CHARS = 24_000
_UX_ACTION_TEMPLATE_ID = "PillAction@1"


def _weather_builtin_assets_for_components(components: tuple[Any, ...]) -> tuple[str, ...]:
    has_direct_weather = any(
        component.name == "WeatherOverview" and component.implementation == "terse-dsl"
        for component in components
    )
    return _WEATHER_BUILTIN_ASSETS if has_direct_weather else ()


class _ScopePromptBridge(BaseModel):
    """仅把新 Scope 投影给现有可信 Contract 构造器，不触发旧 UI Planner。"""

    model_config = ConfigDict(frozen=True)

    theme_id: str
    local_template_ids: tuple[str, ...]
    action_placement: str = "content"
    primary_domain: str
    adaptive_template_id: None = None
    advanced_component_ids: tuple[str, ...]
    disable_template_fallback: bool = True


@dataclass(frozen=True)
class UxMixedPromptProjection:
    messages: list[dict[str, str]]
    contract: HybridBodyContract
    facts: tuple[Fact, ...]
    requested_template_ids: tuple[str, ...]
    allowed_layout_ids: tuple[str, ...]
    theme_id: str


def build_ux_mixed_validation_retry_prompt(
    messages: list[dict[str, str]],
    raw_output: str,
    error: ValueError,
) -> list[dict[str, str]]:
    """Ask only the second layer to regenerate after strict contract rejection."""
    return [
        *messages,
        {"role": "assistant", "content": raw_output},
        {
            "role": "user",
            "content": (
                "上一输出未通过服务端严格契约校验："
                f"{error}。严格使用原动态契约，重新输出完整调用树。"
                "输出必须以 Template( 开头并以 ); 结束；"
                "所有 Template 都必须是不含关键字参数的直接位置调用。"
                "禁止变量赋值、return、props=、children=、对象方法、"
                "数组 children、Markdown 或解释。"
                "每个 requiredLocalTemplateGroups 恰好选择一个业务 Template；"
                "不得新增基础组件、业务文本、Action 或候选外 Template。"
                "只输出类 Tersel 调用树，不要解释。"
            ),
        },
    ]


def build_ux_mixed_prompt(
    *,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    scope: AdvancedScopeBrief,
    component_candidates: tuple[TemplateComponentCandidate, ...],
    required_template_groups: tuple[tuple[str, ...], ...] = (),
    registry: CardPlanRegistry,
) -> UxMixedPromptProjection:
    """复用事实、Action 和 Template 安全契约，替换旧候选与布局决策入口。"""
    components = tuple(
        registry.require_ux_business_component(item) for item in scope.advanced_component_ids
    )
    requested_candidate_ids = {
        candidate.component_id: candidate.available_template_ids
        for candidate in component_candidates
    }
    if tuple(requested_candidate_ids) != scope.advanced_component_ids:
        raise ValueError("Template candidates do not match Advanced Scope")
    preferred_template_ids = tuple(
        template_id
        for template_ids in requested_candidate_ids.values()
        for template_id in template_ids
    )
    satisfiable_template_ids = set(
        scope_template_ids(
            scope,
            registry,
            task_spec,
            preferred_template_ids=preferred_template_ids,
        )
    )
    candidate_ids_by_component = {
        component_id: tuple(
            template_id
            for template_id in template_ids
            if template_id in satisfiable_template_ids
        )
        for component_id, template_ids in requested_candidate_ids.items()
    }
    if any(not template_ids for template_ids in candidate_ids_by_component.values()):
        raise ValueError("Advanced Scope component has no satisfiable candidate Template")
    selected_action_ids = tuple(
        event.id for event in task_spec.eventCandidates if event.id is not None
    )
    task_spec = task_spec_with_selected_action(task_spec, selected_action_ids)
    allowed_layout_ids, layout_kind = _second_layer_layout_selection(
        scope,
        task_spec,
        required_template_groups,
        registry,
    )
    candidate_ids_by_component, effective_required_template_groups = (
        _filter_second_layer_template_candidates(
            candidate_ids_by_component,
            required_template_groups,
            layout_kind,
        )
    )
    selected_template_ids = tuple(
        template_id
        for component_id in scope.advanced_component_ids
        for template_id in candidate_ids_by_component[component_id]
    )
    allowed_layout_template_ids = tuple(f"{layout_id}@1" for layout_id in allowed_layout_ids)
    for template_id in allowed_layout_template_ids:
        definition = registry.require_template(template_id)
        if not definition.accepts_children or definition.provider_id != "com.huawei.layout.cli":
            raise ValueError(f"UX Layout Template contract is invalid: {template_id}")
    bridge = _ScopePromptBridge(
        theme_id=scope.theme_id,
        local_template_ids=selected_template_ids,
        primary_domain=components[0].domain_id,
        advanced_component_ids=scope.advanced_component_ids,
    )
    base = build_hybrid_prompt(
        task_spec=task_spec,
        card_spec=card_spec,
        ui_brief=bridge,
        registry=registry,
        ux_layout_root_ids=allowed_layout_ids,
        expose_data_facts=False,
    )
    template_components = tuple(
        component for component in components if component.implementation == "template"
    )
    direct_components = tuple(
        component.name for component in components if component.implementation == "terse-dsl"
    )
    has_weather = any(component.name == "WeatherOverview" for component in components)
    weather_builtin_assets = _weather_builtin_assets_for_components(components)
    has_heart_rate = any(component.name == "HeartRateOverview" for component in components)
    effective_required_template_groups = tuple(
        _required_template_group(group, base.requested_template_ids)
        for group in effective_required_template_groups
    )
    if any(not group for group in effective_required_template_groups):
        raise ValueError("An explicit output field has no satisfiable candidate Template")
    allowed_assets = tuple(
        dict.fromkeys(
            (
                *base.contract.allowed_asset_sources,
                *weather_builtin_assets,
            )
        )
    )
    asset_tags = dict(base.contract.asset_semantic_tags_by_source)
    if weather_builtin_assets:
        asset_tags.update(
            {
                _WEATHER_BUILTIN_ASSETS[0]: ("weather", "condition", "rain"),
                _WEATHER_BUILTIN_ASSETS[1]: ("weather", "condition", "sun"),
                _WEATHER_BUILTIN_ASSETS[2]: ("weather", "condition", "cold", "snow"),
            }
        )
    required_literals = base.contract.required_literals
    protected_literals = base.contract.protected_literals
    required_numbers = base.contract.required_numbers
    if has_weather:
        weather_facts = extract_weather_overview_facts(task_spec.dataModelSchema)
        if weather_facts is not None:
            server_owned_weather_literals = {
                weather_facts.city,
                weather_facts.temperature,
                weather_facts.condition,
                weather_facts.air_quality,
                weather_facts.cold_level,
                weather_facts.temperature_range,
            }
            server_owned_weather_literals.discard("")
            required_literals = tuple(
                item for item in required_literals if item not in server_owned_weather_literals
            )
            protected_literals = tuple(
                item for item in protected_literals if item not in server_owned_weather_literals
            )
    if has_heart_rate:
        heart_rate_facts = extract_heart_rate_overview_facts(task_spec.dataModelSchema)
        if heart_rate_facts is None:
            raise ValueError("HeartRateOverview has no trusted positive average heart rate")
        required_numbers = tuple(
            item for item in required_numbers if item != heart_rate_facts.average_bpm
        )
        if heart_rate_facts.updated_at is not None:
            required_literals = tuple(
                item for item in required_literals if item != heart_rate_facts.updated_at
            )
            protected_literals = tuple(
                item for item in protected_literals if item != heart_rate_facts.updated_at
            )
    calendar_component_ids = {"CalendarOverview", "ScheduleOverview"}
    if calendar_component_ids.intersection(scope.advanced_component_ids):
        schedule_facts = extract_schedule_overview_facts(task_spec.dataModelSchema)
        optional_literals = {
            schedule_facts.location
            if schedule_facts is not None and schedule_facts.location is not None
            else ""
        }
        required_literals = tuple(
            item for item in required_literals if item not in optional_literals
        )
        protected_literals = tuple(
            item for item in protected_literals if item not in optional_literals
        )
    if "AppUsageOverview" in direct_components:
        app_usage_facts = extract_app_usage_overview_facts(task_spec.dataModelSchema)
        if app_usage_facts is None:
            raise ValueError("AppUsageOverview has no complete trusted single-app facts")
        required_literals = tuple(
            item for item in required_literals if item != app_usage_facts.duration_text
        )
        protected_literals = tuple(
            item for item in protected_literals if item != app_usage_facts.duration_text
        )
    if "SleepOverview" in direct_components:
        sleep_facts = extract_sleep_overview_facts(task_spec.dataModelSchema)
        if sleep_facts is None:
            raise ValueError("SleepOverview has no losslessly renderable night duration")
        server_owned_sleep_literals = {
            sleep_facts.duration_text,
            sleep_facts.status,
            sleep_facts.fall_asleep_time,
            sleep_facts.wakeup_time,
        }
        required_literals = tuple(
            item for item in required_literals if item not in server_owned_sleep_literals
        )
        protected_literals = tuple(
            item for item in protected_literals if item not in server_owned_sleep_literals
        )
    if "BluetoothDeviceOverview" in direct_components:
        bluetooth_facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
        if bluetooth_facts is None:
            raise ValueError("BluetoothDeviceOverview has no compatible trusted earphone facts")
        server_owned_bluetooth_literals = {bluetooth_facts.earphone_name}
        required_literals = tuple(
            item for item in required_literals if item not in server_owned_bluetooth_literals
        )
        protected_literals = tuple(
            item for item in protected_literals if item not in server_owned_bluetooth_literals
        )
    provider_owned_values = set(
        _provider_component_server_owned_values(
            task_spec,
            card_spec,
            template_components,
            registry,
            set(selected_template_ids),
        )
    )
    required_literals = tuple(
        item for item in required_literals if item not in provider_owned_values
    )
    protected_literals = tuple(
        item for item in protected_literals if item not in provider_owned_values
    )
    required_numbers = tuple(item for item in required_numbers if item not in provider_owned_values)
    contract = base.contract.model_copy(
        update={
            "required_template_groups": effective_required_template_groups,
            "allowed_template_ids": tuple(
                dict.fromkeys(
                    (*base.contract.allowed_template_ids, *allowed_layout_template_ids)
                )
            ),
            "allowed_components": tuple(
                dict.fromkeys((*base.contract.allowed_components, *direct_components))
            ),
            "allowed_business_component_ids": direct_components,
            "required_business_component_ids": direct_components,
            "template_only_composition": True,
            "allowed_asset_sources": allowed_assets,
            "asset_semantic_tags_by_source": asset_tags,
            "required_literals": required_literals,
            "required_numbers": required_numbers,
            "protected_literals": protected_literals,
        }
    )
    business_template_contracts = build_template_prompt_contracts(
        selected_template_ids,
        contract,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=True,
    )
    available_business_template_ids = tuple(
        item["templateId"] for item in business_template_contracts
    )
    available_business_ids = set(available_business_template_ids)
    candidate_ids_by_component = {
        component_id: tuple(
            template_id
            for template_id in template_ids
            if template_id in available_business_ids
        )
        for component_id, template_ids in candidate_ids_by_component.items()
    }
    if any(not template_ids for template_ids in candidate_ids_by_component.values()):
        raise ValueError("Second-layer component has no complete Template signature")
    effective_required_template_groups = tuple(
        tuple(
            template_id
            for template_id in group
            if template_id in available_business_ids
        )
        for group in effective_required_template_groups
    )
    if any(not group for group in effective_required_template_groups):
        raise ValueError("Second-layer required Template group has no complete signature")
    effective_component_candidates = tuple(
        TemplateComponentCandidate(
            componentId=component_id,
            availableTemplateIds=template_ids,
        )
        for component_id, template_ids in candidate_ids_by_component.items()
    )
    action_template_ids = (
        (_UX_ACTION_TEMPLATE_ID,) if selected_action_ids else ()
    )
    action_template_contracts = build_template_prompt_contracts(
        action_template_ids,
        contract,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=True,
    )
    layout_template_contracts = build_template_prompt_contracts(
        allowed_layout_template_ids,
        contract,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=True,
    )
    layout_contracts = _layout_prompt_contracts(
        layout_template_contracts,
        allowed_layout_ids,
        task_spec,
        registry,
    )
    allowed_template_ids = tuple(
        dict.fromkeys(
            (
                *available_business_template_ids,
                *action_template_ids,
                *allowed_layout_template_ids,
            )
        )
    )
    contract = contract.model_copy(
        update={
            "required_template_groups": effective_required_template_groups,
            "allowed_template_ids": allowed_template_ids,
        }
    )
    provider_second_layer_rules = registry.provider_second_layer_guidance(
        scope.advanced_component_ids
    )
    selected_actions = _selected_action_candidates(contract)
    asset_candidates = _asset_prompt_candidates(task_spec, contract)
    user = "\n".join(
        (
            "themeId=" + json.dumps(base.theme_id, ensure_ascii=False),
            "trustedStringLiterals=" + json.dumps(contract.trusted_literals, ensure_ascii=False),
            "trustedAssetSources=" + json.dumps(contract.allowed_asset_sources, ensure_ascii=False),
            "trustedAssetCandidates=" + json.dumps(asset_candidates, ensure_ascii=False),
            "componentCandidates="
            + json.dumps(
                [
                    candidate.model_dump(by_alias=True)
                    for candidate in effective_component_candidates
                ],
                ensure_ascii=False,
            ),
            "templateContracts="
            + json.dumps(business_template_contracts, ensure_ascii=False),
            "allowedUxLayouts=" + json.dumps(allowed_layout_ids, ensure_ascii=False),
            "layoutContracts=" + json.dumps(layout_contracts, ensure_ascii=False),
            "requiredLocalTemplateGroups="
            + json.dumps(effective_required_template_groups, ensure_ascii=False),
            "directBusinessComponents=" + json.dumps(direct_components, ensure_ascii=False),
            "selectedActionCandidates=" + json.dumps(selected_actions, ensure_ascii=False),
            "selectedActionEventIds=" + json.dumps(selected_action_ids, ensure_ascii=False),
            "actionContracts="
            + json.dumps(action_template_contracts, ensure_ascii=False),
            "providerSecondLayerRules="
            + json.dumps(provider_second_layer_rules, ensure_ascii=False),
            "outputGrammar="
            + json.dumps(
                _output_grammar(
                    allowed_layout_template_ids[0],
                    effective_required_template_groups,
                    selected_actions,
                ),
                ensure_ascii=False,
            ),
            "第一层已完成展示覆盖。从每个 requiredLocalTemplateGroups 恰好选择一个"
            " Template，按完整签名设置 Props，并严格使用唯一布局根。",
            "只输出一棵以分号结束的类 Tersel Template 调用树，不输出说明。",
        )
    )
    messages = [
        {"role": "system", "content": UX_MIXED_SYSTEM_PROMPT_KERNEL},
        {"role": "user", "content": user},
    ]
    if sum(len(item["content"]) for item in messages) > _MAX_UX_MIXED_PROMPT_CHARS:
        raise ValueError("UX Mixed Prompt exceeds the service input budget")
    return UxMixedPromptProjection(
        messages=messages,
        contract=contract,
        facts=base.facts,
        requested_template_ids=allowed_template_ids,
        allowed_layout_ids=allowed_layout_ids,
        theme_id=base.theme_id,
    )


def _layout_prompt_contracts(
    template_contracts: tuple[dict[str, Any], ...],
    allowed_layout_ids: tuple[str, ...],
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[dict[str, Any], ...]:
    contracts_by_id = {
        item["templateId"]: item for item in template_contracts
    }
    result: list[dict[str, Any]] = []
    for layout_id in allowed_layout_ids:
        template_id = f"{layout_id}@1"
        template_contract = contracts_by_id.get(template_id)
        if template_contract is None:
            raise ValueError(f"UX Layout has no complete Template signature: {template_id}")
        layout = registry.require_ux_layout_component(layout_id)
        result.append(
            {
                **template_contract,
                "businessChildren": {
                    "minimum": layout.minimum_children(task_spec.size),
                    "maximum": layout.max_children_by_size[task_spec.size],
                },
                "actionChildren": {
                    "minimum": layout.min_action_children_by_size[task_spec.size],
                    "maximum": layout.max_action_children_by_size[task_spec.size],
                    "placement": "contiguous trailing direct children",
                },
                "callSyntax": f'Template("{template_id}", props, ...children)',
            }
        )
    return tuple(result)


def _selected_action_candidates(
    contract: HybridBodyContract,
) -> tuple[dict[str, str], ...]:
    selected_ids = set(contract.content_action_ids)
    return tuple(
        {
            "actionId": action.action_id,
            "label": action.display_label,
        }
        for action in contract.action_bindings
        if action.action_id in selected_ids
    )


def _asset_prompt_candidates(
    task_spec: TaskSpec,
    contract: HybridBodyContract,
) -> tuple[dict[str, Any], ...]:
    requested_by_source = {
        str(item["src"]): item
        for item in task_spec.assetCandidates
        if isinstance(item, dict) and isinstance(item.get("src"), str)
    }
    return tuple(
        {
            "src": source,
            "id": requested_by_source.get(source, {}).get("id"),
            "description": requested_by_source.get(source, {}).get("description", ""),
            "semanticTags": contract.asset_semantic_tags_by_source.get(source, ()),
        }
        for source in contract.allowed_asset_sources
    )


def _output_grammar(
    layout_template_id: str,
    required_template_groups: tuple[tuple[str, ...], ...],
    selected_actions: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    business_children = [
        {
            "position": index,
            "templateIds": template_ids,
            "syntax": 'Template("<one templateId from templateIds>", <matching props>)',
        }
        for index, template_ids in enumerate(required_template_groups)
    ]
    action_children = [
        {
            "position": len(required_template_groups) + index,
            "templateId": _UX_ACTION_TEMPLATE_ID,
            "syntax": (
                f'Template("{_UX_ACTION_TEMPLATE_ID}",'
                + json.dumps(action, ensure_ascii=False, separators=(",", ":"))
                + ")"
            ),
        }
        for index, action in enumerate(selected_actions)
    ]
    return {
        "root": f'Template("{layout_template_id}", {{}}, ...children);',
        "businessChildren": business_children,
        "actionChildren": action_children,
        "childOrder": "businessChildren first, then actionChildren",
    }


def _calendar_date_schedule_pair_is_required(
    scope: AdvancedScopeBrief,
    required_template_groups: tuple[tuple[str, ...], ...],
) -> bool:
    if scope.advanced_component_ids != ("CalendarOverview",):
        return False
    candidate_ids = {
        template_id
        for group in required_template_groups
        for template_id in group
    }
    has_date = any(template_id.startswith("DateOverview") for template_id in candidate_ids)
    has_schedule = any(
        template_id.startswith("ScheduleOverview") for template_id in candidate_ids
    )
    return has_date and has_schedule


def _second_layer_layout_selection(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    required_template_groups: tuple[tuple[str, ...], ...],
    registry: CardPlanRegistry,
) -> tuple[tuple[str, ...], str]:
    """Resolve only layout capacity and Action shape in the second layer."""
    action_count = len(task_spec.eventCandidates)
    component_count = len(scope.advanced_component_ids)
    calendar_pair = _calendar_date_schedule_pair_is_required(
        scope,
        required_template_groups,
    )
    if calendar_pair:
        if action_count:
            raise ValueError("Calendar date-schedule Compact pair cannot include an Action")
        expected_layout = "TwoCompactLayout"
        layout_kind = "Compact"
    elif task_spec.size == "2x2":
        layout_policy = {
            (1, 0): ("SingleFocusLayout", "Full"),
            (1, 1): ("HeroActionLayout", "Hero"),
            (1, 2): ("CompactTwoActionLayout", "Compact"),
            (2, 0): ("TwoCompactLayout", "Compact"),
        }
        selected = layout_policy.get((component_count, action_count))
        if selected is None:
            raise ValueError("2x2 Template candidates do not fit one supported layout")
        expected_layout, layout_kind = selected
    elif task_spec.size == "2x4" and component_count == 1 and action_count <= 1:
        expected_layout = "WideSingleFocusLayout"
        layout_kind = "WideHero" if action_count else "WideFull"
    else:
        raise ValueError("Template candidates do not fit one supported layout")
    allowed_layout_ids = resolve_scope_layout_ids(scope, task_spec, registry)
    if expected_layout not in allowed_layout_ids:
        raise ValueError("Advanced Scope has no compatible UX layout")
    return (expected_layout,), layout_kind


def _filter_second_layer_template_candidates(
    candidates_by_component: dict[str, tuple[str, ...]],
    required_template_groups: tuple[tuple[str, ...], ...],
    layout_kind: str,
) -> tuple[dict[str, tuple[str, ...]], tuple[tuple[str, ...], ...]]:
    """Filter first-layer candidates by layout without inspecting business data."""
    filtered = {
        component_id: tuple(
            template_id
            for template_id in template_ids
            if provider_template_layout_kind(template_id) == layout_kind
        )
        for component_id, template_ids in candidates_by_component.items()
    }
    for component_id, template_ids in filtered.items():
        if not template_ids:
            raise ValueError(
                f"Advanced Scope component {component_id} has no {layout_kind} template"
            )
    allowed_ids = {
        template_id
        for template_ids in filtered.values()
        for template_id in template_ids
    }
    groups = required_template_groups or tuple(filtered.values())
    filtered_groups = tuple(
        tuple(template_id for template_id in group if template_id in allowed_ids)
        for group in groups
    )
    if any(not group for group in filtered_groups):
        raise ValueError(
            f"First-layer Template candidates have no complete {layout_kind} coverage"
        )
    return filtered, filtered_groups


def _required_template_group(
    component_template_ids: tuple[str, ...],
    requested_template_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Prefer the current UX generation when compatibility Templates coexist."""
    eligible = tuple(
        template_id
        for template_id in component_template_ids
        if template_id in requested_template_ids
    )
    current = tuple(template_id for template_id in eligible if template_id.endswith("@2"))
    return current or eligible


def _provider_component_server_owned_values(
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    components: tuple[BusinessTemplateGroup, ...],
    registry: CardPlanRegistry,
    allowed_template_ids: set[str],
) -> tuple[str | int | float, ...]:
    values: list[str | int | float] = []
    for component in components:
        definitions = []
        for template_id in component.local_template_ids:
            if template_id not in allowed_template_ids:
                continue
            definition = registry.require_template(template_id)
            if definition.source_format == "cardtpl/1":
                definitions.append(definition)
        if not definitions:
            continue
        for subtree in _schema_values_for_key(task_spec.dataModelSchema, component.name):
            values.extend(_schema_sample_values(subtree))
        for definition in definitions:
            if not definition.capability_id:
                continue
            root = _card_spec_data_root(card_spec, definition.capability_id)
            if root is None:
                continue
            for binding in definition.bindings.values():
                leaf = _schema_pointer_value(
                    task_spec.dataModelSchema,
                    f"{root.rstrip('/')}{binding.path}",
                )
                values.extend(_schema_sample_values(leaf))
    return tuple(dict.fromkeys(values))


def _card_spec_data_root(card_spec: dict[str, Any], capability_id: str) -> str | None:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return None
    roots = {
        item.get("writeResultTo")
        for item in bindings
        if isinstance(item, dict)
        and item.get("capabilityId") == capability_id
        and isinstance(item.get("writeResultTo"), str)
    }
    return next(iter(roots)) if len(roots) == 1 else None


def _schema_values_for_key(value: Any, key: str) -> tuple[Any, ...]:
    matches: list[Any] = []
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                matches.append(child)
            matches.extend(_schema_values_for_key(child, key))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_schema_values_for_key(child, key))
    return tuple(matches)


def _schema_pointer_value(value: Any, pointer: str) -> Any | None:
    current = value
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
    return current


def _schema_sample_values(value: Any) -> list[str | int | float]:
    values: list[str | int | float] = []
    if isinstance(value, dict):
        sample = value.get("sampleValue")
        if isinstance(sample, (str, int, float)) and not isinstance(sample, bool):
            values.append(sample)
        for child in value.values():
            values.extend(_schema_sample_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_schema_sample_values(child))
    return values
