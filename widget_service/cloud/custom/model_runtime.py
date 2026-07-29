# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from app.logger import logger
from config.config import Settings, get_settings
from custom.llmclient_model_transport import LlmClientModelTransport
from custom.mep_model_transport import MepModelTransport
from custom.model_transport import ModelBackend, ModelTransportError

_MODULE = "[Model Runtime]"


class ModelExecutionRuntime:
    """为所有真实模型后端提供进程级并发、排队和执行超时控制。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        mep_transport: MepModelTransport | None = None,
        llmclient_transport: LlmClientModelTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._semaphore = asyncio.Semaphore(self.settings.model_max_concurrency)
        self._mep_transport = mep_transport or MepModelTransport(self.settings)
        self._llmclient_transport = llmclient_transport or LlmClientModelTransport()
        self._llmclient_executor = ThreadPoolExecutor(
            max_workers=self.settings.model_max_concurrency,
            thread_name_prefix="llmclient-model",
        )

    async def aclose(self) -> None:
        """关闭共享 HTTP 连接池并停止接收新的 llmclient 线程任务。"""
        await self._mep_transport.aclose()
        self._llmclient_executor.shutdown(wait=False, cancel_futures=False)

    async def generate(
        self,
        backend: ModelBackend,
        messages: list[dict[str, str]],
    ) -> str:
        """取得共享并发令牌后调用指定模型后端。"""
        queue_started_at = time.perf_counter()
        queue_timeout = self.settings.model_queue_timeout_seconds
        try:
            async with asyncio.timeout(queue_timeout):
                await self._semaphore.acquire()
        except TimeoutError as exc:
            logger.error(
                f"{_MODULE} queue_timeout backend={backend} "
                f"timeout_seconds={queue_timeout} exception={exc!r}"
            )
            raise ModelTransportError(
                f"model concurrency queue timed out after {queue_timeout}s",
                code="MODEL_QUEUE_TIMEOUT",
            ) from exc

        queue_duration_ms = round((time.perf_counter() - queue_started_at) * 1000, 2)
        logger.info(
            f"{_MODULE} permit_acquired backend={backend} "
            f"queue_duration_ms={queue_duration_ms}"
        )
        execution_started_at = time.perf_counter()
        execution_status = "failed"
        try:
            if backend == "mep":
                result = await self._generate_mep(messages)
            else:
                result = await self._generate_llmclient(messages)
            execution_status = "success"
            return result
        finally:
            self._semaphore.release()
            execution_duration_ms = round(
                (time.perf_counter() - execution_started_at) * 1000,
                2,
            )
            logger.info(
                f"{_MODULE} permit_released backend={backend} "
                f"execution_status={execution_status} "
                f"execution_duration_ms={execution_duration_ms}"
            )

    async def _generate_mep(self, messages: list[dict[str, str]]) -> str:
        timeout = self.settings.model_request_timeout_seconds
        try:
            async with asyncio.timeout(timeout):
                return await self._mep_transport.generate(messages)
        except TimeoutError as exc:
            logger.error(
                f"{_MODULE} request_timeout backend=mep timeout_seconds={timeout} "
                f"exception={exc!r} traceback={traceback.format_exc()}"
            )
            raise ModelTransportError(
                f"model request timed out after {timeout}s",
                code="MODEL_REQUEST_TIMEOUT",
            ) from exc

    async def _generate_llmclient(self, messages: list[dict[str, str]]) -> str:
        """在线程中运行原 llmclient，并在超时后继续持有令牌直至真实调用结束。"""
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            self._llmclient_executor,
            self._llmclient_transport.generate,
            messages,
        )
        timeout = self.settings.model_request_timeout_seconds
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except TimeoutError as exc:
            logger.error(
                f"{_MODULE} request_timeout backend=llmclient timeout_seconds={timeout} "
                "waiting_for_physical_completion=true"
            )
            await self._finish_timed_out_llmclient(future)
            raise ModelTransportError(
                f"model request timed out after {timeout}s",
                code="MODEL_REQUEST_TIMEOUT",
            ) from exc
        except asyncio.CancelledError:
            logger.warning(
                f"{_MODULE} llmclient_wait_cancelled "
                "waiting_for_physical_completion=true"
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
