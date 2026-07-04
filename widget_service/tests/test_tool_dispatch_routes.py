from fastapi.testclient import TestClient

from main import app


def test_tool_dispatch_overview():
    client = TestClient(app)
    response = client.post("/api/v1/tools/getWidgetCapabilityOverview", json={"arguments": {}})

    assert response.status_code == 200
    body = response.json()
    assert body["capabilityRegistryVersion"] == "app-1.0.0_rom-7.0.0"
    assert body["dataCapabilities"]


def test_generate_widget_card_ws():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/widget/generate") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"

        websocket.send_json(
            {
                "requestId": "test-1",
                "arguments": {
                    "userQuery": "帮我做通勤卡片，包含天气和今日日程",
                    "size": "2x4",
                    "romVersion": "7.0.0",
                    "candidateDataBindings": [
                        {
                            "capabilityId": "ViewWeather",
                            "arguments": {"districtName": "上海", "forecastDays": 1},
                            "writeResultTo": "/data/weather",
                        }
                    ],
                    "options": {"returnArtifactInline": True},
                },
            }
        )
        result = websocket.receive_json()

    assert result["type"] == "generateWidgetCardResult"
    assert result["requestId"] == "test-1"
    assert result["data"]["status"] == "success"
    assert result["data"]["artifactUrl"]


def test_generate_widget_card_tool_dispatch_uses_ws():
    client = TestClient(app)
    response = client.post("/api/v1/tools/generateWidgetCard", json={"arguments": {}})

    assert response.status_code == 400
    assert "WebSocket" in response.json()["detail"]
