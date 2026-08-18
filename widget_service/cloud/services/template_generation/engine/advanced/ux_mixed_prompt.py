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
    activity_overview_variants,
    advanced_component_data_admission_is_relaxed,
    approved_app_usage_action_ids,
    approved_battery_power_action_ids,
    approved_bluetooth_music_action_ids,
    approved_memory_cleanup_action_ids,
    approved_schedule_action_ids,
    approved_sleep_action_ids,
    approved_workout_action_ids,
    extract_app_usage_overview_facts,
    extract_battery_overview_facts,
    extract_bluetooth_device_overview_facts,
    extract_heart_rate_overview_facts,
    extract_resource_usage_overview_facts,
    extract_schedule_overview_facts,
    extract_sleep_overview_facts,
    extract_weather_overview_facts,
    relaxed_activity_overview_variants,
    relaxed_workout_overview_variants,
    schedule_query_requests_focus,
    sleep_overview_variants,
    workout_overview_variants,
)
from .models import AdvancedScopeBrief, UxBusinessComponentCapability
from .scope_planner import (
    resolve_available_capability_ids,
    resolve_scope_layout_ids,
    scope_template_ids,
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
    task_spec = _task_spec_with_scope_actions(task_spec, components)
    allowed_layout_ids = resolve_scope_layout_ids(scope, task_spec, registry)
    if not allowed_layout_ids:
        raise ValueError("Advanced Scope has no compatible UX layout")
    bridge = _ScopePromptBridge(
        theme_id=scope.theme_id,
        local_template_ids=scope_template_ids(scope, registry, task_spec),
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
    required_template_groups = tuple(
        _required_template_group(component.local_template_ids, base.requested_template_ids)
        for component in template_components
    )
    if any(not group for group in required_template_groups):
        raise ValueError("Advanced Scope component has no satisfiable trusted Template")
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
            "required_template_groups": required_template_groups,
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
            f"- {layout.name}([config], child1, ...): {layout.description}; "
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
            task_spec,
        )
        for component in components
    ]
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
            "最终输出必须直接以唯一批准的布局高级组件为根并以分号结束；禁止 card@1。",
        )
    )
    user_suffix = "\n".join(
        (
            "trustedStringLiterals=" + json.dumps(contract.trusted_literals, ensure_ascii=False),
            "trustedAssetSources=" + json.dumps(contract.allowed_asset_sources, ensure_ascii=False),
            "uxAdvancedScope=" + json.dumps(scope.model_dump(by_alias=True), ensure_ascii=False),
            "allowedUxLayouts=" + json.dumps(allowed_layout_ids, ensure_ascii=False),
            "requiredLocalTemplateGroups="
            + json.dumps(required_template_groups, ensure_ascii=False),
            "directBusinessComponents=" + json.dumps(direct_components, ensure_ascii=False),
            "业务高级组件字段由服务端绑定到 TaskSpec.dataModelSchema 的端侧数据路径；"
            "最终有效 TerseDSL 使用完整 `${data.weather.temperature}` 占位值，模型不得编造路径。",
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
    task_spec: TaskSpec,
) -> str:
    common = (
        f"- {component.name}: {component.description}; "
        f"variants={list(component.enabled_variants(capability_ids))}; "
        f"roles={list(component.roles)}; maxItems={component.max_items_by_size[size]}"
    )
    if component.implementation == "terse-dsl":
        if component.name == "ActivityOverview":
            variants = (
                relaxed_activity_overview_variants(task_spec, capability_ids)
                if advanced_component_data_admission_is_relaxed()
                else activity_overview_variants(task_spec, capability_ids)
            )
            if not variants:
                raise ValueError("ActivityOverview has no query-backed trusted variant")
            return (
                common
                + "; effectiveVariants="
                + json.dumps(variants, ensure_ascii=False)
                + '; syntax=ActivityOverview({"variant":"steps|dailySummary",'
                '"role":"hero|support","stepsIcon?":"<trustedAssetSources item>",'
                '"caloriesIcon?":"<trustedAssetSources item>",'
                '"distanceIcon?":"<trustedAssetSources item>"}); '
                "不得输出步数、热量、距离、目标、比例、状态、样式、尺寸、Ring、Progress、Action 或 "
                "Template；服务端从可信投影确定性展开。图标均可省略；引用时必须逐字复制 "
                "trustedAssetSources 中与 steps/activity、calories/energy、distance/route 分别语义"
                "匹配的素材。单业务使用 hero；与 Sleep/HeartRate 组合时 Activity 必须是首个 hero；"
                "与 Workout "
                "组合时 Activity 必须是第二个 support。"
            )
        if component.name == "WorkoutOverview":
            variants = (
                relaxed_workout_overview_variants(task_spec, capability_ids)
                if advanced_component_data_admission_is_relaxed()
                else workout_overview_variants(task_spec, capability_ids)
            )
            if not variants:
                raise ValueError("WorkoutOverview has no query-backed trusted variant")
            return (
                common
                + "; effectiveVariants="
                + json.dumps(variants, ensure_ascii=False)
                + '; syntax=WorkoutOverview({"variant":"latest|countdown","role":"hero",'
                '"sourceIcon?":"<trustedAssetSources item>",'
                '"caloriesIcon?":"<trustedAssetSources item>"}); '
                "不得输出运动类型、时长、热量、倒计时天数、赛事名、训练计划、状态、距离、配速、"
                "轨迹、心率区间、总量、比例、样式、尺寸、Ring、Progress 或 Template；服务端从可信"
                "投影确定性展开。图标可省略；引用时必须逐字复制 sport/workout 或 calories/energy "
                "语义匹配素材。Action 只允许布局末尾 PillAction，且只使用本轮批准的 "
                "event.open.health.sport；没有批准 contentActions 时必须使用无动作布局。与 "
                "Activity "
                "组合时 Workout 必须是首个 hero，Activity 为 support。"
            )
        if component.name == "HeartRateOverview":
            return (
                common + '; effectiveVariants=["average"]; '
                'syntax=HeartRateOverview({"variant":"average","role":"hero|support",'
                '"sourceIcon?":"<trustedAssetSources item>"}); '
                "不得输出心率值、更新时间、current/attention、state、异常结论、区间、趋势、波形、"
                "最大/最低心率、样式、尺寸、Ring、Progress、Action 或 Template；服务端只展开可信"
                "运动平均心率和可选更新时间。sourceIcon 可省略；引用时必须逐字复制 "
                "trustedAssetSources 中与 heart/heart-rate/pulse 语义匹配的素材。多业务时必须位于"
                "第二个"
                " child 并使用 support。"
            )
        if component.name == "SleepOverview":
            variants = sleep_overview_variants(task_spec, capability_ids)
            if not variants:
                raise ValueError("SleepOverview has no query-backed trusted variant")
            return (
                common
                + "; effectiveVariants="
                + json.dumps(variants, ensure_ascii=False)
                + '; syntax=SleepOverview({"variant":"duration|insufficient|schedule",'
                '"role":"hero|support","sourceIcon?":'
                '"<trustedAssetSources item>"}); '
                "不得输出 sleepStatus、时长、入睡/醒来时刻、派生数值/单位、样式、尺寸、"
                "Ring、Progress、阶段图、建议、Action 或 Template；服务端只从同一可信睡眠"
                "记录确定性展开。上游因批测宽松准入的得分、阶段、午睡、目标、趋势、建议或"
                "缺失状态/作息请求也只能按 effectiveVariants 输出，通常降级 duration，不得补造。"
                "sourceIcon 可省略；引用时必须逐字复制 trustedAssetSources "
                "中与 sleep/moon/alarm 语义匹配的一项。2x2 单业务使用 hero，只展示标题与"
                "双值总时长；多业务 Sleep 固定为第二个 support。2x4 单业务内部使用总时长 Hero "
                "与入睡/醒来 Support；多业务可由 HeroSupportLayout 或 SequentialSummaryLayout "
                "表达主辅关系。Action 只允许布局末尾 PillAction，actionId 只能是本轮批准的 "
                "event.open.clock.alarm；没有批准 contentActions 时必须使用无动作布局。"
            )
        if component.name == "AppUsageOverview":
            facts = extract_app_usage_overview_facts(task_spec.dataModelSchema)
            if facts is None:
                raise ValueError("AppUsageOverview has no complete trusted single-app facts")
            return (
                common + '; effectiveVariants=["singleApp"]; '
                'syntax=AppUsageOverview({"variant":"singleApp","role":"hero",'
                '"appIcon?":"<trustedAssetSources item>"}); '
                "不得输出 appName、durationText、updatedAt、数值片段、样式、尺寸、进度、"
                "限额、超限、排行、状态或 Template；服务端仅从同一可信数据树的三项原始"
                "字段和无损时长解析结果确定性展开。appIcon 可省略；引用时必须逐字复制 "
                "trustedAssetSources 中与 app/application 语义匹配的一项。单业务必须使用 "
                "hero；小时和分钟始终位于同一 Row。Action 只能是布局末尾的 PillAction，"
                "actionId 只能使用本轮批准的 event.open.settings.parentControl；动作图标只能"
                "从 trustedAssetSources 中与 timer/settings/parental-control 语义匹配的素材"
                "选择，缺素材时省略。没有批准 contentActions 时必须使用无动作布局。"
            )
        if component.name == "DateOverview":
            return (
                common + '; syntax=DateOverview({"variant":"compactDate|dateHero",'
                '"role":"hero|support"}); '
                "不得输出业务字段、样式、尺寸、图标、Action 或 Template。单业务 2x2/2x4 使用 "
                "dateHero+hero；多业务 2x2 使用 compactDate+support 且日期位于首个业务 child；"
                "多业务 2x4 使用 dateHero+hero 且位于左侧。服务端仅从可信 date/weekday "
                "确定性展开。"
            )
        if component.name == "ScheduleOverview":
            facts = extract_schedule_overview_facts(task_spec.dataModelSchema)
            variants = ["nextEvent", "meetingCompact"]
            if facts is not None and facts.location is not None:
                variants.append("meetingExpanded")
            if schedule_query_requests_focus(task_spec.userQuery) and approved_schedule_action_ids(
                task_spec
            ):
                variants.append("focusContext")
            return (
                common
                + "; effectiveVariants="
                + json.dumps(variants, ensure_ascii=False)
                + '; syntax=ScheduleOverview({"variant":"nextEvent|meetingCompact|'
                'meetingExpanded|focusContext","role":"hero|support",'
                '"sourceIcon?":"<trustedAssetSources item>",'
                '"timeIcon?":"<trustedAssetSources item>",'
                '"locationIcon?":"<trustedAssetSources item>"}); '
                "不得输出 title/timeText/location、样式、尺寸、Action 或 Template；服务端只从"
                "同一可信首项日程展开。meetingExpanded 仅在 location 存在时使用，否则服务端"
                "确定性降级 meetingCompact。source/time/location 图标可省略；引用时必须逐字"
                "复制 trustedAssetSources 中语义匹配的素材。Action 只能作为布局末尾 child，"
                "actionId 只能来自本轮 approved contentActions，图标也必须语义匹配。"
            )
        if component.name == "ResourceUsageOverview":
            facts = extract_resource_usage_overview_facts(task_spec.dataModelSchema)
            if facts is None:
                raise ValueError("ResourceUsageOverview has no complete trusted memory facts")
            return (
                common + '; effectiveVariants=["memory"]; '
                'syntax=ResourceUsageOverview({"variant":"memory",'
                '"role":"hero|peer","icon?":"<trustedAssetSources item>",'
                '"showTitle?":false}); '
                "不得输出 usagePercent、availableMemText、totalMemText、freeMemText、state、"
                "样式、尺寸或 Template；服务端仅从可信三字段确定性展开。icon 可省略；"
                "引用时必须逐字复制 trustedAssetSources 中与 memory/resource 语义匹配的素材。"
                "禁止 storage 变体和压力状态文案。单业务使用 hero 且不得关闭内部标题；"
                "2x2 与 Battery 组合必须用 PeerPairLayout+peer，并对两个构造器都显式设置 "
                "showTitle=false，由服务端在高级组件之外写独立总标题；2x4 与 Battery 组合时 "
                "ResourceUsageOverview "
                "必须是首个 hero，Battery 为 Support。清理 Action 只能使用本轮批准的 "
                "event.clean.memory，并作为布局末尾 child；动作图标必须来自语义匹配素材，"
                "缺素材时省略图标。"
            )
        if component.name == "BatteryOverview":
            facts = extract_battery_overview_facts(task_spec.dataModelSchema)
            if facts is None:
                raise ValueError("BatteryOverview has no complete trusted phone battery facts")
            return (
                common
                + "; effectiveVariants="
                + json.dumps([facts.state], ensure_ascii=False)
                + '; syntax=BatteryOverview({"variant":"normal|charging|low",'
                '"role":"hero|support|peer",'
                '"batteryIcon?":"<trustedAssetSources item>","showTitle?":false}); '
                "不得输出 SOC、SOC 文本、电量等级、充电状态、续航/预计充满时间、健康度、"
                "温度、电压、电流、充电器类型、样式、尺寸或 Template；服务端仅从可信四字段"
                "确定性展开。batteryIcon 可省略，引用时必须逐字复制 trustedAssetSources 中"
                "与 battery/power 语义匹配的素材。单业务用 hero 且不得关闭内部标题；与 "
                "ResourceUsageOverview 的 2x2 对等组合必须对两个构造器都显式设置 "
                "showTitle=false，由服务端在高级组件之外写独立总标题；手机+耳机多业务必须用 "
                "PeerPairLayout+peer，两个业务区使用对等 Ring，且不得输出标题区来源图标。"
                "2x2 省电动作必须是末尾 IconAction，并同时有批准事件与 power-saving 语义"
                "素材；2x4 可用末尾 PillAction。没有批准 contentActions 时必须使用无动作布局。"
            )
        if component.name == "BluetoothDeviceOverview":
            facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
            if facts is None:
                raise ValueError("BluetoothDeviceOverview has no compatible trusted earphone facts")
            return (
                common + '; effectiveVariants=["earbuds"]; '
                'syntax=BluetoothDeviceOverview({"variant":"earbuds",'
                '"role":"hero|support|peer",'
                '"sourceIcon?":"<trustedAssetSources item>",'
                '"leftEarIcon?":"<trustedAssetSources item>",'
                '"rightEarIcon?":"<trustedAssetSources item>"}); '
                "不得输出连接态、设备名、盒/左/右电量、充电状态、更新时间、播放态、曲目、进度、"
                "样式、尺寸、业务图标 ID 或 Template；服务端只从可信投影确定性展开。sourceIcon "
                "与左右耳图标均可省略；引用时必须逐字复制 trustedAssetSources 中与"
                "耳机/audio/product "
                "语义匹配的素材，不能自行生成路径。单业务使用 hero；2x2 有音乐事件时使用一个末尾 "
                "PillAction，2x4 可用 ActionMatrixLayout + 最多两个末尾 ActionTile。"
                "actionId 只能使用"
                "本轮批准的 event.open.music.daily/favorite，动作图标必须分别匹配 music 或"
                "favorite/heart 语义；没有批准 contentActions 时必须使用无动作布局。手机+耳机"
                "组合不得带动作：2x2 使用 PeerPairLayout，2x4 使用 HeroSupportLayout；"
                "BatteryOverview 必须在前且为 hero，本组件在后且为 support。"
            )
        return (
            common + '; syntax=WeatherOverview({"variant":"current|commute",'
            '"role":"hero|support|peer","conditionIcon":"<trustedAssetSources item>"}); '
            "conditionIcon 必须由本轮第二步模型显式选择，且只能逐字复制 "
            "trustedAssetSources 中与天气状态匹配的一项；不得省略或自行生成路径。"
            "不得输出其它业务字段、样式、尺寸或 Template，"
            "服务端从可信五字段确定性展开。"
        )
    templates = [item for item in component.local_template_ids if item in requested_template_ids]
    if component.name == "WeatherOverview" and "WeatherOverview@1" in templates:
        return (
            common + '; syntax=Template("WeatherOverview@1","heroIcon|compactIcon",'
            '{"conditionIcon":"<trustedAssetSources item>"}); '
            "单业务或 2x4 主视觉使用 heroIcon；2x2 多业务及 support/peer 使用 compactIcon。"
            "conditionIcon 必须由"
            "本轮第二步模型显式选择，且只能逐字复制 trustedAssetSources 中与天气状态匹配的一项；"
            "不得省略、自行生成路径或输出旧 WeatherOverview(...) 构造器。"
        )
    if component.name == "HeartRateOverview" and "HeartRateOverview@1" in templates:
        return (
            common + '; syntax=Template("HeartRateOverview@1",'
            '"hero|heroUpdated|heroIcon|heroUpdatedIcon|support|supportUpdated|'
            'supportIcon|supportUpdatedIcon",params); '
            "单业务使用 hero 前缀，多业务固定使用 support 前缀；Prompt 未下发的 Variant 不得使用。"
            "名称含 Updated 时模板展示可信 updatedAt，名称含 Icon 时 params 仅传入"
            '{"sourceIcon":"<trustedAssetSources item>"}，否则 params={}。不得输出旧 '
            "HeartRateOverview(...) 构造器。"
        )
    if component.name == "DateOverview" and "DateOverview@1" in templates:
        return (
            common + '; syntax=Template("DateOverview@1","compactDate|dateHero",{}); '
            "单业务使用 dateHero；日期+日程组合在 2x2 使用 compactDate，2x4 使用 dateHero。"
            "不得输出旧 DateOverview(...) 构造器。"
        )
    if component.name == "ScheduleOverview" and "ScheduleOverview@1" in templates:
        return (
            common + '; syntax=Template("ScheduleOverview@1",'
            '"nextEvent|nextEventLocation|meetingCompact|meetingCompactLocation|'
            "meetingCompactSource|meetingCompactLocationSource|meetingExpanded|"
            'meetingExpandedSource",params); '
            "单业务使用 nextEvent，有可信地点时使用 nextEventLocation；日期组合在 2x2 使用 "
            "meetingCompact/meetingCompactLocation，2x4 有地点时使用 meetingExpanded。"
            "需要来源图标的日期组合改用对应 Source 后缀。timeText 由服务端可信投影自动补齐；"
            "params 只传 Variant 签名允许且语义匹配的 sourceIcon/timeIcon/locationIcon，"
            "缺失时使用 {}。"
            "不得输出旧 ScheduleOverview(...) 构造器。"
        )
    if component.name == "BatteryOverview" and "BatteryOverview@1" in templates:
        return (
            common + '; syntax=Template("BatteryOverview@1",variant,params); '
            "单业务 2x2 使用 normal/charging/low，2x4 使用对应 Wide 后缀；"
            "与内存对等组合使用 Peer 后缀，与耳机组合使用 Phone 后缀，"
            "与天气 2x2 组合使用 Weather 后缀。前缀必须与可信充电/低电状态一致；"
            "有匹配素材时 params 可传 batteryIcon，否则 params={}；"
            "Action 由布局末尾持有。"
            "不得输出旧 BatteryOverview(...) 构造器。"
        )
    if component.name == "ResourceUsageOverview" and "ResourceUsageOverview@1" in templates:
        return (
            common + '; syntax=Template("ResourceUsageOverview@1","memory|memoryPeer",params); '
            "单业务使用 memory；2x2 与电量对等组合使用 memoryPeer。"
            "有匹配素材时 params 可传 icon，否则 params={}。"
            "内存清理 Action 只能位于布局末尾。不得输出旧 ResourceUsageOverview(...) 构造器。"
        )
    if component.name == "AppUsageOverview" and "AppUsageOverview@1" in templates:
        return (
            common + '; syntax=Template("AppUsageOverview@1",variant,params); '
            "2x2/2x4 分别使用 singleApp/singleAppWide；存在可信次数值和单位时使用对应 "
            "Detailed 后缀。时长分段由服务端可信投影自动补齐；有匹配素材时 params 可传 "
            "appIcon，否则 params={}。"
            "管控 Action 只能位于布局末尾。不得输出旧 AppUsageOverview(...) 构造器。"
        )
    if component.name == "ActivityOverview" and "ActivityOverview@1" in templates:
        return (
            common + '; syntax=Template("ActivityOverview@1",'
            '"steps|stepsSupport|dailySummary|dailySummaryWide",params); '
            "只有完整热量和距离时使用 dailySummary，2x4 单业务使用 dailySummaryWide；"
            "多业务 Support 使用 stepsSupport，否则使用 steps。params 只传 Variant 签名允许且"
            "语义匹配的 stepsIcon/caloriesIcon/distanceIcon，缺失时使用 {}。"
            "组合布局中的顺序由布局规则决定。"
            "不得输出旧 ActivityOverview(...) 构造器。"
        )
    if component.name == "WorkoutOverview":
        if "WorkoutOverview@1" in templates:
            return (
                common
                + '; syntax=Template("WorkoutOverview@1","latest",params); '
                "params 只传 Variant 签名允许且语义匹配的 sourceIcon/caloriesIcon，缺失时使用 {}。"
                "动作只由布局末尾持有；不得输出旧 WorkoutOverview(...) 构造器。"
            )
    if component.name == "CountdownOverview" and "CountdownOverview@1" in templates:
        return (
            common + '; syntax=Template("CountdownOverview@1","countdown",{}); '
            "只展示可信 countdownDays 与模板内置的通用倒计时标签；不得补造"
            "事件名、目标日期、进度或运动语义，不得输出旧 WorkoutOverview(...) 构造器。"
        )
    if component.name == "SleepOverview" and "SleepOverview@1" in templates:
        return (
            common + '; syntax=Template("SleepOverview@1",'
            '"duration|durationDetailed|durationSupport|durationDetailedSupport|'
            "insufficient|insufficientDetailed|schedule|scheduleDetailed|scheduleStatus|"
            'scheduleDetailedStatus",params); '
            "多业务按是否存在次时长分段使用 durationSupport 或 durationDetailedSupport；"
            "普通 Hero 存在可信状态时按时长分段使用 insufficient 或 insufficientDetailed；"
            "2x4 且入睡/醒来时间完整时，按状态和次时长分段选择对应 schedule* 变体；"
            "其余按是否存在次时长分段使用 duration 或 durationDetailed。"
            "时长分段由服务端可信投影自动补齐；Hero 有匹配素材时 params 可传 sourceIcon，"
            "Support 或缺少素材时 params={}。"
            "不得输出旧 SleepOverview(...) 构造器。"
        )
    if component.name == "BluetoothDeviceOverview" and "BluetoothDeviceOverview@1" in templates:
        return (
            common + '; syntax=Template("BluetoothDeviceOverview@1",'
            '"connection|disconnected|disconnectedPhone|earbuds|leftEarbud|rightEarbud|earbudPair|earbudsFull|'
            'earbudsDynamicWide|earbudsPhone|earbudsPhoneWide",params); '
            "未连接单业务使用 disconnected，与手机组合使用 disconnectedPhone；"
            "单业务 2x2 仅查连接状态使用 connection；仅查充电盒电量或充电盒电量+"
            "连接状态使用 earbuds；其余使用实际字段最完整 Variant。2x4 统一使用 "
            "earbudsDynamicWide；与手机组合的 2x2/2x4 分别使用 earbudsPhone/"
            "earbudsPhoneWide，模板会按可信左右耳/充电盒字段自动裁剪。params 只传 "
            "Variant 签名允许且语义匹配的 sourceIcon/"
            "leftEarIcon/rightEarIcon，缺失时使用 {}。"
            "音乐 Action 只能位于布局末尾。不得输出旧 BluetoothDeviceOverview(...) 构造器。"
        )
    return common + "; 可信局部Template=" + json.dumps(templates, ensure_ascii=False)


def _task_spec_with_scope_actions(
    task_spec: TaskSpec,
    components: tuple[UxBusinessComponentCapability, ...],
) -> TaskSpec:
    component_ids = {item.name for item in components}
    if "SleepOverview" in component_ids and not component_ids & {
        "ActivityOverview",
        "HeartRateOverview",
        "WorkoutOverview",
    }:
        approved_ids = set(approved_sleep_action_ids(task_spec))
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    if component_ids & {"ActivityOverview", "HeartRateOverview", "WorkoutOverview"}:
        approved_ids = (
            set(approved_workout_action_ids(task_spec))
            if "WorkoutOverview" in component_ids
            else set()
        )
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    if "AppUsageOverview" in component_ids:
        approved_ids = set(approved_app_usage_action_ids(task_spec))
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    if "ResourceUsageOverview" in component_ids:
        approved_ids = set(approved_memory_cleanup_action_ids(task_spec))
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    battery_owned = component_ids.issubset({"BatteryOverview", "BluetoothDeviceOverview"})
    if component_ids == {"BatteryOverview", "BluetoothDeviceOverview"}:
        return task_spec.model_copy(update={"eventCandidates": []})
    if battery_owned and "BatteryOverview" in component_ids:
        approved_ids = set(approved_battery_power_action_ids(task_spec))
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    if component_ids == {"BluetoothDeviceOverview"}:
        approved_ids = set(approved_bluetooth_music_action_ids(task_spec))
        events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
        return task_spec.model_copy(update={"eventCandidates": events})
    schedule_owned = component_ids.issubset({"DateOverview", "ScheduleOverview"})
    if not schedule_owned or "ScheduleOverview" not in component_ids:
        return task_spec
    approved_ids = set(approved_schedule_action_ids(task_spec))
    events = [item for item in task_spec.eventCandidates if item.id in approved_ids]
    return task_spec.model_copy(update={"eventCandidates": events})


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
) -> tuple[str | int | float, ...]:
    values: list[str | int | float] = []
    for component in components:
        definitions = tuple(
            registry.require_template(template_id)
            for template_id in component.local_template_ids
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
