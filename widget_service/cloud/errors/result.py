# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""异常处理结果模型。"""

from dataclasses import dataclass, field
from typing import Any

from errors.errors import BaseError
from errors.severity import ErrorSeverity


@dataclass(frozen=True)
class ErrorResult:
    """描述异常处理后的状态和调用方应采取的动作。"""

    error: BaseError
    severity: ErrorSeverity
    should_retry: bool
    should_abort: bool
    should_notify_user: bool
    user_message: str | None
    can_recover: bool
    log_entry: dict[str, str] = field(default_factory=dict)
    retry_result: Any = None

    def to_tool_error_message(self) -> str:
        """生成适合返回给模型的工具错误说明。"""
        guidance = "Please try a different approach."
        if not self.can_recover:
            guidance = "The task cannot continue."
        return (
            f"[Error] {type(self.error).__name__}: {self.error}\n"
            f"This error is {self.severity.value}. {guidance}"
        )
