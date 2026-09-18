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
from services.template_generation.engine.cardplan.generic_metrics import GENERIC_HEALTH_LABELS
from services.template_generation.engine.cardplan.models import (
    CARDTPL_SOURCE_FORMATS,
    BusinessTemplateGroup,
    Fact,
    HybridBodyContract,
    TemplatePlan,
)
from services.template_generation.engine.cardplan.prompt import (
    action_binding_ids,
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
_COMPACT_ACTION_TEMPLATE_ID = "CompactAction@1"
_ICON_ACTION_TEMPLATE_ID = "IconAction@1"
_LARGE_ICON_ACTION_TEMPLATE_ID = "LargeIconAction@1"
_TWO_FOCUS_LAYOUT_IDS = frozenset(
    {"WideTwoFocusLayout", "WideTwoFocusActionLayout", "WideTwoFocusTwoActionLayout"}
)


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
    preserve_search_candidates: bool = False


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
                "若原动态契约包含 planCandidates，必须完整选择其中一个原子 Plan，"
                "不得跨 Plan 混用布局、业务模板或 Action 消费位置；"
                "有 Plan 时按 Plan 的业务实例数生成；无 Plan 时每个 "
                "requiredLocalTemplateGroups 恰好选择一个业务 Template；"
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
    template_plans: tuple[TemplatePlan, ...] = (),
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
    selected_event_ids = tuple(
        event.id for event in task_spec.eventCandidates if event.id is not None
    )
    task_spec = task_spec_with_selected_action(task_spec, selected_event_ids)
    selected_action_ids = action_binding_ids(task_spec)
    if template_plans:
        _validate_prompt_template_plans(template_plans, scope, selected_action_ids)
        layout_selection = _planned_layout_selection(template_plans)
        effective_required_template_groups = required_template_groups
    else:
        layout_selection = _second_layer_layout_selection(
            scope,
            task_spec,
            registry,
            required_template_groups=required_template_groups,
        )
        if _TWO_FOCUS_LAYOUT_IDS.intersection(layout_selection.layout_ids):
            candidate_ids_by_component, required_template_groups = (
                _order_two_focus_component_slots(
                    candidate_ids_by_component,
                    required_template_groups,
                    card_spec,
                    registry,
                )
            )
        if task_spec.size == "2x4" and layout_selection.business_layout_kinds_by_position:
            (
                candidate_ids_by_component,
                effective_required_template_groups,
                _,
            ) = _filter_second_layer_template_candidates(
                candidate_ids_by_component,
                required_template_groups,
                layout_selection.business_layout_kinds_by_position,
                exact_slots=True,
            )
        elif layout_selection.business_layout_kinds_by_position:
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
    theme_id = None
    if not template_plans:
        theme_id = registry.hero_content_theme_id(selected_template_ids, scope.theme_id)
    has_planned_hero_content = any(
        plan.layout_template_id == "HeroTitleContentActionLayout@1"
        for plan in template_plans
    )
    primary_component = components[1] if theme_id is not None else components[0]
    if has_planned_hero_content:
        primary_component = components[1]
    bridge = _ScopePromptBridge(
        theme_id=theme_id or scope.theme_id,
        local_template_ids=selected_template_ids,
        primary_domain=primary_component.domain_id,
        advanced_component_ids=scope.advanced_component_ids,
        preserve_search_candidates=bool(template_plans),
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
            raise ValueError("HeartRateOverview has no trusted exercise heart-rate facts")
        heart_rate_numbers = heart_rate_facts.bpm_values()
        required_numbers = tuple(
            item for item in required_numbers if item not in heart_rate_numbers
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
            raise ValueError(
                "SleepOverview has no losslessly renderable night or nap duration"
            )
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
            bluetooth_facts.left_charging_status,
            bluetooth_facts.right_charging_status,
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
            "trusted_literals": tuple(dict.fromkeys(
                (*base.contract.trusted_literals, *GENERIC_HEALTH_LABELS.values())
            )),
            # 原子计划已校验操作归属，内置按钮不占布局根的 Action 槽位。
            "content_action_ids": (
                selected_action_ids if template_plans else base.contract.content_action_ids
            ),
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
    available_business_template_ids = _template_contract_ids(
        business_template_contracts,
        "Business Template contract",
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
    candidate_groups = _candidate_groups_for_prompt(
        effective_component_candidates,
        effective_required_template_groups,
    )
    action_template_ids = (
        layout_selection.action_template_ids if selected_action_ids else ()
    )
    # 仅无 Plan 的旧路径保留歌单改写；有 Plan 时 action_template_ids 已由
    # _planned_layout_selection 从计划推导（Planner 负责歌单专用模板），
    # 改写整组会破坏 PillAction 与 WideHalf 混排的多 Plan 提示词。
    if (
        not template_plans
        and layout_selection.layout_ids == ("WideHalfTwoCompactLayout",)
        and selected_action_ids == ("event.open.music.daily",)
    ):
        action_template_ids = ("PlaylistCompactAction@1",)
    action_template_contracts = build_template_prompt_contracts(
        action_template_ids,
        contract,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=True,
    )
    available_action_template_ids = _template_contract_ids(
        action_template_contracts,
        "Action Template contract",
    )
    layout_template_contracts = build_template_prompt_contracts(
        allowed_layout_template_ids,
        contract,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=True,
    )
    available_layout_template_ids = _template_contract_ids(
        layout_template_contracts,
        "Layout Template contract",
    )
    if template_plans:
        _validate_planned_template_contracts(
            template_plans,
            set(available_business_template_ids),
            set(available_action_template_ids),
            set(available_layout_template_ids),
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
                *available_action_template_ids,
                *available_layout_template_ids,
            )
        )
    )
    contract = contract.model_copy(
        update={
            "required_template_groups": effective_required_template_groups,
            "allowed_template_ids": allowed_template_ids,
            "allowed_template_plans": template_plans,
        }
    )
    provider_second_layer_rules = registry.provider_second_layer_guidance(
        scope.advanced_component_ids
    )
    selected_actions = _selected_action_candidates(contract)
    asset_candidates = _asset_prompt_candidates(task_spec, contract)
    candidate_group_guidance = (
        "candidateGroups 中每一组对应一个独立布局槽位；同一个通用组件可以在多个槽位实例化。"
        "本用例必须按槽位顺序选择 Full、Compact、Compact，并由布局根承载。"
        if tuple(item["layoutKind"] for item in candidate_groups)
        == ("Full", "Compact", "Compact")
        else "candidateGroups 中每一组对应一个独立布局槽位；严格按槽位顺序选择并组合模板。"
    )
    layout_consistency_instruction = (
        "严格按所选 Plan 的 layoutTemplateId 和 children 顺序生成；"
        "主题已经由 Planner 确定，不得根据候选模板自行更换布局、主题或 Action 消费位置。"
        if template_plans
        else (
            "HeroTitleContentActionLayout 的三个直接 children 必须严格按 HeroTitle、"
            "HeroContent、PillAction 排列。全局主题已按主业务 HeroContent 确定，"
            "标题与动作继承同一主题；融球背景由服务端按版本门禁统一展开，不由模型生成。"
            if "HeroTitleContentActionLayout" in allowed_layout_ids
            else "严格按所选布局的槽位顺序组合；使用首层确定的主题，不得自行更换。"
        )
    )
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
            *(
                (
                    "candidateGroups=" + json.dumps(candidate_groups, ensure_ascii=False),
                    candidate_group_guidance,
                )
                if task_spec.size == "2x4"
                else ()
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
            "planCandidates="
            + json.dumps(
                [plan.model_dump(by_alias=True) for plan in template_plans],
                ensure_ascii=False,
            ),
            "actionContracts="
            + json.dumps(action_template_contracts, ensure_ascii=False),
            "providerSecondLayerRules="
            + json.dumps(provider_second_layer_rules, ensure_ascii=False),
            "outputGrammar="
            + json.dumps(
                (
                    _planned_output_grammar(template_plans, selected_actions)
                    if template_plans
                    else _output_grammar(
                        allowed_layout_template_ids,
                        effective_required_template_groups,
                        selected_actions,
                        action_template_ids,
                        embeds_support_actions=layout_selection.embeds_support_actions,
                    )
                ),
                ensure_ascii=False,
            ),
            (
                "Planner 已给出最多三个完整原子 Plan。必须完整选择其中一个 Plan，"
                "严格保持 layoutTemplateId、业务 Template 顺序以及 Action 消费位置；"
                "不得跨 Plan 混用或更换 fieldBindings；重复通用模板按 Plan 实例数生成。"
                "仅补全所选 Template 的开放 Props 与可信素材。"
                if template_plans
                else (
                    "第一层已完成展示覆盖。从每个 requiredLocalTemplateGroups 恰好选择一个"
                    " Template，按完整签名设置 Props，并使用一个与业务后缀及动作形态匹配的布局根。"
                )
            ),
            layout_consistency_instruction,
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


def _candidate_groups_for_prompt(
    candidates: tuple[TemplateComponentCandidate, ...],
    required_groups: tuple[tuple[str, ...], ...],
) -> tuple[dict[str, Any], ...]:
    """Expose repeated template slots without duplicating component candidates."""
    candidate_ids_by_component = {
        candidate.component_id: set(candidate.available_template_ids)
        for candidate in candidates
    }
    groups: list[dict[str, Any]] = []
    for slot_index, template_group in enumerate(required_groups):
        template_ids = tuple(template_group)
        matching_components = tuple(
            component_id
            for component_id, available_ids in candidate_ids_by_component.items()
            if set(template_ids).intersection(available_ids)
        )
        groups.append(
            {
                "slotIndex": slot_index,
                "componentId": matching_components[0] if matching_components else "",
                "availableTemplateIds": list(template_ids),
                "layoutKind": (
                    provider_template_layout_kind(template_ids[0])
                    if template_ids
                    else ""
                ),
            }
        )
    return tuple(groups)


def _selected_action_candidates(
    contract: HybridBodyContract,
) -> tuple[dict[str, str], ...]:
    selected_ids = set(contract.content_action_ids)
    entries: list[dict[str, str]] = []
    for action in contract.action_bindings:
        if action.action_id not in selected_ids:
            continue
        entry = {
            "actionId": action.action_id,
            "label": action.display_label,
        }
        if action.display_subtitle:
            entry["subtitle"] = action.display_subtitle
        entries.append(entry)
    return tuple(entries)


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
        "WideFullOnlyLayout": "WideFull",
        "WideTwoFullLayout": "Full",
        "WideHeroCompactLayout": ("Hero", "Compact"),
        "WideFullHeroActionLayout": ("Full", "Hero"),
        "WideHeroActionFullLayout": ("Full", "Hero"),
        "WideFullTwoCompactLayout": "Full",
        "WideFourCompactLayout": ("Compact",) * 4,
        "WideFullHeroTwoActionLayout": ("Full", "Hero"),
        "WideTwoHeroActionLayout": ("Hero", "Hero"),
        "WideFullFourActionLayout": "Full",
        "WideTwoHalfLayout": "WideHalf",
        "WideHalfTwoCompactLayout": ("WideHalf", "Compact", "Compact"),
        "WideHalfCompactTwoLargeActionLayout": ("WideHalf", "Compact"),
        "WideHalfFourLargeActionLayout": "WideHalf",
        "WideTwoFocusLayout": ("Hero", "Hero"),
        "WideTwoFocusActionLayout": ("Hero", "Hero"),
        "WideTwoFocusTwoActionLayout": ("Hero", "Hero"),
    }[layout_id]
    if layout_id == "WideFullTwoCompactLayout":
        business_template_ids = required_template_groups
        layout_kind_label = "Full+Compact"
    elif isinstance(layout_kind, tuple):
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
        "WideFullHeroActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideHeroActionFullLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideFullTwoCompactLayout": _COMPACT_ACTION_TEMPLATE_ID,
        "WideHalfTwoCompactLayout": (
            "PlaylistCompactAction@1"
            if "PlaylistCompactAction@1" in action_template_ids
            else _COMPACT_ACTION_TEMPLATE_ID
        ),
        "WideFullHeroTwoActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideTwoHeroActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideFullFourActionLayout": _LARGE_ICON_ACTION_TEMPLATE_ID,
        "WideHalfCompactTwoLargeActionLayout": _LARGE_ICON_ACTION_TEMPLATE_ID,
        "WideHalfFourLargeActionLayout": _LARGE_ICON_ACTION_TEMPLATE_ID,
        "WideTwoFocusActionLayout": _PILL_ACTION_TEMPLATE_ID,
        "WideTwoFocusTwoActionLayout": _PILL_ACTION_TEMPLATE_ID,
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


# 候选动作可携带 subtitle 等附加信息，但输出语法只允许模板签名内的 Props。
_ACTION_TEMPLATE_ALLOWED_PROPS: dict[str, tuple[str, ...]] = {
    "PillAction@1": ("actionId", "label"),
    "PlaylistCompactAction@1": ("actionId", "label"),
    "CompactAction@1": ("actionId", "label", "subtitle", "prominent"),
    "IconAction@1": ("actionId",),
    "LargeIconAction@1": ("actionId",),
}


def _action_output_syntax(
    action_template_id: str,
    action: dict[str, str],
) -> str:
    allowed_props = _ACTION_TEMPLATE_ALLOWED_PROPS.get(action_template_id)
    filtered = (
        {key: action[key] for key in allowed_props if key in action}
        if allowed_props is not None
        else action
    )
    if action_template_id in {_COMPACT_ACTION_TEMPLATE_ID, "PlaylistCompactAction@1"}:
        props = {
            **filtered,
            "icon": "<one semantically matching trustedAssetSource>",
        }
    elif action_template_id in {_ICON_ACTION_TEMPLATE_ID, _LARGE_ICON_ACTION_TEMPLATE_ID}:
        props = {
            "actionId": filtered["actionId"],
            "icon": "<one semantically matching trustedAssetSource>",
        }
    else:
        props = filtered
    return (
        f'Template("{action_template_id}",'
        + json.dumps(props, ensure_ascii=False, separators=(",", ":"))
        + ")"
    )


def _template_contract_ids(
    contracts: tuple[dict[str, Any], ...],
    contract_name: str,
) -> tuple[str, ...]:
    template_ids: list[str] = []
    for contract in contracts:
        template_id = contract.get("templateId")
        if not isinstance(template_id, str) or not template_id:
            raise ValueError(f"{contract_name} has no templateId")
        if template_id not in template_ids:
            template_ids.append(template_id)
    return tuple(template_ids)


def _validate_planned_template_contracts(
    plans: tuple[TemplatePlan, ...],
    business_template_ids: set[str],
    action_template_ids: set[str],
    layout_template_ids: set[str],
) -> None:
    for plan in plans:
        if plan.layout_template_id not in layout_template_ids:
            raise ValueError("Template Plan Layout has no complete signature")
        for slot in plan.business_slots:
            if slot.template_id not in business_template_ids:
                raise ValueError("Template Plan business Template has no complete signature")
        for assignment in plan.action_assignments:
            if assignment.consumer != "root-action":
                continue
            action_template_id = assignment.action_template_id
            if action_template_id is None:
                raise ValueError("Root Action Plan is missing its Template")
            if action_template_id not in action_template_ids:
                raise ValueError("Template Plan Action has no complete signature")


def _validate_prompt_template_plans(
    plans: tuple[TemplatePlan, ...],
    scope: AdvancedScopeBrief,
    selected_action_ids: tuple[str, ...],
) -> None:
    if len(plans) > 3:
        raise ValueError("Second layer accepts at most three Template Plans")
    plan_ids = tuple(plan.plan_id for plan in plans)
    if len(plan_ids) != len(set(plan_ids)):
        raise ValueError("Second-layer Template Plan IDs must be unique")
    expected_business_ids = set(scope.advanced_component_ids)
    expected_action_ids = set(selected_action_ids)
    for plan in plans:
        business_ids = {slot.business_id for slot in plan.business_slots}
        action_ids = {item.action_id for item in plan.action_assignments}
        if business_ids != expected_business_ids:
            raise ValueError("Template Plan businesses do not match Advanced Scope")
        if action_ids != expected_action_ids:
            raise ValueError("Template Plan Actions do not match selected Actions")
        if plan.theme_id != scope.theme_id:
            raise ValueError("Template Plan Theme does not match Advanced Scope")


def _planned_layout_selection(
    plans: tuple[TemplatePlan, ...],
) -> _SecondLayerLayoutSelection:
    layout_ids_list: list[str] = []
    action_template_ids_list: list[str] = []
    embeds_support_actions = False
    for plan in plans:
        layout_id = plan.layout_template_id.removesuffix("@1")
        if layout_id not in layout_ids_list:
            layout_ids_list.append(layout_id)
        for assignment in plan.action_assignments:
            if assignment.consumer == "business-template":
                embeds_support_actions = True
                continue
            action_template_id = assignment.action_template_id
            if action_template_id is None:
                raise ValueError("Root Action Plan is missing its Template")
            if action_template_id not in action_template_ids_list:
                action_template_ids_list.append(action_template_id)
    return _SecondLayerLayoutSelection(
        layout_ids=tuple(layout_ids_list),
        layout_kinds=(),
        action_template_ids=tuple(action_template_ids_list),
        embeds_support_actions=embeds_support_actions,
    )


def _planned_output_grammar(
    plans: tuple[TemplatePlan, ...],
    selected_actions: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    actions_by_id: dict[str, dict[str, str]] = {}
    for item in selected_actions:
        action_id = item.get("actionId")
        if not isinstance(action_id, str):
            raise ValueError("Selected Action candidate has no actionId")
        actions_by_id[action_id] = item
    options: list[dict[str, Any]] = []
    for plan in plans:
        embedded_by_position = {
            item.business_position: item.action_id
            for item in plan.action_assignments
            if item.consumer == "business-template"
        }
        business_children = []
        for slot in plan.business_slots:
            action_id = embedded_by_position.get(slot.position)
            embedded_action = None
            if action_id is not None:
                embedded_action = actions_by_id.get(action_id)
                if embedded_action is None:
                    raise ValueError("Template Plan embeds an unknown Action")
            business_children.append(
                {
                    "position": slot.position,
                    "templateId": slot.template_id,
                    "layoutRole": slot.layout_role,
                    "requiredFieldBindings": slot.field_bindings,
                    "fieldLabels": {
                        path: GENERIC_HEALTH_LABELS.get(path)
                        for path in slot.field_bindings.values()
                    },
                    "syntax": (
                        f'Template("{slot.template_id}", <matching props>)'
                    ),
                    **(
                        {
                            "requiredEmbeddedAction": embedded_action,
                            "requiredProp": {"actionId": action_id},
                        }
                        if action_id is not None
                        else {"forbiddenProp": "actionId"}
                    ),
                }
            )
        root_actions = []
        for assignment in plan.action_assignments:
            if assignment.consumer != "root-action":
                continue
            action = actions_by_id.get(assignment.action_id)
            if action is None:
                raise ValueError("Template Plan references an unknown root Action")
            action_template_id = assignment.action_template_id
            if action_template_id is None:
                raise ValueError("Root Action Plan is missing its Template")
            root_actions.append(
                {
                    "position": len(plan.business_slots) + len(root_actions),
                    "templateId": action_template_id,
                    "syntax": _action_output_syntax(action_template_id, action),
                }
            )
        options.append(
            {
                "planId": plan.plan_id,
                "root": f'Template("{plan.layout_template_id}", {{}}, ...children);',
                "businessChildren": business_children,
                "actionChildren": root_actions,
            }
        )
    return {
        "atomicPlanOptions": options,
        "selectionRule": "choose exactly one option without cross-plan mixing",
    }


def _order_two_focus_component_slots(
    candidates_by_component: dict[str, tuple[str, ...]],
    required_template_groups: tuple[tuple[str, ...], ...],
    card_spec: dict[str, Any],
    registry: CardPlanRegistry,
) -> tuple[dict[str, tuple[str, ...]], tuple[tuple[str, ...], ...]]:
    """Order symmetric two-focus slots by the request data-binding order.

    The two-focus layouts place the first slot on the left panel. The retrieval
    pipeline orders candidates alphabetically, so without this projection a
    "weather + battery" request would render battery first. Reorder both the
    component candidates and the per-component template groups by the request
    ``dataBindings`` order, which follows the user's mention order.
    """
    bindings = card_spec.get("dataBindings")
    capability_order: dict[str, int] = {}
    if isinstance(bindings, list):
        for index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                continue
            capability_id = binding.get("capabilityId")
            if isinstance(capability_id, str) and capability_id not in capability_order:
                capability_order[capability_id] = index

    def slot_order(component_id: str) -> tuple[int, str]:
        capability_ids = registry.require_ux_business_component(
            component_id
        ).data_capability_ids
        indexes = [
            capability_order[capability_id]
            for capability_id in capability_ids
            if capability_id in capability_order
        ]
        return (min(indexes) if indexes else len(capability_order), component_id)

    ordered_components = dict(
        sorted(candidates_by_component.items(), key=lambda item: slot_order(item[0]))
    )
    groups_by_component: dict[str, tuple[str, ...]] = {}
    for group in required_template_groups:
        for component_id, template_ids in ordered_components.items():
            if component_id in groups_by_component:
                continue
            if set(group).intersection(template_ids):
                groups_by_component[component_id] = group
                break
    if len(groups_by_component) != len(ordered_components):
        return candidates_by_component, required_template_groups
    ordered_groups = tuple(
        groups_by_component[component_id] for component_id in ordered_components
    )
    return ordered_components, ordered_groups


def _second_layer_layout_selection(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    *,
    required_template_groups: tuple[tuple[str, ...], ...] = (),
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
    elif task_spec.size == "2x4":
        group_kinds = tuple(
            {
                provider_template_layout_kind(template_id)
                for template_id in group
            }
            for group in required_template_groups
        )
        def has_half(index: int) -> bool:
            return index < len(group_kinds) and "WideHalf" in group_kinds[index]
        if (component_count, action_count) == (1, 0):
            layout_id, kinds, actions = "WideFullOnlyLayout", ("WideFull",), ()
        elif (component_count, action_count) == (1, 1):
            if (
                len(group_kinds) >= 2
                and "Full" in group_kinds[0]
                and "Compact" in group_kinds[1]
            ):
                layout_id, kinds, actions = (
                    "WideFullTwoCompactLayout",
                    ("Full", "Compact"),
                    (_COMPACT_ACTION_TEMPLATE_ID,),
                )
            else:
                layout_id, kinds, actions = (
                    "WideSingleFocusLayout", ("WideHero",), (_PILL_ACTION_TEMPLATE_ID,)
                )
        elif (component_count, action_count) == (1, 2):
            layout_id, kinds, actions = (
                "WideFullTwoCompactLayout", ("Full",), (_COMPACT_ACTION_TEMPLATE_ID,)
            )
        elif (component_count, action_count) == (2, 0):
            if (
                len(group_kinds) >= 3
                and "Full" in group_kinds[0]
                and "Compact" in group_kinds[1]
                and "Compact" in group_kinds[2]
            ):
                layout_id, kinds, actions = (
                    "WideFullTwoCompactLayout", ("Full", "Compact"), ()
                )
            elif len(group_kinds) >= 2 and "Compact" in group_kinds[1]:
                if "Full" in group_kinds[0]:
                    raise ValueError(
                        "2x4 Full + Compact composition is not supported; "
                        "use WideFullTwoCompactLayout with two Compact children"
                    )
                elif "Hero" in group_kinds[0]:
                    layout_id, kinds, actions = (
                        "WideHeroCompactLayout", ("Hero", "Compact"), ()
                    )
                else:
                    raise ValueError(
                        "2x4 primary business must provide Full or Hero beside Compact"
                    )
            else:
                if has_half(0) and has_half(1):
                    layout_id, kinds, actions = "WideTwoHalfLayout", ("WideHalf", "WideHalf"), ()
                elif "Hero" in group_kinds[0] and "Hero" in group_kinds[1]:
                    layout_id, kinds, actions = "WideTwoFocusLayout", ("Hero", "Hero"), ()
                else:
                    layout_id, kinds, actions = "WideTwoFullLayout", ("Full", "Full"), ()
        elif (component_count, action_count) == (4, 0):
            if not all("Compact" in kinds for kinds in group_kinds):
                raise ValueError(
                    "2x4 four-Compact layout requires four Compact business templates"
                )
            layout_id, kinds, actions = (
                "WideFourCompactLayout", ("Compact",) * 4, ()
            )
        elif (component_count, action_count) == (2, 1):
            if has_half(0) and "Compact" in group_kinds[1]:
                selection = _SecondLayerLayoutSelection(
                    layout_ids=("WideHalfTwoCompactLayout",),
                    layout_kinds=("WideHalf",),
                    action_template_ids=(_COMPACT_ACTION_TEMPLATE_ID,),
                    business_layout_kinds_by_position=("WideHalf", "Compact"),
                )
            elif len(group_kinds) >= 2 and "Compact" in group_kinds[1]:
                if "Full" in group_kinds[0]:
                    selection = _SecondLayerLayoutSelection(
                        layout_ids=("WideFullTwoCompactLayout",),
                        layout_kinds=("Full",),
                        action_template_ids=(_COMPACT_ACTION_TEMPLATE_ID,),
                        business_layout_kinds_by_position=("Full", "Compact"),
                    )
                elif "Hero" in group_kinds[0]:
                    selection = _SecondLayerLayoutSelection(
                        layout_ids=("WideFullTwoCompactLayout",),
                        layout_kinds=("Hero",),
                        action_template_ids=(_COMPACT_ACTION_TEMPLATE_ID,),
                        business_layout_kinds_by_position=("Hero", "Compact"),
                    )
                else:
                    raise ValueError(
                        "2x4 primary business must provide Full or Hero beside Compact"
                    )
            else:
                hero_pair = (
                    len(group_kinds) >= 2
                    and "Hero" in group_kinds[0]
                    and "Hero" in group_kinds[1]
                )
                selection = _SecondLayerLayoutSelection(
                    layout_ids=(
                        ("WideTwoFocusActionLayout",)
                        if hero_pair
                        else (
                            "WideFullHeroActionLayout",
                            "WideHeroActionFullLayout",
                        )
                    ),
                    layout_kinds=("Full", "Full") if not hero_pair else ("Hero",),
                    action_template_ids=(_PILL_ACTION_TEMPLATE_ID,),
                    business_layout_kinds_by_position=("Full", "Hero")
                    if not hero_pair
                    else ("Hero", "Hero"),
                )
        elif (component_count, action_count) == (3, 0):
            layout_id, kinds, actions = (
                ("WideHalfTwoCompactLayout", ("WideHalf", "Compact", "Compact"), ())
                if has_half(0)
                else ("WideFullTwoCompactLayout", ("Full", "Compact", "Compact"), ())
            )
        elif (component_count, action_count) == (2, 2):
            if has_half(0):
                layout_id, kinds, actions = (
                    "WideHalfCompactTwoLargeActionLayout",
                    ("WideHalf", "Compact"),
                    (_LARGE_ICON_ACTION_TEMPLATE_ID,),
                )
            elif "Hero" in group_kinds[0] and "Hero" in group_kinds[1]:
                layout_id, kinds, actions = (
                    "WideTwoFocusTwoActionLayout",
                    ("Hero", "Hero"),
                    (_PILL_ACTION_TEMPLATE_ID,),
                )
            else:
                layout_id, kinds, actions = (
                    "WideFullHeroTwoActionLayout",
                    ("Full", "Hero"),
                    (_PILL_ACTION_TEMPLATE_ID,),
                )
        elif (component_count, action_count) == (1, 4):
            layout_id, kinds, actions = (
                ("WideHalfFourLargeActionLayout", ("WideHalf",), (_LARGE_ICON_ACTION_TEMPLATE_ID,))
                if has_half(0)
                else ("WideFullFourActionLayout", ("Full",), (_LARGE_ICON_ACTION_TEMPLATE_ID,))
            )
        else:
            raise ValueError("2x4 Template candidates do not fit one supported layout")
        if (component_count, action_count) != (2, 1):
            selection = _SecondLayerLayoutSelection(
                layout_ids=(layout_id,),
                layout_kinds=(kinds[0],),
                action_template_ids=actions,
                business_layout_kinds_by_position=kinds,
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
    *,
    exact_slots: bool = False,
) -> tuple[
    dict[str, tuple[str, ...]],
    tuple[tuple[str, ...], ...],
    tuple[str, ...],
]:
    """Filter first-layer candidates by layout without inspecting business data."""
    if exact_slots:
        if len(layout_kinds) == len(candidates_by_component):
            filtered = {
                component_id: tuple(
                    template_id
                    for template_id in template_ids
                    if provider_template_layout_kind(template_id) == layout_kind
                )
                for (component_id, template_ids), layout_kind in zip(
                    candidates_by_component.items(), layout_kinds, strict=True
                )
            }
            if any(not template_ids for template_ids in filtered.values()):
                raise ValueError(
                    "First-layer Template candidates have no complete layout-slot coverage"
                )
            allowed_ids = {item for values in filtered.values() for item in values}
            groups = required_template_groups or tuple(filtered.values())
            filtered_groups = tuple(
                tuple(item for item in group if item in allowed_ids) for group in groups
            )
            if any(not group for group in filtered_groups):
                raise ValueError(
                    "First-layer Template candidates have no complete layout-slot coverage"
                )
            return filtered, filtered_groups, layout_kinds
        if (
            len(required_template_groups) == len(layout_kinds)
            and len(layout_kinds) > len(candidates_by_component)
        ):
            # Split-slot composition (one component, e.g. a Full + Compact
            # pair): every slot group must contain a template of its slot kind
            # among that component's candidates.
            allowed_ids = {
                item for values in candidates_by_component.values() for item in values
            }
            filtered_groups = []
            for group, layout_kind in zip(required_template_groups, layout_kinds):
                group_ids = tuple(item for item in group if item in allowed_ids)
                if not any(
                    provider_template_layout_kind(item) == layout_kind
                    for item in group_ids
                ):
                    raise ValueError(
                        "First-layer Template candidates have no complete layout-slot coverage"
                    )
                filtered_groups.append(group_ids)
            return dict(candidates_by_component), tuple(filtered_groups), layout_kinds
        raise ValueError("Layout slot count does not match Advanced Scope components")
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
    large_icon_layout_ids = {
        "WideFullFourActionLayout",
        "WideHalfCompactTwoLargeActionLayout",
        "WideHalfFourLargeActionLayout",
    }
    has_large_icon_layout = any(
        layout_id in large_icon_layout_ids for layout_id, _ in pairs
    )
    has_icon_layout = any(layout_id == "FullIconActionLayout" for layout_id, _ in pairs)
    has_pill_layout = any(
        layout_id not in large_icon_layout_ids | {"FullIconActionLayout"}
        for layout_id, _ in pairs
    )
    action_templates: list[str] = []
    for template_id in selection.action_template_ids:
        if template_id == _PILL_ACTION_TEMPLATE_ID and has_pill_layout:
            action_templates.append(template_id)
        if template_id == _ICON_ACTION_TEMPLATE_ID and has_icon_layout:
            action_templates.append(template_id)
        if template_id == _LARGE_ICON_ACTION_TEMPLATE_ID and has_large_icon_layout:
            action_templates.append(template_id)
        if template_id == _COMPACT_ACTION_TEMPLATE_ID and has_pill_layout:
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
            if definition.source_format in CARDTPL_SOURCE_FORMATS:
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
