"""本地渲染转换接口与云侧转换器的一致性。"""

import json
from types import SimpleNamespace

import pytest
from debug_tools.end_to_end_debug.backend.debug_agent.config import DebugSettings
from debug_tools.end_to_end_debug.backend.server import create_app
from debug_tools.static_site import create_frontend_app
from fastapi.testclient import TestClient

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui

SOURCE = '\n'.join(
    (
        '["root","Column",{"width":"matchParent","height":"matchParent"},["cta"]]',
        '["cta","PillButton",{"label":"打开省电模式",'
        '"icon":"resources/base/media/battery_leaf_fill.svg",'
        '"actionSurface":"#331F4799","actionInk":"#FF1F4799",'
        '"onClick":[{"call":"clickToIntent","args":{}}]}]',
        '["/data/phoneBattery/batterySOC",68]',
    )
)


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
    assert result.get("genui") == convert_compact_dsl_to_a2ui(SOURCE, size=resolved_size)


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
