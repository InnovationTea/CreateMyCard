from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

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

_WEATHER_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/current/coldLevel",
    "/daily/0/temperatureRangeText",
)


@pytest.mark.parametrize(
    ("enabled", "requested_theme", "expected_theme"),
    [
        (False, "family-weather-care-blue", "meeting-paper-neutral"),
        (False, "meeting-paper-neutral", "meeting-paper-neutral"),
        (True, "fusion-weather-blue", "fusion-schedule-cool"),
        (True, "fusion-schedule-cool", "fusion-schedule-cool"),
        (True, "meeting-paper-neutral", "fusion-schedule-cool"),
    ],
)
def test_hero_content_theme_follows_main_business_and_version_gate(
    enabled: bool, requested_theme: str, expected_theme: str,
) -> None:
    registry = get_cardplan_registry(enabled)
    template_ids = (
        "WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1", "PillAction@1",
    )
    assert registry.hero_content_theme_id(template_ids, requested_theme) == expected_theme


def test_hero_content_without_fusion_never_borrows_title_business_fusion() -> None:
    registry = CardPlanRegistry(enable_fusion_ball=True)
    registry.themes.pop("fusion-schedule-cool")
    template_ids = ("WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1")
    assert registry.hero_content_theme_id(template_ids, "fusion-weather-blue") == (
        "meeting-paper-neutral"
    )


@pytest.mark.parametrize(
    "template_ids",
    [
        (),
        ("WeatherOverviewHeroTitle@1",),
        ("ScheduleOverviewHeroContent@1",),
        ("WeatherOverviewHero@1", "ScheduleOverviewHeroContent@1"),
        ("WeatherOverviewHeroTitle@1", "ScheduleOverviewDateFull@1"),
        (
            "WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1",
            "SleepOverviewFull@1",
        ),
    ],
)
def test_other_layouts_do_not_acquire_hero_content_theme_ownership(
    template_ids: tuple[str, ...],
) -> None:
    registry = get_cardplan_registry(True)
    assert registry.hero_content_theme_owner(template_ids) is None
    assert registry.hero_content_theme_id(template_ids, "fusion-weather-blue") is None


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

    with pytest.raises(
        TemplateRetrievalMiss,
        match="absent or untyped|no provider template|no Full template",
    ):
        retrieve_template_variants(query, task, get_cardplan_registry(), (binding,), _card_spec())


def test_trusted_gallery_template_drops_runtime_only_retrieval_fields() -> None:
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

    assert restricted.required_output_fields_by_capability == {
        "GetPhoneBatteryInfo": (
            "/batterySOC",
        )
    }


def test_match_requires_all_provider_required_data_in_task_schema() -> None:
    task = _task()
    del task.dataModelSchema["data"]["weather"]["current"]["condition"]

    with pytest.raises(
        TemplateRetrievalMiss,
        match="absent or untyped|no provider template|no Full template",
    ):
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )


def test_provider_required_data_types_are_checked_when_known() -> None:
    task = _task()
    task.dataModelSchema["data"]["weather"]["current"]["condition"] = _field(1, "integer")

    with pytest.raises(TemplateRetrievalMiss, match="no provider template|no Full template"):
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            get_cardplan_registry(),
            (_binding(),),
            _card_spec(),
        )


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


def test_cross_theme_query_keeps_field_compatible_candidates() -> None:
    query = _query("/current/condition").model_copy(update={"theme_id": "meeting-paper-neutral"})

    result = retrieve_template_variants(
        query, _task(), get_cardplan_registry(), (_binding(),), _card_spec()
    )

    assert result.component_candidates
    assert "WeatherOverviewFull@1" in result.allowed_template_ids


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

    assert "ScheduleOverviewNextEventLocationFull@1" in result.allowed_template_ids


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


