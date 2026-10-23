"""图片主题固定构图、完整按钮避让和冻结前景合同。"""

import hashlib
from pathlib import Path

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.square_photo_expansion import expand_square, expansion_gate
from services.subjectless_wide_theme import wide_gate
from services.theme_content_regions import button_ids
from services.theme_style_roles import role
from theme_photo_samples import expansion_photo


@pytest.fixture
def enabled(monkeypatch):
    settings = get_settings()
    for flag in ("enable_photo_background_theme",
                 "enable_square_photo_expansion", "enable_subjectless_wide_theme"):
        monkeypatch.setattr(settings, flag, True)
    return settings


def task_for(size, query="倒计时"):
    return {"size": size, "userQuery": query, "dataModelSchema": {"data": {
        "countdown" if size == "2x2" else "phoneBattery": {"value": {"type": "integer"}},
    }}}


@pytest.mark.parametrize("size,gate", [("2x2", expansion_gate), ("2x4", wide_gate)])
def test_retained_features_do_not_trigger_without_enabled_assets(enabled, size, gate):
    for number in range(30):
        task = task_for(size, f"查看倒计时 {number}")
        first = gate(task)
        assert first == gate(task)
        assert first.get("eligible") is False
        assert "没有启用" in first.get("reason", "")
        assert "sampleRate" not in first and "bucket" not in first


@pytest.mark.parametrize("query", ["保持2x2", "不要扩展", "保留原尺寸", "纯色倒计时", "不要背景图"])
def test_user_size_and_theme_requests_prevent_expansion(enabled, query):
    assert expansion_gate(task_for("2x2", query)).get("eligible") is False


@pytest.mark.parametrize("size,gate", [("2x2", wide_gate), ("2x4", expansion_gate)])
def test_photo_gates_do_not_cross_size_pools(enabled, size, gate):
    assert gate(task_for(size)).get("eligible") is False


def test_current_subject_and_texture_assets_are_active_and_present():
    root = Path(__file__).resolve().parents[2]
    expected = {"photos": 13, "texturePhotos": 15,
                "subjectlessWidePhotos": 0, "squareExpansions": 0}
    for key, count in expected.items():
        entries = themes.registered_themes(key)
        assert isinstance(entries, list) and len(entries) == count
        for entry in entries:
            src = entry.get("src")
            assert isinstance(src, str) and src.startswith("resources/base/media/")
            assert (root / src).is_file()
    assert all(p.get("id", "").startswith("photo-ux-")
               for p in themes.registered_themes("photos"))
    photos = themes.registered_themes("photos", include_disabled=True)
    photos.extend(themes.registered_themes("texturePhotos", include_disabled=True))
    expected_paths = {root / entry.get("src") for entry in photos}
    assert set((root / "resources/base/media").glob("bg_*")) == expected_paths


@pytest.mark.parametrize("entry", [
    *themes.registered_themes("photos", include_disabled=True),
    *themes.registered_themes("texturePhotos", include_disabled=True),
], ids=lambda entry: entry.get("id"))
def test_photo_assets_match_delivery_hash_and_preserve_source_record(entry):
    src = entry.get("src")
    assert isinstance(src, str)
    payload = (Path(__file__).resolve().parents[2] / src).read_bytes()
    assert payload.startswith(b"\xff\xd8\xff")
    metadata = entry.get("source", {})
    assert hashlib.sha256(payload).hexdigest() == metadata.get("assetSha256")
    assert len(payload) == metadata.get("assetBytes")
    original_hash = metadata.get("sourceSha256")
    assert isinstance(original_hash, str)
    assert len(original_hash) == 64
    assert metadata.get("originalSize")
    assert metadata.get("assetSize")


def test_capsules_and_round_buttons_both_occupy_the_whole_area():
    def node(identity, width):
        return {"id": identity, "component": "Button", "onClick": [{"call": "open"}],
                "styles": {"width": width, "height": 30, "borderRadius": 15}}

    assert button_ids([node("pill", 120), node("circle", 30)]) == ["pill", "circle"]


def test_subject_avoidance_cannot_use_legacy_capsule_exemptions():
    photo = {"size": "2x2", "business": "weather", "subjectBounds": [.6, .1, .4, .6]}
    content = {"id": "title", "rect": [.1, .1, .3, .1]}
    capsule = {"id": "pill_text", "rect": [.1, .5, .8, .2]}
    evidence = {"complete": True, "occupied": [content, capsule], "subjectAvoidance": [content]}
    assert "冲突" in themes._photo_geometry_reason(photo, evidence)
    changed = {**evidence, "subjectAvoidance": [capsule]}
    assert "冲突" in themes._photo_geometry_reason(photo, changed)
    assert themes._photo_geometry_reason(photo, {**evidence, "complete": False}) is not None


def test_expansion_only_adds_half_width_wrapper_and_background():
    photo = expansion_photo()
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": {"path": "/data/countdown/value"},
         "styles": {"fontColor": role("primary"), "fontSize": 24}},
    ]}}])
    result = expand_square(source, photo, task_for("2x2"))
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    nodes = themes.components(themes.decode(result))
    half = next(node for node in nodes if node.get("id") == themes.PREFIX + "contentHalf")
    assert half.get("styles", {}).get("width") == "50%"
    title = next(node for node in nodes if node.get("id") == "title")
    assert title.get("content") == {"path": "/data/countdown/value"}
    assert title.get("styles", {}).get("fontSize") == 24
