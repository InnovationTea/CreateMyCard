from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BridgeResult:
    """一次 JSX 生成及 A2UI 转换的完整结果。"""

    component_name: str
    jsx: str
    source: str
    a2ui_messages: tuple[dict[str, Any], ...]
    turns: int
    elapsed_seconds: float
    failed_submissions: int
    repair_calls: int
    warnings: tuple[dict[str, Any], ...]