def test_calendar_date_and_schedule_require_one_covering_business_template() -> None:
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

    with pytest.raises(TemplateRetrievalMiss, match="no provider template|cannot cover"):
        retrieve_template_variants(
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
    assert "2x2-two-support" not in payload["themes"]
    assert "2x2-two-support" not in payload["themeFirstLayerRules"]
    assert payload["actionCandidates"] == [
        {"eventId": "event.open.weather", "call": "clickToDeeplink"}
    ]
    assert "不得为了迁就布局限制而省略" in messages[0]["content"]
    assert "2x2 模板 Search 接受一个可完整覆盖的业务" in messages[0]["content"]
    assert "恰好两个数据业务加一个显式 Action" in messages[0]["content"]


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


def test_search_rejects_2x4_before_prompt_or_retrieval() -> None:
    task = _task().model_copy(update={"size": "2x4"})
    card_spec = _card_spec() | {"suggestSize": "2x4"}
    inaccessible_registry = cast(CardPlanRegistry, object())

    with pytest.raises(TemplateRetrievalMiss, match="does not support 2x4"):
        build_template_retrieval_prompt(task, inaccessible_registry, (_binding(),))
    with pytest.raises(TemplateRetrievalMiss, match="does not support 2x4"):
        retrieve_template_variants(
            _query("/current/condition"),
            task,
            inaccessible_registry,
            (_binding(),),
            card_spec,
        )


def test_search_rejects_two_data_businesses() -> None:
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
    with pytest.raises(TemplateRetrievalMiss, match="multiple data businesses"):
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


@pytest.mark.parametrize("business_title", [None, "天气和日程", "天气 + 日历日程组合画廊"])
@pytest.mark.parametrize("weather_state", ["both", "condition", "temperature", "neither", "empty"])
@pytest.mark.parametrize(
    ("enable_fusion_ball", "requested_theme", "expected_theme"),
    [
        (False, "family-weather-care-blue", "meeting-paper-neutral"),
        (True, "fusion-weather-blue", "fusion-schedule-cool"),
    ],
)
def test_search_orders_complete_hero_title_and_hero_content_businesses(
    business_title: str | None,
    enable_fusion_ball: bool,
    requested_theme: str,
    expected_theme: str,
    weather_state: str,
) -> None:
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
    first_layer_messages = build_template_retrieval_prompt(
        task, registry, (weather_binding, calendar_binding)
    )
    first_layer_text = json.dumps(first_layer_messages, ensure_ascii=False)
    assert "不要求温度字段必须存在" in first_layer_text
    assert "温度字段可用且能完整使用" not in first_layer_text
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

    assert result.scope.advanced_component_ids == (
        "WeatherOverview",
        "CalendarOverview",
    )
    assert result.component_candidates[0].available_template_ids == (
        "WeatherOverviewHeroTitle@1",
    )
    assert result.component_candidates[1].available_template_ids == (
        "ScheduleOverviewHeroContent@1",
    )
    assert result.required_template_groups == (
        ("WeatherOverviewHeroTitle@1",),
        ("ScheduleOverviewHeroContent@1",),
    )
    assert projection.allowed_layout_ids == ("HeroTitleContentActionLayout",)
    assert result.scope.theme_id == expected_theme
    assert projection.theme_id == expected_theme
    assert projection.contract.theme_profile_id == expected_theme
    messages = [json.loads(line) for line in compilation.a2ui.splitlines() if line.strip()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    by_id = {component.get("id"): component for component in components}
    root = by_id.get("root")
    assert isinstance(root, dict)
    expected_color = "#FFCCEEFF" if enable_fusion_ball else "#FF1F4799"
    themed_text_count = 0
    for component in components:
        content = component.get("content")
        if not isinstance(content, str):
            continue
        primary_paths = (
            "/data/weather/location/districtName", "/data/weather/current/temperatureText",
            "/data/weather/current/condition", "/data/calendar/events/0/title",
        )
        is_primary_text = any(path in content for path in primary_paths)
        if content == action.display_label or is_primary_text:
            assert component.get("styles", {}).get("fontColor") == expected_color
            themed_text_count += 1
    assert themed_text_count == (3 if weather_state == "neither" else 4)
    assert "全局主题已按主业务 HeroContent 确定" in projection.messages[1]["content"]
    assert "不得因缺少温度拒绝该模板" in projection.messages[1]["content"]
    city_nodes = [
        component for component in components
        if "/data/weather/location/districtName" in str(component.get("content", ""))
    ]
    assert len(city_nodes) == 1
    city_id = city_nodes[0].get("id")
    headers = [component for component in components if city_id in component.get("children", [])]
    assert len(headers) == 1
    header = headers[0]
    assert header.get("component") == "Row"
    header_children = header.get("children")
    assert isinstance(header_children, list)
    assert header_children[0] == city_id
    assert len(header_children) == (1 if weather_state == "neither" else 2)
    if weather_state != "neither":
        details = by_id.get(header_children[1])
        assert isinstance(details, dict)
        assert details.get("component") == "Text"
        details_content = details.get("content")
        assert isinstance(details_content, str)
        if weather_state in {"both", "empty"}:
            assert details_content.index("/condition") < details_content.index("/temperatureText")
            assert " | " in details_content
        else:
            assert "|" not in details_content
    if enable_fusion_ball:
        assert root.get("children") == ["fusionBallBackground", "template_root"]
        background_count = sum(
            component.get("id") == "fusionBallBackground" for component in components
        )
        assert background_count == 1
        palette = {
            "fusionBallLarge": "#FF121E59",
            "fusionBallMedium": "#FF2BA2D9",
            "fusionBallSmall": "#FF52CCCC",
        }
        for component_id, color in palette.items():
            component = by_id.get(component_id)
            assert isinstance(component, dict)
            assert component.get("styles", {}).get("backgroundColor") == color
    else:
        assert root.get("styles", {}).get("backgroundColor") == "#FFE5EDFE"
        assert "fusionBallBackground" not in by_id
    child_order = (
        '"childOrder": "position 0 HeroTitle, position 1 HeroContent, position 2 PillAction"'
    )
    assert child_order in projection.messages[1]["content"]
    assert "HeroTitleContentActionLayout" not in compilation.a2ui
    assert "events/0/title" in compilation.a2ui
    for field_name in ("temperatureText", "condition"):
        assert (f"/data/weather/current/{field_name}" in compilation.a2ui) == (
            f"/current/{field_name}" in weather_fields
        )
    assert "_advancedComponent" not in compilation.a2ui
    if business_title is not None:
        assert business_title in projection.contract.trusted_literals
        assert business_title not in compilation.a2ui
        assert card_spec.get("title") == business_title
    assert compilation.stats.action_used_ids == (action.action_id,)


@pytest.mark.parametrize("action_count", (0, 1, 2))
@pytest.mark.parametrize("weather_field", ("/current/condition", "/location/districtName"))
def test_optional_weather_title_does_not_relax_single_business_templates(
    action_count: int, weather_field: str,
) -> None:
    events = [
        EventAction(
            id=f"event.open.{index}", description="查看详情", call="clickToDeeplink",
            args={"uri": "example://details"},
        )
        for index in range(action_count)
    ]
    task = TaskSpec(
        userQuery="显示城市或天气现象", size="2x2", eventCandidates=events,
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"districtName": _field("青浦区")},
                    "current": {"condition": _field("多云")},
                }
            }
        },
    )
    query = _query(weather_field).model_copy(
        update={"action_ids": tuple(event.id for event in events)}
    )
    with pytest.raises(TemplateRetrievalMiss):
        retrieve_template_variants(
            query, task, get_cardplan_registry(), (_binding(),), _card_spec()
        )


