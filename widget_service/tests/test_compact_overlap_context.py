"""重叠根因反馈使用同轮几何数据，且不会新增校验门禁。"""

import json
from typing import Any

from services.card_validation.compact_geometry import validate_compact_geometry
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.prompt_builder import PromptBuilder


def _check(rows: list[list[Any]]):
    source = "\n".join(json.dumps(row) for row in rows)
    parsed = parse_compact_dsl_rows(source)
    components = [row for row in parsed if isinstance(row, ComponentRow)]
    return validate_compact_geometry(components, size="2x4")


def _rows(height: int = 36) -> list[list[Any]]:
    return [
        ["root", "Column", {}, ["previous", "slot"]],
        ["previous", "Text", {"width": 100, "height": 20, "content": "会议"}],
        ["slot", "Row", {"width": 100, "height": height}, ["action"]],
        ["action", "Text", {"width": 100, "height": 57, "content": "动作"}],
    ]


def test_overlap_explains_expanded_child_and_parent_budget() -> None:
    result = _check(_rows())
    assert len(result.errors) == 1
    error = result.errors[0]
    assert "COMPACT_LAYOUT_OVERLAP" in error
    assert "child action has expanded height 57.00vp" in error
    assert "parent slot (Row) provides only 36.00vp" in error
    assert "exceeds by 21.00vp" in error
    assert "Main-axis weight/shrink does not reduce this cross-axis height" in error
    assert "model estimates, not pixel measurements" in error
    messages = PromptBuilder().build_repair(
        [{"role": "system", "content": "生成卡片"}, {"role": "user", "content": "日程"}],
        "source",
        [{"stage": "validation", "code": "COMPACT_DSL_VALIDATION_FAILED", "message": error}],
        dsl_format="design-compact-dsl",
    )
    content = messages[1].get("content")
    assert isinstance(content, str)
    assert "exceeds by 21.00vp" in content


def test_padding_and_margin_reduce_available_cross_axis_space() -> None:
    rows = _rows()
    rows[2] = ["slot", "Row", {"width": 100, "height": 36, "padding": 2}, ["action"]]
    rows[3] = ["action", "Text", {"width": 80, "height": 57, "margin": 1, "content": "动作"}]
    error = "\n".join(_check(rows).errors)
    assert "provides only 30.00vp after padding/margins; exceeds by 27.00vp" in error


def test_context_covers_width_overflow_in_column() -> None:
    rows = [
        ["root", "Row", {}, ["previous", "slot"]],
        ["previous", "Text", {"width": 20, "height": 100, "content": "前项"}],
        ["slot", "Column", {"width": 36, "height": 100, "alignItems": "center"}, ["wide"]],
        ["wide", "Text", {"width": 57, "height": 100, "content": "宽内容"}],
    ]
    error = "\n".join(_check(rows).errors)
    assert "expanded width 57.00vp" in error
    assert "parent slot (Column) provides only 36.00vp" in error


def test_compressed_ancestor_is_reported_for_overlapping_descendant() -> None:
    rows = _rows()
    rows[0] = ["root", "Column", {"height": 40}, ["previous", "slot"]]
    error = "\n".join(_check(rows).errors)
    assert "parent root (Column) compresses child slot height" in error
    assert "check its descendants against the reduced slot" in error


def test_context_is_recomputed_after_repair() -> None:
    assert "provides only 36.00vp" in "\n".join(_check(_rows()).errors)
    result = _check(_rows(height=57))
    assert result.errors == []
    assert result.warnings == []


def test_overflow_without_overlap_does_not_add_error() -> None:
    rows = _rows()
    rows[0] = ["root", "Column", {}, ["slot"]]
    rows.pop(1)
    result = _check(rows)
    assert result.errors == []
    assert result.warnings == []


def test_overlap_without_size_pressure_does_not_invent_cause() -> None:
    rows = [
        ["root", "Stack", {}, ["one", "two"]],
        ["one", "Text", {"width": 50, "height": 20, "content": "一"}],
        ["two", "Text", {"width": 50, "height": 20, "content": "二"}],
    ]
    result = _check(rows)
    assert len(result.errors) == 1
    assert "Layout size context" not in result.errors[0]
