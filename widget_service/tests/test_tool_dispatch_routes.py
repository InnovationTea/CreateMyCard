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
UNSUPPORTED_APP_VERSION = ".".join(("98", "0", "0", "0"))
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

app = importlib.import_module("start_websocket_server").app
A2UIModelClient = importlib.import_module("custom.a2ui_model_client").A2UIModelClient
A2UIModelGenerationError = importlib.import_module(
    "custom.a2ui_model_client"
).A2UIModelGenerationError
DeepSeekPlatformClient = importlib.import_module(
    "custom.deepseek_platform_client"
).DeepSeekPlatformClient
task_logger = importlib.import_module("app.logger").task_logger
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
compact_dsl_argument_issue_tracker = importlib.import_module(
    "services.compact_dsl_argument_repair"
).compact_dsl_argument_issue_tracker


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


def _receive_frames_until_final(websocket, expected_request_id: str) -> list[dict]:
    """读取同一请求的全部非心跳帧，直到 final。"""
    frames = []
    while True:
        message = websocket.receive_json()
        stream_info = message["reply"]["streamInfo"]
        assert stream_info["streamingTextId"] == expected_request_id
        if stream_info["streamType"] == "partial":
            continue
        frames.append(message)
        if stream_info["streamType"] == "final":
            return frames


def _command_envelope(frame: dict) -> dict:
    """解析 command 帧中的 command 消息 JSON。"""
    stream_info = frame["reply"]["streamInfo"]
    assert stream_info["streamType"] == "command"
    assert stream_info["textType"] == "command"
    assert frame["reply"]["items"] == []
    return json.loads(stream_info["streamContent"])


def _command_content(frame: dict) -> dict:
    """从 command 消息的 content 字符串解析完整指令 JSON。"""
    return json.loads(_command_envelope(frame)["content"])


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


