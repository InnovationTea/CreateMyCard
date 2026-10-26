"""辅助槽位按绑定/数值语义着色，不根据业务词汇，也不拆分文字节点。"""

import copy

import pytest

from services.compact_high_level_components import (
    ComponentRow,
    _expand_emphasis_text,
    _expand_info_block,
)
from services.theme_style_roles import layout_phase


def expand(kind, value, color, size, *, unit=False):
    props = {"fontColor": color, "secondaryText": copy.deepcopy(value)}
    if kind == "EmphasisText":
        props["mainText"] = "主读数"
        function = _expand_emphasis_text
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


@pytest.mark.parametrize("kind,unit", [
    ("EmphasisText", False), ("InfoBlock", False), ("InfoBlock", True),
])
@pytest.mark.parametrize("size", ["2x2", "2x4"])
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
    if unit:
        primary += "_value"
    by_id = {row.component_id: row for row in rows}
    main = by_id.get(primary)
    secondary = by_id.get("reading_secondary")
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
        if current.component_id == "reading_secondary":
            props["content"] = original.props.get("content")
            props["fontColor"] = original.props.get("fontColor")
        assert props == original.props


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_multiple_bound_values_remain_one_secondary_text(size):
    bindings = [{"path": "/data/custom/a"}, {"path": "/data/custom/b"}]
    rows = expand("EmphasisText", bindings, "#FFFFFFFF", size)
    assert len(rows) == 3
    secondary = next(row for row in rows if row.component_id == "reading_secondary")
    assert secondary.props.get("fontColor") == "#FFFFFFFF"
    assert secondary.props.get("content") == "{{ ${/data/custom/a} + ' | ' + ${/data/custom/b} }}"
