"""后置主题与最新语义布局、模板来源及修复提示的边界。"""

import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services import post_layout_theme as themes
from services.artifact_store import ArtifactStore
from services.card_validation.theme_phase_validator import theme_phase_errors
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessingResult,
)
from services.layout_theme_contract import strip_source_colors, uses_post_layout_theme
from services.theme_style_roles import in_layout_phase, layout_phase, role
from services.widget_generation_service import WidgetGenerationService


@pytest.mark.parametrize("operation,template,jsx,expected", [
    ("generateWidgetCardCompactDsl", False, False, True),
    ("generateWidgetCardCompactDsl", True, False, False),
    ("generateWidgetCardCompactDsl", False, True, False),
    ("generateWidgetCardTerseDslNested2", False, False, False),
    ("generateWidgetCard", False, False, False),
])
def test_only_actual_fusion_source_uses_theme(operation, template, jsx, expected):
    assert uses_post_layout_theme(operation, template_source=template, jsx_source=jsx) == expected


@pytest.mark.parametrize("context_flag", [False, True])
def test_processor_requires_explicit_fusion_context(monkeypatch, context_flag):
    captured = []

    def capture(self, source, context):
        captured.append(in_layout_phase())
        return DslProcessingResult(source)

    monkeypatch.setattr(DesignCompactProcessor, "_process", capture)
    context = DslProcessingContext(
        size="2x2", card_spec={}, task_spec={}, protocol_profile={}, colorless_layout=context_flag,
    )
    DesignCompactProcessor().process("source", context)
    assert captured == [context_flag]
    assert not in_layout_phase()


@pytest.mark.parametrize("operation,filtered", [
    ("generateWidgetCardCompactDsl", True), ("generateWidgetCardTerseDslNested2", False),
    ("template-generation", False), ("a2ui-model", False),
])
def test_prompt_filter_does_not_touch_template_clients(monkeypatch, operation, filtered):
    client = A2UIModelClient(use_mock=True, operation_name=operation)
    messages = [{"role": "system", "content": "布局规则"}, {"role": "user", "content": "天气"}]
    received = []

    def capture(profile, prompt):
        received.extend(prompt)
        return "ok"

    monkeypatch.setattr(client, "_load_mock_data", capture)
    asyncio.run(client.generate(messages, {"format": "compact-dsl"}))
    assert (received != messages) == filtered


@pytest.mark.asyncio
async def test_fusion_service_always_themes_after_colorless_layout(monkeypatch):
    settings = get_settings()
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_POST_LAYOUT_THEME", "false")
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_photo_background_theme", False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: False)
    calls = []
    layouts = []
    saved = []
    source = '\n'.join([
        '["root","Layout",{"layout":"S-center"},["value"]]',
        '["value","DataDisplay",{"label":"静态卡片","value":"服务已就绪",'
        '"supportingText":"状态","fontSize":24}]',
    ])

    def model(_client, profile, prompt):
        calls.append(profile.get("format"))
        if profile.get("format") == "raw-json":
            return '{"themeId":"gradient-blue"}'
        assert "不选择主题" in prompt[0].get("content", "")
        return source

    process = DesignCompactProcessor._process

    def record_layout(processor, value, context):
        assert context.colorless_layout
        result = process(processor, value, context)
        layouts.append(result.standard_dsl)
        return result

    async def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(
            artifactUrl="https://artifact.test/fusion", artifactDigest="sha256:x",
        )

    monkeypatch.setattr(A2UIModelClient, "_load_mock_data", model)
    monkeypatch.setattr(DesignCompactProcessor, "_process", record_layout)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="test-user", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="生成一个名为静态卡片的卡片", size="2x2", title="静态卡片",
        description="固定后置主题流程",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)

    assert response.status == GenerationStatus.SUCCESS, response
    assert calls == ["compact-dsl", "raw-json"]
    assert len(layouts) == len(saved) == 1
    assert not re.search(r"#[0-9A-Fa-f]{6,8}", layouts[0])
    assert theme_phase_errors(layouts[0], layout=True) == []
    final = saved[0].genui
    assert "linearGradient" in final and "@theme:" not in final
    assert themes.foreground_signature(layouts[0]) == themes.foreground_signature(final)


def test_strip_preserves_semantic_source_and_data_colors():
    rows = [
        ["root", "Layout", {"layout": "S-center", "backgroundColor": "#FF112233"}, ["value"]],
        ["value", "EmphasisText", {"mainText": "状态"}],
        ["/data/color", "#FF112233"],
    ]
    result = strip_source_colors("\n".join(json.dumps(row) for row in rows))
    actual = [json.loads(line) for line in result.splitlines()]
    assert actual[0] == ["root", "Layout", {"layout": "S-center"}, ["value"]]
    assert actual[2] == rows[2]


def test_semantic_region_backplates_remain_colorless_until_theme():
    source = '\n'.join([
        '["root","Layout",{"layout":"W-split-panels"},["left","right"]]',
        '["left","Region",{"variant":"center"},["first"]]',
        '["right","Region",{"variant":"center"},["second"]]',
        '["first","EmphasisText",{"mainText":"天气"}]',
        '["second","EmphasisText",{"mainText":"电量"}]',
    ])
    with layout_phase():
        layout = convert_compact_dsl_to_a2ui(source, size="2x4")
    assert not re.search(r"#[0-9a-fA-F]{6,8}", layout)
    assert not theme_phase_errors(layout, layout=True)
    theme = next(t for t in themes.presets({"size": "2x4"}) if t.get("id") == "gradient-blue")
    final = themes.apply_theme(layout, theme, {"size": "2x4"}, {})
    for node in themes.components(themes.decode(final)):
        if node.get("id") in {"left", "right"}:
            assert node.get("styles", {}).get("backgroundColor") == "#99FFFFFF"
    legacy = convert_compact_dsl_to_a2ui(source, size="2x4")
    assert themes.foreground_signature(final) == themes.foreground_signature(legacy)
    assert "@theme:" not in legacy


@pytest.mark.parametrize("key", ["barColor", "trackColor", "dividerColor", "strokeColor"])
def test_chart_colors_are_not_geometry(key):
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "styles": {}},
        {"id": "chart", "component": "Divider", "styles": {key: role("primary")}},
    ]}}])
    theme = next(t for t in themes.presets({"size": "2x4"}) if t.get("id") == "gradient-blue")
    result = themes.apply_theme(source, theme, {"size": "2x4"}, {})
    assert "@theme:" not in result
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


@pytest.mark.parametrize("update", [None, [], "invalid", {"components": None}, {"components": {}}])
def test_malformed_protocol_is_left_to_protocol_validator(update):
    source = json.dumps({"updateComponents": update})
    assert theme_phase_errors(source, layout=False) == []
