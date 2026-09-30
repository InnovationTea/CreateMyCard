"""可选修复建议：显式专用函数、静态默认配置、无建议三条路径。"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.logger import logger

from .diagnostics import CompactDiagnostic
from .rule_catalog import RULE_CODES


@dataclass(frozen=True)
class RepairGuidanceContext:
    """调用方明确提供的本轮条件，未知信息不自动转换成 false。"""

    mode: str | None = None
    constraints: Mapping[str, Any] = field(default_factory=dict)


HintBuilder = Callable[[CompactDiagnostic, RepairGuidanceContext | None], str | None]
# 只有真实条件来源已接通时才在此显式登记；不从配置导入函数。
HINT_BUILDERS: tuple[tuple[str, HintBuilder], ...] = ()
DEFAULT_HINT_PATH = (
    Path(__file__).resolve().parents[3] / "data/validator_rules/compact/repair_hints.json"
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate repair hint key: {key}")
        result[key] = value
    return result


def load_default_hints(path: Path) -> dict[str, str]:
    """严格检查配置；供交付校验直接调用，错误不得被测试忽略。"""
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("Compact repair hints must be an object")
    for code, hint in value.items():
        if code not in RULE_CODES:
            raise ValueError(f"Unknown Compact rule code: {code}")
        if not isinstance(hint, str) or not hint.strip():
            raise ValueError(f"Repair hint must be a non-empty string: {code}")
    return value


@lru_cache(maxsize=1)
def _default_hints(path: Path) -> dict[str, str]:
    return load_default_hints(path)


def validate_builders(entries: tuple[tuple[str, HintBuilder], ...]) -> dict[str, HintBuilder]:
    builders: dict[str, HintBuilder] = {}
    for code, builder in entries:
        if code not in RULE_CODES:
            raise ValueError(f"Unknown Compact hint builder code: {code}")
        if code in builders:
            raise ValueError(f"Duplicate Compact hint builder: {code}")
        if not callable(builder):
            raise TypeError(f"Compact hint builder is not callable: {code}")
        builders[code] = builder
    return builders


def resolve_fix_hint(
    diagnostic: CompactDiagnostic, context: RepairGuidanceContext | None = None
) -> str | None:
    """建议异常仅隔离在本函数内，不扩大校验器的异常捕获范围。"""
    hint: str | None = None
    try:
        builder = validate_builders(HINT_BUILDERS).get(diagnostic.code)
        if builder is not None:
            hint = builder(deepcopy(diagnostic), deepcopy(context))
            if hint is not None and (not isinstance(hint, str) or not hint.strip()):
                raise ValueError("Compact hint builder returned an invalid hint")
    except Exception as exc:
        logger.warning(
            "Compact hint builder failed: {} {}: {}", diagnostic.code, type(exc).__name__, exc
        )
        hint = None
    if hint is not None:
        logger.debug("Compact hint source=builder code={}", diagnostic.code)
        return hint
    try:
        hint = _default_hints(DEFAULT_HINT_PATH).get(diagnostic.code)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Compact default hints unavailable: {}: {}", type(exc).__name__, exc)
    logger.debug(
        "Compact hint source={} code={}", "default" if hint is not None else "none", diagnostic.code
    )
    return hint
