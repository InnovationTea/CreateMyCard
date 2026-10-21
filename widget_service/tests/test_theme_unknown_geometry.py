"""Cloud themes must not infer host pixels from logical card sizes."""

import ast
import asyncio
import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import square_photo_expansion as expansion
from services.theme_content_regions import photo_layout_evidence
from theme_photo_samples import expansion_photo, protected_photo


def source_nodes():
    return [
        {"id": "root", "component": "Column", "children": ["title", "action"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "sleep", "styles": {}},
        {"id": "action", "component": "Stack", "children": ["icon"],
         "onClick": ["open"], "styles": {}},
        {"id": "icon", "component": "Image", "src": "resources/base/media/alarm_fill_1.svg",
         "styles": {}},
    ]


def test_layout_evidence_reports_unknown_geometry_and_complete_buttons():
    evidence = photo_layout_evidence(source_nodes())
    assert evidence.pop("textFlow").get("root", {}).get("maxLines") is None
    assert evidence == {
        "basis": "layout-only", "complete": True, "reason": None,
        "contentIds": ["title", "icon"], "buttonIds": ["action"], "deviceGeometryKnown": False,
        "sideBySidePanels": False,
        "panelIds": [],
        "nonTextIds": ["icon"], "nonTextAncestors": {"icon": ["action", "root"]},
    }
    for key in ("viewport", "responsive", "occupied", "width", "height"):
        assert key not in evidence


@pytest.mark.parametrize("axis,value", [
    ("width", 183), ("height", 197), ("width", None), ("height", "wrapContent"),
])
def test_layout_evidence_does_not_treat_fixed_or_unknown_roots_as_adaptive(axis, value):
    nodes = source_nodes()
    nodes[0].get("styles", {})[axis] = value
    assert photo_layout_evidence(nodes).get("complete") is False


def test_empty_layout_is_not_enough_for_a_photo():
    assert photo_layout_evidence([]).get("complete") is False
    assert photo_layout_evidence(source_nodes()[:1]).get("complete") is False


@pytest.mark.parametrize("setting", ["viewports", "viewport", "width", "height", "referenceSize"])
def test_registry_rejects_pixel_matching_configuration(setting):
    config = registry.load_theme_registry()
    config.get("matching", {})[setting] = {"width": 183, "height": 197}
    with pytest.raises(ValueError, match="matching"):
        registry.validate_registry(config)


@pytest.mark.parametrize("module", [themes, registry, expansion])
def test_theme_runtime_has_no_default_card_pixel_sizes(module):
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            assert node.value not in {150, 176, 300, 400}
    assert "post_layout_measure_command" not in type(get_settings()).model_fields


def test_protected_photo_is_rejected_even_if_model_selects_it(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    original_registry = themes.registered_themes

    def with_test_photo(pool, **kwargs):
        if pool == "photos":
            return [protected_photo()]
        return original_registry(pool, **kwargs)

    monkeypatch.setattr(themes, "registered_themes", with_test_photo)
    source = themes.encode([{"updateComponents": {"components": source_nodes()}}])
    client = SimpleNamespace(generate=AsyncMock(
        return_value='{"themeId":"test-protected-weather"}'))
    result, audit = asyncio.run(themes.select_theme(
        source, {"size": "2x2", "userQuery": "天气"}, client))
    assert audit.get("themeId") == "gradient-blue"
    assert "图片缺少统一准入配置" in audit.get("rejected", {}).get("test-protected-weather", "")
    assert themes.foreground_signature(result) == themes.foreground_signature(source)
    payload = json.loads(client.generate.call_args.args[0][1].get("content"))
    assert payload.get("eligiblePhotos") == []


def test_retained_expansion_does_not_infer_or_double_surface_pixels():
    source = themes.encode([
        {"createSurface": {"surfaceId": "test"}},
        {"updateComponents": {"components": source_nodes()}},
    ])
    result = expansion.expand_square(source, expansion_photo(), {"size": "2x2"})
    assert themes.decode(result)[0] == themes.decode(source)[0]
    assert themes.foreground_signature(result) == themes.foreground_signature(source)
    shell = next(node for node in themes.components(themes.decode(result))
                 if node.get("id") == "root")
    assert shell.get("styles", {}).get("width") == "matchParent"
    assert shell.get("styles", {}).get("height") == "matchParent"


@pytest.mark.parametrize("basis", [
    "layout-only", "explicit-test-viewport", "device-independent-proof",
])
def test_retained_expansion_cannot_use_fabricated_measurement_evidence(monkeypatch, basis):
    monkeypatch.setattr(expansion, "expansion_gate", lambda task: {
        "eligible": True, "business": "countdown",
    })
    theme = expansion_photo()
    evidence = {"basis": basis, "complete": True, "occupied": [
        {"id": "title", "rect": [.1, .1, .2, .2]},
    ]}
    reason = expansion.expansion_reason(theme, {"size": "2x2"}, evidence)
    assert reason is not None and "真实卡片宽高未知" in reason
