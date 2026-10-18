# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest

from api.schemas import GenerateWidgetCardResponse
from core.errors import GenerationStatus
from models.service import WidgetWebSocketErrorMessage


@pytest.mark.parametrize("status", list(GenerationStatus))
def test_generation_response_omits_message_but_preserves_internal_text(status):
    response = GenerateWidgetCardResponse(
        status=status,
        suggestSize="2x2",
        message="内部生成结果说明",
        errorCode="TEST_ERROR" if status == GenerationStatus.FAILED else "",
    )
    expected = {
        "status": status.value,
        "artifactUrl": "",
        "artifactDigest": "",
        "suggestSize": "2x2",
        "removedCapabilities": [],
        "errorCode": response.errorCode,
        "effectiveCapabilities": {},
    }

    assert response.message == "内部生成结果说明"
    assert response.model_dump(mode="json", exclude_none=True) == expected
    assert json.loads(response.model_dump_json()) == expected


def test_generation_serialization_schema_omits_message():
    schema = GenerateWidgetCardResponse.model_json_schema(mode="serialization")
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    assert "message" not in properties


def test_websocket_error_keeps_diagnostic_message():
    response = WidgetWebSocketErrorMessage(
        operation="generateWidgetCardCompactDsl",
        errorCode="INVALID_ARGUMENTS",
        error={"message": "参数格式错误"},
    )
    payload = response.model_dump(mode="json", exclude_none=True)
    assert payload.get("error") == {"message": "参数格式错误"}
