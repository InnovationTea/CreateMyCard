from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass

from ..jsx_runner.agent import PLAN_MAX_TOKENS


@dataclass(frozen=True, slots=True)
class BridgeOptions:
    """JSX 生成、校验和修复参数的统一入口。"""

    max_turns: int = 20
    max_tokens: int = 8192
    request_timeout: float = 120.0
    browser_fallback_after: int = 3
    browser_validation: bool = True
    validation_enabled: bool = True
    layout_budget_validation: bool = False
    validate_dynamic_values: bool = True
    validate_non_empty_data_ids: bool = True
    enable_dynamic_data_binding: bool = True
    include_few_shot: bool = False
    plan_max_tokens: int = PLAN_MAX_TOKENS
    submit_mode: str = "direct"
    thinking_mode: str = "disable"
    verbose: bool = True

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns must be positive")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if self.browser_fallback_after < 0:
            raise ValueError("browser_fallback_after must be non-negative")
        if not 1 <= self.plan_max_tokens <= PLAN_MAX_TOKENS:
            raise ValueError(f"plan_max_tokens must be between 1 and {PLAN_MAX_TOKENS}")
        if self.submit_mode not in {"auto", "direct"}:
            raise ValueError("submit_mode must be 'auto' or 'direct'")
