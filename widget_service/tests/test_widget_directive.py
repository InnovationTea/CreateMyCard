# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

widget_directive = importlib.import_module("services.widget_directive")
WidgetDirectiveState = widget_directive.WidgetDirectiveState
build_widget_directive_response = widget_directive.build_widget_directive_response


def _raw_payload() -> dict:
    return {
        "deviceInfo": {
            "deviceId": "device-1",
            "marketingName": "Device Model",
            "deviceFormation": "phone",
            "phoneType": "phone",
            "prdVer": "11.7.7.205",
        },
        "session": {"sessionId": "session-1", "interactionId": 6},
        "userAuth": {"user": {"userId": "user-1"}},
    }


def _directive_content(state: WidgetDirectiveState, artifact_url: str = "") -> dict:
    response = build_widget_directive_response(
        _raw_payload(),
        state,
        "stream-1",
        "card-1",
        "request-1",
        artifact_url,
    )
    result = response.model_dump(mode="json")
    stream_info = result["reply"]["streamInfo"]
    assert stream_info["streamType"] == "command"
    assert stream_info["textType"] == "command"
    assert result["reply"]["items"] == []
    command_message = json.loads(stream_info["streamContent"])
    assert command_message["content_type"] == "aIWidgetDirectives"
    assert command_message["event"] == "command"
    assert command_message["task_id"] == "request-1"
    datetime.strptime(command_message["process_time"], "%Y-%m-%d %H:%M:%S.%f")
    return json.loads(command_message["content"])


def test_widget_directive_payloads_use_plugin_command_frame():
    start = _directive_content(WidgetDirectiveState.START)
    success = _directive_content(
        WidgetDirectiveState.SUCCESS,
        "https://example.invalid/artifact.json",
    )
    failure = _directive_content(WidgetDirectiveState.FAILURE)

    assert start["directives"][0]["payload"] == {
        "executeParam": {"intentName": "AIWidgetStart", "cardId": "card-1"}
    }
    assert success["directives"][0]["payload"]["executeParam"] == {
        "status": True,
        "intentName": "AIWidgetEnd",
        "cardId": "card-1",
        "intentParam": {"genWidgetResult": "https://example.invalid/artifact.json"},
    }
    assert failure["directives"][0]["payload"] == {
        "executeParam": {
            "status": False,
            "intentName": "AIWidgetEnd",
            "cardId": "card-1",
        }
    }
    assert start["session"]["sessionId"] == "session-1"
    assert start["session"]["interactionId"] == 6
    assert start["session"]["messageName"] == "progressInfo"


def test_success_widget_directive_requires_artifact_url():
    with pytest.raises(ValueError, match="requires artifact URL"):
        _directive_content(WidgetDirectiveState.SUCCESS)
