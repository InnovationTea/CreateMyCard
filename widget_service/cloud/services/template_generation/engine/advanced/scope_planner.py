"""第五接口的新第一层 LLM：只选择 Theme 和业务高级组件范围。"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from itertools import combinations, product
from typing import Any

from pydantic import ValidationError

from models.generation import CandidateDataBinding, TaskSpec, WidgetSize
from services.template_generation.engine.cardplan.prompt import (
    admitted_provider_template_variants,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

from . import content_selectors as _content_selectors
from .content_selectors import (
    activity_overview_is_eligible,
    activity_overview_variants,
    app_usage_overview_is_eligible,
    approved_app_usage_action_ids,
    approved_battery_power_action_ids,
    approved_bluetooth_music_action_ids,
    approved_memory_cleanup_action_ids,
    approved_schedule_action_ids,
    approved_sleep_action_ids,
    approved_workout_action_ids,
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
    TemplateRouteDecision,
    UxBusinessComponentCapability,
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
    candidate_output_fields: dict[str, tuple[str, ...]] | None = None,
    card_spec: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """构造不含 Template、布局源码和整卡置信度信息的新第一层 Prompt。"""
    effective_ids = resolve_available_capability_ids(
        task_spec,
        registry,
        available_capability_ids,
    )
    component_candidates = _component_candidates(task_spec, data_shape, registry, effective_ids)
    if not component_candidates:
        raise ValueError("no provider-backed UX Business Component candidate")
    candidate_ids = {item.name for item in component_candidates}
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
                "id": theme.theme_profile_id,
                "description": theme.description,
            }
            for theme in registry.themes.values()
        ],
        "crossDomainThemeIds": registry.palette_scene_theme_ids["generic"],
        "advancedComponents": [
            _scope_candidate_prompt_payload(
                capability,
                task_spec,
                effective_ids,
                candidate_ids,
                registry,
                card_spec,
                include_template_coverage=template_route_decision,
            )
            for capability in component_candidates
        ],
        "maxAdvancedComponents": registry.ux_size_budgets[task_spec.size].max_business_components,
        "temporaryDataAdmissionBypass": admission_relaxed,
    }
    if template_route_decision:
        user_payload["candidateOutputFieldsByCapability"] = candidate_output_fields or {}
        schema = TemplateRouteDecision.model_json_schema(by_alias=True)
        scope_instruction = (
            "你是第四接口的首层模板路由判断器。只输出 JSON；routeVersion 固定为"
            " template-route-decision/2。candidateOutputFieldsByCapability 是本轮可用候选，不是"
            "全部必显字段。requiredOutputFieldsByCapability 中的每一个路径都必须从同一 capability"
            " 的 candidateOutputFieldsByCapability 数组中逐字复制，必须保留开头斜杠、大小写和"
            "数组下标；禁止输出 /_advancedSelectors、/data、writeResultTo 前缀、展示别名，或任何"
            "自行拼接、缩写和改写后的路径。只选择 userQuery 明确要求展示的候选字段，不要因为"
            "模板内部需要其他数据而把全部候选字段都列为 query 必显字段。"
            "对于 WeatherOverview，city、temperature、condition、airQuality、temperatureRange"
            "只是语义名称，不是允许输出的路径；必须分别从候选数组中选择实际 Provider 路径，"
            "通常对应 /location/districtName、/current/temperatureText、/current/condition、"
            "/current/airQuality、/daily/0/temperatureRangeText，且只能选择本轮候选数组中真实存在"
            "的项。例如 query 为'看看是否下雨、现在多少度'时，只应复制候选中的"
            " /current/condition 和 /current/temperatureText，不得输出"
            " /_advancedSelectors/weather/condition 或 /_advancedSelectors/weather/temperature。"
            "如果 userQuery 包含天气组件的意图（如"
            "'天气小组件'、'天气卡片'、'今天天气怎么样'等），则认为 WeatherOverview 适用，"
            "完全忽略 userQuery 中对体感温度、湿度、风力、紫外线、感冒指数、预警等的提及，"
            "这些舒适度提及不纳入 requiredOutputFieldsByCapability，也不影响 "
            "templateUsable 的判断。"
            "不得纳入 query 未要求的候选字段，也不得输出候选以外的路径。"
            "只有一个或多个 advancedComponents 的 templateCoverageByCapability 能完整覆盖"
            "全部必显数据"
            "时，templateUsable 才能为 true，并同时输出 themeId 与 advancedComponentIds。"
            "只要有一个数据无法映射或呈现，或存在歧义、缺字段、缺模板，必须输出 "
            "templateUsable=false、themeId=null、advancedComponentIds=[]、"
            "requiredOutputFieldsByCapability={}。不得让标准组件、静态文案、推测值或后续模型"
            "补齐模板不支持的数据。不得输出理由或额外字段。"
        )
    else:
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
            "content": (
                scope_instruction
                + "WeatherOverview 用于天气卡片请求：只要 userQuery 表达了天气组件意图（如"
                "'天气小组件'、'天气卡片'、"
                "'查看天气'等），即认为适用，完全忽略对体感温度、湿度、风力、紫外线、感冒指数、预警等的提及，"
                "不要将这些纳入 requiredOutputFieldsByCapability。只在 ViewWeather 提供完整"
                "核心五事实且用户未请求小时预报、日出日落、气压、能见度、AQI 数值、降雨概率"
                "或未来多日预报时可选；候选列表已由服务端执行相同准入过滤。"
                "DateOverview 只表达 "
                "GetCalendarEvents "
                "首个有效事件的日期和星期：仅当候选说明中的全部准入条件满足时选择；"
                "系统当前日期、月/年/农历/相对日期请求，以及 2x2 未明确请求事件日期的"
                "纯日程内容请求都不得选择 DateOverview。ScheduleOverview 只表达 "
                "GetCalendarEvents 同一可信首项的非空 title、由非空 dtStart 和可选 dtEnd "
                "形成的 timeText，以及可选 location；只支持 nextEvent、meetingCompact 和"
                "有地点时的 meetingExpanded。多日程列表、实时状态、分钟倒计时、会议号、"
                "备注、邀请人、可加入状态、待办和备忘录不得选择。明确请求地点时必须有"
                "非空 location；明确请求入会/返回/查看或开启专注时必须有语义匹配的本轮"
                "批准事件候选。明确请求来源、时间、地点或 Action 图标时，"
                "必须有语义匹配的本轮"
                "assetCandidates。候选列表与模型输出后均由服务端执行同一准入复核。"
                "BatteryOverview 只表达 GetPhoneBatteryInfo 的手机本机 SOC 数值/文本、电量等级"
                "与充电状态：SOC 必须为 0 到 100，或可从百分比文本确定性解析，二者同时存在时"
                "必须一致，0% 合法，等级与充电状态必须为可信非空字符串。只要 userQuery 表达了电池"
                "卡片意图（如'低电量卡片'、'电量小组件'、'电量状态'、'省电模式'等），即认为适用，"
                "完全忽略对续航时间、剩余可用时间、预计充满时间等的提及，不要将这些纳入"
                "requiredOutputFieldsByCapability。只请求健康度、温度、电压、电流、充电器类型或外设"
                "电量时不得选择；外设电量应选 BluetoothDeviceOverview。省电动作只有存在语义闭环"
                "的批准事件候选时才可进入第二层；否则仍可选择 BatteryOverview，但必须生成"
                "无动作布局。"
                "BluetoothDeviceOverview 只表达 GetEarphoneInfo 的蓝牙耳机/耳塞连接状态、"
                "设备名称和盒/左/右电量。必须有可信 boolean isConnected、非空 earphoneName，"
                "以及至少一路 0 到 100 的电量；0% 合法。用户明确请求左耳、右耳、双耳或充电盒"
                "时，对应电量必须存在。只有用户主体明确为蓝牙耳机/耳塞，或手机+蓝牙耳机设备"
                "电量/连接概览时才能选择；天气、日程、运动、睡眠、应用使用及手表、车机、键鼠、"
                "音箱等非耳机设备请求不得选择。播放/暂停、上一首、下一首、曲目或进度请求也不得"
                "选择。音乐入口只允许本轮真实的 event.open.music.daily 和"
                " event.open.music.favorite；没有批准事件时必须生成无动作布局。"
                "ResourceUsageOverview 当前只表达 GetSystemMemInfo 的 memory 变体，且仅使用"
                "完整可信的 usagePercent、availableMemText、totalMemText；usagePercent 必须是"
                " 0 到 100 的有限数值，0% 合法。存储/磁盘、缓存、进程明细、CPU/GPU、swap、"
                "趋势、历史曲线或仅请求 freeMemText 时不得选择；不得从百分比推断内存不足、"
                "正常或告警。一键清理只在用户明确请求且存在 event.clean.memory 候选时可用。"
                "AppUsageOverview 当前只允许 singleApp：必须有 GetAppUsageDuration，用户明确"
                "指定一个应用并请求该应用使用时长，当日口径由 Provider 能力定义；同一"
                "可信数据树中的 appName 和"
                "durationText 均为非空字符串，updatedAt 可选且只在存在时展示；明确请求更新时间时"
                "updatedAt 才必须存在。durationText 需可由服务端按小时/分钟"
                "无损解析。总屏幕时间、多应用、排行、限额、超限、剩余时长、比例/进度、趋势/"
                "历史和分类汇总均不得选择；纯秒或含秒时长也不得选择。dailyLimit、overLimit、"
                "topApps 虽在 Registry 声明但当前 capability 未启用。管控动作只在用户明确请求且"
                "存在 event.open.settings.parentControl 候选时进入第二层，否则使用无动作布局。"
                "AppUsageOverview 与 SystemModeOverview 只有两边均有可信数据时才能组合；当前无"
                "可信 SystemMode 状态时不得选择该组合，也不得输出占位状态。"
                "ActivityOverview 当前只开放 steps 和 dailySummary。steps 要求 dailySteps 为非负"
                "整数，0 有效；dailySummary 要求步数、热量文本、距离文本完整且类型正确。明确请求"
                "热量或距离时对应事实必须存在；缺项只有需求仍仅为步数时才能降为 steps。目标步数、"
                "达成率、目标环/进度、活动分钟、站立小时、趋势、单独 calories/exercise 均不得选择，"
                "也不得生成 Ring 或 Progress。Activity 无动作。"
                "WorkoutOverview 当前只开放 latest，要求运动类型、时长、热量三个非空可信"
                "字符串，暂无运动视为空态。CountdownOverview 只表达 GetCountdownDays 的非负整数"
                "剩余天数，0 天有效；适用于高考、考试、节日、纪念日、旅行或赛事等通用倒计时，"
                "不得补造事件名或目标日期。"
                "实时/计划状态、距离、配速、轨迹、心率区间、赛事名、训练计划、总里程和完成率均不得"
                "选择；倒计时不得生成进度或补造名称。运动动作只有用户请求动作且本轮存在批准的"
                " event.open.health.sport 时可用。"
                "HeartRateOverview 只开放 average，且必须表述为运动平均心率；心率值必须是正整数。"
                "明确请求更新时间时 updatedAt 必须存在。当前/实时、静息、异常/风险、区间、趋势、"
                "波形、最大/最低心率均不得选择；不得判断状态或生成 Ring、Progress、折线、波形。"
                "多业务中 HeartRateOverview 固定为 Support 且无动作。Activity 多业务只与独立通过"
                "准入的 SleepOverview 或 HeartRateOverview 组合；Workout 多业务只与独立通过准入的"
                " ActivityOverview 组合，不得生成占位业务。"
                "SleepOverview 只消费 GetHealthAndSportSummary 同一可信记录中的夜间总睡眠时长；"
                "nightSleepDurationText 必须是可无损解析并确定性归一化的小时/分钟文本，0分钟合法。"
                "状态、入睡时刻和醒来时刻只在各自字段类型与格式可信时使用；schedule 只对 2x4"
                " 且同时具有 HH:mm 入睡/醒来时刻开放。insufficient 只在 sleepStatus 明确表达睡眠"
                "不足时开放，绝不根据时长阈值推断。批量效果测试阶段，睡眠得分、深睡/浅睡/REM、"
                "午睡、目标完成率、趋势、历史、阶段图和睡眠建议虽超出当前投影，但只要总时长准入"
                "成立仍可选择，并统一降级到 duration；请求状态或作息而对应字段不可信时也降级到"
                " duration，不得补造所请求内容。提醒动作只允许用户明确"
                "请求且本轮批准的 event.open.clock.alarm；否则必须使用无动作布局。"
                "跨领域选择多个组件时，themeId "
                "必须从 crossDomainThemeIds 中选择。"
                + (
                    "临时批跑模式：第一层高级组件数据适配准入已放开。"
                    "忽略上文关于字段完整性、查询细分与动作闭环是否允许进入候选的限制，"
                    "以 advancedComponents 实际列表为准进行选择；不得虚构候选列表之外的组件。"
                    if admission_relaxed
                    else ""
                )
                + "\n"
                + json.dumps(schema, ensure_ascii=False)
            ),
        },
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _scope_candidate_prompt_payload(
    capability: UxBusinessComponentCapability,
    task_spec: TaskSpec,
    effective_ids: set[str],
    candidate_ids: set[str],
    registry: CardPlanRegistry,
    card_spec: dict[str, Any] | None,
    *,
    include_template_coverage: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": capability.name,
        "description": capability.description,
        "variants": _effective_candidate_variants(capability, task_spec, effective_ids),
        "themeIds": _theme_ids_for_components((capability,), registry),
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
    capability: UxBusinessComponentCapability,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    effective_ids: set[str],
    card_spec: dict[str, Any] | None,
) -> tuple[dict[str, frozenset[str]], ...]:
    options: list[dict[str, frozenset[str]]] = []
    for template_id in capability.local_template_ids:
        definition = registry.require_template(template_id)
        capability_id = definition.capability_id
        if capability_id is None or capability_id not in effective_ids:
            continue
        for variant in admitted_provider_template_variants(
            definition,
            task_spec,
            card_spec,
        ):
            binding_names = (*variant.required_bindings, *variant.optional_bindings)
            paths = {
                definition.bindings[name].path
                for name in binding_names
                if name in definition.bindings
            }
            for parameter_schema in variant.parameters_schema.get("properties", {}).values():
                if not isinstance(parameter_schema, dict):
                    continue
                paths.update(parameter_schema.get("sourcePaths", ()))
            options.append({capability_id: frozenset(paths)})
    return tuple(options)


def _component_template_coverage_union(
    capability: UxBusinessComponentCapability,
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


def _requested_output_fields_by_capability(
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> dict[str, tuple[str, ...]]:
    fields: dict[str, list[str]] = {}
    for binding in coverage_bindings:
        values = fields.setdefault(binding.capabilityId, [])
        values.extend(binding.candidateOutputFields)
    return {
        capability_id: tuple(dict.fromkeys(paths))
        for capability_id, paths in fields.items()
    }


def validate_template_request_coverage(
    scope: AdvancedScopeBrief,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    required_output_fields: dict[str, tuple[str, ...]],
    card_spec: dict[str, Any] | None,
) -> None:
    """证明每个 query 筛选字段都可由所选组件的某组模板 Variant 覆盖。"""
    if not coverage_bindings:
        raise ValueError("Template route requires query-selected data fields")
    capability_ids = [binding.capabilityId for binding in coverage_bindings]
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError("Template route requires one binding root per data capability")
    candidates = _requested_output_fields_by_capability(coverage_bindings)
    if not required_output_fields:
        raise ValueError("Template route requires query-selected data fields")
    for capability_id, fields in required_output_fields.items():
        candidate_fields = set(candidates.get(capability_id, ()))
        if not candidate_fields:
            raise ValueError("query-required capability has no candidateOutputFields")
        if not set(fields).issubset(candidate_fields):
            raise ValueError("query-required fields must be selected from candidateOutputFields")
    effective_ids = resolve_available_capability_ids(task_spec, registry, tuple(capability_ids))
    component_options = []
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
                "Template route component has no applicable Provider Template: "
                f"{component_id}"
            )
        component_options.append(options)
    for selected_options in product(*component_options):
        covered: dict[str, set[str]] = {}
        for option in selected_options:
            for capability_id, paths in option.items():
                covered.setdefault(capability_id, set()).update(paths)
        has_full_coverage = all(
            set(fields).issubset(covered.get(capability_id, set()))
            for capability_id, fields in required_output_fields.items()
        )
        if has_full_coverage:
            return
    raise ValueError("selected Provider Templates do not cover every query-selected data field")


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
) -> AdvancedScopeBrief:
    """由首层 LLM 决定模板路由，并用 Provider 契约做确定性完整覆盖复核。"""
    candidate_fields = _requested_output_fields_by_capability(coverage_bindings)
    prompt = build_advanced_scope_prompt(
        task_spec,
        data_shape,
        registry,
        available_capability_ids,
        template_route_decision=True,
        candidate_output_fields=candidate_fields,
        card_spec=card_spec,
    )
    raw = await generate_json(prompt, "template-route-decision")
    try:
        decision = TemplateRouteDecision.model_validate(raw)
    except ValidationError as exc:
        raise TemplateRouteNotApplicable("invalid TemplateRouteDecision") from exc
    if not decision.template_usable:
        raise TemplateRouteNotApplicable("first-layer LLM rejected the Template route")
    scope = AdvancedScopeBrief(
        themeId=decision.theme_id or "",
        advancedComponentIds=decision.advanced_component_ids,
    )
    scope = _normalize_redundant_2x2_support(scope, task_spec)
    try:
        validate_advanced_scope(
            scope,
            task_spec,
            data_shape,
            registry,
            available_capability_ids,
        )
        validate_template_request_coverage(
            scope,
            task_spec,
            registry,
            coverage_bindings,
            decision.required_output_fields_by_capability,
            card_spec,
        )
    except ValueError as exc:
        raise TemplateRouteNotApplicable(str(exc)) from exc
    return scope


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
    preferred_theme_ids = tuple(
        theme_id
        for component in components
        for scene in component.palette_scenes
        if scene != "generic"
        for theme_id in registry.palette_scene_theme_ids[scene]
        if theme_id in theme_ids
    )
    resolved_theme_id = next(iter(dict.fromkeys(preferred_theme_ids)), theme_ids[0])
    return scope.model_copy(update={"theme_id": resolved_theme_id})


def plan_advanced_scope_offline(
    task_spec: TaskSpec,
    data_shape: DataShape,
    registry: CardPlanRegistry,
    available_capability_ids: tuple[str, ...] | None = None,
) -> AdvancedScopeBrief:
    """仅供显式离线兼容测试；第五接口生产主链路默认不启用。"""
    effective_ids = resolve_available_capability_ids(
        task_spec,
        registry,
        available_capability_ids,
    )
    candidates = _component_candidates(task_spec, data_shape, registry, effective_ids)
    if not candidates:
        raise ValueError("no provider-backed UX Business Component candidate")
    primary = candidates[0]
    theme_ids = _theme_ids_for_components((primary,), registry)
    scope = AdvancedScopeBrief(
        themeId=theme_ids[0],
        advancedComponentIds=(primary.name,),
    )
    validate_advanced_scope(
        scope,
        task_spec,
        data_shape,
        registry,
        available_capability_ids,
    )
    return scope


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
    allowed_themes = set(_theme_ids_for_components(components, registry))
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
            if scope.theme_id not in set(_theme_ids_for_components(components, registry)):
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
    component_names = {item.name for item in components}
    if (
        "BluetoothDeviceOverview" in component_names
        and count > 1
        and component_names != {"BatteryOverview", "BluetoothDeviceOverview"}
    ):
        return ()
    health_component_names = component_names & {
        "ActivityOverview",
        "HeartRateOverview",
        "WorkoutOverview",
    }
    approved_health_compositions = (
        {"ActivityOverview", "SleepOverview"},
        {"ActivityOverview", "HeartRateOverview"},
        {"ActivityOverview", "WorkoutOverview"},
    )
    if (
        health_component_names
        and count > 1
        and component_names not in approved_health_compositions
    ):
        return ()
    if "AppUsageOverview" in component_names:
        action_count = len(approved_app_usage_action_ids(task_spec))
    if "ResourceUsageOverview" in component_names:
        action_count = len(approved_memory_cleanup_action_ids(task_spec))
    if "SleepOverview" in component_names:
        action_count = len(approved_sleep_action_ids(task_spec))
    if health_component_names:
        action_count = (
            len(approved_workout_action_ids(task_spec))
            if "WorkoutOverview" in component_names
            else 0
        )
    schedule_owned_scope = {item.name for item in components}.issubset(
        {"DateOverview", "ScheduleOverview"}
    )
    if schedule_owned_scope and any(item.name == "ScheduleOverview" for item in components):
        action_count = len(approved_schedule_action_ids(task_spec))
    battery_owned_scope = component_names.issubset(
        {"BatteryOverview", "BluetoothDeviceOverview"}
    )
    if component_names == {"BatteryOverview", "BluetoothDeviceOverview"}:
        action_count = 0
    elif battery_owned_scope and "BatteryOverview" in component_names:
        action_count = len(approved_battery_power_action_ids(task_spec))
    if component_names == {"BluetoothDeviceOverview"}:
        action_count = len(approved_bluetooth_music_action_ids(task_spec))
    has_action = action_count > 0
    common = set(registry.ux_layout_components)
    for capability in components:
        common &= set(capability.supported_layouts)
    allowed: list[str] = []
    for layout_id in common:
        layout = registry.require_ux_layout_component(layout_id)
        if task_spec.size not in layout.supported_card_sizes:
            continue
        if (
            not layout.minimum_children(task_spec.size)
            <= count
            <= layout.max_children_by_size[task_spec.size]
        ):
            continue
        if action_count < layout.min_action_children_by_size[task_spec.size]:
            continue
        if "ResourceUsageOverview" in component_names and count > 1:
            resource_battery = component_names == {
                "BatteryOverview",
                "ResourceUsageOverview",
            }
            if not resource_battery:
                continue
            expected_layouts = (
                {"PeerPairLayout"}
                if task_spec.size == "2x2"
                else {"HeroSupportLayout", "HeroSupportActionLayout"}
            )
            if layout_id not in expected_layouts:
                continue
        if "AppUsageOverview" in component_names and count > 1:
            if component_names != {"AppUsageOverview", "SystemModeOverview"}:
                continue
            if layout_id not in {"HeroSupportLayout", "HeroSupportActionLayout"}:
                continue
        if component_names == {"BatteryOverview", "BluetoothDeviceOverview"}:
            expected_layout = (
                "PeerPairLayout" if task_spec.size == "2x2" else "HeroSupportLayout"
            )
            if layout_id != expected_layout:
                continue
        if component_names == {"BluetoothDeviceOverview"}:
            if action_count == 0:
                expected_bluetooth_layouts = {"SingleFocusLayout"}
            elif task_spec.size == "2x2":
                expected_bluetooth_layouts = {"HeroActionLayout"}
            else:
                expected_bluetooth_layouts = {"ActionMatrixLayout"}
            if layout_id not in expected_bluetooth_layouts:
                continue
        has_weather = any(item.name == "WeatherOverview" for item in components)
        if has_weather and layout_id == "WeatherNowForecastLayout":
            continue
        if has_weather and count > 1 and task_spec.size == "2x2" and layout_id not in {
            "HeroSupportLayout",
            "HeroSupportActionLayout",
        }:
            continue
        allowed.append(layout_id)
    return tuple(sorted(allowed, key=lambda item: _layout_rank(item, count, has_action)))


def scope_template_ids(
    scope: AdvancedScopeBrief,
    registry: CardPlanRegistry,
    task_spec: TaskSpec | None = None,
) -> tuple[str, ...]:
    template_ids = tuple(
        dict.fromkeys(
            template_id
            for component_id in scope.advanced_component_ids
            for capability in (registry.require_ux_business_component(component_id),)
            if capability.implementation == "template"
            for template_id in capability.local_template_ids
        )
    )[:12]
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
) -> tuple[UxBusinessComponentCapability, ...]:
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
    capability: UxBusinessComponentCapability,
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
        if any(
            registry.require_ux_layout_component(layout_id).minimum_children(size)
            <= 2
            <= registry.require_ux_layout_component(layout_id).max_children_by_size[size]
            for layout_id in shared
        ):
            compatible.append(component_id)
    return tuple(compatible)


def _effective_candidate_variants(
    capability: UxBusinessComponentCapability,
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
    components: tuple[UxBusinessComponentCapability, ...],
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    if len(components) == 1 and components[0].name == "SleepOverview":
        return tuple(registry.palette_scene_theme_ids["sleep.violet"])
    per_component = [
        tuple(
            dict.fromkeys(
                theme_id
                for scene in component.palette_scenes
                for theme_id in registry.palette_scene_theme_ids[scene]
            )
        )
        for component in components
    ]
    if not per_component:
        return ()
    cross_domain = len({component.domain_id for component in components}) > 1
    if cross_domain:
        return tuple(
            dict.fromkeys(
                theme_id
                for component_theme_ids in per_component
                for theme_id in component_theme_ids
            )
        )
    common = set(per_component[0])
    for theme_ids in per_component[1:]:
        common &= set(theme_ids)
    return tuple(theme_id for theme_id in per_component[0] if theme_id in common)


def _layout_rank(layout_id: str, count: int, has_action: bool) -> tuple[int, str]:
    preferred: dict[tuple[int, bool], tuple[str, ...]] = {
        (1, False): ("SingleFocusLayout", "ListActionLayout"),
        (1, True): ("HeroActionLayout", "ListActionLayout", "SingleFocusLayout"),
        (2, False): ("HeroSupportLayout", "PeerPairLayout", "EqualItemsLayout"),
        (2, True): ("HeroSupportActionLayout", "HeroSupportLayout", "PeerPairLayout"),
    }
    order = preferred.get((count, has_action), ("SequentialSummaryLayout", "EqualItemsLayout"))
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
