"""模板路由专用模型适配器，不改变原有 A2UI 模型客户端。"""

from __future__ import annotations

import json
from typing import Any

import json_repair

from config.config import get_settings
from custom.model_runtime import ModelExecutionRuntime
from custom.unified_model_client import UnifiedModelClient
from models.generation import ModelRequestContext


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
        return await self._client.generate(
            self._backend,
            prompt,
            self._request_context,
            phase=phase,
        )


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
