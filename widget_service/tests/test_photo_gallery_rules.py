"""图册停用、节假日逐对象准入、会议贴底及抽象图形状分配。"""

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_autumn_calendar_photos import expanded
from test_uniform_photo_eligibility import PATHS, choose, evidence, rejection, sample

BIRDS = "photo-ux-birds-countdown-square"
WAVE = "photo-ux-digital-wave-wide"
MEETING_SQUARE = "photo-ux-meeting-room-square"
MEETING_WIDE = "photo-ux-meeting-room-wide"
DISABLED = {
    "galaxy-sleep-square",
    "track-runner-square", "sunrise-runner-square", "track-sprint-square", "running-pair-wide",
    "starry-sky-wide", "airplane-tarmac-wide", "bedside-lamp-wide",
    "texture-blue-circles-wide", "texture-purple-circles-wide", "texture-orange-circles-wide",
}


def test_only_requested_gallery_entries_are_disabled_but_preserved():
    all_photos = registry.registered_themes(include_disabled=True)
    disabled = {item.get("id") for item in all_photos if not item.get("enabled")}
    assert disabled == {"photo-ux-" + name for name in DISABLED}
    assert len(registry.registered_themes("photos")) == 13
    assert len(registry.registered_themes("texturePhotos")) == 15
    for item in all_photos:
        if item.get("id") in disabled:
            assert item.get("remoteUrl", "").startswith("https://")
            assert item.get("source", {}).get("assetSha256")


@pytest.mark.parametrize("business", list(PATHS))
@pytest.mark.parametrize("wide", [False, True])
def test_disabled_images_never_enter_candidates(monkeypatch, business, wide):
    saved = sample(PATHS.get(business), 1, wide=wide, title="假期")
    _, audit = choose(saved, monkeypatch)
    disabled = {"photo-ux-" + name for name in DISABLED}
    assert not disabled.intersection(audit.get("candidates", []))


@pytest.mark.parametrize("title,allowed", [
    ("中秋节", True), ("国庆", True), ("元旦", True), ("假期", True),
    ("生日", False), ("考试", False), ("旅行纪念日", False), ("倒计时", False),
])
def test_a12_requires_visible_holiday_not_user_query(title, allowed):
    saved = sample(PATHS.get("countdown"), 1, title=title)
    saved.task["userQuery"] = "国庆中秋假期倒计时"
    assert (rejection(saved, BIRDS) is None) is allowed
    assert rejection(saved, "photo-ux-texture-orange-diamond-square") is None


def double_countdown(first="国庆", second="中秋", lines=1):
    rows = [["root", "Column", {"width": "matchParent", "height": "matchParent",
                                  "alignItems": "start"}, ["first", "second"]]]
    for identity, name in (("first", first), ("second", second)):
        path = f"/data/countdown/{identity}/countdownDays"
        content = "{{ '" + name + " ' + ${" + path + "} }}"
        rows.extend([
            [identity, "Column", {"surfaceRole": "panel", "alignItems": "start"},
             [identity + "_value"]],
            [identity + "_value", "Text", {"content": content, "maxLines": 5}],
            [path, "\n".join(["30天"] * lines)],
        ])
    return expanded(rows, {"size": "2x2", "userQuery": "倒计时", "appVersion": "99.0.0"})


@pytest.mark.parametrize("second,lines,allowed", [
    ("中秋", 1, True), ("中秋", 2, False), ("考试", 1, False), ("待办", 1, False),
])
def test_a12_dual_panels_need_all_holidays_and_total_at_most_three(second, lines, allowed):
    saved = double_countdown(second=second, lines=lines)
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("root", {})
    assert flow.get("lineCount") == 2 * lines
    assert (rejection(saved, BIRDS) is None) is allowed


def test_hidden_holiday_name_and_button_label_cannot_authorize_a12():
    saved = sample(PATHS.get("countdown"), 1, title="倒计时")
    rows = themes.decode(saved.compact)
    rows.append(["/data/countdown/first/name", "国庆"])
    next(row for row in rows if row[0] == "button")[2]["label"] = "查看国庆假期"
    assert rejection(expanded(rows, saved.task), BIRDS)


@pytest.mark.parametrize("button,align,lines,allowed", [
    (False, "start", 1, True), (False, "start", 3, True), (False, "start", 4, False),
    (False, "center", 1, False), (True, "start", 1, False),
])
def test_a19_only_uses_bottom_left_calendar_body(button, align, lines, allowed):
    saved = sample(PATHS.get("calendar"), lines, wide=True, button=button, align=align)
    assert (rejection(saved, WAVE) is None) is allowed


def test_a19_rejects_top_primary_bottom_support_and_old_information_business():
    saved = sample(PATHS.get("calendar"), 1, wide=True, button=False)
    rows = themes.decode(saved.compact)
    main = next(row for row in rows if row[0] == "main")
    main[2]["variant"] = "title-hero-support"
    main[3].append("details")
    rows.append(["details", "Text", {"content": "会议室"}])
    assert rejection(expanded(rows, saved.task), WAVE)
    assert rejection(sample(PATHS.get("information"), 1, wide=True, button=False), WAVE)


@pytest.mark.parametrize("button,lines", [(False, 1), (True, 1), (True, 3)])
def test_meeting_square_uses_uniform_left_aligned_calendar_body(button, lines):
    saved = sample(PATHS.get("calendar"), lines, button=button)
    assert rejection(saved, MEETING_SQUARE) is None


