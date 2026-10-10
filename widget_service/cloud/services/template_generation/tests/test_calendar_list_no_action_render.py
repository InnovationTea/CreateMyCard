"""多条日程无按钮模板的完整字段覆盖、正式编译及 300×150 布局预算。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

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
    TemplateRetrievalMiss,
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
    event_count: int
    fields: tuple[str, ...]
    show_count: bool

    @property
    def required(self) -> tuple[str, ...]:
        paths = ["/eventCount"] if self.show_count else []
        for index in range(self.event_count):
            for field in self.fields:
                paths.append(f"/events/{index}/{field}")
        return tuple(paths)


_CASES = (
    _Case(
        "ScheduleOverviewTimezoneThreeEventsWideFull@1",
        3,
        ("timeZone", "title", "dtStart", "dtEnd", "eventLocation"),
        False,
    ),
    _Case(
        "ScheduleOverviewEventCountFourDetailsWideFull@1",
        4,
        ("title", "dtStart", "description"),
        True,
    ),
    _Case(
        "ScheduleOverviewEventCountThreeNotesWideFull@1",
        3,
        ("description",),
        True,
    ),
)
_SAMPLES = {
    "timeZone": "Asia/Shanghai",
    "title": "项目评审",
    "dtStart": "14:00",
    "dtEnd": "15:00",
    "eventLocation": "研发三楼会议室",
    "description": "携带评审材料",
}


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(
        enabled_calendar_fallback_template_ids=tuple(case.template_id for case in _CASES),
    )


def _task(case: _Case, long_text: bool, missing_path: str | None = None) -> TaskSpec:
    events = []
    for index in range(case.event_count):
        event: dict[str, Any] = {}
        # 候选可多于展示需求；三条备注模板不能因存在标题、时间而额外绑定它们。
        for field, sample in _SAMPLES.items():
            if f"/events/{index}/{field}" == missing_path:
                continue
            if long_text and field == "description":
                sample = "携带项目评审材料并确认后续安排"
            event[field] = {
                "type": "string",
                "description": f"第 {index + 1} 项日程字段",
                "sampleValue": sample,
            }
        events.append(event)
    calendar = {
        "eventCount": {
            "type": "integer",
            "description": "查询范围内日程总数",
            "sampleValue": case.event_count,
        },
        "events": events,
    }
    return TaskSpec(
        userQuery="显示每项指定日程信息，不需要按钮",
        size="2x4",
        dataModelSchema={"data": {"calendar": calendar}},
    )


def _card(case: _Case, task: TaskSpec) -> tuple[dict[str, Any], CandidateDataBinding]:
    paths = ["/eventCount"]
    for index in range(case.event_count):
        for field in _SAMPLES:
            paths.append(f"/events/{index}/{field}")
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=paths,
    )
    card = {
        "title": "日程",
        "description": task.userQuery,
        "suggestSize": "2x4",
        "dataBindings": [binding.model_dump()],
    }
    return card, binding


def _compile(case: _Case, long_text: bool, registry: CardPlanRegistry) -> dict[str, Any]:
    task = _task(case, long_text)
    card, binding = _card(case, task)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetCalendarEvents": case.required},
    )
    search = search_template_variants(intent, task, registry, (binding,), card)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    assert plans[0].layout_template_id == "WideFullOnlyLayout@1"
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
        f'Template("WideFullOnlyLayout@1",{{}},Template("{case.template_id}",{{}}));',
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


def _assert_grid_width(content: list[dict[str, Any]]) -> None:
    cells = []
    grid_rows = []
    timelines = []
    text_columns = []
    for component in content:
        styles = _styles(component)
        if component.get("component") == "Column" and styles.get("width") == 8:
            timelines.append(component)
            assert styles.get("height") == 36
        if styles.get("height") != 52:
            continue
        if component.get("component") == "Column" and styles.get("width") == 116:
            text_columns.append(component)
            assert component.get("itemMargin") == 6
        if component.get("component") == "Row" and styles.get("width") == 130:
            cells.append(component)
        if component.get("component") == "Row" and styles.get("width") == "matchParent":
            grid_rows.append(component)
    assert len(cells) == 4 and len(grid_rows) == 2
    assert len(timelines) == len(text_columns) == 4
    for cell in cells:
        assert cell.get("itemMargin") == 6
    for row in grid_rows:
        assert row.get("itemMargin") == 16
        assert _styles(row).get("alignItems") == "top"
    dots = [component for component in content if _styles(component).get("borderWidth") == 1.5]
    assert len(dots) == 4
    for dot in dots:
        assert _styles(dot).get("width") == _styles(dot).get("height") == 8
    lines = []
    for component in content:
        styles = _styles(component)
        if component.get("component") == "Divider" and styles.get("vertical"):
            lines.append(component)
            assert styles.get("height") == 20
    assert len(lines) == 4
    assert 8 + 6 + 116 == 130
    assert 130 * 2 + 16 + 12 * 2 == 300


def _assert_split_list_width(
    content: list[dict[str, Any]],
    components: dict[str, Any],
) -> None:
    rows = []
    separators = []
    for component in content:
        styles = _styles(component)
        if component.get("component") == "Row" and styles.get("height") == 32:
            rows.append(component)
        if component.get("component") == "Divider" and styles.get("height") == 1:
            separators.append(component)
    assert len(rows) == 3 and len(separators) == 2
    widths = [160, 108]
    for row in rows:
        assert row.get("itemMargin") == 8
        assert _styles(row).get("alignItems") == "top"
        children = row.get("children")
        assert isinstance(children, list) and len(children) == 2
        for child_id, width in zip(children, widths, strict=True):
            child = components.get(child_id)
            assert isinstance(child, dict)
            assert _styles(child).get("width") == width
    assert sum(widths) + 8 + 12 * 2 == 300
    for separator in separators:
        style = _styles(separator)
        assert style.get("width") == "matchParent"
        assert style.get("strokeWidth") == 1


def _assert_notes_reference_positions(
    content: list[dict[str, Any]],
    components: dict[str, Any],
) -> None:
    lists = []
    for component in content:
        if component.get("component") == "Column" and _styles(component).get("height") == 96:
            lists.append(component)
    assert len(lists) == 1
    note_list = lists[0]
    assert _styles(note_list).get("width") == "matchParent"
    assert note_list.get("itemMargin") == 0
    children = note_list.get("children")
    assert isinstance(children, list) and len(children) == 5
    parents = []
    for component in content:
        if note_list.get("id") in component.get("children", []):
            parents.append(component)
    assert len(parents) == 1
    parent = parents[0]
    assert _styles(parent).get("width") == "matchParent"
    assert parent.get("itemMargin") == 10
    groups = parent.get("children")
    assert isinstance(groups, list) and len(groups) == 2
    text_positions = []
    divider_positions = []
    # 四周 padding 12，标题 20，头部到列表间距 10；按最终组件的 margin 累加坐标。
    top = 12 + _natural_height(groups[0], components) + parent.get("itemMargin")
    for child_id in children:
        child = components.get(child_id)
        assert isinstance(child, dict)
        style = _styles(child)
        if child.get("component") == "Text":
            text_positions.append(top)
            assert style.get("width") == "matchParent"
        else:
            assert child.get("component") == "Divider"
            divider_positions.append(top)
            assert style.get("width") == "matchParent"
            assert style.get("height") == style.get("strokeWidth") == 1
        top += _natural_height(child_id, components)
    assert text_positions == [42, 80, 118]
    assert divider_positions == [71, 109]
    assert top + 12 == 150
    for component in content:
        assert component.get("content") not in {"01", "02", "03"}


def _expected_weight(case: _Case, path: str) -> int:
    if path.endswith("/title"):
        return 700
    if case.event_count == 4:
        return 700 if path.endswith("/dtStart") else 400
    if path.endswith("/description"):
        return 700
    if path.endswith("/timeZone"):
        return 500
    return 400


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.template_id)
@pytest.mark.parametrize("long_text", [False, True], ids=["short", "long-notes"])
def test_list_templates_keep_every_requested_item_within_300x150(
    case: _Case,
    long_text: bool,
    registry: CardPlanRegistry,
) -> None:
    components = _compile(case, long_text, registry)
    content = _subtree("template_root", components)
    text_content = []
    for component in content:
        styles = _styles(component)
        assert component.get("component") not in {"Button", "Image"}
        assert "onClick" not in component and "onClick" not in styles
        if "backgroundColor" in styles:
            assert component.get("component") == "Stack"
            assert styles.get("width") == styles.get("height") == 14
        if component.get("component") == "Text":
            text_content.append(component.get("content"))
    serialized = json.dumps(text_content, ensure_ascii=False)
    actual_paths = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", serialized))
    assert actual_paths == set(case.required)
    root = components.get("template_root")
    assert isinstance(root, dict)
    assert _styles(root).get("padding") == 12
    assert _natural_height("template_root", components) <= 150
    headers = []
    for component in content:
        if component.get("content") in {"日程安排", "跨时区日程"}:
            headers.append(component)
    assert len(headers) == 1
    header_style = _styles(headers[0])
    assert header_style.get("height") == (16 if case.event_count == 4 else 20)
    assert header_style.get("fontSize") == (12 if case.event_count == 4 else 14)
    if case.fields == ("description",):
        assert header_style.get("fontWeight") == 400
    for path in case.required:
        matches = _text_styles(content, path)
        assert len(matches) == 1
        style = matches[0]
        if path == "/eventCount":
            assert style.get("fontSize") == 10
            continue
        assert style.get("fontSize") == 12
        if path.endswith("/description"):
            if case.event_count == 4:
                assert "height" not in style
                assert style.get("maxLines") == 2
            else:
                assert style.get("height") == 20
                assert style.get("maxLines") == 1
                assert style.get("textOverflow") == "ellipsis"
        else:
            assert style.get("height") == 16
            assert style.get("maxLines") == 1
        assert style.get("fontWeight") == _expected_weight(case, path)
        if path.endswith(("/timeZone", "/eventLocation")):
            assert style.get("textAlign") == "end"
    if case.event_count == 4:
        _assert_grid_width(content)
    elif case.fields == ("description",):
        _assert_notes_reference_positions(content, components)
    else:
        _assert_split_list_width(content, components)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.template_id)
def test_list_templates_require_last_item_instead_of_silently_showing_a_prefix(
    case: _Case,
    registry: CardPlanRegistry,
) -> None:
    task = _task(case, False, missing_path=case.required[-1])
    card, binding = _card(case, task)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetCalendarEvents": case.required},
    )
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            intent,
            task,
            registry,
            (binding,),
            card,
            preferred_template_ids=(case.template_id,),
        )


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.template_id)
def test_list_template_metadata_declares_only_displayed_fields(
    case: _Case,
    registry: CardPlanRegistry,
) -> None:
    template = registry.require_template(case.template_id)
    assert set(template.required_data) == set(case.required)
    assert not template.optional_data
    records = [
        record
        for record in registry.template_variant_search_records
        if record.template_id == case.template_id
    ]
    assert len(records) == 1
    assert records[0].supported_card_sizes == frozenset({"2x4"})
    assert template.action_policy == "none"
    assert not template.supported_event_ids
