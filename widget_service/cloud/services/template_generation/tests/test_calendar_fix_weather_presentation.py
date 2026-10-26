"""日程地点与天气概况组合的局部居中及底板规则。"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

import pytest

from services.template_generation.engine.cardplan.calendar_weather_presentation import (
    center_calendar_weather_full,
)
from services.template_generation.engine.cardplan.layout_surface_policy import (
    apply_layout_surface,
    configure_layout_surface,
)
from services.template_generation.engine.cardplan.parser import ParsedCall, parse_ux_layout_card
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.tests.test_calendar_fail_wide_render import _CASES, _compile
from services.template_generation.tests.test_calendar_no_action_template_render import _styles
from services.template_generation.tests.test_calendar_weather_presentation import (
    _column,
    _options,
    _text,
    _texts,
)

_CALENDAR = "ScheduleOverviewTitleLocationHero@1"
_WEATHER = "WeatherOverviewConditionHero@1"
_FLAG = "_calendarConditionFocusSurface"


def _fixture(*, reverse: bool = False, city: bool = False) -> tuple[Nested2Node, ParsedCall]:
    header = "当前城市"
    if city:
        header = "{{ ${data.altWeather.location.prefectureName} || '当前城市' }}"
    weather = _column(
        _column(_text(header)),
        _column(_text("${data.altWeather.current.condition}", color="#FFCCDDFF")),
        _text("当前天气"),
        width="matchParent",
        height="matchParent",
        itemMargin=0,
        alignItems="start",
    )
    calendar = _column(
        _text("日程"),
        _text("${data.altCalendar.events.0.title}"),
        _text("${data.altCalendar.events.0.eventLocation}"),
    )
    names = (_WEATHER, _CALENDAR) if reverse else (_CALENDAR, _WEATHER)
    children = (weather, calendar) if reverse else (calendar, weather)
    body = ",".join(f'Template("{name}",{{}})' for name in names)
    composition = parse_ux_layout_card(f'Template("WideTwoFocusLayout@1",{{}},{body});')
    return Nested2Node("WideTwoFocusLayout", ({},), children), composition


def _surface(color: str = "#33CCEEFF") -> Nested2Node:
    panels = []
    for name in ("calendar", "weather"):
        panels.append(
            _column(
                _text(name),
                layoutWeight=1,
                height="matchParent",
                padding=12,
                backgroundColor=color,
                borderRadius=20,
            )
        )
    return Nested2Node("Row", ({"width": "matchParent", "itemMargin": 8},), tuple(panels))


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("city", [False, True])
def test_exact_pair_centers_three_existing_texts(reverse: bool, city: bool) -> None:
    expanded, composition = _fixture(reverse=reverse, city=city)
    before = copy.deepcopy(expanded)
    result = center_calendar_weather_full(expanded, composition, size="2x4")
    assert expanded == before
    assert result is not expanded
    index = 0 if reverse else 1
    assert result.children[1 - index] is expanded.children[1 - index]
    weather = result.children[index]
    assert _options(weather).get("height") == "matchParent"
    assert _options(weather).get("itemMargin") == 6
    assert _options(weather).get("alignItems") == "center"
    for old, new, height, font, weight in zip(
        _texts(expanded.children[index]),
        weather.children,
        (16, 58, 16),
        (12, 24, 12),
        (500, 700, 400),
        strict=True,
    ):
        assert new.values[0] == old.values[0]
        assert _options(new).get("fontColor") == _options(old).get("fontColor")
        assert _options(new).get("height") == height
        assert _options(new).get("fontSize") == font
        assert _options(new).get("fontWeight") == weight
        assert _options(new).get("textAlign") == "center"
        assert _options(new).get("width") == "matchParent"
        assert _options(new).get("maxLines") == 1
        assert _options(new).get("textOverflow") == "ellipsis"
    assert 16 + 6 + 58 + 6 + 16 == 102


@pytest.mark.parametrize("color", ["#33CCEEFF", "#80112233", "#abcdef"])
def test_only_exact_pair_changes_theme_surface(color: str) -> None:
    expanded, composition = _fixture()
    configured = configure_layout_surface(composition, expanded)
    assert _options(configured).get(_FLAG) is True
    root = _surface(color)
    before = copy.deepcopy(root)
    result = apply_layout_surface(root, "WideTwoFocusLayout", _options(configured))
    assert root == before
    assert _options(result).get("itemMargin") == 12
    for old, panel in zip(root.children, result.children, strict=True):
        assert panel.children is old.children
        options = _options(panel)
        assert options.get("backgroundColor") == "#19" + color[-6:]
        assert options.get("borderRadius") == 12
        assert options.get("padding") == 12
        assert options.get("layoutWeight") == 1
        assert options.get("height") == "matchParent"
    assert (300 - 24 - 12) / 2 - 24 == 108


@pytest.mark.parametrize(
    "case",
    [
        "other-layout",
        "other-calendar",
        "other-weather",
        "direct-layout",
        "third-template",
        "nested-template",
        "temperature",
        "image",
        "button",
        "action",
        "calendar-action",
        "unknown-field",
        "other-root",
        "container-field",
        "decoration",
        "missing-footer",
    ],
)
def test_extra_content_or_other_pairs_keep_weather_and_surface(case: str) -> None:
    expanded, composition = _fixture()
    calendar, weather = expanded.children
    first, second = composition.children
    if case == "other-layout":
        composition = replace(composition, name="WideTwoFullLayout@1")
    elif case == "other-calendar":
        composition = replace(composition, children=(replace(first, name="OtherHero@1"), second))
    elif case == "other-weather":
        composition = replace(composition, children=(first, replace(second, name="OtherHero@1")))
    elif case == "direct-layout":
        composition = replace(composition, kind="component", name="WideTwoFocusLayout")
    elif case == "third-template":
        composition = replace(composition, children=(first, second, first))
    elif case == "nested-template":
        composition = replace(composition, children=(first, replace(second, children=(first,))))
    elif case == "temperature":
        weather = _column(weather, _text("${data.altWeather.current.temperatureC}"))
    elif case in {"image", "button", "decoration"}:
        kind = {"image": "Image", "button": "Button", "decoration": "Divider"}.get(case)
        assert kind is not None
        weather = _column(weather, Nested2Node(kind, ("extra", {}), ()))
    elif case == "action":
        weather = _column(weather, onClick={"id": "view"})
    elif case == "calendar-action":
        calendar = _column(calendar, onClick={"id": "view"})
    elif case in {"unknown-field", "other-root"}:
        path = "data.altWeather.current.airQuality"
        if case == "other-root":
            path = "data.otherWeather.location.prefectureName"
        weather = replace(weather, children=(_text("${" + path + "}"), *weather.children[1:]))
    elif case == "container-field":
        weather = _column(weather, description="${data.altWeather.current.airQuality}")
    else:
        weather = replace(weather, children=weather.children[:2])
    expanded = replace(
        expanded, children=(calendar, weather), values=({"width": "matchParent", _FLAG: True},)
    )
    before = copy.deepcopy(expanded)
    assert center_calendar_weather_full(expanded, composition, size="2x4") is expanded
    configured = configure_layout_surface(composition, expanded)
    assert _FLAG not in _options(configured)
    surface = _surface()
    assert apply_layout_surface(surface, "WideTwoFocusLayout", _options(configured)) is surface
    assert expanded == before


@pytest.mark.parametrize("size", ["2x2", "4x4"])
def test_other_size_keeps_weather(size: str) -> None:
    expanded, composition = _fixture()
    assert center_calendar_weather_full(expanded, composition, size=size) is expanded


@pytest.mark.parametrize("long_text", [False, True])
def test_formal_compiler_uses_centered_weather_and_themed_panels(long_text: bool) -> None:
    case = _CASES[-1]
    registry = CardPlanRegistry(
        enable_fusion_ball=True, enabled_calendar_fallback_template_ids=(case.template_id,)
    )
    components = _compile(case, (), registry, long_text=long_text)
    condition = [
        item
        for item in components.values()
        if "/data/weather/current/condition" in str(item.get("content"))
    ]
    assert len(condition) == 1
    assert _styles(condition[0]).get("fontSize") == 24
    assert _styles(condition[0]).get("height") == 58
    assert _styles(condition[0]).get("textAlign") == "center"
    panels: list[dict[str, Any]] = []
    for item in components.values():
        styles = _styles(item)
        if styles.get("layoutWeight") == 1 and styles.get("padding") == 12:
            panels.append(item)
    assert len(panels) == 2
    for panel in panels:
        assert _styles(panel).get("borderRadius") == 12
        assert str(_styles(panel).get("backgroundColor")).startswith("#19")
    assert all(item.get("component") != "Button" for item in components.values())
    assert not any(_FLAG in str(item) for item in components.values())
