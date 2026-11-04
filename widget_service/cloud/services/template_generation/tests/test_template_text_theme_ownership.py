"""模板文字随图片主题更新，保色不能锁死明确的主次主题引用。"""

from copy import deepcopy

import pytest

from services.post_layout_theme_registry import registered_themes
from services.template_generation.engine.cardplan.compiler import (
    _apply_theme_content_color,
    _battery_text,
    _bluetooth_text,
    _instantiate_blueprint,
    _lower_action_template_tree,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.photo_theme import (
    STYLE_MARKER,
    collect_photo_style_context,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.theme_photo_processing import apply_content_palette


def _photo_nodes(content, photo_id):
    shell = Nested2Node("Stack", (), (content,))
    ownership = collect_photo_style_context(shell)
    clean = _strip_advanced_component_markers(shell)
    nodes = []

    def visit(node, identity):
        options = next((value for value in node.values if isinstance(value, dict)), {})
        item = {"id": identity, "component": node.component_type, "styles": deepcopy(options)}
        item["values"] = tuple(value for value in node.values if not isinstance(value, dict))
        nodes.append(item)
        base = identity.removeprefix("__genui_render_component__")
        for index, child in enumerate(node.children):
            child_options = next((value for value in child.values if isinstance(value, dict)), {})
            visit(child, child_options.get("_id") or f"{base}_{index}")

    visit(clean.children[0], "__genui_render_component__root_1")
    before = deepcopy(nodes)
    photo = next(item for item in registered_themes("photos", include_disabled=True)
                 if item.get("id") == photo_id)
    palette = photo.get("content", {}).get("roles", {})
    apply_content_palette(nodes, palette, None, surface_style={}, legacy_panels=[],
                          ownership=ownership)
    return before, nodes, palette


@pytest.mark.parametrize("photo_id", [
    "photo-ux-cumulus-blue-wide", "photo-ux-meeting-room-brown-chairs-wide",
])
@pytest.mark.parametrize("kind", ["CompactAction", "CompactSubtitleAction"])
def test_registered_action_keeps_text_hierarchy_in_new_photo(kind, photo_id):
    registry = get_cardplan_registry(False)
    theme = registry.require_theme("family-weather-care-blue")
    node = _instantiate_blueprint(
        registry.require_variant(f"{kind}@1", "default").root,
        {"actionId": "event.test", "label": "查看天气", "subtitle": "今日概览",
         "icon": "", "prominent": False}, theme_values=theme.reference_values,
    )
    node = _lower_action_template_tree(
        Nested2Node(kind, (), (node,)), background=theme.action_style.background_color,
        foreground=theme.action_style.content_color,
    )
    before, after, palette = _photo_nodes(node, photo_id)
    colors = {"查看天气": palette.get("primary"), "今日概览": palette.get("secondary")}
    assert all(colors.values())
    seen = set()
    for original, updated in zip(before, after, strict=True):
        if original.get("component") == "Text":
            content = original.get("values", ())[0]
            expected = colors.get(content)
            if expected is not None:
                original.get("styles", {})["fontColor"] = expected
                seen.add(content)
        if kind == "CompactAction" and original.get("component") == "Image":
            # 普通动作图标原本就参与主题配色；本次不改变该行为。
            original.get("styles", {})["fillColor"] = palette.get("secondary")
        # 仅主题颜色变化；布局、动作和内容逐字段不变。
        assert original == updated
    assert seen == set(colors)
    assert "_templateTheme" not in str(after)


@pytest.mark.parametrize("kind", ["battery", "bluetooth"])
@pytest.mark.parametrize("secondary", [False, True])
def test_legacy_text_gets_theme_role_before_photo(kind, secondary):
    registry = get_cardplan_registry(False)
    theme = registry.require_theme("family-weather-care-blue")
    contract = HybridBodyContract.model_construct(theme_profile_id=theme.theme_profile_id)
    if kind == "battery":
        node = _battery_text("{{ /battery/level }}", "label", 10 if secondary else 14, 700)
    else:
        node = _bluetooth_text("{{ /earbud/level }}", "label", 12,
                               400 if secondary else 500, align="center")
    node = _apply_theme_content_color(node, contract, registry)
    before, after, palette = _photo_nodes(node, "photo-ux-cumulus-blue-wide")
    expected = theme.support_content_color if secondary else theme.primary_color
    assert before[0].get("styles", {}).get("fontColor") == expected
    before[0].get("styles", {})["fontColor"] = palette.get("secondary" if secondary else "primary")
    assert before == after


@pytest.mark.parametrize("kind", ["Text", "Button"])
def test_preserved_explicit_and_graphic_colors_remain_unchanged(kind):
    content = Nested2Node("Column", ({"_preserveOriginalColor": True},), (
        Nested2Node(kind, ("主题文字", {"fontColor": "#991F4799",
                                       STYLE_MARKER: {"fontColor": "@theme:secondary/1"}}), ()),
        Nested2Node("Text", ("自定义文字", {"fontColor": "#FF123456"}), ()),
        Nested2Node("Text", ("L", {"fontColor": "#FFFFFFFF"}), ()),
        Nested2Node("Image", ("icon.svg", {"fillColor": "#FF123456",
                                           STYLE_MARKER: {"fillColor": "@theme:primary/1"}}), ()),
    ))
    before, after, palette = _photo_nodes(content, "photo-ux-cumulus-blue-wide")
    before[1].get("styles", {})["fontColor"] = palette.get("secondary")
    assert before == after
