"""双业务（天气+日程）检索排序、主题归属与 HeroTitle/HeroContent 组合的策略测试。

检索策略的确定性结论已固化为场景金样（Layer C）：主题归属矩阵（版本门控、
缺失融球主题回退、非属主组合）、rejection 矩阵（错误类型+完整报错文案）、
单业务选模矩阵（专项字段/逐日数组/共享能力/蓝牙耳机/可选天气标题×动作数
等选模结论）、检索索引逐字段匹配与卡尺寸过滤、受信画廊字段收敛、天气
Full 模板可选数据元数据，以及
双业务 29 组参数组合（卡片标题 × 融球主题 × 天气字段状态；wave-1 代表
组合除外）的选中模板 ID、A2UI 文本摘要、主题着色、根背景与可信字面量。
完整 A2UI 产物仍由 `retrieval__dual_business_hero_title_content` 整体冻结。
候选诊断日志、24 上限裁剪、布局后缀诊断、动作参数字段豁免等 monkeypatch
过程断言，两份第一层 prompt 内容契约，以及两条已知红线用例（q025 风力、
无动作只留 Full——在 HEAD 即失败，保持原样待修）不迁移。引擎或模板改动
后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Callable, cast

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.content_selectors import (
    apply_content_selectors,
)
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan import template_retrieval as retrieval_module
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.cardplan.retrieval_index import (
    FieldToken,
    TemplateVariantSearchRecord,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateRetrievalQuery,
    _component_templates_for_capability,
    _limit_component_templates,
    _required_field_template_groups,
    build_template_retrieval_prompt,
    restrict_query_to_preferred_templates,
    retrieve_template_variants,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_WEATHER_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/current/coldLevel",
    "/daily/0/temperatureRangeText",
)

_WEATHER_TITLE_PATHS = (
    "/data/weather/location/districtName",
    "/data/weather/current/temperatureText",
    "/data/weather/current/condition",
)

_HERO_TITLE_TEMPLATE_IDS = (
    "WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1", "PillAction@1",
)


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {"type": data_type, "description": "trusted", "sampleValue": value}


def _task() -> TaskSpec:
    return TaskSpec(
        userQuery="显示温度和天气情况",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"districtName": _field("青浦区")},
                    "current": {
                        "temperatureText": _field("29°C"),
                        "condition": _field("多云"),
                        "airQuality": _field("良"),
                        "coldLevel": _field("低"),
                    },
                    "daily": [{"temperatureRangeText": _field("25° / 32°")}],
                }
            }
        },
    )


def _binding() -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_FIELDS),
    )


def _card_spec() -> dict[str, Any]:
    return {
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }


def _query(*paths: str) -> TemplateRetrievalQuery:
    return TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={"ViewWeather": paths},
    )


def _capture_error(build: Callable[[], Any]) -> dict[str, str]:
    try:
        build()
    except Exception as error:  # noqa: BLE001 - 冻结错误类型与完整文案
        return {"errorType": type(error).__name__, "message": str(error)}
    return {"error": "NO_ERROR"}


def _selection_value(result: Any) -> dict[str, Any]:
    """把检索选模结果收敛为可冻结的 canonical 载荷。"""
    return {
        "componentIds": [item.component_id for item in result.component_candidates],
        "templateIds": [
            list(item.available_template_ids) for item in result.component_candidates
        ],
        "requiredGroups": [list(group) for group in result.required_template_groups],
        "actionIds": list(result.action_ids),
        "themeId": result.scope.theme_id,
    }


# --------------------------------------------------------------------------
# 场景金样构建函数
# --------------------------------------------------------------------------


@scenario("retrieval__hero_content_theme_matrix")
def _build_hero_content_theme_matrix() -> dict[str, Any]:
    """主题归属解析矩阵：版本门控、融球回退与非属主组合的解析值。"""
    cases: dict[str, Any] = {}
    gate_cases = (
        (False, "family-weather-care-blue", "version_gate__plain_family"),
        (False, "meeting-paper-neutral", "version_gate__plain_meeting"),
        (True, "fusion-weather-blue", "fusion__weather_blue"),
        (True, "fusion-schedule-cool", "fusion__schedule_cool"),
        (True, "meeting-paper-neutral", "fusion__meeting_requested"),
    )
    for enabled, requested_theme, key in gate_cases:
        registry = get_cardplan_registry(enabled)
        cases[key] = registry.hero_content_theme_id(_HERO_TITLE_TEMPLATE_IDS, requested_theme)

    fallback_registry = CardPlanRegistry(enable_fusion_ball=True)
    fallback_registry.themes.pop("fusion-schedule-cool")
    cases["fusion__schedule_theme_removed"] = fallback_registry.hero_content_theme_id(
        ("WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"),
        "fusion-weather-blue",
    )

    non_owner_cases = (
        ("empty", ()),
        ("title_only", ("WeatherOverviewHeroTitle@1",)),
        ("content_only", ("ScheduleOverviewHeroContent@1",)),
        ("hero_with_content", ("WeatherOverviewHero@1", "ScheduleOverviewHeroContent@1")),
        ("title_with_date_full", ("WeatherOverviewHeroTitle@1", "ScheduleOverviewDateFull@1")),
        (
            "title_content_with_sleep",
            (
                "WeatherOverviewHeroTitle@1",
                "ScheduleOverviewHeroContent@1",
                "SleepOverviewFull@1",
            ),
        ),
    )
    registry = get_cardplan_registry(True)
    for key, template_ids in non_owner_cases:
        cases["non_owner__" + key] = [
            registry.hero_content_theme_owner(template_ids),
            registry.hero_content_theme_id(template_ids, "fusion-weather-blue"),
        ]
    return cases


@scenario("retrieval__rejection_matrix")
def _build_rejection_matrix() -> dict[str, Any]:
    """检索 rejection 矩阵：输入组合 → 冻结的错误类型与完整文案。"""
    cases: dict[str, Any] = {}

    def uncontained_query_field() -> None:
        query = _query("/current/windDirection")
        task = _task()
        task.dataModelSchema["data"]["weather"]["current"]["windDirection"] = _field("东南风")
        binding = _binding().model_copy(
            update={"candidateOutputFields": [*_WEATHER_FIELDS, "/current/windDirection"]}
        )
        retrieve_template_variants(query, task, get_cardplan_registry(), (binding,), _card_spec())

    cases["query_field_not_contained"] = _capture_error(uncontained_query_field)

    def missing_schema_field() -> None:
        task = _task()
        del task.dataModelSchema["data"]["weather"]["current"]["condition"]
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )

    cases["provider_required_field_missing"] = _capture_error(missing_schema_field)

    def mismatched_field_type() -> None:
        task = _task()
        task.dataModelSchema["data"]["weather"]["current"]["condition"] = _field(1, "integer")
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )

    cases["provider_required_field_type_mismatch"] = _capture_error(mismatched_field_type)

    def absent_daily_index() -> None:
        task = TaskSpec(
            userQuery="展示明日天气",
            size="2x2",
            dataModelSchema={
                "data": {
                    "weather": {"daily": [{"condition": _field("晴")}]},
                }
            },
        )
        path = "/daily/1/condition"
        binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=[path],
        )
        retrieve_template_variants(
            _query(path), task, get_cardplan_registry(), (binding,), _card_spec()
        )

    cases["daily_index_absent"] = _capture_error(absent_daily_index)

    def calendar_without_covering_business() -> None:
        task = TaskSpec(
            userQuery="显示日期和下一场会议的标题、时间",
            size="2x2",
            dataModelSchema={
                "data": {
                    "calendar": {
                        "events": [
                            {
                                "startDate": _field("2026-08-19"),
                                "title": _field("UI需求评审会"),
                                "dtStart": _field("14:00"),
                                "dtEnd": _field("15:30"),
                            }
                        ],
                        "updatedAt": _field("2026-08-19 09:00"),
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="GetCalendarEvents",
            writeResultTo="/data/calendar",
            candidateOutputFields=[
                "/events/0/startDate",
                "/events/0/title",
                "/events/0/dtStart",
                "/events/0/dtEnd",
                "/updatedAt",
            ],
        )
        retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="meeting-paper-neutral",
                requiredOutputFieldsByCapability={
                    "GetCalendarEvents": (
                        "/events/0/startDate",
                        "/events/0/title",
                        "/events/0/dtStart",
                    )
                },
            ),
            task,
            CardPlanRegistry(),
            (binding,),
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {
                        "capabilityId": "GetCalendarEvents",
                        "writeResultTo": "/data/calendar",
                    }
                ],
            },
        )

    cases["calendar_without_covering_business"] = _capture_error(
        calendar_without_covering_business
    )

    def card_size_2x4_prompt() -> None:
        task = _task().model_copy(update={"size": "2x4"})
        build_template_retrieval_prompt(task, cast(CardPlanRegistry, object()), (_binding(),))

    cases["card_size_2x4_prompt"] = _capture_error(card_size_2x4_prompt)

    def card_size_2x4_retrieval() -> None:
        task = _task().model_copy(update={"size": "2x4"})
        card_spec = _card_spec() | {"suggestSize": "2x4"}
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            cast(CardPlanRegistry, object()),
            (_binding(),),
            card_spec,
        )

    cases["card_size_2x4_retrieval"] = _capture_error(card_size_2x4_retrieval)

    def weather_and_memory() -> None:
        task = _task()
        task.dataModelSchema["data"]["systemMem"] = {
            "usagePercent": _field(65, "number"),
            "availableMemText": _field("4.2 GB"),
            "totalMemText": _field("12 GB"),
        }
        memory = CandidateDataBinding(
            capabilityId="GetSystemMemInfo",
            writeResultTo="/data/systemMem",
            candidateOutputFields=[
                "/usagePercent",
                "/availableMemText",
                "/totalMemText",
            ],
        )
        retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": (
                        "/location/districtName",
                        "/current/temperatureText",
                        "/current/condition",
                        "/current/coldLevel",
                    ),
                    "GetSystemMemInfo": (
                        "/usagePercent",
                        "/availableMemText",
                        "/totalMemText",
                    ),
                },
            ),
            task,
            CardPlanRegistry(),
            (_binding(), memory),
            {
                "dataBindings": [
                    {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
                    {
                        "capabilityId": "GetSystemMemInfo",
                        "writeResultTo": "/data/systemMem",
                    },
                ]
            },
        )

    cases["dual_data_business"] = _capture_error(weather_and_memory)

    def two_businesses_one_capability() -> None:
        task = TaskSpec(
            userQuery="显示昨晚睡眠时长和今天步数",
            size="2x2",
            dataModelSchema={
                "data": {
                    "healthSport": {
                        "nightSleepDurationText": _field("7小时1分"),
                        "sleepScore": _field(82, "integer"),
                        "dailySteps": _field(6200, "integer"),
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="GetHealthAndSportSummary",
            writeResultTo="/data/healthSport",
            candidateOutputFields=[
                "/nightSleepDurationText",
                "/sleepScore",
                "/dailySteps",
            ],
        )
        retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="race-sunrise-action",
                requiredOutputFieldsByCapability={
                    "GetHealthAndSportSummary": (
                        "/nightSleepDurationText",
                        "/dailySteps",
                    )
                },
            ),
            task,
            CardPlanRegistry(),
            (binding,),
            {
                "dataBindings": [
                    {
                        "capabilityId": "GetHealthAndSportSummary",
                        "writeResultTo": "/data/healthSport",
                    }
                ]
            },
        )

    cases["dual_business_one_capability"] = _capture_error(two_businesses_one_capability)

    def weather_and_battery(uv_field: bool) -> None:
        current: dict[str, Any] = {
            "temperatureText": _field("29°C"),
            "condition": _field("多云"),
        }
        if uv_field:
            current["uvIndex"] = _field("弱")
        task = TaskSpec(
            userQuery=(
                "显示天气紫外线和手机电量状态" if uv_field else "显示天气和手机电量状态"
            ),
            size="2x2",
            dataModelSchema={
                "data": {
                    "weather": {
                        "location": {
                            "districtName": _field("福田区"),
                        },
                        "current": current,
                    },
                    "phoneBattery": {
                        "batterySOC": _field(68, "integer"),
                        "batterySOCText": _field("68%"),
                        "batteryCapacityLevelDesc": _field("正常电量"),
                        "chargingStatusDesc": _field("未充电"),
                    },
                }
            },
        )
        weather_paths = [
            "/current/condition",
            "/current/temperatureText",
            "/location/districtName",
        ]
        weather_paths.append("/current/uvIndex" if uv_field else "/current/coldLevel")
        if not uv_field:
            task.dataModelSchema["data"]["weather"]["current"]["coldLevel"] = _field("低")
        weather_binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=weather_paths,
        )
        battery_binding = CandidateDataBinding(
            capabilityId="GetPhoneBatteryInfo",
            writeResultTo="/data/phoneBattery",
            candidateOutputFields=[
                "/batterySOC",
                "/batterySOCText",
                "/batteryCapacityLevelDesc",
                "/chargingStatusDesc",
            ],
        )
        retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": tuple(weather_paths),
                    "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
                },
            ),
            task,
            get_cardplan_registry(),
            (weather_binding, battery_binding),
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
                    {
                        "capabilityId": "GetPhoneBatteryInfo",
                        "writeResultTo": "/data/phoneBattery",
                    },
                ],
            },
        )

    cases["weather_and_battery"] = _capture_error(lambda: weather_and_battery(False))
    cases["weather_uv_and_battery"] = _capture_error(lambda: weather_and_battery(True))

    def countdown_and_weather() -> None:
        task = TaskSpec(
            userQuery="使用2*2规格，做个马拉松赛事倒计时卡片。",
            size="2x2",
            dataModelSchema={
                "data": {
                    "countdown": {"countdownDays": _field(30, "integer")},
                    "weather": {
                        "location": {"districtName": _field("浦东新区")},
                        "current": {
                            "temperatureText": _field("29°C"),
                            "condition": _field("多云"),
                            "uvIndex": _field("中等"),
                            "airQuality": _field("良"),
                            "coldLevel": _field("低"),
                        },
                    },
                }
            },
        )
        bindings = (
            CandidateDataBinding(
                capabilityId="GetCountdownDays",
                writeResultTo="/data/countdown",
                candidateOutputFields=["/countdownDays"],
            ),
            CandidateDataBinding(
                capabilityId="ViewWeather",
                writeResultTo="/data/weather",
                candidateOutputFields=[
                    "/location/districtName",
                    "/current/temperatureText",
                    "/current/condition",
                    "/current/uvIndex",
                    "/current/airQuality",
                    "/current/coldLevel",
                ],
            ),
        )
        retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="race-sunrise-action",
                requiredOutputFieldsByCapability={
                    "GetCountdownDays": ("/countdownDays",),
                    "ViewWeather": (
                        "/current/temperatureText",
                        "/current/condition",
                        "/current/uvIndex",
                    ),
                },
            ),
            task,
            get_cardplan_registry(),
            bindings,
            {
                "suggestSize": "2x2",
                "title": "马拉松倒计时",
                "description": "底部显示赛事当日紫外线强度",
                "dataBindings": [
                    {
                        "capabilityId": "GetCountdownDays",
                        "writeResultTo": "/data/countdown",
                    },
                    {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
                ],
            },
        )

    cases["countdown_and_weather"] = _capture_error(countdown_and_weather)

    def unknown_selected_action() -> None:
        query = _query("/current/condition").model_copy(
            update={"action_ids": ("event.unknown",)}
        )
        retrieve_template_variants(
            query, _task(), get_cardplan_registry(), (_binding(),), _card_spec()
        )

    cases["unknown_selected_action"] = _capture_error(unknown_selected_action)

    def disabled_provider() -> None:
        registry = CardPlanRegistry(
            disabled_provider_ids=("com.huawei.weather.cli",),
        )
        retrieve_template_variants(
            _query("/current/condition"),
            _task(),
            registry,
            (_binding(),),
            _card_spec(),
        )

    cases["disabled_provider"] = _capture_error(disabled_provider)
    return cases


def _select(build: Callable[[], Any]) -> dict[str, Any]:
    """选模结论收敛：正常返回选模载荷，异常冻结错误类型与文案。"""
    try:
        result = build()
    except Exception as error:  # noqa: BLE001
        return {"errorType": type(error).__name__, "message": str(error)}
    return _selection_value(result)


@scenario("retrieval__selection_matrix")
def _build_selection_matrix() -> dict[str, Any]:
    """单业务选模矩阵：输入组合 → 冻结的组件/模板/分组/动作/主题结论。"""
    cases: dict[str, Any] = {}

    cases["cross_theme"] = _select(lambda: retrieve_template_variants(
        _query("/current/condition").model_copy(update={"theme_id": "meeting-paper-neutral"}),
        _task(),
        get_cardplan_registry(),
        (_binding(),),
        _card_spec(),
    ))

    def specialized(path: str, value: Any, data_type: str) -> Any:
        task = _task()
        field_name = path.rsplit("/", 1)[-1]
        task.dataModelSchema["data"]["weather"]["current"][field_name] = _field(value, data_type)
        binding = _binding().model_copy(
            update={"candidateOutputFields": [*_WEATHER_FIELDS, path]}
        )
        return retrieve_template_variants(
            _query(path), task, get_cardplan_registry(), (binding,), _card_spec()
        )

    cases["specialized_humidity"] = _select(
        lambda: specialized("/current/humidityPercent", 70.0, "number")
    )
    cases["specialized_uv"] = _select(lambda: specialized("/current/uvIndex", "中等", "string"))

    def daily(daily_items: list[dict[str, Any]], paths: tuple[str, ...]) -> Any:
        task = TaskSpec(
            userQuery="展示逐日天气",
            size="2x2",
            dataModelSchema={"data": {"weather": {"daily": daily_items}}},
        )
        binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=list(paths),
        )
        return retrieve_template_variants(
            _query(*paths), task, get_cardplan_registry(), (binding,), _card_spec()
        )

    cases["daily_date"] = _select(lambda: daily(
        [
            {},
            {
                "date": _field("2026-09-04"),
                "weekday": _field("星期五"),
                "condition": _field("多云"),
            },
        ],
        ("/daily/1/date", "/daily/1/weekday", "/daily/1/condition"),
    ))
    cases["daily_rain"] = _select(lambda: daily(
        [
            {},
            {
                "temperatureRangeText": _field("25℃ / 32℃"),
                "rainProbabilityPercent": _field("20%"),
            },
        ],
        ("/daily/1/temperatureRangeText", "/daily/1/rainProbabilityPercent"),
    ))
    cases["daily_compare"] = _select(lambda: daily(
        [
            {
                "condition": _field("晴"),
                "airQuality": _field("优"),
            },
            {
                "condition": _field("多云"),
                "airQuality": _field("良"),
            },
        ],
        (
            "/daily/0/condition",
            "/daily/0/airQuality",
            "/daily/1/condition",
            "/daily/1/airQuality",
        ),
    ))
    cases["daily_health"] = _select(lambda: daily(
        [
            {},
            {
                "airQuality": _field("良"),
                "uvIndex": _field("中等"),
                "coldLevel": _field("低"),
            },
        ],
        ("/daily/1/airQuality", "/daily/1/uvIndex", "/daily/1/coldLevel"),
    ))

    def calendar_shared_capability() -> Any:
        task = TaskSpec(
            userQuery="显示下一场会议的标题和时间",
            size="2x2",
            dataModelSchema={
                "data": {
                    "calendar": {
                        "events": [
                            {
                                "title": _field("项目例会"),
                                "dtStart": _field("14:00"),
                                "dtEnd": _field("15:00"),
                                "eventLocation": _field("A1 会议室"),
                            }
                        ]
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="GetCalendarEvents",
            writeResultTo="/data/calendar",
            candidateOutputFields=[
                "/events/0/title",
                "/events/0/dtStart",
                "/events/0/dtEnd",
                "/events/0/eventLocation",
            ],
        )
        query = TemplateRetrievalQuery(
            themeId="meeting-paper-neutral",
            requiredOutputFieldsByCapability={
                "GetCalendarEvents": (
                    "/events/0/title",
                    "/events/0/dtStart",
                    "/events/0/dtEnd",
                    "/events/0/eventLocation",
                )
            },
        )
        return retrieve_template_variants(
            query,
            apply_content_selectors(task, {"GetCalendarEvents"}),
            CardPlanRegistry(),
            (binding,),
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {"capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar"}
                ],
            },
        )

    cases["calendar_shared_capability"] = _select(calendar_shared_capability)
    cases["domain_only"] = _select(lambda: retrieve_template_variants(
        _query(), _task(), CardPlanRegistry(), (_binding(),), _card_spec()
    ))

    _WEATHER_ACTIONS = (
        ("event.open.weather", "Weather_CityCode"),
        ("event.start.navigate", "Navigation"),
    )

    def weather_with_actions(action_ids: tuple[str, ...]) -> Any:
        events = [
            EventAction(id=event_id, call="clickToDeeplink", args={"intentName": intent})
            for event_id, intent in _WEATHER_ACTIONS[: len(action_ids)]
        ]
        task = _task().model_copy(update={"eventCandidates": events})
        return retrieve_template_variants(
            _query("/current/condition").model_copy(update={"action_ids": action_ids}),
            task,
            CardPlanRegistry(),
            (_binding(),),
            _card_spec(),
        )

    cases["one_business_one_action"] = _select(
        lambda: weather_with_actions(("event.open.weather",))
    )
    cases["one_business_two_actions"] = _select(
        lambda: weather_with_actions(("event.open.weather", "event.start.navigate"))
    )

    def q001_condition_hero() -> Any:
        task = TaskSpec(
            userQuery="看杭州市西湖区现在是什么天气，点一下查看详情",
            size="2x2",
            eventCandidates=[
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={"intentName": "Weather_CityCode"},
                )
            ],
            dataModelSchema={
                "data": {
                    "weather": {
                        "location": {
                            "cityCode": _field("60814"),
                            "districtName": _field("西湖区"),
                            "prefectureName": _field("杭州市"),
                        },
                        "current": {"condition": _field("多云")},
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=[
                "/location/cityCode",
                "/location/districtName",
                "/location/prefectureName",
                "/current/condition",
            ],
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": ("/location/districtName", "/current/condition")
                },
                action=("event.open.weather",),
            ),
            task,
            get_cardplan_registry(),
            (binding,),
            _card_spec(),
        )

    cases["q001_condition_hero"] = _select(q001_condition_hero)

    def q004_alert_full() -> Any:
        task = TaskSpec(
            userQuery="重点看长沙当前天气预警和信息更新时间",
            size="2x2",
            dataModelSchema={
                "data": {
                    "weather": {
                        "current": {"alertLevel": _field("暴雨黄色预警")},
                        "updatedAt": _field("2026-09-03 10:00"),
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=["/current/alertLevel", "/updatedAt"],
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": ("/current/alertLevel", "/updatedAt")
                },
            ),
            task,
            get_cardplan_registry(),
            (binding,),
            _card_spec(),
        )

    cases["q004_alert_full"] = _select(q004_alert_full)

    def q034_dual_city() -> Any:
        weather_schema = {
            "location": {"prefectureName": _field("上海市")},
            "current": {
                "temperatureC": _field(29, "number"),
                "condition": _field("多云"),
            },
        }
        task = TaskSpec(
            userQuery="显示成都和上海的温度及天气现象",
            size="2x2",
            dataModelSchema={
                "data": {
                    "weather1": weather_schema,
                    "weather2": {
                        "location": {"prefectureName": _field("成都市")},
                        "current": {
                            "temperatureC": _field(25, "number"),
                            "condition": _field("小雨"),
                        },
                    },
                }
            },
        )
        bindings = (
            CandidateDataBinding(
                capabilityId="ViewWeather",
                writeResultTo="/data/weather1",
                candidateOutputFields=["/current/temperatureC", "/current/condition"],
            ),
            CandidateDataBinding(
                capabilityId="ViewWeather",
                writeResultTo="/data/weather2",
                candidateOutputFields=["/current/temperatureC", "/current/condition"],
            ),
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": ("/current/temperatureC", "/current/condition")
                },
            ),
            task,
            get_cardplan_registry(),
            bindings,
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {"capabilityId": item.capabilityId, "writeResultTo": item.writeResultTo}
                    for item in bindings
                ],
            },
        )

    cases["q034_dual_city"] = _select(q034_dual_city)

    def q043_care_alert() -> Any:
        task = TaskSpec(
            userQuery="查看长沙天气预警、紫外线和空气质量，并给妈妈打电话",
            size="2x2",
            eventCandidates=[
                EventAction(
                    id="event.call.phone",
                    call="clickToApi",
                    args={
                        "intentName": "CallPhone",
                        "params": {"relationship": "母亲", "phoneNumber": ""},
                    },
                )
            ],
            dataModelSchema={
                "data": {
                    "weather": {
                        "location": {"prefectureName": _field("长沙市")},
                        "current": {
                            "alertLevel": _field("寒潮蓝色预警"),
                            "uvIndex": _field("中等"),
                            "airQuality": _field("良"),
                        },
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=[
                "/location/prefectureName",
                "/current/alertLevel",
                "/current/uvIndex",
                "/current/airQuality",
            ],
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={
                    "ViewWeather": (
                        "/location/prefectureName",
                        "/current/alertLevel",
                        "/current/uvIndex",
                        "/current/airQuality",
                    )
                },
                action=("event.call.phone",),
            ),
            task,
            get_cardplan_registry(),
            (binding,),
            _card_spec(),
        )

    cases["q043_care_alert"] = _select(q043_care_alert)

    def q001_sleep_hero() -> Any:
        task = TaskSpec(
            userQuery="显示今日睡眠时长，点击可打开闹钟快速设置提醒",
            size="2x2",
            eventCandidates=[
                EventAction(
                    id="event.open.clock.alarm",
                    call="clickToDeeplink",
                    args={
                        "intentName": "Clock",
                        "bundleName": "com.huawei.hmos.clock",
                        "abilityName": "com.huawei.hmos.clock.phone",
                        "uri": "",
                    },
                )
            ],
            dataModelSchema={
                "data": {
                    "healthSport": {
                        "nightSleepDurationText": _field("7小时1分"),
                        "sleepStatus": _field("良好"),
                        "fallAsleepTimeText": _field("23:15"),
                        "wakeupTimeText": _field("07:30"),
                    }
                }
            },
        )
        binding = CandidateDataBinding(
            capabilityId="GetHealthAndSportSummary",
            writeResultTo="/data/healthSport",
            candidateOutputFields=[
                "/nightSleepDurationText",
                "/sleepStatus",
                "/fallAsleepTimeText",
                "/wakeupTimeText",
            ],
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="sleep-night-violet",
                requiredOutputFieldsByCapability={
                    "GetHealthAndSportSummary": ("/nightSleepDurationText",)
                },
                action=("event.open.clock.alarm",),
            ),
            task,
            get_cardplan_registry(),
            (binding,),
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {
                        "capabilityId": "GetHealthAndSportSummary",
                        "writeResultTo": "/data/healthSport",
                    }
                ],
            },
        )

    cases["q001_sleep_hero"] = _select(q001_sleep_hero)

    def bluetooth(action_ids: tuple[str, ...], fields: dict[str, Any]) -> Any:
        intents = {
            "event.open.music.daily": "Music",
            "event.open.clock.alarm": "Clock",
            "event.open.settings.dnd": "Settings",
        }
        task = TaskSpec(
            userQuery=(
                "展示耳机名称和耳机电量"
                if "earphoneName" in fields
                else "看看耳机盒是否在充电、电量有多少"
            ),
            size="2x2",
            eventCandidates=[
                EventAction(
                    id=event_id,
                    call="clickToDeeplink",
                    args={"intentName": intents[event_id]},
                )
                for event_id in action_ids
            ],
            dataModelSchema={"data": {"earphone": fields}},
        )
        field_paths = ["/" + name for name in fields]
        binding = CandidateDataBinding(
            capabilityId="GetEarphoneInfo",
            writeResultTo="/data/earphone",
            candidateOutputFields=field_paths,
        )
        return retrieve_template_variants(
            TemplateRetrievalQuery(
                themeId="family-weather-care-blue",
                requiredOutputFieldsByCapability={"GetEarphoneInfo": tuple(field_paths)},
                action_ids=action_ids,
            ),
            task,
            get_cardplan_registry(),
            (binding,),
            {
                "suggestSize": "2x2",
                "dataBindings": [
                    {"capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone"}
                ],
            },
        )

    _CASE_FIELDS = {
        "batteryLevel": _field(80, "integer"),
        "chargingStatusDesc": _field("充电中"),
    }
    _EARPHONE_FIELDS = {
        "earphoneName": _field("FreeBuds Pro 3"),
        "batteryLevel": _field(80, "integer"),
    }
    cases["bluetooth_case_two_actions"] = _select(
        lambda: bluetooth(
            ("event.open.music.daily", "event.open.clock.alarm"), _CASE_FIELDS,
        )
    )
    cases["earphone_hero"] = _select(
        lambda: bluetooth(("event.open.music.daily",), _EARPHONE_FIELDS)
    )
    cases["earphone_compact_two_actions"] = _select(
        lambda: bluetooth(
            ("event.open.music.daily", "event.open.settings.dnd"), _EARPHONE_FIELDS,
        )
    )

    def optional_title(weather_field: str, action_ids: tuple[str, ...]) -> Any:
        task = TaskSpec(
            userQuery="显示城市或天气现象",
            size="2x2",
            eventCandidates=[
                EventAction(
                    id=f"event.open.{index}",
                    description="查看详情",
                    call="clickToDeeplink",
                    args={"uri": "example://details"},
                )
                for index in range(len(action_ids))
            ],
            dataModelSchema={
                "data": {
                    "weather": {
                        "location": {"districtName": _field("青浦区")},
                        "current": {"condition": _field("多云")},
                    }
                }
            },
        )
        return retrieve_template_variants(
            _query(weather_field).model_copy(update={"action_ids": action_ids}),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )

    for field_slug, weather_field in (
        ("district", "/location/districtName"),
        ("condition", "/current/condition"),
    ):
        cases[f"optional_title__{field_slug}__actions0"] = _capture_error(
            lambda weather_field=weather_field: optional_title(weather_field, ())
        )
        cases[f"optional_title__{field_slug}__actions1"] = _select(
            lambda weather_field=weather_field: optional_title(
                weather_field, ("event.open.0",)
            )
        )
        cases[f"optional_title__{field_slug}__actions2"] = _capture_error(
            lambda weather_field=weather_field: optional_title(
                weather_field, ("event.open.0", "event.open.1")
            )
        )
    return cases


@scenario("retrieval__gallery_preferred_field_restriction")
def _build_gallery_preferred_field_restriction() -> dict[str, Any]:
    """受信画廊模板只保留其检索记录内的展示字段需求。"""
    query = TemplateRetrievalQuery(
        themeId="fusion-battery-teal",
        requiredOutputFieldsByCapability={
            "GetPhoneBatteryInfo": (
                "/batterySOC",
                "/batterySOCText",
                "/batteryCapacityLevelDesc",
            )
        },
    )
    restricted = restrict_query_to_preferred_templates(
        query,
        get_cardplan_registry(),
        ("BatteryOverviewCompact@1",),
    )
    return {
        "requiredOutputFieldsByCapability": {
            capability_id: list(paths)
            for capability_id, paths in restricted.required_output_fields_by_capability.items()
        }
    }


def _variant_record(template_id: str, tokens: frozenset[FieldToken]) -> TemplateVariantSearchRecord:
    return TemplateVariantSearchRecord(
        capability_id="ViewWeather",
        business_id="WeatherOverview",
        compatible_theme_ids=frozenset(),
        template_id=template_id,
        variant_name="default",
        supported_card_sizes=frozenset(),
        supported_roles=frozenset(),
        available_paths=frozenset(token.path for token in tokens),
        required_paths=frozenset(),
        field_tokens=frozenset(tokens),
        required_field_tokens=frozenset(),
        required_parameter_count=0,
    )


@scenario("retrieval__index_match_matrix")
def _build_index_match_matrix() -> dict[str, Any]:
    """检索索引矩阵：逐字段匹配先保留、路由层再做完整覆盖收敛；卡尺寸过滤。"""
    temperature = FieldToken("ViewWeather", "/current/temperatureText", "string")
    condition = FieldToken("ViewWeather", "/current/condition", "string")
    per_field_registry = SimpleNamespace(
        ux_business_components={
            "WeatherOverview": SimpleNamespace(
                name="WeatherOverview",
                local_template_ids=("WeatherTemperature@1", "WeatherCondition@1"),
            )
        },
        template_variant_search_records=(
            _variant_record("WeatherTemperature@1", frozenset({temperature})),
            _variant_record("WeatherCondition@1", frozenset({condition})),
        ),
        enabled_template_ids=lambda template_ids: template_ids,
    )
    query_tokens = frozenset({temperature, condition})
    candidates = _component_templates_for_capability(
        per_field_registry,  # type: ignore[arg-type]
        "ViewWeather",
        query_tokens,
        _task(),
        _card_spec(),
    )
    token = FieldToken("ViewWeather", "/current/condition", "string")
    size_filter_registry = SimpleNamespace(
        ux_business_components={
            "WeatherOverview": SimpleNamespace(
                name="WeatherOverview",
                local_template_ids=("WeatherCompact@1", "WeatherWide@1"),
            )
        },
        template_variant_search_records=(
            TemplateVariantSearchRecord(
                capability_id="ViewWeather",
                business_id="WeatherOverview",
                compatible_theme_ids=frozenset(),
                template_id="WeatherCompact@1",
                variant_name="default",
                supported_card_sizes=frozenset({"2x2"}),
                supported_roles=frozenset(),
                available_paths=frozenset({token.path}),
                required_paths=frozenset(),
                field_tokens=frozenset({token}),
                required_field_tokens=frozenset(),
                required_parameter_count=0,
            ),
            TemplateVariantSearchRecord(
                capability_id="ViewWeather",
                business_id="WeatherOverview",
                compatible_theme_ids=frozenset(),
                template_id="WeatherWide@1",
                variant_name="default",
                supported_card_sizes=frozenset({"2x4"}),
                supported_roles=frozenset(),
                available_paths=frozenset({token.path}),
                required_paths=frozenset(),
                field_tokens=frozenset({token}),
                required_field_tokens=frozenset(),
                required_parameter_count=0,
            ),
        ),
        enabled_template_ids=lambda template_ids: template_ids,
    )
    size_candidates = _component_templates_for_capability(
        size_filter_registry,  # type: ignore[arg-type]
        "ViewWeather",
        frozenset({token}),
        _task(),
        _card_spec(),
    )
    return {
        "per_field_matches": {
            "candidates": sorted(candidates["WeatherOverview"]),
            "requiredGroups": [
                list(group)
                for group in _required_field_template_groups(query_tokens, candidates)
            ],
        },
        "card_size_filter": {
            "candidates": sorted(size_candidates["WeatherOverview"]),
        },
    }


def _dual_business_fixtures(
    weather_state: str,
) -> tuple[TaskSpec, CandidateDataBinding, CandidateDataBinding]:
    """构造双业务（天气+日程）任务与绑定；weather_state 控制温度/现象字段。"""
    task = _task().model_copy(
        update={
            "userQuery": "显示天气和下一场日程，并提供查看入口",
            "eventCandidates": [
                EventAction(
                    id="event.open.details",
                    description="查看详情",
                    call="clickToDeeplink",
                    args={"uri": "example://details"},
                )
            ],
        }
    )
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    weather = data.get("weather")
    assert isinstance(weather, dict)
    current = weather.get("current")
    assert isinstance(current, dict)
    weather_fields = ["/location/districtName"]
    for field_name in ("temperatureText", "condition"):
        field_is_available = weather_state in {"both", "empty"}
        field_is_available = field_is_available or weather_state == field_name.removesuffix("Text")
        if field_is_available:
            weather_fields.append(f"/current/{field_name}")
            if weather_state == "empty":
                current[field_name] = _field("")
        else:
            current.pop(field_name)
    weather_binding = _binding().model_copy(update={"candidateOutputFields": weather_fields})
    data["calendar"] = {
        "events": [
            {
                "title": _field("项目例会"),
                "dtStart": _field("14:00"),
                "dtEnd": _field("15:00"),
                "eventLocation": _field("A1 会议室"),
            }
        ]
    }
    calendar_binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=[
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/eventLocation",
        ],
    )
    return task, weather_binding, calendar_binding


def _dual_business_stage(
    business_title: str | None,
    enable_fusion_ball: bool,
    requested_theme: str,
    weather_state: str,
) -> tuple[TaskSpec, dict[str, Any], Any, Any, Any]:
    """跑通双业务「检索 → 第二层投影 → 编译」链路，返回各阶段产物。"""
    task, weather_binding, calendar_binding = _dual_business_fixtures(weather_state)
    weather_fields = list(weather_binding.candidateOutputFields)
    query = TemplateRetrievalQuery(
        themeId=requested_theme,
        requiredOutputFieldsByCapability={
            "ViewWeather": tuple(weather_fields),
            "GetCalendarEvents": (
                "/events/0/title",
                "/events/0/dtStart",
                "/events/0/dtEnd",
                "/events/0/eventLocation",
            ),
        },
        action=("event.open.details",),
    )
    card_spec = {
        "title": business_title or "天气和日程",
        "description": "显示天气和下一场日程，并提供查看入口",
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
            },
        ],
    }
    registry = get_cardplan_registry(enable_fusion_ball)
    build_template_retrieval_prompt(task, registry, (weather_binding, calendar_binding))
    result = retrieve_template_variants(
        query,
        task,
        registry,
        (weather_binding, calendar_binding),
        card_spec,
    )
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card_spec,
        scope=result.scope,
        component_candidates=result.component_candidates,
        required_template_groups=result.required_template_groups,
        registry=registry,
    )
    action = projection.contract.action_bindings[0]
    source = (
        'Template("HeroTitleContentActionLayout@1",{},'
        'Template("WeatherOverviewHeroTitle@1",{}),'
        'Template("ScheduleOverviewHeroContent@1",{}),'
        'Template("PillAction@1",'
        + json.dumps(
            {"actionId": action.action_id, "label": action.display_label},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "));"
    )
    compilation = compile_ux_layout_card(
        source,
        task_spec=task,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(
            A2UI_FORM_PROTOCOL_PROFILE_ID
        ).get_profile(),
        registry=registry,
        card_spec=card_spec,
        business_title=business_title,
        enable_data_bindings=True,
    )
    return task, card_spec, result, projection, compilation


def _dual_business_combo_value(
    business_title: str | None,
    enable_fusion_ball: bool,
    requested_theme: str,
    weather_state: str,
) -> dict[str, Any]:
    """双业务单组合的摘要载荷：选中模板 + A2UI 文本摘要 + 主题着色。"""
    _, _, result, projection, compilation = _dual_business_stage(
        business_title, enable_fusion_ball, requested_theme, weather_state
    )
    action = projection.contract.action_bindings[0]
    messages = [json.loads(line) for line in compilation.a2ui.splitlines() if line.strip()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    by_id = {component.get("id"): component for component in components}
    root = by_id.get("root")
    assert isinstance(root, dict)
    digest_texts: list[str] = []
    themed_font_colors: dict[str, str] = {}
    for component in components:
        content_key = "label" if component.get("component") == "Button" else "content"
        content = component.get(content_key)
        if not isinstance(content, str):
            continue
        digest_texts.append(content)
        is_weather_title = any(path in content for path in _WEATHER_TITLE_PATHS)
        is_calendar_title = "/data/calendar/events/0/title" in content
        if content == action.display_label or is_calendar_title or is_weather_title:
            themed_font_colors[content] = component.get("styles", {}).get("fontColor")
    return {
        "templateIds": [
            template_id
            for candidate in result.component_candidates
            for template_id in candidate.available_template_ids
        ],
        "a2uiDigestTexts": digest_texts,
        "themedFontColors": themed_font_colors,
        "rootBackground": root.get("styles", {}).get("backgroundColor"),
        "fusionBallBackground": "fusionBallBackground" in by_id,
        "themeId": result.scope.theme_id,
        "themeProfileId": projection.contract.theme_profile_id,
        "trustedLiterals": sorted(projection.contract.trusted_literals),
    }


_TITLE_CASES: tuple[tuple[str, str | None], ...] = (
    ("title_default", None),
    ("title_weather_schedule", "天气和日程"),
    ("title_gallery", "天气 + 日历日程组合画廊"),
)
_THEME_CASES: tuple[tuple[str, bool, str], ...] = (
    ("fusion", True, "fusion-weather-blue"),
    ("plain", False, "family-weather-care-blue"),
)
_WEATHER_STATES: tuple[str, ...] = ("both", "condition", "temperature", "neither", "empty")
_REPRESENTATIVE_COMBO_KEY = "title_default__fusion__both"


@scenario("retrieval__dual_business_matrix")
def _build_dual_business_matrix() -> dict[str, Any]:
    """双业务参数矩阵：29 组合（wave-1 代表组合除外）的选模与渲染摘要。"""
    cases: dict[str, Any] = {}
    for title_slug, business_title in _TITLE_CASES:
        for theme_slug, enable_fusion_ball, requested_theme in _THEME_CASES:
            for weather_state in _WEATHER_STATES:
                key = f"{title_slug}__{theme_slug}__{weather_state}"
                if key == _REPRESENTATIVE_COMBO_KEY:
                    continue
                cases[key] = _dual_business_combo_value(
                    business_title, enable_fusion_ball, requested_theme, weather_state
                )
    assert len(cases) == 29
    return cases


@scenario("retrieval__weather_full_optional_data_metadata")
def _build_weather_full_optional_data_metadata() -> dict[str, Any]:
    """WeatherOverviewFull 的检索元数据：可选数据可用但不构成硬性要求。"""
    record = next(
        item
        for item in get_cardplan_registry().template_variant_search_records
        if item.template_id == "WeatherOverviewFull@1"
    )
    return {
        "availablePaths": sorted(record.available_paths),
        "requiredPaths": sorted(record.required_paths),
        "airQualityInFieldTokens": any(
            token.path == "/current/airQuality" for token in record.field_tokens
        ),
    }


def test_retrieval_policy_matrices_match_golden_scenarios() -> None:
    assert_golden_scenario("retrieval__hero_content_theme_matrix")
    assert_golden_scenario("retrieval__rejection_matrix")
    assert_golden_scenario("retrieval__selection_matrix")
    assert_golden_scenario("retrieval__index_match_matrix")
    assert_golden_scenario("retrieval__gallery_preferred_field_restriction")
    assert_golden_scenario("retrieval__weather_full_optional_data_metadata")
    assert_golden_scenario("retrieval__dual_business_matrix")


# --------------------------------------------------------------------------
# 保持为普通测试的 monkeypatch 过程断言
# --------------------------------------------------------------------------


def test_candidate_diagnostics_distinguish_user_and_template_field_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_field = FieldToken("ViewWeather", "/current/condition", "string")
    template_field = FieldToken("ViewWeather", "/templateRequired", "string")

    missing_template_input = TemplateVariantSearchRecord(
        capability_id="ViewWeather",
        business_id="WeatherOverview",
        compatible_theme_ids=frozenset(),
        template_id="WeatherMissingInputFull@1",
        variant_name="2x2",
        supported_card_sizes=frozenset({"2x2"}),
        supported_roles=frozenset(),
        available_paths=frozenset({user_field.path, template_field.path}),
        required_paths=frozenset({template_field.path}),
        field_tokens=frozenset({user_field, template_field}),
        required_field_tokens=frozenset({template_field}),
        required_parameter_count=0,
    )
    missing_user_requirement = TemplateVariantSearchRecord(
        capability_id="ViewWeather",
        business_id="WeatherOverview",
        compatible_theme_ids=frozenset(),
        template_id="WeatherOtherFieldFull@1",
        variant_name="2x2",
        supported_card_sizes=frozenset({"2x2"}),
        supported_roles=frozenset(),
        available_paths=frozenset({"/current/airQuality"}),
        required_paths=frozenset(),
        field_tokens=frozenset(
            {FieldToken("ViewWeather", "/current/airQuality", "string")}
        ),
        required_field_tokens=frozenset(),
        required_parameter_count=0,
    )
    template_ids = (
        missing_template_input.template_id,
        missing_user_requirement.template_id,
    )
    registry = SimpleNamespace(
        ux_business_components={
            "WeatherOverview": SimpleNamespace(local_template_ids=template_ids)
        },
        template_variant_search_records=(
            missing_template_input,
            missing_user_requirement,
        ),
        enabled_template_ids=lambda values: values,
    )
    info_logs: list[str] = []
    monkeypatch.setattr(
        retrieval_module,
        "logger",
        SimpleNamespace(info=info_logs.append),
    )

    candidates = _component_templates_for_capability(
        registry,  # type: ignore[arg-type]
        "ViewWeather",
        frozenset({user_field}),
        _task(),
        _card_spec(),
        candidate_output_fields=set(_WEATHER_FIELDS),
    )

    assert candidates == {}
    message = next(item for item in info_logs if "candidate_evaluation" in item)
    diagnostics = json.loads(message.partition("diagnostics=")[2])
    templates = {item["templateId"]: item for item in diagnostics["templates"]}
    missing_input = templates[missing_template_input.template_id]
    missing_requirement = templates[missing_user_requirement.template_id]

    assert diagnostics["userRequiredFields"] == [
        {"path": "/current/condition", "type": "string"}
    ]
    assert diagnostics["candidateOutputFields"] == sorted(_WEATHER_FIELDS)
    assert "templateRequiredFields" not in missing_input
    assert "templateAvailableFields" not in missing_input
    assert missing_input["userRequiredDataFullyCovered"] is True
    assert missing_input["userProvidedDataSatisfiesTemplateRequirements"] is False
    assert missing_input["missingTemplateRequiredFields"] == ["/templateRequired"]
    assert (
        "user_provided_data_missing_template_required_fields"
        in missing_input["rejectionReasons"]
    )
    assert missing_requirement["userRequiredDataFullyCovered"] is False
    assert missing_requirement["userProvidedDataSatisfiesTemplateRequirements"] is True
    assert "user_required_data_not_covered" in missing_requirement["rejectionReasons"]


def test_candidate_limit_keeps_24_templates_and_logs_the_25th(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template_ids = tuple(f"WeatherOverviewFull{index}@1" for index in range(1, 26))
    matches = {template_id: frozenset() for template_id in template_ids}

    limited_matches = _limit_component_templates(
        matches,
        template_ids,
        frozenset(),
    )

    assert len(limited_matches) == 24
    assert template_ids[23] in limited_matches
    assert template_ids[24] not in limited_matches

    evaluations = [
        {"templateId": template_id, "rejectionReasons": []}
        for template_id in template_ids
    ]
    info_logs: list[str] = []
    monkeypatch.setattr(
        retrieval_module,
        "logger",
        SimpleNamespace(info=info_logs.append),
    )
    retrieval_module._log_template_candidate_evaluation(
        capability_id="ViewWeather",
        business_id="WeatherOverview",
        data_root="/data/weather",
        card_size="2x2",
        user_required_fields=[],
        candidate_output_fields=set(),
        task_spec_available_fields=[],
        disabled_provider_ids=set(),
        disabled_template_ids=set(),
        evaluations=evaluations,
        matches=matches,
        limited_matches=limited_matches,
    )

    message = next(item for item in info_logs if "candidate_evaluation" in item)
    diagnostics = json.loads(message.partition("diagnostics=")[2])
    dropped = diagnostics.get("droppedByCandidateLimit")
    templates = diagnostics.get("templates")
    assert isinstance(templates, list)
    dropped_template = next(
        item for item in templates if item.get("templateId") == template_ids[24]
    )
    reasons = dropped_template.get("rejectionReasons")
    assert isinstance(reasons, list)

    assert dropped == [template_ids[24]]
    assert "candidate_limit_exceeded" in reasons


def test_layout_suffix_mismatch_logs_required_layout_and_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info_logs: list[str] = []
    monkeypatch.setattr(
        retrieval_module,
        "logger",
        SimpleNamespace(info=info_logs.append),
    )
    candidate = retrieval_module.TemplateComponentCandidate(
        componentId="BluetoothDeviceOverview",
        availableTemplateIds=("BluetoothDeviceOverviewCompact@1",),
    )

    with pytest.raises(TemplateRetrievalMiss, match="has no Hero/Full template"):
        retrieval_module._apply_2x2_combination_policy(
            (candidate,),
            1,
            [("BluetoothDeviceOverviewCompact@1",)],
        )

    policy_message = next(item for item in info_logs if "layout_policy_selected" in item)
    policy = json.loads(policy_message.partition("diagnostics=")[2])
    mismatch_message = next(item for item in info_logs if "layout_suffix_mismatch" in item)
    mismatch = json.loads(mismatch_message.partition("diagnostics=")[2])

    assert policy["actionCount"] == 1
    assert policy["requiredLayoutSuffixes"] == ["Hero", "Full"]
    assert mismatch == {
        "businessId": "BluetoothDeviceOverview",
        "requiredLayoutSuffixes": ["Hero", "Full"],
        "requiredLayoutLabel": "Hero/Full",
        "availableTemplateIds": ["BluetoothDeviceOverviewCompact@1"],
    }


def test_action_param_fields_do_not_block_template_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一层把事件参数字段（entityId）误列为展示需求时，Search 不得失败。"""
    task = TaskSpec(
        userQuery="显示最近日程的标题、开始时间，点一下进日程详情",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.viewCalendarEvent",
                call="clickToIntent",
                args={
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": "{{ ${/data/calendar/events/0/entityId} }}"},
                },
            )
        ],
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": _field("项目例会"),
                            "dtStart": _field("14:00"),
                            "dtEnd": _field("15:00"),
                            "eventLocation": _field("会议室"),
                            "entityId": _field("example-event-001"),
                        }
                    ]
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=[
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/eventLocation",
            "/events/0/entityId",
        ],
    )
    query = TemplateRetrievalQuery(
        themeId="meeting-paper-neutral",
        requiredOutputFieldsByCapability={
            "GetCalendarEvents": (
                "/events/0/title",
                "/events/0/dtStart",
                "/events/0/eventLocation",
                "/events/0/entityId",
            )
        },
        action=("event.viewCalendarEvent",),
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar"}
        ],
    }
    info_logs: list[str] = []
    monkeypatch.setattr(
        retrieval_module,
        "logger",
        SimpleNamespace(info=info_logs.append),
    )

    result = retrieve_template_variants(query, task, CardPlanRegistry(), (binding,), card_spec)

    assert "ScheduleOverviewNextEventLocationFull@1" in result.allowed_template_ids
    message = next(item for item in info_logs if "action_param_fields_dropped" in item)
    diagnostics = json.loads(message.partition("diagnostics=")[2])
    assert diagnostics["droppedFields"] == ["/events/0/entityId"]
    assert diagnostics["capabilityId"] == "GetCalendarEvents"


