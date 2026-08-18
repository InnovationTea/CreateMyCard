# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import pytest
import websockets

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from services.card_validation import ValidationOptions, validate_card
from services.source_artifact_repository import SourceArtifactRepository
from ws_response_parser import parse_legacy_stream_content

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", socket.gethostbyname("localhost"))
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
WS_BASE_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))

SESSION_ID = "7676c2c8-a6d3-413c-8074-c62ed30db8de"
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"
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


def _tool_payload(content: dict, interaction_id: str, original: str = "") -> dict:
    """构造新协议 WebSocket 请求包络。

    入参：
    - content：业务入参，对应旧协议 arguments。
    - interaction_id：当前交互 ID，会和 sessionId 拼接成 requestId。
    - original：用户原始表达。
    出参：完整 WebSocket 请求字典。
    """
    return {
        "content": {"odid": DEVICE_ODID, **content},
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


def _validate_saved_artifact(artifact_url: str):
    """通过服务内 API 重新校验本地服务保存的 artifact，并打印完整诊断。"""
    artifact = SourceArtifactRepository().load(artifact_url).artifact
    capabilities_dir = (
        CLOUD_ROOT
        / "data"
        / "capabilities"
        / artifact.meta.capabilityRegistryVersion
    )
    reporter = validate_card(
        artifact=artifact.model_dump(mode="json", exclude_none=True),
        options=ValidationOptions(capabilities_dir=capabilities_dir),
    )
    print("\n===== 本地 artifact 校验报告 =====", flush=True)
    print(reporter.render_text(), flush=True)
    print("===== 校验报告结束 =====\n", flush=True)
    return reporter


async def _call_ws(path_name: str, payload: dict, expected_request_id: str) -> dict:
    """调用一个真实 WebSocket path。

    入参：
    - path_name：WS path 最后一段，例如 getWidgetCapabilityOverview。
    - payload：新协议 WebSocket 请求包络。
    - expected_request_id：服务端应返回的 requestId。
    出参：从 final streamContent 解析出的当前完整旧出参。
    """
    uri = f"{WS_BASE_URL}{WS_BASE_PATH}/{path_name}"
    try:
        async with websockets.connect(uri, open_timeout=2.0) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            start_received = False
            while True:
                message = json.loads(await websocket.recv())
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
                break
            print(
                f"[{path_name}] final response received request_id={expected_request_id}",
                flush=True,
            )
            assert message["errorCode"] == "0"
            assert message["errorMessage"] == ""
            stream_info = message["reply"]["streamInfo"]
            assert stream_info["streamingTextId"] == expected_request_id
            assert stream_info["streamType"] == "final"
            assert stream_info["textType"] == "plainText"
            assert message["reply"]["items"] == []
            legacy_message = parse_legacy_stream_content(stream_info["streamContent"])
            assert legacy_message["type"] == "result"
            assert legacy_message["tool"] == path_name
            assert legacy_message["operation"] == path_name
            assert legacy_message["requestId"] == expected_request_id
            assert "data" in legacy_message
            assert "status" in legacy_message
            assert "errorCode" in legacy_message
            assert "error" in legacy_message
            assert legacy_message["error"] == {}
            return legacy_message
    except OSError as exc:
        reason = (
            "本测试需要先启动本地 WebSocket 服务："
            "cd widget_service && py -3.12 cloud\\start_websocket_server.py；"
            f"当前探测地址：{uri}；"
            f"连接错误：{type(exc).__name__}: {exc}"
        )
        pytest.skip(reason)


def test_live_four_websocket_paths_complete_flow():
    """验证本地已启动服务上的三个正式 WebSocket 入口。

    入参：无。
    出参：无；验证概述、schema、可用性校验和生成接口的真实 WS 链路。
    """
    async def scenario() -> None:
        """执行真实 WebSocket 四段调用流程。

        入参：无。
        出参：无；断言每个业务响应符合预期。
        """
        overview_message = await _call_ws(
            "getWidgetCapabilityOverview",
            _tool_payload({"bundleName": "com.omega_w_0823.hmservice"}, "1"),
            _request_id("1"),
        )
        overview = overview_message["data"]
        assert overview_message["status"] == "success"
        assert overview_message["errorCode"] == ""
        assert "apiVersion" not in overview
        assert "capabilityRegistryVersion" not in overview
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
        assert schema_message["status"] == "success"
        assert schema_message["errorCode"] == ""
        assert [item["id"] for item in schema["dataCapabilities"]] == ["ViewWeather"]
        assert schema["missingCapabilityIds"] == []

        candidate_payload = {
            "candidateDataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "arguments": {"prefectureName": "上海市", "forecastDays": 1},
                    "writeResultTo": "/data/weather",
                    "candidateOutputFields": [
                        "/location/districtName",
                        "/current/temperatureText",
                        "/current/condition",
                        "/current/airQuality",
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
                            "uri": (
                                "{{ 'hww://www.huawei.com/totemweather?"
                                "enterType=share&cityCode=' "
                                "+ ${/data/weather/location/cityCode} }}"
                            ),
                        },
                    },
                }
            ],
            "candidateAssetIds": ["asset.drop_1"],
        }
        generate_message = await _call_ws(
            "generateWidgetCard",
            _tool_payload(
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
            ),
            _request_id("3"),
        )
        generated = generate_message["data"]
        assert generate_message["status"] == "success"
        assert generate_message["errorCode"] == ""
        assert generated["status"] == "success"
        assert generated["artifactUrl"]
        assert generated["suggestSize"] == "2x4"
        assert generated["effectiveCapabilities"]["data"] == ["ViewWeather"]

        # 当前 mock.dat 故意保留可被最新校验器识别的问题，用于真实验证：即使校验失败，
        # 主流程仍会返回成功产物并继续保存，而不是阻塞 WebSocket 请求。
        validation_report = await asyncio.to_thread(
            _validate_saved_artifact,
            generated["artifactUrl"],
        )
        assert validation_report.error_count > 0
        print(
            "校验发现问题，但 generateWidgetCard 仍成功返回 artifact，非阻塞链路验证通过。",
            flush=True,
        )

    asyncio.run(scenario())


if __name__ == "__main__":
    test_live_four_websocket_paths_complete_flow()
