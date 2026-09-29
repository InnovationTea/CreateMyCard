"""Compact 参考画布只用于静态预算，端侧布局始终由宿主决定。"""

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _default_profile() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data/protocol_profiles/design-compact-dsl/protocol.json"
    )
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("Compact protocol profile must be an object.")
    return profile


def reference_dimension(size: str, axis: str, profile: dict[str, Any] | None = None) -> float:
    """读当前 profile 的参考值，不猜测未知尺寸或向渲染产物注入宽高。"""
    source = _default_profile() if profile is None else profile
    sizes = source.get("sizes")
    dimensions = sizes.get(size) if isinstance(sizes, dict) else None
    value = dimensions.get(axis) if isinstance(dimensions, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Compact reference {size}.{axis} must be a positive number.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Compact reference {size}.{axis} must be a positive number.")
    return float(value)
