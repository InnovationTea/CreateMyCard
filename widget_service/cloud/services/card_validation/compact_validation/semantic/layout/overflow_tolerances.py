# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""加载并校验 Compact 布局溢出的经验容忍阈值。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_OVERFLOW_TOLERANCES_PATH = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "validator_rules"
    / "compact"
    / "layout_overflow_tolerances.json"
)

_SUPPORTED_SIZES = frozenset({"2x2", "2x4"})
_HEIGHT_SCENARIOS = frozenset(
    {
        "root_column",
        "column_weighted_by_parent_column",
        "column_overflow_absorbable_by_item_margin",
    }
)
_WIDTH_SCENARIOS = {
    "compressibleItemMargin": "row_overflow_fully_absorbable_by_item_margin",
    "rootFlexibleLayout": "root_row",
    "weightedFlexibleLayout": ("row_inside_horizontal_weight_region_without_fixed_width_boundary"),
}


class OverflowToleranceConfigError(ValueError):
    """布局溢出容忍阈值配置缺失或不合法。"""


@dataclass(frozen=True)
class SizeOverflowLimits:
    two_by_two: float
    two_by_four: float

    def for_size(self, size: str) -> float | None:
        """返回指定尺寸的 vp 阈值。"""
        result: float | None = None
        if size == "2x2":
            result = self.two_by_two
        elif size == "2x4":
            result = self.two_by_four
        return result


@dataclass(frozen=True)
class LayoutOverflowTolerances:
    unit: str
    supported_sizes: frozenset[str]
    height_maximum: float
    width_compressible_item_margin: SizeOverflowLimits
    width_root_flexible_layout: SizeOverflowLimits
    width_weighted_flexible_layout: SizeOverflowLimits


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OverflowToleranceConfigError(f"Duplicate layout overflow tolerance key: {key}")
        result[key] = value
    return result


def _required_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OverflowToleranceConfigError(f"{location} must be an object")
    return value


def _required_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OverflowToleranceConfigError(f"{location} must be a non-empty string")
    return value


def _non_negative_number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OverflowToleranceConfigError(f"{location} must be a non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise OverflowToleranceConfigError(f"{location} must be a non-negative number")
    return number


def _validate_supported_sizes(value: Any) -> frozenset[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise OverflowToleranceConfigError("supportedSizes must be an array of strings")
    sizes = frozenset(value)
    if len(sizes) != len(value) or sizes != _SUPPORTED_SIZES:
        raise OverflowToleranceConfigError("supportedSizes must contain 2x2 and 2x4 exactly once")
    return sizes


def _validate_height(value: Any) -> float:
    section = _required_object(value, "height")
    if set(section) != {"maximumOverflow", "appliesTo", "description"}:
        raise OverflowToleranceConfigError("height contains unsupported fields")
    scenarios = section.get("appliesTo")
    if not isinstance(scenarios, list) or any(not isinstance(item, str) for item in scenarios):
        raise OverflowToleranceConfigError("height.appliesTo must be an array of strings")
    if len(scenarios) != len(set(scenarios)) or frozenset(scenarios) != _HEIGHT_SCENARIOS:
        raise OverflowToleranceConfigError("height.appliesTo contains unsupported scenarios")
    _required_string(section.get("description"), "height.description")
    return _non_negative_number(section.get("maximumOverflow"), "height.maximumOverflow")


def _size_limits(value: Any, location: str, expected_scenario: str) -> SizeOverflowLimits:
    section = _required_object(value, location)
    if set(section) != {"maximumOverflowBySize", "appliesTo", "description"}:
        raise OverflowToleranceConfigError(f"{location} contains unsupported fields")
    scenario = _required_string(section.get("appliesTo"), f"{location}.appliesTo")
    if scenario != expected_scenario:
        raise OverflowToleranceConfigError(f"{location}.appliesTo is unsupported")
    _required_string(section.get("description"), f"{location}.description")
    limits = _required_object(
        section.get("maximumOverflowBySize"),
        f"{location}.maximumOverflowBySize",
    )
    if set(limits) != _SUPPORTED_SIZES:
        raise OverflowToleranceConfigError(
            f"{location}.maximumOverflowBySize must contain only 2x2 and 2x4"
        )
    return SizeOverflowLimits(
        two_by_two=_non_negative_number(limits.get("2x2"), f"{location}.maximumOverflowBySize.2x2"),
        two_by_four=_non_negative_number(
            limits.get("2x4"), f"{location}.maximumOverflowBySize.2x4"
        ),
    )


def load_layout_overflow_tolerances(path: Path) -> LayoutOverflowTolerances:
    """读取配置并拒绝缺失、重复、非有限或适用场景不匹配的阈值。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as exc:
        raise OverflowToleranceConfigError(
            f"Unable to load layout overflow tolerances: {path}"
        ) from exc
    root = _required_object(payload, "layout overflow tolerances")
    if set(root) != {"unit", "supportedSizes", "height", "width"}:
        raise OverflowToleranceConfigError("layout overflow tolerances contain unsupported fields")
    unit = _required_string(root.get("unit"), "unit")
    if unit != "vp":
        raise OverflowToleranceConfigError("unit must be vp")
    supported_sizes = _validate_supported_sizes(root.get("supportedSizes"))
    height_maximum = _validate_height(root.get("height"))
    width = _required_object(root.get("width"), "width")
    if set(width) != set(_WIDTH_SCENARIOS):
        raise OverflowToleranceConfigError("width contains unsupported scenarios")
    return LayoutOverflowTolerances(
        unit=unit,
        supported_sizes=supported_sizes,
        height_maximum=height_maximum,
        width_compressible_item_margin=_size_limits(
            width.get("compressibleItemMargin"),
            "width.compressibleItemMargin",
            _WIDTH_SCENARIOS.get("compressibleItemMargin", ""),
        ),
        width_root_flexible_layout=_size_limits(
            width.get("rootFlexibleLayout"),
            "width.rootFlexibleLayout",
            _WIDTH_SCENARIOS.get("rootFlexibleLayout", ""),
        ),
        width_weighted_flexible_layout=_size_limits(
            width.get("weightedFlexibleLayout"),
            "width.weightedFlexibleLayout",
            _WIDTH_SCENARIOS.get("weightedFlexibleLayout", ""),
        ),
    )


@lru_cache(maxsize=1)
def layout_overflow_tolerances() -> LayoutOverflowTolerances:
    """返回进程内缓存的已校验配置。"""
    return load_layout_overflow_tolerances(DEFAULT_OVERFLOW_TOLERANCES_PATH)
