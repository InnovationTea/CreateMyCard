# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验器兼容导出；规则实现位于 compact_validation。"""

from .compact_validation.api import validate_compact_dsl
from .compact_validation.compatibility.hero import (
    _collect_hero_value_errors as _collect_hero_value_errors,
)
from .compact_validation.diagnostics import (
    CompactDslValidationError,
    CompactDslValidationResult,
)
from .compact_validation.flows.text_pressure import small_card_text_pressure

__all__ = [
    "CompactDslValidationError",
    "CompactDslValidationResult",
    "validate_compact_dsl",
    "small_card_text_pressure",
]
