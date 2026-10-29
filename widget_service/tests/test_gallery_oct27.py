"""新增图集共用准入和交付，保留布局、偏好、颜色及既有天气背板例外。"""

import hashlib
from pathlib import Path

import pytest

from config.config import get_settings
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_photo_processing import deliver_photo_source, template_foreground
from test_holiday_weather_panel_photos import panels
from test_photo_background_fallback import node_by_id
from test_photo_gallery_rules import BIRDS, double_countdown
from test_photo_icon_exclusion import with_icon
from test_shared_photo_postprocessing import finalize, only_photo
from test_uniform_photo_eligibility import (
    NEW_SUBJECT_FILES,
    PATHS,
    business_sample,
    choose,
    photo,
    rejection,
    sample,
)
from test_weather_body_regions import weather_regions
from test_wide_photo_focus import focus_sample
from theme_preference_samples import preference, reply

GROUPS = [
    ("car-night-lake", "navigation"), ("glass-hourglass", "countdown"),
    ("meeting-room-brown-chairs", "calendar"), ("meeting-room-green-chairs", "calendar"),
    ("metal-gear", "settings"),
    ("mountain-sunset-lake", "weather"), ("pink-sunset-lake", "weather"),
    ("cumulus-blue", "weather"),
]
WEATHER = ("mountain-sunset-lake", "pink-sunset-lake", "cumulus-blue")
MEETINGS = ("meeting-room-brown-chairs", "meeting-room-green-chairs")


def theme_id(group, wide=False):
    return "photo-ux-" + group + ("-wide" if wide else "-square")


def admitted_sample(group, business, wide=False):
    if business == "weather" and not wide:
        main_lines = 3 if group == "cumulus-blue" else 2
        return weather_regions(main_lines, "button")
    return business_sample(business, 3, wide=wide)


@pytest.mark.parametrize("group", MEETINGS)
@pytest.mark.parametrize("wide", [False, True])
def test_new_meeting_dark_furniture_has_light_surfaces_in_both_routes(monkeypatch, group, wide):
    identity = theme_id(group, wide)
    selected = only_photo(monkeypatch, identity)
    saved = business_sample("calendar", 2, wide=wide)
    records = themes.decode(saved.source)
    for node in themes.components(records):
        if node.get("id") in {"button", "upper", "lower"}:
            node.setdefault("styles", {})["backdropBlur"] = {"radius": 20}
    saved.source = themes.encode(records)
    fusion, _ = choose(saved, monkeypatch)
    original, delivered, selected_id = finalize(saved)
    assert selected_id == identity
    assert themes.foreground_signature(fusion) == themes.foreground_signature(saved.source)
    assert template_foreground(original.a2ui) == template_foreground(delivered.a2ui)
    assert selected.get("content", {}).get("roles", {}).get("componentTertiary") == "#99FFFFFF"
    for result in (fusion, delivered.a2ui):
        for node_id in (["button", "upper", "lower"] if wide else ["button"]):
            styles = node_by_id(result, node_id).get("styles", {})
            assert styles.get("backgroundColor") == "#CCFFFFFF"
            assert styles.get("backdropBlur") == {"radius": 20}
        assert node_by_id(result, "reading").get("styles", {}).get("fontColor") == "#FF000000"


@pytest.mark.parametrize("filename", sorted(NEW_SUBJECT_FILES))
def test_assets_have_exact_delivery_bytes_in_both_copies(filename):
    identity = "photo-ux-" + Path(filename).stem.replace("_", "-")
    item = photo(identity)
    src = item.get("src")
    assert isinstance(src, str)
    root = Path(__file__).parents[2]
    data = (root / src).read_bytes()
    assert data == (root / "debug_tools/a2ui_render/entry/src/main" / src).read_bytes()
    source = item.get("source", {})
    assert len(data) == source.get("assetBytes")
    assert hashlib.sha256(data).hexdigest() == source.get("assetSha256")
    remote = item.get("remoteUrl")
    # 全部图片交付地址已补齐；原始PNG来源与OBS的JPG交付字节分别追溯。
    source_file = source.get("file")
    assert isinstance(source_file, str)
    if source_file.startswith("https://"):
        assert remote == source_file
    assert isinstance(remote, str)
    assert remote.startswith("https://lfcontentcenterdev.hwcloudtest.cn/")
    assert "[" not in remote and "]" not in remote
    assert item.get("enabled") is True


@pytest.mark.parametrize("group,business", GROUPS)
@pytest.mark.parametrize("wide", [False, True])
def test_every_new_photo_delivers_in_both_routes_without_foreground_changes(
    monkeypatch, group, business, wide,
):
    identity = theme_id(group, wide)
    selected = only_photo(monkeypatch, identity)
    saved = admitted_sample(group, business, wide)
    assert rejection(saved, identity) is None
    fusion, audit = choose(saved, monkeypatch)
    assert audit.get("themeId") == identity
    fusion = deliver_photo_source(fusion, selected)
    assert themes.foreground_signature(fusion) == themes.foreground_signature(saved.source)
    original, delivered, template_id = finalize(saved)
    assert template_id == identity
    assert template_foreground(original.a2ui) == template_foreground(delivered.a2ui)
    src = selected.get("remoteUrl") or selected.get("src")
    primary = "#FF000000" if business == "calendar" else "#FFFFFFFF"
    panel = "#CCFFFFFF" if business == "calendar" else "#33FFFFFF"
    for result in (fusion, delivered.a2ui):
        images = []
        for node in themes.components(themes.decode(result)):
            if node.get("component") == "Image" and node.get("id") == "__post_theme_base":
                images.append(node)
        assert len(images) == 1
        assert images[0].get("src") == src
        assert node_by_id(result, "reading").get("styles", {}).get("fontColor") == primary
        if wide:
            styles = node_by_id(result, "upper").get("styles", {})
            assert styles.get("backgroundColor") == panel
            assert styles.get("backdropBlur") == {"radius": 20}
        root = node_by_id(result, "root").get("styles", {})
        if business == "calendar":
            assert root.get("linearGradient", {}).get("colors") == [
                ["#FFFFFFFF", 0], ["#FFE6E6E6", 1],
            ]
        else:
            assert root.get("backgroundColor") == "#FF1F1F99"