def test_overview_interface_filters_default_package_whitelist(monkeypatch):
    monkeypatch.setattr(
        IDSClient,
        "get_device_capability_state",
        lambda _self, _device, _request_id: IDSDeviceCapabilityState(
            installed_apps={"com.huawei.hmsapp.totemweather"}
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
    assert "GetCalendarEvents" not in {
        item["id"] for item in data["dataCapabilities"]
    }
    assert "GetHealthAndSportSummary" not in {
        item["id"] for item in data["dataCapabilities"]
    }
    assert set(data["unavailableCapabilities"]) == {
        "GetCalendarEvents",
        "GetHealthAndSportSummary",
        "event.open.health.sport",
        "event.open.health.sleep",
    }


def test_schema_interface_treats_disabled_data_capability_as_missing():
    client = TestClient(app)
    with client.websocket_connect(
        "/api/v1/ws/tools/getDataCapabilitySchemas"
    ) as websocket:
        websocket.send_json(
            _tool_payload(
                {"dataCapabilityIds": ["GetAppUsageDuration"]},
                "disabled-schema",
            )
        )
        message = _assert_success_envelope(
            _receive_final_frame(
                websocket,
                _request_id("disabled-schema"),
            ),
            "getDataCapabilitySchemas",
            _request_id("disabled-schema"),
        )

    assert message["data"]["dataCapabilities"] == []
    assert message["data"]["missingCapabilityIds"] == [
        "GetAppUsageDuration"
    ]


def test_overview_logs_do_not_include_user_or_device_identifiers(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_sensitive_log_fields", False)
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
            installed_apps={"com.huawei.hmos.health"}
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
    assert "width" not in rows[0]["createSurface"]
    assert "height" not in rows[0]["createSurface"]
    assert rows[1]["updateComponents"]["root"] == "root"
    assert rows[2]["updateDataModel"]["value"]["ui"]["state"] == "ready"


def test_obsolete_compact_directive_route_is_not_registered():
    """已下线的临时生成接口不能继续出现在应用路由表。"""
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/ws/tools/generateWidgetCardCompactDslWithDirective" not in route_paths


def test_compact_route_rejects_stringified_tool_arguments(monkeypatch):
    """外层请求合法但 content.arguments 为字符串时应返回精确错误。"""
    def unexpected_generate(*_args, **_kwargs):
        raise AssertionError("malformed tool arguments must not call the model")

    monkeypatch.setattr(A2UIModelClient, "generate", unexpected_generate)
    interaction_id = "nested-tool-arguments"
    request_id = _request_id(interaction_id)
    content = {
        "skillName": "harmony-card-generation-online-directive",
        "functionName": "generateWidgetCardCompactDslWithDirective",
        "arguments": json.dumps(
            {
                "userQuery": "生成大理天气卡片",
                "title": "大理天气",
                "description": "大理天气关怀卡片",
            },
            ensure_ascii=False,
        ),
    }
    client = TestClient(app)
    request = _tool_payload(content, interaction_id)

    assert isinstance(request, dict)
    request_content = request.get("content")
    assert isinstance(request_content, dict)
    assert isinstance(request_content.get("arguments"), str)

    with client.websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(request)
        response = websocket.receive_json()

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    stream_info = response["reply"]["streamInfo"]
    assert stream_info["streamType"] == "final"
    assert stream_info["streamingTextId"] == request_id
    legacy_message = parse_legacy_stream_content(stream_info["streamContent"])
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    details = legacy_message["error"]["details"]
    assert details["stage"] == "requestEnvelope"
    assert details["modelCalled"] is False
    assert details["issues"][0]["path"] == "/content/arguments"
    assert details["issues"][0]["actualType"] == "string"
    assert "外层请求是合法 JSON" in details["agentInstruction"]
    assert "content 中出现多余" in details["agentInstruction"]


def test_compact_valid_request_breaks_stringified_argument_streak(monkeypatch):
    """同一 requestId 中间出现合法请求后，下一次异常重新从首次提醒计数。"""
    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "enable_compact_dsl_argument_repair_fallback",
        True,
    )
    monkeypatch.setattr(
        settings,
        "compact_dsl_argument_repair_reminder_count",
        1,
    )
    model_formats: list[str] = []

    async def generate_without_repair(_self, prompt, protocol_profile, **_kwargs):
        model_format = protocol_profile.get("format", "")
        model_formats.append(model_format)
        if model_format == "raw-json":
            raise AssertionError("a valid request must reset the malformed-input streak")
        return _valid_model_output(_self, prompt, protocol_profile)

    def capture_artifact(_store, _artifact):
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/widget/streak-reset.json",
            artifactDigest="sha256:streak-reset",
        )

    monkeypatch.setattr(A2UIModelClient, "generate", generate_without_repair)
    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)
    interaction_id = "argument-streak-reset"
    request_id = _request_id(interaction_id)
    valid_content = {
        "userQuery": "生成天气卡片",
        "title": "天气",
        "description": "天气卡片",
        "size": "2x2",
        "romVersion": "VYG-AL00 " + ".".join(("7", "0", "0", "105")),
    }
    malformed_content = {
        "arguments": json.dumps(valid_content, ensure_ascii=False),
        "romVersion": valid_content["romVersion"],
    }
    client = TestClient(app)
    compact_dsl_argument_issue_tracker.clear()
    try:
        with client.websocket_connect(
            "/api/v1/ws/tools/generateWidgetCardCompactDsl"
        ) as websocket:
            websocket.send_json(_tool_payload(malformed_content, interaction_id))
            first_response = websocket.receive_json()

            websocket.send_json(_tool_payload(valid_content, interaction_id))
            valid_response = _receive_final_frame(websocket, request_id)

            websocket.send_json(_tool_payload(malformed_content, interaction_id))
            third_response = websocket.receive_json()
    finally:
        compact_dsl_argument_issue_tracker.clear()

    first_message = parse_legacy_stream_content(
        first_response["reply"]["streamInfo"]["streamContent"]
    )
    _assert_success_envelope(
        valid_response,
        "generateWidgetCardCompactDsl",
        request_id,
    )
    third_message = parse_legacy_stream_content(
        third_response["reply"]["streamInfo"]["streamContent"]
    )
    assert first_message["error"]["details"]["modelCalled"] is False
    assert third_message["error"]["details"]["modelCalled"] is False
    assert model_formats == ["compact-dsl"]


