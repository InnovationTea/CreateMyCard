"""Structured label/value components share emphasis across businesses and themes."""

import copy
import json

import pytest

from services import compact_high_level_components as high_level
from services import post_layout_theme as themes
from services.compact_dsl_a2ui_converter import ComponentRow, convert_compact_dsl_to_a2ui
from services.compact_high_level_components import _expand_secondary_body
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import layout_phase

PAIR_CASES = [
    ("SecondaryBody", "2x2"), ("SecondaryBody", "2x4"),
    ("TableText", "2x2"), ("TableText", "2x4"),
    ("TextBlock", "2x4"),
    ("H_BarChart", "2x2"), ("H_BarChart", "2x4"),
    ("ProgressCircleSingle", "2x2"), ("ProgressCircleSingle", "2x4"),
    ("DataDisplay", "2x2"), ("TopTextBottomValue", "2x4"),
]


def structured_pair_rows(kind, size, color):
    items = [{"label": "业务甲", "value": {"path": "/data/first"}},
             {"label": "业务乙", "value": {"path": "/data/second"}}]
    props = {"fontColor": color}
    label_id = "pair_item0_label"
    value_id = "pair_item0_value"
    if kind == "SecondaryBody":
        props["items"] = items
        expander = high_level._expand_secondary_body
    elif kind == "TableText":
        props["items"] = items
        label_id, value_id = "pair_row0_label", "pair_row0_value"
        expander = high_level._expand_table_text
    elif kind == "TextBlock":
        props["items"] = items
        expander = high_level._expand_text_block
    elif kind == "H_BarChart":
        props.update(items=[{"label": "业务甲", "valueUnit": {"path": "/data/first"},
                             "percent": 30},
                            {"label": "业务乙", "valueUnit": {"path": "/data/second"},
                             "percent": 60}], barColor=color, trackColor="#33000000")
        expander = high_level._expand_h_bar_chart
    elif kind == "ProgressCircleSingle":
        props.update(label="业务甲", displayValue={"path": "/data/first"}, value=30,
                     total=100, secondaryLabel="补充说明", color=color,
                     backgroundColor="#33000000", icon="resources/base/media/battery_leaf_fill.svg")
        label_id, value_id = "pair_label", "pair_display"
        expander = high_level._expand_progress_circle_single
    elif kind == "DataDisplay":
        props.update(label="业务甲", value=30, supportingText="补充说明")
        label_id, value_id = "pair_label", "pair_value"
        expander = high_level._expand_data_display
    elif kind == "TopTextBottomValue":
        props.update(items=[{"label": "业务甲", "value": {"path": "/data/first"}, "unit": "分"},
                            {"label": "业务乙", "value": {"path": "/data/second"}, "unit": "分"},
                            {"label": "业务丙", "value": 90, "unit": "分"}],
                     dividerColor="#33000000")
        expander = high_level._expand_top_text_bottom_value
    else:
        raise ValueError("Unknown structured pair component: " + kind)
    component = ComponentRow("pair", kind, props)
    return {"rows": expander(component, size), "component": component,
            "labelId": label_id, "valueId": value_id}


@pytest.mark.parametrize("kind,size", PAIR_CASES)
@pytest.mark.parametrize("color", ["#FFFFFFFF", "#FF000000", "#FF1F4799"])
def test_all_structured_pairs_dim_labels_and_emphasize_values(kind, size, color):
    sample = structured_pair_rows(kind, size, color)
    nodes = {row.component_id: row for row in sample.get("rows", [])}
    label = nodes.get(sample.get("labelId"))
    value = nodes.get(sample.get("valueId"))
    assert label is not None and value is not None
    assert label.props.get("fontColor") == "#99" + color[3:]
    assert value.props.get("fontColor") == color
    for identity in ("pair_secondary", "pair_supporting"):
        support = nodes.get(identity)
        if support is not None:
            assert support.props.get("fontColor") == "#99" + color[3:]