@pytest.mark.parametrize("business,lines,align", [
    ("calendar", 4, "start"), ("calendar", 1, "center"), ("calendar", 1, "end"),
    ("sleep", 1, "start"), ("countdown", 1, "start"),
])
def test_meeting_square_rejects_wrong_business_alignment_or_line_count(business, lines, align):
    saved = sample(PATHS.get(business), lines, align=align)
    assert rejection(saved, MEETING_SQUARE)


@pytest.mark.parametrize("button,expected", [(False, WAVE), (True, MEETING_WIDE)])
def test_meeting_wide_and_a19_partition_bottom_left_layout(monkeypatch, button, expected):
    saved = sample(PATHS.get("calendar"), 3, wide=True, button=button)
    result, audit = choose(saved, monkeypatch)
    assert audit.get("candidates") == [expected]
    assert audit.get("themeId") == expected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_meeting_wide_accepts_top_primary_with_bottom_support_without_action():
    saved = sample(PATHS.get("calendar"), 2, wide=True, button=False)
    rows = themes.decode(saved.compact)
    main = next(row for row in rows if row[0] == "main")
    main[2]["variant"] = "title-hero-support"
    main[3].append("details")
    rows.append(["details", "Text", {"content": "会议室"}])
    saved = expanded(rows, saved.task)
    assert rejection(saved, MEETING_WIDE) is None
    assert rejection(saved, WAVE)


def test_meeting_wide_keeps_business_line_count_and_wide_layout_gate():
    assert rejection(sample(PATHS.get("calendar"), 4, wide=True), MEETING_WIDE)
    assert rejection(sample(PATHS.get("sleep"), 1, wide=True), MEETING_WIDE)
    saved = sample(PATHS.get("calendar"), 1, wide=True)
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), MEETING_WIDE)


def test_only_new_meeting_photos_use_black_foreground():
    for photo in registry.registered_themes(include_disabled=True):
        if photo.get("kind") != "photo":
            continue
        rgb = "000000" if photo.get("id") in {MEETING_SQUARE, MEETING_WIDE} else "FFFFFF"
        roles = photo.get("content", {}).get("roles", {})
        assert roles.get("primary") == "#FF" + rgb
        assert roles.get("secondary") == "#CC" + rgb
        assert roles.get("tertiary") == "#99" + rgb


@pytest.mark.parametrize("pool", ["photos", "texturePhotos"])
def test_black_foreground_is_only_accepted_in_subject_pool(pool):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", []) if item.get("pool") == pool)
    roles = photo.get("content", {}).get("roles", {})
    for name in ("primary", "secondary", "tertiary",
                 "graphicPrimary", "graphicSecondary", "graphicTertiary"):
        color = roles.get(name)
        assert isinstance(color, str)
        roles[name] = color[:3] + "000000"
    if pool == "photos":
        registry.validate_registry(config)
    else:
        with pytest.raises(ValueError, match="foreground"):
            registry.validate_registry(config)


def centered_sample(business, primitive=False):
    path = PATHS.get(business)
    root = ["root", "Layout", {"layout": "S-center"}, ["reading"]]
    if primitive:
        root = ["root", "Column", {"width": "matchParent", "height": "matchParent",
                                   "alignItems": "center", "justifyContent": "center"}, ["reading"]]
    rows = [root, ["reading", "DataDisplay", {"label": "状态", "value": {"path": path},
                                              "supportingText": "今日"}], [path, 30]]
    return expanded(rows, {"size": "2x2", "userQuery": "显示状态", "appVersion": "99.0.0"})


@pytest.mark.parametrize("business,family", [
    ("calendar", "blue"), ("earphone", "purple"), ("countdown", "orange"),
])
@pytest.mark.parametrize("primitive", [False, True])
def test_fully_centered_uses_only_circles(monkeypatch, business, family, primitive):
    saved = centered_sample(business, primitive)
    result, audit = choose(saved, monkeypatch)
    assert audit.get("candidates") == [f"photo-ux-texture-{family}-circles-square"]
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("shape", ["diamond", "diagonal"])
def test_other_layouts_choose_between_two_equal_candidates(monkeypatch, wide, shape):
    suffix = "wide" if wide else "square"
    expected = {f"photo-ux-texture-blue-{item}-{suffix}" for item in ("diamond", "diagonal")}
    selected = f"photo-ux-texture-blue-{shape}-{suffix}"
    calls = []

    def choice(items):
        calls.append(items)
        assert set(items) == expected
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = sample(PATHS.get("weather"), 1, wide=wide, align="center")
    result, audit = choose(saved, monkeypatch, '{"themeId":"gradient-blue"}')
    assert len(calls) == 1
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("placement,pool,size", [
    ("center", "photos", "2x2"), ("not-center", "texturePhotos", "2x4"),
    ("bottom-left", "texturePhotos", "2x4"), ("bottom-left", "photos", "2x2"),
    ("not-bottom-left", "texturePhotos", "2x4"), ("not-bottom-left", "photos", "2x2"),
])
def test_registry_rejects_placement_in_wrong_pool_or_size(placement, pool, size):
    config = registry.load_theme_registry()
    item = next(item for item in config.get("themes", [])
                if item.get("pool") == pool and item.get("sizes") == [size])
    item.get("contentEligibility", {})["placement"] = placement
    with pytest.raises(ValueError):
        registry.validate_registry(config)
