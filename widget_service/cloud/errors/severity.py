# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""Error severity levels that determine handling strategy."""

from enum import Enum


class ErrorSeverity(Enum):
    """决定异常的重试、恢复、通知和中断策略。"""

    RETRYABLE = "retryable"
    RECOVERABLE = "recoverable"
    USER_FACING = "user_facing"
    FATAL = "fatal"
