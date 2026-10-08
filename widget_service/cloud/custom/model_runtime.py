# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import time
import traceback
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial

from app.logger import logger
from config.config import Settings, get_settings
from custom.deepseek_official_http_transport import DeepSeekOfficialHttpTransport
from custom.deepseek_platform_client import DeepSeekPlatformClient
from custom.llmclient import LLMClientOptions, stream_genui
from custom.mep_model_transport import MepModelTransport
from custom.model_transport import ModelProvider, ModelTransport, ModelTransportError
from custom.official_http_client import request_official_http
from models.generation import ModelRequestContext
from services.generation_trace_recorder import trace_step
from utils.ops_metrics import report_ops_metrics

_MODULE = "[Model Runtime]"


def _generate_with_llmclient(messages: list[dict[str, str]]) -> str:
    """在线程内聚合原有 llmclient 的异步 Token 流。"""

    async def collect_stream() -> str:
        options = LLMClientOptions()
        settings = get_settings()
        if settings.deepseek_http_url.strip().startswith(("http://", "https://")):
            completion = await request_official_http(
                url=settings.deepseek_http_url,
                api_key=options.api_key,
                model=options.model,
                messages=messages,
                user=options.user,
                temperature=options.temperature,
                top_p=options.top_p,
                max_tokens=options.max_tokens,
                stop=options.stop if options.stop is not None else ["DeepSeek"],
                timeout=options.recv_timeout,
            )
            return completion.content
        chunks = [chunk async for chunk in stream_genui(options, messages)]
        return "".join(chunks)

    try:
        result = asyncio.run(collect_stream())
        logger.info(f"{_MODULE} llmclient_response_collected content_chars={len(result)}")
        return result
    except ModelTransportError:
        raise
    except Exception as exc:
        logger.error(
            f"{_MODULE} llmclient_generation_failed error_type={type(exc).__name__} error={exc!r}"
        )
        raise ModelTransportError(f"llmclient model generation failed: {exc}") from exc


