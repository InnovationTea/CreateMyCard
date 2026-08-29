"""旧 Python Terse 模板流水线的显式诊断入口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from models.generation import WidgetSize
from services.generation_pipeline import GenerationRoutePolicy

ModelStartCallback = Callable[[WidgetSize], Awaitable[None]]


async def route_legacy_python_terse_generation(
    host: Any,
    request: Any,
    policy: GenerationRoutePolicy,
    *,
    before_model_call: ModelStartCallback | None = None,
) -> Any:
    """仅用于定位新旧模板差异；生产默认路由不得调用此入口。"""
    if before_model_call is None:
        return await host._generate_widget_card_with_policy(request, policy)
    return await host._generate_widget_card_with_policy(
        request,
        policy,
        before_model_call=before_model_call,
    )
