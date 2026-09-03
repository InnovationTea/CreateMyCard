from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeOptions:
    """JSX 生成、校验和修复参数的统一入口。"""

    max_turns: int = 20
    max_tokens: int = 8192
    request_timeout: float = 120.0
    max_browser_repairs: int = 5
    browser_validation: bool = False
    validation_enabled: bool = True
    layout_budget_validation: bool = True
    validate_dynamic_values: bool = True
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
        if self.max_browser_repairs < 0:
            raise ValueError("max_browser_repairs must be non-negative")
        if self.submit_mode not in {"auto", "direct"}:
            raise ValueError("submit_mode must be 'auto' or 'direct'")
