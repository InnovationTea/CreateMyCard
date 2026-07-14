# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib
import json
import sys
import uuid
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
A2UIModelClient = importlib.import_module("custom.a2ui_model_client").A2UIModelClient
DeviceContext = importlib.import_module("models.generation").DeviceContext
IDSClient = importlib.import_module("services.ids_client").IDSClient


def _tool_payload(
    content: dict,
    interaction_id: str,
    original: str = "",
    device_info: dict | None = None,
) -> dict:
    """构造新协议 WebSocket 请求包络。

    入参：
    - content：业务入参，对应旧协议 arguments。
    - interaction_id：当前交互 ID，会和 sessionId 拼接成 requestId。
    - original：用户原始表达，generateWidgetCard 未传 userQuery 时可兜底使用。
    - device_info：可选设备信息；不传时使用正常版本设备。
    出参：完整 WebSocket 请求字典。
    """
    return {
        "content": content,
        "deviceInfo": device_info or DEVICE_INFO,
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


def _valid_model_output(_self, _prompt, protocol_profile: dict) -> str:
    """为路由集成测试返回对应 profile 的确定性合法模型输出。"""
    if protocol_profile.get("format") == "compact-dsl":
        return (CLOUD_ROOT / "custom" / "mock.compact-dsl.dat").read_text(
            encoding="utf-8"
        )

    rows = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "card",
                "catalogId": "ohos.a2ui.extended.catalog",
                "width": 300,
                "height": 140,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "card",
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": ["title"],
                        "styles": {
                            "width": 300,
                            "height": 140,
                            "padding": 12,
                            "borderRadius": 22,
                            "clip": True,
                        },
                    },
                    {
                        "id": "title",
                        "component": "Text",
                        "content": "Weather",
                        "styles": {
                            "fontSize": 16,
                            "fontWeight": 700,
                            "maxLines": 1,
                        },
                    },
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "card",
                "path": "/",
                "value": {},
            },
        },
    ]
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    )


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
    出参：功能执行状态；三类接口统一读取响应顶层 status。
    """
    return message.get("status", "unknown")


def _assert_success_envelope(message: dict, operation: str, request_id: str) -> dict:
    """校验三个 WebSocket 接口统一华为流处理插件响应包络。

    入参：
    - message：服务端返回的 WebSocket 消息。
    - operation：当前接口名。
    - request_id：预期 requestId。
    出参：reply.items[0] 中保留的当前完整旧出参。
    """
    assert message["errorCode"] == "0"
    assert message["errorMessage"] == ""
    assert "reply" in message
    stream_info = message["reply"]["streamInfo"]
    assert stream_info["streamingTextId"] == request_id
    assert stream_info["streamType"] == "final"
    assert stream_info["textType"] == "markdown"
    assert stream_info["streamContent"]

    assert len(message["reply"]["items"]) == 1
    legacy_message = message["reply"]["items"][0]
    assert legacy_message["type"] == "result"
    assert legacy_message["tool"] == operation
    assert legacy_message["operation"] == operation
    assert legacy_message["requestId"] == request_id
    assert "data" in legacy_message
    assert "status" in legacy_message
    assert "errorCode" in legacy_message
    assert "error" in legacy_message
    assert legacy_message["error"] == {}
    return legacy_message


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
    - record：单个 operation 的请求、响应和状态记录。
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
        f"- 消息状态：`{record['messageType']}`",
        f"- 业务状态：`{record['status']}`",
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


def test_widget_card_service_complete_flow(monkeypatch):
    """验证三个 WebSocket 工具入口覆盖能力概述、数据 schema 加载和卡片生成。

    入参：无。
    出参：无；通过断言验证新协议入参、requestId 拼接和三段业务流程。
    """
    monkeypatch.setattr(A2UIModelClient, "generate", _valid_model_output)
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
        overview_request = _tool_payload(
            {"bundleName": "com.omega_w_0823.hmservice"},
            "1",
        )
        websocket.send_json(overview_request)
        overview_message = websocket.receive_json()
        overview_legacy_message = _assert_success_envelope(
            overview_message,
            "getWidgetCapabilityOverview",
            _request_id("1"),
        )
        overview = overview_legacy_message["data"]
        assert overview_legacy_message["status"] == "success"
        assert overview_legacy_message["errorCode"] == ""
        assert overview["capabilityRegistryVersion"] == "app-11.7.5.205_rom-36"
        assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])
        assert any(item["id"] == "event.open.weather" for item in overview["eventCapabilities"])
        assert any(item["id"] == "asset.drop_1" for item in overview["assetCandidates"])
        records.append(
            {
                "operation": overview_legacy_message["operation"],
                "requestId": overview_legacy_message["requestId"],
                "messageType": overview_legacy_message["type"],
                "status": _operation_status(overview_legacy_message),
                "request": overview_request,
                "response": overview_message,
            }
        )

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        schema_request = _tool_payload(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "dataCapabilityIds": ["ViewWeather"],
            },
            "2",
        )
        websocket.send_json(schema_request)
        schema_message = websocket.receive_json()
        schema_legacy_message = _assert_success_envelope(
            schema_message,
            "getDataCapabilitySchemas",
            _request_id("2"),
        )
        schema = schema_legacy_message["data"]
        assert schema_legacy_message["status"] == "success"
        assert schema_legacy_message["errorCode"] == ""
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert "districtName" in schema["dataCapabilities"][0]["inputSchema"]["properties"]
        assert schema["missingCapabilityIds"] == []
        records.append(
            {
                "operation": schema_legacy_message["operation"],
                "requestId": schema_legacy_message["requestId"],
                "messageType": schema_legacy_message["type"],
                "status": _operation_status(schema_legacy_message),
                "request": schema_request,
                "response": schema_message,
            }
        )

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        generate_request = _tool_payload(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "userQuery": "帮我做通勤卡片，包含天气",
                "size": "2x4",
                "title": "通勤日常",
                "description": "天气速览",
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
        generate_legacy_message = _assert_success_envelope(
            generate_message,
            "generateWidgetCard",
            _request_id("3"),
        )
        generated = generate_legacy_message["data"]
        assert generate_legacy_message["status"] == "success"
        assert generate_legacy_message["errorCode"] == ""
        assert generated["status"] == "success"
        assert generated["artifactUrl"]
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]
        records.append(
            {
                "operation": generate_legacy_message["operation"],
                "requestId": generate_legacy_message["requestId"],
                "messageType": generate_legacy_message["type"],
                "status": _operation_status(generate_legacy_message),
                "request": generate_request,
                "response": generate_message,
            }
        )

    for record in records:
        _write_test_report(record)


def test_generation_routes_lock_and_isolate_protocol_profiles(monkeypatch):
    """验证工具3和工具4在同一服务进程中固定使用各自协议。"""
    monkeypatch.setattr(A2UIModelClient, "generate", _valid_model_output)
    client = TestClient(app)
    generation_content = {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": "生成一张静态天气卡片",
        "size": "2x4",
        "title": "天气速览",
        "description": "查看当前天气",
        "candidateDataBindings": [],
        "candidateEventCandidates": [],
        "candidateAssetIds": [],
        "options": {"returnArtifactInline": True},
    }

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        old_request = _tool_payload(
            {
                **generation_content,
                "protocolProfileId": "compact-dsl-v1",
            },
            "profile-old",
        )
        websocket.send_json(old_request)
        old_message = _assert_success_envelope(
            websocket.receive_json(),
            "generateWidgetCard",
            _request_id("profile-old"),
        )

    old_artifact = old_message["data"]["artifact"]
    old_rows = [json.loads(line) for line in old_artifact["genui"].splitlines()]
    assert old_artifact["meta"]["protocolProfileId"] == "a2ui-form-rom7-v1"
    assert len(old_rows) == 3
    assert [next(iter(row)) for row in old_rows] == ["version", "version", "version"]
    assert "createSurface" in old_rows[0]
    assert "updateComponents" in old_rows[1]
    assert "updateDataModel" in old_rows[2]

    with client.websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        compact_content = {
            **generation_content,
            "protocolProfileId": "a2ui-form-rom7-v1",
        }
        compact_content.pop("userQuery")
        compact_request = _tool_payload(
            compact_content,
            "profile-compact",
            original="生成一张静态天气卡片",
        )
        websocket.send_json(compact_request)
        compact_message = _assert_success_envelope(
            websocket.receive_json(),
            "generateWidgetCardCompactDsl",
            _request_id("profile-compact"),
        )

    compact_artifact = compact_message["data"]["artifact"]
    compact_rows = [
        json.loads(line) for line in compact_artifact["genui"].splitlines()
    ]
    assert compact_artifact["meta"]["protocolProfileId"] == "compact-dsl-v1"
    assert all(isinstance(row, list) for row in compact_rows)
    assert any(len(row) == 2 and row[0] == "/title" for row in compact_rows)


def test_missing_prd_version_returns_empty_capability_results():
    """验证随机不存在 prdVer 时三个接口返回可预期的空能力结果。

    入参：无。
    出参：无；通过随机 prdVer 断言能力概述、schema 和生成接口的降级表现。
    """
    client = TestClient(app)
    random_prd_ver = f"99.99.{uuid.uuid4().int % 100000000}"
    random_capability_id = f"MissingCapability.{uuid.uuid4().hex[:8]}"
    device_info = {**DEVICE_INFO, "prdVer": random_prd_ver}
    expected_version = f"app-{random_prd_ver}_rom-36"

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_json(
            _tool_payload(
                {"bundleName": "com.omega_w_0823.hmservice"},
                "missing-overview",
                device_info=device_info,
            )
        )
        overview_message = websocket.receive_json()

        overview_legacy_message = _assert_success_envelope(
            overview_message,
            "getWidgetCapabilityOverview",
            _request_id("missing-overview"),
        )
        overview = overview_legacy_message["data"]
        assert overview_legacy_message["status"] == "success"
        assert overview_legacy_message["errorCode"] == ""
        assert overview["capabilityRegistryVersion"] == expected_version
        assert overview["dataCapabilities"] == []
        assert overview["eventCapabilities"] == []
        assert overview["assetCandidates"] == []

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "bundleName": "com.omega_w_0823.hmservice",
                    "dataCapabilityIds": [random_capability_id],
                },
                "missing-schema",
                device_info=device_info,
            )
        )
        schema_message = websocket.receive_json()

        schema_legacy_message = _assert_success_envelope(
            schema_message,
            "getDataCapabilitySchemas",
            _request_id("missing-schema"),
        )
        schema = schema_legacy_message["data"]
        assert schema_legacy_message["status"] == "success"
        assert schema_legacy_message["errorCode"] == ""
        assert schema["capabilityRegistryVersion"] == expected_version
        assert schema["dataCapabilities"] == []
        assert schema["missingCapabilityIds"] == [random_capability_id]

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "bundleName": "com.omega_w_0823.hmservice",
                    "userQuery": f"随机能力版本测试 {uuid.uuid4().hex}",
                    "size": "2x4",
                    "title": "随机能力版本测试",
                    "description": "随机能力版本测试",
                    "candidateDataBindings": [
                        {
                            "capabilityId": random_capability_id,
                            "arguments": {"districtName": "上海"},
                            "writeResultTo": "/data/random",
                            "updateModel": {"value": ""},
                        }
                    ],
                    "candidateEventCandidates": [],
                    "candidateAssetIds": [],
                },
                "missing-generate",
                device_info=device_info,
            )
        )
        generate_message = websocket.receive_json()

        generate_legacy_message = _assert_success_envelope(
            generate_message,
            "generateWidgetCard",
            _request_id("missing-generate"),
        )
        generated = generate_legacy_message["data"]
        assert generate_legacy_message["status"] == "unsupported"
        assert generate_legacy_message["errorCode"] == "APP_VERSION_UNSUPPORTED"
        assert generated["status"] == "unsupported"
        assert generated["errorCode"] == "APP_VERSION_UNSUPPORTED"
        assert generated["artifactUrl"] == ""
        assert generated["effectiveCapabilities"] == {"data": [], "event": [], "asset": []}