# --------------------------------------------------------------------------
# 保持为普通测试的 prompt 内容契约
# --------------------------------------------------------------------------


def test_first_layer_prompt_includes_task_fields_rules_and_action_candidates() -> None:
    task = _task().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={},
                )
            ]
        }
    )
    messages = build_template_retrieval_prompt(task, get_cardplan_registry(), (_binding(),))
    payload = json.loads(messages[1]["content"])

    assert payload["taskSpecDataFields"]
    assert payload["taskSpec"] == task.model_dump(mode="json")
    assert payload["providerFirstLayerRules"]
    assert "themeFirstLayerRules" not in payload
    assert "themes" not in payload
    assert payload["actionCandidates"] == [
        {"eventId": "event.open.weather", "call": "clickToDeeplink"}
    ]
    assert "不得为了迁就布局限制而省略" in messages[0]["content"]
    assert "这些组合约束由服务端 Planner" in messages[0]["content"]
    assert "不得判断业务是否能组成布局" in messages[0]["content"]


def test_calendar_first_layer_rule_excludes_meeting_action_parameters() -> None:
    task = TaskSpec(
        userQuery="显示下一场会议的标题和时间，并支持一键加入会议",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.enter.meeting",
                call="clickToDeeplink",
                args={
                    "intentName": "EnterMeeting",
                    "uri": "{{ ${/data/calendar/events/0/oneClickServiceLink} }}",
                },
            )
        ],
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": _field("项目例会"),
                            "dtStart": _field("14:00"),
                            "dtEnd": _field("15:00"),
                            "oneClickServiceLink": _field("meeting://join"),
                            "oneClickServiceType": _field("video"),
                            "isServiceValid": _field(1, "integer"),
                            "entityId": _field("calendar-event-001"),
                        }
                    ]
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=[
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/oneClickServiceLink",
            "/events/0/oneClickServiceType",
            "/events/0/isServiceValid",
            "/events/0/entityId",
        ],
    )

    messages = build_template_retrieval_prompt(task, get_cardplan_registry(), (binding,))
    payload = json.loads(messages[1]["content"])
    calendar_rule = next(
        rule["content"]
        for rule in payload["providerFirstLayerRules"]
        if rule["providerId"] == "com.huawei.calendar.cli"
    )

    for action_field in (
        "oneClickServiceLink",
        "oneClickServiceType",
        "isServiceValid",
        "entityId",
    ):
        assert action_field in calendar_rule
    assert "不得因为 Action" in calendar_rule
    assert "requiredOutputFieldsByCapability" in calendar_rule
    assert "event.enter.meeting" in calendar_rule


