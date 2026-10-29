"""具体颜色不受有限候选色系量化；Mock仅验证执行，不冒充模型理解验证。"""

import pytest

from services import post_layout_theme as themes
from services import theme_user_preferences as preferences
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import PATHS, choose, sample
from theme_preference_samples import preference, reply


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("color", ["#FFCC0000", "#FF267A63", "#FF7045B9", "#FF2268B4"])
@pytest.mark.parametrize("model_theme", ["gradient-warm", "photo-ux-wave-wide", "unknown"])
def test_specific_background_color_survives_family_choice_and_photo_priority(
    monkeypatch, wide, color, model_theme,
):
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    query = "这张卡使用指定的具体配色，气氛轻松"
    saved.task["userQuery"] = query
    request = preference("backgroundColor", color, query)
    result, audit = choose(saved, monkeypatch, reply([request], model_theme))
    assert audit.get("userPreferences") == [request]
    assert audit.get("userColors", {}).get("background", {}).get("color") == color
    assert audit.get("theme", {}).get("kind") in {"solid", "gradient"}
    assert node_by_id(result, "root").get("styles", {}).get("backgroundColor") == color
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("wide", [False, True])
def test_broad_palette_and_specific_text_color_remain_different_targets(monkeypatch, wide):
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "使用柔和暖色底，文字用指定的具体颜色"
    requests = [
        preference("paletteFamily", "warm", "柔和暖色底"),
        preference("textColor", "#FF7045B9", "文字用指定的具体颜色"),
    ]
    result, audit = choose(saved, monkeypatch, reply(requests))
    assert audit.get("theme", {}).get("family") == "warm"
    assert audit.get("userColors", {}).get("background") is None
    assert audit.get("userColors", {}).get("text", {}).get("color") == "#FF7045B9"
    reason = preferences.preference_reason(
        audit.get("theme"), requests, audit.get("userColors"),
    )
    assert reason is None
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
