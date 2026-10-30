"""结构化偏好合同回归；Mock只验证执行链路，不冒充真实模型语义识别。"""

import asyncio
import copy
import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_user_preferences as preferences
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_grouped_photo_text import q52_artifact, q52_sample
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import PATHS, choose, sample
from theme_preference_samples import preference, reply

TONES = {
    "dark": {"color": "#FF1A1A1A", "panelColor": "#33FFFFFF", "primary": "#FFFFFFFF"},
    "light": {"color": "#FFFFFFFF", "panelColor": "#33000000", "primary": "#FF1A1A1A"},
}


@pytest.mark.parametrize("wide,align", [(False, "start"), (False, "end"), (True, "start")])
@pytest.mark.parametrize("tone,query", [
    ("dark", "看天气，底子压暗一些，晚上不刺眼"),
    ("light", "请给我明亮的底色"),
])
@pytest.mark.parametrize("theme_id", ["gradient-blue", "photo-ux-wave-wide", "unknown-theme"])
def test_normalized_tone_precedes_picture_pools(monkeypatch, wide, align, tone, query, theme_id):
    saved = sample(PATHS.get("weather"), 2, wide=wide, align=align)
    saved.task["userQuery"] = query
    before = copy.deepcopy(saved)
    items = [preference("backgroundTone", tone, query)]
    result, audit = choose(saved, monkeypatch, reply(items, theme_id))
    assert audit.get("preferenceStatus") == "confirmed"
    assert audit.get("userPreferences") == items
    assert audit.get("candidates")
    assert all(not identity.startswith(("photo-", "fusion-"))
               for identity in audit.get("candidates", []))
    assert audit.get("photoSelection") == {}
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == (
        TONES.get(tone, {}).get("color")
    )
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert saved == before


@pytest.mark.parametrize("query,attribute,value", [
    ("不要渐变，给我图片背景", "backgroundKind", "gradient"),
    ("不要红色背景", "backgroundColor", "#FFFF0000"),
    ("不要蓝色文字", "textColor", "#FF0000FF"),
    ("不要深色背景", "backgroundTone", "dark"),
])
def test_negative_preferences_are_exclusions_not_affirmative_overrides(
    monkeypatch, query, attribute, value,
):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = query
    items = [preference(attribute, value, query, "avoid")]
    result, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("preferenceStatus") == "confirmed"
    assert preferences.preference_reason(audit.get("theme"), items, audit.get("userColors")) is None
    if attribute == "backgroundKind":
        assert audit.get("theme", {}).get("kind") == "photo"
    elif attribute == "backgroundTone":
        assert audit.get("userColors", {}).get("background", {}).get("tone") == "light"
    else:
        assert audit.get("userColors") == {}
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("wide", [False, True])
def test_original_query_sent_once_with_all_structurally_eligible_types(monkeypatch, wide):
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "不要暗沉的，背景换个清爽的浅调"
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    items = [preference("backgroundTone", "light", saved.task.get("userQuery"))]
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items)))
    _, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    client.generate.assert_awaited_once()
    payload = json.loads(client.generate.call_args.args[0][1].get("content"))
    assert payload.get("query") == saved.task.get("userQuery")
    assert any(item.get("type") == "photo" for item in payload.get("candidates", []))
    assert any(item.get("type") == "gradient" for item in payload.get("candidates", []))
    assert audit.get("userColors", {}).get("background", {}).get("tone") == "light"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("tone", ["dark", "light"])
def test_final_tone_delivery_preserves_foreground_and_backplate_contrast(monkeypatch, size, tone):
    saved = q52_sample()
    original = q52_artifact(saved) if size == "2x4" else artifact()
    original.taskSpec["userQuery"] = "我想要另一种背景亮度"
    before = original.model_copy(deep=True)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    items = [preference("backgroundTone", tone, original.taskSpec.get("userQuery"))]
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, client, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact if size == "2x4" else None,
    ))
    expected = TONES.get(tone, {})
    assert node_by_id(delivered.genui, "root").get("styles", {}).get(
        "backgroundColor"
    ) == expected.get("color")
    panel_id = "upper" if size == "2x4" else "panel"
    assert node_by_id(delivered.genui, panel_id).get("styles", {}).get(
        "backgroundColor"
    ) == expected.get("panelColor")
    value_id = "content_primary_value" if size == "2x4" else "primary"
    assert node_by_id(delivered.genui, value_id).get("styles", {}).get(
        "fontColor"
    ) == expected.get("primary")
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(
        original.genui
    )
    assert original == before


