# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import importlib
import json
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from ws_response_parser import parse_legacy_stream_content

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
REPORT_DIR = PROJECT_ROOT / "test_reports"
SESSION_ID = "7676c2c8-a6d3-413c-8074-c62ed30db8de"
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))
REGISTRY_VERSION = f"app-{APP_VERSION}_rom-6.0"
DEVICE_INFO = {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": APP_VERSION,
    "sysVer": "EmotionUI_9.0.0",
    "romVersion": ROM_VERSION,
    "time": "20260707115342975",
}
REPORT_TIMESTAMPS = {
    "getWidgetCapabilityOverview": "2026-07-10T02:03:51.676293+00:00",
    "getDataCapabilitySchemas": "2026-07-10T02:03:51.678293+00:00",
    "generateWidgetCard": "2026-07-10T02:03:51.679293+00:00",
}

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

app = importlib.import_module("main").app
A2UIModelClient = importlib.import_module("custom.a2ui_model_client").A2UIModelClient
DeviceContext = importlib.import_module("models.generation").DeviceContext
IDSClient = importlib.import_module("services.ids_client").IDSClient
IDSDeviceCapabilityState = importlib.import_module(
    "services.ids_client"
).IDSDeviceCapabilityState
ArtifactSaveResult = importlib.import_module("models.service").ArtifactSaveResult
ArtifactStore = importlib.import_module("services.artifact_store").ArtifactStore
Settings = importlib.import_module("config.config").Settings
get_settings = importlib.import_module("config.config").get_settings
WidgetGenerationService = importlib.import_module(
    "services.widget_generation_service"
).WidgetGenerationService


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
        "content": {"odid": DEVICE_ODID, **content},
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


def _receive_final_frame(websocket, expected_request_id: str) -> dict:
    """读取一次调用的流式帧，验证心跳协议并返回 final 帧。"""
    start_received = False
    while True:
        message = websocket.receive_json()
        assert message["errorCode"] == "0"
        assert message["errorMessage"] == ""
        stream_info = message["reply"]["streamInfo"]
        assert stream_info["streamingTextId"] == expected_request_id
        stream_type = stream_info["streamType"]
        if stream_type == "start":
            assert stream_info["textType"] == "markdown"
            assert not start_received
            assert stream_info["streamContent"] == ""
            assert message["reply"]["items"] == []
            start_received = True
            continue
        if stream_type == "partial":
            assert stream_info["textType"] == "markdown"
            assert start_received
            assert stream_info["streamContent"] == ""
            assert message["reply"]["items"] == []
            continue

        assert stream_type == "final"
        assert start_received
        assert stream_info["textType"] == "plainText"
        return message


def test_websocket_send_disconnect_is_logged_and_not_raised(monkeypatch):
    """验证客户端断开后不再二次发送响应，异常仍按 ERROR 记录。"""
    routes_module = importlib.import_module("api.routes")
    error_messages: list[str] = []

    class CapturedLogger:
        def error(self, message, *_args, **_kwargs):
            error_messages.append(str(message))

    class DisconnectedWebSocket:
        async def send_json(self, _payload):
            raise routes_module.WebSocketDisconnect(code=1006)

    monkeypatch.setattr(routes_module, "logger", CapturedLogger())
    sent = asyncio.run(
        routes_module._send_websocket_json(
            DisconnectedWebSocket(),
            {"frame": "final"},
            "getWidgetCapabilityOverview",
            "request-1",
            "final",
        )
    )

    assert sent is False
    assert any("widget_operation_ws_send_failed" in item for item in error_messages)


