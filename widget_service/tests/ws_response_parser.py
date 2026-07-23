# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import ast
import re

_HEADER_PATTERN = re.compile(
    r"^type=(?P<type>'(?:\\.|[^'])*') "
    r"tool=(?P<tool>'(?:\\.|[^'])*') "
    r"operation=(?P<operation>'(?:\\.|[^'])*') "
    r"requestId=(?P<request_id>None|'(?:\\.|[^'])*')$"
)


def parse_legacy_stream_content(stream_content: str) -> dict:
    """解析路由写入 streamContent 的 Pydantic 旧消息字符串。

    该函数只供联调和回归测试读取业务 data。生产协议仍以服务端
    `str(legacy_message)` 的原始字符串为准，不把 items 恢复为结构化载荷。
    """
    header_text, data_and_tail = stream_content.split(" data=", 1)
    data_text, status_and_tail = data_and_tail.rsplit(" status=", 1)
    status_text, error_code_and_tail = status_and_tail.split(" errorCode=", 1)
    error_code_text, error_text = error_code_and_tail.split(" error=", 1)
    header_match = _HEADER_PATTERN.fullmatch(header_text)
    if header_match is None:
        raise ValueError("Unsupported legacy streamContent header")

    return {
        "type": ast.literal_eval(header_match.group("type")),
        "tool": ast.literal_eval(header_match.group("tool")),
        "operation": ast.literal_eval(header_match.group("operation")),
        "requestId": ast.literal_eval(header_match.group("request_id")),
        "data": ast.literal_eval(data_text),
        "status": ast.literal_eval(status_text),
        "errorCode": ast.literal_eval(error_code_text),
        "error": ast.literal_eval(error_text),
    }
