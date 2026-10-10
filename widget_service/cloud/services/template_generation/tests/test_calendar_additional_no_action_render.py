"""日程补充无按钮模板：字段完整、可选分支、零值与正式编译尺寸预算。"""

from __future__ import annotations

import json
import re
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
from services.template_generation.tests.test_calendar_no_action_template_render import (
    _natural_height,
    _styles,
    _subtree,
    _text_styles,
)


@dataclass(frozen=True)
class _Case:
    template_id: str
    size: Literal["2x2", "2x4"]
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()


_CASES = (
    _Case("ScheduleOverviewTitleStartFull@1", "2x2", ("title", "dtStart")),
    _Case("ScheduleOverviewReminderStartFull@1", "2x2", ("dtStart", "remindTime/0"), ("title",)),
    _Case("ScheduleOverviewDateAllDayFull@1", "2x2", ("startDate", "title", "isAllDay")),
    _Case("ScheduleOverviewDateEndFull@1", "2x2", ("title", "startDate", "dtEnd")),
    _Case(
        "ScheduleOverviewAllDayLocationFull@1",
        "2x2",
        ("isAllDay", "eventLocation"),
        ("title",),
    ),
    _Case(
        "ScheduleOverviewDateStartLocationFull@1",
        "2x2",
        ("startDate", "dtStart", "eventLocation"),
        ("title", "dtEnd"),
    ),
    _Case(
        "ScheduleOverviewReminderDetailsWideFull@1",
        "2x4",
        ("senderName", "importantEventType", "remindTime/0", "/updatedAt"),
    ),
    _Case(
        "ScheduleOverviewDatedMeetingWideFull@1",
        "2x4",
        ("startDate", "title", "dtStart", "dtEnd", "eventLocation"),
    ),
)
_SAMPLES: dict[str, str | int | bool] = {
    "title": "项目评审",
    "dtStart": "14:00",
    "dtEnd": "15:00",
    "startDate": "10-10",
    "eventLocation": "三层会议室",
    "remindTime/0": "15",
    "isAllDay": True,
    "senderName": "项目管理团队",
    "importantEventType": 1,
    "/updatedAt": "2026-10-10 09:00",
}
_GROUPED_REFERENCE = _Case(
    "ScheduleOverviewReminderWideFull@1", "2x4", ("dtStart", "remindTime/0"), ("title",)
)


def _path(field: str) -> str:
    return field if field.startswith("/") else f"/events/0/{field}"


def _combinations() -> list[tuple[_Case, tuple[str, ...]]]:
    result = []
    for case in _CASES:
        for count in range(len(case.optional) + 1):
            for selected in combinations(case.optional, count):
                result.append((case, selected))
    return result


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(
        enabled_calendar_fallback_template_ids=tuple(
            case.template_id for case in (*_CASES, _GROUPED_REFERENCE)
        ),
    )


def _task(
    case: _Case,
    selected: tuple[str, ...],
    values: dict[str, str | int | bool],
) -> TaskSpec:
    event: dict[str, Any] = {}
    calendar: dict[str, Any] = {"events": [event]}
    for field in (*case.required, *selected):
        value = values.get(field)
        assert value is not None
        kind = "string"
        if isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, int):
            kind = "integer"
        typed = {"type": kind, "description": "日程展示字段", "sampleValue": value}
        if field == "/updatedAt":
            calendar["updatedAt"] = typed
        elif field == "remindTime/0":
            event["remindTime"] = [typed]
        else:
            event[field] = typed
    return TaskSpec(
        userQuery="显示指定日程信息，不需要按钮",
        size=case.size,
        dataModelSchema={"data": {"calendar": calendar}},
    )


def _compile(
    case: _Case,
    selected: tuple[str, ...],
    registry: CardPlanRegistry,
    values: dict[str, str | int | bool],
) -> dict[str, dict[str, Any]]:
    task = _task(case, selected, values)
    paths = tuple(_path(field) for field in (*case.required, *selected))
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=list(paths),
    )
    card = {
        "title": "日程",
        "description": task.userQuery,
        "suggestSize": case.size,
        "dataBindings": [binding.model_dump()],
    }
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetCalendarEvents": paths})
    # 原子渲染测试只检索本次被测模板，不替代旧成功计划优先级的入口回归。
    search = search_template_variants(
        intent,
        task,
        registry,
        (binding,),
        card,
        preferred_template_ids=(case.template_id,),
    )
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    layout = "SingleFocusLayout@1" if case.size == "2x2" else "WideFullOnlyLayout@1"
    assert plans[0].layout_template_id == layout
    assert tuple(slot.template_id for slot in plans[0].business_slots) == (case.template_id,)
    assert not plans[0].action_assignments
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    compiled = compile_ux_layout_card(
        f'Template("{layout}",{{}},Template("{case.template_id}",{{}}));',
        task_spec=task,
        card_spec=card,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in compiled.a2ui.splitlines() if line.strip()]
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


def _horizontal_padding(styles: dict[str, Any]) -> float:
    padding = styles.get("padding", 0)
    if isinstance(padding, (float, int)):
        return padding * 2
    assert isinstance(padding, dict)
    left, right = padding.get("left", 0), padding.get("right", 0)
    assert isinstance(left, (float, int)) and isinstance(right, (float, int))
    return left + right


