"""每套主题独立解析内容背板和按钮底色，覆盖真实组件展开链路。"""

import json
import re

import pytest

from services import post_layout_theme as themes
from services.compact_component_runtime import component_visual_recipe
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.theme_style_roles import component_roles, layout_phase, resolve_role, role


def surface_source(size):
    action = [{"call": "clickToDeeplink", "args": {"uri": "test://open"}}]
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, []],
        ["info", "InfoBlock", {"primaryText": "68%", "secondaryText": "电量"}],
        ["pill", "PillButton", {"label": "打开", "onClick": action}],
        ["panel", "Column", {"surfaceRole": "panel"}, ["value"]],
        ["value", "EmphasisText", {"mainText": "示例"}],
    ]
    rows[0][3].extend(["info", "pill", "panel"])
    if size == "2x4":
        rows[1][2]["variant"] = "slot"
        rows.extend([
            ["card", "CardButton", {"label": "打开闹钟", "onClick": action}],
            ["details", "TextBlock", {"items": [
                {"label": "电量", "value": "68%"}, {"label": "状态", "value": "正常"},
            ]}],
            ["summary", "SummaryList", {"items": ["项目例会", "需求讨论"]}],
        ])
        rows[0][3].extend(["card", "details", "summary"])
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase():
        return convert_compact_dsl_to_a2ui(source, size=size)


@pytest.mark.parametrize("kind,part", [("CardButton", "root"), ("TextBlock", "item")])
def test_recipe_panels_are_semantic_and_legacy_cache_unchanged(kind, part):
    before = component_visual_recipe(kind, size="2x4")
    with layout_phase():
        recipe = component_visual_recipe(kind, size="2x4")
    assert recipe.get("parts", {}).get(part, {}).get("styles", {}).get("backgroundColor") == (
        role("panel")
    )
    assert not re.search(r"#[A-Fa-f0-9]{6,8}", json.dumps(recipe))
    assert component_visual_recipe(kind, size="2x4") == before
    assert before.get("parts", {}).get(part, {}).get("styles", {}).get("backgroundColor") == (
        "#99FFFFFF"
    )


@pytest.mark.parametrize("kind", ["InfoBlock", "SummaryList"])
def test_implicit_content_surfaces_use_panel(kind):
    assert component_roles(kind, {}).get("backgroundColor") == role("panel")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("theme_kind", ["gradient", "solid", "photo"])
@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_actual_expanded_surfaces_use_each_theme_standard(size, theme_kind, family):
    task = {"size": size}
    if theme_kind == "photo":
        manifest = json.loads(themes.MANIFEST.read_text(encoding="utf-8"))
        key = "photos" if size == "2x2" else "subjectlessWidePhotos"
        theme = manifest.get(key)[0]
        theme = {**theme, "kind": "photo", "palette": family, "panel": "#FF000000"}
        palette_name, expected = "fusionDark", "#33FFFFFF"
    else:
        theme = next(t for t in themes.presets(task) if t.get("id") == theme_kind + "-" + family)
        palette_name = family
        expected = "#CCFFFFFF" if size == "2x2" else "#99FFFFFF"
    source = surface_source(size)
    final = themes.apply_theme(source, theme, task, {})
    assert themes.foreground_signature(source) == themes.foreground_signature(final)
    assert "@theme:" not in final
    nodes = {n.get("id"): n for n in themes.components(themes.decode(final))}
    ids = ["info", "panel"]
    if size == "2x4":
        ids.extend(["card", "details_item0", "details_item1", "summary_item0", "summary_item1"])
    for identity in ids:
        assert nodes.get(identity, {}).get("styles", {}).get("backgroundColor") == expected
    palette = themes.load_visual_recipe_contract().get("palettes", {}).get(palette_name, {})
    expected_button = palette.get("roles", {}).get("componentSecondary")
    assert expected_button
    assert nodes.get("pill", {}).get("styles", {}).get("backgroundColor") == expected_button


@pytest.mark.parametrize("token", sorted(themes.FUSION_BALL_DESIGN_TOKENS))
def test_fusion_surfaces_keep_existing_white_twenty_percent(token):
    source = surface_source("2x2")
    task = {"size": "2x2", "appVersion": "11.9.9.342"}
    theme = {"id": token, "kind": "fusion", "palette": "fusionDark"}
    final = themes.apply_theme(source, theme, task, {})
    for node in themes.components(themes.decode(final)):
        if node.get("id") in {"info", "pill", "panel"}:
            assert node.get("styles", {}).get("backgroundColor") == "#33FFFFFF"
    assert themes.foreground_signature(source) == themes.foreground_signature(final)


@pytest.mark.parametrize("name", ["panel", "primary", "secondary", "graphicPrimary"])
def test_missing_role_does_not_borrow_button_color(name):
    with pytest.raises(ValueError, match="missing a required color role"):
        resolve_role(role(name), {"componentSecondary": "#33FFFFFF"})


def test_explicit_text_color_does_not_repaint_surfaces():
    source = surface_source("2x4")
    theme = next(t for t in themes.presets({"size": "2x4"}) if t.get("id") == "gradient-purple")
    final = themes.apply_theme(source, theme, {"size": "2x4"}, {"text": {"color": "#FFFF0000"}})
    for node in themes.components(themes.decode(final)):
        styles = node.get("styles", {})
        if node.get("component") == "Text":
            assert styles.get("fontColor", "").endswith("FF0000")
        if node.get("id") in {"card", "info", "panel"}:
            assert styles.get("backgroundColor") == "#99FFFFFF"
