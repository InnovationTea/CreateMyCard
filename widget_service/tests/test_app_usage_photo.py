"""应用使用时长沿用紫色抽象图的业务、行数、布局与交付合同。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.capability_registry import CapabilityRegistry
from services.compact_dsl_a2ui_converter import ComponentRow
from services.protocol_registry import A2UIProtocolRegistry
from services.theme_texture_eligibility import visible_business
from services.validator import ArtifactValidator
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import ACTION, choose, evidence, rejection, sample

USAGE = "/data/dailyUsage/mostUsedApps/0/totalDuration"
PURPLE = "photo-ux-texture-purple-"


@pytest.mark.parametrize("root", ["/data/dailyUsage", "/data/mostUsedApps", "/data/custom/usage"])
@pytest.mark.parametrize("field", ["appName", "totalDuration"])
def test_usage_fields_follow_output_contract_not_fixed_write_root(root, field):
    rows = [ComponentRow("usage", "Text", {
        "content": {"path": f"{root}/mostUsedApps/2/{field}"},
    })]
    assert visible_business(rows) == "app-usage"


@pytest.mark.parametrize("path", [
    "/data/dailyUsage/mostUsedApps/0/unknown",
    "/data/dailyUsage/mostUsedApps/0",
    "/data/dailyUsage/mostUsedApps/first/totalDuration",
    "/data/dailyUsage/mostUsedApps/0/totalDuration/extra",
    "/data/dailyUsage/totalDuration",
    "/data/powerRanking/rankingList/0/appName",
    "/data/powerRanking/rankingList/0/powerConsumption",
    "/data/currentTime/updatedAt",
    "/data/healthSport/nightSleepDurationText",
])
def test_other_or_unknown_fields_are_not_application_usage(path):
    rows = [ComponentRow("reading", "Text", {"content": {"path": path}})]
    assert visible_business(rows) != "app-usage"


def test_multiple_applications_are_one_business_but_sleep_is_not():
    rows = [
        ComponentRow("first", "Text", {"content": {"path": USAGE}}),
        ComponentRow("second", "Text", {
            "content": "{{ ${/data/mostUsedApps/mostUsedApps/1/appName} + ' ' + "
                       "${/data/mostUsedApps/mostUsedApps/1/totalDuration} }}",
        }),
    ]
    assert visible_business(rows) == "app-usage"
    rows.append(ComponentRow("sleep", "Text", {
        "content": {"path": "/data/healthSport/nightSleepDurationText"},
    }))
    assert visible_business(rows) is None


def test_only_purple_abstracts_add_usage_and_keep_enabled_states():
    photos = registry.registered_themes(include_disabled=True)
    usage_photos = []
    for photo in photos:
        businesses = photo.get("contentEligibility", {}).get("businesses", [])
        if "app-usage" in businesses:
            usage_photos.append(photo)
            assert photo.get("pool") == "texturePhotos"
            assert photo.get("family") == "purple"
            assert set(businesses) == {"sleep", "earphone", "music", "app-usage"}
    assert len(usage_photos) == 6
    disabled = [item.get("id") for item in usage_photos if not item.get("enabled")]
    assert disabled == [PURPLE + "circles-wide"]
    registry.validate_registry(registry.load_theme_registry())


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("shape", ["diamond", "diagonal"])
def test_eligible_usage_has_two_uniform_purple_candidates(monkeypatch, wide, shape):
    saved = sample(USAGE, 3, wide=wide)
    suffix = "wide" if wide else "square"
    expected = {PURPLE + item + "-" + suffix for item in ("diamond", "diagonal")}
    selected = PURPLE + shape + "-" + suffix
    calls = []

    def choice(items):
        assert set(items) == expected
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    result, audit = choose(saved, monkeypatch, '{"themeId":"gradient-blue"}')
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert len(calls) == 1
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    scope = "main" if wide else "root"
    assert evidence(saved).get("photoBodyTextFlow", {}).get(scope, {}).get("lineCount") == 3


@pytest.mark.parametrize("lines,allowed", [(1, True), (3, True), (4, False)])
def test_fully_centered_usage_only_uses_circles(monkeypatch, lines, allowed):
    saved = sample(USAGE, lines, button=False, align="center")
    rows = themes.decode(saved.compact)
    root = rows[0]
    root[2].update(alignItems="center", justifyContent="center")
    root[3][:] = ["reading"]
    rows = [row for row in rows if row[0] != "title"]
    saved = expanded(rows, saved.task)
    _, audit = choose(saved, monkeypatch)
    photos = [identity for identity in audit.get("candidates", []) if identity.startswith("photo-")]
    assert photos == ([PURPLE + "circles-square"] if allowed else [])


@pytest.mark.parametrize("wide", [False, True])
def test_over_limit_body_lines_reject_usage_photos(wide):
    limit = 3
    saved = sample(USAGE, limit + 1, wide=wide)
    suffix = "wide" if wide else "square"
    for shape in ("diamond", "diagonal"):
        assert f"超过{limit}行" in rejection(saved, PURPLE + shape + "-" + suffix)


def test_square_sleep_plus_usage_uses_first_business_purple_family():
    saved = sample(USAGE, 1)
    rows = themes.decode(saved.compact)
    rows[0][3].append("sleep")
    path = "/data/healthSport/nightSleepDurationText"
    rows.extend([["sleep", "Text", {"content": {"path": path}}], [path, "7小时"]])
    saved = expanded(rows, saved.task)
    assert rejection(saved, PURPLE + "diamond-square") is None


def test_wide_abstract_uses_first_business_without_main_focus_gate():
    saved = sample(USAGE, 3, wide=True)
    rows = themes.decode(saved.compact)
    upper = next(row for row in rows if row[0] == "upper")
    path = "/data/weather/current/temperature"
    upper[2]["primaryText"] = {"path": path}
    rows.append([path, "29"])
    saved = expanded(rows, saved.task)
    assert rejection(saved, PURPLE + "diamond-wide") is None
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), PURPLE + "diamond-wide") is None
    saved = sample(USAGE, 2)
    saved.task["size"] = "2x4"
    assert rejection(saved, PURPLE + "diamond-wide") is None


def test_query_and_unshown_usage_cannot_override_actual_weather():
    saved = sample("/data/weather/current/temperature", 1)
    saved.task["userQuery"] = "应用使用时长"
    saved.task["dataModelSchema"] = {"data": {"dailyUsage": {"mostUsedApps": []}}}
    rows = themes.decode(saved.compact)
    rows.append([USAGE, "45分钟"])
    assert "首个可见业务" in rejection(expanded(rows, saved.task), PURPLE + "diamond-square")


def test_disabled_switch_still_excludes_usage_photos(monkeypatch):
    saved = sample(USAGE, 1)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    _, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    assert not any(item.startswith("photo-") for item in audit.get("candidates", []))


@pytest.mark.parametrize("wide", [False, True])
def test_usage_selection_delivers_one_obs_image_and_preserves_foreground(monkeypatch, wide):
    saved = sample(USAGE, 3, wide=wide, button=False)
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    original.cardSpec["suggestSize"] = saved.task.get("size")
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    capability = capabilities.get_data_capability("GetDailyMostUsage")
    assert capability is not None
    original.effectiveCapabilities = {
        "data": [capability.model_dump()], "event": ACTION, "asset": [],
    }
    original.cardSpec["dataBindings"] = [{
        "capabilityId": "GetDailyMostUsage", "arguments": {}, "writeResultTo": "/data/dailyUsage",
    }]
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    delivered = asyncio.run(themes.theme_artifact(
        original, saved.task, client, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    suffix = "wide" if wide else "square"
    urls = set()
    for item in registry.registered_themes("texturePhotos"):
        if item.get("id") in {PURPLE + "diamond-" + suffix, PURPLE + "diagonal-" + suffix}:
            urls.add(item.get("remoteUrl"))
    background = node_by_id(delivered.genui, themes.PREFIX + "base")
    assert background.get("src") in urls
    images = []
    for node in themes.components(themes.decode(delivered.genui)):
        if node.get("component") == "Image" and node.get("src") in urls:
            images.append(node)
    assert len(images) == 1
    root_styles = node_by_id(delivered.genui, "root").get("styles", {})
    assert root_styles.get("backgroundColor") == "#FF8FADCC"
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(saved.source)
