import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
REPORT_DIR = PROJECT_ROOT / "test_reports"
REPORT_PATH = REPORT_DIR / "widget_card_service_ws_report.md"
TOOL_CONTEXT = {
    "uid": "test-user-001",
    "locale": "zh-CN",
    "device": {
        "deviceId": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
        "deviceType": "ALN-AL00",
        "sysVersion": "HarmonyOS 7.0.0",
        "deviceName": "phone",
        "odid": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
        "udid": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
        "romVersion": "ALN-AL00 7.0.0.36",
        "marketingName": "HUAWEI Mate 60 Pro",
        "ohosApiVersion": 36,
    },
}

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

app = importlib.import_module("main").app
DeviceContext = importlib.import_module("models.generation").DeviceContext
IDSClient = importlib.import_module("services.ids_client").IDSClient


def _json_block(payload: dict) -> str:
    """把 JSON 对象格式化成 Markdown 代码块。

    入参：
    - payload：需要写入报告的 JSON 对象。
    出参：Markdown JSON 代码块字符串。
    """
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def _operation_status(message: dict) -> str:
    """提取单个 WebSocket 响应消息状态。

    入参：
    - message：服务端返回的 WebSocket 消息。
    出参：功能执行状态；生成接口优先返回业务 status，其它接口返回消息 type。
    """
    data = message.get("data", {})
    return data.get("status") or message.get("type", "unknown")


def _write_test_report(ready: dict, records: list[dict]) -> None:
    """输出 WebSocket 全流程测试报告。

    入参：
    - ready：WebSocket 连接建立后的 ready 消息。
    - records：每个 operation 的请求、响应和状态记录。
    出参：无；函数会写入 Markdown 测试报告文件。
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# widgetCardService WebSocket 测试报告",
        "",
        f"- 生成时间：{datetime.now(UTC).isoformat()}",
        "- 入口：`WS /api/v1/ws/tools/widgetCardService`",
        f"- ready 状态：`{ready.get('type')}`",
        f"- 工具名：`{ready.get('tool')}`",
        f"- 覆盖功能数：{len(records)}",
        "",
        "## ready 消息",
        "",
        _json_block(ready),
    ]

    for index, record in enumerate(records, start=1):
        lines.extend(
            [
                "",
                f"## {index}. {record['operation']}",
                "",
                f"- requestId：`{record['requestId']}`",
                f"- 消息状态：`{record['messageType']}`",
                f"- 业务状态：`{record['status']}`",
                "",
                "### 入参",
                "",
                _json_block(record["request"]),
                "",
                "### 出参",
                "",
                _json_block(record["response"]),
            ]
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_widget_card_service_complete_flow():
    """验证统一 WebSocket 工具入口覆盖能力概述、数据 schema 加载和卡片生成。

    入参：无。
    出参：无；断言统一入口三段流程都符合预期。
    """
    client = TestClient(app)
    records: list[dict] = []
    ids_state = IDSClient().get_device_capability_state(
        DeviceContext(**TOOL_CONTEXT["device"]),
        "ids-test-1",
    )
    assert "UG.weather.current" in ids_state.providers

    with client.websocket_connect("/api/v1/ws/tools/widgetCardService") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        assert ready["tool"] == "widgetCardService"

        overview_request = {
            "requestId": "overview-1",
            "arguments": {
                **TOOL_CONTEXT,
                "operation": "getWidgetCapabilityOverview",
            },
        }
        websocket.send_json(overview_request)
        overview_message = websocket.receive_json()
        overview = overview_message["data"]
        assert overview_message["type"] == "result"
        assert overview_message["operation"] == "getWidgetCapabilityOverview"
        assert overview["capabilityRegistryVersion"] == "ohos-36_rom-7.0.0"
        assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])
        assert any(item["id"] == "event.open.weather" for item in overview["eventCapabilities"])
        assert any(item["id"] == "asset.drop_1" for item in overview["assetCandidates"])
        records.append(
            {
                "operation": overview_message["operation"],
                "requestId": overview_message["requestId"],
                "messageType": overview_message["type"],
                "status": _operation_status(overview_message),
                "request": overview_request,
                "response": overview_message,
            }
        )

        schema_request = {
            "requestId": "schema-1",
            "arguments": {
                **TOOL_CONTEXT,
                "operation": "getDataCapabilitySchemas",
                "dataCapabilityIds": ["ViewWeather"],
            },
        }
        websocket.send_json(schema_request)
        schema_message = websocket.receive_json()
        schema = schema_message["data"]
        assert schema_message["type"] == "result"
        assert schema_message["operation"] == "getDataCapabilitySchemas"
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert "districtName" in schema["dataCapabilities"][0]["inputSchema"]["properties"]
        assert schema["missingCapabilityIds"] == []
        records.append(
            {
                "operation": schema_message["operation"],
                "requestId": schema_message["requestId"],
                "messageType": schema_message["type"],
                "status": _operation_status(schema_message),
                "request": schema_request,
                "response": schema_message,
            }
        )

        generate_request = {
            "requestId": "generate-1",
            "arguments": {
                **TOOL_CONTEXT,
                "operation": "generateWidgetCard",
                "userQuery": "帮我做通勤卡片，包含天气",
                "size": "2x4",
                "candidateDataBindings": [
                    {
                        "capabilityId": "ViewWeather",
                        "arguments": {"districtName": "上海", "forecastDays": 1},
                        "writeResultTo": "/data/weather",
                        "updateModel": {
                            "location": {"districtName": ""},
                            "current": {
                                "temperatureText": "",
                                "condition": "",
                                "airQuality": "",
                            },
                            "updatedAt": "",
                        },
                    }
                ],
                "candidateEventCandidates": [
                    {
                        "capabilityId": "event.open.weather",
                        "action": {
                            "call": "clickToDeeplink",
                            "args": {"uri": "hww://weather"},
                        },
                    }
                ],
                "candidateAssetIds": ["asset.drop_1"],
            },
        }
        websocket.send_json(generate_request)
        generate_message = websocket.receive_json()
        generated = generate_message["data"]
        assert generate_message["type"] == "result"
        assert generate_message["operation"] == "generateWidgetCard"
        assert generated["status"] == "success"
        assert generated["artifactUrl"]
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]
        records.append(
            {
                "operation": generate_message["operation"],
                "requestId": generate_message["requestId"],
                "messageType": generate_message["type"],
                "status": _operation_status(generate_message),
                "request": generate_request,
                "response": generate_message,
            }
        )

    _write_test_report(ready, records)
