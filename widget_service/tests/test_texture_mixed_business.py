"""抽象图按首个可见业务配色，混合业务不再排除，主体图规则不变。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_texture_eligibility as texture
from services.capability_registry import CapabilityRegistry
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import ACTION, PATHS, choose, evidence, rejection, sample


def mixed_sample(first="sleep", second="weather", lines=1):
    path = PATHS.get(first, "/data/unknown/value")
    saved = sample(path, lines, button=False, align="end")
    rows = themes.decode(saved.compact)
    rows[0][3].append("second")
    other = PATHS.get(second, "/data/unknown/other")
    rows.extend([["second", "Text", {"content": {"path": other}}], [other, "正文"]])
    return expanded(rows, saved.task)


@pytest.mark.parametrize("first,second,family", [
    ("sleep", "weather", "purple"), ("weather", "sleep", "blue"),
    ("sport", "calendar", "orange"), ("calendar", "sport", "blue"),
    ("battery", "sleep", None), ("travel", "weather", None),
    ("unknown", "sleep", None),
])
def test_mixed_square_uses_first_business_or_all_colors(first, second, family):
    saved = mixed_sample(first, second)
    for color in ("blue", "purple", "orange"):
        identity = f"photo-ux-texture-{color}-diamond-square"
        assert (rejection(saved, identity) is None) is (family is None or color == family)


def test_first_business_uses_tree_order_not_row_declaration_order():
    saved = mixed_sample("sleep", "weather")
    rows = themes.decode(saved.compact)
    rows[0][3] = ["title", "second", "reading"]
    saved = expanded(rows, saved.task)
    assert rejection(saved, "photo-ux-texture-blue-diagonal-square") is None
    assert rejection(saved, "photo-ux-texture-purple-diagonal-square")


def test_unknown_first_business_is_not_replaced_by_later_known_business():
    saved = mixed_sample("unknown", "sleep")
    parsed = parse_compact_dsl_rows(saved.compact, expand_layouts=False)
    by_id = {}
    for row in parsed:
        if isinstance(row, ComponentRow):
            by_id[row.component_id] = row
    assert texture.first_visible_business(texture.subtree("root", by_id)) is None


@pytest.mark.parametrize("lines,allowed", [(1, True), (2, True), (3, False)])
def test_mixed_square_still_counts_all_body_lines(lines, allowed):
    saved = mixed_sample(lines=lines)
    assert (rejection(saved, "photo-ux-texture-purple-diamond-square") is None) is allowed
    assert rejection(saved, "photo-ux-sleep-square")


def test_unknown_color_randomizes_family_before_shape(monkeypatch):
    saved = mixed_sample("battery", "sleep")
    calls = []

    def choice(items):
        calls.append(list(items))
        return items[-1]

    monkeypatch.setattr(themes.secrets, "choice", choice)
    result, audit = choose(saved, monkeypatch)
    assert len(calls) == 2
    assert set(calls[0]) == {"blue", "purple", "orange"}
    assert len(calls[1]) == 2
    assert all(f"texture-{calls[0][-1]}-" in identity for identity in calls[1])
    assert audit.get("themeId") == calls[1][-1]
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def split_sample(lines=1, first="weather", second="battery"):
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]]]
    for side, business in (("left", first), ("right", second)):
        path = PATHS.get(business)
        assert path is not None
        rows.extend([
            [side, "Region", {"variant": "title-content"}, [side + "_title", side + "_text"]],
            [side + "_title", "SingleLineTitle", {"title": "标题不计"}],
            [side + "_text", "Text", {"content": {"path": path}, "maxLines": 20}],
            [path, "\n".join(["正文"] * lines)],
        ])
    return expanded(rows, {"size": "2x4", "userQuery": "显示状态", "appVersion": "99.0.0"})


@pytest.mark.parametrize("lines,allowed", [(1, True), (3, True), (4, False)])
def test_split_panels_count_horizontal_maximum_not_sum(lines, allowed):
    saved = split_sample(lines)
    assert evidence(saved).get("textureBodyTextFlow", {}).get("root", {}).get("lineCount") == lines
    subject_flow = evidence(saved).get("photoBodyTextFlow", {}).get("root", {})
    assert subject_flow.get("lineCount") == lines + 1
    assert (rejection(saved, "photo-ux-texture-blue-diamond-wide") is None) is allowed
    assert rejection(saved, "photo-ux-wave-wide")


@pytest.mark.parametrize("align", ["start", "center", "end"])
@pytest.mark.parametrize("vertical", ["start", "center", "end", "spaceBetween"])
@pytest.mark.parametrize("wide", [False, True])
def test_abstract_any_alignment_keeps_three_line_limit(align, vertical, wide):
    saved = sample(PATHS.get("battery"), 3, align=align)
    rows = themes.decode(saved.compact)
    rows[0][2].update(alignItems=align, justifyContent=vertical)
    saved.task["size"] = "2x4" if wide else "2x2"
    saved = expanded(rows, saved.task)
    identity = "photo-ux-texture-blue-diamond-" + ("wide" if wide else "square")
    assert rejection(saved, identity) is None
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == 3


def test_whole_wide_count_includes_supporting_body():
    from test_wide_photo_focus import focus_sample

    saved = focus_sample("sleep", 1, "top")
    assert rejection(saved, "photo-ux-texture-purple-diamond-wide") is None
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == 3
    saved = focus_sample("sleep", 2, "top")
    assert "超过3行" in rejection(saved, "photo-ux-texture-purple-diamond-wide")


def test_unknown_fully_centered_uses_only_circles(monkeypatch):
    saved = sample(PATHS.get("battery"), 1, button=False, align="center")
    rows = themes.decode(saved.compact)
    rows[0][2].update(alignItems="center", justifyContent="center")
    rows[0][3] = ["reading"]
    rows = [row for row in rows if row[0] != "title"]
    _, audit = choose(expanded(rows, saved.task), monkeypatch)
    assert set(audit.get("candidates", [])) == {
        f"photo-ux-texture-{color}-circles-square" for color in ("blue", "purple", "orange")
    }


def test_random_color_not_weighted_by_number_of_enabled_shapes(monkeypatch):
    config = registry.load_theme_registry()
    for item in config.get("themes", []):
        if item.get("id") == "photo-ux-texture-blue-diagonal-square":
            item["enabled"] = False
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    calls = []

    def choice(items):
        calls.append(list(items))
        return items[0]

    monkeypatch.setattr(themes.secrets, "choice", choice)
    _, audit = choose(mixed_sample("battery", "earphone"), monkeypatch)
    assert calls == [["blue", "orange", "purple"], ["photo-ux-texture-blue-diamond-square"]]
    assert audit.get("photoSelection", {}).get("mode") == "uniform-family-and-shape"


def test_disabling_mapped_family_does_not_reclassify_to_random_color(monkeypatch):
    config = registry.load_theme_registry()
    for item in config.get("themes", []):
        if item.get("pool") == "texturePhotos" and item.get("family") == "purple":
            item["enabled"] = False
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    _, audit = choose(mixed_sample(), monkeypatch)
    assert all(not item.startswith("photo-") for item in audit.get("candidates", []))


@pytest.mark.parametrize("first,expected", [("navigation", "blue"), ("music", "purple"),
                                          ("unknown", None)])
def test_action_only_cards_use_first_actual_action(first, expected):
    actions = {
        "navigation": [{"call": "clickToIntent", "args": {"intentName": "StartNavigate"}}],
        "music": ACTION,
        "unknown": [{"call": "clickToDeeplink", "args": {"intentName": "Other"}}],
    }
    rows = [["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["a", "b"]],
            ["a", "PillButton", {"label": "第一个", "onClick": actions.get(first)}],
            ["b", "PillButton", {"label": "第二个", "onClick": ACTION}]]
    saved = expanded(rows, {"size": "2x2", "userQuery": "天气"})
    for color in ("blue", "purple", "orange"):
        reason = rejection(saved, f"photo-ux-texture-{color}-diamond-square")
        assert (reason is None) is (expected is None or color == expected)


@pytest.mark.parametrize("first", ["weather", "battery"])
@pytest.mark.parametrize("layout", ["square", "column-wide", "split-wide", "four-wide"])
@pytest.mark.parametrize("ice_enabled", [False, True])
def test_mixed_photo_final_obs_delivery_and_colors(monkeypatch, first, layout, ice_enabled):
    config = registry.load_theme_registry()
    ice = next(item for item in config.get("themes", []) if item.get("id") == "photo-ux-ice-wide")
    ice["enabled"] = ice_enabled
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    second = "earphone"
    saved = mixed_sample(first, second)
    if layout == "split-wide":
        saved = split_sample(2, first, second)
    if layout == "column-wide":
        saved.task["size"] = "2x4"
        saved = expanded(themes.decode(saved.compact), saved.task)
    if layout == "four-wide":
        rows = [["root", "Layout", {"layout": "W-four-slots"}, ["a", "b", "c", "d"]]]
        for slot, business in (("a", first), ("b", second), ("c", second), ("d", second)):
            path = PATHS.get(business)
            assert path is not None
            rows.append([slot, "InfoBlock", {"variant": "slot", "surfaceRole": "panel",
                                             "primaryText": {"path": path},
                                             "secondaryText": "当前状态"}])
        for business in (first, second):
            rows.append([PATHS.get(business), "正文"])
        saved = expanded(rows, {**saved.task, "size": "2x4"})
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    original.cardSpec["suggestSize"] = saved.task.get("size")
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    data = []
    bindings = []
    for identity, target in (("ViewWeather", "/data/weather"),
                             ("GetPhoneBatteryInfo", "/data/phoneBattery"),
                             ("GetEarphoneInfo", "/data/earphone")):
        capability = capabilities.get_data_capability(identity)
        assert capability is not None
        data.append(capability.model_dump())
        bindings.append({"capabilityId": identity, "arguments": {}, "writeResultTo": target})
    original.effectiveCapabilities["data"] = data
    original.cardSpec["dataBindings"] = bindings
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    audits = []
    select = themes.select_theme

    async def capture(*args, **kwargs):
        result, audit = await select(*args, **kwargs)
        audits.append(audit)
        return result, audit

    monkeypatch.setattr(themes, "select_theme", capture)
    result = asyncio.run(themes.theme_artifact(
        original, saved.task, client, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    audit = audits[0]
    assert not audit.get("finalValidationErrors"), audit
    assert themes.foreground_signature(result.genui) == themes.foreground_signature(saved.source)
    if ice_enabled and first == "weather" and layout in {"split-wide", "four-wide"}:
        assert audit.get("themeId") == "photo-ux-ice-wide"
    elif layout == "four-wide":
        assert not audit.get("themeId", "").startswith("photo-")
        return
    else:
        assert audit.get("themeId", "").startswith("photo-ux-texture-")
    assert node_by_id(result.genui, "root").get("styles", {}).get("backgroundColor") == "#FF1F1F99"
    assert node_by_id(result.genui, themes.PREFIX + "base").get("src") == (
        audit.get("theme", {}).get("remoteUrl")
    )
    images = []
    for node in themes.components(themes.decode(result.genui)):
        if node.get("id", "").startswith(themes.PREFIX) and node.get("component") == "Image":
            images.append(node)
        if node.get("component") == "Text":
            assert node.get("styles", {}).get("fontColor") in {
                "#FFFFFFFF", "#CCFFFFFF", "#99FFFFFF",
            }
    assert len(images) == 1


def test_body_subtitle_is_not_excluded_as_a_region_title():
    saved = mixed_sample("weather", "sleep")
    rows = themes.decode(saved.compact)
    rows[0][3].extend(["subtitle", "extra"])
    rows.extend([["subtitle", "SingleLineTitle", {"title": "正文小标题"}],
                 ["extra", "Text", {"content": "第四行"}]])
    saved = expanded(rows, saved.task)
    assert evidence(saved).get("textureBodyTextFlow", {}).get("root", {}).get("lineCount") == 4
    assert "超过3行" in rejection(saved, "photo-ux-texture-blue-diamond-square")
