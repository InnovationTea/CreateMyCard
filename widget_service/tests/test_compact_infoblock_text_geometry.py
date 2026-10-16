"""固定信息槽的文字规格；不改变数据、visual 的尺寸或小卡规格。"""

import json

import pytest

from services.compact_component_runtime import visual_recipe_part
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui


def _styles(part: str, *, size: str = "2x4") -> dict:
    _, styles = visual_recipe_part("InfoBlock", part, size=size)
    return styles


@pytest.mark.parametrize("part", ["primary", "primaryValue"])
def test_wide_primary_text_uses_same_line_box_with_or_without_unit(part: str) -> None:
    styles = _styles(part)
    assert styles.get("fontSize") == 14
    assert styles.get("fontWeight") == 700
    assert styles.get("height") == 19
    assert styles.get("fontSize") * styles.get("lineHeight") == pytest.approx(19)


def test_wide_copy_keeps_top_inset_without_moving_visual() -> None:
    copy = _styles("copy")
    assert copy.get("height") == "matchParent"
    assert copy.get("padding") == {"top": 8}
    assert copy.get("justifyContent") == "start"
    assert copy.get("itemMargin") == 2
    secondary = _styles("secondary")
    assert secondary.get("fontSize") == 12
    assert secondary.get("fontWeight") == 500
    assert secondary.get("height") == 16
    assert secondary.get("fontSize") * secondary.get("lineHeight") == pytest.approx(16)
    for part in ("root", "rootNoVisual"):
        root = _styles(part)
        assert root.get("height") == 57
        assert root.get("padding") == {"left": 8, "right": 8}
        assert root.get("justifyContent") in {"center", "spaceBetween"}
    assert _styles("root").get("alignItems") == "center"
    assert _styles("icon").get("height") == 24
    assert _styles("progressStack").get("height") == 44
    assert _styles("progressIcon").get("height") == 20
    assert _styles("primaryRow").get("height") == 19
    assert _styles("primaryRow").get("alignItems") == "bottom"


def test_small_card_info_recipe_is_unchanged() -> None:
    copy = _styles("copy", size="2x2")
    assert "height" not in copy
    assert "padding" not in copy
    assert copy.get("itemMargin") == 0
    assert copy.get("justifyContent") == "center"
    assert _styles("primary", size="2x2").get("fontSize") == 16
    assert _styles("primaryValue", size="2x2").get("height") == 22
    assert _styles("secondary", size="2x2").get("fontSize") == 10
    assert _styles("root", size="2x2").get("height") == 63


@pytest.mark.parametrize("visual", [None, "icon", "progressCircle"])
@pytest.mark.parametrize("unit", [None, "%"])
def test_semantic_fixed_slot_conversion_preserves_binding_and_geometry(visual, unit) -> None:
    info = {
        "variant": "slot", "primaryText": {"path": "/data/level"},
        "secondaryText": "设备电量", "fontColor": "#FF1F4799",
        "backgroundColor": "#99FFFFFF",
    }
    if visual is not None:
        info["visual"] = {"type": visual, "icon": "resources/base/media/battery_leaf_fill.svg"}
    if unit is not None:
        info["unit"] = unit
    rows = [
        ["root", "Layout", {"layout": "W-four-slots"}, ["info", "a", "b", "c"]],
        ["info", "InfoBlock", info],
        ["a", "InfoBlock", {**info, "primaryText": "在线", "visual": None}],
        ["b", "InfoBlock", {**info, "primaryText": "正常", "visual": None}],
        ["c", "InfoBlock", {**info, "primaryText": "启用", "visual": None}],
        ["/data/level", 62],
    ]
    for row in rows[2:5]:
        row[2].pop("visual", None)
        row[2].pop("unit", None)
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = convert_compact_dsl_to_a2ui(source, size="2x4")
    components = {}
    for line in result.splitlines():
        update = json.loads(line).get("updateComponents")
        if not update:
            continue
        for component in update.get("components", []):
            components[component.get("id")] = component
    text_id = "info_primary_value" if unit else "info_primary"
    primary = components.get(text_id)
    assert primary is not None
    assert primary.get("content") == "{{ ${/data/level} }}"
    styles = primary.get("styles")
    assert styles is not None and styles.get("height") == 19
    assert styles.get("fontSize") == 14
    copy = components.get("info_text")
    assert copy is not None
    copy_styles = copy.get("styles")
    assert copy_styles is not None
    assert copy_styles.get("height") == "matchParent"
    assert copy_styles.get("padding") == {"top": 8}
    secondary = components.get("info_secondary")
    assert secondary is not None
    secondary_styles = secondary.get("styles")
    assert secondary_styles is not None
    assert secondary_styles.get("textOverflow") == "ellipsis"
    if visual == "progressCircle":
        ring = components.get("info_visual_progress")
        assert ring is not None
        assert ring.get("value") == "{{ ${/data/level} }}"
        ring_styles = ring.get("styles")
        assert ring_styles is not None and ring_styles.get("height") == 44
