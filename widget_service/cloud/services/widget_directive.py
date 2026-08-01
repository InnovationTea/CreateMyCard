# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import uuid
from enum import StrEnum
from typing import Any

from models.service import WidgetPluginReply, WidgetPluginStreamResponse, WidgetStreamInfo


class WidgetDirectiveState(StrEnum):
    """卡片生成进度指令状态。"""

    START = "start"
    SUCCESS = "success"
    FAILURE = "failure"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_value(*values: Any, default: Any = "") -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _build_session(raw_payload: dict[str, Any]) -> dict[str, Any]:
    session = _mapping(raw_payload.get("session"))
    device_info = _mapping(raw_payload.get("deviceInfo"))
    user_auth = _mapping(raw_payload.get("userAuth"))
    user = _mapping(user_auth.get("user"))
    phone_type = _first_value(session.get("phoneType"), device_info.get("phoneType"))
    return {
        "clientVersion": _first_value(session.get("clientVersion"), device_info.get("prdVer")),
        "deviceId": _first_value(session.get("deviceId"), device_info.get("deviceId")),
        "deviceModel": _first_value(session.get("deviceModel"), device_info.get("marketingName")),
        "deviceType": _first_value(session.get("deviceType"), device_info.get("deviceFormation")),
        "dialogId": _first_value(session.get("dialogId"), default=0),
        "dialogPageId": _first_value(session.get("dialogPageId")),
        "interactionId": _first_value(session.get("interactionId")),
        "ipAddress": _first_value(session.get("ipAddress")),
        "messageId": str(uuid.uuid4()),
        "messageName": "progressInfo",
        "packageName": _first_value(
            session.get("packageName"),
            default="com.huawei.hmos.vassistant",
        ),
        "phoneType": phone_type,
        "prdVer": _first_value(session.get("prdVer"), device_info.get("prdVer")),
        "sessionId": _first_value(session.get("sessionId")),
        "uid": _first_value(session.get("uid"), user.get("userId")),
    }


def _build_execute_payload(state: WidgetDirectiveState, artifact_url: str) -> dict[str, Any]:
    if state is WidgetDirectiveState.START:
        return {"executeParam": {"intentName": "AIWidgetStart"}}
    execute_param: dict[str, Any] = {
        "status": state is WidgetDirectiveState.SUCCESS,
        "intentName": "AIWidgetEnd",
    }
    if state is WidgetDirectiveState.SUCCESS:
        if not artifact_url:
            raise ValueError("success widget directive requires artifact URL")
        execute_param["intentParam"] = {"genWidgetResult": artifact_url}
    return {"executeParam": execute_param}


def build_widget_directive_response(
    raw_payload: dict[str, Any],
    state: WidgetDirectiveState,
    streaming_text_id: str,
    artifact_url: str = "",
) -> WidgetPluginStreamResponse:
    """构造插件协议 command 帧，streamContent 保存完整端侧指令 JSON。"""
    directive = {
        "directives": [
            {
                "header": {"name": "Action", "namespace": "Common"},
                "payload": _build_execute_payload(state, artifact_url),
            }
        ],
        "errorCode": "0",
        "errorMsg": "OK",
        "isContainsDialogFinishDirective": False,
        "isDialogFinished": False,
        "isFinal": False,
        "isFinished": False,
        "isIgnoreDialogState": False,
        "session": _build_session(raw_payload),
        "triggerRedLine": False,
    }
    stream_content = json.dumps(directive, ensure_ascii=False, separators=(",", ":"))
    return WidgetPluginStreamResponse(
        errorCode="0",
        errorMessage="",
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                streamContent=stream_content,
                streamingTextId=streaming_text_id,
                streamType="command",
                textType="command",
            ),
            items=[],
        ),
    )
