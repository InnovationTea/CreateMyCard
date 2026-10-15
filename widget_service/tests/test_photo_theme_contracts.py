"""图片主题固定构图、稳定抽样和冻结前景合同。"""

import json
from pathlib import Path

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.square_photo_expansion import expand_square, expansion_gate
from services.subjectless_wide_theme import wide_gate
from services.theme_content_regions import capsule_ids
from services.theme_style_roles import role


@pytest.fixture
def enabled(monkeypatch):
    settings = get_settings()
    for flag in ("enable_post_layout_theme", "enable_photo_background_theme",
                 "enable_square_photo_expansion", "enable_subjectless_wide_theme"):
        monkeypatch.setattr(settings, flag, True)
    monkeypatch.setattr(settings, "square_photo_expansion_sample_rate", .1)
    monkeypatch.setattr(settings, "subjectless_wide_sample_rate", .1)
    return settings


def task_for(size, query="倒计时"):
    return {"size": size, "userQuery": query, "dataModelSchema": {"data": {
        "countdown" if size == "2x2" else "phoneBattery": {"value": {"type": "integer"}},
    }}}


@pytest.mark.parametrize("size,gate", [("2x2", expansion_gate), ("2x4", wide_gate)])
def test_ten_percent_gate_is_stable_and_not_always_on(enabled, size, gate):
    hits = 0
    for number in range(2000):
        task = task_for(size, f"查看倒计时 {number}")
        first = gate(task)
        assert first == gate(task)
        assert first.get("sampleRate") == .1
        assert first.get("eligible") == (first.get("bucket") < 1000)
        hits += int(first.get("eligible"))
    assert 140 < hits < 260


@pytest.mark.parametrize("query", ["保持2x2", "不要扩展", "保留原尺寸", "纯色倒计时", "不要背景图"])
def test_user_size_and_theme_requests_prevent_expansion(enabled, query):
    enabled.square_photo_expansion_sample_rate = 1
    assert expansion_gate(task_for("2x2", query)).get("eligible") is False


@pytest.mark.parametrize("size,gate", [("2x2", wide_gate), ("2x4", expansion_gate)])
def test_photo_gates_do_not_cross_size_pools(enabled, size, gate):
    assert gate(task_for(size)).get("eligible") is False


def test_only_ten_selected_assets_are_active_and_present():
    manifest = json.loads(themes.MANIFEST.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[2]
    expected = {"photos": 4, "subjectlessWidePhotos": 3, "squareExpansions": 3}
    for key, count in expected.items():
        entries = manifest.get(key)
        assert isinstance(entries, list) and len(entries) == count
        for entry in entries:
            src = entry.get("src")
            assert isinstance(src, str) and src.startswith("resources/base/media/")
            assert (root / src).is_file()
    assert {p.get("business") for p in manifest.get("subjectlessWidePhotos")} == {
        "weather", "battery", "sleep",
    }


def test_capsules_are_exempt_but_round_buttons_are_not():
    def node(identity, width):
        return {"id": identity, "component": "Button", "onClick": [{"call": "open"}],
                "styles": {"width": width, "height": 30, "borderRadius": 15}}

    assert capsule_ids([node("pill", 120), node("circle", 30)]) == ["pill"]


def test_subject_avoidance_uses_content_not_capsule_or_full_slots():
    photo = {"size": "2x2", "business": "weather", "subjectBounds": [.6, .1, .4, .6]}
    task = {"size": "2x2", "userQuery": "天气"}
    content = {"id": "title", "rect": [.1, .1, .3, .1]}
    capsule = {"id": "pill_text", "rect": [.1, .5, .8, .2]}
    evidence = {"complete": True, "occupied": [content, capsule], "subjectAvoidance": [content]}
    assert themes.photo_reason(photo, task, evidence) is None
    assert "冲突" in themes.photo_reason(photo, task, {**evidence, "subjectAvoidance": [capsule]})
    assert themes.photo_reason(photo, task, {**evidence, "complete": False}) is not None


def test_expansion_only_adds_half_width_wrapper_and_background():
    manifest = json.loads(themes.MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("squareExpansions")
    assert entries
    source = themes.encode([{"updateComponents": {"components": [
        {"id": "root", "component": "Column", "children": ["title"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "title", "component": "Text", "content": {"path": "/data/countdown/value"},
         "styles": {"fontColor": role("primary"), "fontSize": 24}},
    ]}}])
    result = expand_square(source, {**entries[0], "kind": "photo"}, task_for("2x2"))
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    nodes = themes.components(themes.decode(result))
    half = next(node for node in nodes if node.get("id") == themes.PREFIX + "contentHalf")
    assert half.get("styles", {}).get("width") == "50%"
    title = next(node for node in nodes if node.get("id") == "title")
    assert title.get("content") == {"path": "/data/countdown/value"}
    assert title.get("styles", {}).get("fontSize") == 24
