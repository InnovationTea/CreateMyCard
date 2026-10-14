"""小卡文字压力估计供修复使用，不作为发布门禁。"""

from __future__ import annotations

import logging
from typing import Any

from services.card_validation.compact_validation.semantic.layout.text_width import (
    _collect_text_width_budget_errors,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    DataRow,
    build_compact_data_model,
    expand_high_level_component_rows,
    parse_compact_dsl_rows,
)

logger = logging.getLogger(__name__)


def small_card_text_pressure(source: str, task_spec: dict[str, Any]) -> list[str]:
    """同行自然标签的估计只交给错误修复，不当精确字体测量的发布门禁。"""
    if task_spec.get("size") != "2x2":
        return []
    try:
        rows = parse_compact_dsl_rows(source)
        components = [row for row in rows if isinstance(row, ComponentRow)]
        data_rows = [row for row in rows if isinstance(row, DataRow)]
        data_model = build_compact_data_model(data_rows)
        components = expand_high_level_component_rows(components, size="2x2", data_model=data_model)
        messages: list[str] = []
        _collect_text_width_budget_errors(
            components,
            task_spec,
            {"suggestSize": "2x2"},
            messages,
            None,
            include_label_pressure=True,
        )
        return messages
    except ValueError as exc:
        logger.debug("Small-card pressure unavailable: %s: %s", type(exc).__name__, exc)
        return []
