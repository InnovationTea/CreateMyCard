"""睡眠卡右侧填满组件的高度闭合回归；不修改正文组件的字号合同。"""

from dataclasses import replace

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.diagnostics import DiagnosticCollector
from services.card_validation.compact_validation.repair_guidance import resolve_fix_hint
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _collect_height_budget_errors,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    expand_high_level_component_rows,
    normalize_mixed_font_text_rows,
    parse_compact_dsl_rows,
)

SLEEP = '\n'.join([
    '["root","Column",{"width":"matchParent","height":"matchParent",'
    '"padding":12,"itemMargin":8,"clip":true},["title","body"]]',
    '["title","SingleLineTitle",{"title":"昨晚睡眠","width":"matchParent"}]',
    '["body","Row",{"width":"matchParent","itemMargin":8,"alignItems":"start",'
    '"layoutWeight":1},["primary","details"]]',
    '["primary","Column",{"width":"matchParent","itemMargin":2,"layoutWeight":1},'
    '["score","status"]]',
    '["score","EmphasizedData",{"value":82,"unit":"分","fontSize":30,'
    '"width":"matchParent"}]',
    '["status","SecondaryBody",{"role":"metadata","items":[{"value":"睡眠状态 良好"}],'
    '"width":"matchParent"}]',
    '["details","Column",{"width":"matchParent","itemMargin":8,"alignItems":"start",'
    '"layoutWeight":2},["durations","heart_action"]]',
    '["durations","TextBlock",{"items":[{"label":"睡眠时长","value":"7小时1分"},'
    '{"label":"深睡时长","value":"2小时15分"}],"width":"matchParent"}]',
    '["heart_action","Row",{"width":"matchParent","itemMargin":8,"alignItems":"bottom",'
    '"flexShrink":0},["heart","parent_control"]]',
    '["heart","EmphasisText",{"mainText":"最低心率","secondaryText":"96次/分钟",'
    '"fontSize":18,"width":"matchParent","layoutWeight":1}]',
    '["parent_control","PillButton",{"label":"使用时长","layoutWeight":1,"onClick":'
    '[{"call":"clickToDeeplink","args":{"intentName":"Settings",'
    '"bundleName":"com.huawei.hmos.settings",'
    '"abilityName":"com.huawei.hmos.settings.MainAbility","uri":"parent_control"}}]}]',
])


def _sleep_rows(*, closed: bool = False) -> list[ComponentRow]:
    # 正文采用合同默认字号，单独隔离本次高度问题，不绕过或放宽字号校验。
    rows = []
    for row in parse_compact_dsl_rows(SLEEP):
        assert isinstance(row, ComponentRow)
        if closed and row.component_id == "details":
            row = replace(row, props={**row.props, "height": "matchParent"})
        rows.append(row)
    expanded = expand_high_level_component_rows(rows, size="2x4", data_model={})
    return normalize_mixed_font_text_rows(expanded, data_model={})


def _height_errors(rows: list[ComponentRow], size: str = "2x4") -> DiagnosticCollector:
    errors = DiagnosticCollector()
    _collect_height_budget_errors(rows, {"size": size}, {"suggestSize": size}, errors)
    return errors


def test_sleep_card_rejects_unbounded_text_block_column() -> None:
    errors = _height_errors(_sleep_rows())
    records = errors.records
    assert len(records) == 1
    diagnostic = records[0]
    assert not isinstance(diagnostic, str)
    assert diagnostic.code == "COMPACT_LAYOUT_HEIGHT_UNRESOLVED"
    assert diagnostic.component_id == "details"
    assert diagnostic.actual == {"availableHeight": None, "dependentChildren": ["durations"]}
    hint = resolve_fix_hint(diagnostic)
    assert hint is not None
    assert "height=matchParent" in hint


def test_sleep_card_accepts_closed_height_without_removing_facts() -> None:
    assert not _height_errors(_sleep_rows(closed=True))


def test_public_validator_reports_height_closure_with_source_location() -> None:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            SLEEP,
            task_spec={"size": "2x4", "dataModelSchema": {"data": {}}},
            card_spec={"suggestSize": "2x4"},
        )
    diagnostics = []
    for diagnostic in captured.value.diagnostics:
        if diagnostic.code == "COMPACT_LAYOUT_HEIGHT_UNRESOLVED":
            diagnostics.append(diagnostic)
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.component_id == "details"
    assert diagnostic.source_line == 7
    assert diagnostic.fix_hint is not None


def test_closed_sleep_card_still_rejects_insufficient_height() -> None:
    rows = []
    for row in _sleep_rows(closed=True):
        if row.component_id == "details":
            row = replace(row, props={**row.props, "height": 90})
        rows.append(row)
    errors = _height_errors(rows)
    codes = []
    for diagnostic in errors.records:
        assert not isinstance(diagnostic, str)
        codes.append(diagnostic.code)
    assert "COMPACT_LAYOUT_HEIGHT_OVERFLOW" in codes


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("dependency", [{"height": "matchParent"}, {"layoutWeight": 1}])
def test_unknown_height_dependency_is_not_silently_skipped(
    size: str, dependency: dict[str, object],
) -> None:
    rows = [
        ComponentRow("root", "Row", {}, ("column",)),
        ComponentRow("column", "Column", {}, ("content",)),
        ComponentRow("content", "Text", {"content": "正文", **dependency}, ()),
    ]
    assert "unresolved available height" in " ".join(_height_errors(rows, size))


@pytest.mark.parametrize("weight", [None, 0])
def test_natural_height_without_vertical_dependency_stays_allowed(weight: int | None) -> None:
    props: dict[str, object] = {"content": "自然高度正文"}
    if weight is not None:
        props["layoutWeight"] = weight
    rows = [
        ComponentRow("root", "Row", {}, ("column",)),
        ComponentRow("column", "Column", {}, ("content",)),
        ComponentRow("content", "Text", props, ()),
    ]
    assert not _height_errors(rows)
