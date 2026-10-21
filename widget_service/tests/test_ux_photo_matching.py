"""UX 图片不猜测真实宽高；无主体按布局匹配，有主体保守回退。"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services import square_photo_expansion, subjectless_wide_theme
from services.theme_content_regions import button_ids, photo_layout_evidence
from theme_photo_samples import expansion_photo

SPORT_LAYOUT = '\n'.join([
    '["root","Layout",{"layout":"W-content-side-slots"},["main","upper","lower"]]',
    '["main","Region",{"variant":"title-content"},["heading","value"]]',
    '["heading","SingleLineTitle",{"title":"最近跑步"}]',
    '["value","EmphasizedData",{"value":{"path":"/data/healthSport/exerciseDurationText"}}]',
    '["upper","InfoBlock",{"variant":"slot","primaryText":"今日运动"}]',
    '["lower","CardButton",{"label":"锻炼记录"}]',
])
SLEEP_LAYOUT = '\n'.join([
    '["root","Layout",{"layout":"S-title-content"},["header","reading"]]',
    '["header","SingleLineTitle",{"title":"睡眠"}]',
    '["reading","EmphasisText",{"mainText":{"path":"/data/healthSport/sleepStatus"}}]',
])


def sleep_task(query="睡眠"):
    return {"size": "2x2", "userQuery": query,
            "dataModelSchema": {"data": {"healthSport": {"sleepStatus": {"type": "string"}}}}}


def sleep_nodes():
    return [
        {"id": "root", "component": "Column", "children": ["header", "reading"],
         "styles": {"width": "matchParent", "height": "matchParent", "alignItems": "start"}},
        {"id": "header", "component": "Text", "content": "睡眠",
         "styles": {"maxLines": 1, "textAlign": "start"}},
        {"id": "reading", "component": "Text", "content": "{{ ${/data/healthSport/sleepStatus} }}",
         "styles": {"maxLines": 1, "textAlign": "start"}},
    ]


def ux(identity):
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == "photo-ux-" + identity)


def evidence(size, rects):
    return {"basis": "layout-only", "complete": True, "deviceGeometryKnown": False,
            "contentIds": [str(index) for index in range(len(rects))],
            "textFlow": photo_layout_evidence(sleep_nodes()).get("textFlow"),
            "occupied": [{"id": str(index), "rect": rect} for index, rect in enumerate(rects)]}


@pytest.mark.parametrize("basis", [None, "production-web-renderer", "explicit-test-viewport"])
def test_test_viewports_cannot_authorize_runtime_photos(basis):
    measured = evidence("2x4", [[.1, .1, .2, .2]])
    measured["basis"] = basis
    assert themes.photo_reason(ux("sport-center-wide"),
                               {"size": "2x4", "userQuery": "运动"}, measured,
                               final_layout=SPORT_LAYOUT) is not None


def test_noninteractive_panels_remain_empty_but_clickable_cards_are_content():
    nodes = [{"id": "root", "component": "Column", "onClick": ["open"]},
             {"id": "panel", "component": "Column"},
             {"id": "card", "component": "Row", "onClick": ["open"]},
             {"id": "button", "component": "Button"}]
    assert button_ids(nodes) == ["card", "button"]


def test_expansion_geometry_diagnostics_check_all_supplied_samples():
    before = evidence("2x2", [[.1, .1, .3, .2]])
    before["responsive"] = [copy.deepcopy(before)]
    after = copy.deepcopy(before)
    for view in [before, *before.get("responsive", [])]:
        view["visible"] = [{"id": "text", "text": "ok", "rect": [.1, .1, .3, .2]}]
    for view in [after, *after.get("responsive", [])]:
        view["occupied"] = [{"id": "0", "rect": [.05, .1, .15, .2]}]
        view["visible"] = [{"id": "text", "text": "ok", "rect": [.05, .1, .15, .2]}]
    assert square_photo_expansion.same_square_geometry(before, after)
    after.get("responsive", [])[0].get("visible", [])[0]["rect"] = [.05, .2, .15, .2]
    assert not square_photo_expansion.same_square_geometry(before, after)


@pytest.mark.parametrize("photo", registry.registered_themes("photos"))
def test_original_assets_are_present_and_fully_adaptive(photo):
    root = Path(__file__).resolve().parents[2]
    src = photo.get("src")
    assert src
    assert hashlib.sha256((root / src).read_bytes()).hexdigest() == (
        photo.get("source", {}).get("assetSha256")
    )
    assert photo.get("objectFit") == "fill"
    assert photo.get("sizes") == [photo.get("size")]
    layers = themes.photo_background(photo)
    for layer in layers:
        if layer.get("component") == "Image":
            assert layer.get("styles") == {
                "width": "matchParent", "height": "matchParent", "objectFit": "fill",
            }


@pytest.mark.parametrize("module,pool,size,data", [
    (square_photo_expansion, "squareExpansions", "2x2", "countdown"),
    (subjectless_wide_theme, "subjectlessWidePhotos", "2x4", "phoneBattery"),
])
def test_retained_feature_gates_no_longer_sample(monkeypatch, module, pool, size, data):
    settings = get_settings()
    for flag in ("enable_photo_background_theme", "enable_square_photo_expansion",
                 "enable_subjectless_wide_theme"):
        monkeypatch.setattr(settings, flag, True)
    photo = expansion_photo()
    if size == "2x4":
        photo.update(pool=pool, composition="subjectless", business="battery")
    entries = [photo]
    monkeypatch.setattr(module, "registered_themes", lambda _pool: entries)
    gate = module.expansion_gate if size == "2x2" else module.wide_gate
    for number in range(100):
        task = {"size": size, "userQuery": f"显示倒计时{number}",
                "dataModelSchema": {"data": {data: {"value": {"type": "integer"}}}}}
        assert gate(task).get("eligible") is True


def sleep_anchor_layout(button="CircleButton"):
    return '\n'.join([
        '["root","Layout",{"layout":"S-title-anchor"},["header","reading","support","action"]]',
        '["header","SingleLineTitle",{"title":"睡眠"}]',
        '["reading","EmphasisText",{"mainText":{"path":"/data/healthSport/sleepStatus"}}]',
        '["support","SecondaryBody",{"items":[{"value":"昨晚"}]}]',
        json.dumps(["action", button, {"icon": "resources/base/media/alarm_fill_1.svg"}]),
    ])


def sleep_support_layout():
    rows = [json.loads(line) for line in sleep_anchor_layout().splitlines()]
    rows[0][2]["layout"] = "S-title-dual-content"
    rows[0][3].remove("action")
    return '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows[:-1])


@pytest.mark.parametrize("container,limit,expected", [
    ("Row", 1, 1), ("Column", 1, 2), ("Row", 2, 4),
])
def test_text_flow_uses_declared_rows_without_a_device_viewport(container, limit, expected):
    nodes = [
        {"id": "root", "component": container, "children": ["value", "unit"], "styles": {}},
        {"id": "value", "component": "Text", "styles": {"maxLines": limit}},
        {"id": "unit", "component": "Text", "styles": {"maxLines": limit}},
    ]
    flow = photo_layout_evidence(nodes).get("textFlow", {}).get("root", {})
    assert flow.get("maxLines") == expected


@pytest.mark.parametrize("child", ["missing", "root"])
def test_text_flow_missing_or_recursive_nodes_are_unknown(child):
    nodes = [{"id": "root", "component": "Column", "children": [child]}]
    assert photo_layout_evidence(nodes).get("textFlow", {}).get("root", {}).get("maxLines") is None


@pytest.mark.parametrize("change", [
    {"maxTextLines": 0}, {"maxTextLines": "3"}, {"includeTitle": "true"},
    {"layouts": {"S-center": "left"}}, {"viewport": {"width": 123}},
    {"kind": "unknown"}, {"excludeComponents": ["CircleButton"]},
])
def test_invalid_content_eligibility_rejected_at_registry_load(change):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-sleep-square")
    photo.get("contentEligibility", {}).update(change)
    with pytest.raises(ValueError):
        registry.validate_registry(config)
