"""强调数值的无单位展开与最终Form协议一致，不改变既有字底补偿。"""

import json

import pytest

from services.card_validation import ValidationOptions, validate_card
from services.compact_dsl_a2ui_converter import (
    _normalize_component,
    convert_compact_dsl_to_a2ui,
)
from services.compact_high_level_components import ComponentRow
from services.post_layout_theme import apply_theme, foreground_signature, presets
from services.theme_style_roles import layout_phase


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("unit", [None, "项"])
def test_emphasized_data_final_alignment_is_legal_with_or_without_unit(size, unit):
    props = {"value": {"path": "/data/reading"}, "fontSize": 30}
    if unit is not None:
        props["unit"] = unit
    if size == "2x2":
        rows = [["root", "Layout", {"layout": "S-title-content"}, ["title", "reading"]]]
    else:
        rows = [
            ["root", "Layout", {"layout": "W-top-bottom"}, ["title", "reading", "details"]],
            ["details", "TextBlock", {"items": [
                {"label": "来源", "value": "传感器"}, {"label": "状态", "value": "正常"},
            ]}],
        ]
    rows.extend([
        ["title", "SingleLineTitle", {"title": "读数", "fontSize": 12}],
        ["reading", "EmphasizedData", props],
        ["/data/reading", 42 if unit else "42项"],
    ])
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase():
        converted = convert_compact_dsl_to_a2ui(source, size=size)
    task = {"size": size, "userQuery": "查看读数"}
    theme = next(item for item in presets(task) if item.get("id") == "gradient-blue")
    themed = apply_theme(converted, theme, task, {})
    assert foreground_signature(themed) == foreground_signature(converted)
    update = json.loads(themed.splitlines()[1]).get("updateComponents")
    assert update is not None
    registry = {}
    for node in update.get("components", []):
        registry[node.get("id")] = node
    root = registry.get("reading")
    value = registry.get("reading_value")
    assert root is not None and value is not None
    assert root.get("styles", {}).get("alignItems") == "bottom"
    assert value.get("content") == "{{ ${/data/reading} }}"
    assert value.get("styles", {}).get("fontSize") == 30
    if unit:
        assert root.get("children") == ["reading_value", "reading_unit"]
        assert root.get("itemMargin") == 2
        unit_node = registry.get("reading_unit")
        assert unit_node is not None
        assert unit_node.get("content") == unit
        assert unit_node.get("styles", {}).get("fontSize") == 12
    else:
        assert root.get("children") == ["reading_value"]
        assert root.get("itemMargin") == 0
    report = validate_card(dsl_text=themed, options=ValidationOptions(stage="hard"))
    assert not any(item.code == "STYLE_ENUM_INVALID" for item in report.diagnostics)


def test_wide_baseline_mapping_does_not_enable_small_axis_aliases():
    baseline = ComponentRow("reading", "Row", {"alignItems": "baseline"}, ("value",))
    expected = ComponentRow("reading", "Row", {"alignItems": "bottom"}, ("value",))
    assert _normalize_component(baseline) == expected
    legacy_alias = ComponentRow("other", "Row", {"alignItems": "start"}, ("value",))
    assert _normalize_component(legacy_alias) == legacy_alias
    assert _normalize_component(legacy_alias, normalize_axis_aliases=True).props == {
        "alignItems": "top",
    }


@pytest.mark.parametrize("alignment,valid", [("bottom", True), ("baseline", False)])
def test_final_protocol_still_rejects_baseline(alignment, valid):
    messages = [
        {"version": "v0.9", "createSurface": {
            "surfaceId": "test", "catalogId": "ohos.a2ui.extended.catalog.form",
        }},
        {"version": "v0.9", "updateComponents": {"surfaceId": "test", "components": [
            {"id": "root", "component": "Row", "children": ["value"],
             "styles": {"alignItems": alignment}},
            {"id": "value", "component": "Text", "content": "42项"},
        ]}},
        {"version": "v0.9", "updateDataModel": {"surfaceId": "test", "value": {}}},
    ]
    source = "\n".join(json.dumps(message) for message in messages)
    report = validate_card(dsl_text=source, options=ValidationOptions(stage="hard"))
    errors = [item for item in report.diagnostics if item.code == "STYLE_ENUM_INVALID"]
    assert bool(errors) is not valid
