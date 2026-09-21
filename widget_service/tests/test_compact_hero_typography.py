# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""验证模板主文字豁免边界，以及普通生成和其它 Compact 检查保持生效。"""

import json
from typing import Any

import pytest

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    _collect_hero_value_errors,
    validate_compact_dsl,
)
from services.card_validation.validation_policy import CompactRule, resolve_validation_policy
from services.compact_dsl_a2ui_converter import ComponentRow


def _fixture(
    size: str = "2x2", fusion: bool = False, content: Any = "7小时1分"
) -> tuple[list[ComponentRow], dict[str, Any]]:
    width = 160 if size == "2x2" else 320
    root_props: dict[str, Any] = {"width": width, "height": 160}
    if fusion:
        root_props["fusionBallBackground"] = {"business": "sleep"}
    rows = [
        ComponentRow("root", "Stack", root_props, ("template_root",)),
        ComponentRow(
            "template_root", "Column", {"width": "matchParent", "height": 136}, ("reading",)
        ),
        ComponentRow("reading", "Row", {}, ("value", "label")),
        ComponentRow(
            "value", "Text",
            {"content": content, "fontSize": 30, "height": 40, "maxLines": 1},
        ),
        ComponentRow(
            "label", "Text",
            {"content": "睡眠时长", "fontSize": 12, "height": 16},
        ),
    ]
    spec = {"size": size, "dataModelSchema": {"data": {"sleep": {"value": {
        "type": "string", "description": "睡眠时长", "sampleValue": "7小时1分",
    }}}}}
    return rows, spec


def _errors(rows: list[ComponentRow], spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _collect_hero_value_errors(rows, spec, errors)
    return errors


def _validation_errors(rows: list[ComponentRow], spec: dict[str, Any]) -> list[str]:
    source = _source(rows)
    schema = spec.get("dataModelSchema", {}).get("data", {})
    for root, fields in schema.items():
        for name, node in fields.items():
            assert "sampleValue" in node
            source += "\n" + json.dumps([f"/data/{root}/{name}", node.get("sampleValue")])
    errors: list[str] = []
    try:
        validate_compact_dsl(source, task_spec=spec, card_spec={"suggestSize": spec.get("size")})
    except CompactDslValidationError as exc:
        errors = list(exc.errors)
    return errors


def _source(rows: list[ComponentRow]) -> str:
    lines = []
    for component in rows:
        row = [component.component_id, component.component_type, component.props]
        if component.children:
            row.append(list(component.children))
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("content", [
    "7小时1分", "8月19日", "68%",
    {"path": "/data/sleep/value"}, "{{ ${/data/sleep/value} }}",
    "{{ ${/data/sleep/value} + '睡眠' }}",
])
def test_valid_template_skips_hero_typography(
    size: str, fusion: bool, content: Any,
) -> None:
    rows, spec = _fixture(size, fusion, content)
    assert not _validation_errors(rows, spec)


@pytest.mark.parametrize("marker", [
    "missing", "dangling", "orphan", "nested", "prefix", "duplicate", "wrong-root",
])
def test_invalid_template_marker_keeps_hero_validation(marker: str) -> None:
    rows, spec = _fixture(fusion=True)
    if marker == "missing":
        rows[0] = ComponentRow("root", "Stack", {}, ("reading",))
        rows.pop(1)
    elif marker == "dangling":
        rows.pop(1)
    elif marker == "orphan":
        rows[0] = ComponentRow("root", "Stack", {}, ("reading",))
    elif marker == "nested":
        rows[0] = ComponentRow("root", "Stack", {}, ("wrapper",))
        rows.append(ComponentRow("wrapper", "Stack", {}, ("template_root",)))
    elif marker == "prefix":
        rows[0] = ComponentRow("root", "Stack", {}, ("template_root_0",))
        rows[1] = ComponentRow("template_root_0", "Column", {}, ("reading",))
    elif marker == "duplicate":
        rows.append(ComponentRow("value", "Text", {"content": "重复"}))
    else:
        rows[0] = ComponentRow("preview_root", "Stack", {}, ("template_root",))
    policy = resolve_validation_policy(
        root_id=rows[0].component_id,
        root_children=rows[0].children,
        component_ids=(row.component_id for row in rows),
    )
    assert CompactRule.HERO_VALUE in policy.compact_rules
    assert any("fontSize 30" in error for error in _errors(rows, spec))


def test_template_marker_is_rechecked_after_each_repair() -> None:
    rows, spec = _fixture()
    assert not _validation_errors(rows, spec)
    rows[0] = ComponentRow("root", "Stack", {}, ("reading",))
    assert _validation_errors(rows, spec)


def test_template_skips_adjacent_numeric_label_check() -> None:
    rows, spec = _fixture(content="68")
    assert not _validation_errors(rows, spec)
    rows[0] = ComponentRow("root", "Stack", {}, ("reading",))
    assert any("real unit" in error for error in _validation_errors(rows, spec))


@pytest.mark.parametrize(("change", "message"), [
    ("height", "vertical layout"),
    ("binding", "not declared"),
    ("empty", "non-empty"),
])
def test_template_keeps_other_compact_validations(change: str, message: str) -> None:
    rows, spec = _fixture()
    if change == "height":
        rows[3].props["height"] = 200
    elif change == "binding":
        rows[3].props["content"] = {"path": "/data/unknown/value"}
    else:
        rows[2] = ComponentRow("reading", "Column", {}, ())
    with pytest.raises(CompactDslValidationError, match=message):
        validate_compact_dsl(
            _source(rows), task_spec=spec, card_spec={"suggestSize": "2x2"}
        )


@pytest.mark.parametrize("change", [
    "none", "expression", "inherited-width", "percent-description",
])
def test_non_template_formatted_readout_keeps_original_contract(change: str) -> None:
    rows = [
        ComponentRow("root", "Column", {"width": 136}, ("value",)),
        ComponentRow("value", "Text", {
            "content": {"path": "/data/battery/value"},
            "width": 136, "height": 34, "fontSize": 24, "maxLines": 1,
        }),
    ]
    value_schema = {
        "type": "string", "description": "电量百分比", "sampleValue": "68%",
    }
    spec = {"size": "2x2", "dataModelSchema": {"data": {"battery": {
        "value": value_schema,
    }}}}
    if change == "expression":
        rows[1].props["content"] = "{{ ${/data/battery/value} }}"
    elif change == "inherited-width":
        rows[1].props["width"] = "matchParent"
    elif change == "percent-description":
        value_schema["description"] = "电量，已包含 % 单位"
    assert bool(_errors(rows, spec)) is (change != "none")