def test_search_rejects_two_businesses_backed_by_one_capability() -> None:
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
    query = TemplateRetrievalQuery(
        themeId="race-sunrise-action",
        requiredOutputFieldsByCapability={
            "GetHealthAndSportSummary": (
                "/nightSleepDurationText",
                "/dailySteps",
            )
        },
    )

    with pytest.raises(TemplateRetrievalMiss, match="multiple data businesses"):
        retrieve_template_variants(
            query,
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
    template_ids = result.component_candidates[0].available_template_ids
    assert any(template_id.endswith("Hero@1") for template_id in template_ids)
    assert any(template_id.endswith("Full@1") for template_id in template_ids)


def test_q001_sleep_assistant_matches_hero_without_sleep_score() -> None:
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
    query = TemplateRetrievalQuery(
        themeId="sleep-night-violet",
        requiredOutputFieldsByCapability={
            "GetHealthAndSportSummary": ("/nightSleepDurationText",)
        },
        action=("event.open.clock.alarm",),
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetHealthAndSportSummary",
                "writeResultTo": "/data/healthSport",
            }
        ],
    }

    result = retrieve_template_variants(
        query,
        task,
        get_cardplan_registry(),
        (binding,),
        card_spec,
    )

    assert len(result.component_candidates) == 1
    candidate = result.component_candidates[0]
    assert candidate.component_id == "SleepOverview"
    assert "SleepOverviewHero@1" in candidate.available_template_ids


