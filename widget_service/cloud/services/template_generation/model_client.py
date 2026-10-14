"""模板路由专用模型适配器，不改变原有 A2UI 模型客户端。"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

import json_repair

from app.logger import logger
from config.config import get_settings
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient
from models.generation import ModelRequestContext
from services.generation_trace_recorder import trace_increment_retry, trace_record


class TemplateModelUnavailable(RuntimeError):
    """当前运行方式没有可用于模板判断的真实模型。"""


class TemplateModelClient:
    """复用 dev 的模型运行时，但只暴露模板引擎需要的两个窄接口。"""

    def __init__(
        self,
        runtime: ModelExecutionRuntime,
        request_context: ModelRequestContext,
    ) -> None:
        settings = get_settings()
        self._backend = settings.design_compact_model_backend
        self._request_context = request_context
        self._client = UnifiedModelClient(
            settings,
            runtime,
            operation_name="generateWidgetCardCompactDsl.template",
        )
        # 第二层由模板内部控制最多两次调用，避免叠加公共重试和主备预算。
        self._body_client = UnifiedModelClient(
            settings.model_copy(update={"enable_model_failure_retry": False}),
            runtime,
            operation_name="generateWidgetCardCompactDsl.template.body",
        )
        self._settings = settings
        self._sleep = asyncio.sleep
        self._random_uniform = random.uniform

    async def generate_json(
        self,
        prompt: list[dict[str, str]],
        *,
        phase: str,
    ) -> dict[str, Any]:
        raw = await self._generate_raw(prompt, phase)
        return _parse_json_object(raw)

    async def generate(
        self,
        prompt: list[dict[str, str]],
        _profile: dict[str, Any] | None = None,
        *,
        phase: str = "advanced-mixed-body",
        **_kwargs: Any,
    ) -> str:
        raw = await self._generate_raw(prompt, phase)
        return _strip_markdown_fence(raw)

    async def _generate_raw(
        self,
        prompt: list[dict[str, str]],
        phase: str,
    ) -> str:
        logger.info(
            f"[Template Model Prompt] phase={phase} messages="
            f"{json.dumps(prompt, ensure_ascii=False)}"
        )
        if phase in {"advanced-mixed-body", "advanced-mixed-body-repair"}:
            return await self._generate_body(prompt, phase)
        return await self._client.generate(
            self._backend,
            prompt,
            self._request_context,
            phase=phase,
        )

    async def _generate_body(self, prompt: list[dict[str, str]], phase: str) -> str:
        for attempt in (1, 2):
            try:
                return await self._body_client.generate(
                    self._backend, prompt, self._request_context, phase=phase,
                )
            except ModelTransportError as exc:
                if exc.code != "MODEL_EMPTY_OUTPUT" or attempt == 2:
                    raise
                maximum = self._settings.model_failure_retry_max_delay_seconds
                delay = min(self._settings.model_failure_retry_initial_delay_seconds, maximum)
                jitter = delay * self._settings.model_failure_retry_jitter_ratio
                delay = round(self._random_uniform(
                    max(0.0, delay - jitter), min(maximum, delay + jitter),
                ), 3)
                trace_increment_retry("templateEmptyOutputRetries")
                trace_record(
                    "template.empty_output_retry", stage="template.model", status="started",
                    details={"phase": phase, "nextAttempt": 2, "backoffMs": delay * 1000},
                )
                logger.warning(
                    f"[Template Model] empty_output_retry phase={phase} "
                    f"next_attempt=2 delay_seconds={delay}"
                )
                await self._sleep(delay)
        raise AssertionError("template body retry loop exited unexpectedly")


def create_template_model_client(
    runtime: ModelExecutionRuntime | None,
    request_context: ModelRequestContext,
) -> TemplateModelClient:
    """真实模型关闭时保持 dev 原有 mock 路由，不让模板测试污染既有用例。"""
    if runtime is None or get_settings().enable_a2ui_model_mock:
        raise TemplateModelUnavailable("template routing requires the real shared model runtime")
    return TemplateModelClient(runtime, request_context)


def _parse_json_object(raw: str) -> dict[str, Any]:
    candidate = _strip_markdown_fence(raw)
    _prefix, opening, remainder = candidate.partition("{")
    body, closing, _suffix = remainder.rpartition("}")
    if not opening or not closing:
        raise ValueError("template decision response does not contain a JSON object")
    candidate = opening + body + closing
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = json_repair.loads(candidate)
    if not isinstance(value, dict):
        raise ValueError("template decision response must be a JSON object")
    return value


def _strip_markdown_fence(raw: str) -> str:
    value = raw.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return "\n".join(lines[1:]).strip()
