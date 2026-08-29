# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import inspect
from collections.abc import Awaitable, Callable
from typing import TypeVar

from models.service import RetryResult

T = TypeVar("T")


async def _resolve(value: T | Awaitable[T]) -> T:  # noqa: UP047
    """兼容异步生产实现和测试提供的立即返回值。"""
    if inspect.isawaitable(value):
        return await value
    return value


class RetryController:
    async def run(
        self,
        operation: Callable[[], str | Awaitable[str]],
        evaluate: Callable[[str], list[str] | Awaitable[list[str]]],
        *,
        retry_on_quality_failure: bool = False,
        max_repair_attempts: int = 1,
        repair: Callable[[str, list[str]], str | Awaitable[str]] | None = None,
    ) -> RetryResult:
        """生成一次，并按转换或校验 error 在有限次数内执行定向 repair。"""
        if max_repair_attempts < 1:
            raise ValueError("max_repair_attempts must be at least 1")
        result = await _resolve(operation())
        initial_errors = await _resolve(evaluate(result))
        should_repair = bool(initial_errors) and retry_on_quality_failure
        if not should_repair:
            return RetryResult(
                result=result,
                retryCount=0,
                errors=initial_errors,
                initialErrors=initial_errors,
            )
        if repair is None:
            raise ValueError("Repair callback is required when quality retry is enabled")

        errors = initial_errors
        repair_count = 0
        while errors and repair_count < max_repair_attempts:
            result = await _resolve(repair(result, errors))
            repair_count += 1
            errors = await _resolve(evaluate(result))
        return RetryResult(
            result=result,
            retryCount=repair_count,
            errors=errors,
            initialErrors=initial_errors,
            repairAttempted=repair_count > 0,
        )
