"""蓝天白云仅用左上1至2行正文；按钮不计行数，但仍占用空间。"""

import copy

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_autumn_calendar_photos import expanded
from test_uniform_photo_eligibility import (
    ACTION,
    BLUE,
    PATHS,
    choose,
    evidence,
    photo,
    rejection,
    sample,
)

CLOUDS = "photo-ux-clouds-weather-square"
ICON = "resources/base/media/drop_1.svg"


def weather_sample(lines=2):
    saved = sample(PATHS.get("weather"), lines, button=False, title="天气")
    rows = themes.decode(saved.compact)
    rows[1][2]["icon"] = ICON
    return expanded(rows, saved.task)


def attach_node(saved, node):
    root = next(item for item in saved.nodes if item.get("id") == "root")
    root.get("children", []).append(node.get("id"))
    saved.nodes.append(node)


@pytest.mark.parametrize("lines,allowed", [
    (0, False), (1, True), (2, True), (3, False), (4, False),
])
def test_current_body_lines_ignore_header_and_max_lines(lines, allowed):
    saved = weather_sample(lines)
    before = copy.deepcopy(saved.nodes)
    assert (rejection(saved, CLOUDS) is None) is allowed
    assert saved.nodes == before
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == lines


@pytest.mark.parametrize("alignment", [
    "end", "center", "spaceBetween", "spaceAround", "spaceEvenly",
])
def test_vertical_center_bottom_or_distributed_content_is_rejected(alignment):
    saved = weather_sample(1)
    root = next(item for item in saved.nodes if item.get("id") == "root")
    root.get("styles", {})["justifyContent"] = alignment
    assert "居左居上且下方留空" in rejection(saved, CLOUDS)


@pytest.mark.parametrize("align", ["center", "end"])
def test_left_alignment_still_required(align):
    saved = sample(PATHS.get("weather"), 1, button=False, align=align)
    assert "正文整体居左" in rejection(saved, CLOUDS)


@pytest.mark.parametrize("layout", ["S-title-content", "S-title-content-action", "S-title-anchor"])
def test_real_semantic_layout_expansion_rejects_bottom_content(layout):
    children = ["header", "reading"]
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["header", "SingleLineTitle", {"title": "天气", "icon": ICON}],
        ["reading", "EmphasisText", {"mainText": {"path": PATHS.get("weather")}}],
        [PATHS.get("weather"), "晴天"],
    ]
    if layout == "S-title-anchor":
        children.append("support")
        rows.append(["support", "SecondaryBody", {"items": [{"label": "状态", "value": "晴"}]}])
    if layout != "S-title-content":
        children.append("action")
        kind = "CircleButton" if layout == "S-title-anchor" else "PillButton"
        props = {"icon": ICON, "onClick": ACTION}
        if kind == "CircleButton":
            props["accessibility"] = {"label": "查看天气"}
        else:
            props["label"] = "查看天气"
        rows.append(["action", kind, props])
    saved = expanded(rows, {"size": "2x2", "userQuery": "天气", "appVersion": "99.0.0"})
    before = copy.deepcopy(saved.nodes)
    assert rejection(saved, CLOUDS)
    assert saved.nodes == before


def test_lower_capsule_label_is_excluded_from_count_but_not_occupancy():
    saved = sample(PATHS.get("weather"), 2, button=True)
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("root", {})
    assert flow.get("lineCount") == 2
    assert "正文下方" in rejection(saved, CLOUDS)


@pytest.mark.parametrize("kind,styles", [
    ("Image", {"width": 20, "height": 20}),
    ("Divider", {"height": 1, "color": "#FFFFFFFF"}),
    ("Progress", {"type": "ring"}),
    ("Column", {"height": 24, "backgroundColor": "#33FFFFFF"}),
    ("Column", {"layoutWeight": 1, "backgroundColor": "@role:panel"}),
])
def test_lower_non_text_elements_are_not_ignored(kind, styles):
    saved = weather_sample(1)
    attach_node(saved, {"id": "lower", "component": kind, "styles": styles, "src": ICON})
    assert rejection(saved, CLOUDS)


def test_lower_text_after_flexible_primary_region_is_rejected():
    saved = weather_sample(1)
    reading = next(item for item in saved.nodes if item.get("id") == "reading")
    reading["styles"] = {"layoutWeight": 1}
    attach_node(saved, {"id": "lower", "component": "Text", "content": "空气质量良"})
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == 2
    assert rejection(saved, CLOUDS)


