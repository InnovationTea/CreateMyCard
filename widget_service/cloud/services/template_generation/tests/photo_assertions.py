"""图片开关双态断言：观察真实后处理，不替换匹配、选择或模型结果。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from config.config import get_settings
from services.fusion_ball_expander import fusion_ball_enabled
from services.post_layout_theme_registry import photo_fallback, registered_themes
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.compiler import HybridCompilation
from services.template_generation.engine.pipeline import TemplateEngineOutput
from services.theme_photo_processing import template_foreground


@dataclass(frozen=True)
class PhotoApplication:
    before: str
    after: str
    theme_id: str


@dataclass
class TemplatePhotoCapture:
    calls: list[PhotoApplication] = field(default_factory=list)

    def assert_output(self, output: TemplateEngineOutput, *, expect_photo: bool) -> dict | None:
        assert self.calls, "必须经过实际图片后处理入口"
        application = self.calls[-1]
        assert application.after == output.a2ui
        assert application.theme_id == output.theme_id
        assert template_foreground(application.before) == template_foreground(application.after)
        photo: dict | None = None
        if expect_photo:
            photo = _assert_registered_photo(output)
        else:
            assert application.after == application.before
            assert '"__post_theme_base"' not in output.a2ui
        return photo


def capture_template_photos(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool,
) -> TemplatePhotoCapture:
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    actual_finalize = pipeline.finalize_template_photo
    capture = TemplatePhotoCapture()

    def observe(original: HybridCompilation, **options: Any) -> tuple[HybridCompilation, str]:
        result, theme_id = actual_finalize(original, **options)
        capture.calls.append(PhotoApplication(original.a2ui, result.a2ui, theme_id))
        return result, theme_id

    monkeypatch.setattr(pipeline, "finalize_template_photo", observe)
    return capture


def _assert_registered_photo(output: TemplateEngineOutput) -> dict:
    photo = next((item for item in registered_themes() if item.get("id") == output.theme_id), None)
    assert photo is not None and photo.get("kind") == "photo"
    nodes = []
    for line in output.a2ui.splitlines():
        nodes.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    by_id = {node.get("id"): node for node in nodes}
    assert len(by_id) == len(nodes), "背景不得引入重复节点ID"
    root = by_id.get("root")
    layer = by_id.get("__post_theme_background")
    image = by_id.get("__post_theme_base")
    assert root is not None and layer is not None and image is not None
    assert root.get("children") == ["__post_theme_background", "template_root"]
    assert layer.get("component") == "Stack"
    assert image.get("component") == "Image"
    address = photo.get("remoteUrl") or photo.get("src")
    assert image.get("src") == address
    requested_sources = []
    for asset in output.projected_task_spec.assetCandidates:
        requested_sources.append(asset.get("src"))
    assert address in [*output.trusted_internal_asset_sources, *requested_sources]
    assert image.get("styles", {}).get("width") == "matchParent"
    assert image.get("styles", {}).get("height") == "matchParent"
    fallback = photo_fallback(photo.get("content", {}).get("roles", {}).get("primary"))
    background = fallback.get("background", {})
    styles = root.get("styles", {})
    expected_children = ["__post_theme_base"]
    if fallback.get("kind") == "fusion":
        ball_colors = background.get("ballColors", {})
        assert styles.get("backgroundColor") == ball_colors.get("large")
        assert "linearGradient" not in styles
        if fusion_ball_enabled(output.projected_task_spec.appVersion):
            expected_children.insert(0, "fusionBallBackground")
            for size in ("large", "medium", "small"):
                ball = by_id.get("fusionBall" + size.capitalize())
                assert ball is not None
                assert ball.get("styles", {}).get("backgroundColor") == ball_colors.get(size)
    else:
        gradient_colors = background.get("colors", [])
        assert len(gradient_colors) == 2
        assert styles.get("backgroundColor") == gradient_colors[-1]
        assert styles.get("linearGradient", {}).get("colors") == [
            [gradient_colors[0], 0], [gradient_colors[1], 1],
        ]
    assert layer.get("children") == expected_children
    return photo
