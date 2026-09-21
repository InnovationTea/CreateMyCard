# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""模板公共入口跳过全部规则，普通卡片和无效标记仍执行校验。"""

import json
from typing import Any
from unittest.mock import Mock

import pytest

from services.card_validation import (
    CompactDslValidationError,
    CompactDslValidationResult,
    ValidationOptions,
    compact_dsl_validator,
    pipeline,
    validate_card,
    validate_compact_dsl,
)


def _components(size: str = "2x2", fusion: bool = False) -> list[dict[str, Any]]:
    root: dict[str, Any] = {
        "id": "root", "component": "Stack", "children": ["template_root"],
        "styles": {"width": 160 if size == "2x2" else 320, "height": 160},
    }
    if fusion:
        root["fusionBallBackground"] = {"business": "battery"}
    return [
        root,
        {"id": "template_root", "component": "Column", "children": ["value"]},
        {
            "id": "value", "component": "Text", "content": {"path": "/data/undeclared"},
            "styles": {"height": 300, "fontSize": 30},
        },
    ]


def _a2ui(components: list[dict[str, Any]]) -> str:
    messages = [
        {"createSurface": {"surfaceId": "test"}},
        {"updateComponents": {
            "surfaceId": "test", "root": components[0].get("id"), "components": components,
        }},
        {"updateDataModel": {"surfaceId": "test", "path": "/", "value": {"data": {}}}},
    ]
    return "\n".join(json.dumps(message) for message in messages)


def _compact(components: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for component in components:
        props = dict(component)
        component_id = props.pop("id")
        component_type = props.pop("component")
        children = props.pop("children", [])
        styles = props.pop("styles", {})
        props.update(styles)
        lines.append(json.dumps([component_id, component_type, props, children]))
    return "\n".join(lines)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("stage", ["hard", "semantic", "all"])
def test_a2ui_entry_does_not_call_any_validator(
    size: str, fusion: bool, stage: str, monkeypatch, caplog,
) -> None:
    calls: list[Mock] = []
    validators = pipeline.STATIC_VALIDATORS + pipeline.EFFECTIVE_VALIDATORS
    validators += pipeline.QUALITY_VALIDATORS
    for validator in validators:
        call = Mock(side_effect=AssertionError("模板场景不应执行校验器"))
        monkeypatch.setattr(validator, "validate", call)
        calls.append(call)
    with caplog.at_level("INFO"):
        reporter = validate_card(
            dsl_text=_a2ui(_components(size, fusion)),
            cardspec={"suggestSize": size},
            options=ValidationOptions(stage=stage, stop_on_stage_error=True),
        )
    assert reporter.diagnostics == []
    assert reporter.quality_score is None
    for call in calls:
        call.assert_not_called()
    assert "card_validation_skipped reason=template_root entry=run_pipeline" in caplog.text


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("fusion", [False, True])
def test_compact_entry_skips_rules_and_unused_binding_warnings(
    size: str, fusion: bool, monkeypatch, caplog,
) -> None:
    first_rule = Mock(side_effect=AssertionError("模板场景不应执行 Compact 规则"))
    warnings = Mock(side_effect=AssertionError("模板场景不应计算未使用绑定告警"))
    monkeypatch.setattr(compact_dsl_validator, "_collect_asset_source_errors", first_rule)
    monkeypatch.setattr(compact_dsl_validator, "_unused_data_capability_warnings", warnings)
    with caplog.at_level("INFO"):
        result = validate_compact_dsl(
            _compact(_components(size, fusion)),
            task_spec={"size": size, "dataModelSchema": {"data": {}}},
            card_spec={
                "suggestSize": size,
                "dataBindings": [{"capabilityId": "unused", "writeResultTo": "/data/unused"}],
            },
        )
    assert isinstance(result, CompactDslValidationResult)
    assert result.warnings == ()
    first_rule.assert_not_called()
    warnings.assert_not_called()
    assert "card_validation_skipped reason=template_root entry=validate_compact_dsl" in caplog.text


def _invalidate_marker(components: list[dict[str, Any]], marker: str) -> None:
    if marker == "missing":
        components[0]["children"] = ["value"]
        components.pop(1)
    elif marker == "dangling":
        components.pop(1)
    elif marker == "orphan":
        components[0]["children"] = ["value"]
    elif marker == "nested":
        components[0]["children"] = ["wrapper"]
        components.append({
            "id": "wrapper", "component": "Column", "children": ["template_root"],
        })
    elif marker == "prefix":
        components[0]["children"] = ["template_root_0"]
        components[1]["id"] = "template_root_0"
    elif marker == "duplicate":
        components.append({"id": "value", "component": "Text", "content": "重复 ID"})
    elif marker == "wrong-root":
        components[0]["id"] = "preview_root"
    else:
        raise ValueError(f"Unknown marker: {marker}")


@pytest.mark.parametrize("marker", [
    "missing", "dangling", "orphan", "nested", "prefix", "wrong-root",
])
def test_invalid_marker_keeps_both_entry_validations(marker: str) -> None:
    components = _components()
    _invalidate_marker(components, marker)
    reporter = validate_card(dsl_text=_a2ui(components))
    assert reporter.error_count > 0
    with pytest.raises(CompactDslValidationError):
        validate_compact_dsl(_compact(components), task_spec={}, card_spec={})


def test_duplicate_ids_follow_existing_input_parsing() -> None:
    components = _components()
    _invalidate_marker(components, "duplicate")
    assert validate_card(dsl_text=_a2ui(components)).has_code("DSL_COMPONENT_ID_DUPLICATED")
    # Compact 解析器原有去重先于入口判断，保留首个同 ID 组件。
    result = validate_compact_dsl(_compact(components), task_spec={}, card_spec={})
    assert result.warnings == ()


def test_template_marker_is_rechecked_at_both_entries() -> None:
    components = _components()
    assert validate_card(dsl_text=_a2ui(components)).diagnostics == []
    assert validate_compact_dsl(_compact(components), task_spec={}, card_spec={}).warnings == ()
    _invalidate_marker(components, "missing")
    assert validate_card(dsl_text=_a2ui(components)).error_count > 0
    with pytest.raises(CompactDslValidationError):
        validate_compact_dsl(_compact(components), task_spec={}, card_spec={})


def test_template_marker_does_not_hide_input_parse_errors() -> None:
    components = _components()
    valid_dsl = _a2ui(components)
    invalid_dsl = valid_dsl.rsplit("\n", 1)[0] + "\n{"
    reporter = validate_card(dsl_text=invalid_dsl)
    assert reporter.has_code("DSL_JSON_PARSE_FAILED")
    reporter = validate_card(dsl_text=valid_dsl, cardspec="{")
    assert reporter.has_code("CARD_JSON_PARSE_FAILED")
    with pytest.raises(CompactDslValidationError):
        validate_compact_dsl(_compact(components) + "\n[", task_spec={}, card_spec={})