@pytest.mark.parametrize("position", ["before", "after"])
def test_empty_bottom_spacer_allowed_but_leading_spacer_rejected(position):
    saved = weather_sample(1)
    attach_node(saved, {"id": "spacer", "component": "Column", "children": [],
                        "styles": {"layoutWeight": 1}})
    root = next(item for item in saved.nodes if item.get("id") == "root")
    if position == "before":
        root.get("children", []).remove("spacer")
        root.get("children", []).insert(1, "spacer")
    assert (rejection(saved, CLOUDS) is None) is (position == "after")


@pytest.mark.parametrize("kind", ["Image", "CircleButton"])
def test_top_inline_icon_or_button_does_not_create_a_lower_region(kind):
    saved = weather_sample(2)
    rows = themes.decode(saved.compact)
    rows[0][3][1] = "top_row"
    inline_children = ["reading"]
    if kind == "CircleButton":
        inline_children.append("button_slot")
        rows.append(["button_slot", "Stack", {"width": 40, "height": 40,
                                               "alignContent": "center"}, ["inline"]])
        rows.append(["inline", kind, {"icon": ICON, "onClick": ACTION,
                                      "accessibility": {"label": "查看天气"}}])
    rows.append(["top_row", "Row", {"alignItems": "center"}, inline_children])
    saved = expanded(rows, saved.task)
    if kind == "Image":
        row = next(item for item in saved.nodes if item.get("id") == "top_row")
        row.get("children", []).append("inline")
        saved.nodes.append({"id": "inline", "component": "Image", "src": ICON,
                            "styles": {"width": 20, "height": 20}})
    assert rejection(saved, CLOUDS) is None


@pytest.mark.parametrize("placement", ["bottomStart", "center"])
def test_bottom_or_center_stack_is_rejected(placement):
    saved = weather_sample(1)
    root = next(item for item in saved.nodes if item.get("id") == "root")
    root["component"] = "Stack"
    root.get("styles", {})["alignContent"] = placement
    assert rejection(saved, CLOUDS)


def test_unknown_top_evidence_fails_closed():
    saved = weather_sample(1)
    measured = evidence(saved)
    measured.pop("photoTopContent")
    assert themes.photo_reason(photo(CLOUDS), saved.task, measured, final_layout=saved.compact)


@pytest.mark.parametrize("styles", [
    {"offset": {"y": "60%"}}, {"position": {"y": "70%"}},
    {"translate": {"y": "50%"}}, {"alignSelf": "end"},
])
def test_independently_positioned_content_is_rejected(styles):
    saved = weather_sample(1)
    reading = next(item for item in saved.nodes if item.get("id") == "reading")
    reading.get("styles", {}).update(styles)
    assert rejection(saved, CLOUDS)


@pytest.mark.parametrize("stretched,allowed", [(False, True), (True, False)])
def test_local_inline_baseline_alignment_is_not_card_bottom_alignment(stretched, allowed):
    saved = weather_sample(1)
    rows = themes.decode(saved.compact)
    rows[0][3][1] = "body_row"
    props = {"alignItems": "bottom"}
    if stretched:
        props["layoutWeight"] = 1
    rows.append(["body_row", "Row", props, ["reading"]])
    assert (rejection(expanded(rows, saved.task), CLOUDS) is None) is allowed


def test_unmatched_clouds_can_use_starfield_without_relayout(monkeypatch):
    saved = sample(PATHS.get("weather"), 3, button=True)
    result, audit = choose(saved, monkeypatch)
    assert CLOUDS not in audit.get("candidates", [])
    assert audit.get("themeId") == "photo-ux-starfield-weather-square"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert rejection(saved, BLUE) is None


@pytest.mark.parametrize("identity", [CLOUDS, "photo-ux-sand-arch-square", BLUE])
@pytest.mark.parametrize("color_role", ["primary", "secondary", "tertiary", "graphicPrimary"])
def test_registry_rejects_mixed_foreground_palettes_for_every_photo_pool(identity, color_role):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == identity)
    roles = entry.get("content", {}).get("roles", {})
    roles[color_role] = roles.get(color_role, "")[:3] + "000000"
    with pytest.raises(ValueError, match="foreground"):
        registry.validate_registry(config)


@pytest.mark.parametrize("change,value", [
    ("maxTextLines", 3), ("maxTextLines", 0), ("placement", "bottom-left"),
])
def test_registry_rejects_invalid_top_only_policy(change, value):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == CLOUDS)
    entry.get("contentEligibility", {})[change] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)
