# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""连接已启动且启用语义编辑的服务，验证创建、视觉编辑及数据删除拒绝。"""

import asyncio
import json
import os
import socket

import pytest
import websockets

from ws_response_parser import parse_legacy_stream_content

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", socket.gethostbyname("localhost"))
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")
WS_URI = f"ws://{SERVER_HOST}:{SERVER_PORT}{WS_BASE_PATH}/generateWidgetCard"
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))

SESSION_ID = "multi-round-live-test"
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"
DEVICE_INFO = {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": APP_VERSION,
    "romVersion": ROM_VERSION,
    "sysVer": "36",
}


def _tool_payload(content: dict, interaction_id: str) -> dict:
    """构造华为流处理插件 WebSocket 请求包络。"""
    return {
        "content": {"odid": DEVICE_ODID, **content},
        "deviceInfo": DEVICE_INFO,
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": interaction_id,
            "isNew": False,
            "sessionId": SESSION_ID,
        },
        "userAuth": {"user": {"userId": "multi-round-live-user"}},
        "utterance": {"original": content["userQuery"], "type": "text"},
        "version": "1.0",
        "bundleName": "com.omega_w_0823.hmservice",
    }


async def _generate(content: dict, interaction_id: str) -> dict:
    """调用真实 generateWidgetCard，并返回业务 data。"""
    expected_request_id = f"{SESSION_ID}&{interaction_id}"
    try:
        async with websockets.connect(WS_URI, open_timeout=3.0) as websocket:
            await websocket.send(
                json.dumps(_tool_payload(content, interaction_id), ensure_ascii=False)
            )
            start_received = False
            while True:
                response = json.loads(await websocket.recv())
                stream_info = response["reply"]["streamInfo"]
                assert stream_info["streamingTextId"] == expected_request_id
                if stream_info["streamType"] == "start":
                    start_received = True
                    continue
                if stream_info["streamType"] == "partial":
                    continue

                assert stream_info["streamType"] == "final"
                assert start_received
                assert response["reply"]["items"] == []
                result_item = parse_legacy_stream_content(
                    stream_info["streamContent"]
                )
                assert result_item["type"] == "result"
                assert result_item["operation"] == "generateWidgetCard"
                assert result_item["requestId"] == expected_request_id
                data = result_item["data"]
                print(
                    f"\n[{interaction_id}] generateWidgetCard response:\n"
                    + json.dumps(data, ensure_ascii=False, indent=2)
                )
                return data
    except OSError as exc:
        reason = (
            "需要先启动本地服务：设置 WIDGET_SERVICE_ENABLE_WIDGET_EDIT=true，"
            "然后在 widget_service 下执行 py -3.12 cloud\\start_websocket_server.py；"
            f"当前探测地址：{WS_URI}；"
            f"连接错误：{type(exc).__name__}: {exc}"
        )
        pytest.skip(reason)


def _assert_artifact_success(data: dict) -> None:
    assert data["status"] in {"success", "degraded"}
    assert data["artifactUrl"]
    assert data["artifactUrl"].endswith(".md")
    assert data["artifactDigest"].startswith("sha256:")


def test_live_multi_round_create_visual_edit_and_reject_data_removal():
    """验证创建及视觉编辑成功，删除动态数据不生成新产物。"""

    async def scenario() -> None:
        created = await _generate(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "userQuery": "生成一张上海天气卡片",
                "size": "2x4",
                "title": "上海天气",
                "description": "当前天气速览",
                "candidateDataBindings": [
                    {
                        "capabilityId": "ViewWeather",
                        "arguments": {"prefectureName": "上海市", "forecastDays": 1},
                        "writeResultTo": "/data/weather",
                        "candidateOutputFields": [
                            "/location/districtName",
                            "/current/temperatureText",
                            "/current/condition",
                        ],
                    }
                ],
                "candidateEventCandidates": [],
                "candidateAssetIds": ["asset.drop_1"],
            },
            "create-1",
        )
        _assert_artifact_success(created)
        assert created["suggestSize"] == "2x4"
        assert created["effectiveCapabilities"]["data"] == ["ViewWeather"]

        if created.get("errorCode") == "WIDGET_EDIT_DISABLED":
            pytest.fail(
                "服务没有开启多轮编辑，请设置 "
                "WIDGET_SERVICE_ENABLE_WIDGET_EDIT=true 后重启服务。"
            )

        visual_edit = await _generate(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "userQuery": "整体改成蓝色风格，信息更紧凑",
                "sourceArtifactUrl": created["artifactUrl"],
            },
            "edit-visual-2",
        )
        if visual_edit.get("errorCode") == "WIDGET_EDIT_DISABLED":
            pytest.fail(
                "服务没有开启多轮编辑，请设置 "
                "WIDGET_SERVICE_ENABLE_WIDGET_EDIT=true 后重启服务。"
            )
        _assert_artifact_success(visual_edit)
        assert visual_edit["artifactUrl"] != created["artifactUrl"]
        assert visual_edit["suggestSize"] == "2x4"
        assert visual_edit["effectiveCapabilities"]["data"] == ["ViewWeather"]

        rejected = await _generate(
            {
                "bundleName": "com.omega_w_0823.hmservice",
                "userQuery": "去掉动态天气，只保留静态卡片",
                "sourceArtifactUrl": visual_edit["artifactUrl"],
                "candidateDataBindings": [],
            },
            "edit-clear-3",
        )
        assert rejected.get("status") == "unsupported"
        assert rejected.get("errorCode") == "WIDGET_EDIT_UNSUPPORTED"
        assert not rejected.get("artifactUrl")
        assert not rejected.get("artifactDigest")

        print("\n多轮 WebSocket 测试通过：创建、视觉编辑成功，删除数据被拒绝")

    asyncio.run(scenario())


if __name__ == "__main__":
    test_live_multi_round_create_visual_edit_and_reject_data_removal()
