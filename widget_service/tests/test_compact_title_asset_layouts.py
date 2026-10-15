"""标题素材按实际布局消费，覆盖 #534、#535 与相邻硬约束。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.compact_plan import compact_plan_context, evaluate_compact_plan_coverage

TITLE_ICON = "resources/calendar.svg"
OTHER_ICON = "resources/weather.svg"
MUSIC_ICON = "resources/music.svg"
ALARM_ICON = "resources/alarm.svg"


def _task_spec(size: str) -> dict[str, Any]:
    return {
        "size": size,
        "dataModelSchema": {"data": {}},
        "eventCandidates": [
            {"id": "music", "call": "openMusic", "args": {}},
            {"id": "alarm", "call": "openAlarm", "args": {}},
        ],
        "assetCandidates": [
            {"id": "calendar", "src": TITLE_ICON},
            {"id": "weather", "src": OTHER_ICON},
            {"id": "music", "src": MUSIC_ICON},
            {"id": "alarm", "src": ALARM_ICON},
        ],
    }


def _plan(asset_id: str | None, *, actions: bool = False) -> dict[str, Any]:
    title: dict[str, Any] = {"assetId": asset_id}
    if asset_id is None:
        title["reason"] = "布局没有标题槽或无匹配标题素材"
    assignments: list[dict[str, str]] = []
    if actions:
        assignments = [
            {"actionId": "music", "assetId": "music"},
            {"actionId": "alarm", "assetId": "alarm"},
        ]
    return {"info_required": [], "assetAssignments": {"actions": assignments, "title": title}}


def _split_dsl(
    left_icon: str | None,
    right_icon: str | None,
    *,
    reverse_rows: bool = False,
) -> str:
    left: dict[str, Any] = {"title": "天气", "fontSize": 12}
    right: dict[str, Any] = {"title": "日程", "fontSize": 12}
    if left_icon is not None:
        left["icon"] = left_icon
    if right_icon is not None:
        right["icon"] = right_icon
    titles = [["weather", "SingleLineTitle", left], ["calendar", "SingleLineTitle", right]]
    if reverse_rows:
        titles.reverse()
    rows = [
        ["root", "Row", {"width": 320, "height": 150}, ["left", "right"]],
        ["left", "Column", {"width": 138, "height": 126}, ["weather"]],
        ["right", "Column", {"width": 138, "height": 126}, ["calendar"]],
        *titles,
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_split_title_icon_is_independent_of_component_row_order(reverse_rows: bool) -> None:
    validate_compact_dsl(
        _split_dsl(None, TITLE_ICON, reverse_rows=reverse_rows),
        task_spec=_task_spec("2x4"),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        compact_plan=_plan("calendar"),
    )


@pytest.mark.parametrize(
    ("left_icon", "right_icon", "asset_id", "message"),
    [
        (None, None, "calendar", "found 0 uses"),
        (None, OTHER_ICON, "calendar", "unassigned icon"),
        (TITLE_ICON, TITLE_ICON, "calendar", "found 2 uses"),
        (OTHER_ICON, TITLE_ICON, "calendar", "unassigned icon"),
        (TITLE_ICON, OTHER_ICON, "calendar", "unassigned icon"),
        (None, TITLE_ICON, None, "asset assignment is null"),
        (TITLE_ICON, None, None, "asset assignment is null"),
    ],
)
@pytest.mark.parametrize("reverse_rows", [False, True])
def test_split_title_assignment_still_rejects_invalid_consumption(
    left_icon: str | None,
    right_icon: str | None,
    asset_id: str | None,
    message: str,
    reverse_rows: bool,
) -> None:
    with pytest.raises(CompactDslValidationError, match=message):
        validate_compact_dsl(
            _split_dsl(left_icon, right_icon, reverse_rows=reverse_rows),
            task_spec=_task_spec("2x4"),
            card_spec={"suggestSize": "2x4", "dataBindings": []},
            compact_plan=_plan(asset_id),
        )


def test_split_titles_allow_null_assignment_without_icons() -> None:
    validate_compact_dsl(
        _split_dsl(None, None),
        task_spec=_task_spec("2x4"),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        compact_plan=_plan(None),
    )


def _titleless_dsl(*, missing_music_icon: bool = False) -> str:
    music: dict[str, Any] = {
        "label": "歌单",
        "onClick": [{"call": "openMusic", "args": {}}],
    }
    if not missing_music_icon:
        music["icon"] = MUSIC_ICON
    rows = [
        [
            "root",
            "Column",
            {"width": 150, "height": 150, "padding": 12, "itemMargin": 8},
            ["content_area", "music", "alarm"],
        ],
        ["content_area", "Column", {"width": 126, "height": 38}, ["summary"]],
        [
            "summary",
            "TableText",
            {
                "fontSize": 12,
                "items": [
                    {"label": "耳机盒", "value": "80%"},
                    {"label": "状态", "value": "充电中"},
                ],
            },
        ],
        ["music", "PillButton", music],
        [
            "alarm",
            "PillButton",
            {"label": "闹钟", "icon": ALARM_ICON, "onClick": [{"call": "openAlarm", "args": {}}]},
        ],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("asset_id", ["calendar", None])
def test_titleless_dual_action_layout_does_not_require_decorative_title(
    asset_id: str | None,
) -> None:
    validate_compact_dsl(
        _titleless_dsl(),
        task_spec=_task_spec("2x2"),
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        compact_plan=_plan(asset_id, actions=True),
        layout_scope="S-content-dual-action",
        enforce_model_component_types=True,
    )


def test_titleless_layout_still_requires_assigned_button_icon() -> None:
    with pytest.raises(CompactDslValidationError, match="button for action 'music' must use"):
        validate_compact_dsl(
            _titleless_dsl(missing_music_icon=True),
            task_spec=_task_spec("2x2"),
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            compact_plan=_plan("calendar", actions=True),
        )


def test_titleless_layout_still_requires_explicit_title_fact() -> None:
    plan = _plan("calendar", actions=True)
    plan["info_required"] = [
        {
            "requirement": "必须展示睡前准备标题",
            "text": "睡前准备",
            "priority": "must",
            "componentHints": ["SingleLineTitle"],
        }
    ]
    result = evaluate_compact_plan_coverage(_titleless_dsl(), plan, _task_spec("2x2"))
    assert len(result.errors) == 1
    assert "Plan title fact must be visible in a SingleLineTitle.title" in result.errors[0]


@pytest.mark.parametrize("execution_selected", [False, True])
def test_dsl_handoff_keeps_titleless_and_multi_title_asset_contracts(
    execution_selected: bool,
) -> None:
    context = compact_plan_context(
        _plan("calendar", actions=True),
        execution_selected=execution_selected,
    )
    assert "不按组件行顺序或左右位置确定标题" in context
    assert "无标题布局不消费标题装饰素材" in context
    assert "必需标题事实仍须满足" in context
    assert "按钮分配始终落实" in context
