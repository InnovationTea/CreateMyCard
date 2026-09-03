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
_PILL_ACTION_TEMPLATE_ID = "PillAction@1"
_ICON_ACTION_TEMPLATE_ID = "IconAction@1"


@dataclass(frozen=True)
class _SecondLayerLayoutSelection:
    layout_ids: tuple[str, ...]
    layout_kinds: tuple[str, ...]
    action_template_ids: tuple[str, ...] = ()
    embeds_support_actions: bool = False
    business_layout_kinds_by_position: tuple[str, ...] = ()


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
    layout_selection = _second_layer_layout_selection(
        scope,
        task_spec,
        registry,
    )
    if layout_selection.business_layout_kinds_by_position:
        (
            candidate_ids_by_component,
            effective_required_template_groups,
        ) = _filter_positional_second_layer_template_candidates(
            candidate_ids_by_component,
            required_template_groups,
            layout_selection.business_layout_kinds_by_position,
        )
    else:
        (
            candidate_ids_by_component,
            effective_required_template_groups,
            viable_layout_kinds,
        ) = _filter_second_layer_template_candidates(
            candidate_ids_by_component,
            required_template_groups,
            layout_selection.layout_kinds,
        )
        layout_selection = _prune_layout_selection(
            layout_selection,
            viable_layout_kinds,
        )
    allowed_layout_ids = layout_selection.layout_ids
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
    theme_id = registry.hero_content_theme_id(selected_template_ids, scope.theme_id)
    primary_component = components[1] if theme_id is not None else components[0]
    bridge = _ScopePromptBridge(
        theme_id=theme_id or scope.theme_id,
        local_template_ids=selected_template_ids,
        primary_domain=primary_component.domain_id,
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
        server_owned_bluetooth_literals: set[str] = set()
        bluetooth_literals = (
            bluetooth_facts.earphone_name,
            bluetooth_facts.case_charging_status,
        )
        for value in bluetooth_literals:
            if value is not None:
                server_owned_bluetooth_literals.add(value)
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
        layout_selection.action_template_ids if selected_action_ids else ()
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
                    allowed_layout_template_ids,
                    effective_required_template_groups,
                    selected_actions,
                    action_template_ids,
                    embeds_support_actions=layout_selection.embeds_support_actions,
                ),
                ensure_ascii=False,
            ),
            "第一层已完成展示覆盖。从每个 requiredLocalTemplateGroups 恰好选择一个"
            " Template，按完整签名设置 Props，并使用一个与业务后缀及动作形态匹配的布局根。",
            "HeroTitleContentActionLayout 的三个直接 children 必须严格按 HeroTitle、"
            "HeroContent、PillAction 排列。全局主题已按主业务 HeroContent 确定，"
            "标题与动作继承同一主题；融球背景由服务端按版本门禁统一展开，不由模型生成。",
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
                **(
                    {
                        "businessChildLayoutKindsByPosition": [
                            "HeroTitle",
                            "HeroContent",
                        ]
                    }
                    if layout_id == "HeroTitleContentActionLayout"
                    else {}
                ),
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
    layout_template_ids: tuple[str, ...],
    required_template_groups: tuple[tuple[str, ...], ...],
    selected_actions: tuple[dict[str, str], ...],
    action_template_ids: tuple[str, ...],
    *,
    embeds_support_actions: bool,
) -> dict[str, Any]:
    business_children = [
        {
            "position": index,
            "templateIds": template_ids,
            "syntax": 'Template("<one templateId from templateIds>", <matching props>)',
            **(
                {
                    "embeddedAction": {
                        "optionalProp": "actionId",
                        "allowedValues": selected_actions,
                    }
                }
                if embeds_support_actions
                else {}
            ),
        }
        for index, template_ids in enumerate(required_template_groups)
    ]
    layout_options = [
        _layout_output_option(
            layout_template_id,
            required_template_groups,
            selected_actions,
            action_template_ids,
        )
        for layout_template_id in layout_template_ids
    ]
    return {
        "layoutOptions": layout_options,
        "businessChildren": business_children,
        "childOrder": (
            "Support businessChildren only; selected actions appear once in Support actionId props"
            if embeds_support_actions
            else (
                "position 0 HeroTitle, position 1 HeroContent, position 2 PillAction"
                if "HeroTitleContentActionLayout@1" in layout_template_ids
                else "businessChildren first, then actionChildren"
            )
        ),
    }


