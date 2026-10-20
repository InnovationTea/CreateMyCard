"""本地渲染转换接口与云侧转换器的一致性。"""

import json
import re
from types import SimpleNamespace

import pytest
from debug_tools.end_to_end_debug.backend.debug_agent.config import DebugSettings
from debug_tools.end_to_end_debug.backend.server import create_app
from debug_tools.static_site import create_frontend_app
from fastapi.testclient import TestClient

from services import fusion_ball_expander
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.post_layout_theme import apply_theme, components, decode
from services.post_layout_theme_registry import fallback_theme
from services.theme_selection_policy import default_palette_family
from services.theme_style_roles import layout_phase

SOURCE = '\n'.join(
    (
        '["root","Column",{"width":"matchParent","height":"matchParent"},["cta"]]',
        '["cta","PillButton",{"label":"打开省电模式",'
        '"icon":"resources/base/media/battery_leaf_fill.svg",'
        '"onClick":[{"call":"clickToIntent","args":{}}]}]',
        '["/data/phoneBattery/batterySOC",68]',
    )
)


def _expected_themed_conversion(source: str, size: str, app_version: str | None = None) -> str:
    roots = sorted(set(re.findall(r"/data/([^/}\s\"'+]+)", source)))
    task = {
        "size": size,
        "appVersion": app_version,
        "userQuery": "",
        "dataModelSchema": {"data": {root: {} for root in roots}},
    }
    with layout_phase(task=task):
        converted = convert_compact_dsl_to_a2ui(
            source,
            size=size,
            protocol_profile={"version": "v0.9", "appVersion": app_version},
        )
    family = default_palette_family(task)
    return apply_theme(converted, fallback_theme(family), task, {})


@pytest.fixture(params=["frontend", "full"])
def client(request):
    if request.param == "frontend":
        app = create_frontend_app()
    else:
        app = create_app(DebugSettings(), production_settings=SimpleNamespace())
    return TestClient(app)


@pytest.mark.parametrize("size", ["auto", "2x2", "2x4"])
def test_conversion_matches_cloud_converter(client, size):
    response = client.post("/debug/renderer/convert", json={"source": SOURCE, "size": size})
    assert response.status_code == 200
    result = response.json()
    resolved_size = "2x2" if size == "auto" else size
    assert result.get("size") == resolved_size
    assert result.get("genui") == _expected_themed_conversion(SOURCE, resolved_size)


def test_auto_size_detects_wide_card(client):
    source = '["root","Column",{"width":300},["text"]]\n'
    source += '["text","Text",{"content":"宽卡"}]'
    response = client.post("/debug/renderer/convert", json={"source": source})
    assert response.status_code == 200
    result = response.json()
    assert result.get("size") == "2x4"
    genui = result.get("genui")
    assert isinstance(genui, str)
    assert len([json.loads(line) for line in genui.splitlines()]) == 3


@pytest.mark.parametrize("size,layout", [("2x2", "S-title-content"),
                                        ("2x4", "W-split-panels")])
def test_auto_size_detects_semantic_layout_before_expansion(client, size, layout):
    children = ["title", "value"] if size == "2x2" else ["left", "right"]
    rows = [["root", "Layout", {"layout": layout}, children],
            ["title", "SingleLineTitle", {"title": "状态", "fontSize": 12}],
            ["value", "EmphasisText", {"mainText": "正常", "fontSize": 18}]]
    if size == "2x4":
        rows.extend([
            ["left", "Region", {"variant": "title-content"}, ["title", "value"]],
            ["right", "Region", {"variant": "center"}, ["other"]],
            ["other", "EmphasisText", {"mainText": "在线", "fontSize": 18}],
        ])
    source = "\n".join(json.dumps(row) for row in rows)
    response = client.post("/debug/renderer/convert", json={"source": source, "size": "auto"})
    assert response.status_code == 200
    assert response.json().get("size") == size
    assert response.json().get("genui") == _expected_themed_conversion(source, size)


@pytest.mark.parametrize(
    "data_root,expected_colors",
    [
        ("weather", [["#FFCBDDFE", 0], ["#FFF1F6FE", 1]]),
        ("healthSport", [["#FFDBCCFF", 0], ["#FFF6F2FF", 1]]),
    ],
)
def test_conversion_applies_registered_preview_theme(client, data_root, expected_colors):
    source = '\n'.join(
        (
            '["root","Column",{"width":"matchParent","height":"matchParent"},["value"]]',
            '["value","EmphasisText",{"mainText":{"path":"/data/'
            + data_root
            + '/value"},"fontSize":18}]',
            '["/data/' + data_root + '/value","正常"]',
        )
    )

    response = client.post("/debug/renderer/convert", json={"source": source, "size": "2x4"})

    assert response.status_code == 200
    nodes = components(decode(response.json()["genui"]))
    root = next(node for node in nodes if node.get("id") == "root")
    assert root.get("styles", {}).get("linearGradient", {}).get("colors") == expected_colors


def test_conversion_preserves_explicit_compact_theme(client):
    source = '\n'.join(
        (
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"backgroundColor":"#FFFFFFFF"},["value"]]',
            '["value","Text",{"content":"显式白色背景"}]',
        )
    )

    response = client.post("/debug/renderer/convert", json={"source": source, "size": "2x2"})

    assert response.status_code == 200
    assert response.json().get("genui") == convert_compact_dsl_to_a2ui(source, size="2x2")


def test_single_line_title_svg_without_fill_color_renders(client):
    source = '\n'.join(
        (
            '["root","Column",{"width":"matchParent","height":"matchParent"},["header"]]',
            '["header","SingleLineTitle",{"title":"活动安排",'
            '"icon":"resources/base/media/figure_run.svg","fontSize":12,'
            '"width":"matchParent"}]',
        )
    )

    response = client.post(
        "/debug/renderer/convert",
        json={"source": source, "size": "2x2"},
    )

    assert response.status_code == 200
    genui = response.json().get("genui")
    assert isinstance(genui, str)
    assert '"fillColor":"#FF1F4799"' in genui


@pytest.mark.parametrize(
    "payload",
    [
        {"source": "invalid"},
        {"source": ""},
        {"source": SOURCE, "size": "3x3"},
        {"source": SOURCE, "extra": True},
    ],
)
def test_invalid_conversion_is_rejected(client, payload):
    response = client.post("/debug/renderer/convert", json=payload)
    assert response.status_code == 422
    assert response.json().get("detail")


@pytest.mark.parametrize("version", [None, "11.0.0.0", "invalid", "", "12.0.0.1"])
def test_client_version_preserves_fusion_gate(client, monkeypatch, version):
    monkeypatch.setattr(
        fusion_ball_expander,
        "get_settings",
        lambda: SimpleNamespace(CONFIG={"fusion_ball_min_prd_version": "11.7.5.206"}),
    )
    source = '["root","Column",{"design":"fusion-ball-schedule-warm"},["title"]]\n'
    source += '["title","Text",{"content":"日程"}]'
    response = client.post(
        "/debug/renderer/convert",
        json={"source": source, "size": "2x2", "appVersion": version},
    )
    assert response.status_code == 200
    genui = response.json().get("genui")
    assert isinstance(genui, str)
    expected = convert_compact_dsl_to_a2ui(
        source, size="2x2", protocol_profile={"version": "v0.9", "appVersion": version}
    )
    assert genui == expected
    assert ("fusionBall" in genui) == (version == "12.0.0.1")
