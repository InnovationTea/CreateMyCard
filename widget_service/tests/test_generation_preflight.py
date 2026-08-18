# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from pathlib import Path

import pytest

from api.schemas import GenerateWidgetCardRequest
from core.errors import ErrorCode
from custom.a2ui_model_client import A2UIModelClient
from models.preflight import GenerationPreflightError
from services.capability_registry import CapabilityRegistry
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_preflight import GenerationPreflight
from services.widget_generation_service import WidgetGenerationService

REGISTRY_VERSION = "app-11.7.5.205_rom-6.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _request(**updates) -> GenerateWidgetCardRequest:
    values = {
        "uid": "test-user",
        "prdVer": "11.7.5.205",
        "device": {"romVersion": "6.0"},
        "userQuery": "生成测试卡片",
        "size": "2x2",
        "title": "测试卡片",
        "description": "生成前置校验",
        "candidateDataBindings": [],
        "candidateEventCandidates": [],
        "candidateAssetIds": [],
    }
    values.update(updates)
    return GenerateWidgetCardRequest(**values)


def _run(request: GenerateWidgetCardRequest):
    normalized = EditRequestNormalizer.normalize_create(request)
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    return GenerationPreflight(registry).run(normalized)


def test_generation_tool_schema_matches_source_direct_result_contract():
    tool_path = (
        PROJECT_ROOT
        / "skills"
        / "harmony-card-generation-online"
        / "references"
        / "tools"
        / "com.omega_w_0823.hmservice__generateWidgetCardCompactDsl.json"
    )
    tool = json.loads(tool_path.read_text(encoding="utf-8"))
    properties = tool["arguments"]["properties"]
    data_item = properties["candidateDataBindings"]["properties"]["ArrayItem"]
    output_schema = tool["outputSchema"]

    assert tool["arguments"]["required"] == ["userQuery"]
    assert set(data_item["properties"]) == {
        "writeResultTo",
        "arguments",
        "capabilityId",
        "candidateOutputFields",
    }
    assert output_schema["required"] == ["status", "suggestSize", "message"]
    assert "artifactUrl" in output_schema["properties"]
    assert "effectiveCapabilities" in output_schema["properties"]


def _weather_binding(arguments=None, output_fields=None):
    return {
        "capabilityId": "ViewWeather",
        "arguments": arguments or {"prefectureName": "杭州市", "forecastDays": 1},
        "writeResultTo": "/data/weather",
        "candidateOutputFields": output_fields or ["/current/condition"],
    }


def test_preflight_accepts_weather_without_district_and_builds_specs():
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    event = registry.get_event_capability("event.open.weather")
    assert event is not None
    request = _request(
        candidateDataBindings=[_weather_binding()],
        candidateEventCandidates=[
            {
                "capabilityId": event.id,
                "action": event.actionTemplate.model_dump(mode="json"),
            }
        ],
    )

    result = _run(request)

    assert result.blocking_issues == ()
    assert result.card_spec is not None
    assert result.task_spec is not None
    assert result.card_spec.dataBindings[0].arguments == {
        "prefectureName": "杭州市",
        "forecastDays": 1,
    }
    assert [item.id for item in result.effective_events] == [event.id]
    weather_schema = result.task_spec.dataModelSchema["data"]["weather"]
    assert weather_schema["current"]["condition"]
    assert weather_schema["location"]["cityCode"]


def test_preflight_reports_exact_missing_weather_argument_path():
    request = _request(
        candidateDataBindings=[
            _weather_binding(arguments={"districtName": "滨江区"})
        ]
    )

    result = _run(request)

    issue = result.blocking_issues[0]
    assert issue.code == "DATA_ARGUMENT_SCHEMA_INVALID"
    assert issue.path == "/candidateDataBindings/0/arguments/prefectureName"
    assert issue.agentAction == "FIX_AND_RETRY"
    assert issue.retryable is True
    assert "JSON 类型 string" in issue.expected
    assert "城市名" in issue.expected
    assert "无法唯一确定时询问用户" in issue.repairInstruction
    assert issue.referenceSource.endswith("inputSchema")
    assert result.card_spec is None
    assert result.task_spec is None


