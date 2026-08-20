"""第二层高级组件与基础组件混合生成 Prompt。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.models import Fact, HybridBodyContract
from services.template_generation.engine.cardplan.prompt import build_hybrid_prompt
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
    UxBusinessComponentCapability,
)
from .scope_planner import (
    resolve_available_capability_ids,
    resolve_scope_layout_ids,
    scope_template_ids,
    task_spec_with_selected_action,
)

_WEATHER_BUILTIN_ASSETS = (
    "resources/base/media/icon_weather1.svg",
    "resources/base/media/sun_max.svg",
    "resources/base/media/cold.svg",
)


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
                f"{error}。不要解释；保持同一个 uxAdvancedScope，重新输出完整布局根 DSL。"
                "只能逐字使用原请求 trustedStringLiterals/trustedAssetSources，"
                "不得新增标签、单位、颜色、尺寸、Action 或未批准 Template；"
                "必须逐组补齐 requiredLocalTemplateGroups，并保留 directBusinessComponents。"
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
    available_capability_ids = _card_spec_capability_ids(card_spec)
    effective_capability_ids = resolve_available_capability_ids(
        task_spec,
        registry,
        available_capability_ids,
    )
    components = tuple(
        registry.require_ux_business_component(item) for item in scope.advanced_component_ids
    )
    requested_candidate_ids = {
        candidate.component_id: candidate.available_template_ids
        for candidate in component_candidates
    }
    if tuple(requested_candidate_ids) != scope.advanced_component_ids:
        raise ValueError("Template candidates do not match Advanced Scope")
    satisfiable_template_ids = set(scope_template_ids(scope, registry, task_spec))
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
    selected_template_ids = tuple(
        template_id
        for component_id in scope.advanced_component_ids
        for template_id in candidate_ids_by_component[component_id]
    )
    effective_component_candidates = tuple(
        TemplateComponentCandidate(
            componentId=component_id,
            availableTemplateIds=template_ids,
        )
        for component_id, template_ids in candidate_ids_by_component.items()
    )
    selected_action_id = next(
        (event.id for event in task_spec.eventCandidates if event.id is not None),
        None,
    )
    task_spec = task_spec_with_selected_action(task_spec, selected_action_id)
    allowed_layout_ids = resolve_scope_layout_ids(scope, task_spec, registry)
    if not allowed_layout_ids:
        raise ValueError("Advanced Scope has no compatible UX layout")
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
    )
    template_components = tuple(
        component for component in components if component.implementation == "template"
    )
    direct_components = tuple(
        component.name for component in components if component.implementation == "terse-dsl"
    )
    has_weather = any(component.name == "WeatherOverview" for component in components)
    has_heart_rate = any(component.name == "HeartRateOverview" for component in components)
    effective_required_template_groups = (
        tuple(
            tuple(template_id for template_id in group if template_id in selected_template_ids)
            for group in required_template_groups
        )
        if required_template_groups
        else tuple(
            _required_template_group(
                candidate_ids_by_component[component.name],
                base.requested_template_ids,
            )
            for component in template_components
        )
    )
    if any(not group for group in effective_required_template_groups):
        raise ValueError("An explicit output field has no satisfiable candidate Template")
    allowed_assets = tuple(
        dict.fromkeys(
            (
                *base.contract.allowed_asset_sources,
                *(_WEATHER_BUILTIN_ASSETS if has_weather else ()),
            )
        )
    )
    asset_tags = dict(base.contract.asset_semantic_tags_by_source)
    if has_weather:
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
        if weather_facts is None:
            raise ValueError("WeatherOverview has no complete trusted weather facts")
        server_owned_weather_literals = {
            weather_facts.city,
            weather_facts.temperature,
            weather_facts.condition,
            weather_facts.air_quality,
            weather_facts.temperature_range,
        }
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
    if "ScheduleOverview" in direct_components:
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
            "allowed_asset_sources": allowed_assets,
            "asset_semantic_tags_by_source": asset_tags,
            "required_literals": required_literals,
            "required_numbers": required_numbers,
            "protected_literals": protected_literals,
        }
    )
    layout_lines = [
        (
            f'- Template("{layout.name}@1", {{}}, child1, ...): {layout.description}; '
            f"businessChildren={layout.minimum_children(task_spec.size)}.."
            f"{layout.max_children_by_size[task_spec.size]}（不含 Action）; "
            f"actions={layout.min_action_children_by_size[task_spec.size]}.."
            f"{layout.max_action_children_by_size[task_spec.size]}; "
            "Action 必须是连续末尾直接 children；configSchema="
            + json.dumps(layout.parameters_schema, ensure_ascii=False)
        )
        for layout_id in allowed_layout_ids
        for layout in (registry.require_ux_layout_component(layout_id),)
    ]
    business_lines = [
        _business_component_line(
            component,
            effective_capability_ids,
            task_spec.size,
            base.requested_template_ids,
            candidate_ids_by_component[component.name],
        )
        for component in components
    ]
    provider_second_layer_rules = registry.provider_second_layer_rules(scope.advanced_component_ids)
    ux_override = "\n".join(
        (
            "",
            "UX Token=" + json.dumps(registry.ux_tokens, ensure_ascii=False),
            "允许的布局高级组件：",
            *layout_lines,
            "已批准的业务高级组件范围：",
            *business_lines,
            "template 实现的业务高级组件必须逐组使用 requiredLocalTemplateGroups；"
            "terse-dsl 实现必须使用对应的 directBusinessComponents 调用，不能改用 JSON Template。",
            "最终输出必须直接以唯一批准的布局 Template 为根并以分号结束；禁止 card@1。",
        )
    )
    user_suffix = "\n".join(
        (
            "trustedStringLiterals=" + json.dumps(contract.trusted_literals, ensure_ascii=False),
            "trustedAssetSources=" + json.dumps(contract.allowed_asset_sources, ensure_ascii=False),
            "uxAdvancedScope=" + json.dumps(scope.model_dump(by_alias=True), ensure_ascii=False),
            "componentCandidates="
            + json.dumps(
                [
                    candidate.model_dump(by_alias=True)
                    for candidate in effective_component_candidates
                ],
                ensure_ascii=False,
            ),
            "allowedUxLayouts=" + json.dumps(allowed_layout_ids, ensure_ascii=False),
            "requiredLocalTemplateGroups="
            + json.dumps(effective_required_template_groups, ensure_ascii=False),
            "directBusinessComponents=" + json.dumps(direct_components, ensure_ascii=False),
            "providerSecondLayerRules="
            + json.dumps(provider_second_layer_rules, ensure_ascii=False),
            "只能从 componentCandidates 中同一 componentId 的 availableTemplateIds "
            "选择最终业务模板；不得使用 Provider 文档中的其他模板。",
            "selectedActionEventId=" + json.dumps(selected_action_id, ensure_ascii=False),
            "Action 与业务组件解耦；selectedActionEventId 非空时，只能在布局根末尾输出唯一的 "
            'PillAction({"actionId":"<selectedActionEventId>"})；为空时不得输出 Action。',
            "业务高级组件字段由服务端绑定到 TaskSpec.dataModelSchema 的端侧数据路径；"
            "最终有效 TerseDSL 使用完整 `${data.weather.temperature}` 占位值，"
            "并由服务端附加确定性的 `data = {...}`；"
            "模型不得编造路径，已有全局路径的值不得改用 props。",
            "只输出混合 DSL，不输出说明。",
        )
    )
    base_user_message = "\n".join(
        (
            "mustKeep=" + json.dumps(contract.required_literals, ensure_ascii=False)
            if line.startswith("mustKeep=")
            else line
        )
        for line in base.messages[1]["content"].splitlines()
    )
    messages = [
        {"role": "system", "content": base.messages[0]["content"] + ux_override},
        {"role": "user", "content": base_user_message + "\n" + user_suffix},
    ]
    if sum(len(item["content"]) for item in messages) > 80_000:
        raise ValueError("UX Mixed Prompt exceeds the service input budget")
    return UxMixedPromptProjection(
        messages=messages,
        contract=contract,
        facts=base.facts,
        requested_template_ids=base.requested_template_ids,
        allowed_layout_ids=allowed_layout_ids,
        theme_id=base.theme_id,
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


def _business_component_line(
    component: UxBusinessComponentCapability,
    capability_ids: set[str],
    size: str,
    requested_template_ids: tuple[str, ...],
    selected_template_ids: tuple[str, ...],
) -> str:
    templates = tuple(
        item for item in selected_template_ids if item in requested_template_ids
    )
    return (
        f"- {component.name}: variants={list(component.enabled_variants(capability_ids))}; "
        f"roles={list(component.roles)}; maxItems={component.max_items_by_size[size]}; "
        f"availableTemplateIds={list(templates)}"
    )


def _card_spec_capability_ids(card_spec: dict[str, Any]) -> tuple[str, ...] | None:
    bindings = card_spec.get("dataBindings")
    if bindings is None:
        return None
    if not isinstance(bindings, list):
        return ()
    return tuple(
        capability_id
        for binding in bindings
        if isinstance(binding, dict)
        for capability_id in (binding.get("capabilityId"),)
        if isinstance(capability_id, str)
    )


def _provider_component_server_owned_values(
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    components: tuple[UxBusinessComponentCapability, ...],
    registry: CardPlanRegistry,
    allowed_template_ids: set[str],
) -> tuple[str | int | float, ...]:
    values: list[str | int | float] = []
    for component in components:
        definitions = tuple(
            registry.require_template(template_id)
            for template_id in component.local_template_ids
            if template_id in allowed_template_ids
            if registry.require_template(template_id).source_format == "cardtpl/1"
        )
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