class ModelExecutionRuntime:
    """为所有物理模型客户端提供共享并发、排队和执行超时控制。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        mep_transport: MepModelTransport | None = None,
        deepseek_platform_transport: ModelTransport | None = None,
        llmclient_transport: ModelTransport | None = None,
        deepseek_official_http_transport: DeepSeekOfficialHttpTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._semaphore = asyncio.Semaphore(self.settings.model_max_concurrency)
        self._mep_transport = mep_transport or MepModelTransport(self.settings)
        self._deepseek_platform_transport = deepseek_platform_transport or DeepSeekPlatformClient(
            self.settings
        )
        self._deepseek_official_http_transport = (
            deepseek_official_http_transport or DeepSeekOfficialHttpTransport(self.settings)
        )
        self._llmclient_generate = (
            llmclient_transport.generate
            if llmclient_transport is not None
            else _generate_with_llmclient
        )
        self._llmclient_executor = ThreadPoolExecutor(
            max_workers=self.settings.model_max_concurrency,
            thread_name_prefix="llmclient-model",
        )

    async def aclose(self) -> None:
        """关闭共享 HTTP 连接池并停止接收新的 llmclient 线程任务。"""
        await self._mep_transport.aclose()
        await self._deepseek_official_http_transport.aclose()
        self._llmclient_executor.shutdown(wait=False, cancel_futures=False)

    async def generate_once(
        self,
        provider: ModelProvider,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None = None,
    ) -> str:
        """取得共享令牌后调用一次指定物理模型客户端。"""
        queue_started_at = time.perf_counter()
        queue_timeout = self.settings.model_queue_timeout_seconds
        try:
            async with asyncio.timeout(queue_timeout):
                await self._semaphore.acquire()
        except TimeoutError as exc:
            queue_duration_ms = round(
                (time.perf_counter() - queue_started_at) * 1000,
                2,
            )
            trace_step(
                "model.queue",
                stage="model.queue",
                status="timeout",
                duration_ms=queue_duration_ms,
                details={"provider": provider, "timeoutSeconds": queue_timeout},
            )
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.error(
                f"{_MODULE} queue_timeout provider={provider} "
                f"timeout_seconds={queue_timeout} exception={exc!r}"
            )
            raise ModelTransportError(
                f"model concurrency queue timed out after {queue_timeout}s",
                code="MODEL_QUEUE_TIMEOUT",
            ) from exc

        queue_duration_ms = round((time.perf_counter() - queue_started_at) * 1000, 2)
        logger.info(
            f"{_MODULE} permit_acquired provider={provider} queue_duration_ms={queue_duration_ms}"
        )
        trace_step(
            "model.queue",
            stage="model.queue",
            status="success",
            duration_ms=queue_duration_ms,
            details={"provider": provider},
        )
        execution_started_at = time.perf_counter()
        execution_status = "failed"
        execution_error: Exception | None = None
        try:
            result = await self._execute_provider(provider, messages, request_context)
            execution_status = "success"
            return result
        except Exception as exc:
            execution_error = exc
            raise
        finally:
            self._semaphore.release()
            execution_duration_ms = round(
                (time.perf_counter() - execution_started_at) * 1000,
                2,
            )
            logger.info(
                f"{_MODULE} permit_released provider={provider} "
                f"execution_status={execution_status} "
                f"execution_duration_ms={execution_duration_ms}"
            )
            execution_details = {"provider": provider}
            if execution_error is not None:
                execution_details.update(
                    {
                        "exceptionType": type(execution_error).__name__,
                        "message": str(execution_error),
                        "errorCode": getattr(execution_error, "code", ""),
                    }
                )
            trace_step(
                "model.provider_execution",
                stage="model.providerExecution",
                status=execution_status,
                duration_ms=execution_duration_ms,
                details=execution_details,
            )

    async def generate(
        self,
        provider: ModelProvider,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None = None,
    ) -> str:
        """兼容旧调用方；新代码使用 generate_once 强调单次物理调用。"""
        return await self.generate_once(provider, messages, request_context)

    async def _execute_provider(
        self,
        provider: ModelProvider,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None,
    ) -> str:
        if provider == "mep":
            operation = self._mep_transport.generate(messages)
            return await self._await_async_provider(provider, operation)
        if provider == "deepseek_platform":
            if request_context is None:
                raise ModelTransportError("DeepSeek Platform request context is missing")
            operation = self._deepseek_platform_transport.generate(
                messages,
                request_context,
            )
            return await self._await_async_provider(provider, operation)
        if provider == "deepseek_official_http":
            operation = self._deepseek_official_http_transport.generate(
                messages,
                request_context,
            )
            return await self._await_async_provider(provider, operation)
        if provider == "llmclient":
            return await self._generate_llmclient(messages)
        raise ModelTransportError(
            f"unsupported model provider: {provider}",
            code="MODEL_PROVIDER_UNSUPPORTED",
        )

    async def _await_async_provider(
        self,
        provider: ModelProvider,
        operation: Awaitable[str],
    ) -> str:
        timeout = self.settings.model_request_timeout_seconds
        try:
            async with asyncio.timeout(timeout):
                return await operation
        except TimeoutError as exc:
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.error(
                f"{_MODULE} request_timeout provider={provider} "
                f"timeout_seconds={timeout} exception={exc!r} "
                f"traceback={traceback.format_exc()}"
            )
            raise ModelTransportError(
                f"model request timed out after {timeout}s",
                code="MODEL_REQUEST_TIMEOUT",
            ) from exc

    async def _generate_llmclient(self, messages: list[dict[str, str]]) -> str:
        """在线程中运行同步适配器；超时后持有令牌直至真实调用结束。"""
        loop = asyncio.get_running_loop()
        context = copy_context()
        future = loop.run_in_executor(
            self._llmclient_executor,
            partial(context.run, self._llmclient_generate, messages),
        )
        timeout = self.settings.model_request_timeout_seconds
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except TimeoutError as exc:
            logger.error(
                f"{_MODULE} request_timeout provider=llmclient "
                f"timeout_seconds={timeout} waiting_for_physical_completion=true"
            )
            await self._finish_timed_out_llmclient(future)
            raise ModelTransportError(
                f"model request timed out after {timeout}s",
                code="MODEL_REQUEST_TIMEOUT",
            ) from exc
        except asyncio.CancelledError:
            logger.warning(
                f"{_MODULE} llmclient_wait_cancelled waiting_for_physical_completion=true"
            )
            await self._finish_cancelled_llmclient(future)
            raise

    @staticmethod
    async def _finish_timed_out_llmclient(future: asyncio.Future[str]) -> None:
        try:
            await asyncio.shield(future)
        except Exception as exc:
            logger.error(
                f"{_MODULE} timed_out_llmclient_completed_with_error "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )

    @staticmethod
    async def _finish_cancelled_llmclient(future: asyncio.Future[str]) -> None:
        try:
            await asyncio.shield(future)
        except Exception as exc:
            logger.error(
                f"{_MODULE} cancelled_llmclient_completed_with_error "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
