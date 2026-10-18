"""多字段已知文本不能因单路径解析限制而跳过宽度；不执行算术或未知表达式。"""

import json

import pytest

from services.card_validation import validate_compact_dsl
from services.card_validation.compact_validation.constants import _VISUAL_RECIPE_MARKER_PREFIX
from services.card_validation.compact_validation.semantic.layout.text_width import (
    _collect_text_width_budget_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _errors(content: str, schema: dict, *, width: int = 80, size: str = "2x4") -> list[str]:
    rows = [
        ComponentRow("root", "Column", {"width": width, "height": 100}, ("value",)),
        ComponentRow("value", "Text", {"content": content, "width": width,
                     "fontSize": 12, "maxLines": 1}, ()),
    ]
    errors = []
    _collect_text_width_budget_errors(
        rows, {"size": size, "dataModelSchema": {"data": schema}}, {}, errors, None,
    )
    return errors


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_complete_multifield_string_is_measured_for_both_sizes(size: str) -> None:
    schema = {
        "place": {"type": "string", "sampleValue": "书房"},
        "state": {"type": "string", "sampleValue": "滤芯需要更换"},
    }
    errors = _errors("{{ ${/data/place} + ' · ' + ${/data/state} }}", schema, size=size)
    assert len(errors) == 1
    assert "书房 · 滤芯需要更换" in errors[0]
    assert "text width overflow" in errors[0]


def test_short_multifield_string_remains_accepted() -> None:
    schema = {
        "place": {"type": "string", "sampleValue": "书房"},
        "state": {"type": "string", "sampleValue": "在线"},
    }
    assert not _errors("{{ ${/data/place} + ' · ' + ${/data/state} }}", schema)


def test_pure_numeric_addition_is_not_guessed_as_text_concatenation() -> None:
    schema = {
        "first": {"type": "integer", "sampleValue": 123456789},
        "second": {"type": "integer", "sampleValue": 987654321},
    }
    assert not _errors("{{ ${/data/first} + ${/data/second} }}", schema)


def test_unknown_multifield_value_is_not_fabricated() -> None:
    schema = {"place": {"type": "string", "sampleValue": "书房"}, "state": {"type": "string"}}
    assert not _errors("{{ ${/data/place} + ' · ' + ${/data/state} }}", schema)


def test_boolean_two_state_copy_checks_longer_branch_without_running_expression() -> None:
    schema = {"ready": {"type": "boolean", "sampleValue": True}}
    errors = _errors("{{ ${/data/ready} ? '就绪' : '需要更换滤芯' }}", schema, width=60)
    assert len(errors) == 1
    assert "需要更换滤芯" in errors[0]


def test_infoblock_secondary_overflow_is_reported_as_warning() -> None:
    rows = [
        ComponentRow("root", "Column", {"width": 132, "height": 57}, ("secondary",)),
        ComponentRow(
            "secondary",
            "Text",
            {
                "content": "时长 40分 · 消耗 260 千卡 · 心率 135/96 次/分钟",
                "width": 116,
                "fontSize": 12,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "_visualRecipe": f"{_VISUAL_RECIPE_MARKER_PREFIX}InfoBlock.secondary",
            },
            (),
        ),
    ]
    errors: list[str] = []
    warnings: list[str] = []

    _collect_text_width_budget_errors(
        rows,
        {"size": "2x4", "dataModelSchema": {"data": {}}},
        {},
        errors,
        None,
        warnings=warnings,
    )

    assert errors == []
    assert len(warnings) == 1
    assert "InfoBlock.secondaryText" in warnings[0]
    assert "ellipsis" in warnings[0]


@pytest.mark.parametrize("part", ["TextBlock.label", "TextBlock.value"])
def test_text_block_overflow_is_reported_as_warning(part: str) -> None:
    font_size = 12 if part == "TextBlock.label" else 10
    rows = [
        ComponentRow("root", "Column", {"width": 47, "height": 16}, ("detail",)),
        ComponentRow(
            "detail",
            "Text",
            {
                "content": "东南风 2级",
                "width": 47,
                "fontSize": font_size,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "_visualRecipe": f"{_VISUAL_RECIPE_MARKER_PREFIX}{part}",
            },
            (),
        ),
    ]
    errors: list[str] = []
    warnings: list[str] = []

    _collect_text_width_budget_errors(
        rows,
        {"size": "2x4", "dataModelSchema": {"data": {}}},
        {},
        errors,
        None,
        warnings=warnings,
    )

    assert errors == []
    assert len(warnings) == 1
    assert part in warnings[0]
    assert "ellipsis" in warnings[0]


def test_card_button_label_overflow_is_reported_as_warning() -> None:
    rows = [
        ComponentRow("root", "Column", {"width": 76, "height": 20}, ("lower_label",)),
        ComponentRow(
            "lower_label",
            "Text",
            {
                "content": "查看首场日程",
                "width": 76,
                "fontSize": 14,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "_visualRecipe": (
                    f"{_VISUAL_RECIPE_MARKER_PREFIX}CardButton.label"
                ),
            },
            (),
        ),
    ]
    errors: list[str] = []
    warnings: list[str] = []

    _collect_text_width_budget_errors(
        rows,
        {"size": "2x4", "dataModelSchema": {"data": {}}},
        {},
        errors,
        None,
        warnings=warnings,
    )

    assert errors == []
    assert len(warnings) == 1
    assert "CardButton.label" in warnings[0]
    assert "ellipsis" in warnings[0]


def test_text_block_value_overflow_does_not_reject_compact_dsl() -> None:
    rows = [
        [
            "root",
            "Column",
            {"width": "matchParent", "height": "matchParent", "padding": 12},
            ["details"],
        ],
        [
            "details",
            "TextBlock",
            {
                "items": [
                    {"label": "天气", "value": "多云"},
                    {"label": "体感", "value": "31℃"},
                    {"label": "湿度", "value": "68%"},
                    {"label": "风力", "value": "东南风 2级"},
                ]
            },
        ],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)

    result = validate_compact_dsl(
        source,
        task_spec={"size": "2x4", "dataModelSchema": {"data": {}}},
        card_spec={},
    )

    assert any("TextBlock.value" in warning for warning in result.warnings)


def test_infoblock_secondary_overflow_does_not_reject_compact_dsl() -> None:
    rows = [
        ["root", "Column", {"width": 132, "height": 57}, ["info"]],
        [
            "info",
            "InfoBlock",
            {
                "variant": "slot",
                "primaryText": "户外跑步",
                "secondaryText": "时长 40分 · 消耗 260 千卡 · 心率 135/96 次/分钟",
                "fontColor": "#FF8C4B1C",
                "backgroundColor": "#99FFFFFF",
            },
        ],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)

    result = validate_compact_dsl(
        source,
        task_spec={"size": "2x4", "dataModelSchema": {"data": {}}},
        card_spec={},
    )

    assert len(result.warnings) == 1
    assert "InfoBlock.secondaryText" in result.warnings[0]
