"""天气居中仅作用于指定日程双 Full 组合，不增减原始内容或绑定。"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

import pytest

from services.template_generation.engine.cardplan.calendar_weather_presentation import (
    center_calendar_weather_full,
)
from services.template_generation.engine.cardplan.parser import ParsedCall, parse_ux_layout_card
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.tests.test_calendar_no_action_template_render import _styles
from services.template_generation.tests.test_calendar_richeng3_no_action_render import (
    _CASES,
    _compile,
)

_WEATHER = "WeatherOverviewFull@1"
_CALENDAR = "ScheduleOverviewDateTitleFull@1"


def _text(content: str, *, color: str = "#99CCDDFF") -> Nested2Node:
    return Nested2Node(
        "Text",
        (content, {"fontColor": color, "fontSize": 12, "fontWeight": 400, "maxLines": 1}),
        (),
    )


def _column(*children: Nested2Node, **options: Any) -> Nested2Node:
    return Nested2Node("Column", (options,), tuple(children))


def _fixture(
    *, reverse: bool = False, city: str = "districtName", pointer: bool = False
) -> tuple[Nested2Node, ParsedCall]:
    paths = (f"location/{city}", "current/temperatureText", "current/condition")
    bindings = []
    for path in paths:
        binding = "/data/alternateWeather/" + path
        if not pointer:
            binding = binding.removeprefix("/").replace("/", ".")
        bindings.append("${" + binding + "}")
    weather = _column(
        _column(_text(bindings[0])),
        Nested2Node("Row", ({"height": 44},), (_text(bindings[1], color="#FFCCDDFF"),)),
        _column(_text("{{ " + bindings[2] + " }}")),
        width="matchParent",
        height="matchParent",
        itemMargin=4,
        justifyContent="spaceBetween",
        alignItems="start",
        clip=True,
    )
    calendar = _column(_text("日程"), _text("${data.calendar.events.0.title}"))
    names = (_CALENDAR, _WEATHER) if reverse else (_WEATHER, _CALENDAR)
    children = (calendar, weather) if reverse else (weather, calendar)
    body = ",".join(f'Template("{name}",{{}})' for name in names)
    composition = parse_ux_layout_card(f'Template("WideTwoFullLayout@1",{{}},{body});')
    return Nested2Node("WideTwoFullLayout", ({},), children), composition


def _texts(node: Nested2Node) -> list[Nested2Node]:
    result = [node] if node.component_type == "Text" else []
    for child in node.children:
        result.extend(_texts(child))
    return result


def _options(node: Nested2Node) -> dict[str, Any]:
    options = next((value for value in node.values if isinstance(value, dict)), None)
    assert isinstance(options, dict)
    return options


@pytest.mark.parametrize("reverse", [False, True], ids=["weather-first", "calendar-first"])
@pytest.mark.parametrize("city", ["districtName", "prefectureName"])
@pytest.mark.parametrize("pointer", [False, True], ids=["dotted", "pointer"])
def test_exact_pair_centers_weather_without_mutating_content(
    reverse: bool, city: str, pointer: bool
) -> None:
    original, composition = _fixture(reverse=reverse, city=city, pointer=pointer)
    before = copy.deepcopy(original)
    result = center_calendar_weather_full(original, composition, size="2x4")
    assert result is not original
    assert original == before
    weather_index = 1 if reverse else 0
    assert result.children[1 - weather_index] is original.children[1 - weather_index]
    weather = result.children[weather_index]
    options = _options(weather)
    assert weather.component_type == "Column"
    assert options.get("height") == 102
    assert options.get("itemMargin") == 6
    assert options.get("alignItems") == "center"
    assert options.get("justifyContent") == "spaceBetween"
    assert 16 + 6 + 58 + 6 + 16 == 102
    old_texts = _texts(original.children[weather_index])
    for old, new, expected in zip(
        old_texts, weather.children, ((16, 12, 500), (58, 38, 700), (16, 12, 400)), strict=True
    ):
        height, font_size, weight = expected
        assert new.values[0] == old.values[0]
        assert _options(new).get("fontColor") == _options(old).get("fontColor")
        assert _options(new).get("height") == height
        assert _options(new).get("fontSize") == font_size
        assert _options(new).get("fontWeight") == weight
        assert _options(new).get("width") == "matchParent"
        assert _options(new).get("textAlign") == "center"
        assert _options(new).get("maxLines") == 1
        assert _options(new).get("textOverflow") == "ellipsis"


@pytest.mark.parametrize("size", ["2x2", "4x4", "1x2"])
def test_other_sizes_are_returned_unchanged(size: str) -> None:
    original, composition = _fixture()
    assert center_calendar_weather_full(original, composition, size=size) is original


@pytest.mark.parametrize(
    "case",
    [
        "other-layout",
        "direct-layout",
        "other-calendar",
        "other-weather",
        "third-template",
        "duplicate-weather",
        "nested-business",
        "single-weather",
        "wrong-expanded-layout",
        "missing-expanded-child",
    ],
)
def test_other_compositions_are_returned_unchanged(case: str) -> None:
    original, composition = _fixture()
    first, second = composition.children
    if case == "other-layout":
        composition = replace(composition, name="WideFullOnlyLayout@1")
    elif case == "direct-layout":
        composition = replace(composition, kind="component", name="WideTwoFullLayout")
    elif case == "other-calendar":
        composition = replace(composition, children=(first, replace(second, name="OtherFull@1")))
    elif case == "other-weather":
        composition = replace(composition, children=(replace(first, name="OtherFull@1"), second))
    elif case == "third-template":
        composition = replace(composition, children=(first, second, first))
    elif case == "duplicate-weather":
        composition = replace(composition, children=(first, first))
    elif case == "nested-business":
        composition = replace(composition, children=(replace(first, children=(second,)), second))
    elif case == "single-weather":
        composition = replace(composition, name="SingleFocusLayout@1", children=(first,))
        original = replace(
            original, component_type="SingleFocusLayout", children=original.children[:1]
        )
    elif case == "wrong-expanded-layout":
        original = replace(original, component_type="WideFullOnlyLayout")
    else:
        original = replace(original, children=original.children[:1])
    assert center_calendar_weather_full(original, composition, size="2x4") is original


@pytest.mark.parametrize(
    "case",
    [
        "extra-binding",
        "both-cities",
        "repeated-binding",
        "other-root",
        "static-city",
        "missing-text",
        "extra-text",
        "image",
        "button",
        "action",
        "container-binding",
        "decoration",
        "calendar-image",
        "calendar-action",
    ],
)
def test_extra_content_or_actions_are_returned_unchanged(case: str) -> None:
    original, composition = _fixture()
    weather, calendar = original.children
    texts = _texts(weather)
    if case == "extra-binding":
        texts[2] = _text(str(texts[2].values[0]) + " ${data.alternateWeather.current.airQuality}")
    elif case == "both-cities":
        texts[0] = _text(
            str(texts[0].values[0]) + " ${data.alternateWeather.location.prefectureName}"
        )
    elif case == "repeated-binding":
        texts[2] = _text(str(texts[2].values[0]) * 2)
    elif case == "other-root":
        texts[1] = _text("${data.otherWeather.current.temperatureText}")
    elif case == "static-city":
        texts[0] = _text("当前城市")
    elif case == "missing-text":
        texts.pop()
    elif case == "extra-text":
        texts.append(_text("其它天气详情"))
    elif case == "image":
        texts.append(Nested2Node("Image", ("weather.svg", {}), ()))
    elif case == "button":
        texts.append(Nested2Node("Button", ("详情", {}), ()))
    elif case == "action":
        texts[2] = replace(texts[2], values=(texts[2].values[0], {"onClick": {"id": "view"}}))
    elif case == "decoration":
        texts.append(Nested2Node("Divider", ({"height": 1},), ()))
    elif case == "calendar-image":
        calendar = _column(calendar, Nested2Node("Image", ("calendar.svg", {}), ()))
    elif case == "calendar-action":
        calendar = _column(calendar, onClick={"id": "view"})
    weather = replace(weather, children=tuple(texts))
    if case == "container-binding":
        weather = replace(weather, values=({"description": "${data.alternateWeather.current.uv}"},))
    original = replace(original, children=(weather, calendar))
    before = copy.deepcopy(original)
    assert center_calendar_weather_full(original, composition, size="2x4") is original
    assert original == before


def test_formal_compiler_applies_only_the_basic_weather_presentation() -> None:
    case = _CASES[2]
    registry = CardPlanRegistry(
        enable_fusion_ball=True, enabled_calendar_fallback_template_ids=(case.template_id,)
    )
    components = _compile(case, registry)
    weather_texts = []
    for component in components.values():
        content = json.dumps(component.get("content"), ensure_ascii=False)
        if component.get("component") == "Text" and "/data/weather/" in content:
            weather_texts.append(component)
    assert len(weather_texts) == 3
    expected = ("location/districtName", "current/temperatureText", "current/condition")
    for text, path, height in zip(weather_texts, expected, (16, 58, 16), strict=True):
        assert f"/data/weather/{path}" in str(text.get("content"))
        assert _styles(text).get("height") == height
        assert _styles(text).get("textAlign") == "center"
        assert _styles(text).get("width") == "matchParent"
    assert _styles(weather_texts[1]).get("fontSize") == 38
    assert _styles(weather_texts[1]).get("fontWeight") == 700
    assert _styles(weather_texts[1]).get("maxLines") == 1
    assert all(component.get("component") != "Button" for component in components.values())
