"""同一列表续行沿用表格值列，普通辅助文字保留原排列。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui


@pytest.mark.parametrize(
    ("value", "label", "max_lines", "align"),
    [
        ({"path": "/data/records/2/reading"}, "丙", 1, "end"),
        ("{{ ${/data/records/2/reading} }}", "丙", 1, "end"),
        ({"path": "/data/other/2/reading"}, "丙", 1, None),
        ({"path": "/data/records/2/description"}, "丙", 1, None),
        ({"path": "/data/records/1/reading"}, "丙", 1, None),
        ({"path": "/data/records/2/reading"}, None, 1, None),
        ({"path": "/data/records/2/reading"}, "丙", 2, None),
        ("{{ ${/data/records/2/reading} + '秒' }}", "丙", 1, None),
    ],
)
def test_only_single_line_labeled_members_continue_the_value_column(
    value: object, label: str | None, max_lines: int, align: str | None,
) -> None:
    item = {"value": value, "maxLines": max_lines}
    if label is not None:
        item["label"] = label
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["table", "tail"]],
        ["table", "TableText", {"items": [
            {"label": "甲", "value": {"path": "/data/records/0/reading"}},
            {"label": "乙", "value": {"path": "/data/records/1/reading"}},
        ], "fontSize": 12}],
        ["tail", "SecondaryBody", {"items": [item], "fontSize": 14}],
        ["/data/records/0/reading", "30秒"],
        ["/data/records/1/reading", "12秒"],
        ["/data/records/2/reading", "3秒"],
        ["/data/records/2/description", "说明"],
        ["/data/other/2/reading", "3秒"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    message = json.loads(converted.splitlines()[1]).get("updateComponents")
    assert message is not None
    components = message.get("components")
    assert components is not None
    nodes = {node.get("id"): node for node in components}
    value_node = nodes.get("tail_item0_value")
    assert value_node is not None
    styles = value_node.get("styles")
    assert styles is not None
    assert styles.get("textAlign") == align
    expected = value
    if isinstance(value, dict):
        expected = "{{ ${" + str(value.get("path")) + "} }}"
    assert value_node.get("content") == expected
    if max_lines == 1:
        assert styles.get("fontSize") == 14