def test_preflight_blocks_whole_request_when_one_binding_is_invalid():
    request = _request(
        candidateDataBindings=[
            _weather_binding(),
            {
                "capabilityId": "GetCountdownDays",
                "arguments": {},
                "writeResultTo": "/data/countdown",
            },
        ]
    )

    result = _run(request)

    assert [item.capabilityId for item in result.effective_bindings] == [
        "ViewWeather"
    ]
    assert any(
        issue.path == "/candidateDataBindings/1/arguments/targetDate"
        for issue in result.blocking_issues
    )
    assert result.task_spec is None


def test_preflight_rejects_invalid_output_projection():
    request = _request(
        candidateDataBindings=[
            _weather_binding(output_fields=["/current/notRegistered"])
        ]
    )

    result = _run(request)

    issue = result.blocking_issues[0]
    assert issue.code == "OUTPUT_FIELD_PATH_INVALID"
    assert issue.path == "/candidateDataBindings/0/candidateOutputFields/0"


def test_preflight_accepts_weather_output_fields_without_layout_count_limit():
    output_fields = [
        "/location/districtName",
        "/location/prefectureName",
        "/current/temperatureText",
        "/current/condition",
        "/current/feelsLikeC",
        "/current/humidityPercent",
        "/current/airQuality",
        "/current/windDirection",
        "/current/windLevel",
        "/current/uvIndex",
        "/current/alertLevel",
        "/daily/0/temperatureRangeText",
        "/daily/0/rainProbabilityPercent",
    ]
    request = _request(
        userQuery="使用2x2规格，展示上海天气的全部信息",
        candidateDataBindings=[_weather_binding(output_fields=output_fields)],
    )

    result = _run(request)

    assert result.blocking_issues == ()
    assert result.task_spec is not None
    weather = result.task_spec.dataModelSchema["data"]["weather"]
    assert weather["current"]["temperatureText"]
    assert weather["daily"][0]["rainProbabilityPercent"]


def test_preflight_accepts_calendar_array_indices_and_scalar_array_field():
    request = _request(
        candidateDataBindings=[
            {
                "capabilityId": "GetCalendarEvents",
                "arguments": {"futureDays": 7},
                "writeResultTo": "/data/calendar",
                "candidateOutputFields": [
                    "/events/0/title",
                    "/events/1/title",
                    "/events/1/remindTime",
                    "/events/2/title",
                ],
            }
        ]
    )

    result = _run(request)

    assert result.blocking_issues == ()
    assert result.task_spec is not None
    events = result.task_spec.dataModelSchema["data"]["calendar"]["events"]
    assert len(events) == 3
    assert events[0]["title"]
    assert events[1]["title"]
    assert events[1]["remindTime"][0]
    assert events[2]["title"]


def test_preflight_reports_write_result_conflict_on_second_binding():
    request = _request(
        candidateDataBindings=[
            _weather_binding(),
            {
                "capabilityId": "GetCountdownDays",
                "arguments": {"targetDate": "2026-12-31"},
                "writeResultTo": "/data/weather/countdown",
            },
        ]
    )

    result = _run(request)

    issue = next(
        item
        for item in result.blocking_issues
        if item.code == ErrorCode.WRITE_RESULT_CONFLICT
    )
    assert issue.path == "/candidateDataBindings/1/writeResultTo"


def test_preflight_rejects_event_call_and_fixed_argument_mismatch():
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    event = registry.get_event_capability("event.open.settings.battery")
    assert event is not None
    action = event.actionTemplate.model_dump(mode="json")
    action["call"] = "clickToIntent"
    action["args"]["intentName"] = "Changed"
    request = _request(
        candidateEventCandidates=[
            {
                "capabilityId": event.id,
                "action": action,
            }
        ]
    )

    result = _run(request)

    issue_paths = {item.path for item in result.blocking_issues}
    assert "/candidateEventCandidates/0/action/call" in issue_paths
    assert "/candidateEventCandidates/0/action/args/intentName" in issue_paths


