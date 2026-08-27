from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.content_selectors import (
    apply_content_selectors,
)
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
    _required_field_template_groups,
    build_template_retrieval_prompt,
    retrieve_template_variants,
)

_WEATHER_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/current/coldLevel",
    "/daily/0/temperatureRangeText",
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


def test_match_rejects_query_fields_not_contained_by_any_template() -> None:
    query = _query("/current/windDirection")
    task = _task()
    task.dataModelSchema["data"]["weather"]["current"]["windDirection"] = _field("东南风")
    binding = _binding().model_copy(
        update={"candidateOutputFields": [*_WEATHER_FIELDS, "/current/windDirection"]}
    )

    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        retrieve_template_variants(query, task, get_cardplan_registry(), (binding,), _card_spec())


def test_match_requires_all_provider_required_data_in_task_schema() -> None:
    task = _task()
    del task.dataModelSchema["data"]["weather"]["location"]["districtName"]

    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )


def test_provider_required_data_types_are_checked_when_known() -> None:
    task = _task()
    task.dataModelSchema["data"]["weather"]["location"]["districtName"] = _field(1, "integer")

    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )


def test_cross_theme_query_keeps_field_compatible_candidates() -> None:
    query = _query("/current/condition").model_copy(update={"theme_id": "meeting-paper-neutral"})

    result = retrieve_template_variants(
        query, _task(), get_cardplan_registry(), (_binding(),), _card_spec()
    )

    assert result.component_candidates
    assert set(result.allowed_template_ids) >= {
        "WeatherOverviewCompact@1",
        "WeatherOverviewFull@1",
    }


@pytest.mark.parametrize(
    ("path", "value", "data_type", "expected_template"),
    [
        (
            "/current/humidityPercent",
            70.0,
            "number",
            "WeatherOverviewHumidityFull@1",
        ),
        ("/current/uvIndex", "中等", "string", "WeatherOverviewUvFull@1"),
    ],
)
def test_specialized_weather_focus_routes_to_ux_template(
    path: str,
    value: Any,
    data_type: str,
    expected_template: str,
) -> None:
    task = _task()
    field_name = path.rsplit("/", 1)[-1]
    task.dataModelSchema["data"]["weather"]["current"][field_name] = _field(
        value,
        data_type,
    )
    binding = _binding().model_copy(
        update={"candidateOutputFields": [*_WEATHER_FIELDS, path]}
    )

    result = retrieve_template_variants(
        _query(path),
        task,
        get_cardplan_registry(),
        (binding,),
        _card_spec(),
    )

    assert expected_template in result.allowed_template_ids


def test_shared_capability_keeps_each_component_scoped_templates() -> None:
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
                        }
                    ]
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=["/events/0/title", "/events/0/dtStart", "/events/0/dtEnd"],
    )
    query = TemplateRetrievalQuery(
        themeId="meeting-paper-neutral",
        requiredOutputFieldsByCapability={
            "GetCalendarEvents": ("/events/0/title", "/events/0/dtStart")
        },
    )

    selected_task = apply_content_selectors(task, {"GetCalendarEvents"})
    result = retrieve_template_variants(
        query,
        selected_task,
        CardPlanRegistry(),
        (binding,),
        {
            "suggestSize": "2x2",
            "dataBindings": [
                {"capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar"}
            ],
        },
    )

    assert "ScheduleOverviewNextEventFull@1" in result.allowed_template_ids


def test_calendar_date_and_schedule_share_one_business_component() -> None:
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
    fields = (
        "/events/0/startDate",
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/updatedAt",
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )
    query = TemplateRetrievalQuery(
        themeId="meeting-paper-neutral",
        requiredOutputFieldsByCapability={
            "GetCalendarEvents": (
                "/events/0/startDate",
                "/events/0/title",
                "/events/0/dtStart",
            )
        },
    )

    result = retrieve_template_variants(
        query,
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

    assert result.scope.advanced_component_ids == ("CalendarOverview",)
    assert len(result.component_candidates) == 1
    assert set(result.allowed_template_ids) >= {
        "DateOverviewCompact@1",
        "ScheduleOverviewMeetingCompact@1",
    }
    assert any("DateOverviewCompact@1" in group for group in result.required_template_groups)
    assert any(
        "ScheduleOverviewMeetingCompact@1" in group
        for group in result.required_template_groups
    )


def test_domain_only_query_returns_candidates_when_required_data_is_available() -> None:
    result = retrieve_template_variants(
        _query(),
        _task(),
        CardPlanRegistry(),
        (_binding(),),
        _card_spec(),
    )

    assert result.component_candidates
    assert result.required_template_groups


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
    assert payload["themeFirstLayerRules"]
    assert payload["actionCandidates"] == [
        {"eventId": "event.open.weather", "call": "clickToDeeplink"}
    ]


def test_search_allows_two_data_businesses() -> None:
    task = _task()
    task.dataModelSchema["data"]["calendar"] = {
        "events": [
            {
                "title": _field("项目例会"),
                "dtStart": _field("14:00"),
                "dtEnd": _field("15:00"),
            }
        ]
    }
    calendar = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=["/events/0/title", "/events/0/dtStart"],
    )
    result = retrieve_template_variants(
        TemplateRetrievalQuery(
            themeId="family-weather-care-blue",
            requiredOutputFieldsByCapability={
                "ViewWeather": ("/current/condition",),
                "GetCalendarEvents": ("/events/0/title", "/events/0/dtStart"),
            },
        ),
        task,
        CardPlanRegistry(),
        (_binding(), calendar),
        {
            "dataBindings": [
                {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
                {"capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar"},
            ]
        },
    )

    assert {item.component_id for item in result.component_candidates} == {
        "CalendarOverview",
        "WeatherOverview",
    }


def test_search_still_rejects_more_than_two_data_businesses() -> None:
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "CapabilityA": ("/value",),
            "CapabilityB": ("/value",),
            "CapabilityC": ("/value",),
        },
    )

    with pytest.raises(TemplateRetrievalMiss, match="at most two data businesses"):
        retrieve_template_variants(query, _task(), CardPlanRegistry(), (), {})