def test_search_allows_one_data_business_with_two_actions() -> None:
    task = _task().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={"intentName": "Weather_CityCode"},
                ),
                EventAction(
                    id="event.start.navigate",
                    call="clickToDeeplink",
                    args={"intentName": "Navigation"},
                ),
            ]
        }
    )
    query = _query("/current/condition").model_copy(
        update={
            "action_ids": (
                "event.open.weather",
                "event.start.navigate",
            )
        }
    )

    result = retrieve_template_variants(
        query,
        task,
        CardPlanRegistry(),
        (_binding(),),
        _card_spec(),
    )

    assert len(result.component_candidates) == 1
    assert result.action_ids == (
        "event.open.weather",
        "event.start.navigate",
    )
    assert all(
        template_id.endswith("Compact@1")
        for template_id in result.component_candidates[0].available_template_ids
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


def test_search_index_reports_per_field_matches_before_route_intersection() -> None:
    """索引先保留逐字段匹配；路由层随后会拒绝不能独立完整覆盖的模板。"""
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


def test_search_rejects_weather_and_battery_businesses() -> None:
    task = TaskSpec(
        userQuery="显示天气和手机电量状态",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {
                        "districtName": _field("福田区"),
                    },
                    "current": {
                        "temperatureText": _field("29°C"),
                        "condition": _field("多云"),
                        "coldLevel": _field("低"),
                    },
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
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/current/condition",
                "/current/temperatureText",
                "/location/districtName",
                "/current/coldLevel",
            ),
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
        },
    )
    bindings = (
        CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=[
                "/current/condition",
                "/current/temperatureText",
                "/location/districtName",
                "/current/coldLevel",
            ],
        ),
        CandidateDataBinding(
            capabilityId="GetPhoneBatteryInfo",
            writeResultTo="/data/phoneBattery",
            candidateOutputFields=[
                "/batterySOC",
                "/batterySOCText",
                "/batteryCapacityLevelDesc",
                "/chargingStatusDesc",
            ],
        ),
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
            {"capabilityId": "GetPhoneBatteryInfo", "writeResultTo": "/data/phoneBattery"},
        ],
    }

    with pytest.raises(TemplateRetrievalMiss, match="multiple data businesses"):
        retrieve_template_variants(
            query,
            task,
            get_cardplan_registry(),
            bindings,
            card_spec,
        )


def test_search_rejects_weather_uv_and_battery_businesses() -> None:
    task = TaskSpec(
        userQuery="显示天气紫外线和手机电量状态",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {
                        "districtName": _field("福田区"),
                    },
                    "current": {
                        "temperatureText": _field("29°C"),
                        "condition": _field("多云"),
                        "uvIndex": _field("弱"),
                    },
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
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/current/condition",
                "/current/temperatureText",
                "/location/districtName",
                "/current/uvIndex",
            ),
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
        },
    )
    bindings = (
        CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=[
                "/current/condition",
                "/current/temperatureText",
                "/location/districtName",
                "/current/uvIndex",
            ],
        ),
        CandidateDataBinding(
            capabilityId="GetPhoneBatteryInfo",
            writeResultTo="/data/phoneBattery",
            candidateOutputFields=[
                "/batterySOC",
                "/batterySOCText",
                "/batteryCapacityLevelDesc",
                "/chargingStatusDesc",
            ],
        ),
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
            {"capabilityId": "GetPhoneBatteryInfo", "writeResultTo": "/data/phoneBattery"},
        ],
    }

    with pytest.raises(TemplateRetrievalMiss, match="multiple data businesses"):
        retrieve_template_variants(
            query,
            task,
            get_cardplan_registry(),
            bindings,
            card_spec,
        )


def test_search_rejects_countdown_and_weather_businesses() -> None:
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
                    }
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
    with pytest.raises(TemplateRetrievalMiss, match="multiple data businesses"):
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