def _check_widths(
    component_id: str,
    components: dict[str, dict[str, Any]],
    available: float,
) -> None:
    component = components.get(component_id)
    assert isinstance(component, dict)
    styles = _styles(component)
    width = styles.get("width", available)
    if isinstance(width, (float, int)):
        assert width <= available
        available = width
    inner = available - _horizontal_padding(styles)
    assert inner >= 0
    children = component.get("children", [])
    assert isinstance(children, list)
    if component.get("component") != "Row":
        for child in children:
            _check_widths(child, components, inner)
        return
    fixed: dict[str, float] = {}
    flexible = []
    for child_id in children:
        child = components.get(child_id)
        assert isinstance(child, dict)
        child_styles = _styles(child)
        child_width = child_styles.get("width")
        if child_styles.get("layoutWeight") == 1:
            flexible.append(child_id)
        elif isinstance(child_width, (float, int)):
            fixed[child_id] = float(child_width)
        elif len(children) == 1:
            fixed[child_id] = inner
        else:
            # 仅重要程度静态标签使用自然宽度；按每字一整字宽核对保守上界。
            content = child.get("content")
            font_size = child_styles.get("fontSize")
            assert isinstance(content, str) and "{{" not in content
            assert isinstance(font_size, (float, int))
            fixed[child_id] = len(content) * font_size
    gap = component.get("itemMargin", 0)
    assert isinstance(gap, (float, int))
    remaining = inner - sum(fixed.values()) - gap * max(0, len(children) - 1)
    assert remaining >= 0
    for child_id, child_width in fixed.items():
        _check_widths(child_id, components, child_width)
    for child_id in flexible:
        _check_widths(child_id, components, remaining / len(flexible))


@pytest.mark.parametrize(("case", "selected"), _combinations())
@pytest.mark.parametrize("long_text", [False, True], ids=["normal", "long-text"])
def test_additional_templates_preserve_fields_and_fit_card(
    case: _Case,
    selected: tuple[str, ...],
    long_text: bool,
    registry: CardPlanRegistry,
) -> None:
    values = dict(_SAMPLES)
    if long_text:
        values.update(
            {
                "title": "跨部门联合项目评审及产品发布计划确认会议",
                "senderName": "产品研发与质量管理联合项目团队",
                "eventLocation": "研发总部三层东侧大型联合评审会议室",
            }
        )
    components = _compile(case, selected, registry, values)
    content = _subtree("template_root", components)
    texts = [item for item in content if item.get("component") == "Text"]
    serialized = json.dumps(texts, ensure_ascii=False)
    actual = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", serialized))
    assert actual == {_path(field) for field in (*case.required, *selected)}
    root = components.get("template_root")
    assert isinstance(root, dict)
    assert _styles(root).get("padding") == 12
    assert _natural_height("template_root", components) <= 150
    _check_widths("template_root", components, 150 if case.size == "2x2" else 300)
    for component in content:
        assert component.get("component") not in {"Button", "Image"}
        assert "onClick" not in component
        styles = _styles(component)
        assert "onClick" not in styles
        assert "backgroundColor" not in styles
        if component.get("component") == "Text":
            font = styles.get("fontSize")
            assert isinstance(font, (float, int)) and font <= 18
            assert styles.get("maxLines") == 1
    for field in (*case.required, *selected):
        assert _text_styles(content, _path(field))
    if "dtEnd" in case.optional and "dtEnd" not in selected:
        assert " - " not in serialized
    template = registry.require_template(case.template_id)
    assert set(template.required_data) == {_path(field) for field in case.required}
    assert set(template.optional_data) == {_path(field) for field in case.optional}


@pytest.mark.parametrize("case", [_CASES[1], _CASES[2], _CASES[4], _CASES[6]])
def test_false_and_zero_samples_do_not_remove_or_freeze_dynamic_fields(
    case: _Case,
    registry: CardPlanRegistry,
) -> None:
    ordinary = _compile(case, case.optional, registry, dict(_SAMPLES))
    zero_values = dict(_SAMPLES)
    zero_values.update({"isAllDay": False, "importantEventType": 0, "remindTime/0": "0"})
    zero = _compile(case, case.optional, registry, zero_values)
    # 比较最终组件而不是样例数据；真实值由端侧按绑定求值，不允许编译时固定成普通/15。
    assert zero == ordinary
    content = _subtree("template_root", zero)
    serialized = json.dumps(content, ensure_ascii=False)
    if "isAllDay" in case.required:
        assert "/events/0/isAllDay" in serialized
        assert "全天" in serialized and "非全天" in serialized
    if "importantEventType" in case.required:
        assert "/events/0/importantEventType" in serialized
        assert "普通" not in serialized
    if "remindTime/0" in case.required:
        assert "/events/0/remindTime/0" in serialized
        assert "提前" in serialized and "分钟提醒" in serialized


