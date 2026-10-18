"""主线小卡压力提示迁入分类模块后的公开入口回归。"""

import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_dsl_validator import small_card_text_pressure


def test_small_card_pressure_keeps_complete_label_and_value() -> None:
    rows = [
        ["root", "Column", {"width": "matchParent"}, ["body"]],
        ["body", "SecondaryBody", {
            "role": "supporting", "width": 100, "fontSize": 14,
            "items": [{"label": "完整状态标签", "value": "正常"}],
        }],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    task = {"size": "2x2", "dataModelSchema": {"data": {}}}
    pressure = small_card_text_pressure(source, task)
    assert len(pressure) == 1
    assert "完整状态标签" in pressure[0] and "正常" in pressure[0]
    assert "112vp" in pressure[0] and "100vp" in pressure[0]
    assert small_card_text_pressure(source, {**task, "size": "2x4"}) == []


def test_pressure_failure_stays_optional_and_records_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("DEBUG"):
        assert small_card_text_pressure("not json", {"size": "2x2"}) == []
    assert "Small-card pressure unavailable" in caplog.text
    assert "CompactDslConversionError" in caplog.text


@pytest.mark.parametrize("overflow", [2, 3])
def test_small_card_height_tolerance_is_preserved_in_diagnostic(overflow: int) -> None:
    source = "\n".join([
        '["root","Column",{},["panel"]]',
        json.dumps(["panel", "Column", {"height": 12 - overflow}, ["title"]]),
        '["title","SingleLineTitle",{"title":"天气","fontColor":"#FF112233"}]',
    ])
    task = {"size": "2x2", "dataModelSchema": {"data": {}}}
    if overflow == 2:
        assert validate_compact_dsl(source, task_spec=task, card_spec={}).warnings == ()
    else:
        with pytest.raises(CompactDslValidationError) as captured:
            validate_compact_dsl(source, task_spec=task, card_spec={})
        diagnostic = next(
            item for item in captured.value.diagnostics
            if item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
        )
        assert diagnostic.expected.get("heightTolerance") == 2.0
        assert diagnostic.actual.get("overflow") == 3
