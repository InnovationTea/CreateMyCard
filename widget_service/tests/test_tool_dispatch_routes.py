# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
REPORT_DIR = PROJECT_ROOT / "test_reports"
SESSION_ID = "7676c2c8-a6d3-413c-8074-c62ed30db8de"
DEVICE_INFO = {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": "11.7.5.205",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260707115342975",
}

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

app = importlib.import_module("main").app
DeviceContext = importlib.import_module("models.generation").DeviceContext
IDSClient = importlib.import_module("services.ids_client").IDSClient


def _tool_payload(content: dict, interaction_id: str, original: str = "") -> dict:
    """构造新协议 WebSocket 请求包络。

    入参：
    - content：业务入参，对应旧协议 arguments。
    - interaction_id：当前交互 ID，会和 sessionId 拼接成 requestId。
    - original：用户原始表达，generateWidgetCard 未传 userQuery 时可兜底使用。
    出参：完整 WebSocket 请求字典。
    """
    return {
        "content": content,
        "deviceInfo": DEVICE_INFO,
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": interaction_id,
            "isNew": False,
            "sessionId": SESSION_ID,
        },
        "userAuth": {"user": {"userId": "test-user-001"}},
        "utterance": {"original": original, "type": "text"},
        "version": "1.0",
        "bundleName": "com.omega_w_0823.hmservice",
    }


def _request_id(interaction_id: str) -> str:
    """生成服务端应返回的 requestId。

    入参：
    - interaction_id：当前交互 ID。
    出参：`sessionId&interactionId` 格式的 requestId。
    """
    return f"{SESSION_ID}&{interaction_id}"


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


def _report_path(operation: str) -> Path:
    """生成单接口测试报告路径。

    入参：
    - operation：接口名。
    出参：以接口名命名的 Markdown 测试报告路径。
    """
    return REPORT_DIR / f"{operation}.md"


def _write_test_report(record: dict) -> None:
    """输出单个 WebSocket 接口测试报告。

    入参：
    - record：单个 operation 的 ready、请求、响应和状态记录。
    出参：无；函数会写入 `接口名.md` 测试报告文件。
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {record['operation']} 测试报告",
        "",
        f"- 生成时间：{datetime.now(UTC).isoformat()}",
        f"- 接口名：`{record['operation']}`",
        f"- WebSocket path：`/api/v1/ws/tools/{record['operation']}`",
        "- 请求协议：content/deviceInfo/session 外层包络",
        f"- requestId：`{record['requestId']}`",
        f"- ready 状态：`{record['ready'].get('type')}`",
        f"- 消息状态：`{record['messageType']}`",
        f"- 业务状态：`{record['status']}`",
        "",
        "## ready 消息",
        "",
        _json_block(record["ready"]),
        "",
        "## 入参",
        "",
        _json_block(record["request"]),
        "",
        "## 出参",
        "",
        _json_block(record["response"]),
    ]

    _report_path(record["operation"]).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def test_widget_card_service_complete_flow():
    """验证三个 WebSocket 工具入口覆盖能力概述、数据 schema 加载和卡片生成。

    入参：无。
    出参：无；通过断言验证新协议入参、requestId 拼接和三段业务流程。
    """
    client = TestClient(app)
    records: list[dict] = []
    device = DeviceContext(
        deviceType=DEVICE_INFO["phoneType"],
        sysVersion=DEVICE_INFO["sysVer"],
        deviceName=DEVICE_INFO["deviceFormation"],
        romVersion="ALN-AL00 7.0.0.36",
        marketingName=DEVICE_INFO["phoneType"],
        ohosApiVersion=36,
    )
    ids_state = IDSClient().get_device_capability_state(device, "ids-test-1")
    assert "UG.weather.current" in ids_state.providers

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        assert ready["tool"] == "getWidgetCapabilityOverview"

        overview_request = _tool_payload(
            {"bundleName": "com.omega_w_0823.hmservice"},
            "1",
        )
        websocket.send_json(overview_request)
        overview_message = websocket.receive_json()
        overview = overview_message["data"]
        assert overview_message["type"] == "result"
        assert overview_message["operation"] == "getWidgetCapabilityOverview"
        assert overview_message["requestId"] == _request_id("1")
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
                "ready": ready,
                "request": overview_request,
                "response": overview_message,
            }
        )

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        schema_ready = websocket.receive_json()
        assert schema_ready["type"] == "ready"
        assert schema_ready["tool"] == "getDataCapabilitySchemas"

        schema_request = _tool_payload(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "dataCapabilityIds": ["ViewWeather"],
            },
            "2",
        )
        websocket.send_json(schema_request)
        schema_message = websocket.receive_json()
        schema = schema_message["data"]
        assert schema_message["type"] == "result"
        assert schema_message["operation"] == "getDataCapabilitySchemas"
        assert schema_message["requestId"] == _request_id("2")
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert "districtName" in schema["dataCapabilities"][0]["inputSchema"]["properties"]
        assert schema["missingCapabilityIds"] == []
        records.append(
            {
                "operation": schema_message["operation"],
                "requestId": schema_message["requestId"],
                "messageType": schema_message["type"],
                "status": _operation_status(schema_message),
                "ready": schema_ready,
                "request": schema_request,
                "response": schema_message,
            }
        )

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        generate_ready = websocket.receive_json()
        assert generate_ready["type"] == "ready"
        assert generate_ready["tool"] == "generateWidgetCard"

        generate_request = _tool_payload(
            {
                "bundleName": "com.omega_w_0823.hmservice",
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
            "3",
            "帮我做通勤卡片，包含天气",
        )
        websocket.send_json(generate_request)
        generate_message = websocket.receive_json()
        generated = generate_message["data"]
        assert generate_message["type"] == "result"
        assert generate_message["operation"] == "generateWidgetCard"
        assert generate_message["requestId"] == _request_id("3")
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
                "ready": generate_ready,
                "request": generate_request,
                "response": generate_message,
            }
        )

    for record in records:
        _write_test_report(record)
