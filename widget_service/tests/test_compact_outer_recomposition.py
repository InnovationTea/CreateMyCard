"""小卡确定性重组遵循无 role 正文合同，并在实际处理器中闭合容量。"""

import copy
import json

import pytest

from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_outer_recomposition import (
    _paragraph,
    _reflow_items,
    _wrap_complete_value_rows,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


@pytest.mark.parametrize("legacy_role", [None, "supporting", "body", "metadata"])
def test_short_attribute_uses_layout_instead_of_legacy_role(legacy_role: str | None) -> None:
    props = {"items": [{"label": "状态 ", "value": "正常"}], "fontSize": 14}
    if legacy_role is not None:
        props["role"] = legacy_role
    row = ComponentRow("status", "SecondaryBody", props)
    before = copy.deepcopy(row)
    assert _reflow_items(row) == props.get("items")
    assert row == before


def test_wrapped_value_uses_multiline_recipe_and_keeps_expression() -> None:
    expression = "{{ ${/data/device/status} + '，请检查设备' }}"
    row = ComponentRow("status", "SecondaryBody", {
        "fontSize": 14, "items": [{"value": expression}],
    })
    task = {"dataModelSchema": {"data": {"device": {
        "status": {"type": "string", "sampleValue": "当前设备运行正常"},
    }}}}
    before = copy.deepcopy(row)
    rows, changed = _wrap_complete_value_rows([row], task, 126.0)
    assert changed
    assert rows[0].props == {
        "fontSize": 12, "items": [{"value": expression, "maxLines": 2}],
    }
    assert row == before


def test_paragraph_keeps_same_object_bindings_and_does_not_merge_other_objects() -> None:
    title = ComponentRow("title", "SingleLineTitle", {"title": "天气"})
    values = [
        ComponentRow("temperature", "SecondaryBody", {
            "fontSize": 14,
            "items": [{"label": "温度 ", "value": {"path": "/data/weather/temperature"}}],
        }),
        ComponentRow("humidity", "SecondaryBody", {
            "fontSize": 14,
            "items": [{"label": "湿度 ", "value": {"path": "/data/weather/humidity"}}],
        }),
    ]
    task = {"dataModelSchema": {"data": {"weather": {
        "temperature": {"type": "string", "sampleValue": "26℃"},
        "humidity": {"type": "string", "sampleValue": "60%"},
    }, "device": {"battery": {"type": "string", "sampleValue": "68%"}}}}}
    leaves = [title, *values]
    before = copy.deepcopy(leaves)
    grouped = _paragraph(leaves, task, 126.0)
    assert grouped is not None and len(grouped) == 2
    props = grouped[1].props
    assert props.get("fontSize") == 12
    assert "role" not in props
    items = props.get("items")
    assert isinstance(items, list)
    expression = items[0].get("value")
    assert "/data/weather/temperature" in expression
    assert "/data/weather/humidity" in expression
    assert items[0].get("maxLines") == 2
    other = ComponentRow("battery", "SecondaryBody", {
        "fontSize": 14,
        "items": [{"label": "电量 ", "value": {"path": "/data/device/battery"}}],
    })
    assert _paragraph([title, values[0], other], task, 126.0) is None
    assert leaves == before


def test_small_processor_recomposes_roleless_source_with_real_validation() -> None:
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent",
                            "padding": 12, "itemMargin": 6}, ["title", "body"]],
        ["title", "SingleLineTitle", {"title": "设备状态", "fontSize": 12}],
        ["body", "Column", {"width": "matchParent", "height": 50,
                            "alignItems": "start", "justifyContent": "end"}, ["content"]],
        ["content", "Column", {"width": "matchParent", "itemMargin": 20},
         ["primary", "status"]],
        ["primary", "EmphasisText", {"mainText": "设备运行正常", "fontSize": 18}],
        ["status", "SecondaryBody", {"fontSize": 14, "items": [
            {"value": {"path": "/data/device/status"}},
        ]}],
        ["/data/device/status", "当前设备运行正常，请检查设备"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    context = DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"},
        task_spec={"size": "2x2", "appVersion": "99.0", "dataModelSchema": {"data": {"device": {
            "status": {"type": "string", "sampleValue": "当前设备运行正常，请检查设备"},
        }}}},
        protocol_profile={"version": "v0.9", "appVersion": "99.0"},
        layout_scope="S-title-content",
        compact_plan={"info_required": [{"dataId": "/data/device/status",
                                         "requirement": "设备状态", "priority": "must"}]},
    )
    result = DesignCompactProcessor().process(source, context)
    assert result.errors == ()
    assert result.standard_dsl
    assert result.source_dsl != source
    secondary = None
    for row in parse_compact_dsl_rows(result.source_dsl):
        if isinstance(row, ComponentRow) and row.component_id == "status":
            secondary = row
            break
    assert secondary is not None
    assert secondary.props.get("fontSize") == 12
    assert "role" not in secondary.props
    assert secondary.props.get("items") == [
        {"value": {"path": "/data/device/status"}, "maxLines": 2},
    ]
