# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Regression coverage for formatted readings in compiled template columns."""
from typing import Any

import pytest

from services.card_validation.compact_dsl_validator import _collect_hero_value_errors
from services.compact_dsl_a2ui_converter import ComponentRow


def _fixture(
    font: int = 24, height: int = 34, content: Any = "{{ ${/data/battery/value} }}"
) -> tuple[list[ComponentRow], dict[str, Any]]:
    rows = [
        ComponentRow("root", "Stack", {"width": 160}, ("inset",)),
        ComponentRow("inset", "Stack", {"width": "matchParent", "padding": 12}, ("column",)),
        ComponentRow("column", "Column", {"width": "matchParent"}, ("value",)),
        ComponentRow("value", "Text", {
            "width": "matchParent", "height": height, "fontSize": font,
            "maxLines": 1, "content": content,
        }),
    ]
    spec = {"size": "2x2", "dataModelSchema": {"data": {"battery": {"value": {
        "type": "string", "description": "当前电量，单位 %", "sampleValue": "68%",
    }}}}}
    return rows, spec


def _errors(rows: list[ComponentRow], spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _collect_hero_value_errors(rows, spec, errors)
    return errors


@pytest.mark.parametrize("content", [{"path": "/data/battery/value"},
                                     "{{ ${/data/battery/value} }}"])
@pytest.mark.parametrize(("font", "height"), [(20, 28), (24, 34)])
def test_direct_formatted_reading_accepts_equivalent_bindings(
    content: Any, font: int, height: int
) -> None:
    rows, spec = _fixture(font, height, content)
    assert not _errors(rows, spec)


@pytest.mark.parametrize(("font", "height"), [(20, 27), (24, 32), (24, 33), (30, 40)])
def test_formatted_reading_still_enforces_font_and_height(font: int, height: int) -> None:
    rows, spec = _fixture(font, height)
    assert _errors(rows, spec)


@pytest.mark.parametrize("content", [
    "{{ ${/data/battery/value} + '剩余' }}", "{{ ${/data/battery/value} * 1 }}", "68%",
])
def test_only_a_single_direct_reference_is_accepted(content: str) -> None:
    rows, spec = _fixture(content=content)
    assert _errors(rows, spec)


@pytest.mark.parametrize(("sample", "description", "font", "height", "accepted"), [
    ("29.0 ℃", "电池温度", 20, 28, True),
    ("7小时1分", "睡眠时长", 20, 28, True),
    ("7小时1分", "睡眠时长", 24, 34, False),
    ("2026年9月20日", "日期", 20, 28, False),
    ("23:15", "入睡时刻", 20, 28, False),
    ("正常", "电池健康状态", 20, 28, False),
    ("我的耳机", "耳机名称", 24, 34, False),
])
def test_semantic_and_pressure_limits_remain_enforced(
    sample: str, description: str, font: int, height: int, accepted: bool
) -> None:
    rows, spec = _fixture(font, height)
    spec["dataModelSchema"] = {"data": {"battery": {"value": {
        "type": "string", "sampleValue": sample, "description": description,
    }}}}
    assert (not _errors(rows, spec)) is accepted


@pytest.mark.parametrize("obstacle", [
    "narrow", "padding", "margin", "row", "unknown", "cycle", "multiple", "multiline",
    "two-businesses",
])
def test_full_width_and_single_business_are_required(obstacle: str) -> None:
    rows, spec = _fixture()
    if obstacle == "narrow":
        rows[0].props["width"] = 150
    elif obstacle == "padding":
        rows[2].props["padding"] = {"left": 1}
    elif obstacle == "margin":
        rows[2].props["margin"] = {"right": 1}
    elif obstacle == "row":
        rows[2] = ComponentRow("column", "Row", {"width": "matchParent"}, ("value",))
    elif obstacle == "unknown":
        rows[0].props.pop("width")
    elif obstacle == "cycle":
        rows[0] = ComponentRow("root", "Stack", {"width": "matchParent"}, ("inset",))
        rows.append(ComponentRow("loop", "Stack", {"width": "matchParent"}, ("root",)))
        rows[1] = ComponentRow("inset", "Stack", {"width": "matchParent"}, ("loop", "column"))
    elif obstacle == "multiple":
        rows.append(ComponentRow("other", "Column", {"width": 136}, ("value",)))
    elif obstacle == "multiline":
        rows[3].props["maxLines"] = 2
    else:
        spec["dataModelSchema"] = {"data": {"battery": {}, "weather": {}}}
    assert _errors(rows, spec)


@pytest.mark.parametrize("content", [{"path": "/data/battery/value"},
                                     "{{ ${/data/battery/value} }}"])
def test_pure_numeric_value_keeps_30fp(content: Any) -> None:
    rows, spec = _fixture(30, 40, content)
    spec["dataModelSchema"] = {"data": {"battery": {"value": {
        "type": "integer", "sampleValue": 68, "description": "当前电量",
    }}}}
    assert not _errors(rows, spec)
