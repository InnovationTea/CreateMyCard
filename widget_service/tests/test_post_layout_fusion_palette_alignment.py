"""Fusion copies template background colors, never template trigger rules or content colors."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import role

# The approved cb5904d2 palette is copied, not a live dependency on template changes.
APPROVED_BACKGROUNDS = {
    "fusion-ball-schedule-blue": ("#FF1F1F99", "#FF2B65D9", "#FF57AED9"),
    "fusion-ball-battery-teal": ("#FF1F9985", "#FF24B3B3", "#FF5AB38E"),
    "fusion-ball-sleep-violet": ("#FF493D99", "#FF5536B3", "#FF7D6B99"),
    "fusion-ball-sport-orange": ("#FFF24131", "#FFFF8833", "#FFE68073"),
}


@pytest.mark.parametrize("identity,colors", APPROVED_BACKGROUNDS.items())
def test_four_fusion_backgrounds_keep_approved_snapshot_colors(identity, colors):
    theme = next(item for item in registered_themes() if item.get("id") == identity)
    large, medium, small = colors
    expected = {"large": large, "medium": medium, "small": small}
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
    assert identities == set(APPROVED_BACKGROUNDS)
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