def test_search_allows_one_data_business_with_action() -> None:
    task = _task().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={"intentName": "Weather_CityCode"},
                )
            ]
        }
    )
    query = _query("/current/condition").model_copy(
        update={"action_ids": ("event.open.weather",)}
    )

    result = retrieve_template_variants(
        query,
        task,
        CardPlanRegistry(),
        (_binding(),),
        _card_spec(),
    )

    assert len(result.component_candidates) == 1
    assert result.action_id == "event.open.weather"


def test_one_component_may_use_multiple_templates_to_cover_requested_fields() -> None:
    """Search 不把同一组件的字段错误地限制在单个 CardTpl 中。"""
    temperature = FieldToken("ViewWeather", "/current/temperatureText", "string")
    condition = FieldToken("ViewWeather", "/current/condition", "string")

    def record(template_id: str, token: FieldToken) -> TemplateVariantSearchRecord:
        return TemplateVariantSearchRecord(
            capability_id="ViewWeather",
            business_id="WeatherOverview",
            compatible_theme_ids=frozenset(),
            template_id=template_id,
            variant_name="default",
            supported_card_sizes=frozenset(),
            supported_roles=frozenset(),
            available_paths=frozenset({token.path}),
            required_paths=frozenset(),
            field_tokens=frozenset({token}),
            required_field_tokens=frozenset(),
            required_parameter_count=0,
        )

    registry = SimpleNamespace(
        ux_business_components={
            "WeatherOverview": SimpleNamespace(
                name="WeatherOverview",
                local_template_ids=("WeatherTemperature@1", "WeatherCondition@1"),
            )
        },
        template_variant_search_records=(
            record("WeatherTemperature@1", temperature),
            record("WeatherCondition@1", condition),
        ),
        enabled_template_ids=lambda template_ids: template_ids,
    )
    query_tokens = frozenset({temperature, condition})

    candidates = _component_templates_for_capability(
        registry,  # type: ignore[arg-type]
        "ViewWeather",
        query_tokens,
        _task(),
        _card_spec(),
    )

    assert set(candidates["WeatherOverview"]) == {
        "WeatherTemperature@1",
        "WeatherCondition@1",
    }
    assert _required_field_template_groups(query_tokens, candidates) == (
        ("WeatherCondition@1",),
        ("WeatherTemperature@1",),
    )


def test_search_filters_provider_templates_by_card_size() -> None:
    token = FieldToken("ViewWeather", "/current/condition", "string")

    def record(template_id: str, sizes: frozenset[str]) -> TemplateVariantSearchRecord:
        return TemplateVariantSearchRecord(
            capability_id="ViewWeather",
            business_id="WeatherOverview",
            compatible_theme_ids=frozenset(),
            template_id=template_id,
            variant_name="default",
            supported_card_sizes=sizes,
            supported_roles=frozenset(),
            available_paths=frozenset({token.path}),
            required_paths=frozenset(),
            field_tokens=frozenset({token}),
            required_field_tokens=frozenset(),
            required_parameter_count=0,
        )

    registry = SimpleNamespace(
        ux_business_components={
            "WeatherOverview": SimpleNamespace(
                name="WeatherOverview",
                local_template_ids=("WeatherCompact@1", "WeatherWide@1"),
            )
        },
        template_variant_search_records=(
            record("WeatherCompact@1", frozenset({"2x2"})),
            record("WeatherWide@1", frozenset({"2x4"})),
        ),
        enabled_template_ids=lambda template_ids: template_ids,
    )

    candidates = _component_templates_for_capability(
        registry,  # type: ignore[arg-type]
        "ViewWeather",
        frozenset({token}),
        _task(),
        _card_spec(),
    )

    assert tuple(candidates["WeatherOverview"]) == ("WeatherCompact@1",)


def test_selected_action_must_belong_to_task_spec() -> None:
    query = _query("/current/condition").model_copy(
        update={"action_ids": ("event.unknown",)}
    )

    with pytest.raises(TemplateRetrievalMiss, match="selected Action"):
        retrieve_template_variants(
            query, _task(), get_cardplan_registry(), (_binding(),), _card_spec()
        )


def test_disabled_provider_templates_never_enter_search_candidates() -> None:
    registry = CardPlanRegistry(
        disabled_provider_ids=("com.huawei.weather.cli",),
    )

    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        retrieve_template_variants(
            _query("/current/condition"),
            _task(),
            registry,
            (_binding(),),
            _card_spec(),
        )


def test_optional_data_is_available_but_not_required_for_second_containment() -> None:
    record = next(
        item
        for item in get_cardplan_registry().template_variant_search_records
        if item.template_id == "AppUsageOverviewFull@1"
    )

    assert "/updatedAt" in record.available_paths
    assert "/updatedAt" not in record.required_paths
    assert any(token.path == "/updatedAt" for token in record.field_tokens)
