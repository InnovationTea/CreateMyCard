"""可选日程字段只增加分支，保留完整旧输入的正式编译结果。"""

from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_additional_no_action_render import (
    _SAMPLES,
    _Case,
    _check_widths,
    _compile,
    _path,
    _task,
)
from services.template_generation.tests.test_calendar_no_action_template_render import (
    _natural_height,
    _styles,
    _subtree,
)

_CASES = (
    _Case("ScheduleOverviewDateAllDayFull@1", "2x2", ("title", "isAllDay"), ("startDate",)),
    _Case(
        "ScheduleOverviewReminderDetailsWideFull@1",
        "2x4",
        ("senderName", "importantEventType", "remindTime/0"),
        ("/updatedAt",),
    ),
    _Case(
        "ScheduleOverviewDatedMeetingWideFull@1",
        "2x4",
        ("title", "dtStart", "eventLocation"),
        ("startDate", "dtEnd"),
    ),
)

# 来自修改前 56c3e782：相同正式 Search/Planner/Compiler、相同主题和输入。
# 比较全部组件（含 ID、表达式、样式及层级），不只比较几项视觉属性。
_FULL_INPUT_COMPONENT_DIGESTS = {
    "ScheduleOverviewDateAllDayFull@1": (
        "2fc136d44c5d24b1955545e79ddc5528928326577a8703ca327cc14626676ea8"
    ),
    "ScheduleOverviewReminderDetailsWideFull@1": (
        "822a353c3efd1a6059bfc452d794d276f9198cf50c652593b711545a77c41781"
    ),
    "ScheduleOverviewDatedMeetingWideFull@1": (
        "9610ffbebb6717e4a9635f965ba0b8b39bfda15386f932195ef7c8c76673b1bc"
    ),
}


def _variants() -> list[tuple[_Case, tuple[str, ...]]]:
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


@pytest.mark.parametrize(("case", "selected"), _variants())
@pytest.mark.parametrize("long_text", [False, True], ids=["normal", "long-text"])
def test_optional_calendar_fields_render_only_available_paths_and_fit(
    case: _Case,
    selected: tuple[str, ...],
    long_text: bool,
    registry: CardPlanRegistry,
) -> None:
    values = dict(_SAMPLES)
    if long_text:
        values.update(
            {
                "title": "跨部门产品研发及发布计划联合评审会议",
                "senderName": "产品研发与质量管理联合项目团队",
                "eventLocation": "研发总部三层东侧大型联合评审会议室",
            }
        )
    components = _compile(case, selected, registry, values)
    content = _subtree("template_root", components)
    serialized = json.dumps(content, ensure_ascii=False)
    actual = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", serialized))
    assert actual == {_path(field) for field in (*case.required, *selected)}
    assert _natural_height("template_root", components) <= 150
    _check_widths("template_root", components, 150 if case.size == "2x2" else 300)
    for component in content:
        assert component.get("component") not in {"Button", "Image"}
        assert "onClick" not in component
        styles = _styles(component)
        assert "onClick" not in styles and "backgroundColor" not in styles
        if component.get("component") == "Text":
            font = styles.get("fontSize")
            assert isinstance(font, (float, int)) and font <= 18
            assert styles.get("maxLines") == 1
    if case is _CASES[2] and "dtEnd" not in selected:
        assert " - " not in serialized
    template = registry.require_template(case.template_id)
    assert set(template.required_data) == {_path(field) for field in case.required}
    assert set(template.optional_data) == {_path(field) for field in case.optional}


@pytest.mark.parametrize("case", _CASES)
def test_complete_original_inputs_keep_every_compiled_component(
    case: _Case,
    registry: CardPlanRegistry,
) -> None:
    components = _compile(case, case.optional, registry, dict(_SAMPLES))
    encoded = json.dumps(
        components,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    expected = _FULL_INPUT_COMPONENT_DIGESTS.get(case.template_id)
    assert expected is not None
    assert hashlib.sha256(encoded).hexdigest() == expected


@pytest.mark.parametrize(("case", "selected"), _variants()[:4])
def test_missing_date_or_update_keeps_false_zero_and_reminder_dynamic(
    case: _Case,
    selected: tuple[str, ...],
    registry: CardPlanRegistry,
) -> None:
    ordinary = _compile(case, selected, registry, dict(_SAMPLES))
    values = dict(_SAMPLES)
    values.update({"isAllDay": False, "importantEventType": 0, "remindTime/0": "0"})
    zero = _compile(case, selected, registry, values)
    assert zero == ordinary
    serialized = json.dumps(_subtree("template_root", zero), ensure_ascii=False)
    if "isAllDay" in case.required:
        assert "全天" in serialized and "非全天" in serialized
        assert "/data/calendar/events/0/isAllDay" in serialized
    else:
        assert "/data/calendar/events/0/importantEventType" in serialized
        assert "/data/calendar/events/0/remindTime/0" in serialized
        assert "提前" in serialized and "分钟提醒" in serialized


@pytest.mark.parametrize("case", _CASES)
def test_optional_values_do_not_replace_runtime_bindings_with_sample_branches(
    case: _Case,
    registry: CardPlanRegistry,
) -> None:
    ordinary = _compile(case, case.optional, registry, dict(_SAMPLES))
    values = dict(_SAMPLES)
    for field in case.optional:
        values[field] = ""
    assert _compile(case, case.optional, registry, values) == ordinary


def test_complete_dated_meeting_with_explicit_date_focus_still_plans(
    registry: CardPlanRegistry,
) -> None:
    case = _CASES[2]
    task = _task(case, case.optional, dict(_SAMPLES))
    fields = tuple(_path(field) for field in (*case.required, *case.optional))
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )
    card = {"suggestSize": task.size, "dataBindings": [binding.model_dump()]}
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetCalendarEvents": fields},
        primaryOutputFieldByCapability={"GetCalendarEvents": "/events/0/startDate"},
    )
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
    assert plans[0].layout_template_id == "WideFullOnlyLayout@1"
    assert tuple(slot.template_id for slot in plans[0].business_slots) == (case.template_id,)
    assert not plans[0].action_assignments