def test_compact_route_keeps_transport_only_stringified_arguments_reminder(
    monkeypatch,
):
    """四个透传字段场景沿用纠错提示，不进入连续计数或模型兜底。"""
    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "enable_compact_dsl_argument_repair_fallback",
        True,
    )
    monkeypatch.setattr(
        settings,
        "compact_dsl_argument_repair_reminder_count",
        0,
    )

    def unexpected_generate(*_args, **_kwargs):
        raise AssertionError("transport-only content must not call the model")

    monkeypatch.setattr(A2UIModelClient, "generate", unexpected_generate)
    interaction_id = "inferred-stringified-tool-arguments"
    request_id = _request_id(interaction_id)
    content = {
        "uid": "tool-user",
        "romVersion": "NJL-AL20 6.0.0.105",
        "bundleName": "com.omega_w_0823.hmservice",
    }
    client = TestClient(app)
    request = _tool_payload(content, interaction_id)
    request_content = request.get("content")
    assert isinstance(request_content, dict)
    assert set(request_content) == {"uid", "odid", "romVersion", "bundleName"}
    compact_dsl_argument_issue_tracker.clear()
    try:
        with client.websocket_connect(
            "/api/v1/ws/tools/generateWidgetCardCompactDsl"
        ) as websocket:
            websocket.send_json(request)
            response = websocket.receive_json()
    finally:
        compact_dsl_argument_issue_tracker.clear()

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    stream_info = response["reply"]["streamInfo"]
    assert stream_info["streamType"] == "final"
    assert stream_info["streamingTextId"] == request_id
    legacy_message = parse_legacy_stream_content(stream_info["streamContent"])
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    details = legacy_message["error"]["details"]
    assert details["stage"] == "requestEnvelope"
    assert details["modelCalled"] is False
    assert details["issues"][0]["code"] == "STRINGIFIED_TOOL_ARGUMENTS"
    assert details["issues"][0]["path"] == "/arguments"
    assert details["issues"][0]["actualType"] == "string"
    assert "arguments 必须直接传合法的 JSON 对象" in details["agentInstruction"]
    assert "content" not in details["agentInstruction"]


def test_generation_model_error_sends_start_and_failure_commands(monkeypatch):
    """验证模型调用失败时已发送开始指令，并以失败结束指令收口。"""
    monkeypatch.setattr(get_settings(), "enable_widget_directive_commands", True)

    def fail_model_call(_self, _prompt, _protocol_profile):
        raise A2UIModelGenerationError("model unavailable")

    monkeypatch.setattr(A2UIModelClient, "generate", fail_model_call)
    client = TestClient(app)
    interaction_id = "directive-model-error"
    request_id = _request_id(interaction_id)
    request = _tool_payload(
        {
            "userQuery": "生成卡片",
            "size": "2x4",
            "title": "卡片",
            "description": "模型异常",
            "candidateDataBindings": [],
            "candidateEventCandidates": [],
            "candidateAssetIds": [],
        },
        interaction_id,
    )

    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(request)
        frames = _receive_frames_until_final(websocket, request_id)

    frame_types = [item["reply"]["streamInfo"]["streamType"] for item in frames]
    assert frame_types == ["start", "command", "command", "final"]
    start_command = _command_content(frames[1])
    failure_command = _command_content(frames[2])
    start_card_id = start_command["directives"][0]["payload"]["executeParam"]["cardId"]
    assert start_command["directives"][0]["payload"] == {
        "executeParam": {
            "intentName": "AIWidgetStart",
            "cardId": start_card_id,
            "size": "2x4",
        }
    }
    assert failure_command["directives"][0]["payload"] == {
        "executeParam": {
            "status": False,
            "intentName": "AIWidgetEnd",
            "cardId": start_card_id,
            "size": "2x4",
        }
    }


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
        assert "apiVersion" not in schema
        assert "capabilityRegistryVersion" not in schema
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert schema["missingCapabilityIds"] == [random_capability_id]


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
    assert "apiVersion" not in schema
    assert "capabilityRegistryVersion" not in schema
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
    device_info = {**DEVICE_INFO, "prdVer": UNSUPPORTED_APP_VERSION}
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