@pytest.mark.parametrize("kind,size", PAIR_CASES)
@pytest.mark.parametrize("colorless", [False, True])
def test_full_converter_keeps_all_pair_values_in_primary_role(kind, size, colorless):
    sample = structured_pair_rows(kind, size, "#FF1F4799")
    component = sample.get("component")
    assert component is not None
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["pair"]],
        ["pair", kind, component.props], ["/data/first", 30], ["/data/second", 60],
    ])
    with layout_phase(colorless):
        source = convert_compact_dsl_to_a2ui(compact, size=size)
    nodes = {node.get("id"): node for node in themes.components(themes.decode(source))}
    label = nodes.get(sample.get("labelId"), {}).get("styles", {}).get("fontColor")
    value = nodes.get(sample.get("valueId"), {}).get("styles", {}).get("fontColor")
    if colorless:
        assert label == "@theme:primary/0.6"
        assert value == "@theme:primary/1"
    else:
        assert isinstance(value, str) and value.startswith("#FF")
        assert label == "#99" + value[3:]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("columns", [1, 2])
@pytest.mark.parametrize("color", ["#FFFFFFFF", "#FF000000", "#FF1F4799", "#FF8C4B1C"])
def test_secondary_labels_are_dim_and_bound_values_use_primary_color(size, columns, color):
    component = ComponentRow("support", "SecondaryBody", {
        "fontColor": color, "columns": columns, "items": [
            {"label": "天气 ", "value": {"path": "/data/weather/condition"}},
            {"label": "湿度 ", "value": "{{ ${/data/weather/humidity} + '%' }}"},
        ],
    })
    before = copy.deepcopy(component)
    rows = _expand_secondary_body(component, size)
    by_id = {row.component_id: row for row in rows}
    for index in range(2):
        label = by_id.get(f"support_item{index}_label")
        value = by_id.get(f"support_item{index}_value")
        assert label is not None and value is not None
        assert label.props.get("fontColor") == "#99" + color[3:]
        assert value.props.get("fontColor") == color
    assert component == before
    value = by_id.get("support_item0_value")
    assert value is not None
    assert value.props.get("content") == {"path": "/data/weather/condition"}
    for row in rows:
        if row.component_id.endswith("_separator"):
            assert row.props.get("fontColor") == "#99" + color[3:]


def test_standalone_supporting_text_keeps_existing_dim_color():
    component = ComponentRow("support", "SecondaryBody", {
        "fontColor": "#FFFFFFFF", "items": [{"value": "夜间睡眠时长"}],
    })
    rows = _expand_secondary_body(component, "2x2")
    value = next(row for row in rows if row.component_id == "support_item0_value")
    assert value.props.get("fontColor") == "#99FFFFFF"


def test_existing_merged_multiline_value_is_not_split_to_change_color():
    component = ComponentRow("support", "SecondaryBody", {
        "fontColor": "#FF000000", "columns": 1,
        "items": [{"label": "地点 ", "value": {"path": "/data/location"}}],
    })
    rows = _expand_secondary_body(
        component, "2x2", data_model={"data": {"location": "会议室会议室会议室"}},
        available_width=80,
    )
    assert not any(row.component_id == "support_item0_label" for row in rows)
    value = next(row for row in rows if row.component_id == "support_item0_value")
    assert value.props.get("fontColor") == "#FF000000"
    assert "地点 " in value.props.get("content", "")
    assert "/data/location" in value.props.get("content", "")
    assert value.props.get("maxLines") == 2


@pytest.mark.parametrize("theme", registered_themes(), ids=lambda theme: theme.get("id"))
def test_every_theme_resolves_label_value_roles_without_rewriting_foreground(theme):
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"},
         ["header", "primary", "support"]],
        ["header", "SingleLineTitle", {"title": "下一场会议"}],
        ["primary", "EmphasisText", {"mainText": "14:00"}],
        ["support", "SecondaryBody", {"items": [
            {"label": "地点 ", "value": {"path": "/data/calendar/location"}},
        ]}],
        ["/data/calendar/location", "会议室"],
    ]
    task = {"size": theme.get("sizes", ["2x2"])[0], "appVersion": "11.9.9.342"}
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size=task.get("size"))
    final = themes.apply_theme(source, theme, task, {})
    nodes = {node.get("id"): node for node in themes.components(themes.decode(final))}
    label = nodes.get("support_item0_label", {})
    value = nodes.get("support_item0_value", {})
    header = nodes.get("header_title", {})
    roles = theme.get("content", {}).get("roles", {})
    primary = roles.get("primary")
    assert isinstance(primary, str)
    assert label.get("styles", {}).get("fontColor") == "#99" + primary[3:]
    assert value.get("styles", {}).get("fontColor") == primary
    assert header.get("styles", {}).get("fontColor") == roles.get("secondary")
    assert themes.foreground_signature(source) == themes.foreground_signature(final)
