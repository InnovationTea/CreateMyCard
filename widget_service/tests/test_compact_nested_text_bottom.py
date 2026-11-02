"""同行正文对齐；保留原字号、两行预算和动态绑定。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("label", [None, "日程"])
@pytest.mark.parametrize("max_lines,sample", [
    (1, "14:00 项目例会"),
    (2, "14:00 项目例会"),
    (2, "14:00\n项目例会"),
])
def test_labeled_body_uses_content_height_without_changing_line_capacity(
    size, max_lines, label, sample,
):
    item = {"value": {"path": "/data/event"}, "maxLines": max_lines}
    if label is not None:
        item["label"] = label
    rows = [
        ["root", "Column", {}, ["body"]],
        ["body", "SecondaryBody", {"columns": 1, "items": [item]}],
        ["/data/event", sample],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    messages = convert_compact_dsl_to_a2ui(source, size=size).splitlines()
    envelope = json.loads(messages[1])
    nodes = {}
    for component in envelope.get("updateComponents", {}).get("components", []):
        nodes[component.get("id")] = component
    value = nodes.get("body_item0_value")
    assert isinstance(value, dict)
    styles = value.get("styles", {})
    # Explicit multiline and single-line contracts retain their existing font and budget.
    font_size = 12 if max_lines == 2 else 14
    assert styles.get("fontSize") == font_size
    assert styles.get("maxLines") == max_lines
    assert styles.get("lineHeight") == 1
    assert value.get("content") == "{{ ${/data/event} }}"
    if label is not None and max_lines == 2:
        assert "height" not in styles
    else:
        assert styles.get("height") == font_size * max_lines
    for identifier in ("body_item0", "body_row0"):
        container = nodes.get(identifier)
        assert isinstance(container, dict)
        assert container.get("styles", {}).get("height") == font_size * max_lines
        expected_alignment = "top" if size == "2x2" else "start"
        assert container.get("styles", {}).get("alignItems") == expected_alignment
    item_node = nodes.get("body_item0")
    assert isinstance(item_node, dict)
    children = ["body_item0_value"]
    if label is not None:
        children.insert(0, "body_item0_label")
        label_node = nodes.get("body_item0_label")
        assert isinstance(label_node, dict)
        assert label_node.get("content") == label
        assert label_node.get("styles", {}).get("height") == font_size
    assert item_node.get("children") == children
    data = json.loads(messages[2]).get("updateDataModel", {}).get("value")
    assert data == {"data": {"event": sample}}


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("max_lines", [1, 2])
def test_nested_inline_body_keeps_slot_and_uses_actual_text_height(size, max_lines):
    font_size = 14 if max_lines == 1 else 12
    # 当前正文合同使用等字号行盒：单行14vp，多行每行12vp。
    line_height = font_size
    rows = [
        ["root", "Row", {"alignItems": "center", "itemMargin": 8}, ["value", "body"]],
        ["value", "EmphasizedData", {"value": 29, "unit": "℃", "fontSize": 30}],
        ["body", "SecondaryBody", {
            "fontSize": font_size, "layoutWeight": 1,
            "items": [{"value": {"path": "/data/status"}, "maxLines": max_lines}],
        }],
        ["/data/status", "多云"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = convert_compact_dsl_to_a2ui(source, size=size)
    nodes = {}
    for line in result.splitlines():
        envelope = json.loads(line)
        for component in envelope.get("updateComponents", {}).get("components", []):
            nodes[component.get("id")] = component
    root = nodes.get("root")
    body = nodes.get("body")
    text = nodes.get("body_item0_value")
    assert root is not None and body is not None and text is not None
    assert root.get("styles", {}).get("alignItems") == "bottom"
    assert root.get("itemMargin") == 8
    assert body.get("styles", {}).get("justifyContent") == "end"
    assert body.get("styles", {}).get("alignItems") == "start"
    assert text.get("styles", {}).get("fontSize") == font_size
    assert text.get("styles", {}).get("maxLines") == max_lines
    assert "height" not in text.get("styles", {})
    assert "${/data/status}" in text.get("content", "")
    for identifier in ("body_row0", "body_item0"):
        wrapper = nodes.get(identifier)
        assert wrapper is not None
        assert wrapper.get("styles", {}).get("height") == line_height * max_lines
        assert wrapper.get("styles", {}).get("alignItems") == "bottom"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_vertical_supporting_list_is_not_flattened_or_bottom_rewritten(size):
    rows = [
        ["root", "Row", {"alignItems": "center"}, ["value", "details"]],
        ["value", "EmphasizedData", {"value": 29, "unit": "℃"}],
        ["details", "SecondaryBody", {"columns": 1,
         "items": [{"value": "多云"}, {"value": "降雨概率20%"}]}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    envelope = json.loads(convert_compact_dsl_to_a2ui(source, size=size).splitlines()[1])
    components = envelope.get("updateComponents", {}).get("components", [])
    nodes = {item.get("id"): item for item in components}
    assert nodes.get("root", {}).get("styles", {}).get("alignItems") == "center"
    assert nodes.get("details", {}).get("children") == ["details_row0", "details_row1"]
    assert nodes.get("details_item0_value", {}).get("styles", {}).get("height") == 12
