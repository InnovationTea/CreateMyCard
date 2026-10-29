"""融球不可用仍交付普通背景，保留其它偏好、布局和原门禁。"""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.capability_registry import CapabilityRegistry
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_autumn_calendar_photos import expanded
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_post_layout_sleep_theme import ACTION, sleep_layout, sleep_task
from test_uniform_photo_eligibility import PATHS, sample
from theme_preference_samples import preference, reply

QUERY = "使用融球，其余配色与排除条件按我的要求"
FUSION = preference("backgroundKind", "fusion", "使用融球")


@pytest.fixture(autouse=True)
def enable_features(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_photo_background_theme", True)
    original_get = settings.CONFIG.get

    def configured(key, default=None):
        return "11.7.5.206" if key == "fusion_ball_min_prd_version" else original_get(key, default)

    monkeypatch.setattr(settings.CONFIG, "get", configured)


def choose(saved, items, theme_id="gradient-blue"):
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items, theme_id)))
    result, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    client.generate.assert_awaited_once()
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    return result, audit


def fusion_sample():
    saved = expanded(themes.decode(sleep_layout()), sleep_task(QUERY))
    return saved


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("business", ["weather", "calendar", "sleep", "sport", "earphone"])
def test_ineligible_fusion_preserves_foreground_across_sizes_and_businesses(wide, business):
    saved = sample(PATHS.get(business), 2, wide=wide)
    saved.task["userQuery"] = QUERY
    before = copy.deepcopy(saved)
    _, audit = choose(saved, [FUSION])
    assert audit.get("theme", {}).get("kind") in {"gradient", "solid"}
    assert audit.get("unmetPreferences") == [FUSION]
    assert audit.get("userPreferences") == [FUSION]
    assert audit.get("preferenceStatus") == "confirmed"
    assert audit.get("preferenceWarning")
    assert not audit.get("fusionEligibility", {}).get("allowedTokens")
    assert all(not item.startswith("photo-") for item in audit.get("candidates", []))
    assert saved == before


@pytest.mark.parametrize("extra,expected", [
    (preference("backgroundTone", "dark", QUERY), "#FF1A1A1A"),
    (preference("backgroundTone", "light", QUERY), "#FFFFFFFF"),
    (preference("backgroundColor", "#123456", "#123456"), "#FF123456"),
    (preference("backgroundKind", "gradient", QUERY, "avoid"), None),
    (preference("paletteFamily", "purple", QUERY), None),
])
def test_other_color_tone_and_negative_preferences_survive(extra, expected):
    saved = sample(PATHS.get("weather"), 2, wide=True)
    saved.task["userQuery"] = QUERY + "，精确底色 #123456"
    result, audit = choose(saved, [FUSION, extra])
    assert audit.get("unmetPreferences") == [FUSION]
    if expected:
        assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == expected
    elif extra.get("property") == "backgroundKind":
        assert audit.get("theme", {}).get("kind") == "solid"
        assert "linearGradient" not in node_by_id(result, "root").get("styles", {})
    else:
        assert audit.get("theme", {}).get("family") == "purple"


@pytest.mark.parametrize("attribute,value", [
    ("backgroundKind", "fusion"), ("themeId", "fusion-ball-sleep-violet"),
])
def test_available_fusion_still_selected(attribute, value):
    saved = fusion_sample()
    item = preference(attribute, value, "使用融球")
    _, audit = choose(saved, [item], "fusion-ball-sleep-violet")
    assert audit.get("themeId") == "fusion-ball-sleep-violet"
    assert audit.get("unmetPreferences") == []
    assert audit.get("preferenceWarning") is None


def test_old_version_uses_ordinary_background():
    saved = fusion_sample()
    saved.task["appVersion"] = "1.0.0"
    _, audit = choose(saved, [FUSION])
    assert not any(identity.startswith("fusion-") for identity in audit.get("modelCandidates", []))
    assert audit.get("theme", {}).get("kind") == "gradient"
    assert audit.get("unmetPreferences") == [FUSION]


def test_fallback_does_not_ignore_forbidden_ordinary_backgrounds():
    saved = sample(PATHS.get("weather"), 2, wide=True)
    saved.task["userQuery"] = QUERY
    items = [FUSION, preference("backgroundKind", "gradient", QUERY, "avoid"),
             preference("backgroundKind", "solid", QUERY, "avoid")]
    with pytest.raises(ValueError, match="conflict"):
        choose(saved, items)


@pytest.mark.parametrize("explicit_theme", [False, True])
def test_fusion_drawing_failure_uses_ordinary_background(monkeypatch, explicit_theme):
    saved = fusion_sample()
    original_apply = themes.apply_theme

    def apply(source, theme, task, overrides):
        if theme.get("kind") == "fusion":
            raise ValueError("fusion drawing unavailable")
        return original_apply(source, theme, task, overrides)

    monkeypatch.setattr(themes, "apply_theme", apply)
    item = FUSION
    if explicit_theme:
        item = preference("themeId", "fusion-ball-sleep-violet", "使用融球")
    _, audit = choose(saved, [item], "fusion-ball-sleep-violet")
    assert audit.get("theme", {}).get("kind") == "gradient"
    assert audit.get("selectorError") == "fusion drawing unavailable"
    assert audit.get("unmetPreferences") == [item]


def test_fusion_validation_failure_delivers_valid_ordinary_artifact(monkeypatch):
    saved = fusion_sample()
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    capability = capabilities.get_data_capability("GetHealthAndSportSummary")
    assert capability is not None
    original.effectiveCapabilities["data"] = [capability.model_dump()]
    original.effectiveCapabilities["event"] = [ACTION]
    original.cardSpec["dataBindings"] = [{"capabilityId": "GetHealthAndSportSummary",
                                         "arguments": {}, "writeResultTo": "/data/healthSport"}]
    before = original.model_copy(deep=True)
    real_validator = ArtifactValidator({})
    calls = []
    completed = []

    def validate(delivered, profile):
        calls.append(delivered.genui)
        return ["ASSET.INVALID: injected fusion rejection"] if len(calls) == 1 else (
            real_validator.validate(delivered, profile)
        )

    def record(name, **kwargs):
        if name == "theme.completed":
            completed.append(kwargs.get("json_artifacts", {}).get("theme_audit"))

    monkeypatch.setattr(themes, "trace_record", record)
    client = SimpleNamespace(generate=AsyncMock(return_value=reply([FUSION])))
    profile = A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile()
    delivered = asyncio.run(themes.theme_artifact(
        original, saved.task, client, SimpleNamespace(validate=validate), profile,
        final_layout=saved.compact,
    ))
    client.generate.assert_awaited_once()
    assert len(calls) == 2
    assert real_validator.validate(delivered, profile) == []
    assert completed[0].get("unmetPreferences") == [FUSION]
    assert completed[0].get("theme", {}).get("kind") == "gradient"
    assert completed[0].get("preferenceWarning")
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(saved.source)
    assert original == before
