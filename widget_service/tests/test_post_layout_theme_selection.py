"""后置主题保留原融合选择合同，不把宽卡默认改成融球。"""

import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import theme_selection_policy as policy
from services.compact_component_runtime import load_visual_recipe_contract
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.layout_theme_contract import layout_only_prompt
from services.protocol_registry import A2UIProtocolRegistry
from services.theme_style_roles import layout_phase

LAYOUT = '\n'.join([
    '["root","Column",{"width":"matchParent","height":"matchParent"},["value"]]',
    '["value","EmphasisText",{"mainText":"已连接"}]',
])
FUSION_THEME_IDS = {
    "fusion-ball-schedule-blue", "fusion-ball-battery-teal",
    "fusion-ball-sleep-violet", "fusion-ball-sport-orange",
}


@pytest.fixture
def settings(monkeypatch):
    config = get_settings()
    monkeypatch.setattr(config, "enable_photo_background_theme", False)
    monkeypatch.setattr(config, "enable_subjectless_wide_theme", False)
    return config


def layout_source(size):
    with layout_phase():
        return convert_compact_dsl_to_a2ui(LAYOUT, size=size)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fusion_candidates_require_square_and_runtime_gate(monkeypatch, enabled, size):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: enabled)
    candidates = themes.presets({"size": size})
    balls = [item for item in candidates if item.get("kind") == "fusion"]
    assert bool(balls) == (enabled and size == "2x2")
    if balls:
        assert {item.get("id") for item in balls} == FUSION_THEME_IDS


def test_selection_contract_reuses_original_mapping_without_color_values():
    rules = themes.original_selection_rules()
    for clause in (
        "独立事实不超过 3 项", "仅一个内容组", "显式动作不超过 1 个",
        "单会议时间线使用暖色微渐变", "列表、双分区、多组指标及 2x4",
        "纯主题标题和 CTA 不计入事实数", "多业务以用户明确的主业务为准",
        "天气、耳机、电量、设备、未知业务默认蓝色",
        "睡眠、专注、一般运动和健康概览默认紫色",
        "日程、会议、倒计时和纪念日默认暖色",
        "单个会议、日程、提醒（沿用原融球触发条件）",
    ):
        assert clause in rules
    assert not re.search(r"#[0-9a-fA-F]{6,8}", rules)
    assert "天气" not in rules.split("融球业务映射：", 1)[1]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_gradient_colors_and_geometry_unchanged(settings, size, family):
    names = {"blue": "蓝色", "purple": "紫色", "warm": "暖色"}
    task = {"size": size, "userQuery": "使用" + names.get(family), "appVersion": "11.9.9.342"}
    source = layout_source(size)
    client = SimpleNamespace(generate=AsyncMock(
        return_value=json.dumps({"themeId": "gradient-" + family})
    ))
    final, audit = asyncio.run(themes.select_theme(source, task, client, final_layout=LAYOUT))
    assert audit.get("themeId") == "gradient-" + family
    assert audit.get("selectorError") is None
    assert themes.foreground_signature(source) == themes.foreground_signature(final)
    nodes = themes.components(themes.decode(final))
    root = next(node for node in nodes if node.get("id") == "root")
    pair = load_visual_recipe_contract().get("palettes", {}).get(family, {}).get("gradients")
    assert pair
    assert root.get("styles", {}).get("linearGradient") == {
        "direction": "RightBottom", "colors": [[pair[0][0], 0], [pair[0][1], 1]],
    }
    messages = client.generate.call_args.args[0]
    payload = json.loads(messages[1].get("content"))
    assert payload.get("size") == size
    assert "finalLayout" not in payload
    assert payload.get("layoutSummary", {}).get("complete") is True
    assert "已连接" in json.dumps(payload.get("layoutSummary"), ensure_ascii=False)
    assert themes.original_selection_rules() in messages[0].get("content")


@pytest.mark.parametrize("token", sorted(FUSION_THEME_IDS))
def test_wide_rejects_model_attempt_to_select_fusion(settings, monkeypatch, token):
    monkeypatch.setattr(themes, "fusion_ball_enabled", lambda version: True)
    task = {"size": "2x4", "userQuery": "耳机状态"}
    source = layout_source("2x4")
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": token})))
    final, audit = asyncio.run(themes.select_theme(source, task, client))
    assert audit.get("themeId") == "gradient-blue"
    assert audit.get("selectorError")
    assert not any(item.startswith("fusion-ball-") for item in audit.get("candidates", []))
    assert "fusionBall" not in final


