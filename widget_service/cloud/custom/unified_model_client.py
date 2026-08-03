# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.logger import json_for_log, logger
from config.config import Settings
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelBackend, ModelProvider, ModelTransportError
from models.generation import ModelRequestContext

_MODULE = "[Unified Model Client]"

SleepOperation = Callable[[float], Awaitable[None]]
RandomUniform = Callable[[float, float], float]


@dataclass(frozen=True)
class ProviderAttemptPlan:
    """一次逻辑模型调用中的物理客户端及其额外重试预算。"""

    provider: ModelProvider
    role: str
    max_retry_attempts: int


class UnifiedModelClient:
    """统一执行路由选择、模型异常重试和 OpenAI 主备切换。"""

    def __init__(
        self,
        settings: Settings,
        runtime: ModelExecutionRuntime,
        *,
        operation_name: str,
        sleep: SleepOperation | None = None,
        random_uniform: RandomUniform | None = None,
    ) -> None:
        self.settings = settings
        self.runtime = runtime
        self.operation_name = operation_name
        self.retry_count = 0
        self._sleep = sleep or asyncio.sleep
        self._random_uniform = random_uniform or random.uniform

    async def generate(
        self,
        backend: ModelBackend,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None,
        *,
        phase: str,
        allow_mep_partial_abort: bool = False,
    ) -> str:
        """执行一次逻辑模型调用；每轮 repair 会重新调用并从 master 开始。"""
        plans = self._provider_plans(backend)
        last_error: Exception | None = None
        for plan_index, plan in enumerate(plans):
            if plan_index > 0:
                self.retry_count += 1
                logger.warning(
                    f"{_MODULE} fallback_started operation={self.operation_name} "
                    f"phase={phase} provider={plan.provider}"
                )
            try:
                return await self._generate_with_provider(
                    plan,
                    messages,
                    request_context,
                    phase,
                    allow_mep_partial_abort,
                )
            except Exception as exc:
                last_error = exc
        if last_error is None:
            raise ModelTransportError("model provider plan is empty")
        if isinstance(last_error, ModelTransportError):
            raise last_error
        raise ModelTransportError("model generation failed") from last_error

    def _provider_plans(self, backend: ModelBackend) -> tuple[ProviderAttemptPlan, ...]:
        master_retry_count = self._retry_count_for_role("master")
        if backend == "mep":
            return (
                ProviderAttemptPlan(
                    provider="mep",
                    role="master",
                    max_retry_attempts=master_retry_count,
                ),
            )
        master = ProviderAttemptPlan(
            provider=self.settings.openai_master_client,
            role="master",
            max_retry_attempts=master_retry_count,
        )
        fallback_enabled = self.settings.enable_openai_fallback
        if not self.settings.enable_model_failure_retry or not fallback_enabled:
            return (master,)
        fallback = ProviderAttemptPlan(
            provider=self.settings.openai_fallback_client,
            role="fallback",
            max_retry_attempts=self._retry_count_for_role("fallback"),
        )
        return master, fallback

    def _retry_count_for_role(self, role: str) -> int:
        if not self.settings.enable_model_failure_retry:
            return 0
        if role == "fallback":
            return self.settings.fallback_model_failure_max_retry_attempts
        return self.settings.model_failure_max_retry_attempts

    async def _generate_with_provider(
        self,
        plan: ProviderAttemptPlan,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None,
        phase: str,
        allow_mep_partial_abort: bool,
    ) -> str:
        max_attempts = plan.max_retry_attempts + 1
        for attempt in range(1, max_attempts + 1):
            try:
                result = await self._runtime_generate_once(
                    plan.provider,
                    messages,
                    request_context,
                )
                return self._require_output(result)
            except Exception as exc:
                recovered = self._recover_mep_partial_output(
                    exc,
                    plan.provider,
                    allow_mep_partial_abort,
                )
                if recovered is not None:
                    return recovered
                should_retry = attempt < max_attempts
                delay_seconds = self._retry_delay_seconds(attempt) if should_retry else 0.0
                log_failure = logger.warning if should_retry else logger.error
                log_failure(
                    f"{_MODULE} model_call_failed operation={self.operation_name} "
                    f"phase={phase} provider={plan.provider} role={plan.role} "
                    f"attempt={attempt} max_attempts={max_attempts} "
                    f"will_retry={json_for_log(should_retry)} "
                    f"retry_delay_seconds={delay_seconds} "
                    f"exception_type={type(exc).__name__}"
                )
                if not should_retry:
                    raise
                self.retry_count += 1
                await self._sleep(delay_seconds)
        raise AssertionError("model retry loop exited unexpectedly")

    async def _runtime_generate_once(
        self,
        provider: ModelProvider,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None,
    ) -> str:
        return await self.runtime.generate_once(provider, messages, request_context)

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
    def _require_output(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ModelTransportError(
                "model returned empty output",
                code="MODEL_EMPTY_OUTPUT",
            )
        if value.lstrip().startswith("a2ui_model_error:"):
            raise ModelTransportError(
                "model returned an error instead of DSL",
                code="MODEL_ERROR_OUTPUT",
            )
        return value

    @staticmethod
    def _recover_mep_partial_output(
        exc: Exception,
        provider: ModelProvider,
        allow_partial_abort: bool,
    ) -> str | None:
        if not isinstance(exc, ModelTransportError):
            return None
        is_recoverable_error = exc.code == "6241" and provider == "mep"
        if not allow_partial_abort or not is_recoverable_error:
            return None
        partial_output = exc.partial_output.strip()
        if not partial_output:
            return None
        logger.warning(
            f"{_MODULE} mep_partial_output_recovered error_code={exc.code} "
            f"partial_length={len(partial_output)}"
        )
        return partial_output
