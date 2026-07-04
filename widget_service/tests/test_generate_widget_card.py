from api.schemas import GenerateWidgetCardRequest
from core.errors import GenerationStatus
from models.generation import CandidateDataBinding, EventAction, GenerationOptions
from services.widget_generation_service import WidgetGenerationService


def test_generate_widget_card_success_with_weather_and_calendar():
    response = WidgetGenerationService().generate_widget_card(
        GenerateWidgetCardRequest(
            userQuery="帮我做通勤卡片，包含天气和今日日程",
            size="2x4",
            romVersion="7.0.0",
            candidateDataBindings=[
                CandidateDataBinding(
                    capabilityId="ViewWeather",
                    arguments={"districtName": "青浦区", "forecastDays": 1},
                    writeResultTo="/data/weather",
                ),
                CandidateDataBinding(
                    capabilityId="calendar.events.search",
                    arguments={"timeRange": "today"},
                    writeResultTo="/data/calendar",
                ),
            ],
            candidateEventCapabilityIds=["event.open.weather"],
            candidateEventActions=[
                EventAction(call="clickToDeeplink", args={"uri": "hww://weather"})
            ],
            candidateAssetIds=["asset.drop_1", "asset.calendar_fill"],
            options=GenerationOptions(returnArtifactInline=True),
        )
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl
    assert response.artifactDigest.startswith("sha256:")
    assert response.artifact is not None
    assert response.artifact["cardSpec"]["suggestSize"] == "2x4"
    assert len(response.artifact["genui"].splitlines()) == 3


def test_generate_widget_card_degraded_for_unknown_capability():
    response = WidgetGenerationService().generate_widget_card(
        GenerateWidgetCardRequest(
            userQuery="帮我做包含天气和股票的大卡片",
            size="2x4",
            romVersion="7.0.0",
            candidateDataBindings=[
                CandidateDataBinding(
                    capabilityId="ViewWeather", arguments={}, writeResultTo="/data/weather"
                ),
                CandidateDataBinding(
                    capabilityId="stock.quote", arguments={}, writeResultTo="/data/stock"
                ),
            ],
            options=GenerationOptions(returnArtifactInline=True),
        )
    )

    assert response.status == GenerationStatus.DEGRADED
    assert response.removedCapabilities[0].reason == "UNKNOWN_CAPABILITY"
    assert response.artifact is not None
    bindings = response.artifact["cardSpec"]["dataBindings"]
    assert [item["capabilityId"] for item in bindings] == ["ViewWeather"]


def test_generate_widget_card_unsupported_when_all_dynamic_capabilities_removed():
    response = WidgetGenerationService().generate_widget_card(
        GenerateWidgetCardRequest(
            userQuery="帮我做美团外卖配送状态卡片",
            size="2x4",
            romVersion="7.0.0",
            candidateDataBindings=[
                CandidateDataBinding(
                    capabilityId="meituan.delivery.status",
                    arguments={},
                    writeResultTo="/data/delivery",
                )
            ],
        )
    )

    assert response.status == GenerationStatus.UNSUPPORTED
    assert response.errorCode == "NO_EFFECTIVE_CAPABILITY"
    assert not response.artifactUrl


def test_generate_widget_card_removes_write_result_conflict():
    response = WidgetGenerationService().generate_widget_card(
        GenerateWidgetCardRequest(
            userQuery="帮我做通勤卡片",
            size="2x4",
            romVersion="7.0.0",
            candidateDataBindings=[
                CandidateDataBinding(
                    capabilityId="ViewWeather", arguments={}, writeResultTo="/data/common"
                ),
                CandidateDataBinding(
                    capabilityId="calendar.events.search",
                    arguments={},
                    writeResultTo="/data/common",
                ),
            ],
            options=GenerationOptions(returnArtifactInline=True),
        )
    )

    assert response.status == GenerationStatus.DEGRADED
    assert any(item.reason == "WRITE_RESULT_CONFLICT" for item in response.removedCapabilities)
