# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""逐项调用已经启动的本地服务，便于按 pytest 用例名调试单个 WS 功能。"""

import asyncio
import json
import os
import socket

import pytest
import requests
import websockets

from ws_response_parser import parse_legacy_stream_content

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", socket.gethostbyname("localhost"))
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")
WS_BASE_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}{WS_BASE_PATH}"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
RESPONSE_TIMEOUT = float(os.getenv("WIDGET_SERVICE_TEST_RESPONSE_TIMEOUT", "180"))
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))
SESSION_ID = "single-feature-live-test"
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"
DATA_CAPABILITY_IDS = (
    "ViewWeather",
    "GetCalendarEvents",
    "GetCountdownDays",
    "GetEarphoneInfo",
    "GetPhoneBatteryInfo",
    "GetHealthAndSportSummary",
)


@pytest.fixture(scope="module", autouse=True)
def require_local_service():
    """整个文件只探测一次 8855；服务未启动时统一跳过本地联调用例。"""
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=1.0):
            pass
    except OSError as exc:
        pytest.skip(
            "请先在 widget_service 下执行 py -3.12 cloud\\start_websocket_server.py；"
            f"当前地址={SERVER_HOST}:{SERVER_PORT}，连接失败={exc}"
        )
    yield


def _tool_payload(content: dict, interaction_id: str, original: str = "") -> dict:
    """构造与正式插件一致的 WebSocket 原始请求包络。"""
    return {
        "content": {"odid": DEVICE_ODID, **content},
        "deviceInfo": {
            "countryCode": "CN",
            "deviceFormation": "HDSpeaker",
            "deviceType": 0,
            "locale": "zh-CN",
            "phoneType": "CLS-AL30",
            "prdVer": APP_VERSION,
            "romVersion": ROM_VERSION,
        },
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": interaction_id,
            "isNew": False,
            "sessionId": SESSION_ID,
        },
        "userAuth": {"user": {"userId": "single-feature-live-user"}},
        "utterance": {"original": original, "type": "text"},
        "version": "1.0",
        "bundleName": "com.omega_w_0823.hmservice",
    }


async def _call_ws(operation: str, content: dict, interaction_id: str) -> tuple[dict, dict]:
    """调用一个真实 WS 功能，返回插件外层响应和解析后的 streamContent。"""
    uri = f"{WS_BASE_URL}/{operation}"
    payload = _tool_payload(content, interaction_id, content.get("userQuery", ""))
    expected_request_id = f"{SESSION_ID}&{interaction_id}"
    async with websockets.connect(uri, open_timeout=3.0) as websocket:
        await websocket.send(json.dumps(payload, ensure_ascii=False))
        start_received = False
        while True:
            raw_response = await asyncio.wait_for(
                websocket.recv(),
                timeout=RESPONSE_TIMEOUT,
            )
            response = json.loads(raw_response)
            stream_info = response["reply"]["streamInfo"]
            assert stream_info["streamingTextId"] == expected_request_id
            if stream_info["streamType"] == "start":
                start_received = True
                assert stream_info["streamContent"] == ""
                assert response["reply"]["items"] == []
                continue
            if stream_info["streamType"] == "partial":
                assert start_received
                assert stream_info["streamContent"] == ""
                assert response["reply"]["items"] == []
                continue
            assert stream_info["streamType"] == "final"
            assert response["errorCode"] == "0"
            assert response["errorMessage"] == ""
            assert response["reply"]["items"] == []
            legacy_message = parse_legacy_stream_content(
                stream_info["streamContent"]
            )
            assert legacy_message["operation"] == operation
            assert legacy_message["requestId"] == expected_request_id
            print(
                f"\n[{operation}] {interaction_id}\n"
                + json.dumps(legacy_message, ensure_ascii=False, indent=2),
                flush=True,
            )
            return response, legacy_message


def _run_ws(operation: str, content: dict, interaction_id: str) -> tuple[dict, dict]:
    """给同步 pytest 用例提供单次 asyncio 入口。"""
    return asyncio.run(_call_ws(operation, content, interaction_id))


def test_live_health_check():
    """单独验证本地 HTTP 健康检查。"""
    response = requests.get(f"{HTTP_BASE_URL}/health", timeout=3.0)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_live_widget_capability_overview():
    """单独验证能力概述、事件清单和素材清单。"""
    _, legacy_message = _run_ws(
        "getWidgetCapabilityOverview",
        {},
        "overview",
    )
    data = legacy_message["data"]
    available_ids = {item["id"] for item in data["dataCapabilities"]}
    package_independent_ids = set(DATA_CAPABILITY_IDS) - {"GetHealthAndSportSummary"}

    assert legacy_message["type"] == "result"
    assert legacy_message["status"] == "success"
    assert package_independent_ids <= available_ids
    assert data["eventCapabilities"]
    assert data["assetCandidates"]


