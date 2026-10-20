# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""只提取新单步链路的完整响应包装，不修补或选择候选DSL。"""

import re

_SINGLE_FENCE = re.compile(
    r"\A```(?:genui|jsonl)[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```\Z",
    re.IGNORECASE,
)


class SingleStepOutputError(ValueError):
    """单步响应包含不能唯一提取的代码围栏。"""


def extract_single_step_output(raw_output: str) -> str:
    """接受裸响应或一个明确围栏，拒绝歧义包装；内部DSL仍须完整校验。"""
    text = raw_output.strip()
    match = _SINGLE_FENCE.fullmatch(text)
    if match is None:
        if any(line.lstrip().startswith("```") for line in text.splitlines()):
            raise SingleStepOutputError(
                "single-step response must contain one complete JSONL block"
            )
        return text
    body = match.group("body")
    if any(line.lstrip().startswith("```") for line in body.splitlines()):
        raise SingleStepOutputError("single-step response contains multiple or nested code blocks")
    return body.strip()
