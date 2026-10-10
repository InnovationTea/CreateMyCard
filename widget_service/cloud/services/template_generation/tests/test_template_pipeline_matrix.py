# -*- coding: utf-8 -*-
"""模板可选字段组合金样（Layer C）：走完整管线（除真实 LLM）的缺席组合穷举。

取代 test_template_optional_combinations.py 的 harness 级渲染：本文件对每个
声明了可选绑定的 2x2 Provider 模板（Full/Hero/Compact/Support/HeroTitle），
从 TaskSpec 出发调用 generate_template_a2ui 跑「能力解析 → 内容选择器 →
数据形状 → Search 检索 → 第二层提示词 → 桩模板体 → 组装 → 校验 → A2UI」
全链路，仅用确定性桩模型替换两次 LLM 调用（第一层检索意图 + 第二层模板体）。
``#if`` 剪枝因此发生在真实组装与业务校验之内，而不是 harness 直拼。

布局批准（host layout）由 Search 规划器按「业务数 × 选中动作数」确定
（template_plan_planner._single_business_drafts / _dual_business_drafts）：
0 动作 → SingleFocusLayout（Full / Support 双业务）；1 动作 →
HeroActionLayout（Hero）；2 动作 → CompactTwoActionLayout（Compact）；
双业务 1 动作 → HeroTitleContentActionLayout（HeroTitle + HeroContent）。
桩体必须使用与规划一致的 host layout，否则契约校验拒绝。

对每个模板穷举 ``2^k`` 个 optional 绑定缺席子集（k = optionalBindings 数）；
缺席字段同步从 dataModelSchema 与 candidateOutputFields 中剪除（绑定在而
schema 缺失的组合按设计不存在）。组合键：``all``（全在）、``none``（全缺）、
``absent_<binding>+<binding>``（其余缺席）。

管线确定拒绝的组合（缺席剪空 cardtpl 容器、检索判别器/manifest 门禁）不进
``combinations``，而是连同原因冻结在 ``excludedCombinations``——拒绝语义变化
会以 diff 呈现并走 bless 复核；完全不可达的模板记录在 ``_SKIPPED_TEMPLATES``
并由守护测试校验清单准确性（不允许静默丢弃）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.preview_dataset import (
    _TEXT_BY_TEMPLATE_PARAMETER,
    _set_path,
)

# #467 耳机每日歌单 2x4 家族：actionId 必填，绑定每日歌单动作（与
# MusicCompact 的预览取值同源）。仅本矩阵使用，不改引擎侧预览表。
_MATRIX_TEXT_PARAMS: dict[tuple[str, str], str] = {
    **_TEXT_BY_TEMPLATE_PARAMETER,
    ("BluetoothDeviceOverviewEarbudsChargingWideFull@1", "actionId"): "event.open.music.daily",
    # #434 新增 MeetingSenderFull 必填 title：管线信任门要求字面量来自受信源
    # （数据样例/用户话术/卡片文案），预览表里的 "UI需求评审会" 不满足；
    # 信任集里的卡片文案只有日历的卡片标题，故沿用之。
    ("ScheduleOverviewMeetingSenderFull@1", "title"): "今日日程",
}
from services.template_generation.engine.cardplan.provider_bundle import (
    asset_semantic_tags,
    parameter_value_kind,
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.prompt import (
    _action_label,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
)
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
)

_REGISTRY = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())

_LAYOUT_BY_KIND = {
    "Full": "SingleFocusLayout@1",
    "Hero": "HeroActionLayout@1",
    "Compact": "CompactTwoActionLayout@1",
    "Support": "TwoSupportLayout@1",
    "HeroTitle": "HeroTitleContentActionLayout@1",
    "HeroContent": "HeroTitleContentActionLayout@1",
    # 2x4 wide 家族（#404 后 Search 支持 2x4）：每个 wide 模板至少一次全链路固化。
    "WideHero": "WideSingleFocusLayout@1",
    "WideFull": "WideFullOnlyLayout@1",
    "WideHalf": "WideTwoHalfLayout@1",
}

# Support 模板必须落进双业务 TwoSupportLayout；每个能力固定一个跨能力伙伴。
# 电池业务不可用：_provider_variant_matches_trusted_state 对 BatteryOverview@1
# 的 support 族变体永不放行（prompt 契约门禁比编译门禁更严），电池 Support
# 模板因此无法通过管线渲染（见 _SKIPPED_TEMPLATES）。
_SUPPORT_PARTNER_BY_CAPABILITY = {
    "GetCalendarEvents": ("GetSystemMemInfo", "ResourceUsageOverviewSupport@1"),
    "GetCountdownDays": ("GetSystemMemInfo", "ResourceUsageOverviewSupport@1"),
    "GetEarphoneInfo": ("GetCountdownDays", "CountdownOverviewTravelSupport@1"),
    "GetPhoneBatteryInfo": ("GetCountdownDays", "CountdownOverviewTravelSupport@1"),
    "GetHealthAndSportSummary": ("GetSystemMemInfo", "ResourceUsageOverviewSupport@1"),
    "GetSystemMemInfo": ("GetCountdownDays", "CountdownOverviewTravelSupport@1"),
    "ViewWeather": ("GetSystemMemInfo", "ResourceUsageOverviewSupport@1"),
}

# 每能力动作候选（1 动作取第一个，2 动作取全部）；id 必须出现在 eventCandidates。
# PillAction label 由引擎 _action_label 按 eventId 规范化，测试侧不得自带文案。
_EVENT_FIXTURES_BY_CAPABILITY = {
    "GetCalendarEvents": ("event.open.clock.alarm", "event.startNavigate"),
    "GetCountdownDays": ("event.startNavigate", "event.open.clock.alarm"),
    "GetEarphoneInfo": ("event.open.music.favorite", "event.startNavigate"),
    "GetHealthAndSportSummary": ("event.open.health.sport", "event.startNavigate"),
    "GetPhoneBatteryInfo": ("event.setPowerSavingMode", "event.startNavigate"),
    "GetSystemMemInfo": ("event.startNavigate", "event.open.clock.alarm"),
    "ViewWeather": ("event.open.weather", "event.startNavigate"),
}

# 个别家族的准入动作不在版式动作位里（wide 版式 action_count=0），但路由仍要求
# 该动作出现在本轮候选中（#467：每日歌单动作准入后才放行耳机 2x4 家族）。
_EXTRA_CANDIDATE_EVENTS_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    "BluetoothDeviceOverviewEarbudsChargingWideFull@1": ("event.open.music.daily",),
}

_USER_QUERY_BY_CAPABILITY = {
    "GetCalendarEvents": "查看今天的日程安排",
    "GetCountdownDays": "看看距离目标日期还有几天",
    "GetEarphoneInfo": "查看耳机名称和电量",
    "GetHealthAndSportSummary": "查看今天的运动健康数据",
    "GetPhoneBatteryInfo": "查看手机电量和充电状态",
    "GetSystemMemInfo": "查看设备内存使用情况",
    "ViewWeather": "查看今天天气和温度",
}

_TITLE_BY_CAPABILITY = {
    "GetCalendarEvents": "今日日程",
    "GetCountdownDays": "倒计时",
    "GetEarphoneInfo": "耳机",
    "GetHealthAndSportSummary": "运动健康",
    "GetPhoneBatteryInfo": "设备电量",
    "GetSystemMemInfo": "设备内存",
    "ViewWeather": "天气",
}

# 模板必填资产参数（parametersSchema.required）的资产池：按业务给出候选资产，
# 必填参数按 asset_parameter_semantic_tags 的语义标签从池中确定性挑选。
_ASSET_FIXTURES_BY_BUSINESS = {
    "BatteryOverview": (
        {
            "src": "resources/base/media/battery_leaf_fill.svg",
            "description": "电池电量叶子图标",
            "sceneTags": ["device", "battery"],
        },
        {
            "src": "resources/base/media/icon_phone.svg",
            "description": "手机电量图标",
            "sceneTags": ["phone-device"],
        },
    ),
    "BluetoothDeviceOverview": (
        {
            "src": "resources/base/media/earphone_case_16644.svg",
            "description": "耳机收纳盒实心图标",
            "sceneTags": ["device", "audio"],
        },
        {
            "src": "resources/base/media/icon_earphone.svg",
            "description": "左右分体耳机本体图标",
            "sceneTags": ["device", "audio"],
        },
        {
            "src": "resources/base/media/icon_music.svg",
            "description": "双音符音乐图标（音乐/歌单/音频内容）",
            "sceneTags": ["music"],
        },
    ),
    "HeartRateOverview": (
        {
            "src": "resources/base/media/figure_run.svg",
            "description": "运动心率跑步图标",
            "sceneTags": ["sport", "heart"],
        },
    ),
    "GenericMetricOverview": (
        {
            "src": "resources/base/media/figure_run.svg",
            "description": "运动指标跑步图标",
            "sceneTags": ["sport"],
        },
    ),
    "CalendarOverview": (
        {
            "src": "resources/base/media/calendar_fill.svg",
            "description": "日程日历图标",
            "sceneTags": ["calendar", "schedule"],
        },
    ),
    "WeatherOverview": (
        {
            "src": "resources/base/media/icon_weather_thermometer.svg",
            "description": "天气温度温度计图标",
            "sceneTags": ["weather"],
        },
    ),
}

# 有语义的字符串样例值；其余按绑定类型取 _FALLBACK_SAMPLE_BY_TYPE。
_SAMPLE_BY_PATH: dict[tuple[str, str], Any] = {
    ("GetCalendarEvents", "/eventCount"): 3,
    ("GetCalendarEvents", "/events/0/description"): "同步项目进展",
    ("GetCalendarEvents", "/events/0/dtEnd"): "2026-09-22 11:00",
    ("GetCalendarEvents", "/events/0/dtStart"): "2026-09-22 10:00",
    ("GetCalendarEvents", "/events/0/eventLocation"): "会议室A",
    ("GetCalendarEvents", "/events/0/importantEventType"): 1,
    ("GetCalendarEvents", "/events/0/isAllDay"): False,
    ("GetCalendarEvents", "/events/0/remindTime/0"): "2026-09-22 09:50",
    ("GetCalendarEvents", "/events/0/senderName"): "张三",
    ("GetCalendarEvents", "/events/0/startDate"): "2026-09-22",
    ("GetCalendarEvents", "/events/0/timeZone"): "GMT+08:00",
    ("GetCalendarEvents", "/events/0/title"): "项目周会",
    ("GetCountdownDays", "/countdownDays"): 3,
    ("GetEarphoneInfo", "/batteryLevel"): 80,
    ("GetEarphoneInfo", "/chargingStatusDesc"): "充电中",
    ("GetEarphoneInfo", "/earphoneName"): "测试耳机",
    ("GetEarphoneInfo", "/isConnected"): True,
    ("GetEarphoneInfo", "/leftBatteryLevel"): 76,
    ("GetEarphoneInfo", "/leftChargingStatusDesc"): "未充电",
    ("GetEarphoneInfo", "/rightBatteryLevel"): 78,
    ("GetEarphoneInfo", "/rightChargingStatusDesc"): "充电中",
    ("GetHealthAndSportSummary", "/dailyDistanceText"): "4.60 公里",
    ("GetHealthAndSportSummary", "/dailySteps"): 6200,
    ("GetHealthAndSportSummary", "/dailyTotalCaloriesText"): "420 千卡",
    ("GetHealthAndSportSummary", "/deepSleepDurationText"): "2小时10分",
    ("GetHealthAndSportSummary", "/exerciseCalorieText"): "320 千卡",
    ("GetHealthAndSportSummary", "/exerciseDurationText"): "45分钟",
    ("GetHealthAndSportSummary", "/exerciseEndTimeText"): "2026-09-22 08:00",
    ("GetHealthAndSportSummary", "/exerciseHeartRateAvg"): 95,
    ("GetHealthAndSportSummary", "/exerciseHeartRateMax"): 132,
    ("GetHealthAndSportSummary", "/exerciseHeartRateMin"): 68,
    ("GetHealthAndSportSummary", "/exerciseTypeName"): "户外跑步",
    ("GetHealthAndSportSummary", "/fallAsleepTimeText"): "23:10",
    ("GetHealthAndSportSummary", "/nightSleepDurationText"): "7小时1分",
    ("GetHealthAndSportSummary", "/sleepScore"): 82,
    ("GetHealthAndSportSummary", "/sleepStatus"): "已入睡",
    ("GetHealthAndSportSummary", "/sleepTypeDesc"): "夜间睡眠",
    ("GetHealthAndSportSummary", "/totalNapDurationText"): "45分钟",
    ("GetHealthAndSportSummary", "/wakeupTimeText"): "07:00",
    ("GetPhoneBatteryInfo", "/batteryCapacityLevelDesc"): "正常电量",
    ("GetPhoneBatteryInfo", "/batterySOC"): 80,
    ("GetPhoneBatteryInfo", "/batterySOCText"): "80%",
    ("GetPhoneBatteryInfo", "/batteryTemperatureText"): "29.0 ℃",
    ("GetPhoneBatteryInfo", "/chargingStatusDesc"): "未充电",
    ("GetPhoneBatteryInfo", "/healthStatusDesc"): "正常",
    ("GetPhoneBatteryInfo", "/isBatteryPresentText"): "已装入",
    ("GetPhoneBatteryInfo", "/nowCurrentText"): "120 mA",
    ("GetPhoneBatteryInfo", "/pluggedTypeDesc"): "未连接",
    ("GetPhoneBatteryInfo", "/voltageText"): "3.85 V",
    ("GetSystemMemInfo", "/availableMemText"): "3.0 GB",
    ("GetSystemMemInfo", "/totalMemText"): "8.0 GB",
    ("GetSystemMemInfo", "/usagePercent"): 62.5,
    ("ViewWeather", "/current/alertLevel"): "黄色预警",
    ("ViewWeather", "/current/airQuality"): "优",
    ("ViewWeather", "/current/coldLevel"): "无需",
    ("ViewWeather", "/current/condition"): "多云",
    ("ViewWeather", "/current/feelsLikeC"): 24.5,
    ("ViewWeather", "/current/humidityPercent"): 55,
    ("ViewWeather", "/current/temperatureC"): 22.5,
    ("ViewWeather", "/current/temperatureText"): "22℃",
    ("ViewWeather", "/current/uvIndex"): "中等",
    ("ViewWeather", "/current/windDirection"): "东南风",
    ("ViewWeather", "/current/windLevel"): 2,
    ("ViewWeather", "/daily/0/airQuality"): "优",
    ("ViewWeather", "/daily/0/condition"): "多云",
    ("ViewWeather", "/daily/1/airQuality"): "良",
    ("ViewWeather", "/daily/1/coldLevel"): "无需",
    ("ViewWeather", "/daily/1/condition"): "小雨",
    ("ViewWeather", "/daily/1/date"): "09月23日",
    ("ViewWeather", "/daily/1/rainProbabilityPercent"): "60",
    ("ViewWeather", "/daily/1/temperatureRangeText"): "20℃~26℃",
    ("ViewWeather", "/daily/1/uvIndex"): "中等",
    ("ViewWeather", "/daily/1/weekday"): "周三",
    ("ViewWeather", "/daily/2/condition"): "阴",
    ("ViewWeather", "/daily/2/temperatureRangeText"): "19℃~25℃",
    ("ViewWeather", "/daily/4/condition"): "多云",
    ("ViewWeather", "/daily/4/rainProbabilityPercent"): "30",
    ("ViewWeather", "/daily/4/temperatureRangeText"): "21℃~27℃",
    ("ViewWeather", "/location/districtName"): "思明区",
    ("ViewWeather", "/location/prefectureName"): "厦门市",
}

_FALLBACK_SAMPLE_BY_TYPE = {
    "string": "样例文本",
    "integer": 80,
    "number": 3.5,
    "boolean": True,
    "null": None,
}

_UPDATED_AT = "2026-09-22 10:00"
for _capability in (
    "GetCalendarEvents",
    "GetHealthAndSportSummary",
    "GetPhoneBatteryInfo",
    "ViewWeather",
):
    _SAMPLE_BY_PATH.setdefault((_capability, "/updatedAt"), _UPDATED_AT)


class _SimpleEvent:
    """``_action_label`` 只读取 eventId；用于复用引擎的规范化动作文案。"""

    def __init__(self, event_id: str) -> None:
        self.id = event_id


class _PinnedPlanModel:
    """确定性桩：第一层返回固定检索意图，第二层返回固定模板体。"""

    def __init__(
        self,
        *,
        output_fields_by_capability: dict[str, tuple[str, ...]],
        action_ids: tuple[str, ...],
        body: str,
    ) -> None:
        self._output_fields = dict(output_fields_by_capability)
        self._action_ids = action_ids
        self.body = body
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "requiredOutputFieldsByCapability": {
                capability_id: list(paths)
                for capability_id, paths in self._output_fields.items()
            },
            "action": list(self._action_ids),
        }

    def generate(
        self,
        prompt: list[dict[str, str]],
        *_args: Any,
        **_kwargs: Any,
    ) -> str:
        self.second_layer_prompt = prompt
        return self.body


@dataclass(frozen=True)
class _FamilySpec:
    """单个 2x2 模板的管线场景静态输入（与缺席子集无关的部分）。

    wide 2x4 家族（``slot_definitions`` 非空）：lead 模板 = 第一个槽位，
    其余槽位为固定搭档；缺席子集只作用于 lead。``size`` 为 "2x4"。
    """

    wire_id: str
    layout_kind: str
    definition: TemplateDefinition
    optional_names: tuple[str, ...]
    partner_definition: TemplateDefinition | None
    size: str = "2x2"
    slot_definitions: tuple[TemplateDefinition, ...] = ()

    @property
    def capability_id(self) -> str:
        return self.definition.capability_id or ""

    @property
    def layout_template_id(self) -> str:
        return _LAYOUT_BY_KIND[self.layout_kind]


def _slug(wire_id: str) -> str:
    return wire_id.split("@")[0].lower()


def _sample_value(capability_id: str, binding) -> Any:
    override = _SAMPLE_BY_PATH.get((capability_id, binding.path))
    if override is not None:
        return override
    return _FALLBACK_SAMPLE_BY_TYPE[binding.data_type]


def _present_definitions(
    definition: TemplateDefinition,
    absent: frozenset[str],
) -> tuple[tuple[str, Any], ...]:
    return tuple(
        (name, binding)
        for name, binding in definition.bindings.items()
        if name not in absent
    )


# 能力级上下文字段：始终写进 dataModelSchema，但从不进入 candidateOutputFields。
# 只为满足 Search 记录的 manifest 级必填路径与业务事实抽取（蓝牙设备身份），
# 不改变「模板 optional 绑定缺席」这一被冻结的维度。
_CONTEXT_FIELD_TYPES_BY_CAPABILITY = {
    "ViewWeather": {
        "/current/temperatureText": "string",
        "/current/condition": "string",
    },
    "GetEarphoneInfo": {
        "/earphoneName": "string",
        "/isConnected": "boolean",
    },
}

# 模板级上下文字段：单绑定新模板（仅声明一个字段）不足以让 content_selectors
# 的事实抽取器产出 facts（睡眠抽取器要求 nightSleepDurationText/totalNapDurationText，
# 日程抽取器要求首事件 title+dtStart）。仅补齐抽取器下限，不进入
# candidateOutputFields，不改变「模板 optional 绑定缺席」这一被冻结的维度。
_TEMPLATE_CONTEXT_FIELD_TYPES: dict[str, dict[str, str]] = {
    "SleepOverviewScoreCompact@1": {
        "/nightSleepDurationText": "string",
    },
    "ScheduleOverviewReminderCompact@1": {
        "/events/0/title": "string",
        "/events/0/dtStart": "string",
    },
}

# 双数据源模板（bindingCount=2）的两个 TaskSpec 数据根（与 q034 语料一致）。
_DUAL_SOURCE_ROOTS = ("/data/weather1", "/data/weather2")


def _data_roots(definition: TemplateDefinition) -> tuple[str, ...]:
    domain = (definition.data_domain or "/data").rstrip("/")
    if any(binding.root_index for binding in definition.bindings.values()):
        return _DUAL_SOURCE_ROOTS
    return (domain,)


def _schema_and_bindings(
    entries: list[tuple[TemplateDefinition, frozenset[str]]],
) -> tuple[dict[str, Any], tuple[CandidateDataBinding, ...]]:
    """按缺席子集同步构建 dataModelSchema 与 candidateOutputFields。

    每个模板按其绑定 root_index 拆分数据根（双源模板产出两个同能力绑定）；
    缺席绑定同步从对应根的 schema 与 candidateOutputFields 中剪除。
    """
    schema: dict[str, Any] = {"data": {}}
    bindings: list[CandidateDataBinding] = []
    for definition, absent in entries:
        capability_id = definition.capability_id or ""
        roots = _data_roots(definition)
        for root_index, domain in enumerate(roots):
            fields: dict[str, Any] = {}
            for _name, binding in _present_definitions(definition, absent):
                if binding.root_index != root_index:
                    continue
                leaf = {
                    "type": binding.data_type,
                    "description": "trusted provider field",
                    "sampleValue": _sample_value(capability_id, binding),
                }
                _set_path(schema, f"{domain}{binding.path}", leaf)
                fields[binding.path.lstrip("/")] = leaf
            for path, data_type in _CONTEXT_FIELD_TYPES_BY_CAPABILITY.get(
                capability_id, {}
            ).items():
                if root_index == 0:
                    _set_path(
                        schema,
                        f"{domain}{path}",
                        {
                            "type": data_type,
                            "description": "trusted provider field",
                            "sampleValue": _SAMPLE_BY_PATH.get(
                                (capability_id, path),
                                _FALLBACK_SAMPLE_BY_TYPE[data_type],
                            ),
                        },
                    )
            for path, data_type in _TEMPLATE_CONTEXT_FIELD_TYPES.get(
                definition.wire_id, {}
            ).items():
                if root_index == 0:
                    _set_path(
                        schema,
                        f"{domain}{path}",
                        {
                            "type": data_type,
                            "description": "trusted provider field",
                            "sampleValue": _SAMPLE_BY_PATH.get(
                                (capability_id, path),
                                _FALLBACK_SAMPLE_BY_TYPE[data_type],
                            ),
                        },
                    )
            if not fields and capability_id:
                # 无声明绑定的 props 驱动泛型模板（GenericMetricOverview* 等）：
                # 数据路径来自必填 data-path 型 props，取值用预览数据集的同源
                # 字面量表，据此合成数据根与 candidateOutputFields。
                prop_schema = definition.variants[0].parameters_schema
                for name in prop_schema.get("required", ()):
                    if parameter_value_kind(name, prop_schema.get("properties", {}).get(name, {})) != "data-path":
                        continue
                    path = _MATRIX_TEXT_PARAMS.get((definition.wire_id, name))
                    if not isinstance(path, str) or not path.startswith("/"):
                        continue
                    sample = _SAMPLE_BY_PATH.get((capability_id, path))
                    if isinstance(sample, bool):
                        data_type = "boolean"
                    elif isinstance(sample, int):
                        data_type = "integer"
                    elif isinstance(sample, float):
                        data_type = "number"
                    else:
                        data_type = "string"
                    leaf = {
                        "type": data_type,
                        "description": "trusted provider field",
                        "sampleValue": sample if sample is not None else "",
                    }
                    _set_path(schema, f"{domain}{path}", leaf)
                    fields[path.lstrip("/")] = leaf
            bindings.append(
                CandidateDataBinding(
                    capabilityId=capability_id,
                    writeResultTo=domain,
                    candidateOutputFields=[f"/{key}" for key in sorted(fields)],
                )
            )
    return schema, tuple(bindings)


def _event_candidates(capability_id: str, count: int) -> tuple[EventAction, ...]:
    return tuple(
        EventAction(
            id=event_id,
            call="clickToIntent",
            args={"intentName": event_id},
        )
        for event_id in _EVENT_FIXTURES_BY_CAPABILITY[capability_id][:count]
    )


def _template_asset_params(
    definition: TemplateDefinition,
    asset_pool: tuple[dict[str, Any], ...],
) -> dict[str, str]:
    """只填必填资产参数与必填字面量参数；可选参数留给模板 ``#if`` 条件剪枝。

    每个必填资产参数按其语义标签要求从资产池中确定性挑选（与引擎
    ``asset_semantic_tags`` 同源的标签推导）；必填非资产参数取预览数据集的
    同源字面量取值（``_TEXT_BY_TEMPLATE_PARAMETER``）。
    """
    schema = definition.variants[0].parameters_schema
    asset_tags = definition.asset_parameter_semantic_tags
    params: dict[str, str] = {}
    for name in schema.get("required", ()):
        if name in asset_tags or any(
            token in name.casefold() for token in ("icon", "image", "asset", "source", "src")
        ):
            required_tags = set(asset_tags.get(name, ()))
            for source in asset_pool:
                if required_tags.issubset(set(asset_semantic_tags(source))):
                    params[name] = source["src"]
                    break
            else:
                raise ValueError(
                    f"no asset fixture matches {definition.wire_id}/{name} tags={sorted(required_tags)}"
                )
            continue
        override = _MATRIX_TEXT_PARAMS.get((definition.wire_id, name))
        if override is None:
            raise ValueError(f"unfilled non-asset required param: {definition.wire_id}/{name}")
        params[name] = override
    return params


def _template_call(
    definition: TemplateDefinition,
    asset_pool: tuple[dict[str, Any], ...],
) -> str:
    params = _template_asset_params(definition, asset_pool)
    rendered = ",".join(f'"{key}":"{value}"' for key, value in params.items())
    return f'Template("{definition.wire_id}",{{{rendered}}})'


def _action_count_for(layout_kind: str) -> int:
    return {
        "Hero": 1,
        "Compact": 2,
        "HeroTitle": 1,
        "WideHero": 1,
        "WideFull": 0,
        "WideHalf": 0,
    }.get(layout_kind, 0)


def _action_pills(capability_id: str, action_count: int) -> tuple[str, ...]:
    return tuple(
        f'Template("PillAction@1",{{"actionId":"{event_id}","label":"{_action_label(_SimpleEvent(event_id))}"}})'
        for event_id in _EVENT_FIXTURES_BY_CAPABILITY[capability_id][:action_count]
    )


def _pinned_body(spec: _FamilySpec, asset_pool: tuple[dict[str, Any], ...]) -> str:
    calls = [_template_call(spec.definition, asset_pool)]
    if spec.partner_definition is not None:
        calls.append(_template_call(spec.partner_definition, asset_pool))
    calls.extend(_action_pills(spec.capability_id, _action_count_for(spec.layout_kind)))
    joined = ",".join(calls)
    return f'Template("{spec.layout_template_id}",{{}},{joined});'


async def _render_pipeline_combination(
    spec: _FamilySpec,
    absent: frozenset[str],
    enable_fusion_ball: bool = False,
) -> dict:
    action_count = _action_count_for(spec.layout_kind)
    if spec.slot_definitions:
        # wide 2x4 家族：缺席子集只作用于 lead 槽位，其余槽位保持 canonical。
        entries = [(spec.definition, absent)]
        entries.extend((slot, frozenset()) for slot in spec.slot_definitions)
    else:
        entries = [(spec.definition, absent)]
        if spec.partner_definition is not None:
            entries.append((spec.partner_definition, frozenset()))
    schema, coverage_bindings = _schema_and_bindings(entries)
    capabilities = tuple(entry[0].capability_id for entry in entries)
    events = _event_candidates(capabilities[0], action_count) + tuple(
        EventAction(id=event_id, call="clickToIntent", args={"intentName": event_id})
        for event_id in _EXTRA_CANDIDATE_EVENTS_BY_TEMPLATE.get(spec.wire_id, ())
    )
    asset_pool = tuple(
        source
        for definition, _absent in entries
        for source in _ASSET_FIXTURES_BY_BUSINESS.get(definition.business_id or "", ())
    )
    task_spec = TaskSpec(
        userQuery=_USER_QUERY_BY_CAPABILITY[capabilities[0]],
        size=spec.size,
        eventCandidates=events,
        assetCandidates=list(asset_pool),
        dataModelSchema=schema,
    )
    card_spec = {
        "title": _TITLE_BY_CAPABILITY[capabilities[0]],
        "description": _USER_QUERY_BY_CAPABILITY[capabilities[0]],
        "suggestSize": spec.size,
        "dataBindings": [
            {
                "capabilityId": binding.capabilityId,
                "arguments": {},
                "writeResultTo": binding.writeResultTo,
            }
            for binding in coverage_bindings
        ],
    }
    action_ids = tuple(event.id for event in events if event.id)
    # 同能力多数据根（双源模板）时检索要求显式字段被每个根同时覆盖（交集）。
    output_fields: dict[str, set[str]] = {}
    for binding in coverage_bindings:
        current = set(binding.candidateOutputFields)
        if binding.capabilityId not in output_fields:
            output_fields[binding.capabilityId] = current
        else:
            output_fields[binding.capabilityId] &= current
    model = _PinnedPlanModel(
        output_fields_by_capability={
            capability_id: tuple(sorted(paths or ()))
            for capability_id, paths in output_fields.items()
        },
        action_ids=action_ids,
        body=_pinned_body(spec, asset_pool),
    )
    result = await generate_template_a2ui(
        task_spec,
        card_spec,
        coverage_bindings,
        model,
        enable_fusion_ball=enable_fusion_ball,
        trusted_template_candidate_ids=tuple(
            definition.wire_id for definition, _absent in entries
        ),
    )
    return a2ui_messages(result)


def _combination_key(absent: frozenset[str], optional_names: tuple[str, ...]) -> str:
    if not absent:
        return "all"
    if len(absent) == len(optional_names):
        return "none"
    return "absent_" + "+".join(sorted(absent))


# 管线确定拒绝的组合（empirically frozen）：这些缺席子集会把 cardtpl 的容器
# 剪空或触发检索判别器/manifest 必填路径门禁，引擎以 TemplateGenerationError /
# TemplateRouteNotApplicable 拒绝；拒绝行为本身被冻结在 excludedCombinations，
# 引擎语义变化会以 diff 呈现并走复核。
_COMBINATION_REFUSAL_REASONS: dict[str, str] = {
    "SleepOverviewFull@1": (
        "缺席子集剪空仅含 napDuration/deepDuration/score/status 的 cardtpl 容器，"
        "编译期拒绝（Expanded container must contain at least one child）"
    ),
    "SleepOverviewNapFull@1": (
        "startTime/endTime 任一缺席会剪空睡眠时段行容器，编译期拒绝"
        "（Expanded container must contain at least one child）"
    ),
    "HeartRateOverviewMinMaxFull@1": (
        "updatedAt 缺席会剪空更新时间行容器，编译期拒绝"
        "（Expanded container must contain at least one child）"
    ),
    "WeatherOverviewTravelSupport@1": (
        "daily/4 预报字段子集缺席会剪空旅行预报容器，编译期拒绝"
        "（Expanded container must contain at least one child）；全缺席时无显式字段"
    ),
    "WeatherOverviewAlertFull@1": (
        "检索判别器要求显式 /current/alertLevel（缺 alertLevel 组合不可达）；"
        "updatedAt 缺席命中 manifest 必填路径门禁"
    ),
}


def _register_template_family(spec: _FamilySpec) -> None:
    subsets = [
        frozenset(absent)
        for size in range(len(spec.optional_names) + 1)
        for absent in combinations(spec.optional_names, size)
    ]
    refusal_reason = _COMBINATION_REFUSAL_REASONS.get(spec.wire_id)

    def build_family(enable_fusion_ball: bool) -> dict:
        combinations_payload: dict[str, dict] = {}
        excluded: dict[str, str] = {}
        for absent in subsets:
            key = _combination_key(absent, spec.optional_names)
            try:
                combinations_payload[key] = asyncio.run(
                    _render_pipeline_combination(
                        spec, absent, enable_fusion_ball=enable_fusion_ball
                    )
                )
            except (TemplateGenerationError, TemplateRouteNotApplicable, ValueError) as exc:
                excluded[key] = (
                    refusal_reason
                    or f"{type(exc).__name__}: {exc}"
                )
        ids = combo_sample_ids()
        result = {
            "templateId": spec.wire_id,
            "size": spec.size,
            "fusionBall": enable_fusion_ball,
            "layout": spec.layout_template_id,
            "optionalBindings": list(spec.optional_names),
            "sampleIds": {
                key: ids[(spec.wire_id, key)]
                for key in sorted(
                    set(combinations_payload) | set(excluded)
                )
            },
            "combinations": combinations_payload,
        }
        if excluded:
            result["excludedCombinations"] = excluded
        if not combinations_payload:
            raise ValueError(
                f"pipeline refused every combination for {spec.wire_id} "
                f"(fusion_ball={enable_fusion_ball}): {excluded}"
            )
        return result

    # 同一模板冻结两份家族：常规渲染 + 融球模式（enable_fusion_ball=True）。
    scenario(f"pipeline_combo__{_slug(spec.wire_id)}")(
        lambda enable_fusion_ball=False: build_family(enable_fusion_ball)
    )
    scenario(f"pipeline_combo_fusion__{_slug(spec.wire_id)}")(
        lambda enable_fusion_ball=True: build_family(enable_fusion_ball)
    )


# 显式记录无法通过管线渲染的 2x2 模板（不允许静默丢弃）。
# BatteryOverviewSupport@1：双业务 TwoSupportLayout 的唯一归宿里，第二层提示词
# 契约门禁 _provider_variant_matches_trusted_state 对 BatteryOverview@1 的
# support 族变体一律拒绝（prompt 侧 state-independent 集合不含 support 族，
# "support" 也不以 low/charging/normal 任一状态前缀开头；且 battery+earphone
# 组合还要求 {state}Phone 变体，本分支无此模板）。编译门禁虽然放行，但模板
# 根本到不了编译阶段，故本族无法走管线，只能显式跳过。
_SKIPPED_TEMPLATES: dict[str, str] = {
    "BatteryOverviewSupport@1": (
        "BatteryOverview@1 support 族变体无法通过第二层提示词契约门禁 "
        "(_provider_variant_matches_trusted_state)，TwoSupportLayout 组合不可达"
    ),
    "ScheduleOverviewHeroContent@1": (
        "双业务第二业务无法单独构成 atomic plan（Search: candidates cannot form "
        "a supported atomic plan）；其 DSL 渲染已由 HeroTitle 配对家族 "
        "(pipeline_combo__weatheroverviewherotitle) 冻结"
    ),
    "GenericMetricOverviewCompact@1": (
        "props 驱动泛型模板无声明绑定，检索无法从输出字段覆盖角度选中它；"
        "上游仅在 2x4 残差组合白名单（GenericMetricOverview + 2x4）路由该业务，"
        "2x2 确定性 Search 无路由；其 DSL/props 契约由 internal_contracts 与 "
        "wide_template_planner 用例固化"
    ),
    "GenericMetricOverviewDualCompact@1": (
        "同 GenericMetricOverviewCompact@1：无声明绑定的 props 驱动泛型模板，"
        "2x2 确定性 Search 无路由"
    ),
    "BluetoothDeviceOverviewCompletePhoneWideFull@1": (
        "phone-earphone 双业务 2x4 组合的 phone 槽模板：布局门禁要求同体包含 "
        "BatteryOverview 槽位（paired_with_phone），引擎尚无 battery+bluetooth "
        "的 2x4 配对 planner 路径，单模板家族无法满足；等上游补齐配对路由后入阵"
    ),
    "BluetoothDeviceOverviewEarbudsPhoneWideFull@1": (
        "同 BluetoothDeviceOverviewCompletePhoneWideFull@1：phone-earphone "
        "双业务 2x4 配对路由缺失"
    ),
    "BatteryOverviewPercentLevelHero@1": (
        "BatteryOverviewChargingProgressHero@1 扩展后以 optionalData 覆盖 "
        "/batteryCapacityLevelDesc（Q049 数据契约），文本等级兜底的检索门"
        "（仅在无其它模板完整覆盖二字段意图时放行）不再放行该变体，全部组合被拒；"
        "等级字段的渲染由 pipeline_combo__batteryoverviewchargingprogresshero 家族冻结"
    ),
    "WorkoutOverviewTrainingRecordHero@1": (
        "WorkoutOverview 投影仅经 extract_workout_latest_facts（latest 变体），"
        "该选择器要求 /exerciseDurationText 才产出事实；本模板面向 Q027 的"
        "无时长训练记录契约（targetDateText+exerciseTypeName+heartRateMin），"
        "schema 无 exerciseDurationText 时投影为空（no renderable provider facts）。"
        "待 Q027 语料补充时长字段或训练记录投影分支扩展后再入阵；其检索/计划路由"
        "已由单测与 Q027 用例固化"
    ),
}


def _hero_content_partner(capability_id: str) -> TemplateDefinition:
    """HeroTitle 模板唯一的双业务搭档：另一个能力下唯一的 HeroContent 模板。"""
    for wire_id in sorted(_REGISTRY.provider_template_ids):
        if provider_template_layout_kind(wire_id) != "HeroContent":
            continue
        partner = _REGISTRY.require_template(wire_id)
        if partner.capability_id != capability_id:
            return partner
    raise ValueError(f"no HeroContent partner available for {capability_id}")


def _collect_family_specs() -> list[_FamilySpec]:
    specs: list[_FamilySpec] = []
    for wire_id in sorted(_REGISTRY.provider_template_ids):
        if wire_id in _SKIPPED_TEMPLATES:
            continue
        definition = _REGISTRY.require_template(wire_id)
        if definition.capability_id is None:
            continue
        layout_kind = provider_template_layout_kind(wire_id)
        if layout_kind not in _LAYOUT_BY_KIND:
            continue
        # k=0 模板同样入阵：单一 all 组合 = 每个模板至少一次全链路 DSL 固化。
        optional_names = tuple(sorted(definition.variants[0].optional_bindings))
        partner_definition: TemplateDefinition | None = None
        size = "2x2"
        slot_definitions: tuple[TemplateDefinition, ...] = ()
        if layout_kind in ("WideHero", "WideFull", "WideHalf"):
            # 2x4 wide 家族（#404 后 Search 支持 2x4）：单模板/成对槽位组合，
            # size=2x4，缺席子集只作用于 lead。WideHalf 布局需要两个半宽槽位，
            # 与排序相邻的 WideHalf 模板配对（wrap-around，覆盖全部半宽模板）。
            size = "2x4"
            if layout_kind == "WideHalf":
                halves = sorted(
                    other
                    for other in _REGISTRY.provider_template_ids
                    if provider_template_layout_kind(other) == "WideHalf"
                    and other not in _SKIPPED_TEMPLATES
                    and _REGISTRY.require_template(other).capability_id is not None
                )
                partner_wire_id = halves[(halves.index(wire_id) + 1) % len(halves)]
                partner_definition = _REGISTRY.require_template(partner_wire_id)
        elif layout_kind == "Support":
            partner_capability, partner_wire_id = _SUPPORT_PARTNER_BY_CAPABILITY[
                definition.capability_id
            ]
            partner_definition = _REGISTRY.require_template(partner_wire_id)
            if partner_definition.capability_id != partner_capability:
                raise ValueError(f"unsupported Support partner: {partner_wire_id}")
        elif layout_kind == "HeroTitle":
            # HeroTitleContentActionLayout 必须按位置配一个 HeroContent 业务。
            partner_definition = _hero_content_partner(definition.capability_id or "")
        specs.append(
            _FamilySpec(
                wire_id=wire_id,
                layout_kind=layout_kind,
                definition=definition,
                optional_names=optional_names,
                partner_definition=partner_definition,
                size=size,
                slot_definitions=slot_definitions,
            )
        )
    return specs


for _spec in _collect_family_specs():
    _register_template_family(_spec)


_COMBO_SAMPLE_ID_CACHE: dict[tuple[str, str], str] | None = None


def combo_sample_ids() -> dict[tuple[str, str], str]:
    """(templateId, comboKey) → 端侧画廊顺序编号 C001…（单一事实来源）。

    排序规则与 ``test_support/combo_gallery.py`` 的导出顺序一致：Provider
    按 id 排序 → 模板按 wire_id 排序 → 组合按 caseId（``<slug>__<key>``）
    字符串排序；结构性跳过模板的伪用例键为 ``"skipped"``。家族金样把编号
    固化在顶层 ``sampleIds`` 映射里，画廊导出直接复用，两侧不会漂移。
    """
    global _COMBO_SAMPLE_ID_CACHE
    if _COMBO_SAMPLE_ID_CACHE is not None:
        return _COMBO_SAMPLE_ID_CACHE
    specs_by_wire = {spec.wire_id: spec for spec in _collect_family_specs()}
    groups: dict[str, list[str]] = {}
    for wire_id, spec in specs_by_wire.items():
        groups.setdefault(spec.definition.provider_id, []).append(wire_id)
    for wire_id in _SKIPPED_TEMPLATES:
        if wire_id in specs_by_wire:
            continue
        definition = _REGISTRY.require_template(wire_id)
        groups.setdefault(definition.provider_id, []).append(wire_id)
    ids: dict[tuple[str, str], str] = {}
    sequence = 0
    for provider_id in sorted(groups):
        for wire_id in sorted(groups[provider_id]):
            slug = _slug(wire_id)
            if wire_id in _SKIPPED_TEMPLATES and wire_id not in specs_by_wire:
                sequence += 1
                ids[(wire_id, "skipped")] = f"C{sequence:03d}"
                continue
            spec = specs_by_wire[wire_id]
            keys = [
                _combination_key(frozenset(absent), spec.optional_names)
                for size in range(len(spec.optional_names) + 1)
                for absent in combinations(spec.optional_names, size)
            ]
            for key in sorted(keys):
                sequence += 1
                ids[(wire_id, key)] = f"C{sequence:03d}"
    _COMBO_SAMPLE_ID_CACHE = ids
    return ids


def test_pipeline_combinations_match_goldens() -> None:
    from services.template_generation.test_support import golden_scenarios

    for scenario_id in sorted(golden_scenarios._REGISTRY):
        if scenario_id.startswith(("pipeline_combo__", "pipeline_combo_fusion__")):
            assert_golden_scenario(scenario_id)


def test_skipped_templates_stay_documented_and_accurate() -> None:
    """跳过清单必须指向矩阵范围内真实存在的 2x2 模板，防止清单过期。"""
    for wire_id in sorted(_SKIPPED_TEMPLATES):
        definition = _REGISTRY.require_template(wire_id)
        assert definition.capability_id is not None, wire_id
        assert provider_template_layout_kind(wire_id) in _LAYOUT_BY_KIND, wire_id
