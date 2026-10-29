"""宽卡主焦点四行及批准图片跨方向准入；不改变方卡、业务或前景。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.capability_registry import CapabilityRegistry
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import ACTION, PATHS, choose, evidence, rejection, sample
from theme_preference_samples import preference, reply

A19 = "photo-ux-digital-wave-wide"
WAVE = "photo-ux-mountain-sunset-lake-wide"
FUZZY = "photo-ux-pink-sunset-lake-wide"
GRADIENT = "photo-ux-gradient-wide"
BLUE = "photo-ux-texture-blue-diamond-wide"
PURPLE = "photo-ux-texture-purple-diagonal-wide"
ORANGE = "photo-ux-texture-orange-diamond-wide"
CASES = [(A19, "calendar"), (WAVE, "weather"), (BLUE, "weather"),
         (PURPLE, "sleep"), (ORANGE, "countdown"), (FUZZY, "weather"),
         (GRADIENT, "countdown")]


def focus_sample(business="weather", lines=4, layout="top", variant="continuous", title=True):
    path = PATHS.get(business)
    assert path is not None
    saved = sample(path, lines, wide=True)
    content = {"path": path}
    if business == "countdown":
        content = "{{ ${" + path + "} + '天' }}"
    if layout in {"left", "right"}:
        rows = themes.decode(saved.compact)
        rows[0][2]["orientation"] = "content-" + layout
        next(row for row in rows if row[0] == "reading")[2]["content"] = content
        return expanded(rows, saved.task)
    children = ["header", "primary", "details"] if title else ["primary", "details"]
    rows = [
        ["root", "Layout", {"layout": "W-top-bottom", "variant": variant}, children],
        ["primary", "Text", {"content": content, "maxLines": 20}],
        ["details", "TextBlock", {"items": [
            {"label": "电量", "value": {"path": PATHS.get("battery")}},
            {"label": "耳机", "value": {"path": PATHS.get("earphone")}},
        ]}],
        [path, "\n".join(["主区正文"] * lines)],
        [PATHS.get("battery"), "80%"], [PATHS.get("earphone"), "已连接"],
    ]
    if title:
        rows.append(["header", "SingleLineTitle", {"title": "顶部标题"}])
    return expanded(rows, saved.task)


@pytest.mark.parametrize("identity,business", CASES)
@pytest.mark.parametrize("layout", ["left", "right", "top"])
@pytest.mark.parametrize("lines", [3, 4, 5])
def test_subject_counts_main_but_abstract_counts_whole_card(identity, business, layout, lines):
    saved = focus_sample(business, lines, layout)
    reason = rejection(saved, identity)
    abstract = "texture" in identity
    limit = 3 if abstract else 4
    body_lines = lines + 2 if abstract and layout == "top" else lines
    assert (reason is None) is (body_lines <= limit), reason
    if body_lines > limit:
        assert f"超过{limit}行" in reason
    scope = "primary" if layout == "top" else "main"
    assert evidence(saved).get("photoBodyTextFlow", {}).get(scope, {}).get("lineCount") == lines


@pytest.mark.parametrize("variant", ["continuous", "bottom-details", "equal"])
@pytest.mark.parametrize("title", [False, True])
@pytest.mark.parametrize("identity,business", [(WAVE, "weather"), (FUZZY, "weather"),
                                             (GRADIENT, "countdown")])
def test_all_registered_top_bottom_variants_have_the_same_main_scope(variant, title, identity,
                                                                   business):
    saved = focus_sample(business, variant=variant, title=title)
    assert rejection(saved, identity) is None


@pytest.mark.parametrize("identity,business", [
    ("photo-ux-sleep-wide", "sleep"), ("photo-ux-sport-center-wide", "sport"),
    ("photo-ux-meeting-room-wide", "calendar"),
])
@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_other_subjects_gain_four_lines_but_not_new_layouts(identity, business, layout):
    saved = focus_sample(business, 4, layout)
    assert (rejection(saved, identity) is None) is (layout == "left")
    assert rejection(focus_sample(business, 5, "left"), identity)


@pytest.mark.parametrize("identity,business", CASES)
def test_mixed_or_unknown_main_business_does_not_use_auxiliary_business(identity, business):
    saved = focus_sample(business, 1)
    rows = themes.decode(saved.compact)
    primary = next(row for row in rows if row[0] == "primary")
    primary[2]["content"] = {"path": "/data/unknown/value"}
    rows.append(["/data/unknown/value", "未知"])
    if "texture" in identity:
        assert rejection(expanded(rows, saved.task), identity) is None
    else:
        assert "单业务" in rejection(expanded(rows, saved.task), identity)
    primary[2]["content"] = (
        "{{ ${" + PATHS.get(business) + "} + ${/data/phoneBattery/batteryLevel} }}"
    )
    if "texture" in identity:
        assert rejection(expanded(rows, saved.task), identity) is None
    else:
        assert "单业务" in rejection(expanded(rows, saved.task), identity)


def test_only_approved_wide_configs_use_main_focus_and_circle_enablement_is_unchanged():
    flexible = []
    for item in registry.registered_themes(include_disabled=True):
        policy = item.get("contentEligibility", {})
        if policy.get("wideLayout") == "main-focus":
            flexible.append(item.get("id"))
            assert item.get("size") == "2x4"
            assert item.get("pool") == "photos" and item.get("id") in {
                A19, WAVE, FUZZY, GRADIENT, "photo-ux-cumulus-blue-wide",
                "photo-ux-wave-wide", "photo-ux-fuzzy-wide",
            }
    assert len(flexible) == 7
    for item in registry.registered_themes("texturePhotos", include_disabled=True):
        assert "wideLayout" not in item.get("contentEligibility", {})
        if item.get("id", "").endswith("circles-wide"):
            assert item.get("enabled") is False
    assert registry.load_theme_registry().get("photoEligibility", {}).get("wideMaxTextLines") == 4


@pytest.mark.parametrize("limit", [3, 5, "4", True, None])
def test_registry_rejects_invalid_wide_limit(limit):
    config = registry.load_theme_registry()
    config.get("photoEligibility", {})["wideMaxTextLines"] = limit
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_registry_rejects_main_focus_policy_on_square():
    config = registry.load_theme_registry()
    item = next(item for item in config.get("themes", [])
                if item.get("id") == "photo-ux-wave-square")
    item.get("contentEligibility", {})["wideLayout"] = "main-focus"
    with pytest.raises(ValueError, match="wide photo"):
        registry.validate_registry(config)


@pytest.mark.parametrize("identity,business", [
    ("photo-ux-wave-square", "weather"),
    ("photo-ux-texture-purple-diamond-square", "sleep"),
])
def test_square_photos_still_stop_at_three_lines(identity, business):
    assert rejection(sample(PATHS.get(business), 3), identity) is None
    assert "超过3行" in rejection(sample(PATHS.get(business), 4), identity)


@pytest.mark.parametrize("layout", ["W-split-panels", "W-four-slots"])
@pytest.mark.parametrize("business", ["weather", "countdown"])
def test_split_and_grid_select_ice_for_weather_otherwise_check_abstract_total_lines(
    monkeypatch, layout, business,
):
    path = PATHS.get(business)
    assert path is not None
    content = {"path": path}
    if business == "countdown":
        content = "{{ ${" + path + "} + '天' }}"
    if layout == "W-split-panels":
        rows = [["root", "Layout", {"layout": layout}, ["left", "right"]]]
        for side in ("left", "right"):
            rows.extend([
                [side, "Region", {"variant": "title-content"}, [side + "_title", side + "_text"]],
                [side + "_title", "SingleLineTitle", {"title": "天气"}],
                [side + "_text", "Text", {"content": content}],
            ])
    else:
        rows = [["root", "Layout", {"layout": layout}, ["a", "b", "c", "d"]]]
        for identity in ("a", "b", "c", "d"):
            rows.append([identity, "InfoBlock", {"variant": "slot", "surfaceRole": "panel",
                                                "primaryText": content,
                                                "secondaryText": "天气"}])
    rows.append([path, "29"])
    saved = expanded(rows, {"size": "2x4", "userQuery": "天气", "appVersion": "99.0.0"})
    _, audit = choose(saved, monkeypatch)
    if business == "weather":
        assert audit.get("candidates") == ["photo-ux-ice-wide"]
        assert audit.get("themeId") == "photo-ux-ice-wide"
    elif layout == "W-split-panels":
        assert all(identity.startswith("photo-ux-texture-")
                   for identity in audit.get("candidates", []))
        assert audit.get("themeId", "").startswith("photo-ux-texture-")
    else:
        assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))
    for identity in (WAVE, FUZZY, GRADIENT):
        assert rejection(saved, identity)


@pytest.mark.parametrize("identity,business", [(WAVE, "weather"), (FUZZY, "weather"),
                                             (GRADIENT, "countdown")])
def test_top_primary_title_alone_is_not_a_main_focus(identity, business):
    saved = focus_sample(business)
    rows = themes.decode(saved.compact)
    rows[0][3] = ["header", "details"]
    rows = [row for row in rows if row[0] != "primary"]
    assert rejection(expanded(rows, saved.task), identity)


@pytest.mark.parametrize("query,value,operation", [
    ("使用融球效果", "fusion", "prefer"),
    ("不要背景图片", "photo", "avoid"),
    ("使用纯色背景", "solid", "prefer"),
])
def test_explicit_user_theme_stays_above_new_photo_rules(monkeypatch, query, value, operation):
    saved = focus_sample()
    saved.task["userQuery"] = query
    items = [preference("backgroundKind", value, query, operation)]
    _, audit = choose(saved, monkeypatch, reply(items))
    assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))
    if value == "fusion":
        assert audit.get("theme", {}).get("kind") == "gradient"
        assert audit.get("unmetPreferences") == items
        assert audit.get("preferenceWarning")


@pytest.mark.parametrize("identity,business", [(A19, "calendar"), (WAVE, "weather"),
                                             (ORANGE, "countdown"), (FUZZY, "weather"),
                                             (GRADIENT, "countdown")])
@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_final_obs_delivery_validates_and_preserves_every_foreground(monkeypatch, identity,
                                                                   business, layout):
    if identity == ORANGE:
        config = registry.load_theme_registry()
        for item in config.get("themes", []):
            if item.get("id") in {
                GRADIENT, "photo-ux-hourglass-wide", "photo-ux-glass-hourglass-wide",
            }:
                item["enabled"] = False
        monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    saved = focus_sample(business, 1 if identity == ORANGE else 4, layout)
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    original.cardSpec["suggestSize"] = "2x4"
    original.effectiveCapabilities["event"] = ACTION
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    data = []
    bindings = []
    for capability_id, target in (
        ("GetCalendarEvents", "/data/calendar"), ("ViewWeather", "/data/weather"),
        ("GetCountdownDays", "/data/countdown/first"),
        ("GetPhoneBatteryInfo", "/data/phoneBattery"), ("GetEarphoneInfo", "/data/earphone"),
    ):
        capability = capabilities.get_data_capability(capability_id)
        assert capability is not None
        data.append(capability.model_dump())
        bindings.append({"capabilityId": capability_id, "arguments": {}, "writeResultTo": target})
    original.effectiveCapabilities["data"] = data
    original.cardSpec["dataBindings"] = bindings
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    monkeypatch.setattr(themes.secrets, "choice", lambda items: identity)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    audit_log = []
    select = themes.select_theme

    async def capture(*args, **kwargs):
        result, audit = await select(*args, **kwargs)
        audit_log.append(audit)
        return result, audit

    monkeypatch.setattr(themes, "select_theme", capture)
    result = asyncio.run(themes.theme_artifact(
        original, saved.task, client, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    audit = audit_log[0]
    assert identity in audit.get("candidates", [])
    assert not audit.get("finalValidationErrors"), audit
    assert audit.get("themeId") == identity
    assert themes.foreground_signature(result.genui) == themes.foreground_signature(saved.source)
    assert node_by_id(result.genui, themes.PREFIX + "base").get("src") == (
        audit.get("theme", {}).get("remoteUrl")
    )
    styles = node_by_id(result.genui, "root").get("styles", {})
    rgb = "000000" if identity == GRADIENT else "FFFFFF"
    if identity == GRADIENT:
        assert styles.get("backgroundColor") == "#FFE6E6E6"
        assert styles.get("linearGradient") == {
            "direction": "LeftBottom", "colors": [["#FFFFFFFF", 0], ["#FFE6E6E6", 1]],
        }
    else:
        assert styles.get("backgroundColor") == "#FF1F1F99"
    nodes = themes.components(themes.decode(result.genui))
    backgrounds = []
    for node in nodes:
        if node.get("id", "").startswith(themes.PREFIX) and node.get("component") == "Image":
            backgrounds.append(node)
        if node.get("component") == "Text":
            assert node.get("styles", {}).get("fontColor") in {
                "#FF" + rgb, "#CC" + rgb, "#99" + rgb,
            }
    assert len(backgrounds) == 1
