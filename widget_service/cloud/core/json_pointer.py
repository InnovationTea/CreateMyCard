# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""JSON Pointer 解析工具。"""


def parse_json_pointer(pointer: str) -> tuple[str, ...] | None:
    """解析严格 JSON Pointer；空路径、空分段及非法转义返回 ``None``。"""
    if not isinstance(pointer, str) or not pointer.startswith("/") or pointer == "/":
        return None

    parts: list[str] = []
    for raw_part in pointer[1:].split("/"):
        if raw_part == "":
            return None
        index = 0
        while index < len(raw_part):
            if raw_part[index] == "~":
                if index + 1 >= len(raw_part) or raw_part[index + 1] not in {"0", "1"}:
                    return None
                index += 2
            else:
                index += 1
        parts.append(raw_part.replace("~1", "/").replace("~0", "~"))
    return tuple(parts)