def _valid_model_output(_self, _prompt, protocol_profile: dict) -> str:
    """为路由集成测试返回对应 profile 的确定性合法模型输出。"""
    if protocol_profile.get("format") == "compact-dsl":
        compact_rows = [
            [
                "root",
                "Column",
                {
                    "width": 320,
                    "height": 160,
                    "padding": 12,
                    "borderRadius": 22,
                    "clip": True,
                    "itemMargin": 6,
                    "backgroundColor": "#FFFFFFFF",
                },
                ["header", "body", "footer"],
            ],
            [
                "header",
                "Text",
                {
                    "width": 276,
                    "height": 20,
                    "content": "Weather",
                    "fontSize": 16,
                    "fontWeight": 700,
                    "fontColor": "#E5000000",
                    "maxLines": 1,
                },
            ],
            [
                "body",
                "Text",
                {
                    "width": 276,
                    "height": 64,
                    "content": "Static card",
                    "fontSize": 20,
                    "fontWeight": 700,
                    "fontColor": "#E5000000",
                    "maxLines": 1,
                },
            ],
            [
                "footer",
                "Text",
                {
                    "width": 276,
                    "height": 20,
                    "content": "Ready",
                    "fontSize": 12,
                    "fontWeight": 400,
                    "fontColor": "#99000000",
                    "maxLines": 1,
                },
            ],
            ["/ui/state", "ready"],
        ]
        return "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in compact_rows
        )

    rows = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
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
    出参：功能执行状态；正式接口统一读取响应顶层 status。
    """
    return message.get("status", "unknown")


def _assert_success_envelope(message: dict, operation: str, request_id: str) -> dict:
    """校验三个正式 WebSocket 接口统一华为流处理插件响应包络。

    入参：
    - message：服务端返回的 WebSocket 消息。
    - operation：当前接口名。
    - request_id：预期 requestId。
    出参：从 reply.streamInfo.streamContent 解析出的完整旧出参。
    """
    assert message["errorCode"] == "0"
    assert message["errorMessage"] == ""
    assert "reply" in message
    stream_info = message["reply"]["streamInfo"]
    assert stream_info["streamingTextId"] == request_id
    assert stream_info["streamType"] == "final"
    assert stream_info["textType"] == "plainText"
    assert message["reply"]["items"] == []
    legacy_message = parse_legacy_stream_content(stream_info["streamContent"])
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
        f"- 生成时间：{REPORT_TIMESTAMPS[record['operation']]}",
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
    """验证三个 WebSocket 工具入口覆盖能力发现、可用性校验和卡片生成。

    入参：无。
    出参：无；通过断言验证新协议入参、requestId 拼接和三段业务流程。
    """
    monkeypatch.setattr(A2UIModelClient, "generate", _valid_model_output)
    saved_artifacts = []

    def capture_artifact(_store, artifact):
        saved_artifacts.append(artifact.model_dump(mode="json", exclude_none=True))
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/widget/artifact.md",
            artifactDigest="sha256:test-artifact",
        )

    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)
    client = TestClient(app)
    records: list[dict] = []
    device = DeviceContext(
        deviceType=DEVICE_INFO["phoneType"],
        sysVersion=DEVICE_INFO["sysVer"],
        deviceName=DEVICE_INFO["deviceFormation"],
        romVersion="6.0",
        marketingName=DEVICE_INFO["phoneType"],
    )
    ids_state = IDSClient().get_device_capability_state(device, "ids-test-1")
    assert "com.huawei.hmos.weather" in ids_state.installed_apps

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        overview_request = _tool_payload(
            {"bundleName": "com.omega_w_0823.hmservice"},
            "1",
        )
        websocket.send_json(overview_request)
        overview_message = _receive_final_frame(websocket, _request_id("1"))
        overview_legacy_message = _assert_success_envelope(
            overview_message,
            "getWidgetCapabilityOverview",
            _request_id("1"),
        )
        overview = overview_legacy_message["data"]
        assert overview_legacy_message["status"] == "success"
        assert overview_legacy_message["errorCode"] == ""
        assert "apiVersion" not in overview
        assert "capabilityRegistryVersion" not in overview
        assert [item["id"] for item in overview["dataCapabilities"]] == [
            "ViewWeather",
            "GetCalendarEvents",
            "GetCountdownDays",
            "GetAppUsageDuration",
            "GetEarphoneInfo",
            "GetPhoneBatteryInfo",
            "GetHealthAndSportSummary",
            "GetSystemMemInfo",
        ]
        assert overview["unavailableCapabilities"] == []
        assert any(item["id"] == "event.open.weather" for item in overview["eventCapabilities"])
        assert any(item["id"] == "asset.drop_1" for item in overview["assetCandidates"])
        assert "taskSpec" not in overview
        assert "task_spec" not in overview
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
        schema_message = _receive_final_frame(websocket, _request_id("2"))
        schema_legacy_message = _assert_success_envelope(
            schema_message,
            "getDataCapabilitySchemas",
            _request_id("2"),
        )
        schema = schema_legacy_message["data"]
        assert schema_legacy_message["status"] == "success"
        assert schema_legacy_message["errorCode"] == ""
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        weather_schema = schema["dataCapabilities"][0]
        assert "districtName" in weather_schema["inputSchema"]["properties"]
        assert weather_schema["outputSchema"]["properties"]["current"]["properties"][
            "condition"
        ]["sampleValue"] == "多云"
        assert weather_schema["dependencies"] == {
            "requiredPackages": [
                {"packageName": "com.huawei.hmos.weather"}
            ]
        }
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

    candidate_payload = {
        "candidateDataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {"districtName": "上海", "forecastDays": 1},
                "writeResultTo": "/data/weather",
                "candidateOutputFields": [
                    "/location/districtName",
                    "/current/temperatureText",
                    "/current/condition",
                    "/current/airQuality",
                    "/updatedAt",
                ],
            }
        ],
        "candidateEventCandidates": [
            {
                "capabilityId": "event.open.weather",
                "action": {
                    "call": "clickToDeeplink",
                    "args": {
                        "intentName": "Weather_CityCode",
                        "bundleName": "",
                        "abilityName": "",
                        "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
                    },
                },
            }
        ],
        "candidateAssetIds": ["asset.drop_1"],
    }

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        generate_request = _tool_payload(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "userQuery": "帮我做通勤卡片，包含天气",
                "size": "2x4",
                "title": "通勤日常",
                "description": "天气速览",
                **candidate_payload,
            },
            "3",
            "帮我做通勤卡片，包含天气",
        )
        websocket.send_json(generate_request)
        generate_message = _receive_final_frame(websocket, _request_id("3"))
        generate_legacy_message = _assert_success_envelope(
            generate_message,
            "generateWidgetCard",
            _request_id("3"),
        )
        generated = generate_legacy_message["data"]
        assert generate_legacy_message["status"] == "success"
        assert generate_legacy_message["errorCode"] == ""
        assert generated["status"] == "success"
        assert generated["artifactUrl"] == "https://test.invalid/widget/artifact.md"
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]
        assert "artifact" not in generated
        assert len(saved_artifacts) == 1
        task_spec = saved_artifacts[0]["taskSpec"]
        assert set(task_spec) == {
            "userQuery",
            "size",
            "eventCandidates",
            "dataModelSchema",
            "assetCandidates",
        }
        assert task_spec["dataModelSchema"]["data"]["weather"]["current"][
            "temperatureText"
        ]["sampleValue"] == "26℃"
        card_binding = saved_artifacts[0]["cardSpec"]["dataBindings"][0]
        assert set(card_binding) == {"capabilityId", "arguments", "writeResultTo"}
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


def test_overview_interface_filters_health_dependencies(monkeypatch):
    monkeypatch.setattr(
        IDSClient,
        "get_device_capability_state",
        lambda _self, _device, _request_id: IDSDeviceCapabilityState(
            installed_apps={"com.huawei.hmos.weather"}
        ),
    )
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/ws/tools/getWidgetCapabilityOverview"
    ) as websocket:
        websocket.send_json(
            _tool_payload(
                {},
                "overview-health",
            )
        )
        message = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("overview-health")),
            "getWidgetCapabilityOverview",
            _request_id("overview-health"),
        )

    data = message["data"]
    assert "ViewWeather" in {item["id"] for item in data["dataCapabilities"]}
    assert "GetCalendarEvents" in {item["id"] for item in data["dataCapabilities"]}
    assert "GetHealthAndSportSummary" not in {
        item["id"] for item in data["dataCapabilities"]
    }
    assert set(data["unavailableCapabilities"]) == {
        "GetHealthAndSportSummary",
        "event.open.health.sport",
        "event.open.health.sleep",
    }


def test_overview_logs_do_not_include_user_or_device_identifiers(monkeypatch):
    sentinel_uid = "private-user-uid-must-not-be-logged"
    log_messages: list[str] = []

    class CapturedLogger:
        def _capture(self, message, *_args, **_kwargs):
            log_messages.append(str(message))

        info = _capture
        warning = _capture
        error = _capture

    captured_logger = CapturedLogger()
    monkeypatch.setattr(importlib.import_module("api.routes"), "logger", captured_logger)
    monkeypatch.setattr(
        importlib.import_module("services.widget_generation_service"),
        "logger",
        captured_logger,
    )
    monkeypatch.setattr(
        IDSClient,
        "get_device_capability_state",
        lambda _self, _device, _request_id: IDSDeviceCapabilityState(
            installed_apps={"com.huawei.hmos.health.core"}
        ),
    )
    request = _tool_payload({}, "overview-log-uid")
    request["userAuth"]["user"]["userId"] = sentinel_uid
    request["content"]["sourceArtifactUrl"] = (
        "https://obs.test/widget/source-artifact.md"
    )

    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/ws/tools/getWidgetCapabilityOverview"
    ) as websocket:
        websocket.send_json(request)
        _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("overview-log-uid")),
            "getWidgetCapabilityOverview",
            _request_id("overview-log-uid"),
        )

    assert any("widget_operation_ws_payload_received" in item for item in log_messages)
    assert any(
        "payload_keys=" in item and '"content"' in item for item in log_messages
    )
    raw_request_log = next(
        item
        for item in log_messages
        if "widget_operation_ws_raw_request_received" in item
    )
    logged_request = json.loads(raw_request_log.split("request_body=", 1)[1])
    assert logged_request["deviceInfo"]["romVersion"] == ROM_VERSION
    assert logged_request["bundleName"] == request["bundleName"]
    assert "odid" not in logged_request["content"]
    assert logged_request["content"]["sourceArtifactUrl"] == (
        request["content"]["sourceArtifactUrl"]
    )
    assert "userId" not in logged_request["userAuth"]["user"]
    assert any("capability_overview_started" in item for item in log_messages)
    joined_logs = "\n".join(log_messages)
    assert sentinel_uid not in joined_logs
    assert DEVICE_ODID not in joined_logs
    assert all(" uid=" not in item for item in log_messages)


def test_overview_interface_does_not_filter_assets_by_app_version():
    client = TestClient(app)
    device_info = {**DEVICE_INFO, "prdVer": "0.9.0"}
    with client.websocket_connect(
        "/api/v1/ws/tools/getWidgetCapabilityOverview"
    ) as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "capabilityRegistryVersion": REGISTRY_VERSION,
                },
                "overview-asset-version",
                device_info=device_info,
            )
        )
        message = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("overview-asset-version")),
            "getWidgetCapabilityOverview",
            _request_id("overview-asset-version"),
        )

    data = message["data"]
    assert "asset.drop_1" in {item["id"] for item in data["assetCandidates"]}
    assert "asset.drop_1" not in data["unavailableCapabilities"]


def test_generation_routes_lock_and_isolate_protocol_profiles(monkeypatch):
    """验证第三接口走 MEP，第四接口走 llmclient 并转换为版本化标准 A2UI。"""
    model_calls = []

    def capture_model_call(client, prompt, protocol_profile):
        model_calls.append(
            {
                "backend": client.backend,
                "prompt": prompt,
                "protocolProfile": protocol_profile,
            }
        )
        return _valid_model_output(client, prompt, protocol_profile)

    monkeypatch.setattr(A2UIModelClient, "generate", capture_model_call)
    saved_artifacts = []

    def capture_artifact(_store, artifact):
        saved_artifacts.append(artifact.model_dump(mode="json", exclude_none=True))
        return ArtifactSaveResult(
            artifactUrl=f"https://test.invalid/widget/artifact-{len(saved_artifacts)}.json",
            artifactDigest=f"sha256:test-{len(saved_artifacts)}",
        )

    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)
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
            _receive_final_frame(websocket, _request_id("profile-old")),
            "generateWidgetCard",
            _request_id("profile-old"),
        )

    assert "artifact" not in old_message["data"]
    old_artifact = saved_artifacts[0]
    old_rows = [json.loads(line) for line in old_artifact["genui"].splitlines()]
    assert old_artifact["meta"]["protocolProfileId"] == "a2ui-form-rom6.0-v1"
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
            "protocolProfileId": "a2ui-form-rom6.0-v1",
        }
        compact_content.pop("userQuery")
        compact_request = _tool_payload(
            compact_content,
            "profile-compact",
            original="生成一张静态天气卡片",
        )
        websocket.send_json(compact_request)
        compact_message = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("profile-compact")),
            "generateWidgetCardCompactDsl",
            _request_id("profile-compact"),
        )

    assert "artifact" not in compact_message["data"]
    compact_artifact = saved_artifacts[1]
    compact_rows = [
        json.loads(line) for line in compact_artifact["genui"].splitlines()
    ]
    assert compact_artifact["meta"]["protocolProfileId"] == "a2ui-form-rom6.0-v1"
    assert [next(iter(row)) for row in compact_rows] == ["version", "version", "version"]
    assert "createSurface" in compact_rows[0]
    assert "updateComponents" in compact_rows[1]
    assert "updateDataModel" in compact_rows[2]
    assert [item["backend"] for item in model_calls] == ["mep", "llmclient"]
    assert model_calls[1]["protocolProfile"] == {
        "id": "design-compact-dsl",
        "format": "compact-dsl",
    }
    design_prompt = (
        CLOUD_ROOT / "data" / "protocol_profiles" / "design-compact-dsl" / "PROMPT.md"
    ).read_text(encoding="utf-8")
    assert model_calls[1]["prompt"][0]["content"] == design_prompt


def test_compact_route_mock_converts_design_dsl_before_saving(monkeypatch):
    """验证第四接口真实走 A2UI 客户端 mock、转换器和标准 artifact 保存链路。"""
    monkeypatch.setattr(get_settings(), "enable_a2ui_model_mock", True)
    saved_artifacts = []

    def capture_artifact(_store, artifact):
        saved_artifacts.append(artifact.model_dump(mode="json", exclude_none=True))
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/widget/design-mock.json",
            artifactDigest="sha256:design-mock",
        )

    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)
    client = TestClient(app)
    request_id = _request_id("design-mock")
    with client.websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "userQuery": "生成静态卡片",
                    "size": "2x4",
                    "title": "静态卡片",
                    "description": "Design Mock 转换",
                    "candidateDataBindings": [],
                    "candidateEventCandidates": [],
                    "candidateAssetIds": [],
                },
                "design-mock",
            )
        )
        message = _assert_success_envelope(
            _receive_final_frame(websocket, request_id),
            "generateWidgetCardCompactDsl",
            request_id,
        )

    assert message["data"]["status"] == "success"
    assert len(saved_artifacts) == 1
    artifact = saved_artifacts[0]
    rows = [json.loads(line) for line in artifact["genui"].splitlines()]
    assert artifact["meta"]["protocolProfileId"] == "a2ui-form-rom6.0-v1"
    assert rows[0]["createSurface"]["width"] == 300
    assert rows[1]["updateComponents"]["root"] == "root"
    assert rows[2]["updateDataModel"]["value"]["ui"]["state"] == "ready"


def test_unknown_prd_version_falls_back_for_first_two_interfaces():
    """验证第一、第二接口默认回退到 205/6.0 注册表。"""
    client = TestClient(app)
    random_prd_ver = f"99.99.{uuid.uuid4().int % 100000000}"
    random_capability_id = f"MissingCapability.{uuid.uuid4().hex[:8]}"
    device_info = {**DEVICE_INFO, "prdVer": random_prd_ver}

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_json(
            _tool_payload(
                {"bundleName": "com.omega_w_0823.hmservice"},
                "missing-overview",
                device_info=device_info,
            )
        )
        overview_message = _receive_final_frame(
            websocket, _request_id("missing-overview")
        )

        overview_legacy_message = _assert_success_envelope(
            overview_message,
            "getWidgetCapabilityOverview",
            _request_id("missing-overview"),
        )
        overview = overview_legacy_message["data"]
        assert overview_legacy_message["status"] == "success"
        assert overview_legacy_message["errorCode"] == ""
        assert "apiVersion" not in overview
        assert "capabilityRegistryVersion" not in overview
        assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])
        assert overview["eventCapabilities"]
        assert overview["assetCandidates"]

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "bundleName": "com.omega_w_0823.hmservice",
                    "dataCapabilityIds": ["ViewWeather", random_capability_id],
                },
                "missing-schema",
                device_info=device_info,
            )
        )
        schema_message = _receive_final_frame(websocket, _request_id("missing-schema"))

        schema_legacy_message = _assert_success_envelope(
            schema_message,
            "getDataCapabilitySchemas",
            _request_id("missing-schema"),
        )
        schema = schema_legacy_message["data"]
        assert schema_legacy_message["status"] == "success"
        assert schema_legacy_message["errorCode"] == ""
        assert schema["capabilityRegistryVersion"] == REGISTRY_VERSION
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert schema["missingCapabilityIds"] == [random_capability_id]


def test_invalid_arguments_keep_plugin_envelope_successful():
    """参数异常放入 streamContent，插件顶层仍返回成功。"""
    client = TestClient(app)
    request_id = _request_id("invalid-create")
    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "userQuery": "缺少创建模式标题和说明",
                    "candidateDataBindings": [],
                },
                "invalid-create",
            )
        )
        response = websocket.receive_json()

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    assert response["reply"]["items"] == []
    stream_info = response["reply"]["streamInfo"]
    assert stream_info["streamingTextId"] == request_id
    assert stream_info["streamType"] == "final"
    legacy_message = parse_legacy_stream_content(
        stream_info["streamContent"]
    )
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    assert legacy_message["explanation"].startswith("工具参数传入有误")
    assert legacy_message["explanation"].endswith("报错信息如下")
    assert legacy_message["error"]["details"]


def test_malformed_json_keeps_plugin_envelope_successful():
    """JSON 语法异常同样通过 streamContent 返回，不中断插件协议。"""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_text("{invalid-json")
        response = websocket.receive_json()

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    assert response["reply"]["items"] == []
    legacy_message = parse_legacy_stream_content(
        response["reply"]["streamInfo"]["streamContent"]
    )
    assert legacy_message["type"] == "error"
    assert legacy_message["requestId"] is None
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    assert legacy_message["explanation"].startswith("工具参数传入有误")


def test_handler_exception_keeps_plugin_envelope_successful(monkeypatch):
    """服务执行异常保留插件顶层成功，并在旧消息中返回 FAILED。"""
    def fail_overview(_service, _request):
        raise RuntimeError("overview failed")

    monkeypatch.setattr(
        WidgetGenerationService,
        "get_widget_capability_overview",
        fail_overview,
    )
    client = TestClient(app)
    request_id = _request_id("handler-failed")
    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_json(_tool_payload({}, "handler-failed"))
        response = _receive_final_frame(websocket, request_id)

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    legacy_message = parse_legacy_stream_content(
        response["reply"]["streamInfo"]["streamContent"]
    )
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "FAILED"
    assert "未分类的服务异常" in legacy_message["explanation"]
    assert legacy_message["error"]["message"] == "overview failed"


def test_legacy_registry_field_is_ignored_for_first_two_interfaces():
    """验证旧字段不能覆盖 App/ROM 区间选择结果。"""
    client = TestClient(app)
    unknown_version = f"missing-{uuid.uuid4().hex}"

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_json(
            _tool_payload(
                {"capabilityRegistryVersion": unknown_version},
                "explicit-fallback-overview",
            )
        )
        overview = _assert_success_envelope(
            _receive_final_frame(
                websocket, _request_id("explicit-fallback-overview")
            ),
            "getWidgetCapabilityOverview",
            _request_id("explicit-fallback-overview"),
        )["data"]

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "capabilityRegistryVersion": unknown_version,
                    "dataCapabilityIds": ["ViewWeather"],
                },
                "explicit-fallback-schema",
            )
        )
        schema = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("explicit-fallback-schema")),
            "getDataCapabilitySchemas",
            _request_id("explicit-fallback-schema"),
        )["data"]

    assert "apiVersion" not in overview
    assert "capabilityRegistryVersion" not in overview
    assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])
    assert schema["capabilityRegistryVersion"] == REGISTRY_VERSION
    assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]


def test_registry_fallback_switch_defaults_to_enabled():
    assert Settings.model_fields[
        "enable_default_capability_registry_fallback"
    ].default is True


def test_protocol_fallback_switch_defaults_to_enabled():
    assert Settings.model_fields[
        "enable_default_protocol_profile_fallback"
    ].default is True


def test_compact_protocol_fallback_switch_off_returns_unsupported(monkeypatch):
    """验证第四接口协议区间未命中且关闭回退时不调用模型。"""
    monkeypatch.setattr(
        get_settings(),
        "enable_default_protocol_profile_fallback",
        False,
    )
    monkeypatch.setattr(
        A2UIModelClient,
        "generate",
        lambda *_args: (_ for _ in ()).throw(AssertionError("model must not be called")),
    )
    client = TestClient(app)
    device_info = {**DEVICE_INFO, "prdVer": "98.0.0.0"}
    request_id = _request_id("protocol-fallback-off")
    with client.websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "userQuery": "生成静态卡片",
                    "size": "2x4",
                    "title": "静态卡片",
                    "description": "协议回退关闭测试",
                    "candidateDataBindings": [],
                    "candidateEventCandidates": [],
                    "candidateAssetIds": [],
                },
                "protocol-fallback-off",
                device_info=device_info,
            )
        )
        message = _assert_success_envelope(
            _receive_final_frame(websocket, request_id),
            "generateWidgetCardCompactDsl",
            request_id,
        )

    assert message["data"]["status"] == "unsupported"
    assert message["data"]["errorCode"] == "APP_VERSION_UNSUPPORTED"
    assert "App 或 ROM 版本不在服务支持范围内" in message["explanation"]


def test_registry_fallback_switch_off_applies_to_all_three_interfaces(monkeypatch):
    """验证关闭开关后三个接口都不再回退。"""
    monkeypatch.setattr(
        get_settings(),
        "enable_default_capability_registry_fallback",
        False,
    )
    client = TestClient(app)
    random_prd_ver = f"98.98.{uuid.uuid4().int % 100000000}"
    expected_version = f"app-{random_prd_ver}_rom-6.0"
    device_info = {**DEVICE_INFO, "prdVer": random_prd_ver}

    with client.websocket_connect("/api/v1/ws/tools/getWidgetCapabilityOverview") as websocket:
        websocket.send_json(
            _tool_payload({}, "fallback-off-overview", device_info=device_info)
        )
        overview = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("fallback-off-overview")),
            "getWidgetCapabilityOverview",
            _request_id("fallback-off-overview"),
        )["data"]

    with client.websocket_connect("/api/v1/ws/tools/getDataCapabilitySchemas") as websocket:
        websocket.send_json(
            _tool_payload(
                {"dataCapabilityIds": ["ViewWeather"]},
                "fallback-off-schema",
                device_info=device_info,
            )
        )
        schema = _assert_success_envelope(
            _receive_final_frame(websocket, _request_id("fallback-off-schema")),
            "getDataCapabilitySchemas",
            _request_id("fallback-off-schema"),
        )["data"]

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "userQuery": "生成静态卡片",
                    "size": "2x4",
                    "title": "静态卡片",
                    "description": "关闭版本回退测试",
                    "candidateDataBindings": [],
                    "candidateEventCandidates": [],
                    "candidateAssetIds": [],
                },
                "fallback-off-generation",
                device_info=device_info,
            )
        )
        generation_message = _assert_success_envelope(
            _receive_final_frame(
                websocket,
                _request_id("fallback-off-generation"),
            ),
            "generateWidgetCard",
            _request_id("fallback-off-generation"),
        )
        generation = generation_message["data"]

    assert "apiVersion" not in overview
    assert "capabilityRegistryVersion" not in overview
    assert overview["dataCapabilities"] == []
    assert overview["eventCapabilities"] == []
    assert overview["assetCandidates"] == []
    assert schema["capabilityRegistryVersion"] == expected_version
    assert schema["dataCapabilities"] == []
    assert schema["missingCapabilityIds"] == ["ViewWeather"]
    assert generation["status"] == "unsupported"
    assert generation["errorCode"] == "APP_VERSION_UNSUPPORTED"
    assert "App 或 ROM 版本不在服务支持范围内" in generation_message["explanation"]


def test_third_interface_uses_default_registry_fallback():
    """验证生成接口未命中版本区间时也使用默认注册表。"""
    client = TestClient(app)
    unknown_version = f"missing-{uuid.uuid4().hex}"
    unknown_prd_ver = f"88.88.{uuid.uuid4().int % 100000}"
    device_info = {**DEVICE_INFO, "prdVer": unknown_prd_ver}
    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(
            _tool_payload(
                {
                    "capabilityRegistryVersion": unknown_version,
                    "userQuery": "生成静态卡片",
                    "size": "2x4",
                    "title": "静态卡片",
                    "description": "版本回退测试",
                    "candidateDataBindings": [],
                    "candidateEventCandidates": [],
                    "candidateAssetIds": [],
                },
                "third-default-fallback",
                device_info=device_info,
            )
        )
        response = _assert_success_envelope(
            _receive_final_frame(
                websocket,
                _request_id("third-default-fallback"),
            ),
            "generateWidgetCard",
            _request_id("third-default-fallback"),
        )["data"]

    assert response["status"] == "success"
    assert response["errorCode"] == ""
