"""CodeCheck 整改不改变异常降级、配色角色和图片边界判断。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import square_photo_expansion as expansion
from services.compact_high_level_components import (
    CompactDslConversionError,
    _system_palette_color,
)
from services.theme_style_roles import layout_phase, role


def layout_source():
    return themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "天气",
         "styles": {"fontColor": role("primary")}},
    ]}}])


@pytest.mark.parametrize("error_type", [OSError, TimeoutError, ValueError])
def test_selection_measurement_errors_keep_gradient_fallback(monkeypatch, error_type):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    monkeypatch.setattr(themes, "measure", AsyncMock(side_effect=error_type("measurement failed")))
    client = SimpleNamespace(generate=AsyncMock(return_value='{"themeId":"gradient-blue"}'))
    source = layout_source()
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x2", "userQuery": "天气"}, client,
    ))
    assert audit.get("measurement") == {"complete": False, "reason": "measurement failed"}
    assert audit.get("themeId") == "gradient-blue"
    assert themes.foreground_signature(result) == themes.foreground_signature(source)


@pytest.mark.parametrize("error_type", [OSError, TimeoutError, ValueError])
def test_final_measurement_errors_reapply_gradient_from_original(monkeypatch, error_type):
    source = layout_source()
    photo = {"id": "test-photo", "kind": "photo", "src": "test-background.jpg"}
    audit = {"theme": photo, "measurement": {"complete": True}, "outputSize": "2x2"}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=("photo-result", audit)))
    monkeypatch.setattr(themes, "measure", AsyncMock(side_effect=error_type("measurement failed")))
    monkeypatch.setattr(themes, "trace_step", Mock())
    artifact = SimpleNamespace(
        genui=source, meta=SimpleNamespace(generationMode="create"),
        model_copy=Mock(side_effect=lambda **kwargs: SimpleNamespace(
            genui=source, taskSpec={}, cardSpec={"suggestSize": "2x2"}, effectiveCapabilities={},
        )),
    )
    validator = SimpleNamespace(validate=Mock(side_effect=[[], []]))
    result = asyncio.run(themes.theme_artifact(
        artifact, {"size": "2x2", "userQuery": "天气"}, Mock(), validator, {},
    ))
    assert audit.get("finalValidationErrors") == ["THEME.MEASUREMENT: measurement failed"]
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
    reason = themes.photo_reason(photo, {"size": "2x2", "userQuery": "天气"}, evidence)
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
    reason = themes.photo_reason(photo, {"size": "2x2", "userQuery": "天气"}, evidence)
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
    reason = expansion.expansion_reason(expansion_theme, {}, evidence)
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
    reason = expansion.expansion_reason(expansion_theme, {}, evidence)
    assert reason == (None if accepted else "原内容及动态预留超出2x2安全范围")
