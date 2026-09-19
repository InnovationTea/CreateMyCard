# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time
from collections.abc import Awaitable, Callable

from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from app.logger import logger
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelGenerationError
from services.artifact_store import ArtifactUploadError

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
    if not enabled or retry_count == 0:
        return await operation(request)
    if retry_count < 0:
        raise ValueError("retry_count must be non-negative")
    snapshot = request.model_copy(deep=True)
    max_attempts = retry_count + 1
    attempt = 0
    while True:
        attempt += 1
        started_at = time.perf_counter()
        context = f"request_id={request_id} attempt={attempt} max_attempts={max_attempts}"
        logger.info(f"{_MODULE} interface_attempt_started {context}")
        try:
            result = await operation(snapshot.model_copy(deep=True))
        except (
            A2UIModelGenerationError,
            ArtifactUploadError,
            TimeoutError,
            ConnectionError,
        ) as exc:
            reason = type(exc).__name__
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.warning(
                f"{_MODULE} interface_attempt_failed {context} "
                f"exception_type={reason} duration_ms={duration_ms}"
            )
            if attempt == max_attempts:
                raise
        else:
            reason = result.errorCode
            retryable = (
                result.status == GenerationStatus.FAILED and reason in _RETRYABLE_ERROR_CODES
            )
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info(
                f"{_MODULE} interface_attempt_finished {context} "
                f"status={result.status.value} error_code={reason} duration_ms={duration_ms}"
            )
            if not retryable or attempt == max_attempts:
                return result
        logger.warning(
            f"{_MODULE} interface_retry_scheduled {context} retry_count={attempt} reason={reason}"
        )
