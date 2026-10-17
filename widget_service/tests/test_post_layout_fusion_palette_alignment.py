"""Fusion copies template background colors, never template trigger rules or content colors."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import role

TEMPLATE_THEMES = (
    Path(__file__).parents[1] / "cloud/services/template_generation/resources/source/themes"
)
TEMPLATE_PAIRS = {
    "fusion-ball-schedule-blue": "fusion-weather-blue",
    "fusion-ball-battery-teal": "fusion-battery-teal",
    "fusion-ball-sleep-violet": "fusion-sleep-violet",
    "fusion-ball-sport-orange": "fusion-sport-orange",
}


@pytest.mark.parametrize("identity,template_id", TEMPLATE_PAIRS.items())
def test_four_fusion_backgrounds_match_template_colors(identity, template_id):
    theme = next(item for item in registered_themes() if item.get("id") == identity)
    template_path = TEMPLATE_THEMES / template_id / "theme.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template_colors = template.get("fusionBallStyle", {})
    expected = {}
    for ball in ("large", "medium", "small"):
        color = template_colors.get(ball + "Color")
        assert color
        expected[ball] = color
    background = theme.get("background", {})
    assert background.get("ballColors") == expected
    assert background.get("glassColor") == "#0DFFFFFF"
    assert background.get("blurRadius") == 210
    assert background.get("shellColor") == "#00000000"
    assert theme.get("content", {}).get("roles", {}).get("primary") == "#FFFFFFFF"
    assert theme.get("content", {}).get("panelBySize") == {"2x2": "#33FFFFFF"}


def test_only_four_fusion_themes_are_available():
    identities = {theme.get("id") for theme in registered_themes("standard")
                  if theme.get("kind") == "fusion"}
    assert identities == set(TEMPLATE_PAIRS)
    rules = themes.original_selection_rules()
    assert "fusion-ball-schedule-cool" not in rules
    assert "fusion-ball-schedule-warm" not in rules


@pytest.mark.parametrize("identity", ["fusion-ball-schedule-cool", "fusion-ball-schedule-warm"])
def test_retired_theme_ids_cannot_be_selected(monkeypatch, identity):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": "Meeting",
         "styles": {"fontColor": role("primary")}},
    ]}}])
    _, audit = asyncio.run(themes.select_theme(source, {"size": "2x2"}, client))
    assert audit.get("themeId") == "gradient-blue"
    assert audit.get("selectorError")
    assert identity not in audit.get("candidates", [])
