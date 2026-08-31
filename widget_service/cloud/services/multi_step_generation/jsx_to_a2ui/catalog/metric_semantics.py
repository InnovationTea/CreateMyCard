from __future__ import annotations

import re
from typing import Any


_BARE_METRIC = re.compile(
    r"^\s*[+-]?(?:\d+(?:\.\d+)?(?:(?:%|°|℃|°C|GB|MB|KB|分|天|小时|分钟))?|\d{1,2}:\d{2})\s*$",
    re.IGNORECASE,
)
_SELF_DESCRIBING_METRIC = re.compile(
    r"^\s*(?:[+-]?\d+(?:\.\d+)?(?:°|℃|°C)|\d{1,2}:\d{2})\s*$",
    re.IGNORECASE,
)
_AMBIGUOUS_STATUS_VALUES = frozenset({
    "优",
    "良",
    "正常",
    "异常",
    "高",
    "低",
    "是",
    "否",
    "开启",
    "关闭",
})
def metric_requires_label(value: Any) -> bool:
    """Return whether a value is ambiguous without a nearby static label."""
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return True
    normalized = value.strip()
    if _SELF_DESCRIBING_METRIC.fullmatch(normalized) is not None:
        return False
    return (
        not normalized
        or _BARE_METRIC.fullmatch(normalized) is not None
        or normalized in _AMBIGUOUS_STATUS_VALUES
    )
