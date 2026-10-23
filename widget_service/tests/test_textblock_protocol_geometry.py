"""TextBlock 等高依赖子项填满父高，不依赖协议外的 stretch。"""

import json

import pytest

from services.card_validation import ValidationOptions, validate_card
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_high_level_components import ComponentRow, _expand_text_block
from services.post_layout_theme import apply_theme, foreground_signature, presets
from services.theme_style_roles import layout_phase


def text_block(count: int) -> ComponentRow:
    items = []
    for index in range(count):
        items.append({"label": f"指标{index}", "value": f"读数{index}"})
    return ComponentRow("details", "TextBlock", {"items": items, "fontColor": "#FF1F4799"})


@pytest.mark.parametrize("count", [2, 3, 4])
def test_textblock_keeps_fill_height_and_equal_width_with_protocol_alignment(count: int) -> None:
    rows = _expand_text_block(text_block(count), "2x4")
    registry = {}
    for row in rows:
        registry[row.component_id] = row
    root = registry.get("details")
    assert root is not None
    assert root.props.get("alignItems") == "top"
    assert root.props.get("height") == "matchParent"
    assert root.props.get("itemMargin") == 8
    assert root.props.get("constraintSize") == {"minHeight": 48}
    for identity in root.children:
        item = registry.get(identity)
        assert item is not None
        assert item.props.get("height") == "matchParent"
        assert item.props.get("layoutWeight") == 1
        assert item.props.get("justifyContent") == "center"
        assert item.props.get("constraintSize") == {"minWidth": 0, "minHeight": 0}


@pytest.mark.parametrize("alignment,valid", [("top", True), ("stretch", False)])
def test_final_protocol_still_rejects_stretch(alignment: str, valid: bool) -> None:
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "test",
         "catalogId": "ohos.a2ui.extended.catalog.form"}},
        {"version": "v0.9", "updateComponents": {"surfaceId": "test", "components": [
        {"id": "root", "component": "Row", "children": ["value"],
         "styles": {"alignItems": alignment, "width": "matchParent", "height": "matchParent"}},
        {"id": "value", "component": "Text", "content": "值"},
        ]}},
        {"version": "v0.9", "updateDataModel": {"surfaceId": "test", "value": {}}},
    ]
    source = "\n".join(json.dumps(message) for message in messages)
    report = validate_card(dsl_text=source, options=ValidationOptions(stage="hard"))
    failures = []
    for item in report.diagnostics:
        if item.code == "STYLE_ENUM_INVALID":
            failures.append(item)
    assert bool(failures) is not valid


@pytest.mark.parametrize("count", [2, 3, 4])
def test_textblock_theme_preserves_geometry_and_passes_final_style_enum(count: int) -> None:
    block = text_block(count)
    rows = [
        ["root", "Layout", {"layout": "W-top-bottom"}, ["title", "hero", "details"]],
        ["title", "SingleLineTitle", {"title": "概览", "fontSize": 12}],
        ["hero", "EmphasizedData", {"value": 32, "unit": "项", "fontSize": 30}],
        [block.component_id, block.component_type, block.props],
        ["/state/ready", True],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    profile = {"version": "v0.9", "catalogId": "ohos.a2ui.extended.catalog.form"}
    with layout_phase():
        converted = convert_compact_dsl_to_a2ui(source, size="2x4", protocol_profile=profile)
    task = {"size": "2x4", "userQuery": "查看概览"}
    theme = next(item for item in presets(task) if item.get("id") == "gradient-blue")
    themed = apply_theme(converted, theme, task, {})
    assert foreground_signature(converted) == foreground_signature(themed)
    report = validate_card(dsl_text=themed, options=ValidationOptions(stage="hard"))
    for diagnostic in report.diagnostics:
        assert diagnostic.code != "STYLE_ENUM_INVALID"
