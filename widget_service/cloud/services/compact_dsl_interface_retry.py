# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time
from collections.abc import Awaitable, Callable

from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from app.logger import logger
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelGenerationError
from services.artifact_store import ArtifactUploadError
from services.generation_trace_recorder import (
    trace_attempt,
    trace_increment_retry,
    trace_observe_attempt,
    trace_record,
    trace_span,
)

_MODULE = "[Compact DSL Interface Retry]"
_RETRYABLE_ERROR_CODES = frozenset(
    {
        ErrorCode.A2UI_GENERATION_FAILED.value,
        ErrorCode.VALIDATION_FAILED.value,
        ErrorCode.ARTIFACT_UPLOAD_FAILED.value,
        ErrorCode.TIMEOUT.value,
    }
)


async def run_compact_dsl_with_retry(
    operation: Callable[[GenerateWidgetCardRequest], Awaitable[GenerateWidgetCardResponse]],
    request: GenerateWidgetCardRequest,
    *,
    enabled: bool,
    retry_count: int,
    request_id: str | None,
) -> GenerateWidgetCardResponse:
    """重跑已通过入口校验的生成流程，不包含参数修复、指令及最终结果发送。

    retry_count 是首次执行之外的额外次数。每轮复制原始请求，包括模型私有上下文，
    防止生成/编辑归一化修改请求后污染下一轮；取消及非白名单异常保持原样向外抛出。
    """
    if enabled and retry_count < 0:
        raise ValueError("retry_count must be non-negative")
    snapshot = request.model_copy(deep=True) if enabled else request
    max_attempts = retry_count + 1 if enabled else 1
    attempt = 0
    while True:
        attempt += 1
        started_at = time.perf_counter()
        context = f"request_id={request_id} attempt={attempt} max_attempts={max_attempts}"
        logger.info(f"{_MODULE} interface_attempt_started {context}")
        trace_observe_attempt("interfaceAttempts", attempt)
        with (
            trace_attempt(interface=attempt),
            trace_span(
                "interface.attempt",
                stage="interfaceAttempt.total",
                details={"attempt": attempt, "maxAttempts": max_attempts},
                kind="group",
            ) as attempt_span,
        ):
            trace_record(
                "interface.attempt.started",
                stage="interfaceAttempt",
                status="started",
                details={"maxAttempts": max_attempts, "requestId": request_id},
            )
            try:
                attempt_request = snapshot.model_copy(deep=True) if enabled else request
                result = await operation(attempt_request)
            except (
                A2UIModelGenerationError,
                ArtifactUploadError,
                TimeoutError,
                ConnectionError,
            ) as exc:
                reason = type(exc).__name__
                attempt_span.outcome("failed", exceptionType=reason)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.warning(
                    f"{_MODULE} interface_attempt_failed {context} "
                    f"exception_type={reason} duration_ms={duration_ms}"
                )
                trace_record(
                    "interface.attempt.completed",
                    stage="interfaceAttempt",
                    status="failed",
                    duration_ms=duration_ms,
                    details={
                        "maxAttempts": max_attempts,
                        "exceptionType": reason,
                        "willRetry": attempt < max_attempts,
                    },
                )
                if attempt == max_attempts:
                    raise
            else:
                reason = result.errorCode
                attempt_span.outcome(result.status.value, errorCode=reason)
                attempt_span.json_artifacts["generation_response"] = result.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                attempt_span.artifact_roles["generation_response"] = "output"
                retryable = (
                    result.status == GenerationStatus.FAILED and reason in _RETRYABLE_ERROR_CODES
                )
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    f"{_MODULE} interface_attempt_finished {context} "
                    f"status={result.status.value} error_code={reason} "
                    f"duration_ms={duration_ms}"
                )
                trace_record(
                    "interface.attempt.completed",
                    stage="interfaceAttempt",
                    status=result.status.value,
                    duration_ms=duration_ms,
                    details={
                        "maxAttempts": max_attempts,
                        "errorCode": reason,
                        "willRetry": retryable and attempt < max_attempts,
                    },
                )
                if not retryable or attempt == max_attempts:
                    return result
        logger.warning(
            f"{_MODULE} interface_retry_scheduled {context} retry_count={attempt} reason={reason}"
        )
        trace_increment_retry("interfaceRetries")
        with trace_attempt(interface=attempt):
            trace_record(
                "interface.retry.scheduled",
                stage="interfaceAttempt",
                status="scheduled",
                details={"reason": reason, "nextAttempt": attempt + 1},
            )