def test_layout_prompt_still_excludes_original_color_contract():
    original = A2UIProtocolRegistry.read_design_prompt("design-compact-dsl")
    assert "## 背景选择与业务映射" not in original
    messages = layout_only_prompt([{"role": "system", "content": original}])
    prompt = messages[0].get("content")
    assert "## 背景选择与业务映射" not in prompt
    assert "融球业务映射" not in prompt
    assert not re.search(r"#[0-9a-fA-F]{6,8}", prompt)
    assert "不选择主题" in prompt


def test_visible_summary_is_available_when_compact_source_not_provided(settings):
    source = layout_source("2x2")
    client = SimpleNamespace(generate=AsyncMock(return_value='{"themeId":"gradient-blue"}'))
    asyncio.run(themes.select_theme(source, {"size": "2x2", "userQuery": "天气"}, client))
    messages = client.generate.call_args.args[0]
    payload = json.loads(messages[1].get("content"))
    assert "finalLayout" not in payload
    assert payload.get("layoutSummary", {}).get("source") == "expanded-visible-content"
    assert "已连接" in json.dumps(payload.get("layoutSummary"), ensure_ascii=False)


@pytest.mark.parametrize("size,expected", [("2x2", "#CCFFFFFF"), ("2x4", "#99FFFFFF")])
@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_light_panel_is_original_white_surface_not_button_color(size, expected, family):
    source = layout_source(size)
    records = themes.decode(source)
    nodes = themes.components(records)
    nodes.append({
        "id": "panel", "component": "Column", "children": [],
        "styles": {"backgroundColor": "@theme:panel/1"},
    })
    root = next(node for node in nodes if node.get("id") == "root")
    root.get("children", []).append("panel")
    source = themes.encode(records)
    theme = next(t for t in themes.presets({"size": size}) if t.get("id") == "gradient-" + family)
    result = themes.apply_theme(source, theme, {"size": size}, {})
    panel = next(n for n in themes.components(themes.decode(result)) if n.get("id") == "panel")
    assert panel.get("styles", {}).get("backgroundColor") == expected


@pytest.mark.parametrize("business,count,expected", [
    ("earphone", 2, "fusion-ball-battery-teal"),
    ("earphone", 4, None),
    ("weather", 2, None),
    ("calendar", 3, "fusion-ball-schedule-blue"),
])
def test_business_and_visible_facts_gate(monkeypatch, business, count, expected):
    monkeypatch.setattr(policy, "match_compact_layout", lambda *a, **k: SimpleNamespace(
        layout_id="S-title-content-action"
    ))
    fields = {f"field{i}": {"type": "string", "description": str(i)} for i in range(count)}
    task = {"size": "2x2", "userQuery": "状态卡片", "dataModelSchema": {"data": {business: fields}}}
    items = [{"value": {"path": f"/data/{business}/{name}"}} for name in fields]
    # Multiple fields in ONE component are still separate facts.
    source = json.dumps(["details", "SecondaryBody", {"items": items}])
    evidence = policy.fusion_candidate_gate(task, source)
    assert evidence.get("visibleFieldCount") == count
    assert evidence.get("allowedTokens") == ([expected] if expected else [])


@pytest.mark.parametrize("layout_id", ["S-dual-info", "S-quad-content", "S-title-dual-content"])
def test_grouped_layouts_excluded(monkeypatch, layout_id):
    monkeypatch.setattr(policy, "match_compact_layout", lambda *a, **k: SimpleNamespace(
        layout_id=layout_id
    ))
    task = {"size": "2x2", "userQuery": "耳机", "dataModelSchema": {"data": {"earphone": {}}}}
    assert policy.fusion_candidate_gate(task, LAYOUT).get("allowedTokens") == []


def test_removed_photo_pools_are_empty_including_disabled_entries():
    assert len(themes.registered_themes("photos")) == 13
    assert themes.registered_themes("subjectlessWidePhotos", include_disabled=True) == []
    assert themes.registered_themes("squareExpansions", include_disabled=True) == []


@pytest.mark.parametrize("business,family", [
    ("healthSport", "purple"), ("calendar", "warm"), ("countdown", "warm"),
    ("weather", "blue"), ("earphone", "blue"), ("phoneBattery", "blue"),
])
def test_single_business_keeps_original_palette(business, family):
    task = {"userQuery": "显示业务内容", "dataModelSchema": {"data": {business: {}}}}
    assert policy.default_palette_family(task) == family
    task["userQuery"] = "我要紫色背景"
    assert policy.default_palette_family(task) is None
