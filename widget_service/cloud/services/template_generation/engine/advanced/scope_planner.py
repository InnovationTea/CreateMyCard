"""第五接口的新第一层 LLM：只选择 Theme 和业务高级组件范围。"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from itertools import combinations
from typing import Any

from pydantic import ValidationError

from models.generation import CandidateDataBinding, TaskSpec, WidgetSize
from services.template_generation.engine.cardplan.models import BusinessTemplateGroup
from services.template_generation.engine.cardplan.prompt import (
    admitted_provider_template_variants,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_context_admission,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

from . import content_selectors as _content_selectors
from .content_selectors import (
    activity_overview_is_eligible,
    activity_overview_variants,
    app_usage_overview_is_eligible,
    battery_overview_is_eligible,
    bluetooth_device_overview_is_eligible,
    bluetooth_device_overview_variants,
    countdown_overview_is_eligible,
    countdown_overview_variants,
    date_overview_is_eligible,
    date_overview_query_is_supported,
    heart_rate_overview_is_eligible,
    resource_usage_overview_is_eligible,
    schedule_overview_is_eligible,
    sleep_overview_has_trusted_data,
    sleep_overview_is_eligible,
    sleep_overview_variants,
    weather_overview_is_eligible,
    workout_overview_is_eligible,
    workout_overview_variants,
)
from .models import (
    AdvancedScopeBrief,
    DataShape,
    TemplateComponentCandidate,
    TemplateRouteDecision,
    TemplateRouteSelection,
)

_REDUNDANT_2X2_SUPPORTS = {
    frozenset(("WeatherOverview", "LocationOverview")): "LocationOverview",
    frozenset(("ScheduleOverview", "DateOverview")): "DateOverview",
}


class TemplateRouteNotApplicable(ValueError):
    """首层判断无法证明模板能完整覆盖本轮数据需求。"""


def build_advanced_scope_prompt(
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None = None,
    *,
    template_route_decision: bool = False,
    coverage_bindings: tuple[CandidateDataBinding, ...] = (),
    card_spec: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """构造不含 Template、布局源码和整卡置信度信息的新第一层 Prompt。"""
    effective_ids = resolve_available_capability_ids(
        task_spec,
        registry,
        available_capability_ids,
    )
    component_candidates = _component_candidates(task_spec, data_shape, registry, effective_ids)
    if template_route_decision:
        # Template routing may only expose components that have a matching
        # Provider Template; UX-only context components cannot be archived here.
        component_candidates = tuple(
            capability
            for capability in component_candidates
            if _component_template_coverage_options(
                capability,
                task_spec,
                registry,
                effective_ids,
                card_spec,
            )
        )
    if not component_candidates:
        raise ValueError("no provider-backed UX Business Component candidate")
    if template_route_decision:
        return _build_template_route_prompt(
            task_spec=task_spec,
            data_shape=data_shape,
            registry=registry,
            effective_ids=effective_ids,
            component_candidates=component_candidates,
            coverage_bindings=coverage_bindings,
            card_spec=card_spec,
        )
    candidate_ids = {item.name for item in component_candidates}
    first_layer_theme_ids = registry.first_layer_theme_ids(
        tuple(item.name for item in component_candidates)
    )
    first_layer_theme_id_set = set(first_layer_theme_ids)
    admission_relaxed = advanced_component_data_admission_is_bypassed()
    user_payload = {
        "userQuery": task_spec.userQuery,
        "size": task_spec.size,
        "dataShape": data_shape.model_dump(exclude={"fields"}),
        "fields": [
            {
                "path": field.path,
                "name": field.name,
                "dataType": field.data_type,
                "description": field.description,
                "roles": field.roles,
            }
            for field in data_shape.fields
        ],
        "themes": [
            {
                "id": theme_id,
                "description": registry.themes[theme_id].description,
            }
            for theme_id in first_layer_theme_ids
        ],
        "crossDomainThemeIds": tuple(
            theme_id
            for theme_id in registry.palette_scene_theme_ids["generic"]
            if theme_id in first_layer_theme_id_set
        ),
        "advancedComponents": [
            _scope_candidate_prompt_payload(
                capability,
                task_spec,
                effective_ids,
                candidate_ids,
                registry,
                card_spec,
                first_layer_theme_ids,
                include_template_coverage=template_route_decision,
            )
            for capability in component_candidates
        ],
        "maxAdvancedComponents": registry.ux_size_budgets[task_spec.size].max_business_components,
        "temporaryDataAdmissionBypass": admission_relaxed,
    }
    schema = AdvancedScopeBrief.model_json_schema(by_alias=True)
    scope_instruction = (
        "你是第五接口独立的 Advanced Scope Planner。只输出 JSON，且只决定 themeId "
        "与 advancedComponentIds；scopeVersion 固定为 advanced-scope-brief/1。不得输出"
        "整卡置信度、整卡参数、局部模板候选、布局选择、组件参数、颜色、尺寸、"
        "Action、理由或任何额外字段。advancedComponentIds 只能从 advancedComponents 选择，"
        "必须覆盖用户主要业务语义，并遵守 maxAdvancedComponents；选择多个组件时必须"
        "互相出现在 compatibleWith 中。themeId 只能从 themes 选择，并且必须出现在每个"
        "所选高级组件的 themeIds 合集中。"
    )
    return [
        {
            "role": "system",
            "content": scope_instruction + "\n" + json.dumps(schema, ensure_ascii=False),
        },
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _build_template_route_prompt(
    *,
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    component_candidates: tuple[BusinessTemplateGroup, ...],
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any] | None,
) -> list[dict[str, str]]:
    candidate_ids = tuple(item.name for item in component_candidates)
    task_spec_roots = _data_roots_by_capability(coverage_bindings)
    data_roots = registry.provider_data_domains_for_components(candidate_ids)
    for capability_id, data_domain in data_roots.items():
        task_spec_root = task_spec_roots.get(capability_id)
        if task_spec_root is not None and task_spec_root != data_domain:
            raise ValueError(
                "TaskSpec data binding root does not match Provider dataDomain: "
                f"{capability_id}"
            )
    candidate_id_set = set(candidate_ids)
    theme_ids = registry.first_layer_theme_ids(candidate_ids)
    component_catalog = [
        _template_route_component_payload(
            capability,
            task_spec,
            registry,
            effective_ids,
            candidate_id_set,
            data_roots,
            card_spec,
            theme_ids,
        )
        for capability in component_candidates
    ]
    payload = {
        "userQuery": task_spec.userQuery,
        "size": task_spec.size,
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
        "componentCatalog": component_catalog,
        "theme": theme_ids,
        "action": [
            {"eventId": event.id, "call": event.call}
            for event in task_spec.eventCandidates
            if event.id
        ],
        "maxComponent": registry.ux_size_budgets[task_spec.size].max_business_components,
        "providerFirstLayerRules": registry.provider_first_layer_rules(
            candidate_ids,
            data_roots,
        ),
        "themeFirstLayerRules": registry.theme_first_layer_rule_documents(theme_ids),
    }
    schema = TemplateRouteDecision.model_json_schema(by_alias=True)
    system = (
        "你是模板生成的第一层选择器。只输出一个 JSON 对象，且顶层只能有 "
        "theme、componentCandidates、action "
        "三个字段，字段类型必须符合末尾 JSON Schema。theme 只能是 theme 候选中的一个 ID；"
        "componentCandidates 中每个 componentId 只能来自 componentCatalog，"
        "availableTemplateIds 只能从同一 componentCatalog 项的同名字段中选择，"
        "且必须非空；action 只能是 action 候选中的零到两个不重复 eventId 数组。"
        "Action 是点击或跳转动作，不是数据项：不得把 eventId、call 或动作参数"
        "当作数据路径，"
        "不得把动作放进 componentCandidates，也不得判断 Action 属于哪个 component。"
        "只有 userQuery 明确"
        "要求交互时，才在 action 中逐字输出对应 eventId；"
        "没有明确交互请求时输出空数组。"
        "即使模板路线失败，也必须从 theme 候选中选择最匹配用户意图的 theme；失败仅以"
        "componentCandidates 为空数组表示，并把 action 置为空数组。"
        "如果 userQuery 明确要求交互但 action 候选中没有语义匹配的 eventId，"
        "必须拒绝模板路线并"
        '输出 {"theme":"<最匹配的候选 theme>","componentCandidates":[],"action":[]}。'
        "第一步，根据 userQuery 从 taskSpecDataFields 的全量内容中"
        "标定本轮显式要求显示的数据字段；"
        "第二步，只能选择 supportedTaskSpecPaths 的并集能够完整覆盖"
        "全部显式字段的一个或多个"
        "componentId，任意一个显式字段全部或部分不能承载都必须失败；第三步，"
        "为每个组件保留能承载本轮显式字段的 availableTemplateIds，并逐个检查候选模板"
        "自身 primaryData 与 secondaryData 对应的数据字段是否在 taskSpecDataFields 中真实存在，"
        "缺少任意必需字段也必须失败。availableTemplateIds 是第二层可以继续"
        "选择的候选集，不是最终模板结果。"
        "这个中间字段集合"
        "只用于判断，不得出现在输出中。candidateOutputFields 不是本层的强制完整展示集合。"
        "任一必须显示字段无法呈现、组件不兼容、主题不适用或存在歧义时，输出"
        '{"theme":"<最匹配的候选 theme>","componentCandidates":[],"action":[]}。'
        "不得输出数据路径、参数、布局、"
        "理由、置信度或额外字段。\n" + json.dumps(schema, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _template_route_component_payload(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    candidate_ids: set[str],
    data_roots: dict[str, str],
    card_spec: dict[str, Any] | None,
    theme_ids: tuple[str, ...],
) -> dict[str, Any]:
    contracts = _component_template_prompt_contracts(
        capability,
        task_spec,
        registry,
        effective_ids,
        card_spec,
    )
    coverage = _component_template_coverage_union(
        capability,
        task_spec,
        registry,
        effective_ids,
        card_spec,
    )
    return {
        "componentId": capability.name,
        "availableTemplateIds": [item["templateId"] for item in contracts],
        "supportedTaskSpecPaths": sorted(
            _absolute_task_spec_path(data_roots[capability_id], path)
            for capability_id, paths in coverage.items()
            for path in paths
        ),
        "themeIds": theme_ids,
        "templates": contracts,
        "compatibleComponentIds": _compatible_component_ids(
            capability,
            candidate_ids,
            task_spec.size,
            task_spec.userQuery,
            registry,
        ),
    }


def _data_roots_by_capability(
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> dict[str, str]:
    roots: dict[str, str] = {}
    for binding in coverage_bindings:
        existing = roots.get(binding.capabilityId)
        if existing is not None and existing != binding.writeResultTo:
            raise ValueError("Template route requires one TaskSpec root per data capability")
        roots[binding.capabilityId] = binding.writeResultTo
    return roots


def _absolute_task_spec_path(root: str, relative_path: str) -> str:
    return f"{root.rstrip('/')}/{relative_path.lstrip('/')}"


def _scope_candidate_prompt_payload(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    effective_ids: set[str],
    candidate_ids: set[str],
    registry: CardPlanRegistry,
    card_spec: dict[str, Any] | None,
    first_layer_theme_ids: tuple[str, ...],
    *,
    include_template_coverage: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": capability.name,
        "description": capability.description,
        "variants": _effective_candidate_variants(capability, task_spec, effective_ids),
        "themeIds": first_layer_theme_ids,
        "compatibleWith": _compatible_component_ids(
            capability,
            candidate_ids,
            task_spec.size,
            task_spec.userQuery,
            registry,
        ),
    }
    if include_template_coverage:
        payload["templateCoverageByCapability"] = {
            capability_id: sorted(paths)
            for capability_id, paths in _component_template_coverage_union(
                capability,
                task_spec,
                registry,
                effective_ids,
                card_spec,
            ).items()
        }
    return payload


def _component_template_coverage_options(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    card_spec: dict[str, Any] | None,
) -> tuple[dict[str, frozenset[str]], ...]:
    options: list[dict[str, frozenset[str]]] = []
    for template_id in registry.enabled_template_ids(capability.local_template_ids):
        definition = registry.require_template(template_id)
        capability_id = definition.capability_id
        if capability_id is None or capability_id not in effective_ids:
            continue
        for _variant in admitted_provider_template_variants(
            definition,
            task_spec,
            card_spec,
        ):
            paths = set(definition.required_data) | set(definition.optional_data)
            options.append({capability_id: frozenset(paths)})
    return tuple(options)


def _component_template_coverage_union(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    card_spec: dict[str, Any] | None,
) -> dict[str, set[str]]:
    coverage: dict[str, set[str]] = {}
    for option in _component_template_coverage_options(
        capability,
        task_spec,
        registry,
        effective_ids,
        card_spec,
    ):
        for capability_id, paths in option.items():
            coverage.setdefault(capability_id, set()).update(paths)
    return coverage


def _component_template_prompt_contracts(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    card_spec: dict[str, Any] | None,
) -> tuple[dict[str, Any], ...]:
    contracts: list[dict[str, Any]] = []
    for template_id in registry.enabled_template_ids(capability.local_template_ids):
        definition = registry.require_template(template_id)
        if (
            definition.capability_id is None
            or definition.capability_id not in effective_ids
            or definition.data_domain is None
        ):
            continue
        if not admitted_provider_template_variants(definition, task_spec, card_spec):
            continue
        contracts.append(
            {
                "templateId": template_id,
                "description": definition.description,
                "requiredTaskSpecPaths": [
                    _absolute_task_spec_path(definition.data_domain, path)
                    for path in definition.required_data
                ],
                "optionalTaskSpecPaths": [
                    _absolute_task_spec_path(definition.data_domain, path)
                    for path in definition.optional_data
                ],
            }
        )
    return tuple(contracts)


def validate_template_request_coverage(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any] | None,
    component_candidates: tuple[TemplateComponentCandidate, ...] | None = None,
) -> None:
    """证明每个首层所选组件都有能从本轮 TaskSpec 展开的 Provider 模板。"""
    if not coverage_bindings:
        raise ValueError("Template route requires query-selected data fields")
    capability_ids = [binding.capabilityId for binding in coverage_bindings]
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError("Template route requires one binding root per data capability")
    effective_ids = resolve_available_capability_ids(task_spec, registry, tuple(capability_ids))
    candidates_by_component = {
        candidate.component_id: candidate.available_template_ids
        for candidate in component_candidates or ()
    }
    if component_candidates is not None:
        if tuple(candidates_by_component) != scope.advanced_component_ids:
            raise ValueError("Template route componentCandidates do not match selected Scope")
    for component_id in scope.advanced_component_ids:
        capability = registry.require_ux_business_component(component_id)
        options = _component_template_coverage_options(
            capability,
            task_spec,
            registry,
            effective_ids,
            card_spec,
        )
        if not options:
            raise ValueError(
                f"Template route component has no applicable Provider Template: {component_id}"
            )
        if component_candidates is None:
            continue
        prompt_contracts = _component_template_prompt_contracts(
            capability,
            task_spec,
            registry,
            effective_ids,
            card_spec,
        )
        allowed_template_ids = {item["templateId"] for item in prompt_contracts}
        selected_template_ids = candidates_by_component[component_id]
        if not set(selected_template_ids).issubset(allowed_template_ids):
            raise ValueError(
                "Template route selected an unavailable Provider Template: "
                f"{component_id}"
            )


async def plan_advanced_scope_with_llm(
    task_spec: TaskSpec,
    data_shape: DataShape,
    generate_json: Callable[[list[dict[str, str]], str], Awaitable[dict[str, Any]]],
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None = None,
) -> AdvancedScopeBrief:
    prompt = build_advanced_scope_prompt(
        task_spec,
        data_shape,
        registry,
        available_capability_ids,
    )
    raw = await generate_json(prompt, "advanced-component-scope")
    raw = _normalize_empty_component_scope(
        raw,
        task_spec,
        registry,
        available_capability_ids,
    )
    try:
        scope = AdvancedScopeBrief.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid AdvancedScopeBrief: {exc}") from exc
    scope = _normalize_redundant_2x2_support(scope, task_spec)
    scope = _normalize_2x2_two_support_theme(scope, task_spec, registry)
    try:
        validate_advanced_scope(
            scope,
            task_spec,
            data_shape,
            registry,
            available_capability_ids,
        )
    except ValueError as exc:
        if str(exc) == "AdvancedScopeBrief selected a Theme outside component palettes":
            scope = _normalize_scope_to_shared_theme(scope, registry)
            validate_advanced_scope(
                scope,
                task_spec,
                data_shape,
                registry,
                available_capability_ids,
            )
            return scope
        if str(exc) != "AdvancedScopeBrief has no compatible UX layout":
            raise
        try:
            scope = _normalize_scope_to_compatible_layout(scope, task_spec, registry)
            scope = _normalize_2x2_two_support_theme(scope, task_spec, registry)
        except ValueError:
            raise
        validate_advanced_scope(
            scope,
            task_spec,
            data_shape,
            registry,
            available_capability_ids,
        )
    return scope


async def plan_template_route_with_llm(
    task_spec: TaskSpec,
    data_shape: DataShape,
    generate_json: Callable[[list[dict[str, str]], str], Awaitable[dict[str, Any]]],
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    available_capability_ids: tuple[str, ...] | None = None,
    card_spec: dict[str, Any] | None = None,
) -> TemplateRouteSelection:
    """由首层 LLM 决定模板路由，并用 Provider 契约做确定性完整覆盖复核。"""
    prompt = build_advanced_scope_prompt(
        task_spec,
        data_shape,
        registry,
        available_capability_ids,
        template_route_decision=True,
        coverage_bindings=coverage_bindings,
        card_spec=card_spec,
    )
    raw = await generate_json(prompt, "template-route-decision")
    try:
        decision = TemplateRouteDecision.model_validate(raw)
    except ValidationError as exc:
        raise TemplateRouteNotApplicable("invalid TemplateRouteDecision") from exc
    return validate_template_route_decision(
        decision,
        task_spec,
        data_shape,
        registry,
        coverage_bindings,
        available_capability_ids,
        card_spec,
    )


def validate_template_route_decision(
    decision: TemplateRouteDecision,
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    available_capability_ids: tuple[str, ...] | None = None,
    card_spec: dict[str, Any] | None = None,
) -> TemplateRouteSelection:
    """让 LLM 或 Search 的同构结果复用同一套确定性模板路由门禁。"""
    if not decision.component_candidates:
        raise TemplateRouteNotApplicable("first-layer decision rejected the Template route")
    scope = AdvancedScopeBrief(
        themeId=decision.theme,
        advancedComponentIds=decision.component_ids,
    )
    scope = _normalize_redundant_2x2_support(scope, task_spec)
    scope = _normalize_2x2_two_support_theme(scope, task_spec, registry)
    selected_component_ids = set(scope.advanced_component_ids)
    component_candidates = tuple(
        candidate
        for candidate in decision.component_candidates
        if candidate.component_id in selected_component_ids
    )
    try:
        selected_task_spec = task_spec_with_selected_action(
            task_spec,
            decision.action_ids,
        )
        validate_advanced_scope(
            scope,
            selected_task_spec,
            data_shape,
            registry,
            available_capability_ids,
        )
        validate_template_request_coverage(
            scope,
            task_spec,
            registry,
            coverage_bindings,
            card_spec,
            component_candidates,
        )
    except ValueError as exc:
        raise TemplateRouteNotApplicable(str(exc)) from exc
    return TemplateRouteSelection(
        scope=scope,
        componentCandidates=component_candidates,
        actionIds=decision.action_ids,
    )


def _normalize_scope_to_shared_theme(
    scope: AdvancedScopeBrief,
    registry: CardPlanRegistry,
) -> AdvancedScopeBrief:
    components = tuple(
        registry.require_ux_business_component(item) for item in scope.advanced_component_ids
    )
    if len({component.domain_id for component in components}) <= 1:
        raise ValueError("AdvancedScopeBrief selected a Theme outside component palettes")
    theme_ids = _theme_ids_for_components(components, registry)
    if not theme_ids:
        raise ValueError("AdvancedScopeBrief selected a Theme outside component palettes")
    return scope.model_copy(update={"theme_id": theme_ids[0]})


def _normalize_2x2_two_support_theme(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> AdvancedScopeBrief:
    if task_spec.size != "2x2" or len(scope.advanced_component_ids) != 2:
        return scope
    components = tuple(
        registry.require_ux_business_component(item)
        for item in scope.advanced_component_ids
    )
    if any(
        not _component_has_layout_suffix(component, "Support", registry)
        for component in components
    ):
        return scope
    capability_ids = tuple(
        sorted(
            {
                capability_id
                for component in components
                for capability_id in component.data_capability_ids
            }
        )
    )
    theme_id = registry.require_layout_theme("TwoSupportLayout", capability_ids)
    return scope.model_copy(update={"theme_id": theme_id})


def validate_advanced_scope(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None = None,
) -> None:
    del data_shape
    effective_ids = resolve_available_capability_ids(
        task_spec,
        registry,
        available_capability_ids,
    )
    candidates = _component_candidates(
        task_spec,
        extract_shape=None,
        registry=registry,
        available_capability_ids=effective_ids,
    )
    candidate_ids = {item.name for item in candidates}
    selected_ids = set(scope.advanced_component_ids)
    if not selected_ids.issubset(candidate_ids):
        raise ValueError("AdvancedScopeBrief selected a component outside trusted candidates")
    if (
        not advanced_component_data_admission_is_bypassed()
        and selected_ids == {"ActivityOverview", "SleepOverview"}
        and not sleep_overview_has_trusted_data(task_spec)
    ):
        raise ValueError("ActivityOverview cannot compose with an untrusted SleepOverview")
    if (
        "DateOverview" in selected_ids
        and len(selected_ids) > 1
        and "ScheduleOverview" not in selected_ids
    ):
        raise ValueError("DateOverview multi-business scope requires ScheduleOverview")
    budget = registry.ux_size_budgets[task_spec.size]
    if len(scope.advanced_component_ids) > budget.max_business_components:
        raise ValueError("AdvancedScopeBrief exceeds the size component budget")
    components = tuple(
        registry.require_ux_business_component(item) for item in scope.advanced_component_ids
    )
    if any(not item.enabled_variants(effective_ids) for item in components):
        raise ValueError("AdvancedScopeBrief selected a component without a production provider")
    if any(task_spec.size not in item.supported_card_sizes for item in components):
        raise ValueError("AdvancedScopeBrief selected a component unsupported by card size")
    allowed_themes = set(_theme_ids_for_scope(components, task_spec, registry))
    if scope.theme_id not in allowed_themes:
        raise ValueError("AdvancedScopeBrief selected a Theme outside component palettes")
    if not resolve_scope_layout_ids(scope, task_spec, registry):
        raise ValueError("AdvancedScopeBrief has no compatible UX layout")


def _normalize_scope_to_compatible_layout(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> AdvancedScopeBrief:
    """Drop the least-prioritized scope items only when no common layout exists."""
    values = scope.advanced_component_ids
    for size in range(len(values) - 1, 0, -1):
        for candidate_ids in combinations(values, size):
            candidate = scope.model_copy(update={"advanced_component_ids": tuple(candidate_ids)})
            components = tuple(
                registry.require_ux_business_component(item) for item in candidate_ids
            )
            if scope.theme_id not in set(
                _theme_ids_for_scope(components, task_spec, registry)
            ):
                continue
            if resolve_scope_layout_ids(candidate, task_spec, registry):
                return candidate
    raise ValueError("AdvancedScopeBrief has no compatible UX layout")


def _normalize_redundant_2x2_support(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
) -> AdvancedScopeBrief:
    """Keep one atomic owner when a 2x2 content component already owns its context."""
    if task_spec.size != "2x2":
        return scope
    selected = list(scope.advanced_component_ids)
    selected_set = set(selected)
    for pair, redundant_id in _REDUNDANT_2X2_SUPPORTS.items():
        if redundant_id == "DateOverview" and _query_explicitly_requests_date(task_spec.userQuery):
            continue
        if pair.issubset(selected_set):
            selected.remove(redundant_id)
            selected_set.remove(redundant_id)
    if tuple(selected) == scope.advanced_component_ids:
        return scope
    return scope.model_copy(update={"advanced_component_ids": tuple(selected)})


def _query_explicitly_requests_date(query: str) -> bool:
    return date_overview_query_is_supported(query, "2x2")


def _normalize_empty_component_scope(
    raw: dict[str, Any],
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if raw.get("advancedComponentIds") != []:
        return raw
    theme_id = raw.get("themeId")
    if not isinstance(theme_id, str):
        return raw
    selected = next(
        (
            item.name
            for item in _component_candidates(
                task_spec,
                extract_shape=None,
                registry=registry,
                available_capability_ids=resolve_available_capability_ids(
                    task_spec,
                    registry,
                    available_capability_ids,
                ),
            )
            if theme_id in _theme_ids_for_components((item,), registry)
        ),
        None,
    )
    if selected is None:
        return raw
    normalized = dict(raw)
    normalized["advancedComponentIds"] = [selected]
    return normalized


def task_spec_with_selected_action(
    task_spec: TaskSpec,
    action_ids: tuple[str, ...] | str | None,
) -> TaskSpec:
    """Keep only the eventIds independently selected by the first-layer LLM."""
    if action_ids is None:
        selected_ids = ()
    elif isinstance(action_ids, str):
        selected_ids = (action_ids,)
    else:
        selected_ids = action_ids
    available_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if not set(selected_ids).issubset(available_ids):
        raise ValueError("Template route selected an Action outside TaskSpec.eventCandidates")
    return task_spec.model_copy(
        update={
            "eventCandidates": [
                event for event in task_spec.eventCandidates if event.id in selected_ids
            ]
        }
    )


def resolve_scope_layout_ids(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    components = tuple(
        registry.require_ux_business_component(item) for item in scope.advanced_component_ids
    )
    count = len(components)
    action_count = len(task_spec.eventCandidates)
    common = set(registry.ux_layout_components)
    for capability in components:
        common &= set(capability.supported_layouts)
    allowed: list[str] = []
    for layout_id in common:
        if not registry.template_is_enabled(f"{layout_id}@1"):
            continue
        layout = registry.require_ux_layout_component(layout_id)
        if task_spec.size not in layout.supported_card_sizes:
            continue
        if layout_id == "TwoSupportLayout":
            missing_support = any(
                not _component_has_layout_suffix(component, "Support", registry)
                for component in components
            )
            if missing_support:
                continue
        if layout_id == "HeroTitleContentActionLayout":
            has_required_slot_shapes = len(components) == 2
            if has_required_slot_shapes:
                has_hero_title = _component_has_layout_suffix(
                    components[0],
                    "HeroTitle",
                    registry,
                )
                has_hero_content = _component_has_layout_suffix(
                    components[1],
                    "HeroContent",
                    registry,
                )
                has_required_slot_shapes = has_hero_title and has_hero_content
            if not has_required_slot_shapes:
                continue
        if (
            not layout.minimum_children(task_spec.size)
            <= count
            <= layout.max_children_by_size[task_spec.size]
        ):
            continue
        direct_action_count = 0 if layout_id == "TwoSupportLayout" else action_count
        if direct_action_count < layout.min_action_children_by_size[task_spec.size]:
            continue
        if direct_action_count > layout.max_action_children_by_size[task_spec.size]:
            continue
        allowed.append(layout_id)
    return tuple(sorted(allowed, key=lambda item: _layout_rank(item, count, action_count)))


def _component_has_layout_suffix(
    component: BusinessTemplateGroup,
    suffix: str,
    registry: CardPlanRegistry,
) -> bool:
    for template_id in component.local_template_ids:
        if not registry.template_is_enabled(template_id):
            continue
        template_name = template_id.rpartition("@")[0]
        if template_name.endswith(suffix):
            return True
    return False


def scope_template_ids(
    scope: AdvancedScopeBrief,
    registry: CardPlanRegistry,
    task_spec: TaskSpec | None = None,
    *,
    preferred_template_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    declared_template_ids = tuple(
        dict.fromkeys(
            template_id
            for component_id in scope.advanced_component_ids
            for capability in (registry.require_ux_business_component(component_id),)
            if capability.implementation == "template"
            for template_id in registry.enabled_template_ids(capability.local_template_ids)
        )
    )
    preferred = tuple(
        template_id
        for template_id in preferred_template_ids
        if template_id in declared_template_ids
    )
    template_ids = tuple(dict.fromkeys((*preferred, *declared_template_ids)))
    if task_spec is None or advanced_component_data_admission_is_bypassed():
        return template_ids
    return tuple(
        template_id
        for template_id in template_ids
        if _template_has_satisfiable_variant(template_id, task_spec, registry)
    )


def _template_has_satisfiable_variant(
    template_id: str,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> bool:
    definition = registry.require_template(template_id)
    if not provider_template_context_admission(definition, task_spec).admitted:
        return False
    field_names = _schema_field_names(task_spec.dataModelSchema)
    has_assets = any(item.get("src") for item in task_spec.assetCandidates)
    has_actions = bool(task_spec.eventCandidates)
    has_numbers = any(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in _schema_values(task_spec.dataModelSchema)
    )
    for variant in definition.variants:
        properties = variant.parameters_schema.get("properties", {})
        required = variant.parameters_schema.get("required", ())
        if all(
            _required_parameter_is_satisfiable(
                name,
                properties.get(name, {}),
                field_names=field_names,
                has_assets=has_assets,
                has_actions=has_actions,
                has_numbers=has_numbers,
            )
            for name in required
        ):
            return True
    return False


def _required_parameter_is_satisfiable(
    name: str,
    schema: dict[str, Any],
    *,
    field_names: set[str],
    has_assets: bool,
    has_actions: bool,
    has_numbers: bool,
) -> bool:
    semantic = _normalize(f"{name} {schema.get('description', '')}")
    if any(
        token in semantic
        for token in ("icon", "image", "asset", "source", "src", "图标", "图片", "素材", "资源")
    ):
        return has_assets
    if any(token in semantic for token in ("action", "event", "操作", "事件")):
        return has_actions
    if schema.get("type") in {"number", "integer"}:
        return has_numbers
    normalized_name = _normalize(name)
    return any(
        normalized_name == field
        or (len(normalized_name) >= 4 and normalized_name in field)
        or (len(field) >= 4 and field in normalized_name)
        for field in field_names
    )


def _schema_field_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            names.add(_normalize(str(key)))
            names.update(_schema_field_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_schema_field_names(item))
    return names


def _schema_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _schema_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _schema_values(item)
    else:
        yield value


def resolve_available_capability_ids(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    explicit_ids: tuple[str, ...] | None = None,
) -> set[str]:
    """Resolve trusted providers from CardSpec IDs or legacy test schema keys."""
    known_ids = {
        capability_id
        for component in registry.ux_business_components.values()
        for capability_id in component.data_capability_ids
    }
    if explicit_ids is not None:
        return set(explicit_ids) & known_ids

    discovered: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in known_ids:
                    discovered.add(key)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(task_spec.dataModelSchema)
    return discovered


def _component_candidates(
    task_spec: TaskSpec,
    extract_shape: DataShape | None,
    registry: CardPlanRegistry,
    available_capability_ids: set[str],
) -> tuple[BusinessTemplateGroup, ...]:
    schema_parts = [json.dumps(task_spec.dataModelSchema, ensure_ascii=False)]
    if extract_shape is not None:
        schema_parts.append(
            " ".join(
                f"{field.path} {field.name} {field.description} {' '.join(field.roles)}"
                for field in extract_shape.fields
            )
        )
    schema_text = _normalize(" ".join(schema_parts))
    query_text = _normalize(task_spec.userQuery)
    admission_relaxed = advanced_component_data_admission_is_bypassed()
    scored = [
        (
            sum(_detection_term_matches(term, schema_text) for term in item.detection_terms),
            sum(_detection_term_matches(term, query_text) for term in item.detection_terms),
            item,
        )
        for item in registry.ux_business_components.values()
        if task_spec.size in item.supported_card_sizes
        and bool(item.enabled_variants(available_capability_ids))
        and (
            admission_relaxed
            or (
                (
                    item.name != "ActivityOverview"
                    or activity_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "WorkoutOverview"
                    or workout_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "CountdownOverview"
                    or countdown_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "HeartRateOverview"
                    or heart_rate_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "SleepOverview"
                    or sleep_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "WeatherOverview"
                    or weather_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "DateOverview"
                    or date_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "ScheduleOverview"
                    or schedule_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "CalendarOverview"
                    or date_overview_is_eligible(task_spec, available_capability_ids)
                    or schedule_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "BatteryOverview"
                    or battery_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "BluetoothDeviceOverview"
                    or bluetooth_device_overview_is_eligible(
                        task_spec,
                        available_capability_ids,
                    )
                )
                and (
                    item.name != "ResourceUsageOverview"
                    or resource_usage_overview_is_eligible(task_spec, available_capability_ids)
                )
                and (
                    item.name != "AppUsageOverview"
                    or app_usage_overview_is_eligible(task_spec, available_capability_ids)
                )
            )
        )
    ]
    ranked = sorted(scored, key=lambda pair: (-pair[0], -pair[1], pair[2].name))
    schema_positive = [item for schema_score, _query_score, item in ranked if schema_score > 0]
    query_positive = [item for _schema_score, query_score, item in ranked if query_score > 0]
    fallback = [item for _schema_score, _query_score, item in ranked]
    matched_by_name = {item.name: item for item in [*schema_positive, *query_positive]}
    matched = tuple(matched_by_name.values())
    return tuple((matched or tuple(fallback))[:8])


def _compatible_component_ids(
    capability: BusinessTemplateGroup,
    candidate_ids: set[str],
    size: WidgetSize,
    user_query: str,
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    compatible: list[str] = []
    own_layouts = set(capability.supported_layouts)
    for component_id in sorted(candidate_ids):
        if component_id == capability.name:
            continue
        pair = frozenset((capability.name, component_id))
        if not _health_pair_is_approved(pair):
            continue
        if "ResourceUsageOverview" in pair and "BatteryOverview" not in pair:
            continue
        if "BluetoothDeviceOverview" in pair and "BatteryOverview" not in pair:
            continue
        if "DateOverview" in pair and "ScheduleOverview" not in pair:
            continue
        if size == "2x2":
            redundant_id = _REDUNDANT_2X2_SUPPORTS.get(pair)
            if redundant_id is not None and not (
                redundant_id == "DateOverview" and _query_explicitly_requests_date(user_query)
            ):
                continue
        candidate = registry.require_ux_business_component(component_id)
        shared = own_layouts & set(candidate.supported_layouts)
        has_compatible_layout = False
        for layout_id in shared:
            layout = registry.require_ux_layout_component(layout_id)
            if size not in layout.supported_card_sizes:
                continue
            minimum_children = layout.minimum_children(size)
            maximum_children = layout.max_children_by_size.get(size)
            if maximum_children is None:
                continue
            if minimum_children <= 2 <= maximum_children:
                has_compatible_layout = True
                break
        if has_compatible_layout:
            compatible.append(component_id)
    return tuple(compatible)


def _effective_candidate_variants(
    capability: BusinessTemplateGroup,
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    if advanced_component_data_admission_is_bypassed():
        return capability.enabled_variants(capability_ids)
    if capability.name == "ActivityOverview":
        return activity_overview_variants(task_spec, capability_ids)
    if capability.name == "WorkoutOverview":
        return workout_overview_variants(task_spec, capability_ids)
    if capability.name == "CountdownOverview":
        return countdown_overview_variants(task_spec, capability_ids)
    if capability.name == "SleepOverview":
        return sleep_overview_variants(task_spec, capability_ids)
    if capability.name == "BluetoothDeviceOverview":
        return bluetooth_device_overview_variants(task_spec, capability_ids)
    return capability.enabled_variants(capability_ids)


def advanced_component_data_admission_is_bypassed() -> bool:
    """Relax first-layer admission only in the active explicit batch request."""
    return _content_selectors.advanced_component_data_admission_is_relaxed()


def get_settings():
    """Proxy settings lookup so batch-bypass tests can isolate either module boundary."""
    return _content_selectors.get_settings()


def _health_pair_is_approved(pair: frozenset[str]) -> bool:
    health_ids = {"ActivityOverview", "HeartRateOverview", "WorkoutOverview"}
    if not pair & health_ids:
        return True
    return pair in {
        frozenset(("ActivityOverview", "SleepOverview")),
        frozenset(("ActivityOverview", "HeartRateOverview")),
        frozenset(("ActivityOverview", "WorkoutOverview")),
    }


def _theme_ids_for_components(
    components: tuple[BusinessTemplateGroup, ...],
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    return registry.first_layer_theme_ids(tuple(component.name for component in components))


def _theme_ids_for_scope(
    components: tuple[BusinessTemplateGroup, ...],
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    theme_ids = _theme_ids_for_components(components, registry)
    if task_spec.size != "2x2" or len(components) != 2:
        return theme_ids
    capability_ids = tuple(
        sorted(
            {
                capability_id
                for component in components
                for capability_id in component.data_capability_ids
            }
        )
    )
    layout_theme_ids = registry.layout_theme_ids("TwoSupportLayout", capability_ids)
    return tuple(dict.fromkeys((*theme_ids, *layout_theme_ids)))


def _layout_rank(layout_id: str, count: int, action_count: int) -> tuple[int, str]:
    preferred: dict[tuple[int, int], tuple[str, ...]] = {
        (1, 0): ("SingleFocusLayout", "WideSingleFocusLayout"),
        (1, 1): (
            "HeroActionLayout",
            "FullIconActionLayout",
            "SingleFocusLayout",
            "WideSingleFocusLayout",
        ),
        (1, 2): ("CompactTwoActionLayout",),
        (2, 0): ("TwoSupportLayout",),
        (2, 1): ("HeroTitleContentActionLayout", "TwoSupportLayout"),
        (2, 2): ("TwoSupportLayout",),
    }
    order = preferred.get((count, action_count), ())
    return (order.index(layout_id) if layout_id in order else len(order), layout_id)


def _normalize(value: str) -> str:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return re.sub(r"[\s_./:-]+", " ", camel_split.casefold())


def _detection_term_matches(term: str, normalized_text: str) -> bool:
    """Match Latin detection terms by token boundary and CJK terms by phrase."""
    normalized_term = _normalize(term).strip()
    if not normalized_term:
        return False
    if re.search(r"[\u3400-\u9fff]", normalized_term):
        return normalized_term.replace(" ", "") in normalized_text.replace(" ", "")
    term_tokens = tuple(re.findall(r"[a-z0-9]+", normalized_term))
    text_tokens = set(re.findall(r"[a-z0-9]+", normalized_text))
    return bool(term_tokens) and all(
        any(
            text_token == term_token
            or (len(term_token) >= 4 and text_token in {f"{term_token}s", f"{term_token}es"})
            for text_token in text_tokens
        )
        for term_token in term_tokens
    )
