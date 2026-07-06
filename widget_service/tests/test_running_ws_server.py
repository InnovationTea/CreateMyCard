# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402
import asyncio
import json
import os

import pytest
import requests
import websockets

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
WS_BASE_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")

TOOL_CONTEXT = {
    "uid": "live-test-user-001",
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


def _request_health_or_skip() -> requests.Response:
    """请求健康检查接口，服务未启动时跳过 live 测试。

    入参：无。
    出参：健康检查 HTTP 响应。
    """
    try:
        response = requests.get(f"{HTTP_BASE_URL}/health", timeout=2.0)
    except requests.RequestException:
        pytest.skip(
            "本测试需要先启动本地服务："
            "cd widget_service && py -3.12 cloud\\main.py；"
            f"当前探测地址：{HTTP_BASE_URL}/health"
        )
    return response


async def _call_ws(path_name: str, request_id: str, arguments: dict) -> dict:
    """调用一个真实 WebSocket path。

    入参：
    - path_name：WS path 最后一段，例如 getWidgetCapabilityOverview。
    - request_id：测试请求 ID。
    - arguments：业务入参，会放入 WebSocket 消息的 arguments 字段。
    出参：服务端返回的 result 消息。
    """
    uri = f"{WS_BASE_URL}{WS_BASE_PATH}/{path_name}"
    async with websockets.connect(uri, open_timeout=2.0) as websocket:
        ready = json.loads(await websocket.recv())
        assert ready["type"] == "ready"
        assert ready["tool"] == path_name

        await websocket.send(
            json.dumps(
                {
                    "requestId": request_id,
                    "arguments": arguments,
                },
                ensure_ascii=False,
            )
        )
        message = json.loads(await websocket.recv())
        assert message["type"] == "result"
        assert message["tool"] == path_name
        assert message["operation"] == path_name
        assert message["requestId"] == request_id
        return message


def test_live_health_endpoint():
    """验证本地已启动 FastAPI 服务的健康检查接口。

    入参：无。
    出参：无；通过断言验证真实 HTTP `/health` 返回存活状态。
    """
    response = _request_health_or_skip()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_live_three_websocket_paths_complete_flow():
    """验证本地已启动服务上的三个真实 WebSocket 入口。

    入参：无。
    出参：无；通过断言验证能力概述、schema 加载和生成接口的真实 WS 链路。
    """
    _request_health_or_skip()

    async def scenario() -> None:
        """执行真实 WebSocket 三段调用流程。

        入参：无。
        出参：无；断言每个业务响应符合预期。
        """
        overview_message = await _call_ws(
            "getWidgetCapabilityOverview",
            "live-overview-1",
            TOOL_CONTEXT,
        )
        overview = overview_message["data"]
        assert overview["capabilityRegistryVersion"] == "ohos-36_rom-7.0.0"
        assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])

        schema_message = await _call_ws(
            "getDataCapabilitySchemas",
            "live-schema-1",
            {
                **TOOL_CONTEXT,
                "dataCapabilityIds": ["ViewWeather"],
            },
        )
        schema = schema_message["data"]
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert schema["missingCapabilityIds"] == []

        generate_message = await _call_ws(
            "generateWidgetCard",
            "live-generate-1",
            {
                **TOOL_CONTEXT,
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
        )
        generated = generate_message["data"]
        assert generated["status"] == "success"
        assert generated["artifactUrl"]
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]

    asyncio.run(scenario())
