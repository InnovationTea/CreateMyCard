"""日程标题时间宽卡的正式编译、动态绑定与 300×150 布局边界。"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.tests.test_calendar_additional_no_action_render import (
    _business_column,
    _Case,
    _check_widths,
    _children,
    _compile,
)
from services.template_generation.tests.test_calendar_no_action_template_render import (
    _natural_height,
    _styles,
    _subtree,
)

_CASE = _Case("ScheduleOverviewTitleTimeWideFull@1", "2x4", ("title", "dtStart"))
_PATHS = {"/events/0/title", "/events/0/dtStart"}
_NORMAL = {"title": "项目评审", "dtStart": "14:00"}
_LONG = {
    "title": "跨部门联合项目评审及产品发布计划确认会议" * 4,
    "dtStart": "2026年10月31日星期六下午14:00（北京时间）",
}


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(enabled_calendar_fallback_template_ids=(_CASE.template_id,))


@pytest.mark.parametrize(
    "values",
    [_NORMAL, _LONG, {"title": "", "dtStart": ""}],
    ids=["normal", "long-text", "empty-samples"],
)
def test_title_time_wide_preserves_only_two_dynamic_fields_and_fits_card(
    values: dict[str, str], registry: CardPlanRegistry
) -> None:
    components = _compile(_CASE, (), registry, values)
    content = _subtree("template_root", components)
    texts = [item for item in content if item.get("component") == "Text"]
    assert len(texts) == 3
    serialized = json.dumps(texts, ensure_ascii=False)
    paths = re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", serialized)
    assert set(paths) == _PATHS
    assert len(paths) == 2
    assert "startDate" not in serialized
    assert "countdownDays" not in serialized
    assert "dtEnd" not in serialized
    assert "天后" not in serialized

    root = components.get("template_root")
    assert isinstance(root, dict)
    assert _styles(root).get("padding") == 12
    assert _natural_height("template_root", components) <= 150
    _check_widths("template_root", components, 300)
    for component in content:
        assert component.get("component") not in {"Button", "Image", "Divider"}
        assert "onClick" not in component
        styles = _styles(component)
        assert "onClick" not in styles
        if component.get("component") != "Text":
            continue
        assert styles.get("width") == "matchParent"
        assert styles.get("maxLines") == 1
        assert styles.get("textOverflow") == "ellipsis"
        font_size = styles.get("fontSize")
        assert isinstance(font_size, (float, int)) and font_size <= 18

    template = registry.require_template(_CASE.template_id)
    assert set(template.required_data) == _PATHS
    assert not template.optional_data


def _assert_text_style(component: dict[str, Any], *, size: int, weight: int, height: int) -> None:
    styles = _styles(component)
    assert styles.get("fontSize") == size
    assert styles.get("fontWeight") == weight
    assert styles.get("height") == height


def test_title_time_wide_keeps_title_group_above_start_time(
    registry: CardPlanRegistry,
) -> None:
    components = _compile(_CASE, (), registry, _NORMAL)
    business = _business_column(components)
    assert _styles(business).get("justifyContent") == "spaceBetween"
    upper, time = _children(business, components)
    header_row, title = _children(upper, components)
    header = _children(header_row, components)[0]
    assert header.get("content") == "下一个日程"
    assert "/events/0/title" in str(title.get("content"))
    assert "/events/0/dtStart" in str(time.get("content"))
    assert upper.get("itemMargin") == 8
    assert _natural_height(str(upper.get("id")), components) == 56
    assert _natural_height(str(time.get("id")), components) == 16
    _assert_text_style(header, size=12, weight=400, height=16)
    _assert_text_style(title, size=18, weight=700, height=28)
    _assert_text_style(time, size=12, weight=400, height=16)
    assert _styles(header).get("fontColor") == _styles(time).get("fontColor")
    assert _styles(title).get("fontColor") != _styles(time).get("fontColor")


def test_title_time_wide_keeps_bindings_when_samples_change(
    registry: CardPlanRegistry,
) -> None:
    ordinary = _compile(_CASE, (), registry, _NORMAL)
    long_text = _compile(_CASE, (), registry, _LONG)
    assert long_text == ordinary