def _layout_output_option(
    layout_template_id: str,
    required_template_groups: tuple[tuple[str, ...], ...],
    selected_actions: tuple[dict[str, str], ...],
    action_template_ids: tuple[str, ...],
) -> dict[str, Any]:
    layout_id = layout_template_id.removesuffix("@1")
    layout_kind: str | tuple[str, ...] = {
        "SingleFocusLayout": "Full",
        "HeroActionLayout": "Hero",
        "FullIconActionLayout": "Full",
        "CompactTwoActionLayout": "Compact",
        "HeroTitleContentActionLayout": ("HeroTitle", "HeroContent"),
        "TwoSupportLayout": "Support",
        "WideSingleFocusLayout": "WideHero" if selected_actions else "WideFull",
    }[layout_id]
    if isinstance(layout_kind, tuple):
        business_template_ids = tuple(
            tuple(
                template_id
                for template_id in group
                if provider_template_layout_kind(template_id) == layout_kind[index]
            )
            for index, group in enumerate(required_template_groups)
        )
        layout_kind_label = "+".join(layout_kind)
    else:
        business_template_ids = tuple(
            tuple(
                template_id
                for template_id in group
                if provider_template_layout_kind(template_id) == layout_kind
            )
            for group in required_template_groups
        )
        layout_kind_label = layout_kind
    action_template_id = {
        "HeroActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "FullIconActionLayout": _ICON_ACTION_TEMPLATE_ID,
        "CompactTwoActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "HeroTitleContentActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideSingleFocusLayout": _PILL_ACTION_TEMPLATE_ID if selected_actions else None,
    }.get(layout_id)
    if action_template_id not in action_template_ids:
        action_template_id = None
    action_children = [
        {
            "position": len(required_template_groups) + index,
            "templateId": action_template_id,
            "syntax": _action_output_syntax(action_template_id, action),
        }
        for index, action in enumerate(selected_actions)
        if action_template_id is not None
    ]
    return {
        "root": f'Template("{layout_template_id}", {{}}, ...children);',
        "layoutKind": layout_kind_label,
        "businessTemplateIdsByPosition": business_template_ids,
        "actionChildren": action_children,
    }


def _action_output_syntax(
    action_template_id: str,
    action: dict[str, str],
) -> str:
    if action_template_id == _ICON_ACTION_TEMPLATE_ID:
        props = {
            "actionId": action["actionId"],
            "icon": "<one semantically matching trustedAssetSource>",
        }
    else:
        props = action
    return (
        f'Template("{action_template_id}",'
        + json.dumps(props, ensure_ascii=False, separators=(",", ":"))
        + ")"
    )


