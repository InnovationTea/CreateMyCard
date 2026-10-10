"""日程无按钮兜底模板的字段组合、正式编译和 150vp 高度预算。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)


@dataclass(frozen=True)
class _Case:
    template_id: str
    size: Literal["2x2", "2x4"]
    required: tuple[str, ...]
    optional: tuple[str, ...]


_CASES = (
    _Case(
        "ScheduleOverviewSourceReminderFull@1",
        "2x2",
        ("/events/0/senderName", "/events/0/remindTime/0"),
        ("/events/0/title",),
    ),
    _Case(
        "ScheduleOverviewTimezoneWideFull@1",
        "2x4",
        ("/events/0/timeZone", "/events/0/dtStart", "/events/0/eventLocation"),
        ("/events/0/title", "/events/0/dtEnd"),
    ),
    _Case(
        "ScheduleOverviewEventCountDetailsWideFull@1",
        "2x4",
        ("/eventCount", "/events/0/description"),
        ("/events/0/title", "/events/0/dtStart"),
    ),
    _Case(
        "ScheduleOverviewReminderWideFull@1",
        "2x4",
        ("/events/0/dtStart", "/events/0/remindTime/0"),
        ("/events/0/title",),
    ),
)
_SAMPLES = {
    "/events/0/senderName": "项目管理团队",
    "/events/0/remindTime/0": "15",
    "/events/0/title": "跨时区项目联合评审",
    "/events/0/timeZone": "Asia/Shanghai",
    "/events/0/dtStart": "14:00",
    "/events/0/dtEnd": "15:00",
    "/events/0/eventLocation": "研发中心三层会议室",
    "/events/0/description": "请携带最新项目进度及待确认事项",
    "/eventCount": 3,
}


def _parameters() -> list[tuple[_Case, tuple[str, ...]]]:
    result = []
    for case in _CASES:
        for count in range(len(case.optional) + 1):
            for selected in combinations(case.optional, count):
                result.append((case, selected))
    return result


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(
        enabled_calendar_fallback_template_ids=tuple(case.template_id for case in _CASES),
    )


def _task(case: _Case, optional: tuple[str, ...]) -> TaskSpec:
    event: dict[str, Any] = {}
    calendar: dict[str, Any] = {"events": [event]}
    for path in (*case.required, *optional):
        value = _SAMPLES.get(path)
        assert value is not None
        field = {
            "type": "integer" if isinstance(value, int) else "string",
            "description": "日程展示字段",
            "sampleValue": value,
        }
        if path == "/eventCount":
            calendar["eventCount"] = field
        elif path == "/events/0/remindTime/0":
            event["remindTime"] = [field]
        else:
            event[path.removeprefix("/events/0/")] = field
    return TaskSpec(
        userQuery="显示指定日程信息，不需要按钮",
        size=case.size,
        dataModelSchema={"data": {"calendar": calendar}},
    )


def _compile(
    case: _Case,
    optional: tuple[str, ...],
    registry: CardPlanRegistry,
) -> dict[str, dict[str, Any]]:
    task = _task(case, optional)
    fields = (*case.required, *optional)
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )
    card = {
        "title": "日程",
        "description": task.userQuery,
        "suggestSize": case.size,
        "dataBindings": [binding.model_dump()],
    }
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetCalendarEvents": fields})
    search = search_template_variants(intent, task, registry, (binding,), card)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    plan = plans[0]
    layout = "SingleFocusLayout@1" if case.size == "2x2" else "WideFullOnlyLayout@1"
    assert plan.layout_template_id == layout
    assert tuple(slot.template_id for slot in plan.business_slots) == (case.template_id,)
    assert not plan.action_assignments
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    compilation = compile_ux_layout_card(
        f'Template("{layout}",{{}},Template("{case.template_id}",{{}}));',
        task_spec=task,
        card_spec=card,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in compilation.a2ui.splitlines() if line.strip()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    result = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        result[component_id] = component
    return result


def _subtree(
    component_id: str,
    components: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    component = components.get(component_id)
    assert isinstance(component, dict)
    result = [component]
    children = component.get("children", [])
    assert isinstance(children, list)
    for child in children:
        result.extend(_subtree(child, components))
    return result


def _styles(component: dict[str, Any]) -> dict[str, Any]:
    styles = component.get("styles")
    assert isinstance(styles, dict)
    return styles


def _vertical_insets(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (float, int)):
        return float(value) * 2
    assert isinstance(value, dict)
    top = value.get("top", 0)
    bottom = value.get("bottom", 0)
    assert isinstance(top, (float, int)) and isinstance(bottom, (float, int))
    return float(top + bottom)


def _natural_height(component_id: str, components: dict[str, dict[str, Any]]) -> float:
    """核对每层最小高度，不能让固定容器高度掩盖内部溢出。"""
    component = components.get(component_id)
    assert isinstance(component, dict)
    styles = _styles(component)
    kind = component.get("component")
    children = component.get("children", [])
    assert isinstance(children, list)
    if kind == "Text":
        font_size = styles.get("fontSize")
        max_lines = styles.get("maxLines", 1)
        assert isinstance(font_size, (float, int)) and isinstance(max_lines, int)
        content_height = font_size * 1.25 * max_lines
    elif kind == "Divider":
        content_height = 0.0
    else:
        assert children
        heights = [_natural_height(child, components) for child in children]
        gap = component.get("itemMargin", 0)
        assert isinstance(gap, (float, int))
        if kind == "Column":
            content_height = sum(heights) + gap * (len(children) - 1)
        else:
            assert kind in {"Row", "Stack"}
            content_height = max(heights)
    required_height = content_height + _vertical_insets(styles.get("padding"))
    height = styles.get("height")
    if isinstance(height, (float, int)):
        assert required_height <= height, (component_id, required_height, height)
        required_height = float(height)
    return required_height + _vertical_insets(styles.get("margin"))


def _text_styles(content: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
    matches = []
    for component in content:
        if component.get("component") != "Text":
            continue
        value = json.dumps(component.get("content"), ensure_ascii=False)
        if f"/data/calendar{path}" in value:
            matches.append(_styles(component))
    # 开始时间可同时被辅助提醒行用作空值守卫，因此路径允许出现在多行中。
    assert matches, path
    return matches


def _assert_reference_style(case: _Case, content: list[dict[str, Any]]) -> None:
    # 只约束参考款的主辅文字层级与分组特征，避免复制整份组件树作为期望值。
    if case.template_id == "ScheduleOverviewSourceReminderFull@1":
        expected = (("/events/0/senderName", 16, 700), ("/events/0/remindTime/0", 12, 400))
        sender_styles = _text_styles(content, "/events/0/senderName")
        assert len(sender_styles) == 1
        assert "height" not in sender_styles[0]
        assert sender_styles[0].get("maxLines") == 2
    elif case.template_id == "ScheduleOverviewTimezoneWideFull@1":
        expected = (
            ("/events/0/timeZone", 16, 700),
            ("/events/0/dtStart", 10, 400),
            ("/events/0/eventLocation", 10, 400),
        )
    elif case.template_id == "ScheduleOverviewEventCountDetailsWideFull@1":
        expected = (("/eventCount", 10, 500), ("/events/0/description", 12, 400))
        count_styles = _text_styles(content, "/eventCount")
        assert len(count_styles) == 1
        count_style = count_styles[0]
        assert count_style.get("width") == count_style.get("height") == 14
    else:
        expected = (("/events/0/dtStart", 12, 400), ("/events/0/remindTime/0", 12, 400))
    for path, font_size, font_weight in expected:
        for style in _text_styles(content, path):
            assert style.get("fontSize") == font_size
            assert style.get("fontWeight") == font_weight
    timeline_dots = []
    for component in content:
        styles = _styles(component)
        if styles.get("borderWidth") == 1.5:
            timeline_dots.append(component)
            assert component.get("component") == "Stack"
            assert styles.get("width") == styles.get("height") == 8
            assert styles.get("borderRadius") == 4
    grouped_template = case.template_id in {
        "ScheduleOverviewSourceReminderFull@1",
        "ScheduleOverviewEventCountDetailsWideFull@1",
        "ScheduleOverviewReminderWideFull@1",
    }
    assert len(timeline_dots) == (0 if grouped_template else 1)
    if grouped_template:
        for component in content:
            if component.get("component") == "Divider":
                styles = _styles(component)
                assert styles.get("width") == styles.get("height") == 0


def _assert_grouped_layout(case: _Case, content: list[dict[str, Any]]) -> None:
    columns = [component for component in content if component.get("component") == "Column"]
    assert columns
    root = columns[0]
    if case.template_id == "ScheduleOverviewSourceReminderFull@1":
        assert _styles(root).get("justifyContent") == "start"
        assert root.get("itemMargin") == 8
        assert len(columns) == 2
        assert columns[1].get("itemMargin") == 4
    elif case.template_id in {
        "ScheduleOverviewEventCountDetailsWideFull@1",
        "ScheduleOverviewReminderWideFull@1",
    }:
        assert _styles(root).get("justifyContent") == "spaceBetween"
        assert root.get("itemMargin") == 2
        assert len(columns) == 3
        for group in columns[1:]:
            assert group.get("itemMargin") == 4
        headers = [component for component in content if component.get("component") == "Row"]
        assert len(headers) == 1
        assert _styles(headers[0]).get("height") == 24
        assert _styles(headers[0]).get("alignItems") == "top"


@pytest.mark.parametrize(("case", "optional"), _parameters())
def test_no_action_templates_compile_every_optional_combination_within_150vp(
    case: _Case,
    optional: tuple[str, ...],
    registry: CardPlanRegistry,
) -> None:
    components = _compile(case, optional, registry)
    content = _subtree("template_root", components)
    serialized = json.dumps(content, ensure_ascii=False)
    for path in (*case.required, *optional):
        assert f"/data/calendar{path}" in serialized
    for path in set(case.optional) - set(optional):
        assert f"/data/calendar{path}" not in serialized
    # template_root 自带四周 12vp padding；含 padding 的总预算为 150vp，内容为 126vp。
    template_root = components.get("template_root")
    assert isinstance(template_root, dict)
    assert _styles(template_root).get("padding") == 12
    assert _natural_height("template_root", components) <= 150
    _assert_reference_style(case, content)
    _assert_grouped_layout(case, content)
    if "/events/0/title" in optional:
        title_styles = _text_styles(content, "/events/0/title")
        assert len(title_styles) == 1
        title_style = title_styles[0]
        if case.template_id == "ScheduleOverviewSourceReminderFull@1":
            assert (title_style.get("fontSize"), title_style.get("fontWeight")) == (12, 400)
        elif case.template_id in {
            "ScheduleOverviewEventCountDetailsWideFull@1",
            "ScheduleOverviewReminderWideFull@1",
        }:
            assert (title_style.get("fontSize"), title_style.get("fontWeight")) == (18, 700)
        else:
            assert (title_style.get("fontSize"), title_style.get("fontWeight")) == (14, 700)
    for component in content:
        assert component.get("component") not in {"Button", "Image"}
        styles = _styles(component)
        if "backgroundColor" in styles:
            # 允许旧款时间轴圆点与数量徽标的局部底色，业务内容层不再叠整块蒙版。
            assert component.get("component") == "Stack"
            assert styles.get("width") == styles.get("height")
            assert styles.get("width") in {8, 14}
        assert "onClick" not in component and "onClick" not in styles
        if component.get("component") != "Text":
            continue
        font_size = styles.get("fontSize")
        max_lines = styles.get("maxLines")
        assert isinstance(font_size, (float, int)) and font_size <= 18
        assert isinstance(max_lines, int)
    assert "今日日程" not in serialized and "全部日程" not in serialized
    if "/events/0/dtEnd" not in optional:
        assert " - " not in serialized
