"""PR #522：模板环形槽位必须能够完整转换，不能要求模型补几何。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
    serialize_compact_dsl_source,
)


def _source(variant: str, *, header: str = "plain", action: bool = False) -> str:
    count = 4 if variant in {"four-ratios", "four-items"} else 2
    rings = [f"ring{index}" for index in range(count)]
    children = list(rings)
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["content", "info", "open"]],
        ["info", "InfoBlock", {"variant": "slot", "primaryText": "在线",
                              "secondaryText": "设备状态", "backgroundColor": "#99FFFFFF"}],
        ["open", "CardButton", {"label": "设备设置", "onClick": [{"call": "open", "args": {}}]}],
    ]
    if count == 2:
        children.insert(0, "header")
        props = {"title": "设备电量"}
        kind = "SingleLineTitle"
        if header == "icon":
            props["icon"] = "resources/base/media/battery_leaf_fill.svg"
        if header == "double":
            kind = "DoubleLineTitle"
            props["secondaryInfo"] = "连接的设备"
        if header == "badge":
            rows.extend([
                ["header", "Group", {"variant": "title-count"}, ["title", "badge"]],
                ["title", "SingleLineTitle", props],
                ["badge", "Badge", {"value": "2", "backgroundColor": "#99FFFFFF"}],
            ])
        else:
            rows.append(["header", kind, props])
        if action:
            children.append("more")
            rows.append(["more", "PillButton", {"label": "查看设备", "onClick": [{
                "call": "open", "args": {},
            }]}])
    rows.append(["content", "Region", {"variant": variant}, children])
    for index, identifier in enumerate(rings):
        path = f"/data/device{index}/percent"
        rows.append([identifier, "ProgressCircle", {
            "externalText": {"path": path},
            "icon": "resources/base/media/battery_leaf_fill.svg",
            "accessibility": {"label": f"设备{index}电量"},
            "fillColor": "#FF1F4799", "color": "#FF1F4799", "backgroundColor": "#331F4799",
        }])
        rows.append([path, 68 - index])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("variant", ["title-two-ratios", "four-ratios", "four-items"])
def test_semantic_ratio_slots_convert_and_preserve_binding_and_source(variant: str) -> None:
    source = _source(variant)
    parsed = parse_compact_dsl_rows(source, size="2x4")
    rings = [row for row in parsed if isinstance(row, ComponentRow)
             and row.component_type == "ProgressCircle"]
    expected_height = 106 if variant == "title-two-ratios" else 59
    for row in rings:
        assert row.props.get("width") == 62
        assert row.props.get("height") == expected_height
    saved = serialize_compact_dsl_source(source)
    assert '"width"' not in saved
    assert '"height"' not in saved
    messages = [json.loads(line) for line in convert_compact_dsl_to_a2ui(
        source, size="2x4",
    ).splitlines()]
    assert len(messages) == 3
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    for index, row in enumerate(rings):
        progress = next(item for item in components if item.get("id") == row.component_id + "_ring")
        assert progress.get("component") == "Progress"
        assert progress.get("value") == "{{ ${/data/device" + str(index) + "/percent} }}"
        icon = next(item for item in components if item.get("id") == row.component_id + "_icon")
        assert icon.get("src") == "resources/base/media/battery_leaf_fill.svg"


@pytest.mark.parametrize("header,height", [("icon", 98), ("badge", 102), ("double", 60)])
def test_ring_height_accounts_for_current_header_recipe(header: str, height: int) -> None:
    source = _source("title-two-ratios", header=header)
    parsed = parse_compact_dsl_rows(source, size="2x4")
    ring = next(row for row in parsed
                if isinstance(row, ComponentRow) and row.component_id == "ring0")
    assert ring.props.get("height") == height
    convert_compact_dsl_to_a2ui(source, size="2x4")


def test_optional_button_reserves_its_recipe_height() -> None:
    source = _source("title-two-ratios", action=True)
    parsed = parse_compact_dsl_rows(source, size="2x4")
    ring = next(row for row in parsed
                if isinstance(row, ComponentRow) and row.component_id == "ring0")
    assert ring.props.get("height") == 62
    convert_compact_dsl_to_a2ui(source, size="2x4")


def test_over_budget_title_and_button_do_not_shrink_minimum_ring() -> None:
    with pytest.raises(CompactDslConversionError, match="leave less than 40"):
        convert_compact_dsl_to_a2ui(
            _source("title-two-ratios", header="icon", action=True), size="2x4",
        )


def test_author_geometry_is_still_rejected() -> None:
    source = _source("four-ratios").replace('"externalText":', '"width": 62, "externalText":', 1)
    with pytest.raises(CompactDslConversionError, match="业务几何由模板负责"):
        parse_compact_dsl_rows(source, size="2x4")
