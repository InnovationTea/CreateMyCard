from fastapi.testclient import TestClient

from widget_service.main import app


def test_tool_dispatch_overview():
    client = TestClient(app)
    response = client.post("/api/v1/tools/getWidgetCapabilityOverview", json={"arguments": {}})

    assert response.status_code == 200
    body = response.json()
    assert body["capabilityRegistryVersion"] == "2026-07-03"
    assert body["dataCapabilities"]
