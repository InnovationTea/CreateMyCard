"""Compact 布局溢出经验阈值配置及加载校验。"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from services.card_validation.compact_validation.semantic.layout.overflow_tolerances import (
    DEFAULT_OVERFLOW_TOLERANCES_PATH,
    OverflowToleranceConfigError,
    load_layout_overflow_tolerances,
)


def _default_payload() -> dict:
    payload = json.loads(DEFAULT_OVERFLOW_TOLERANCES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_payload(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_default_overflow_tolerances_keep_current_vp_boundaries() -> None:
    tolerances = load_layout_overflow_tolerances(DEFAULT_OVERFLOW_TOLERANCES_PATH)

    assert tolerances.unit == "vp"
    assert tolerances.supported_sizes == {"2x2", "2x4"}
    assert tolerances.width_compressible_item_margin.for_size("2x2") == 16
    assert tolerances.width_compressible_item_margin.for_size("2x4") == 16
    assert tolerances.width_root_flexible_layout.for_size("2x2") == 10
    assert tolerances.width_root_flexible_layout.for_size("2x4") == 32
    assert tolerances.width_weighted_flexible_layout.for_size("2x2") == 24
    assert tolerances.width_weighted_flexible_layout.for_size("2x4") == 52
    assert tolerances.width_root_flexible_layout.for_size("4x2") is None


def test_rejects_retired_height_tolerance_section(tmp_path: Path) -> None:
    payload = deepcopy(_default_payload())
    payload["height"] = {"maximumOverflow": 35}
    path = _write_payload(tmp_path / "retired-height.json", payload)

    with pytest.raises(
        OverflowToleranceConfigError,
        match="layout overflow tolerances contain unsupported fields",
    ):
        load_layout_overflow_tolerances(path)


def test_rejects_missing_size_threshold(tmp_path: Path) -> None:
    payload = deepcopy(_default_payload())
    width = payload.get("width")
    assert isinstance(width, dict)
    weighted = width.get("weightedFlexibleLayout")
    assert isinstance(weighted, dict)
    limits = weighted.get("maximumOverflowBySize")
    assert isinstance(limits, dict)
    limits.pop("2x4", None)
    path = _write_payload(tmp_path / "missing-size.json", payload)

    with pytest.raises(
        OverflowToleranceConfigError,
        match="must contain only 2x2 and 2x4",
    ):
        load_layout_overflow_tolerances(path)


def test_rejects_unregistered_scenario(tmp_path: Path) -> None:
    payload = deepcopy(_default_payload())
    width = payload.get("width")
    assert isinstance(width, dict)
    weighted = width.get("weightedFlexibleLayout")
    assert isinstance(weighted, dict)
    weighted["appliesTo"] = "any_weighted_ancestor"
    path = _write_payload(tmp_path / "invalid-scenario.json", payload)

    with pytest.raises(
        OverflowToleranceConfigError,
        match="width.weightedFlexibleLayout.appliesTo is unsupported",
    ):
        load_layout_overflow_tolerances(path)


def test_rejects_duplicate_configuration_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"unit":"vp","unit":"px"}', encoding="utf-8")

    with pytest.raises(
        OverflowToleranceConfigError,
        match="Duplicate layout overflow tolerance key: unit",
    ):
        load_layout_overflow_tolerances(path)
