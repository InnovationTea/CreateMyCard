# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""Error severity levels that determine handling strategy."""

from enum import Enum


class ErrorSeverity(Enum):
    """
    RETRYABLE   — 自动重试（指数退避），重试耗尽后升级
    RECOVERABLE — 不重试，但 Agent 可继续运行（将错误信息返回给 LLM 让其自行调整）
    USER_FACING — 中断流程，把 user_message 推送给手机端
    FATAL       — 立即中断，只记日志，不给用户展示内部细节
    """
    RETRYABLE = "retryable"
    RECOVERABLE = "recoverable"
    USER_FACING = "user_facing"
    FATAL = "fatal"