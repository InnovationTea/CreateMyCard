"""Display-only suffixes; source values and their types remain authoritative."""

from __future__ import annotations

import math
import re
import unicodedata
from decimal import Decimal
from typing import Any


UNIT_ALIASES = {
    "%": ("%", "％"),
    "℃": ("℃", "°C", "摄氏度"),
    "分钟": ("分钟", "分"),
    "次/分钟": ("次/分钟", "次／分钟", "次/分", "次／分", "bpm"),
}
_NUMBER_TEXT = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")


def is_unitless_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        return _NUMBER_TEXT.fullmatch(value.strip()) is not None
    return False


def format_display_unit(value: Any, unit: str | None) -> Any:
    if not unit or not is_unitless_number(value):
        return value
    return f"{display_number_text(value)}{unit}"


def repeats_numeric_unit(value: Any, unit: Any) -> bool:
    """Only suppress an explicit unit already present on a numeric display."""
    if not isinstance(value, str) or not isinstance(unit, str):
        return False
    normalized_value = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized_unit = unicodedata.normalize("NFKC", unit).strip().casefold()
    if not normalized_unit or not normalized_value.endswith(normalized_unit):
        return False
    return is_unitless_number(normalized_value[:-len(normalized_unit)])


def display_number_text(value: int | float | str) -> str:
    """Match JavaScript number display while preserving string precision."""
    if not isinstance(value, float):
        return str(value).strip()
    if value == 0:
        return "0"
    if 1e-6 <= abs(value) < 1e21:
        if value.is_integer():
            return str(int(value))
        return format(Decimal(repr(value)), "f").rstrip("0").rstrip(".")
    mantissa, exponent = repr(value).lower().split("e")
    return f"{mantissa.removesuffix('.0')}e{int(exponent):+d}"


def has_display_unit(value: Any, unit: str) -> bool:
    if not isinstance(value, str):
        return False
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    for alias in UNIT_ALIASES.get(unit, (unit,)):
        suffix = unicodedata.normalize("NFKC", alias).casefold()
        if normalized.endswith(suffix):
            return True
    return False
