"""多字段已知文本不能因单路径解析限制而跳过宽度；不执行算术或未知表达式。"""

import pytest

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
