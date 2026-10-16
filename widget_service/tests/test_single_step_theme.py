"""250主题交接只发生于新建；原提示词、前景几何和编辑样式不受影响。"""

import asyncio
import copy
import json
import re

import pytest

from custom.a2ui_model_client import A2UIModelClient
from models.generation import TaskSpec
from services import post_layout_theme as themes
from services.card_validation.theme_phase_validator import theme_phase_errors
from services.generation_pipeline import DslProcessingContext
from services.single_step_250 import converter
from services.single_step_250.resources import MODEL_FORMAT, PROFILE_DIR
from services.single_step_processor import SingleStep250Processor
from services.single_step_prompt import SingleStepPromptBuilder
from services.single_step_theme import prepare_single_step_theme
from services.theme_style_roles import COLOR_FIELDS, in_layout_phase


def _source(design=None):
    root = {"width": "matchParent", "height": "matchParent", "padding": 12}
    if design:
        root["design"] = design
    rows = [
        ["root", "Column", root, ["label", "ring"]],
        ["label", "Text", {"content": "电量80%", "fontSize": 18, "fontColor": "#FF111111"}],
        ["ring", "Progress", {"value": 80, "total": 100, "type": "ring",
                              "width": 44, "height": 44, "color": "#FF9C27B0",
                              "backgroundColor": "#331F4799"}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _convert(source, size="2x2"):
    return converter.convert_compact_dsl_to_a2ui(
        source, size=size, protocol_profile={"version": "v0.9", "appVersion": "11.7.7.331"},
    )


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("design", [None, "fusion-ball-battery-teal"])
def test_handoff_preserves_foreground_data_and_sizes_and_replaces_background(size, design):
    source = _source(design)
    expanded = _convert(source, size)
    task = {"size": size, "appVersion": "11.7.7.331"}
    prepared = prepare_single_step_theme(expanded, source, task)
    assert theme_phase_errors(prepared, layout=True) == []
    assert not in_layout_phase()
    old_nodes = themes.components(themes.decode(expanded))
    new_nodes = themes.components(themes.decode(prepared))
    assert not any(node.get("id") in themes.FUSION_IDS for node in new_nodes)
    for identity in ("label", "ring"):
        old = copy.deepcopy(next(node for node in old_nodes if node.get("id") == identity))
        new = copy.deepcopy(next(node for node in new_nodes if node.get("id") == identity))
        for node in (old, new):
            styles = node.get("styles", {})
            for key in COLOR_FIELDS:
                styles.pop(key, None)
        assert old == new
    assert themes.decode(expanded)[-1] == themes.decode(prepared)[-1]
    theme = next(t for t in themes.presets(task) if t.get("id") == "gradient-blue")
    final = themes.apply_theme(prepared, theme, task, {})
    assert themes.foreground_signature(prepared) == themes.foreground_signature(final)
    assert not theme_phase_errors(final, layout=False)
    assert "@theme:" not in final
    assert "linearGradient" in final


def test_never_removes_user_nodes_merely_because_id_matches_background():
    source = _source()
    records = themes.decode(_convert(source))
    nodes = themes.components(records)
    nodes.append({"id": "fusionBallBackground", "component": "Text", "content": "保留我"})
    prepared = prepare_single_step_theme(themes.encode(records), source, {"size": "2x2"})
    assert "保留我" in prepared
    theme = next(t for t in themes.presets({"size": "2x2"}) if t.get("id") == "gradient-blue")
    with pytest.raises(ValueError, match="only be applied once"):
        themes.apply_theme(prepared, theme, {"size": "2x2"}, {})


def test_generated_background_tampering_is_not_silently_removed():
    source = _source("fusion-ball-battery-teal")
    records = themes.decode(_convert(source))
    nodes = themes.components(records)
    nodes[1]["onClick"] = {"action": "keep-user-action"}
    with pytest.raises(ValueError, match="does not match"):
        prepare_single_step_theme(
            themes.encode(records), source, {"size": "2x2", "appVersion": "11.7.7.331"},
        )


@pytest.mark.parametrize("theme_mode", [False, True])
def test_processor_only_prepares_creation_and_keeps_edit_colors(theme_mode):
    source = _source()
    context = DslProcessingContext(size="2x2", card_spec={}, task_spec={}, protocol_profile={})
    result = SingleStep250Processor(post_layout_theme=theme_mode).process(source, context)
    assert not result.errors
    if theme_mode:
        assert "#FF9C27B0" not in result.standard_dsl
        assert "@theme:" in result.standard_dsl
    else:
        assert result.standard_dsl == _convert(source)
        assert "#FF9C27B0" in result.standard_dsl


def test_native_image_and_content_panel_roles():
    source = _source()
    records = themes.decode(_convert(source))
    nodes = themes.components(records)
    nodes.extend([
        {"id": "native", "component": "Image", "src": "asset.native.svg",
         "styles": {"width": 24, "height": 24, "fillColor": "#FFFF0000"}},
        {"id": "panel", "component": "Column", "children": [],
         "styles": {"width": 100, "backgroundColor": "#CCFFFFFF"}},
    ])
    prepared = prepare_single_step_theme(themes.encode(records), source, {
        "size": "2x2", "assetCandidates": [
            {"src": "asset.native.svg", "description": "多色图标保留原色"},
        ],
    })
    found = themes.components(themes.decode(prepared))
    assert "fillColor" not in found[-2].get("styles", {})
    assert found[-1].get("styles", {}).get("backgroundColor") == "@theme:panel/1"
    assert not in_layout_phase()


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_original_250_examples_handoff_or_keep_original_conversion_error(size):
    text = (PROFILE_DIR / f"FEWSHOT_{size}.md").read_text(encoding="utf-8")
    examples = re.findall(r"```genui\s*\n(.*?)\n```", text, re.DOTALL)
    assert examples
    task = {"size": size, "appVersion": "11.7.7.331"}
    for source in examples:
        try:
            expanded = _convert(source, size)
        except converter.CompactDslConversionError:
            continue
        prepared = prepare_single_step_theme(expanded, source, task)
        assert not theme_phase_errors(prepared, layout=True)
        theme = next(t for t in themes.presets(task) if t.get("id") == "gradient-blue")
        final = themes.apply_theme(prepared, theme, task, {})
        assert themes.foreground_signature(prepared) == themes.foreground_signature(final)
        assert not theme_phase_errors(final, layout=False)


@pytest.mark.parametrize("edit", [False, True])
def test_model_boundary_preserves_original_250_colors_and_edit_source(monkeypatch, edit):
    task = TaskSpec(userQuery="背景改浅蓝", size="2x4", dataModelSchema={})
    prompt = SingleStepPromptBuilder.build(
        task, {}, previous_genui=_convert(_source()) if edit else None,
    )
    original = copy.deepcopy(prompt)
    received = []

    def capture(_client, _profile, messages):
        received.extend(messages)
        return _source()

    monkeypatch.setattr(A2UIModelClient, "_load_mock_data", capture)
    client = A2UIModelClient(use_mock=True, operation_name="generateWidgetCardCompactDsl")
    asyncio.run(client.generate(prompt, {"format": MODEL_FORMAT, "singleStepOutput": True}))
    assert received == original
    assert prompt == original
    assert "布局阶段专用合同" not in received[0].get("content", "")