@pytest.mark.parametrize("capability_id", DATA_CAPABILITY_IDS)
def test_live_each_data_capability_schema(capability_id):
    """每个参数化节点只请求一个数据能力，便于按能力 ID 单点执行。"""
    _, legacy_message = _run_ws(
        "getDataCapabilitySchemas",
        {"dataCapabilityIds": [capability_id]},
        f"schema-{capability_id}",
    )
    data = legacy_message["data"]

    assert legacy_message["type"] == "result"
    assert [item["id"] for item in data["dataCapabilities"]] == [capability_id]
    assert data["missingCapabilityIds"] == []


def test_live_missing_data_capability_schema():
    """单独验证不存在的能力 ID 会进入 missingCapabilityIds。"""
    missing_id = "MissingCapability.LiveTest"
    _, legacy_message = _run_ws(
        "getDataCapabilitySchemas",
        {"dataCapabilityIds": [missing_id]},
        "schema-missing",
    )

    assert legacy_message["data"]["dataCapabilities"] == []
    assert legacy_message["data"]["missingCapabilityIds"] == [missing_id]


def test_live_generate_widget_card():
    """单独验证原 A2UI Form 模型生成和 artifact 保存链路。"""
    _, legacy_message = _run_ws(
        "generateWidgetCard",
        {
            "userQuery": "生成一张简洁的欢迎卡片",
            "size": "2x2",
            "title": "欢迎",
            "description": "本地单功能测试",
            "candidateDataBindings": [],
            "candidateEventCandidates": [],
            "candidateAssetIds": [],
        },
        "generate-a2ui",
    )
    data = legacy_message["data"]

    assert legacy_message["type"] == "result"
    assert data["status"] in {"success", "degraded"}
    assert data["artifactUrl"]
    assert data["artifactDigest"].startswith("sha256:")


def test_live_generate_widget_card_compact_dsl():
    """单独验证 Compact DSL 模型生成和 artifact 保存链路。"""
    _, legacy_message = _run_ws(
        "generateWidgetCardCompactDsl",
        {
            "userQuery": "生成一张简洁的欢迎卡片",
            "size": "2x2",
            "title": "欢迎",
            "description": "Compact DSL 本地测试",
            "candidateDataBindings": [],
            "candidateEventCandidates": [],
            "candidateAssetIds": [],
        },
        "generate-compact",
    )
    data = legacy_message["data"]

    assert legacy_message["type"] == "result"
    assert data["status"] in {"success", "degraded"}
    assert data["artifactUrl"]
    assert data["artifactDigest"].startswith("sha256:")


def test_live_invalid_arguments_plugin_contract():
    """单独验证参数异常仍保持插件顶层成功，并在 streamContent 中携带详情。"""
    response, legacy_message = _run_ws(
        "generateWidgetCard",
        {
            "userQuery": "故意缺少创建模式的 title 和 description",
            "candidateDataBindings": [],
        },
        "invalid-arguments",
    )

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    assert legacy_message["explanation"].startswith("工具参数传入有误")
    assert legacy_message["explanation"].endswith("报错信息如下")
    assert legacy_message["error"]["details"]


def test_live_malformed_json_plugin_contract():
    """单独验证 JSON 语法错误不会断开异常响应链路。"""
    async def scenario() -> tuple[dict, dict]:
        uri = f"{WS_BASE_URL}/getWidgetCapabilityOverview"
        async with websockets.connect(uri, open_timeout=3.0) as websocket:
            await websocket.send("{invalid-json")
            raw_response = await asyncio.wait_for(
                websocket.recv(),
                timeout=RESPONSE_TIMEOUT,
            )
            response = json.loads(raw_response)
            legacy_message = parse_legacy_stream_content(
                response["reply"]["streamInfo"]["streamContent"]
            )
            return response, legacy_message

    response, legacy_message = asyncio.run(scenario())

    assert response["errorCode"] == "0"
    assert response["errorMessage"] == ""
    assert response["reply"]["items"] == []
    assert legacy_message["type"] == "error"
    assert legacy_message["errorCode"] == "INVALID_ARGUMENTS"
    assert legacy_message["explanation"].startswith("工具参数传入有误")
