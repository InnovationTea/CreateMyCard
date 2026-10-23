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
    DataRow,
    build_compact_data_model,
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

WEATHER_SUPPORT_NATURAL = '\n'.join([
    '["root","Layout",{"layout":"S-title-dual-content"},'
    '["title","primary","support"]]',
    '["title","SingleLineTitle",'
    '{"title":{"path":"/data/weather/location/prefectureName"},"fontSize":12}]',
    '["primary","EmphasizedData",'
    '{"value":{"path":"/data/weather/current/temperatureText"},"fontSize":30}]',
    '["support","SecondaryBody",{"items":['
    '{"value":{"path":"/data/weather/current/condition"}},'
    '{"label":"空气质量 ","value":{"path":"/data/weather/current/airQuality"}},'
    '{"label":"湿度 ","value":"{{ ${/data/weather/current/humidityPercent} + \'%\' }}"},'
    '{"label":"风力 ","value":"{{ ${/data/weather/current/windLevel} + \'级\' }}"}'
    '],"columns":2,"fontSize":14}]',
    '["/data/weather/location/prefectureName","上海市"]',
    '["/data/weather/current/temperatureText","29℃"]',
    '["/data/weather/current/condition","多云"]',
    '["/data/weather/current/airQuality","良"]',
    '["/data/weather/current/humidityPercent",68]',
    '["/data/weather/current/windLevel",2]',
])

WEATHER_SUPPORT_OVERFLOW = WEATHER_SUPPORT_NATURAL.replace(
    '{"label":"风力 ","value":"{{ ${/data/weather/current/windLevel} + \'级\' }}"}',
    '{"label":"风力 ","value":"{{ ${/data/weather/current/windLevel} + \'级\' }}"},'
    '{"label":"体感 ","value":"31℃"},{"label":"降雨 ","value":"20%"}',
).replace('"columns":2', '"columns":1')

ANCHOR_MULTILINE_SUPPORT = '\n'.join([
    '["root","Layout",{"layout":"S-title-anchor"},["title","primary","support","action"]]',
    '["title","SingleLineTitle",{"title":"电池体检",'
    '"icon":"resources/base/media/battery_leaf_fill.svg","fontSize":12}]',
    '["primary","EmphasisText",{"mainText":{"path":"/data/phoneBattery/batterySOCText"},'
    '"fontSize":18}]',
    '["support","SecondaryBody",{"items":['
    '{"label":"电量等级 ","value":{"path":"/data/phoneBattery/batteryCapacityLevelDesc"}},'
    '{"label":"健康状态 ","value":{"path":"/data/phoneBattery/healthStatusDesc"}},'
    '{"label":"实时温度 ","value":{"path":"/data/phoneBattery/batteryTemperatureText"}}'
    '],"fontSize":12}]',
    '["action","CircleButton",{"icon":"resources/base/media/gearshape_fill.svg",'
    '"accessibility":{"label":"电池健康设置"},"onClick":[{"call":"clickToDeeplink",'
    '"args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings",'
    '"abilityName":"com.huawei.hmos.settings.MainAbility",'
    '"uri":"smart_charge_battery_health"}}]}]',
    '["/data/phoneBattery/batterySOCText","68%"]',
    '["/data/phoneBattery/batteryCapacityLevelDesc","正常电量"]',
    '["/data/phoneBattery/healthStatusDesc","正常"]',
    '["/data/phoneBattery/batteryTemperatureText","29.0 ℃"]',
])

ANCHOR_MULTILINE_SUPPORT_OVERFLOW = ANCHOR_MULTILINE_SUPPORT.replace(
    '{"label":"实时温度 ","value":{"path":"/data/phoneBattery/batteryTemperatureText"}}',
    '{"label":"实时温度 ","value":{"path":"/data/phoneBattery/batteryTemperatureText"}},'
    '{"label":"充电状态 ","value":{"path":"/data/phoneBattery/chargingStatus"}}',
)