def test_preflight_rejects_event_data_path_outside_registered_template():
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    event = registry.get_event_capability("event.open.weather")
    assert event is not None
    action = event.actionTemplate.model_dump(mode="json")
    action["args"]["uri"] = "{{ ${/data/weather/current/notRegistered} }}"
    request = _request(
        candidateDataBindings=[_weather_binding()],
        candidateEventCandidates=[
            {
                "capabilityId": event.id,
                "action": action,
            }
        ],
    )

    result = _run(request)

    issue = next(
        item
        for item in result.blocking_issues
        if item.code == "EVENT_DATA_PATH_INVALID"
    )
    assert issue.path == "/candidateEventCandidates/0/action/args/uri"


def test_preflight_accepts_legacy_static_weather_event_uri():
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    event = registry.get_event_capability("event.open.weather")
    assert event is not None
    action = event.actionTemplate.model_dump(mode="json")
    action["args"]["uri"] = (
        "hww://www.huawei.com/totemweather?enterType=share&cityCode="
    )
    request = _request(
        candidateDataBindings=[_weather_binding()],
        candidateEventCandidates=[
            {
                "capabilityId": event.id,
                "action": action,
            }
        ],
    )

    result = _run(request)

    assert result.blocking_issues == ()
    assert result.task_spec is not None
    assert result.effective_events[0].args["uri"] == action["args"]["uri"]


def test_preflight_removes_event_with_missing_data_dependency_without_blocking():
    registry = CapabilityRegistry(version=REGISTRY_VERSION)
    event = registry.get_event_capability("event.open.weather")
    assert event is not None
    request = _request(
        candidateEventCandidates=[
            {
                "capabilityId": event.id,
                "action": event.actionTemplate.model_dump(mode="json"),
            }
        ]
    )

    result = _run(request)

    assert result.blocking_issues == ()
    assert result.effective_events == ()
    assert result.warnings[0].code == "EVENT_DATA_DEPENDENCY_REMOVED"
    assert result.removed_capabilities[0].reason == ErrorCode.NO_EFFECTIVE_CAPABILITY


def test_preflight_rejects_unknown_asset():
    result = _run(_request(candidateAssetIds=["asset.not-registered"]))

    issue = result.blocking_issues[0]
    assert issue.code == ErrorCode.UNKNOWN_CAPABILITY
    assert issue.path == "/candidateAssetIds/0"
    assert issue.agentAction == "REFRESH_CAPABILITIES"
    assert issue.referenceSource.endswith("assetCandidates[]")


@pytest.mark.asyncio
async def test_generation_preflight_failure_does_not_call_model_or_start_directive(
    monkeypatch,
):
    def unexpected_generate(*_args, **_kwargs):
        pytest.fail("an invalid candidate plan must not reach the model")

    async def before_model_call(_size):
        pytest.fail("preflight failure must happen before AIWidgetStart")

    monkeypatch.setattr(A2UIModelClient, "generate", unexpected_generate)
    request = _request(
        candidateDataBindings=[
            _weather_binding(arguments={"districtName": "滨江区"})
        ]
    )

    with pytest.raises(GenerationPreflightError) as exc_info:
        await WidgetGenerationService().generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        )

    details = exc_info.value.details()
    assert details["stage"] == "generationPreflight"
    assert details["modelCalled"] is False
    assert details["retryable"] is True
    assert details["requiredActions"] == ["FIX_AND_RETRY"]
    assert "修正全部 issues" in details["agentInstruction"]
    assert details["issues"][0]["path"].endswith("/prefectureName")
    assert "滨江区" not in str(details)
