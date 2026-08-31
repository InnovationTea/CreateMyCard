# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""统一异常处理入口。"""

from errors.classifier import ErrorClassifier
from errors.codes import StatusCode
from errors.errors import raise_error
from errors.executors import (
    BaseExecutor,
    FatalExecutor,
    RecoverableExecutor,
    RetryableExecutor,
    SendMessageCallback,
    UserFacingExecutor,
)
from errors.result import ErrorResult
from errors.retry import RetryContext
from errors.severity import ErrorSeverity


class ErrorHandler:
    """对异常分类，并交由对应级别的执行器处理。"""

    def __init__(self, send_message: SendMessageCallback | None = None):
        self._executors: dict[ErrorSeverity, BaseExecutor] = {
            ErrorSeverity.FATAL: FatalExecutor(send_message),
            ErrorSeverity.USER_FACING: UserFacingExecutor(send_message),
            ErrorSeverity.RETRYABLE: RetryableExecutor(send_message),
            ErrorSeverity.RECOVERABLE: RecoverableExecutor(),
        }

    async def handle(
        self,
        error: Exception,
        *,
        retry: RetryContext | None = None,
    ) -> ErrorResult:
        """处理异常，并返回调用方下一步动作。"""
        wrapped, severity = ErrorClassifier.classify(error)
        executor = self._executors.get(severity)
        if executor is None:
            raise_error(
                StatusCode.FLOW_EXECUTION_ERROR,
                error_msg=f"Unsupported error severity: {severity!r}",
            )
        return await executor.execute(wrapped, severity, retry=retry)
