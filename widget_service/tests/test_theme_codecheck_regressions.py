"""CodeCheck 整改不改变异常降级、配色角色和图片边界判断。"""

import ast
import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import square_photo_expansion as expansion
from services import theme_photo_eligibility, theme_texture_eligibility
from services.compact_high_level_components import (
    CompactDslConversionError,
    _system_palette_color,
)
from services.theme_style_roles import layout_phase, role


@pytest.mark.parametrize("module", [registry, theme_photo_eligibility, theme_texture_eligibility])
def test_theme_comprehension_clauses_stay_on_single_lines(module):
    tree = ast.parse(inspect.getsource(module))
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.comprehension):
            continue
        if node.target.lineno != node.iter.end_lineno:
            violations.append(f"multiline for clause at line {node.target.lineno}")
        for condition in node.ifs:
            if condition.lineno != condition.end_lineno:
                violations.append(f"multiline if clause at line {condition.lineno}")
        if len(node.ifs) > 1:
            violations.append(f"multiple if clauses at line {node.target.lineno}")
    assert not violations, violations


def test_registry_frame_schema_keeps_all_required_positive_dimensions():
    assert registry._FRAME == {
        "type": "object", "additionalProperties": False,
        "required": ["slotWidth", "slotHeight", "imageWidth", "imageHeight", "align"],
        "properties": {
            "slotWidth": {"type": "number", "exclusiveMinimum": 0},
            "slotHeight": {"type": "number", "exclusiveMinimum": 0},
            "imageWidth": {"type": "number", "exclusiveMinimum": 0},
            "imageHeight": {"type": "number", "exclusiveMinimum": 0},
            "align": {"enum": ["topStart", "topEnd", "center", "bottomStart", "bottomEnd"]},
        },
    }


def test_registry_fusion_schema_keeps_three_required_argb_colors():
    background = registry._BACKGROUNDS.get("fusion")
    assert background is not None
    color = {"type": "string", "pattern": r"^#[0-9A-Fa-f]{8}$"}
    assert background.get("properties", {}).get("ballColors") == {
        "type": "object", "required": ["large", "medium", "small"],
        "additionalProperties": False,
        "properties": {"large": color, "medium": color, "small": color},
    }


def layout_source():
    return themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "天气",
         "styles": {"fontColor": role("primary")}},
    ]}}])


@pytest.mark.parametrize("error_type", [OSError, TimeoutError, ValueError])
def test_selection_never_starts_a_measurement_process(monkeypatch, error_type):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    process = AsyncMock(side_effect=error_type("must not start a renderer"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", process)
    client = SimpleNamespace(generate=AsyncMock(return_value='{"themeId":"gradient-blue"}'))
    source = layout_source()
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x2", "userQuery": "天气"}, client,
    ))
    process.assert_not_called()
    assert audit.get("layoutEvidence", {}).get("deviceGeometryKnown") is False
    assert audit.get("themeId") == "gradient-blue"
    assert themes.foreground_signature(result) == themes.foreground_signature(source)


@pytest.mark.parametrize("error", ["ARTIFACT.INVALID", "ASSET.INVALID", "VISUAL.INVALID"])
def test_final_validation_errors_reapply_gradient_from_original(monkeypatch, error):
    source = layout_source()
    photo = {"id": "test-photo", "kind": "photo", "src": "test-background.jpg"}
    audit = {"theme": photo, "outputSize": "2x2"}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=("photo-result", audit)))
    monkeypatch.setattr(themes, "trace_record", Mock())
    artifact = SimpleNamespace(
        genui=source, meta=SimpleNamespace(generationMode="create"),
        model_copy=Mock(side_effect=lambda **kwargs: SimpleNamespace(
            genui=source, taskSpec={}, cardSpec={"suggestSize": "2x2"}, effectiveCapabilities={},
            model_dump=Mock(return_value={}),
        )),
    )
    validator = SimpleNamespace(validate=Mock(side_effect=[[error], []]))
    result = asyncio.run(themes.theme_artifact(
        artifact, {"size": "2x2", "userQuery": "天气"}, Mock(), validator, {},
    ))
    assert audit.get("finalValidationErrors") == [error]
    assert audit.get("themeId") == "gradient-blue"
    assert audit.get("rejectedTheme") == photo
    assert validator.validate.call_count == 2
    assert "linearGradient" in result.genui
    assert result.taskSpec == {}
    assert themes.foreground_signature(result.genui) == themes.foreground_signature(source)