def test_weather_first_layer_rule_treats_temperature_as_optional() -> None:
    """双业务 prompt 的天气规则：温度字段可选，不得用「必须完整可用」表述。"""
    task, weather_binding, calendar_binding = _dual_business_fixtures("both")
    messages = build_template_retrieval_prompt(
        task, get_cardplan_registry(), (weather_binding, calendar_binding)
    )
    first_layer_text = json.dumps(messages, ensure_ascii=False)
    assert "不要求温度字段必须存在" in first_layer_text
    assert "温度字段可用且能完整使用" not in first_layer_text


def test_dual_business_projection_prompt_marks_theme_owner_and_slot_order() -> None:
    """第二层 prompt 必须声明主题归属、温度豁免与 HeroTitle/HeroContent 槽序。"""
    _, _, _, projection, _ = _dual_business_stage(None, True, "fusion-weather-blue", "both")
    content = projection.messages[1]["content"]
    assert "全局主题已按主业务 HeroContent 确定" in content
    assert "不得因缺少温度拒绝该模板" in content
    assert (
        '"childOrder": "position 0 HeroTitle, position 1 HeroContent, position 2 PillAction"'
        in content
    )


# --------------------------------------------------------------------------
# 已知红线（在 HEAD 即失败，保持原样，修复后再纳入场景金样）
# --------------------------------------------------------------------------


