from widget_service.api.schemas import CapabilityOverviewRequest
from widget_service.services.widget_generation_service import WidgetGenerationService


def test_get_widget_capability_overview_returns_versioned_capabilities():
    response = WidgetGenerationService().get_widget_capability_overview(
        CapabilityOverviewRequest(capabilityRegistryVersion="2026-07-03")
    )

    assert response.capabilityRegistryVersion == "2026-07-03"
    assert any(item.id == "ViewWeather" for item in response.dataCapabilities)
    assert any(item.id == "event.open.weather" for item in response.eventCapabilities)
    assert any(item.id == "asset.weather.rain" for item in response.assetCandidates)
