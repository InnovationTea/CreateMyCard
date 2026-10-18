"""数值组件只拒绝能够证明的普通文本，不从未知格式或占位样值推断错误。"""

from copy import deepcopy
from typing import Any

import pytest

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    DiagnosticCollector,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_compound_duration_component_errors,
)
from services.card_validation.compact_validation.semantic.numeric_display import (
    _collect_numeric_component_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect(
    value: Any, task: dict | None = None, kind: str = "EmphasizedData",
) -> DiagnosticCollector:
    errors = DiagnosticCollector()
    component = ComponentRow("hero", kind, {"value": value, "fontColor": "#FF000000"}, ())
    _collect_numeric_component_errors([component], task or {}, errors)
    return errors


def _task(node: dict) -> dict:
    return {"dataModelSchema": {"data": {"metric": node}}}


@pytest.mark.parametrize(
    "value", ["正常", "已连接", "我的手表", "Alice", "2026-10-12", "10月12日", "星期一"],
)
def test_plain_text_is_rejected_with_original_value_evidence(value: str) -> None:
    errors = _collect(value)
    assert len(errors) == 1
    record = errors.records[0]
    assert isinstance(record, CompactDiagnostic)
    assert record.code == "COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE"
    assert record.validation_class == "semantic"
    assert record.category == "display"
    assert record.component_id == "hero"
    assert record.property_path == "/value"
    assert record.actual == {"value": value}
    assert record.fix_hint is None


@pytest.mark.parametrize(
    "value",
    [0, -1.25, "0", "-1.25", "+.5", "1,234.56", "1.2e3", "-2.5E-4", "-12.5℃",
     "1,234.5 km", "50%", "80 bpm", "1.2e3 Pa", "12 knots", "三万", "半小时", "半个月",
     "约 12", "1/2", "09:30", "01:05:30"],
)
def test_numeric_and_single_measurement_formats_are_not_restricted_by_a_new_allowlist(
    value: Any,
) -> None:
    assert _collect(value) == []


@pytest.mark.parametrize(
    "value",
    [None, "", "--", "暂无", "暂无数据（离线）", "加载失败", "加载失败，请重试", "unknown", "N/A"],
)
def test_unavailable_values_do_not_prove_component_misuse(value: Any) -> None:
    assert _collect(value) == []


@pytest.mark.parametrize("binding", [{"path": "/data/metric"}, "{{ ${/data/metric} }}"])
@pytest.mark.parametrize(
    ("description", "sample"),
    [("设备运行状态", "正常"), ("设备名称", "我的手表"), ("日历日期", "2026-10-12"),
     ("当前时刻", "09:30"), ("闹钟钟点", "09:30"), ("约定几点出发", "09:30")],
)
def test_binding_requires_both_semantic_and_sample_evidence(
    binding: Any, description: str, sample: str,
) -> None:
    task = _task({"type": "string", "description": description, "sampleValue": sample})
    original = deepcopy(task)
    errors = _collect(binding, task)
    assert len(errors) == 1
    record = errors.records[0]
    assert isinstance(record, CompactDiagnostic)
    assert record.actual == {
        "value": binding,
        "dataPath": "/data/metric",
        "description": description,
        "sampleValue": sample,
    }
    assert task == original


@pytest.mark.parametrize(
    "node",
    [
        {"type": "string"},
        {"type": "string", "sampleValue": "正常"},
        {"description": "设备运行状态", "sampleValue": "正常"},
        {"type": ["string", "null"], "description": "设备状态", "sampleValue": None},
        {"type": "string", "description": "设备状态", "sampleValue": None},
        {"type": "string", "description": "设备状态", "sampleValue": ""},
        {"type": "string", "description": "设备状态", "sampleValue": "加载失败"},
        {"type": "string", "description": "设备状态", "sampleValue": "加载失败，请重试"},
        {"type": "string", "description": "设备状态", "sampleValue": "暂无数据（离线）"},
        {"type": "string", "description": "温度", "sampleValue": "加载失败"},
        {"type": "string", "description": "温度", "sampleValue": "-12.5℃"},
        {"type": "string", "description": "响应时间", "sampleValue": "12 ms"},
        {"type": "number", "description": "运行状态码", "sampleValue": 1},
    ],
)
def test_unknown_nullable_numeric_and_placeholder_binding_contracts_are_not_rejected(
    node: dict,
) -> None:
    assert _collect({"path": "/data/metric"}, _task(node)) == []


def test_static_pace_with_unit_is_a_valid_single_measurement() -> None:
    errors = DiagnosticCollector()
    rows = [ComponentRow(
        "hero", "EmphasizedData",
        {"value": "05:30", "unit": "min/km", "fontColor": "#FF000000"}, (),
    )]
    _collect_numeric_component_errors(rows, {}, errors)
    assert errors == []


@pytest.mark.parametrize("binding", [{"path": "/data/metric"}, "{{ ${/data/metric} }}"])
@pytest.mark.parametrize(
    ("description", "sample"),
    [("跑步配速，每公里用时", "05:30"), ("运动用时", "01:05:30"),
     ("运动时间，分秒格式", "05:30"), ("时间", "09:30")],
)
def test_colon_binding_does_not_prove_clock_semantics(
    binding: Any, description: str, sample: str,
) -> None:
    task = _task({"type": "string", "description": description, "sampleValue": sample})
    assert _collect(binding, task) == []


def test_json_schema_object_wrapper_resolves_real_binding() -> None:
    task = {
        "dataModelSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "姓名", "sampleValue": "Alice"},
                    },
                },
            },
        },
    }
    assert len(_collect({"path": "/data/metric"}, task)) == 1


@pytest.mark.parametrize(
    "expression",
    ["{{ ${/data/metric} + '℃' }}", "{{ ${/data/metric} * 100 }}",
     "{{ ${/data/metric} == '正常' ? 1 : 0 }}", "{{ round(${/data/metric}) }}"],
)
def test_expression_result_is_not_inferred_from_its_operand_sample(expression: str) -> None:
    task = _task({"type": "string", "description": "设备状态", "sampleValue": "正常"})
    assert _collect(expression, task) == []


def test_missing_binding_does_not_use_other_schema_samples_or_first_frame_data() -> None:
    task = _task({"type": "string", "description": "设备状态", "sampleValue": "正常"})
    task["data"] = {"missing": "正常"}
    assert _collect({"path": "/data/missing"}, task) == []


@pytest.mark.parametrize("kind", ["EmphasisText", "SecondaryBody", "Text", "InfoBlock"])
def test_other_text_components_remain_outside_this_rule(kind: str) -> None:
    assert _collect("正常", kind=kind) == []


@pytest.mark.parametrize("value", ["7小时1分", {"path": "/data/metric"}])
def test_compound_duration_keeps_one_existing_error(value: Any) -> None:
    task = _task({"type": "string", "description": "睡眠时间", "sampleValue": "7小时1分"})
    errors = DiagnosticCollector()
    rows = [ComponentRow("hero", "EmphasizedData", {"value": value}, ())]
    _collect_compound_duration_component_errors(rows, task, errors)
    _collect_numeric_component_errors(rows, task, errors)
    assert len(errors) == 1
    assert "compound duration" in errors[0]
    assert not any(isinstance(record, CompactDiagnostic) for record in errors.records)
