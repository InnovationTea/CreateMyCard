# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""单位校验只消费连续相邻的静态 Text，不跨越其他组件。"""

from types import SimpleNamespace

import pytest

from services.card_validation.diagnostics import Reporter
from services.card_validation.display_unit_validator import DisplayUnitValidator


def _validate_siblings(
    content: str,
    siblings: list[dict],
    *,
    units: tuple[str, ...] = ("天",),
    unit_included: bool = False,
) -> Reporter:
    children = ["value"]
    components = [{"id": "value", "component": "Text", "content": content}]
    for index, sibling in enumerate(siblings):
        component_id = f"sibling_{index}"
        children.append(component_id)
        components.append({**sibling, "id": component_id})
    components.append({"id": "root", "component": "Column", "children": children})
    components_by_id = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        components_by_id[component_id] = component
    context = SimpleNamespace(
        components=components,
        components_by_id=components_by_id,
        cardspec={
            "dataBindings": [{"capabilityId": "Countdown", "writeResultTo": "/data/countdown"}]
        },
        effective_data_capabilities=[
            {
                "id": "Countdown",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "countdownDays": {
                            "type": "string" if unit_included else "integer",
                            "displayUnits": list(units),
                            "unitIncluded": unit_included,
                        }
                    },
                },
            }
        ],
    )
    reporter = Reporter()
    DisplayUnitValidator().validate(context, {}, reporter)
    return reporter


@pytest.mark.parametrize(
    "barrier",
    [
        pytest.param({"component": "Divider"}, id="divider"),
        pytest.param({"component": "Image"}, id="image"),
        pytest.param({"component": "Column", "children": []}, id="container"),
        pytest.param({"component": "Button", "label": "天"}, id="button"),
        pytest.param({"component": "Divider", "content": "天"}, id="non-text-with-content"),
        pytest.param({"component": "Text"}, id="missing-content"),
        pytest.param({"component": "Text", "content": None}, id="null-content"),
        pytest.param({"component": "Text", "content": 1}, id="numeric-content"),
        pytest.param({"component": "Text", "content": False}, id="boolean-content"),
        pytest.param({"component": "Text", "content": []}, id="list-content"),
        pytest.param({"component": "Text", "content": {"path": "/other"}}, id="path-content"),
        pytest.param({"component": "Text", "content": "其他信息"}, id="unrelated-text"),
        pytest.param(
            {"component": "Text", "content": "{{ ${/other} + '天' }}"}, id="dynamic-text"
        ),
    ],
)
@pytest.mark.parametrize("inline_unit", [False, True])
def test_unit_scan_stops_at_barrier(barrier: dict, inline_unit: bool) -> None:
    content = "{{ ${/data/countdown/countdownDays} }}"
    if inline_unit:
        content = "{{ ${/data/countdown/countdownDays} + '天后' }}"
    reporter = _validate_siblings(content, [barrier, {"component": "Text", "content": "天"}])

    assert reporter.has_code("DISPLAY_UNIT_MISSING") is (not inline_unit)
    assert not reporter.has_code("DISPLAY_UNIT_DUPLICATED")


@pytest.mark.parametrize("unit_count", [1, 2])
def test_unit_scan_counts_adjacent_text_before_divider(unit_count: int) -> None:
    siblings = [{"component": "Text", "content": "天"} for _ in range(unit_count)]
    siblings.extend([{"component": "Divider"}, {"component": "Text", "content": "天"}])
    reporter = _validate_siblings("{{ ${/data/countdown/countdownDays} }}", siblings)

    assert not reporter.has_code("DISPLAY_UNIT_MISSING")
    assert reporter.has_code("DISPLAY_UNIT_DUPLICATED") is (unit_count == 2)


@pytest.mark.parametrize(
    "label",
    ["平均 135 次/分钟", "平均心率：次/分钟", "剩余 10 分", "分组训练", "分钟数：40"],
)
@pytest.mark.parametrize("unit_included", [False, True])
def test_independent_metric_does_not_supply_previous_duration_unit(
    label: str, unit_included: bool
) -> None:
    reporter = _validate_siblings(
        "{{ ${/data/countdown/countdownDays} }}",
        [{"component": "Text", "content": label}],
        units=("小时", "分"),
        unit_included=unit_included,
    )

    assert reporter.has_code("DISPLAY_UNIT_MISSING") is (not unit_included)
    assert not reporter.has_code("DISPLAY_UNIT_DUPLICATED")


@pytest.mark.parametrize("unit", ["分", "小时"])
@pytest.mark.parametrize("unit_included", [False, True])
def test_adjacent_duration_unit_is_still_checked(unit: str, unit_included: bool) -> None:
    reporter = _validate_siblings(
        "{{ ${/data/countdown/countdownDays} }}",
        [{"component": "Text", "content": unit}],
        units=("小时", "分"),
        unit_included=unit_included,
    )

    assert not reporter.has_code("DISPLAY_UNIT_MISSING")
    assert reporter.has_code("DISPLAY_UNIT_DUPLICATED") is unit_included