@pytest.mark.parametrize("tone", ["dark", "light"])
@pytest.mark.parametrize("error", ["ASSET.INVALID", "VISUAL.CONTRAST: test rejection"])
def test_validation_fallback_retains_confirmed_tone_and_checks_contrast(monkeypatch, tone, error):
    original = artifact()
    original.taskSpec["userQuery"] = "调整背景亮度"
    validator = ArtifactValidator({})
    calls = []

    def validate(delivered, profile):
        calls.append(delivered.genui)
        return [error] if len(calls) == 1 else validator.validate(delivered, profile)

    items = [preference("backgroundTone", tone, original.taskSpec.get("userQuery"))]
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items, "unknown")))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, client, SimpleNamespace(validate=validate),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert len(calls) == 2
    client.generate.assert_awaited_once()
    assert node_by_id(delivered.genui, "root").get("styles", {}).get("backgroundColor") == (
        TONES.get(tone, {}).get("color")
    )
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(
        original.genui
    )


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("query", ["状态卡片", "正文写着深色、使用、不要、渐变"])
def test_no_model_preference_keeps_picture_priority_without_scanning_words(
    monkeypatch, wide, query,
):
    saved = sample(PATHS.get("weather"), 2, wide=wide, button=False)
    saved.task["userQuery"] = query
    result, audit = choose(saved, monkeypatch, reply([]))
    suffix = "wide" if wide else "square"
    expected = {
        "photo-ux-mountain-sunset-lake-" + suffix,
        "photo-ux-pink-sunset-lake-" + suffix,
    }
    if wide:
        expected.add("photo-ux-cumulus-blue-wide")
    assert set(audit.get("candidates")) == expected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert audit.get("userColors") == {}
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("raw,status", [
    ("invalid", "unavailable"), ('{"themeId":"gradient-blue"}', "legacy-unconfirmed"),
    (reply([]), "confirmed"),
])
def test_missing_or_invalid_preferences_are_audited_without_keyword_guess(monkeypatch, raw, status):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "背景改成深色"
    _, audit = choose(saved, monkeypatch, raw)
    assert audit.get("preferenceStatus") == status
    assert audit.get("userColors") == {}
    assert bool(audit.get("preferenceWarning")) is (status != "confirmed")


def test_transport_failure_reports_unavailable_preferences(monkeypatch):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "深色背景"
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(side_effect=RuntimeError("model unavailable")))
    _, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    client.generate.assert_awaited_once()
    assert audit.get("preferenceStatus") == "unavailable"
    assert audit.get("preferenceWarning")
    assert audit.get("selectorError")
    assert audit.get("userColors") == {}


def test_validation_fallback_never_adds_a_forbidden_gradient(monkeypatch):
    original = artifact()
    original.taskSpec["userQuery"] = "使用纯色"
    items = [preference("backgroundKind", "solid", "使用纯色")]
    validator = ArtifactValidator({})
    calls = []

    def validate(delivered, profile):
        calls.append(delivered.genui)
        return ["ASSET.INVALID"] if len(calls) == 1 else validator.validate(delivered, profile)

    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items, "solid-blue")))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, client, SimpleNamespace(validate=validate),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert len(calls) == 2
    assert "linearGradient" not in node_by_id(delivered.genui, "root").get("styles", {})
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(
        original.genui
    )


@pytest.mark.parametrize("business,wide", [
    ("sleep", False), ("earphone", False), ("calendar", True), ("sport", True),
])
def test_valid_preferences_survive_invalid_choice_across_businesses(monkeypatch, business, wide):
    saved = sample(PATHS.get(business), 2, wide=wide)
    saved.task["userQuery"] = "背景偏暗"
    items = [preference("backgroundTone", "dark", "背景偏暗")]
    result, audit = choose(saved, monkeypatch, reply(items, "invalid-choice"))
    assert audit.get("selectorError")
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == "#FF1A1A1A"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("attribute,value", [
    ("backgroundKind", "solid"), ("backgroundKind", "gradient"),
    ("paletteFamily", "purple"),
])
def test_explicit_type_and_family_keep_hard_layout_gate(monkeypatch, attribute, value):
    saved = sample(PATHS.get("weather"), 2, wide=True)
    saved.task["userQuery"] = "我有明确的视觉要求"
    items = [preference(attribute, value, saved.task.get("userQuery"))]
    _, audit = choose(saved, monkeypatch, reply(items))
    theme = audit.get("theme", {})
    key = "kind" if attribute == "backgroundKind" else "family"
    assert theme.get(key) == value
    assert not any(identity.startswith("fusion-") for identity in audit.get("modelCandidates", []))