@pytest.mark.parametrize("group,business", GROUPS)
def test_new_square_photos_keep_three_lines_left_and_single_business(group, business):
    identity = theme_id(group)
    assert rejection(business_sample(business, 4), identity)
    saved = admitted_sample(group, business)
    assert rejection(saved, identity) is None
    rows = themes.decode(saved.compact)
    next(row for row in rows if row[0] == "reading")[2]["textAlign"] = "center"
    assert rejection(expanded(rows, saved.task), identity)
    saved = admitted_sample(group, business)
    rows = themes.decode(saved.compact)
    rows[0][3].append("other")
    rows.extend([
        ["other", "Text", {"content": {"path": PATHS.get("sleep")}}],
        [PATHS.get("sleep"), "7小时"],
    ])
    assert rejection(expanded(rows, saved.task), identity)


@pytest.mark.parametrize("group,business", GROUPS)
def test_new_wide_photos_keep_layout_and_four_line_limits(group, business):
    identity = theme_id(group, True)
    assert rejection(business_sample(business, 4, wide=True), identity) is None
    assert rejection(business_sample(business, 5, wide=True), identity)
    saved = business_sample(business, 1, wide=True)
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = "content-right"
    assert (rejection(expanded(rows, saved.task), identity) is None) is (business == "weather")
    for layout in ("W-split-panels", "W-four-slots"):
        assert rejection(panels(layout, lines=1), identity)
    if business == "weather":
        assert rejection(focus_sample("weather", 4, "top"), identity) is None


@pytest.mark.parametrize("group", WEATHER)
@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_wide_weather_has_three_equally_likely_regular_choices(monkeypatch, group, layout):
    identity = theme_id(group, True)
    expected = {theme_id(name, True) for name in WEATHER}
    calls = []

    def pick(items):
        assert set(items) == expected
        assert len(items) == 3
        calls.append(list(items))
        return identity

    monkeypatch.setattr(themes.secrets, "choice", pick)
    saved = focus_sample("weather", 4, layout)
    _, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == identity
    assert len(calls) == 1


@pytest.mark.parametrize("group", MEETINGS)
@pytest.mark.parametrize("wide", [False, True])
def test_new_meetings_share_uniform_pool_with_eligible_existing_meetings(monkeypatch, group, wide):
    expected = {theme_id(name, wide) for name in MEETINGS}
    expected.add(theme_id("meeting-room", wide))
    if wide:
        expected.add("photo-ux-digital-wave-wide")
    identity = theme_id(group, wide)

    def pick(items):
        assert len(items) == len(expected)
        assert set(items) == expected
        return identity

    monkeypatch.setattr(themes.secrets, "choice", pick)
    _, audit = choose(business_sample("calendar", wide=wide), monkeypatch)
    assert audit.get("themeId") == identity


@pytest.mark.parametrize("saved", [
    sample(PATHS.get("countdown"), 3, title="中秋节"),
    sample(PATHS.get("countdown"), 6, title="国庆", align="center"),
    double_countdown(lines=4),
])
def test_holiday_priority_does_not_require_base_alignment_or_line_limits(monkeypatch, saved):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    _, audit = choose(saved, monkeypatch)
    assert audit.get("candidates") == [BIRDS]
    assert audit.get("themeId") == BIRDS
    saved.task.setdefault("dataModelSchema", {})
    _, _, identity = finalize(saved)
    assert identity == BIRDS


@pytest.mark.parametrize("group,business", GROUPS)
@pytest.mark.parametrize("wide", [False, True])
def test_new_photos_cannot_override_user_no_photo_or_color_cloud(
    monkeypatch, group, business, wide,
):
    identity = theme_id(group, wide)
    only_photo(monkeypatch, identity)
    saved = admitted_sample(group, business, wide)
    saved.task["userQuery"] = "不要图片"
    preferences = [preference("backgroundKind", "photo", "不要图片", "avoid")]
    _, audit = choose(saved, monkeypatch, reply(preferences))
    assert identity not in audit.get("candidates", [])
    original, delivered, _ = finalize(saved)
    assert original is delivered
    saved.task["userQuery"] = "显示状态"
    _, audit = choose(with_icon(saved), monkeypatch)
    assert identity not in audit.get("candidates", [])
    assert audit.get("photoAssetExclusions")


@pytest.mark.parametrize("layout", ["W-split-panels", "W-four-slots"])
def test_ice_still_handles_weather_panels_without_line_limit(monkeypatch, layout):
    _, audit = choose(panels(layout, lines=8), monkeypatch)
    assert audit.get("candidates") == ["photo-ux-ice-wide"]
    assert audit.get("themeId") == "photo-ux-ice-wide"


def test_registry_remains_valid_and_disabled_weather_never_leaks():
    registry.validate_registry(registry.load_theme_registry())
    enabled = set()
    for item in registry.registered_themes("photos"):
        if item.get("business") == "weather":
            enabled.add(item.get("id"))
    expected = {"photo-ux-ice-wide"}
    for group in WEATHER:
        expected.update((theme_id(group), theme_id(group, True)))
    assert enabled == expected