def _second_layer_layout_selection(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> _SecondLayerLayoutSelection:
    """Resolve only layout capacity and Action shape in the second layer."""
    action_count = len(task_spec.eventCandidates)
    component_count = len(scope.advanced_component_ids)
    if task_spec.size == "2x2":
        if (component_count, action_count) == (2, 1):
            selection = _SecondLayerLayoutSelection(
                layout_ids=("HeroTitleContentActionLayout",),
                layout_kinds=(),
                action_template_ids=(_PILL_ACTION_TEMPLATE_ID,),
                business_layout_kinds_by_position=("HeroTitle", "HeroContent"),
            )
        elif component_count == 2 and action_count in {0, 2}:
            selection = _SecondLayerLayoutSelection(
                layout_ids=("TwoSupportLayout",),
                layout_kinds=("Support",),
                embeds_support_actions=True,
            )
        elif (component_count, action_count) == (1, 0):
            selection = _SecondLayerLayoutSelection(
                layout_ids=("SingleFocusLayout",),
                layout_kinds=("Full",),
            )
        elif (component_count, action_count) == (1, 1):
            layout_ids = ["HeroActionLayout"]
            layout_kinds = ["Hero"]
            action_template_ids = [_PILL_ACTION_TEMPLATE_ID]
            if _has_semantic_action_icon(task_spec):
                layout_ids.append("FullIconActionLayout")
                layout_kinds.append("Full")
                action_template_ids.append(_ICON_ACTION_TEMPLATE_ID)
            selection = _SecondLayerLayoutSelection(
                layout_ids=tuple(layout_ids),
                layout_kinds=tuple(layout_kinds),
                action_template_ids=tuple(action_template_ids),
            )
        elif (component_count, action_count) == (1, 2):
            selection = _SecondLayerLayoutSelection(
                layout_ids=("CompactTwoActionLayout",),
                layout_kinds=("Compact",),
                action_template_ids=(_PILL_ACTION_TEMPLATE_ID,),
            )
        else:
            raise ValueError("2x2 Template candidates do not fit one supported layout")
    elif task_spec.size == "2x4" and component_count == 1 and action_count <= 1:
        selection = _SecondLayerLayoutSelection(
            layout_ids=("WideSingleFocusLayout",),
            layout_kinds=("WideHero" if action_count else "WideFull",),
            action_template_ids=((_PILL_ACTION_TEMPLATE_ID,) if action_count else ()),
        )
    else:
        raise ValueError("Template candidates do not fit one supported layout")
    allowed_layout_ids = resolve_scope_layout_ids(scope, task_spec, registry)
    if any(layout_id not in allowed_layout_ids for layout_id in selection.layout_ids):
        raise ValueError("Advanced Scope has no compatible UX layout")
    return selection


def _has_semantic_action_icon(task_spec: TaskSpec) -> bool:
    keywords = {"action", "event", "shortcut", "动作", "操作", "入口", "快捷"}
    for candidate in task_spec.assetCandidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("src"), str):
            continue
        text_values = [str(candidate.get("description", ""))]
        for key in ("sceneTags", "semanticTags", "tags"):
            values = candidate.get(key, ())
            if isinstance(values, list):
                text_values.extend(str(item) for item in values)
        normalized = " ".join(text_values).casefold()
        if any(keyword in normalized for keyword in keywords):
            return True
    return False


