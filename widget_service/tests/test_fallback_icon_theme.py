"""Converter-injected fallback SVG follows button ink, including after URL mapping."""

import copy

import pytest

from services import post_layout_theme as themes
from services.asset_url_mapper import AssetUrlMapper
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_high_level_components import (
    CompactDslConversionError,
    ComponentRow,
    apply_system_component_colors,
)
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import layout_phase

FALLBACK = "resources/base/media/ic_fallback_light.svg"
URL = "https://hagres-drcn.dbankcdn.com/assets/fallback.svg?version=1"


def fallback_source(size):
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["button"]],
        ["button", "CardButton", {"label": "睡眠详情", "onClick": [
            {"call": "clickToDeeplink", "args": {"intentName": "Health", "bundleName": "",
             "abilityName": "", "uri": "huaweischeme://healthapp/router/sleepDetail"}},
        ]}],
    ]
    original = copy.deepcopy(rows)
    with layout_phase():
        source = convert_compact_dsl_to_a2ui(themes.encode(rows), size=size)
    assert rows == original
    return source


@pytest.mark.parametrize("theme", registered_themes(), ids=lambda item: item.get("id"))
@pytest.mark.parametrize("remote", [False, True])
def test_fallback_svg_uses_theme_ink_without_layout_or_url_changes(theme, remote):
    size = theme.get("size", "2x2")
    source = fallback_source(size)
    if remote:
        source = AssetUrlMapper({FALLBACK: URL}, set()).rewrite_standard(source)
    result = themes.apply_theme(source, theme, {"size": size, "appVersion": "11.9.9.342"}, {})
    nodes = {node.get("id"): node for node in themes.components(themes.decode(result))}
    image = nodes.get("button_visual", {})
    label = nodes.get("button_label", {})
    assert image.get("src") == (URL if remote else FALLBACK)
    assert image.get("styles", {}).get("fillColor") == label.get("styles", {}).get("fontColor")
    primary = theme.get("content", {}).get("roles", {}).get("primary")
    assert image.get("styles", {}).get("fillColor") == primary
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    assert "@theme:" not in result


@pytest.mark.parametrize("icon", [
    "resources/base/media/emoji_z.png", "resources/base/media/sun.svg",
])
def test_business_icons_keep_existing_color_policy(icon):
    rows = [
        ["root", "Column", {}, ["button"]],
        ["button", "CardButton", {"label": "打开", "icon": icon,
                                  "onClick": [{"call": "test", "args": {}}]}],
    ]
    with layout_phase():
        result = convert_compact_dsl_to_a2ui(themes.encode(rows), size="2x2")
    image = next(node for node in themes.components(themes.decode(result))
                 if node.get("id") == "button_visual")
    assert image.get("src") == icon
    assert ("fillColor" in image.get("styles", {})) is icon.endswith(".svg")


def test_explicit_legacy_fallback_tint_is_not_overwritten():
    rows = [
        ["root", "Column", {}, ["button"]],
        ["button", "CardButton", {"label": "打开", "icon": FALLBACK,
                                  "fontColor": "#FF1F4799", "fillColor": "#FF563D99",
                                  "onClick": [{"call": "test", "args": {}}]}],
    ]
    result = convert_compact_dsl_to_a2ui(themes.encode(rows), size="2x2")
    image = next(node for node in themes.components(themes.decode(result))
                 if node.get("id") == "button_visual")
    assert image.get("styles", {}).get("fillColor") == "#FF563D99"


def test_missing_icon_uses_existing_primary_icon_role_before_expansion():
    original = ComponentRow("button", "CardButton", {"fontColor": "#FF563D99"})
    colored = apply_system_component_colors([original], {"primary": "#FF1F4799"})
    assert "icon" not in original.props
    assert "fillColor" not in original.props
    assert colored[0].props.get("icon") == FALLBACK
    assert colored[0].props.get("fillColor") == "#FF1F4799"
    assert colored[0].props.get("fontColor") == "#FF563D99"


@pytest.mark.parametrize("colorless", [False, True])
def test_explicit_null_icon_is_still_rejected(colorless):
    original = ComponentRow("button", "CardButton", {"icon": None})
    colored = apply_system_component_colors([original], {"primary": "#FF1F4799"})
    assert colored[0].props.get("icon") is None
    rows = [
        ["root", "Column", {}, ["button"]],
        ["button", "CardButton", {"label": "打开", "icon": None,
                                  "onClick": [{"call": "test", "args": {}}]}],
    ]
    with layout_phase(colorless), pytest.raises(CompactDslConversionError, match="icon"):
        convert_compact_dsl_to_a2ui(themes.encode(rows), size="2x2")