def test_q025_weather_wind_fields_match_wind_hero() -> None:
    task = TaskSpec(
        userQuery="查看厦门当地风向、风力和天气更新时间，点一下查看详情",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.weather",
                call="clickToDeeplink",
                args={"intentName": "Weather_CityCode"},
            )
        ],
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {
                        "prefectureName": _field("厦门市"),
                        "cityCode": _field("59102"),
                    },
                    "current": {
                        "windDirection": _field("东南风"),
                        "windLevel": _field(3, "integer"),
                    },
                    "updatedAt": _field("2026-09-03 10:00"),
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/location/prefectureName",
            "/current/windDirection",
            "/current/windLevel",
            "/updatedAt",
            "/location/cityCode",
        ],
    )
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/location/prefectureName",
                "/current/windDirection",
                "/current/windLevel",
                "/updatedAt",
            )
        },
        action=("event.open.weather",),
    )

    result = retrieve_template_variants(
        query,
        task,
        get_cardplan_registry(),
        (binding,),
        _card_spec(),
    )

    assert result.component_candidates[0].available_template_ids == (
        "WeatherOverviewWindHero@1",
    )


def test_search_without_action_keeps_only_full_candidates() -> None:
    """没有事件时 Search 只保留 Full，避免第二层生成多余动作区域。"""
    result = retrieve_template_variants(
        _query("/current/condition"),
        _task(),
        get_cardplan_registry(),
        (_binding(),),
        _card_spec(),
    )

    template_ids = set(result.component_candidates[0].available_template_ids)
    assert template_ids == {"WeatherOverviewFull@1"}


# --------------------------------------------------------------------------
# 既有场景金样（wave-1 代表组合）
# --------------------------------------------------------------------------


@scenario("retrieval__dual_business_hero_title_content")
def _build_dual_business_hero_title_content() -> dict[str, Any]:
    """固化代表性组合：fusion 球主题 + 完整天气字段 + 默认卡片标题。"""
    _, _, result, _, compilation = _dual_business_stage(
        None, True, "fusion-weather-blue", "both"
    )
    return {
        "a2ui": [
            json.loads(line)
            for line in compilation.a2ui.splitlines()
            if line.strip()
        ],
        "templateIds": [
            template_id
            for candidate in result.component_candidates
            for template_id in candidate.available_template_ids
        ],
    }


def test_dual_business_hero_title_content_matches_golden_scenario() -> None:
    assert_golden_scenario("retrieval__dual_business_hero_title_content")
