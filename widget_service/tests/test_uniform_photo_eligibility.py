"""统一图集、三行正文、主体居左与按池等概率选图的回归。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_content_regions import photo_layout_evidence
from services.theme_layout_summary import theme_description
from test_autumn_calendar_photos import expanded
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id

BLUE = "photo-ux-texture-blue-diamond-square"
PURPLE = "photo-ux-texture-purple-diamond-square"
ORANGE = "photo-ux-texture-orange-diamond-square"
SLEEP = "/data/healthSport/nightSleepDurationText"
CALENDAR = "/data/calendar/events/0/title"
ACTION = [{"call": "clickToDeeplink", "args": {
    "intentName": "Music", "bundleName": "com.huawei.hmsapp.music",
    "abilityName": "", "uri": "",
}}]
SUBJECT_FILES = {
    "airplane_tarmac_wide", "birds_countdown_square", "bedside_lamp_wide", "clouds_weather_square",
    "concert_stage_wide", "digital_wave_wide", "galaxy_sleep_square", "running_pair_wide",
    "sleep_square", "sleep_wide", "sport_center_wide", "sunrise_runner_square",
    "starfield_weather_square", "starry_sky_square", "starry_sky_wide",
    "track_runner_square", "track_sprint_square", "violin_stage_square", "sand_arch_square",
    "meeting_room_square", "meeting_room_wide",
}
PATHS = {
    "travel": "/data/travel/flightNumber", "countdown": "/data/countdown/first/countdownDays",
    "smart-home": "/data/smartHome/temperature", "weather": "/data/weather/current/temperature",
    "music": "/data/music/trackName", "information": "/data/news/title", "sleep": SLEEP,
    "sport": "/data/healthSport/dailySteps", "earphone": "/data/earphone/connectionState",
    "calendar": CALENDAR, "battery": "/data/phoneBattery/batteryLevel",
}
PHOTOS = registry.registered_themes("photos") + registry.registered_themes("texturePhotos")


def photo(identity):
    return next(item for item in registry.registered_themes(include_disabled=True)
                if item.get("id") == identity)


def sample(path=SLEEP, lines=3, *, wide=False, button=True, align="start", title="状态"):
    body_children = ["title", "reading"]
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent",
                            "alignItems": "start"}, body_children],
        ["title", "SingleLineTitle", {"title": title}],
        ["reading", "Text", {"content": {"path": path}, "maxLines": 20, "textAlign": align}],
        [path, "\n".join(["正文"] * lines)],
    ]
    if button:
        body_children.append("button")
        rows.append(["button", "PillButton", {"label": "按钮\n文案不计", "onClick": ACTION}])
    if wide:
        variant = "title-content-action" if button else "title-content"
        main = ["main", "Region", {"variant": variant}, body_children]
        rows[0] = ["root", "Layout", {"layout": "W-content-side-slots",
                                      "orientation": "content-left"}, ["main", "upper", "lower"]]
        rows.extend([
            main,
            ["upper", "InfoBlock", {"variant": "slot", "surfaceRole": "panel",
                                    "primaryText": "右侧任意业务", "secondaryText": "辅助"}],
            ["lower", "CardButton", {"label": "右侧按钮", "onClick": ACTION}],
        ])
    task = {"size": "2x4" if wide else "2x2", "userQuery": "显示状态",
            "appVersion": "99.0.0", "dataModelSchema": {"data": {"unused": {}}}}
    return expanded(rows, task)


def evidence(saved):
    data = themes.decode(saved.source)[-1].get("updateDataModel", {}).get("value")
    return photo_layout_evidence(saved.nodes, data, final_layout=saved.compact)


def rejection(saved, identity):
    return themes.photo_reason(photo(identity), saved.task, evidence(saved),
                               final_layout=saved.compact)


def choose(saved, monkeypatch, response="{}"):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(return_value=response))
    return asyncio.run(themes.select_theme(saved.source, saved.task, client,
                                          final_layout=saved.compact))


def test_only_current_subject_and_abstract_assets_remain():
    subjects = registry.registered_themes("photos", include_disabled=True)
    assert len(subjects) == 21
    expected = {"bg_ux_" + name + ".jpg" for name in SUBJECT_FILES}
    actual = {Path(item.get("src", "")).name for item in subjects}
    assert actual == expected
    abstract = registry.registered_themes("texturePhotos", include_disabled=True)
    assert len(abstract) == 18
    expected.update(Path(item.get("src", "")).name for item in abstract)
    directory = Path(__file__).parents[2] / "resources/base/media"
    assert {path.name for path in directory.glob("bg_ux_*.jpg")} == expected
    for item in PHOTOS:
        asset = Path(__file__).parents[2] / item.get("src", "")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        assert digest == item.get("source", {}).get("assetSha256")
        expected_keys = {"kind", "businesses"}
        if item.get("id") == "photo-ux-clouds-weather-square":
            expected_keys.update({"maxTextLines", "placement"})
        elif item.get("contentEligibility", {}).get("placement"):
            expected_keys.add("placement")
        assert set(item.get("contentEligibility", {})) == expected_keys
        assert "https://" not in json.dumps(theme_description(item))


@pytest.mark.parametrize("item", PHOTOS, ids=lambda item: item.get("id"))
def test_every_photo_obeys_its_line_limit_and_preserves_foreground(item):
    businesses = item.get("contentEligibility", {}).get("businesses", [])
    business = businesses[0]
    path = PATHS.get(business)
    if business == "holiday":
        path = PATHS.get("countdown")
    assert path
    clouds = item.get("id") == "photo-ux-clouds-weather-square"
    limit = 2 if clouds else 3
    for count in (limit, limit + 1):
        placement = item.get("contentEligibility", {}).get("placement")
        button = not clouds and placement != "bottom-left"
        saved = sample(path, count, wide=item.get("size") == "2x4", title="假期", button=button)
        if placement == "center":
            rows = themes.decode(saved.compact)
            rows[0][2].update(alignItems="center", justifyContent="center")
            rows[0][3][:] = ["reading"]
            next(row for row in rows if row[0] == "reading")[2]["textAlign"] = "center"
            rows = [row for row in rows if row[0] not in {"title", "button"}]
            saved = expanded(rows, saved.task)
        reason = themes.photo_reason(item, saved.task, evidence(saved), final_layout=saved.compact)
        assert (reason is None) is (count == limit), (item.get("id"), reason)
    before = copy.deepcopy(saved.nodes)
    result = themes.apply_theme(saved.source, item, saved.task, {})
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert saved.nodes == before


@pytest.mark.parametrize("identity", ["photo-ux-sleep-square", "photo-ux-galaxy-sleep-square"])
@pytest.mark.parametrize("button", [False, True])
def test_sleep_images_no_longer_have_opposing_button_requirements(identity, button):
    assert rejection(sample(button=button), identity) is None


@pytest.mark.parametrize("align", ["center", "end"])
def test_only_square_subject_requires_left_alignment(align):
    assert rejection(sample(align=align), "photo-ux-sleep-square")
    assert rejection(sample(align=align), PURPLE) is None
    wide = sample(wide=True, align=align)
    assert rejection(wide, "photo-ux-sleep-wide") is None
    assert rejection(wide, PURPLE.replace("square", "wide")) is None


@pytest.mark.parametrize("distribution,allowed", [("start", True), ("spaceBetween", False)])
def test_key_value_rows_must_be_together_at_left_for_subject(distribution, allowed):
    saved = sample(PATHS.get("earphone"), 1, button=False)
    rows = themes.decode(saved.compact)
    reading = next(row for row in rows if row[0] == "reading")
    reading[:] = ["reading", "Row", {"justifyContent": distribution}, ["label", "value"]]
    rows.extend([["label", "Text", {"content": "连接"}],
                 ["value", "Text", {"content": {"path": PATHS.get("earphone")}}]])
    saved = expanded(rows, saved.task)
    assert (rejection(saved, "photo-ux-violin-stage-square") is None) is allowed
    assert rejection(saved, PURPLE) is None
    assert evidence(saved).get("photoBodyTextFlow", {}).get("reading", {}).get("lineCount") == 1


def test_screenshot_four_earphone_lines_rejected_even_without_title_and_button():
    saved = sample(PATHS.get("earphone"), 4, button=False)
    assert rejection(saved, "photo-ux-violin-stage-square")
    assert rejection(saved, BLUE)


def test_header_buttons_excluded_but_body_subtitle_and_clickable_info_count():
    saved = sample(PATHS.get("sport"), 2)
    rows = themes.decode(saved.compact)
    rows[0][3].insert(2, "subtitle")
    rows.append(["subtitle", "SingleLineTitle", {"title": "正文小标题"}])
    saved = expanded(rows, saved.task)
    flow = evidence(saved).get("photoBodyTextFlow", {})
    assert flow.get("root", {}).get("lineCount") == 3
    assert flow.get("title", {}).get("lineCount") == 0
    assert flow.get("button", {}).get("lineCount") == 0
    assert rejection(saved, "photo-ux-sand-arch-square") is None
    rows[0][3].append("extra")
    rows.append(["extra", "InfoBlock", {"primaryText": "额外读数", "secondaryText": "辅助"}])
    saved = expanded(rows, saved.task)
    extra = next(node for node in saved.nodes if node.get("id") == "extra")
    extra["onClick"] = ACTION
    assert rejection(saved, "photo-ux-sand-arch-square")


@pytest.mark.parametrize("other,allowed", [
    ("/data/countdown/second/countdownDays", True), ("/data/weather/current/temperature", False),
])
def test_same_business_instances_count_as_single_business(other, allowed):
    saved = sample(PATHS.get("countdown"), 1, button=False, title="生日和考试")
    rows = themes.decode(saved.compact)
    rows[0][3].append("second")
    rows.extend([["second", "Text", {"content": {"path": other}}], [other, 30]])
    reason = rejection(expanded(rows, saved.task), ORANGE)
    assert (reason is None) is allowed


def test_wide_only_counts_left_body_and_classifies_left_business():
    saved = sample(wide=True)
    rows = themes.decode(saved.compact)
    upper = next(row for row in rows if row[0] == "upper")
    upper[2]["primaryText"] = {"path": PATHS.get("weather")}
    rows.append([PATHS.get("weather"), "多云"])
    saved = expanded(rows, saved.task)
    assert rejection(saved, "photo-ux-sleep-wide") is None
    assert rejection(saved, "photo-ux-sport-center-wide")
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), "photo-ux-sleep-wide")


@pytest.mark.parametrize("identity", ["photo-ux-sleep-wide", PURPLE.replace("square", "wide")])
def test_wide_unrecognized_or_split_layout_rejected(identity):
    saved = sample(wide=False)
    saved.task["size"] = "2x4"
    assert rejection(saved, identity)


@pytest.mark.parametrize("failure", ["missing-layout", "unknown-value", "missing-node", "mixed"])
def test_unknown_and_mixed_content_fail_closed(failure):
    saved = sample()
    if failure == "missing-layout":
        saved.compact = None
    elif failure == "unknown-value":
        records = themes.decode(saved.source)
        records[-1].get("updateDataModel", {})["value"] = {}
        saved.source = themes.encode(records)
    elif failure == "missing-node":
        saved.nodes = [node for node in saved.nodes if node.get("id") != "reading"]
    else:
        rows = themes.decode(saved.compact)
        rows[0][3].append("weather")
        rows.extend([["weather", "Text", {"content": {"path": PATHS.get("weather")}}],
                     [PATHS.get("weather"), 29]])
        saved = expanded(rows, saved.task)
    assert rejection(saved, "photo-ux-sleep-square")
    assert rejection(saved, PURPLE)


@pytest.mark.parametrize("selected", ["photo-ux-sleep-square"])
@pytest.mark.parametrize("model_response", [
    "{}", '{"themeId":"photo-ux-sleep-square"}',
    '{"themeId":"photo-ux-galaxy-sleep-square"}', "invalid",
])
def test_subject_priority_and_uniform_choice_ignore_model_preference(
    monkeypatch, selected, model_response,
):
    calls = []

    def choice(items):
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = sample()
    result, audit = choose(saved, monkeypatch, model_response)
    assert audit.get("themeId") == selected
    assert len(calls) == 1
    assert set(calls[0]) == {"photo-ux-sleep-square"}
    assert set(audit.get("candidates", [])) == set(calls[0])
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_subject_failure_falls_to_abstract_then_ordinary_theme(monkeypatch):
    saved = sample(align="center")
    _, audit = choose(saved, monkeypatch)
    ids = audit.get("candidates", [])
    assert len(ids) == 2
    assert all(identity.startswith("photo-ux-texture-purple-") for identity in ids)
    _, audit = choose(sample(lines=4), monkeypatch)
    assert all(not identity.startswith("photo-") for identity in audit.get("candidates", []))


@pytest.mark.parametrize("query", ["纯色睡眠", "渐变背景", "不要图片", "白色文字"])
def test_explicit_preferences_and_disabled_switch_override_photos(monkeypatch, query):
    saved = sample()
    saved.task["userQuery"] = query
    _, audit = choose(saved, monkeypatch)
    assert all(not identity.startswith("photo-") for identity in audit.get("candidates", []))
    saved.task["userQuery"] = "睡眠状态"
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    _, audit = asyncio.run(themes.select_theme(saved.source, saved.task, client,
                                              final_layout=saved.compact))
    assert all(not identity.startswith("photo-") for identity in audit.get("candidates", []))


@pytest.mark.parametrize("item", PHOTOS, ids=lambda item: item.get("id"))
def test_all_photos_preserve_role_opacity_and_use_solid_fallback(item):
    roles = item.get("content", {}).get("roles", {})
    rgb = "FFFFFF"
    if item.get("id") in {"photo-ux-meeting-room-square", "photo-ux-meeting-room-wide"}:
        rgb = "000000"
    assert (roles.get("primary"), roles.get("secondary"), roles.get("tertiary")) == (
        "#FF" + rgb, "#CC" + rgb, "#99" + rgb,
    )
    original = artifact()
    task = {**original.taskSpec, "size": item.get("size"), "appVersion": "99.0.0"}
    result = themes.apply_theme(original.genui, item, task, {})
    for identity, color in (
        ("primary", "#FF" + rgb), ("secondary", "#CC" + rgb), ("tertiary", "#99" + rgb),
    ):
        assert node_by_id(result, identity).get("styles", {}).get("fontColor") == color
    assert not node_by_id(result, "root").get("styles", {}).get("linearGradient")
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF8FADCC"
    assert node_by_id(result, "panel").get("styles", {}).get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(result) == themes.foreground_signature(original.genui)


@pytest.mark.parametrize("field,value", [
    ("maxTextLines", 4), ("includeButtons", True), ("includeTitle", True),
    ("squareSingleBusiness", False), ("squareSubjectAlignment", "center"),
])
def test_registry_rejects_drift_from_shared_contract(field, value):
    config = registry.load_theme_registry()
    config.get("photoEligibility", {})[field] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("kind", ["sleep-capsule-square", "music-dual-buttons-square", "texture"])
def test_registry_rejects_retired_per_image_policies(kind):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("kind") == "photo")
    entry.get("contentEligibility", {})["kind"] = kind
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("business,family", [
    ("calendar", "blue"), ("battery", None), ("earphone", "purple"), ("weather", "blue"),
    ("sleep", "purple"), ("music", "purple"), ("sport", "orange"), ("countdown", "orange"),
])
@pytest.mark.parametrize("wide", [False, True])
def test_abstract_business_colors_follow_gallery_rules(business, family, wide):
    saved = sample(PATHS.get(business), 1, wide=wide, title="假期")
    suffix = "wide" if wide else "square"
    for color in ("blue", "purple", "orange"):
        identity = f"photo-ux-texture-{color}-diamond-{suffix}"
        assert (rejection(saved, identity) is None) is (color == family)


def test_music_buttons_only_have_zero_body_lines():
    saved = sample(PATHS.get("music"), 1)
    rows = themes.decode(saved.compact)
    rows[0][3].remove("reading")
    rows = [row for row in rows if row[0] != "reading"]
    saved = expanded(rows, saved.task)
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == 0
    assert rejection(saved, "photo-ux-violin-stage-square") is None
    assert rejection(saved, PURPLE) is None


def test_battery_has_subject_but_no_abstract_candidate_even_with_ring():
    saved = sample(PATHS.get("battery"), 3)
    root = next(node for node in saved.nodes if node.get("id") == "root")
    root.get("children", []).append("ring")
    saved.nodes.append({"id": "ring", "component": "Progress",
                        "styles": {"type": "ring"}})
    assert rejection(saved, "photo-ux-starry-sky-square") is None
    assert rejection(saved, BLUE)


@pytest.mark.parametrize("response", ['{"themeId":"gradient-purple"}', "invalid"])
def test_eligible_fusion_precedes_gradient_when_no_photo_matches(monkeypatch, response):
    saved = sample(lines=4)
    monkeypatch.setattr(themes, "fusion_candidate_gate", lambda *args: {
        "allowedTokens": ["fusion-ball-sleep-violet"],
    })
    result, audit = choose(saved, monkeypatch, response)
    assert audit.get("candidates") == ["fusion-ball-sleep-violet"]
    assert audit.get("themeId") == "fusion-ball-sleep-violet"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