def test_palette_role_keeps_layout_and_final_color_contracts():
    with layout_phase():
        assert _system_palette_color({"primary": role("primary")}, "primary") == role("primary")
    assert _system_palette_color({"primary": "#FFFFFFFF"}, "primary") == "#FFFFFFFF"
    with pytest.raises(CompactDslConversionError, match="System palette role primary"):
        _system_palette_color({"primary": role("primary")}, "primary")


@pytest.mark.parametrize("region,accepted", [
    ([.25, .25, .5, .5], True),
    ([.25, .25, .5 + 5e-10, .5], True),
    ([.25, .25, .5, .5 + 5e-10], True),
    ([.24, .25, .5, .5], False),
    ([.25, .24, .5, .5], False),
    ([.25, .25, .5 + 2e-9, .5], False),
    ([.25, .25, .5, .5 + 2e-9], False),
])
def test_subject_regions_preserve_containment_tolerance(region, accepted):
    photo = {"size": "2x2", "business": "weather", "subjectBounds": [.25, .25, .5, .5],
             "subjectRegions": [region]}
    evidence = {"complete": True, "occupied": [{"id": "title", "rect": [0, 0, .1, .1]}]}
    reason = themes._photo_geometry_reason(photo, evidence)
    assert reason == (None if accepted else "主体区域配置无效")


@pytest.mark.parametrize("rect,overlaps", [
    ([0, .25, .25, .25], False),
    ([.75, .25, .25, .25], False),
    ([.25, 0, .25, .25], False),
    ([.25, .75, .25, .25], False),
    ([.001, .25, .25, .25], True),
    ([.749, .25, .25, .25], True),
    ([.25, .001, .25, .25], True),
    ([.25, .749, .25, .25], True),
    ([.3, .3, .1, .1], True),
    ([.1, .1, .8, .8], True),
])
def test_subject_overlap_preserves_touching_edges(rect, overlaps):
    photo = {"size": "2x2", "business": "weather", "subjectBounds": [.25, .25, .5, .5]}
    evidence = {"complete": True, "occupied": [{"id": "title", "rect": rect}]}
    reason = themes._photo_geometry_reason(photo, evidence)
    assert reason == ("主体区域与内容 title 冲突" if overlaps else None)


@pytest.fixture
def expansion_theme(monkeypatch):
    monkeypatch.setattr(expansion, "expansion_gate", lambda task: {
        "eligible": True, "business": "countdown",
    })
    return {"business": "countdown", "sourceSize": "2x2", "size": "2x4",
            "composition": "square-left", "objectFit": "fill",
            "frame": {"slotWidth": 1, "slotHeight": 1, "imageWidth": 1,
                      "imageHeight": 1, "align": "topStart"},
            "subjectBounds": [.5, 0, .5, 1]}


@pytest.mark.parametrize("bounds,accepted", [
    (None, False),
    ([], False),
    ([.5, 0, .5], False),
    ([.5, 0, 0, 1], False),
    ([.5, 0, float("inf"), 1], False),
    ([.5, 0, .5, 1], True),
    ([.6, .1, .3, .8], True),
    ([.499, 0, .5, 1], False),
    ([.5, -.001, .5, 1], False),
    ([.5, 0, .501, 1], False),
    ([.5, 0, .5, 1.001], False),
])
def test_expansion_subject_stays_in_right_half(expansion_theme, bounds, accepted):
    expansion_theme["subjectBounds"] = bounds
    evidence = {"complete": True, "occupied": [{"id": "title", "rect": [0, 0, 1, 1]}]}
    reason = expansion._expansion_geometry_reason(expansion_theme, evidence)
    assert reason == (None if accepted else "图片主体侵入左侧内容半区")


@pytest.mark.parametrize("rect,accepted", [
    ([0, 0, 1, 1], True),
    ([.1, .1, .8, .8], True),
    ([-.001, 0, 1, 1], False),
    ([0, -.001, 1, 1], False),
    ([0, 0, 1.001, 1], False),
    ([0, 0, 1, 1.001], False),
])
def test_expansion_content_stays_in_original_square(expansion_theme, rect, accepted):
    evidence = {"complete": True, "occupied": [{"id": "title", "rect": rect}]}
    reason = expansion._expansion_geometry_reason(expansion_theme, evidence)
    assert reason == (None if accepted else "原内容及动态预留超出2x2安全范围")