WEATHER_TASK_SPEC = {
    "size": "2x2",
    "dataModelSchema": {
        "data": {
            "weather": {
                "location": {"prefectureName": {"type": "string"}},
                "current": {
                    "temperatureText": {"type": "string"},
                    "condition": {"type": "string"},
                    "airQuality": {"type": "string"},
                    "humidityPercent": {"type": "integer"},
                    "windLevel": {"type": "integer"},
                },
            }
        }
    },
    "assetCandidates": [],
    "eventCandidates": [],
}


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


def _height_errors(
    rows: list[ComponentRow],
    size: str | None = "2x4",
) -> DiagnosticCollector:
    errors = DiagnosticCollector()
    _collect_height_budget_errors(
        rows,
        {"size": size},
        {"suggestSize": size},
        errors,
    )
    return errors


def _anchor_multiline_support_rows(*, overflow: bool = False) -> list[ComponentRow]:
    source = ANCHOR_MULTILINE_SUPPORT_OVERFLOW if overflow else ANCHOR_MULTILINE_SUPPORT
    rows = parse_compact_dsl_rows(source, size="2x2")
    components = [row for row in rows if isinstance(row, ComponentRow)]
    data_rows = [row for row in rows if isinstance(row, DataRow)]
    data_model = build_compact_data_model(data_rows)
    expanded = expand_high_level_component_rows(components, size="2x2", data_model=data_model)
    return normalize_mixed_font_text_rows(expanded, data_model=data_model)


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


def test_weather_support_natural_height_uses_available_bottom_space() -> None:
    result = validate_compact_dsl(
        WEATHER_SUPPORT_NATURAL,
        task_spec=WEATHER_TASK_SPEC,
        card_spec={"suggestSize": "2x2"},
    )

    assert result.warnings == ()


def test_weather_support_height_overflow_is_blocking_layout_capacity_error() -> None:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            WEATHER_SUPPORT_OVERFLOW,
            task_spec=WEATHER_TASK_SPEC,
            card_spec={"suggestSize": "2x2"},
        )

    diagnostics = [
        item
        for item in captured.value.diagnostics
        if item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
    ]
    assert diagnostics
    assert all(item.to_payload().get("severity") == "error" for item in diagnostics)
    assert any(item.actual.get("overflow", 0) > 2 for item in diagnostics)
    assert any("Occupancy:" in item.legacy_message for item in diagnostics)


def test_anchor_multiline_support_expands_from_the_bottom_without_overlap() -> None:
    rows = _anchor_multiline_support_rows()
    bottom = next(row for row in rows if row.component_id == "__layout__root__bottom")
    body = next(row for row in rows if row.component_id == "__layout__root__body")

    assert "height" not in bottom.props
    assert bottom.props.get("constraintSize") == {"minHeight": 40}
    assert bottom.props.get("flexShrink") == 0
    assert body.props.get("itemMargin") == 2
    assert not _height_errors(rows, size="2x2")


def test_anchor_multiline_support_still_rejects_total_height_overflow() -> None:
    errors = _height_errors(_anchor_multiline_support_rows(overflow=True), size="2x2")
    diagnostics = [item for item in errors.records if not isinstance(item, str)]

    assert any(
        item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
        and item.component_id == "__layout__root__body"
        for item in diagnostics
    )


def test_closed_sleep_card_rejects_height_even_when_item_margin_matches_overflow() -> None:
    rows = []
    for row in _sleep_rows(closed=True):
        if row.component_id == "details":
            row = replace(row, props={**row.props, "height": 90})
        rows.append(row)
    errors = _height_errors(rows)

    assert len(errors.records) == 1
    diagnostic = errors.records[0]
    assert not isinstance(diagnostic, str)
    assert diagnostic.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
    assert diagnostic.actual.get("overflow") == 2.0


@pytest.mark.parametrize("component_id", ["root", "weighted"])
def test_root_and_weighted_column_height_overflow_are_errors(component_id: str) -> None:
    props: dict[str, object] = {"height": 40}
    if component_id == "weighted":
        props["layoutWeight"] = 1
    rows = [
        ComponentRow(component_id, "Column", props, ("text",)),
        ComponentRow("text", "Text", {"height": 41}, ()),
    ]
    errors = _height_errors(rows, size=None)
    diagnostics = [item for item in errors.records if not isinstance(item, str)]

    assert any(
        item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW" and item.component_id == component_id
        for item in diagnostics
    )


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
