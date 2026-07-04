from api.schemas import DataCapabilitySchemasRequest
from services.widget_generation_service import WidgetGenerationService


def test_get_data_capability_schemas_returns_full_schema():
    response = WidgetGenerationService().get_data_capability_schemas(
        DataCapabilitySchemasRequest(dataCapabilityIds=["ViewWeather", "unknown"])
    )

    assert [item.id for item in response.dataCapabilities] == ["ViewWeather"]
    assert response.dataCapabilities[0].defaultWriteResultTo == "/data/weather"
    assert response.missingCapabilityIds == ["unknown"]
