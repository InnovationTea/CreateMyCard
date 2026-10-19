"""工具结果使用 JSON 字符串，多层封装不得改变业务文本或数据类型。"""

import json

import pytest
from starlette.websockets import WebSocket

from api.routes import _build_plugin_stream_response, _send_websocket_json
from api.schemas import CapabilityOverviewRequest
from models.service import WidgetWebSocketErrorMessage, WidgetWebSocketResultMessage
from services.ids_client import IDSClient, IDSDeviceCapabilityState
from services.widget_generation_service import WidgetGenerationService
from ws_response_parser import parse_legacy_stream_content

OPERATIONS = [
    "getWidgetCapabilityOverview",
    "getDataCapabilitySchemas",
    "generateWidgetCard",
    "generateWidgetCardCompactDsl",
    "generateWidgetCardTerseDslNested2",
]


def _message(operation="getWidgetCapabilityOverview", request_id="session&9"):
    return WidgetWebSocketResultMessage(
        tool=operation,
        operation=operation,
        requestId=request_id,
        data={
            "description": """中文'单引号'和"双引号"，换行\n制表\t表情😀""",
            "literalEscape": r"\u4e2d",
            "backslashes": r'C:\data\file and \"--\"',
            "expression": "{{ 'app://weather?a=1&city=' + ${/data/weather/city} }}",
            "empty": "",
            "nested": {"enabled": True, "disabled": False, "value": None, "number": 1.5},
            "array": [0, None, "中文", {"key": "value"}],
        },
    )


def _html_safe_json(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    for character in "'=&<>":
        encoded = encoded.replace(character, f"\\u{ord(character):04x}")
    return encoded


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("request_id", [None, "session&9"])
def test_success_is_complete_json_without_changing_envelope(operation, request_id):
    message = _message(operation, request_id)
    before = message.model_copy(deep=True)
    response = _build_plugin_stream_response(message, "explicit-stream-id")
    stream = response.reply.streamInfo
    assert json.loads(stream.streamContent) == message.model_dump(mode="json")
    assert "中文" in stream.streamContent
    assert "😀" in stream.streamContent
    assert not stream.streamContent.startswith("type=")
    assert stream.streamingTextId == "explicit-stream-id"
    assert stream.streamType == "final"
    assert stream.textType == "plainText"
    assert response.errorCode == "0"
    assert response.errorMessage == ""
    assert response.reply.items == []
    assert message == before


@pytest.mark.parametrize("html_safe", [True, False])
@pytest.mark.asyncio
async def test_actual_websocket_and_two_more_json_layers_preserve_content(html_safe):
    message = _message()
    response = _build_plugin_stream_response(message)
    frames = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(frame):
        frames.append(frame)

    websocket = WebSocket({"type": "websocket"}, receive, send)
    await websocket.accept()
    assert await _send_websocket_json(
        websocket, response.model_dump(mode="json"), message.operation, message.requestId, "final"
    )
    wire = frames[-1].get("text")
    assert isinstance(wire, str)
    assert "中文" in wire
    received = json.loads(wire)
    reply = received.get("reply")
    assert isinstance(reply, dict)
    response_text = json.dumps(reply, ensure_ascii=False, separators=(",", ":"))
    outer = {"responseText": response_text, "resultDataList": []}
    encoded = _html_safe_json(outer) if html_safe else json.dumps(outer, ensure_ascii=False)
    decoded_outer = json.loads(encoded)
    decoded_reply = json.loads(decoded_outer.get("responseText"))
    stream_info = decoded_reply.get("streamInfo")
    assert isinstance(stream_info, dict)
    content = stream_info.get("streamContent")
    assert isinstance(content, str)
    assert json.loads(content) == message.model_dump(mode="json")


@pytest.mark.parametrize("stage", [None, "argumentRepair"])
def test_error_keeps_explanation_details_and_json_body(stage):
    details = {"stage": stage, "retryable": False}
    message = WidgetWebSocketErrorMessage(
        operation="generateWidgetCardCompactDsl",
        errorCode="INVALID_ARGUMENTS",
        error={"message": "参数'不合法'", "details": details},
    )
    response = _build_plugin_stream_response(message)
    content = response.reply.streamInfo.streamContent
    explanation, separator, body = content.partition("：")
    assert separator
    assert explanation
    if stage == "argumentRepair":
        assert "停止本轮自动调用" in explanation
    assert json.loads(body) == message.model_dump(mode="json")
    parsed = parse_legacy_stream_content(content)
    assert parsed.get("explanation") == explanation
    assert parsed.get("error") == message.error


def test_real_overview_keeps_every_field_and_reduces_html_safe_expansion(monkeypatch):
    def installed_state(_client, _device, _request_id):
        return IDSDeviceCapabilityState(
            installed_apps={
                "com.huawei.hmos.weather",
                "com.huawei.hmos.health",
                "com.huawei.hmos.calendar",
            }
        )

    monkeypatch.setattr(IDSClient, "get_device_capability_state", installed_state)
    result = WidgetGenerationService().get_widget_capability_overview(
        CapabilityOverviewRequest(
            uid="test-user", prdVer="11.7.7.330", device={"romVersion": "7.0"}
        )
    )
    message = WidgetWebSocketResultMessage(
        tool="getWidgetCapabilityOverview", operation="getWidgetCapabilityOverview",
        requestId="test&9", data=result.model_dump(mode="json"),
    )
    response = _build_plugin_stream_response(message)
    current = response.reply.streamInfo.streamContent
    assert json.loads(current) == message.model_dump(mode="json")
    assert result.dataCapabilities
    assert result.assetCandidates
    lengths = []
    for content in (str(message), current):
        reply = {"items": [], "streamInfo": {"streamContent": content}}
        outer = {"responseText": json.dumps(reply, ensure_ascii=False, separators=(",", ":"))}
        lengths.append(len(_html_safe_json(outer)))
    assert lengths[1] < lengths[0]


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("prefix", ["", "参数错误："])
def test_test_client_parser_accepts_old_and_new_records(legacy, prefix):
    message = _message()
    text = str(message) if legacy else message.model_dump_json()
    parsed = parse_legacy_stream_content(prefix + text)
    assert parsed.pop("explanation") == prefix.removesuffix("：")
    assert parsed == message.model_dump(mode="json")


def test_parser_does_not_reinterpret_truncated_json_as_legacy_text():
    with pytest.raises(json.JSONDecodeError):
        parse_legacy_stream_content('{"type":"result","data":')