def _filter_second_layer_template_candidates(
    candidates_by_component: dict[str, tuple[str, ...]],
    required_template_groups: tuple[tuple[str, ...], ...],
    layout_kinds: tuple[str, ...],
) -> tuple[
    dict[str, tuple[str, ...]],
    tuple[tuple[str, ...], ...],
    tuple[str, ...],
]:
    """Filter first-layer candidates by layout without inspecting business data."""
    viable_layout_kind_values: list[str] = []
    for layout_kind in layout_kinds:
        has_complete_coverage = _layout_kind_has_complete_coverage(
            candidates_by_component,
            required_template_groups,
            layout_kind,
        )
        if has_complete_coverage:
            viable_layout_kind_values.append(layout_kind)
    viable_layout_kinds = tuple(viable_layout_kind_values)
    if not viable_layout_kinds:
        layout_label = "/".join(layout_kinds)
        raise ValueError(
            f"First-layer Template candidates have no complete {layout_label} coverage"
        )
    filtered = {
        component_id: tuple(
            template_id
            for template_id in template_ids
            if provider_template_layout_kind(template_id) in viable_layout_kinds
        )
        for component_id, template_ids in candidates_by_component.items()
    }
    for component_id, template_ids in filtered.items():
        if not template_ids:
            layout_label = "/".join(viable_layout_kinds)
            raise ValueError(
                f"Advanced Scope component {component_id} has no {layout_label} template"
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
        layout_label = "/".join(viable_layout_kinds)
        raise ValueError(f"First-layer Template candidates have no {layout_label} coverage")
    return filtered, filtered_groups, viable_layout_kinds


def _filter_positional_second_layer_template_candidates(
    candidates_by_component: dict[str, tuple[str, ...]],
    required_template_groups: tuple[tuple[str, ...], ...],
    layout_kinds_by_position: tuple[str, ...],
) -> tuple[dict[str, tuple[str, ...]], tuple[tuple[str, ...], ...]]:
    """Filter ordered business candidates against per-position layout suffixes."""
    component_items = tuple(candidates_by_component.items())
    if len(component_items) != len(layout_kinds_by_position):
        raise ValueError("Positional layout shape does not match Advanced Scope")
    filtered: dict[str, tuple[str, ...]] = {}
    for (component_id, template_ids), layout_kind in zip(
        component_items,
        layout_kinds_by_position,
        strict=True,
    ):
        matching_ids = {
            template_id
            for template_id in template_ids
            if provider_template_layout_kind(template_id) == layout_kind
        }
        component_groups = [
            set(group).intersection(template_ids)
            for group in required_template_groups
            if set(group).intersection(template_ids)
        ]
        complete_ids = matching_ids
        if component_groups:
            complete_ids = matching_ids.intersection(*component_groups)
        if not complete_ids:
            raise ValueError(
                f"Advanced Scope component {component_id} has no complete {layout_kind} template"
            )
        filtered[component_id] = tuple(
            template_id for template_id in template_ids if template_id in complete_ids
        )
    return filtered, tuple(filtered.values())


def _layout_kind_has_complete_coverage(
    candidates_by_component: dict[str, tuple[str, ...]],
    required_template_groups: tuple[tuple[str, ...], ...],
    layout_kind: str,
) -> bool:
    ids_by_component = {
        component_id: {
            template_id
            for template_id in template_ids
            if provider_template_layout_kind(template_id) == layout_kind
        }
        for component_id, template_ids in candidates_by_component.items()
    }
    if any(not template_ids for template_ids in ids_by_component.values()):
        return False
    groups = required_template_groups or tuple(
        tuple(template_ids) for template_ids in ids_by_component.values()
    )
    for template_ids in ids_by_component.values():
        component_groups = [set(group).intersection(template_ids) for group in groups]
        component_groups = [group for group in component_groups if group]
        if component_groups and not set.intersection(*component_groups):
            return False
    allowed_ids = set().union(*ids_by_component.values())
    return all(set(group).intersection(allowed_ids) for group in groups)


def _prune_layout_selection(
    selection: _SecondLayerLayoutSelection,
    viable_layout_kinds: tuple[str, ...],
) -> _SecondLayerLayoutSelection:
    viable = set(viable_layout_kinds)
    pairs_values: list[tuple[str, str]] = []
    layout_pairs = zip(
        selection.layout_ids,
        selection.layout_kinds,
        strict=True,
    )
    for layout_id, layout_kind in layout_pairs:
        if layout_kind in viable:
            pairs_values.append((layout_id, layout_kind))
    pairs = tuple(pairs_values)
    if not pairs:
        raise ValueError("Second-layer layout candidates have no complete business Template")
    has_pill_layout = any(layout_id != "FullIconActionLayout" for layout_id, _ in pairs)
    has_icon_layout = any(layout_id == "FullIconActionLayout" for layout_id, _ in pairs)
    action_templates: list[str] = []
    for template_id in selection.action_template_ids:
        if template_id == _PILL_ACTION_TEMPLATE_ID and has_pill_layout:
            action_templates.append(template_id)
        if template_id == _ICON_ACTION_TEMPLATE_ID and has_icon_layout:
            action_templates.append(template_id)
    return _SecondLayerLayoutSelection(
        layout_ids=tuple(layout_id for layout_id, _ in pairs),
        layout_kinds=tuple(layout_kind for _, layout_kind in pairs),
        action_template_ids=tuple(action_templates),
        embeds_support_actions=selection.embeds_support_actions,
        business_layout_kinds_by_position=selection.business_layout_kinds_by_position,
    )


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
