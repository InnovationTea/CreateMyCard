from api.schemas import CapabilityOverviewRequest
from services.widget_generation_service import WidgetGenerationService


def test_get_widget_capability_overview_returns_versioned_capabilities():
    response = WidgetGenerationService().get_widget_capability_overview(
        CapabilityOverviewRequest(appVersion="1.0.0", romVersion="7.0.0")
    )

    assert response.capabilityRegistryVersion == "app-1.0.0_rom-7.0.0"
    assert any(item.id == "ViewWeather" for item in response.dataCapabilities)
    assert any(item.id == "event.open.weather" for item in response.eventCapabilities)
    assert any(item.id == "asset.drop_1" for item in response.assetCandidates)
    assert "descriptionForLLM" not in response.dataCapabilities[0].model_dump()
    weather_event = next(
        item for item in response.eventCapabilities if item.id == "event.open.weather"
    )
    assert weather_event.argsTemplate
    assert len(response.assetCandidates) > 40
