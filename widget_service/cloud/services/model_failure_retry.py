# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import inspect
import random
from collections.abc import Awaitable, Callable

from app.logger import json_for_log, logger
from config.config import Settings
from custom.a2ui_model_client import A2UIModelGenerationError, require_generated_dsl

_MODULE = "[Model Failure Retry]"

ModelOperation = Callable[[], str | Awaitable[str]]
SleepOperation = Callable[[float], Awaitable[None]]
RandomUniform = Callable[[float, float], float]


class ModelFailureRetryExecutor:
    """在真实模型调用边界统一执行有限次数的异步退避重试。"""

    def __init__(
        self,
        settings: Settings,
        *,
        operation_name: str,
        backend: str,
        sleep: SleepOperation | None = None,
        random_uniform: RandomUniform | None = None,
    ) -> None:
        self.settings = settings
        self.operation_name = operation_name
        self.backend = backend
        self.retry_count = 0
        self._sleep = sleep or asyncio.sleep
        self._random_uniform = random_uniform or random.uniform

    async def execute(self, model_operation: ModelOperation, phase: str) -> str:
        """调用模型；任意调用异常或空输出均按配置退避后重试同一请求。"""
        max_retry_attempts = self._max_retry_attempts()
        max_attempts = max_retry_attempts + 1
        for attempt in range(1, max_attempts + 1):
            try:
                model_result = model_operation()
                if inspect.isawaitable(model_result):
                    model_result = await model_result
                result = require_generated_dsl(model_result)
                if attempt > 1:
                    logger.info(
                        f"{_MODULE} retry_succeeded operation={self.operation_name} "
                        f"backend={self.backend} phase={phase} attempt={attempt}"
                    )
                return result
            except Exception as exc:
                should_retry = attempt < max_attempts
                delay_seconds = self._retry_delay_seconds(attempt) if should_retry else 0.0
                log_failure = logger.warning if should_retry else logger.error
                log_failure(
                    f"{_MODULE} model_call_failed operation={self.operation_name} "
                    f"backend={self.backend} phase={phase} attempt={attempt} "
                    f"max_attempts={max_attempts} retry_enabled="
                    f"{json_for_log(self.settings.enable_model_failure_retry)} "
                    f"will_retry={json_for_log(should_retry)} "
                    f"retry_delay_seconds={delay_seconds} "
                    f"exception_type={type(exc).__name__}"
                )
                if not should_retry:
                    self._raise_generation_error(exc)
                self.retry_count += 1
                await self._sleep(delay_seconds)
        raise AssertionError("model retry loop exited unexpectedly")

    def _max_retry_attempts(self) -> int:
        if not self.settings.enable_model_failure_retry:
            return 0
        return self.settings.model_failure_max_retry_attempts

    def _retry_delay_seconds(self, retry_index: int) -> float:
        initial_delay = self.settings.model_failure_retry_initial_delay_seconds
        multiplier = self.settings.model_failure_retry_backoff_multiplier
        max_delay = self.settings.model_failure_retry_max_delay_seconds
        nominal_delay = min(max_delay, initial_delay * multiplier ** (retry_index - 1))
        jitter_span = nominal_delay * self.settings.model_failure_retry_jitter_ratio
        lower_bound = max(0.0, nominal_delay - jitter_span)
        upper_bound = min(max_delay, nominal_delay + jitter_span)
        return round(self._random_uniform(lower_bound, upper_bound), 3)

    @staticmethod
    def _raise_generation_error(exc: Exception) -> None:
        if isinstance(exc, A2UIModelGenerationError):
            raise exc
        raise A2UIModelGenerationError("model generation failed") from exc
