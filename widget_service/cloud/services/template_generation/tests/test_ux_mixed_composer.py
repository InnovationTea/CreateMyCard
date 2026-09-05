"""Prototype 01: deterministic second-layer composition (fast path)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.controls import TemplateControls, load_template_controls
from services.template_generation.engine.advanced.ux_mixed_composer import (
    compose_deterministic_tree,
)
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalQuery,
    retrieve_template_variants,
)
from services.template_generation.engine.pipeline import (
    TemplateEngineOutput,
    _generate_selected_templates,
)

_WEATHER_FULL_DEMAND = ("/current/temperatureText", "/current/condition")


class _RefusingModelClient:
    """任何 LLM 调用都应使测试失败：确定性组合路径不得触达模型。"""

    def generate_json(self, prompt: Any, phase: str = "") -> Any:
        raise AssertionError(f"LLM generate_json must not be called (phase={phase})")

    def generate(self, messages: Any, profile: Any, **kwargs: Any) -> str:
        raise AssertionError("LLM generate must not be called on the fast path")


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {"type": data_type, "description": "trusted", "sampleValue": value}


def _weather_schema() -> dict[str, Any]:
    return {
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
    }


def _weather_task() -> TaskSpec:
    return TaskSpec(
        userQuery="显示温度和天气情况",
        size="2x2",
        dataModelSchema=_weather_schema(),
    )


def _weather_binding() -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/location/districtName",
            "/current/temperatureText",
            "/current/condition",
            "/current/airQuality",
            "/current/coldLevel",
        ],
    )


def _weather_card_spec() -> dict[str, Any]:
    return {
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }


def _pinned_full_selection() -> Any:
    """单一业务 Full 需求：唯一模板覆盖，布局与模板均无选择空间。"""
    task = _weather_task()
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={"ViewWeather": _WEATHER_FULL_DEMAND},
    )
    result = retrieve_template_variants(
        query,
        task,
        get_cardplan_registry(),
        (_weather_binding(),),
        _weather_card_spec(),
    )
    return task, result


def test_controls_default_enables_deterministic_composer() -> None:
    controls = TemplateControls.model_validate({"schemaVersion": "template-controls/1"})
    assert controls.second_layer_deterministic_composer is True
    disabled = TemplateControls.model_validate(
        {
            "schemaVersion": "template-controls/1",
            "secondLayerDeterministicComposer": False,
        }
    )
    assert disabled.second_layer_deterministic_composer is False
    assert load_template_controls().second_layer_deterministic_composer is True


def test_composer_builds_single_focus_tree_for_pinned_full_template() -> None:
    task, result = _pinned_full_selection()
    assert result.component_candidates[0].available_template_ids == (
        "WeatherOverviewFull@1",
    )
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=_weather_card_spec(),
        scope=result.scope,
        component_candidates=result.component_candidates,
        required_template_groups=result.required_template_groups,
        registry=get_cardplan_registry(),
    )
    tree = compose_deterministic_tree(projection, get_cardplan_registry())
    assert tree is not None
    assert 'Template("SingleFocusLayout@1"' in tree
    assert 'Template("WeatherOverviewFull@1", {})' in tree

    compilation = compile_ux_layout_card(
        tree,
        task_spec=task,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(
            A2UI_FORM_PROTOCOL_PROFILE_ID
        ).get_profile(),
        registry=get_cardplan_registry(),
        card_spec=_weather_card_spec(),
        enable_data_bindings=True,
    )
    assert set(compilation.stats.template_used_ids) == {
        "WeatherOverviewFull@1",
        "SingleFocusLayout@1",
    }


def test_composer_builds_hero_title_content_tree_with_action() -> None:
    task = TaskSpec(
        userQuery="显示天气和下一场日程，并提供查看入口",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": _weather_schema()["data"]["weather"],
                "calendar": {
                    "events": [
                        {
                            "title": _field("项目例会"),
                            "dtStart": _field("14:00"),
                            "dtEnd": _field("15:00"),
                            "eventLocation": _field("A1 会议室"),
                        }
                    ]
                },
            }
        },
        eventCandidates=[
            EventAction(
                id="event.open.details",
                description="查看详情",
                call="clickToDeeplink",
                args={"uri": "example://details"},
            )
        ],
    )
    weather_binding = _weather_binding().model_copy(
        update={
            "candidateOutputFields": [
                "/location/districtName",
                "/current/temperatureText",
                "/current/condition",
            ]
        }
    )
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
    card_spec = {
        "title": "天气和日程",
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
            {"capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar"},
        ],
    }
    result = retrieve_template_variants(
        TemplateRetrievalQuery(
            themeId="family-weather-care-blue",
            requiredOutputFieldsByCapability={
                "ViewWeather": (
                    "/location/districtName",
                    "/current/temperatureText",
                    "/current/condition",
                ),
                "GetCalendarEvents": (
                    "/events/0/title",
                    "/events/0/dtStart",
                    "/events/0/dtEnd",
                    "/events/0/eventLocation",
                ),
            },
            action=("event.open.details",),
        ),
        task,
        get_cardplan_registry(),
        (weather_binding, calendar_binding),
        card_spec,
    )
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card_spec,
        scope=result.scope,
        component_candidates=result.component_candidates,
        required_template_groups=result.required_template_groups,
        registry=get_cardplan_registry(),
    )
    tree = compose_deterministic_tree(projection, get_cardplan_registry())
    assert tree is not None
    layout_index = tree.index('Template("HeroTitleContentActionLayout@1"')
    title_index = tree.index('Template("WeatherOverviewHeroTitle@1"')
    content_index = tree.index('Template("ScheduleOverviewHeroContent@1"')
    action_index = tree.index('Template("PillAction@1"')
    assert layout_index < title_index < content_index < action_index
    assert '"actionId":"event.open.details"' in tree
    assert tree.endswith(";")

    compilation = compile_ux_layout_card(
        tree,
        task_spec=task,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(
            A2UI_FORM_PROTOCOL_PROFILE_ID
        ).get_profile(),
        registry=get_cardplan_registry(),
        card_spec=card_spec,
        enable_data_bindings=True,
    )
    assert "WeatherOverviewHeroTitle@1" in compilation.stats.template_used_ids
    assert "ScheduleOverviewHeroContent@1" in compilation.stats.template_used_ids


def test_composer_returns_none_when_group_has_multiple_candidates() -> None:
    task = _weather_task()
    task.dataModelSchema["data"]["weather"]["current"]["humidityPercent"] = _field(62, "number")
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/current/temperatureText",
                "/current/condition",
                "/current/airQuality",
                "/current/coldLevel",
            )
        },
    )
    result = retrieve_template_variants(
        query,
        task,
        get_cardplan_registry(),
        (_weather_binding(),),
        _weather_card_spec(),
    )
    assert len(result.required_template_groups[0]) == 2
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=_weather_card_spec(),
        scope=result.scope,
        component_candidates=result.component_candidates,
        required_template_groups=result.required_template_groups,
        registry=get_cardplan_registry(),
    )
    assert compose_deterministic_tree(projection, get_cardplan_registry()) is None


def test_generate_selected_templates_skips_llm_on_deterministic_composition() -> None:
    task, result = _pinned_full_selection()
    output = asyncio.run(
        _generate_selected_templates(
            source_task_spec=task,
            card_spec=_weather_card_spec(),
            effective_capability_ids={"ViewWeather"},
            scope=result.scope,
            component_candidates=result.component_candidates,
            required_template_groups=result.required_template_groups,
            registry=get_cardplan_registry(),
            model_client=_RefusingModelClient(),
            use_deterministic_composer=True,
        )
    )
    assert isinstance(output, TemplateEngineOutput)
    assert "WeatherOverviewFull@1" in output.template_ids
    assert "SingleFocusLayout@1" in output.template_ids
    assert output.a2ui


def test_generate_selected_templates_flag_off_uses_llm_path() -> None:
    task, result = _pinned_full_selection()
    with pytest.raises(AssertionError, match="must not be called"):
        asyncio.run(
            _generate_selected_templates(
                source_task_spec=task,
                card_spec=_weather_card_spec(),
                effective_capability_ids={"ViewWeather"},
                scope=result.scope,
                component_candidates=result.component_candidates,
                required_template_groups=result.required_template_groups,
                registry=get_cardplan_registry(),
                model_client=_RefusingModelClient(),
                use_deterministic_composer=False,
            )
        )