def test_empty_optional_end_uses_start_without_a_dangling_separator(
    registry: CardPlanRegistry,
) -> None:
    case = _CASES[5]
    values = dict(_SAMPLES)
    values.update({"title": "", "dtEnd": ""})
    components = _compile(case, case.optional, registry, values)
    content = _subtree("template_root", components)
    expressions = []
    for component in content:
        expression = component.get("content")
        if isinstance(expression, str) and "/events/0/dtEnd" in expression:
            expressions.append(expression)
    assert len(expressions) == 1
    expression = expressions[0]
    assert re.search(r"\$\{/data/calendar/events/0/dtEnd\}\s*==\s*''", expression)
    assert re.search(r"\?\s*\$\{/data/calendar/events/0/dtStart\}\s*:", expression)


def _children(
    component: dict[str, Any], components: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    children = component.get("children", [])
    assert isinstance(children, list)
    result = []
    for child_id in children:
        child = components.get(child_id)
        assert isinstance(child, dict)
        result.append(child)
    return result


def _business_column(components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    # 只取业务根；外层 SingleFocus/WideFullOnly 的宽度不同，不参与参照布局比较。
    for component in _subtree("template_root", components):
        if component.get("component") == "Column":
            return component
    raise AssertionError("缺少日程业务 Column")


def _visual_properties(component: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in component.items() if key not in {"id", "content", "children"}
    }


def _visual_tree(
    component: dict[str, Any], components: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result = _visual_properties(component)
    result["children"] = [
        _visual_tree(child, components) for child in _children(component, components)
    ]
    return result


@pytest.mark.parametrize(
    ("case", "selected"),
    [
        (_CASES[1], ()),
        (_CASES[1], ("title",)),
        (_CASES[2], ()),
        (_CASES[3], ()),
        (_CASES[4], ()),
        (_CASES[4], ("title",)),
    ],
)
def test_small_grouped_layout_matches_existing_reminder_reference(
    case: _Case, selected: tuple[str, ...], registry: CardPlanRegistry
) -> None:
    components = _compile(case, selected, registry, dict(_SAMPLES))
    has_title = "title" in (*case.required, *selected)
    reference = _compile(
        _GROUPED_REFERENCE, ("title",) if has_title else (), registry, dict(_SAMPLES)
    )
    root = _business_column(components)
    assert _visual_tree(root, components) == _visual_tree(_business_column(reference), reference)
    upper, lower = _children(root, components)
    upper_children = _children(upper, components)
    assert len(upper_children) == (2 if has_title else 1)
    assert len(_children(lower, components)) == 2
    assert _natural_height(str(upper.get("id")), components) == (56 if has_title else 24)
    assert _natural_height(str(lower.get("id")), components) == 36
    content = _subtree("template_root", components)
    assert all(item.get("component") != "Divider" for item in content)
    if case.template_id == "ScheduleOverviewDateAllDayFull@1":
        assert _children(upper_children[0], components)[0].get("content") == "日程详情"
        serialized = json.dumps(content, ensure_ascii=False)
        assert serialized.count("/data/calendar/events/0/startDate") == 1


def test_dated_meeting_uses_existing_reminder_details_layout(
    registry: CardPlanRegistry,
) -> None:
    components = _compile(_CASES[7], (), registry, dict(_SAMPLES))
    reference = _compile(_CASES[6], (), registry, dict(_SAMPLES))
    root, reference_root = _business_column(components), _business_column(reference)
    assert _visual_properties(root) == _visual_properties(reference_root)
    header, body = _children(root, components)
    reference_header, reference_body = _children(reference_root, reference)
    assert _visual_tree(header, components) == _visual_tree(reference_header, reference)
    assert _visual_properties(body) == _visual_properties(reference_body)
    timeline, details = _children(body, components)
    reference_timeline, reference_details = _children(reference_body, reference)
    assert _visual_tree(timeline, components) == _visual_tree(reference_timeline, reference)
    assert _visual_properties(details) == _visual_properties(reference_details)
    title, secondary = _children(details, components)
    reference_title, reference_secondary = _children(reference_details, reference)
    assert _visual_properties(title) == _visual_properties(reference_title)
    assert _visual_properties(secondary) == _visual_properties(reference_secondary)
    secondary_lines = _children(secondary, components)
    assert len(secondary_lines) == 3
    reference_line = _children(reference_secondary, reference)[1]
    for line in secondary_lines:
        assert _visual_properties(line) == _visual_properties(reference_line)
    assert _natural_height(str(body.get("id")), components) == 70


def test_small_reminder_stays_independent_when_start_is_empty(
    registry: CardPlanRegistry,
) -> None:
    values = dict(_SAMPLES)
    values.update({"dtStart": "", "remindTime/0": "0"})
    components = _compile(_CASES[1], (), registry, values)
    reminder_expressions = []
    for component in _subtree("template_root", components):
        content = component.get("content")
        if isinstance(content, str) and "/events/0/remindTime/0" in content:
            reminder_expressions.append(content)
    assert len(reminder_expressions) == 1
    expression = reminder_expressions[0]
    assert "提前" in expression and "分钟提醒" in expression
    assert "/events/0/dtStart" not in expression
    assert "?" not in expression