@pytest.mark.parametrize("items", [
    None, {}, [None], [{"property": "backgroundTone"}],
    [preference("geometry", "change", "原文")],
    [preference("backgroundTone", "dark", "不存在的原文")],
    [preference("backgroundTone", "dark", "原文", "maybe")],
    [preference("backgroundTone", [], "原文")],
    [preference("backgroundTone", "unknown", "原文")],
    [preference("themeId", "not-registered", "原文")],
    [preference("backgroundColor", "#123", "原文")],
    [preference("backgroundColor", "#00112233", "原文")],
    [preference("backgroundTone", "dark", "")],
    [preference("backgroundTone", "dark", "原文")] * 17,
    [preference("backgroundTone", "dark", "原文"),
     preference("backgroundTone", "light", "原文")],
    [preference("backgroundTone", "dark", "原文"),
     preference("backgroundTone", "dark", "原文", "avoid")],
    [preference("backgroundTone", "dark", "原文", "avoid"),
     preference("backgroundTone", "light", "原文", "avoid")],
])
def test_invalid_semantic_contract_rejected(items):
    with pytest.raises(ValueError):
        preferences.parse_preferences(items, "原文", registry.registered_themes())


def test_specific_color_beats_tone_without_named_color_keywords():
    query = "深色背景，精确背景色 #123456，字用米白"
    items = [
        preference("backgroundTone", "dark", query),
        preference("backgroundColor", "#123456", query),
        preference("textColor", "#f5f5dc", query),
    ]
    normalized = preferences.parse_preferences(items, query, registry.registered_themes())
    colors = preferences.color_overrides(normalized)
    assert colors.get("background") == {
        "color": "#FF123456", "evidence": query, "panelColor": "#33FFFFFF",
    }
    assert colors.get("text") == {"color": "#FFF5F5DC", "evidence": query}


def test_unregistered_model_asset_never_becomes_a_candidate(monkeypatch):
    saved = sample(PATHS.get("weather"), 2)
    saved.task["userQuery"] = "用一张图"
    items = [preference("themeId", "https://invalid.example/photo.jpg", "用一张图")]
    _, audit = choose(saved, monkeypatch, reply(items))
    assert audit.get("preferenceStatus") == "unavailable"
    assert audit.get("selectorError")
    assert not any(identity.startswith("https:") for identity in audit.get("candidates", []))


def test_explicit_registered_image_still_obeys_structure_gate(monkeypatch):
    saved = sample(PATHS.get("weather"), 5)
    saved.task["userQuery"] = "使用海浪图"
    items = [preference("themeId", "photo-ux-wave-square", "使用海浪图")]
    _, audit = choose(saved, monkeypatch, reply(items, "photo-ux-wave-square"))
    assert audit.get("preferenceStatus") == "unavailable"
    assert "photo-ux-wave-square" not in audit.get("candidates", [])


def test_unsatisfiable_preferences_do_not_relax_wide_fusion_gate(monkeypatch):
    saved = sample(PATHS.get("weather"), 2, wide=True)
    saved.task["userQuery"] = "使用融球"
    items = [preference("backgroundKind", "fusion", "使用融球")]
    result, audit = choose(saved, monkeypatch, reply(items, "fusion-ball-sleep-violet"))
    assert audit.get("theme", {}).get("kind") == "gradient"
    assert audit.get("unmetPreferences") == items
    assert audit.get("preferenceWarning")
    assert not audit.get("fusionEligibility", {}).get("allowedTokens")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_tone_defaults_stay_configurable(monkeypatch):
    config = registry.load_theme_registry()
    dark = config.get("userColorOverrides", {}).get("toneBackgrounds", {}).get("dark")
    assert dark is not None
    dark["color"] = "#FF202020"
    registry.validate_registry(config)
    monkeypatch.setattr(registry, "_load_registry", lambda _path: copy.deepcopy(config))
    colors = preferences.color_overrides([preference("backgroundTone", "dark", "用户要求")])
    assert colors.get("background", {}).get("color") == "#FF202020"
    dark["color"] = "#00202020"
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("color", ["#FF123456", "#FFF5F5DC"])
def test_specific_background_color_keeps_generated_ink_and_panels_readable(
    monkeypatch, size, color,
):
    saved = q52_sample()
    original = q52_artifact(saved) if size == "2x4" else artifact()
    original.taskSpec["userQuery"] = f"使用我指定的底色 {color}"
    items = [preference("backgroundColor", color, original.taskSpec.get("userQuery"))]
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items)))
    validator = ArtifactValidator({})
    profile = A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile()
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, client, validator, profile,
        final_layout=saved.compact if size == "2x4" else None,
    ))
    roles = registry.user_background_roles(color)
    panel = "upper" if size == "2x4" else "panel"
    assert node_by_id(delivered.genui, panel).get("styles", {}).get(
        "backgroundColor"
    ) == roles.get("componentSecondary")
    assert validator.validate(delivered, profile) == []
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(
        original.genui
    )


def test_preference_runtime_has_no_user_language_regex():
    source = inspect.getsource(preferences)
    assert "_VERB" not in source
    assert "_NEGATION" not in source
    assert "re.search" not in source
    assert "re.finditer" not in source
    assert not hasattr(themes, "user_color_overrides")
