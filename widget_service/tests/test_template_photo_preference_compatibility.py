"""模板旧字符串入口与 Fusion 结构化偏好共存，应用导入不依赖已移除接口。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_websocket_app_imports_with_both_generation_routes():
    cloud = Path(__file__).resolve().parents[1] / "cloud"
    environment = os.environ.copy()
    python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(cloud), python_path] if python_path else [str(cloud)],
    )
    source = (
        "from start_websocket_server import app; "
        "from services.template_generation import TemplateSourceGenerator; "
        "from services import post_layout_theme; "
        "assert any(getattr(route, 'path', None) == '/health' for route in app.routes); "
        "assert not hasattr(post_layout_theme, 'user_color_overrides'); "
        "assert callable(post_layout_theme.theme_artifact)"
    )
    process = subprocess.run(
        [sys.executable, "-c", source], env=environment, cwd=cloud,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
        check=False,
    )
    assert process.returncode == 0, process.stderr


@pytest.mark.parametrize("query,expected", [
    ("天气卡，背景红色", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("天气卡，白色的背景", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("文字用黑色", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("绿色字体", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("背景用#267A63", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("#FF7045B9字色", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("底色：#267a63", "用户明确颜色优先，本轮使用固定底色/渐变"),
    ("不要图片，文字用黑色", "用户明确其它主题或不要图片"),
    ("纯色天气卡", "用户明确其它主题或不要图片"),
    ("渐变天气卡", "用户明确其它主题或不要图片"),
    ("融球天气卡", "用户明确其它主题或不要图片"),
    ("不用背景图片", "用户明确其它主题或不要图片"),
    ("无背景图", "用户明确其它主题或不要图片"),
    ("显示天气和空气质量", None),
    ("显示红色预警信息", None),
    ("", None),
])
def test_template_preference_keeps_existing_decisions(query, expected):
    from services.template_generation.engine.cardplan.photo_preference import (
        photo_preference_reason,
    )

    assert photo_preference_reason(query) == expected


def test_template_preference_reads_configured_color_names(monkeypatch):
    from services.template_generation.engine.cardplan import photo_preference

    monkeypatch.setattr(photo_preference, "load_theme_registry", lambda: {
        "userColorOverrides": {"namedColors": {"自定义色": "#FF267A63"}},
    })
    assert photo_preference.photo_preference_reason("背景用自定义色") is not None
    assert photo_preference.photo_preference_reason("说明中提到自定义色") is None
