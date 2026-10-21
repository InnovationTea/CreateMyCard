"""统一注册表迁移必须保持已批准输出及选择边界，不把配色或 DSL 交给模型。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import compact_component_runtime, fusion_ball_expander
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import theme_selection_policy as policy
from services.theme_layout_summary import layout_summary

BASELINE = json.loads((Path(__file__).parent / "fixtures/post_layout_theme_v1_outputs.json")
                      .read_text(encoding="utf-8"))
RETIRED_BALL_COLORS = {
    "fusion-ball-schedule-cool": ("#FF1F3399", "#FF2385B3", "#FF24B3B3"),
    "fusion-ball-schedule-warm": ("#FF731D28", "#FFFF5533", "#FFE68A2E"),
}


@pytest.fixture(autouse=True)
def runtime(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_photo_background_theme", False)
    monkeypatch.setattr(settings, "enable_subjectless_wide_theme", False)
    original_get = settings.CONFIG.get

    def configured(key, default=None):
        return "1.0.0" if key == "fusion_ball_min_prd_version" else original_get(key, default)

    monkeypatch.setattr(settings.CONFIG, "get", configured)
    return settings


def configured_theme(identity):
    return next(theme for theme in registry.registered_themes(include_disabled=True)
                if theme.get("id") == identity)


def use_config(monkeypatch, config):
    registry.validate_registry(config)
    monkeypatch.setattr(registry, "_load_registry", lambda _path: copy.deepcopy(config))


STANDARD_CASES = []
for baseline_case in BASELINE.get("cases", []):
    if baseline_case.get("id") in RETIRED_BALL_COLORS:
        continue
    if baseline_case.get("id", "").startswith("photo-"):
        continue
    STANDARD_CASES.append(baseline_case)


@pytest.mark.parametrize("case", STANDARD_CASES)
def test_output_matches_frozen_pre_migration_theme(case):
    size = case.get("size")
    source = BASELINE.get("sources", {}).get(size)
    assert source
    task = {"size": size, "appVersion": "99.0.0"}
    theme = configured_theme(case.get("id"))
    result = themes.apply_theme(source, theme, task, case.get("overrides", {}))
    records = themes.decode(result)
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(canonical.encode()).hexdigest() == case.get("digest")


@pytest.mark.parametrize("case", [case for case in BASELINE.get("cases", [])
                                 if case.get("id") in RETIRED_BALL_COLORS])
def test_blue_replaces_only_the_retired_ball_colors(case):
    source = BASELINE.get("sources", {}).get("2x2")
    result = themes.apply_theme(source, configured_theme("fusion-ball-schedule-blue"),
                                {"size": "2x2", "appVersion": "99.0.0"}, {})
    records = themes.decode(result)
    old_colors = RETIRED_BALL_COLORS.get(case.get("id"))
    assert old_colors
    ball_ids = ("fusionBallLarge", "fusionBallMedium", "fusionBallSmall")
    colors_by_id = dict(zip(ball_ids, old_colors, strict=True))
    for node in themes.components(records):
        color = colors_by_id.get(node.get("id"))
        if color:
            node.get("styles", {})["backgroundColor"] = color
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(canonical.encode()).hexdigest() == case.get("digest")


def test_all_themes_are_self_contained_and_only_current_photos_remain():
    config = registry.load_theme_registry()
    entries = config.get("themes", [])
    assert len(entries) == 49
    assert len({theme.get("id") for theme in entries}) == 49
    for theme in entries:
        assert "palette" not in theme
        assert theme.get("background")
        content = theme.get("content", {})
        assert set(content.get("roles", {})) == set(registry._ROLE_NAMES)
        assert set(theme.get("sizes", [])).issubset(content.get("panelBySize", {}))
    photos = registry.registered_themes("photos", include_disabled=True)
    assert len(photos) == 21
    assert all(item.get("contentEligibility", {}).get("kind") == "uniform" for item in photos)
    for pool in ("subjectlessWidePhotos", "squareExpansions"):
        assert registry.registered_themes(pool, include_disabled=True) == []


@pytest.mark.parametrize("path,value", [
    (("themes", 0, "content", "roles", "primary"), "not-a-color"),
    (("themes", 0, "content", "roles"), {}),
    (("themes", 0, "content", "panelBySize"), {"2x2": "#CCFFFFFF"}),
    (("themes", 0, "background", "colors"), ["#FFFFFFFF"]),
    (("themes", 0, "enabled"), "yes"),
    (("themes", 0, "sizes"), ["unknown"]),
    (("themes", 6, "sizes"), ["2x4"]),
    (("themes", 6, "background", "ballColors"), {}),
    (("themes", 6, "background", "blurRadius"), -1),
    (("themes", 6, "background", "blurRadius"), float("nan")),
    (("themes", 6, "background", "blurRadius"), float("inf")),
    (("themes", 6, "businessDescription"), ""),
    (("themes", 11, "background", "src"), "https://invalid/image.jpg"),
    (("themes", 11, "background", "frame", "slotWidth"), 0),
    (("selection", "fallbacks", "blue"), "missing-theme"),
    (("selection", "fusionRouting", 0, "themeId"), "missing-theme"),
    (("selection", "fusionRouting", 0, "queryAll"), ["[invalid"]),
    (("themes", 0, "enabled"), False),
    (("themes", 13, "sourceSize"), []),
    (("matching",), None),
])
def test_invalid_registry_fails_at_load(path, value):
    config = registry.load_theme_registry()
    target = config
    for key in path[:-1]:
        target = target[key] if isinstance(target, list) else target.get(key)
        assert target is not None
    target[path[-1]] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_duplicate_theme_id_rejected():
    config = registry.load_theme_registry()
    entries = config.get("themes", [])
    entries.append(copy.deepcopy(entries[0]))
    with pytest.raises(ValueError, match="Duplicate"):
        registry.validate_registry(config)


def test_registry_returns_independent_copies():
    first = registry.load_theme_registry()
    first.get("themes", []).clear()
    assert len(registry.load_theme_registry().get("themes", [])) == 49


def test_adding_disabling_and_deleting_themes_only_requires_registry(monkeypatch):
    config = registry.load_theme_registry()
    entries = config.get("themes", [])
    extra = copy.deepcopy(entries[0])
    extra["id"] = "gradient-blue-added"
    extra["name"] = "新增主题"
    entries.append(extra)
    use_config(monkeypatch, config)
    assert "gradient-blue-added" in {theme.get("id") for theme in themes.presets({"size": "2x2"})}
    extra["enabled"] = False
    use_config(monkeypatch, config)
    assert "gradient-blue-added" not in {theme.get("id") for theme in registry.registered_themes()}
    entries.remove(extra)
    use_config(monkeypatch, config)
    assert len(registry.registered_themes()) == 38


@pytest.mark.parametrize("identity", [
    "gradient-blue", "solid-blue", "fusion-ball-sleep-violet", "photo-ux-clouds-weather-square",
])
def test_each_theme_reads_its_own_complete_content(monkeypatch, identity):
    config = registry.load_theme_registry()
    theme = next(item for item in config.get("themes", []) if item.get("id") == identity)
    content = theme.get("content", {})
    primary = "#FFFFFFFF" if theme.get("kind") == "photo" else "#FF112233"
    content.get("roles", {})["primary"] = primary
    content.get("panelBySize", {})["2x2"] = "#22123456"
    use_config(monkeypatch, config)
    source = BASELINE.get("sources", {}).get("2x2")
    result = themes.apply_theme(source, configured_theme(identity),
                                {"size": "2x2", "appVersion": "99.0.0"}, {})
    nodes = themes.components(themes.decode(result))
    panel = next(node for node in nodes if node.get("id") == "panel")
    assert panel.get("styles", {}).get("backgroundColor") == "#22123456"
    assert primary in result
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


def test_fusion_colors_and_glass_read_config_not_legacy_constants(monkeypatch):
    config = registry.load_theme_registry()
    theme = next(item for item in config.get("themes", []) if item.get("kind") == "fusion")
    background = theme.get("background", {})
    background.get("ballColors", {})["large"] = "#FF112233"
    background["glassColor"] = "#11FFFFFF"
    background["blurRadius"] = 123
    use_config(monkeypatch, config)
    nodes = themes.fusion_background(theme, {"size": "2x2", "appVersion": "99.0.0"})
    ball = next(node for node in nodes if node.get("id") == "fusionBallLarge")
    glass = next(node for node in nodes if node.get("id") == "fusionBallGlassLayer")
    assert ball.get("styles", {}).get("backgroundColor") == "#FF112233"
    assert glass.get("styles", {}).get("backgroundColor") == "#11FFFFFF"
    assert glass.get("styles", {}).get("backdropBlur") == {"radius": 123}


def test_final_theme_expansion_does_not_read_legacy_color_sources(monkeypatch):
    def forbidden_palette_read():
        raise RuntimeError("Post-layout themes must not load legacy palettes")

    monkeypatch.setattr(compact_component_runtime, "load_visual_recipe_contract",
                        forbidden_palette_read)
    monkeypatch.setattr(fusion_ball_expander, "_DESIGN_TOKEN_FIXED_PALETTES", {})
    for theme in registry.registered_themes():
        size = theme.get("sourceSize") or theme.get("sizes", [])[0]
        task = {"size": size, "appVersion": "99.0.0"}
        source = BASELINE.get("sources", {}).get(size)
        assert source
        result = themes.apply_theme(source, theme, task, {})
        assert "@theme:" not in result
        assert themes.foreground_signature(source) == themes.foreground_signature(result)


def test_invalid_file_is_rejected_on_first_load(tmp_path):
    config = registry.load_theme_registry()
    config.get("themes", [])[0].get("content", {}).get("roles", {}).pop("primary")
    path = tmp_path / "invalid-themes.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="primary"):
        registry._load_registry(path)


def semantic_layout():
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "center"}, ["weather"]],
        ["right", "Region", {"variant": "center"}, ["sleep", "action"]],
        ["weather", "EmphasizedData", {
            "value": {"path": "/data/weather/temperature"}, "unit": "度",
        }],
        ["sleep", "SecondaryBody", {"items": [{"label": "睡眠", "value": 82,
                                              "icon": "resources/private.svg",
                                              "fontColor": "#12345678"}]}],
        ["action", "PillButton", {"label": "打开闹钟", "onClick": [
            {"call": "open", "args": {"uri": "private://secret"}},
        ]}],
        ["/data/unused", "unused-sample-value"],
    ])


def test_layout_summary_retains_groups_facts_actions_without_raw_dsl():
    summary = layout_summary(semantic_layout(), [])
    assert summary.get("layoutTypes") == ["W-split-panels"]
    assert summary.get("source") == "compact-semantics"
    assert "compactSummaryUnavailable" not in summary
    assert len(summary.get("contentGroups", [])) == 2
    assert summary.get("actionCount") == 1
    serialized = json.dumps(summary, ensure_ascii=False)
    for expected in ("睡眠", "82", "/data/weather/temperature", "打开闹钟"):
        assert expected in serialized
    for forbidden in ("#12345678", "resources/", "private://", "unused-sample", "onClick"):
        assert forbidden not in serialized


def test_model_only_receives_summary_and_candidate_descriptions():
    client = SimpleNamespace(generate=AsyncMock(return_value='{"themeId":"gradient-blue"}'))
    source = BASELINE.get("sources", {}).get("2x4")
    task = {"size": "2x4", "userQuery": "看看天气和睡眠",
            "dataModelSchema": {"secret": "not-needed"}}
    asyncio.run(themes.select_theme(source, task, client, final_layout=semantic_layout()))
    messages = client.generate.call_args.args[0]
    payload = json.loads(messages[1].get("content"))
    assert payload.get("layoutSummary", {}).get("complete")
    assert payload.get("layoutSummary", {}).get("source") == "compact-semantics"
    assert payload.get("candidates")
    assert "finalLayout" not in payload
    assert "dataModelSchema" not in payload
    for candidate in payload.get("candidates", []):
        assert candidate.get("themeId") and candidate.get("description")
        for forbidden in ("background", "content", "roles", "src", "frame", "ballColors"):
            assert forbidden not in candidate
    assert source not in messages[1].get("content")
    assert "private://" not in messages[1].get("content")


@pytest.mark.parametrize("response", [
    '{"themeId":"unknown"}', '{"themeId":"gradient-blue","color":"#FF123456"}',
    '{"themeId":null}', '["gradient-blue"]', 'invalid-json',
])
def test_invalid_model_choice_keeps_original_gradient_fallback(response):
    client = SimpleNamespace(generate=AsyncMock(return_value=response))
    task = {"size": "2x2", "userQuery": "睡眠", "dataModelSchema": {"data": {"healthSport": {}}}}
    result, audit = asyncio.run(themes.select_theme(BASELINE.get("sources", {}).get("2x2"),
                                                   task, client))
    assert audit.get("themeId") == "gradient-purple"
    assert audit.get("selectorError")
    assert "linearGradient" in result


@pytest.mark.parametrize("route,query,expected", [
    ("earphone-status", "耳机", "fusion-ball-battery-teal"),
    ("battery-readout", "电量", "fusion-ball-battery-teal"),
    ("countdown", "倒计时", "fusion-ball-sport-orange"),
    ("calendar-event", "会议提醒", "fusion-ball-schedule-blue"),
    ("calendar-event", "会议使用融球", "fusion-ball-schedule-blue"),
    ("calendar-event", "评审使用融球", "fusion-ball-schedule-blue"),
    ("calendar-event", "日程提醒", "fusion-ball-schedule-blue"),
    ("health-readout", "睡眠", "fusion-ball-sleep-violet"),
    ("health-readout", "运动", "fusion-ball-sport-orange"),
    ("health-readout", "心率", None),
    ("weather", "天气", None),
])
def test_business_mapping_preserves_original_routes(monkeypatch, route, query, expected):
    monkeypatch.setattr(policy.PromptBuilder, "_visual_route", lambda task: (route, {}))
    task = SimpleNamespace(userQuery=query, dataModelSchema={})
    assert policy._business_token(task) == expected
