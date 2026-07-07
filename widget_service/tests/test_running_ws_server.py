# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402
import asyncio
import json
import os

import pytest
import websockets

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
WS_BASE_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")

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


def _tool_payload(content: dict, interaction_id: str, original: str = "") -> dict:
    """构造新协议 WebSocket 请求包络。

    入参：
    - content：业务入参，对应旧协议 arguments。
    - interaction_id：当前交互 ID，会和 sessionId 拼接成 requestId。
    - original：用户原始表达。
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
        "userAuth": {"user": {"userId": "live-test-user-001"}},
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


async def _call_ws(path_name: str, payload: dict, expected_request_id: str) -> dict:
    """调用一个真实 WebSocket path。

    入参：
    - path_name：WS path 最后一段，例如 getWidgetCapabilityOverview。
    - payload：新协议 WebSocket 请求包络。
    - expected_request_id：服务端应返回的 requestId。
    出参：服务端返回的 result 消息。
    """
    uri = f"{WS_BASE_URL}{WS_BASE_PATH}/{path_name}"
    try:
        async with websockets.connect(uri, open_timeout=2.0) as websocket:
            ready = json.loads(await websocket.recv())
            assert ready["type"] == "ready"
            assert ready["tool"] == path_name

            await websocket.send(json.dumps(payload, ensure_ascii=False))
            message = json.loads(await websocket.recv())
            assert message["type"] == "result"
            assert message["tool"] == path_name
            assert message["operation"] == path_name
            assert message["requestId"] == expected_request_id
            return message
    except (OSError, TimeoutError):
        pytest.skip(
            "本测试需要先启动本地 WebSocket 服务："
            "cd widget_service && py -3.12 cloud\\main.py；"
            f"当前探测地址：{uri}"
        )


def test_live_three_websocket_paths_complete_flow():
    """验证本地已启动服务上的三个真实 WebSocket 入口。

    入参：无。
    出参：无；通过断言验证能力概述、schema 加载和生成接口的真实 WS 链路。
    """
    async def scenario() -> None:
        """执行真实 WebSocket 三段调用流程。

        入参：无。
        出参：无；断言每个业务响应符合预期。
        """
        overview_message = await _call_ws(
            "getWidgetCapabilityOverview",
            _tool_payload({"bundleName": "com.omega_w_0823.hmservice"}, "1"),
            _request_id("1"),
        )
        overview = overview_message["data"]
        assert overview["capabilityRegistryVersion"] == "ohos-36_rom-7.0.0"
        assert any(item["id"] == "ViewWeather" for item in overview["dataCapabilities"])

        schema_message = await _call_ws(
            "getDataCapabilitySchemas",
            _tool_payload(
                {
                    "bundleName": "com.omega_w_0823.hmservice",
                    "dataCapabilityIds": ["ViewWeather"],
                },
                "2",
            ),
            _request_id("2"),
        )
        schema = schema_message["data"]
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert schema["missingCapabilityIds"] == []

        generate_message = await _call_ws(
            "generateWidgetCard",
            _tool_payload(
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
            ),
            _request_id("3"),
        )
        generated = generate_message["data"]
        assert generated["status"] == "success"
        assert generated["artifactUrl"]
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]

    asyncio.run(scenario())
