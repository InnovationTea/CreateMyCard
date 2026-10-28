"""创建请求的内容策略与显式准入上下文；默认保持原链路。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

STATIC_COMPONENTS = frozenset({"TextList", "SingleLineList", "ComparisonGroup"})
STATIC_LAYOUTS = {"2x2": "S-static-content", "2x4": "W-static-content"}
STATIC_SUPPORT_COMPONENTS = frozenset(
    {"SingleLineTitle", "EmphasisText"}
)
STATIC_ACTION_LAYOUTS: dict[str, tuple[str, ...]] = {}


@dataclass(frozen=True)
class GenerationContentPolicy:
    """同一次请求固定使用一个内容合同，不能由模型或 DSL 标记授权。"""

    mode: str = "existing"
    version: str = "existing-v1"

    @property
    def is_static(self) -> bool:
        return self.mode == "static_content"


EXISTING_CONTENT_POLICY = GenerationContentPolicy()
STATIC_CONTENT_POLICY = GenerationContentPolicy(mode="static_content", version="static-content-v1")
_POLICY = ContextVar("generation_content_policy", default=EXISTING_CONTENT_POLICY)


def current_content_policy() -> GenerationContentPolicy:
    return _POLICY.get()


def activate_request_policy(policy: GenerationContentPolicy) -> None:
    """仅在 isolated_content_request 的生命周期内切换已预检请求。"""
    _POLICY.set(policy)


def isolated_content_request[**P, R](
    operation: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    @wraps(operation)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        with content_policy_scope(EXISTING_CONTENT_POLICY):
            return await operation(*args, **kwargs)

    return wrapped


@contextmanager
def content_policy_scope(policy: GenerationContentPolicy) -> Iterator[None]:
    """请求、异步任务与工作线程之间隔离准入，不修改共享注册表。"""
    token = _POLICY.set(policy)
    try:
        yield
    finally:
        _POLICY.reset(token)


def resolve_content_policy(
    *,
    operation: str,
    enabled: bool,
    is_edit: bool,
    requested_data: bool,
    effective_data: bool,
    requested_events: bool,
    effective_events: bool,
    single_step: bool = False,
) -> GenerationContentPolicy:
    """只识别预检成功且无数据、无事件的请求，不用空候选掩盖能力失败。"""
    result = EXISTING_CONTENT_POLICY
    eligible = operation == "generateWidgetCardCompactDsl" and enabled
    if not eligible or is_edit or single_step:
        return result
    if requested_data or effective_data:
        return result
    if requested_events or effective_events:
        return result
    return STATIC_CONTENT_POLICY


def effective_layout_scope(size: str) -> str:
    prefix = "S" if size == "2x2" else "W"
    suffix = "static-content-guided" if current_content_policy().is_static else "plan-guided"
    return f"{prefix}-{suffix}"


def static_components_for_size(size: str) -> tuple[str, ...]:
    result = ("TextList", "SingleLineList", "EmphasisText")
    if size == "2x4":
        result += ("ComparisonGroup",)
    return result


def static_model_components(size: str) -> frozenset[str]:
    return frozenset(static_components_for_size(size)) | STATIC_SUPPORT_COMPONENTS


def static_layout_ids(size: str) -> tuple[str, ...]:
    identifier = STATIC_LAYOUTS.get(size)
    if identifier is None:
        return ()
    return (identifier,)
