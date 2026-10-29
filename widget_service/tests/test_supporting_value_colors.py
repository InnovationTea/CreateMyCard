"""辅助槽位按绑定/数值语义着色，不根据业务词汇，也不拆分文字节点。"""

import copy
import json

import pytest

from services import post_layout_theme as themes
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_high_level_components import (
    ComponentRow,
    _expand_data_display,
    _expand_emphasis_text,
    _expand_info_block,
)
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import layout_phase


def expand(kind, value, color, size, *, unit=False):
    props = {"fontColor": color, "secondaryText": copy.deepcopy(value)}
    if kind == "EmphasisText":
        props["mainText"] = "主读数"
        function = _expand_emphasis_text
    elif kind == "DataDisplay":
        props.pop("secondaryText")
        props.update(label="标题", value="主区读数", supportingText=copy.deepcopy(value))
        function = _expand_data_display
    else:
        props.update(primaryText="主读数", backgroundColor="#33000000")
        props["variant"] = "stacked" if size == "2x2" else "slot"
        if unit:
            props["unit"] = "单位"
        function = _expand_info_block
    component = ComponentRow("reading", kind, props)
    before = copy.deepcopy(component)
    with layout_phase(color.startswith("@theme:")):
        rows = function(component, size)
    assert component == before
    return rows


@pytest.mark.parametrize("kind,unit,size", [
    ("EmphasisText", False, "2x2"), ("EmphasisText", False, "2x4"),
    ("InfoBlock", False, "2x2"), ("InfoBlock", False, "2x4"),
    ("InfoBlock", True, "2x2"), ("InfoBlock", True, "2x4"),
    ("DataDisplay", False, "2x2"),
])
@pytest.mark.parametrize("color", ["#FFFFFFFF", "#FF000000", "#FF563D99", "@theme:primary/1"])
@pytest.mark.parametrize("value,emphasize", [
    ({"path": "/data/custom/value"}, True),
    ("{{ '说明 ' + ${/data/custom/value} }}", True),
    ("{{ ('任意标签 ' + ${/data/custom/value}) + ' 单位' }}", True),
    ("{{ ${/data/custom/state} ? '状态甲' : '状态乙' }}", True),
    (0, True),
    ("数据 ${/data/custom/value} 示例", False),
    ("普通辅助说明", False),
    ("{{ '固定文字' }}", False),
])
def test_supporting_values_keep_full_ink_and_all_foreground_structure(
    kind, unit, size, color, value, emphasize,
):
    rows = expand(kind, value, color, size, unit=unit)
    baseline = expand(kind, "普通辅助说明", color, size, unit=unit)
    primary = "reading_main" if kind == "EmphasisText" else "reading_primary"
    secondary_id = "reading_secondary"
    if kind == "DataDisplay":
        primary = "reading_value"
        secondary_id = "reading_supporting"
    if unit:
        primary += "_value"
    by_id = {row.component_id: row for row in rows}
    main = by_id.get(primary)
    secondary = by_id.get(secondary_id)
    assert main is not None and secondary is not None
    expected = color if emphasize else "#99" + color[3:]
    if not emphasize and color.startswith("@theme:"):
        expected = "@theme:primary/0.6"
    assert secondary.props.get("fontColor") == expected
    assert secondary.props.get("content") == value
    assert main.props.get("fontColor") == color
    # 与同组件的说明文字比较：仅这个槽位的内容和颜色可以不同。
    for current, original in zip(rows, baseline, strict=True):
        assert current.component_id == original.component_id
        assert current.component_type == original.component_type
        assert current.children == original.children
        props = copy.deepcopy(current.props)
        if current.component_id == secondary_id:
            props["content"] = original.props.get("content")
            props["fontColor"] = original.props.get("fontColor")
        assert props == original.props


@pytest.mark.parametrize("color", ["#FFFFFFFF", "#FF000000", "@theme:primary/1"])
@pytest.mark.parametrize("leading,value", [
    ({"label": "标题"}, 42),
    ({"label": "标题"}, "主区读数"),
    ({"icon": "resources/base/media/ic_weather_monochrome.svg"}, "主区读数"),
])
def test_data_display_supporting_value_keeps_label_icon_and_primary_unchanged(
    color, leading, value,
):
    props = {
        **leading, "value": value, "supportingText": {"path": "/data/custom/value"},
        "fontColor": color,
    }
    if "icon" in props:
        props["fillColor"] = color
    component = ComponentRow("reading", "DataDisplay", props)
    original = copy.deepcopy(component)
    with layout_phase(color.startswith("@theme:")):
        rows = _expand_data_display(component, "2x2")
    assert component == original
    by_id = {row.component_id: row for row in rows}
    supporting = by_id.get("reading_supporting")
    primary = by_id.get("reading_value")
    assert supporting is not None and primary is not None
    assert supporting.props.get("fontColor") == primary.props.get("fontColor") == color
    if "label" in props:
        label = by_id.get("reading_label")
        assert label is not None
        expected = "@theme:primary/0.6" if color.startswith("@theme:") else "#99" + color[3:]
        assert label.props.get("fontColor") == expected
    else:
        icon = by_id.get("reading_icon")
        assert icon is not None
        assert icon.props.get("src") == props.get("icon")
        assert icon.props.get("fillColor") == color


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_multiple_bound_values_remain_one_secondary_text(size):
    bindings = [{"path": "/data/custom/a"}, {"path": "/data/custom/b"}]
    rows = expand("EmphasisText", bindings, "#FFFFFFFF", size)
    assert len(rows) == 3
    secondary = next(row for row in rows if row.component_id == "reading_secondary")
    assert secondary.props.get("fontColor") == "#FFFFFFFF"
    assert secondary.props.get("content") == "{{ ${/data/custom/a} + ' | ' + ${/data/custom/b} }}"


@pytest.mark.parametrize("theme_id", [
    "photo-ux-texture-blue-circles-square", "photo-ux-meeting-room-square", "solid-blue",
])
@pytest.mark.parametrize("overrides", [
    {},
    {"background": {"color": "#FF3B82F6", "panelColor": "#331A1A1A"}},
    {"text": {"color": "#FF563D99"}},
])
@pytest.mark.parametrize("supporting,emphasize", [
    ("{{ '任意标签 ' + ${/data/custom/value} }}", True),
    ("普通辅助说明", False),
])
def test_data_display_full_conversion_respects_theme_and_user_colors(
    theme_id, overrides, supporting, emphasize,
):
    theme = next(item for item in registered_themes() if item.get("id") == theme_id)
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "S-center"}, ["reading"]],
        ["reading", "DataDisplay", {"label": "标题", "value": 42,
                                    "supportingText": supporting}],
        ["/data/custom/value", "任意读数"],
    ])
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(compact, size="2x2")
    task = {"size": "2x2", "appVersion": "11.9.9.342"}
    final = themes.apply_theme(source, theme, task, overrides)
    nodes = {node.get("id"): node for node in themes.components(themes.decode(final))}
    main = nodes.get("reading_value", {}).get("styles", {}).get("fontColor")
    assert isinstance(main, str) and main.startswith("#FF")
    expected = main if emphasize else "#99" + main[3:]
    assert nodes.get("reading_supporting", {}).get("styles", {}).get("fontColor") == expected
    assert nodes.get("reading_supporting", {}).get("content") == supporting
    assert nodes.get("reading_label", {}).get("styles", {}).get("fontColor") == "#99" + main[3:]
    assert themes.foreground_signature(source) == themes.foreground_signature(final)
