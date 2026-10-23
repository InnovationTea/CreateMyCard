"""小花天气图采用经确认的布局准入，保持其它图片及未知尺寸规则。"""

import json
from types import SimpleNamespace

from services import post_layout_theme_registry as registry

PHOTO_ID = "photo-ux-clouds-weather-square"
WEATHER_PATH = "/data/weather/current/condition"


def photo():
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == PHOTO_ID)


def task():
    return {"size": "2x2", "userQuery": "普通天气卡片",
            "dataModelSchema": {"data": {"weather": {"current": {
                "condition": {"type": "string"},
            }}}}}


def fixture(layout="S-title-content", alignment="start", lines=1, path=WEATHER_PATH):
    actions = {"S-title-anchor": "CircleButton", "S-title-content-action": "PillButton",
               "S-title-primary-secondary-action": "PillButton"}
    children = ["header", "reading"]
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["header", "SingleLineTitle", {"title": "天气"}],
        ["reading", "EmphasisText", {"mainText": {"path": path}}],
    ]
    nodes = [
        {"id": "root", "component": "Column", "children": children,
         "styles": {"width": "matchParent", "height": "matchParent", "alignItems": "start"}},
        {"id": "header", "component": "Text", "content": "天气",
         "styles": {"maxLines": 1}},
        {"id": "reading", "component": "Text", "content": "{{ ${" + path + "} }}",
         "styles": {"maxLines": lines, "textAlign": alignment}},
    ]
    if layout in actions:
        children.append("action")
        rows.append(["action", actions.get(layout), {"label": "查看天气"}])
        nodes.append({"id": "action", "component": "Text", "content": "查看天气",
                      "styles": {"maxLines": 1, "textAlign": "center"}})
    return SimpleNamespace(layout="\n".join(json.dumps(row) for row in rows), nodes=nodes)
