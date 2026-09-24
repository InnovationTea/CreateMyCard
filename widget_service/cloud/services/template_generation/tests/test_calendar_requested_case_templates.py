"""十个日历用例的模板检索、编译期分支和核心渲染回归。

十个用例最终 A2UI 中出现的日历运行时绑定引用矩阵，以及 Q024 参考几何
蓝图、Q035 角标 action 配色、Q041 全天三元表达的渲染已固化为场景金样
（Layer C，``calendar_reqcase__*``）：引擎或模板改动后按 golden 工作流
``check --diff`` / ``bless --declared`` 复核。检索命中与字段投影、
provider 数据契约、可选 end 分支展开、标题/地点互斥选择与 Q006 双事件
索引仍为内联精度断言，保持不变。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.content_selectors import (
    apply_content_selectors,
    project_content_component_facts,
    schedule_overview_is_eligible,
)
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_effective_document,
    _serialize_node,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateRetrievalQuery,
    retrieve_template_variants,
)
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    convert_tersel_to_a2ui,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
from services.template_generation.profile import read_tersel_protocol_profile

_CAPABILITY_ID = "GetCalendarEvents"
_DATA_ROOT = "/data/calendar"
_THEME_ID = "meeting-paper-neutral"


@lru_cache(maxsize=1)
def _registry() -> CardPlanRegistry:
    return CardPlanRegistry()


@dataclass(frozen=True)
class CalendarCase:
    case_id: str
    template_id: str
    fields: tuple[str, ...]
    action_id: str | None = None


def _case(
    case_id: str,
    template: str,
    fields: str,
    action_id: str | None = None,
) -> CalendarCase:
    return CalendarCase(case_id, f"ScheduleOverview{template}@1", tuple(fields.split()), action_id)


_CASES = (
    _case(
        "Q006",
        "TwoEventsFull",
        "/events/0/title /events/0/dtStart /events/1/title /events/1/dtStart",
    ),
    _case(
        "Q007",
        "LocationDescriptionEndFull",
        "/events/0/eventLocation /events/0/description /events/0/dtEnd",
    ),
    _case(
        "Q017",
        "DatedAllDayHero",
        "/events/0/title /events/0/startDate /events/0/isAllDay /events/0/entityId",
        "event.viewCalendarEvent",
    ),
    _case(
        "Q018",
        "LocationHero",
        "/events/0/dtStart /events/0/eventLocation",
        "event.startNavigate",
    ),
    _case(
        "Q023",
        "TimezoneDateEndFull",
        "/events/0/title /events/0/startDate /events/0/dtEnd /events/0/timeZone",
    ),
    _case(
        "Q024",
        "ReminderDetailsHero",
        "/events/0/senderName /events/0/importantEventType /events/0/remindTime/0 /updatedAt",
        "event.open.settings.dnd",
    ),
    _case(
        "Q030",
        "TitleHero",
        "/events/0/title /events/0/dtStart /events/0/dtEnd /events/0/oneClickServiceLink",
        "event.enter.meeting",
    ),
    _case(
        "Q033",
        "TitleHero",
        "/events/0/title /events/0/dtStart",
        "event.open.clock.alarm",
    ),
    _case(
        "Q035",
        "EventCountDetailsHero",
        "/eventCount /events/0/title /events/0/dtStart /events/0/description /events/0/entityId",
        "event.viewCalendarEvent",
    ),
    _case(
        "Q041",
        "TimezoneAllDayFull",
        "/events/0/title /events/0/timeZone /events/0/isAllDay /events/0/eventLocation",
    ),
)

_SAMPLES: dict[str, tuple[Any, str]] = {
    "/eventCount": (4, "integer"),
    "/updatedAt": ("2026-09-02 10:00", "string"),
    "/events/0/title": ("产品立项会", "string"),
    "/events/0/dtStart": ("09:00", "string"),
    "/events/0/dtEnd": ("15:30", "string"),
    "/events/0/eventLocation": ("A3 会议室", "string"),
    "/events/0/description": ("客户方案交流", "string"),
    "/events/0/startDate": ("09-05", "string"),
    "/events/0/isAllDay": (False, "boolean"),
    "/events/0/entityId": ("calendar-event-001", "string"),
    "/events/0/senderName": ("", "string"),
    "/events/0/importantEventType": (0, "integer"),
    "/events/0/remindTime/0": ("15", "string"),
    "/events/0/oneClickServiceLink": ("meeting://join/30", "string"),
    "/events/0/timeZone": ("Asia/Shanghai", "string"),
    "/events/1/title": ("客户交流会", "string"),
    "/events/1/dtStart": ("15:00", "string"),
}

_QUERIES = {
    "Q006": (
        "明天上午九点有产品立项会，下午三点有客户交流会，帮我做个卡片，分别看两场会议的标题和开始时间。"
    ),
    "Q007": "下一场日程是明天下午两点的客户方案交流会，帮我做个卡片，看会议地点、备注和结束时间。",
    "Q017": (
        "周六有用户体验营，帮我做个日程卡片，看活动标题、日期和是不是全天安排，点一下查看日程详情。"
    ),
    "Q018": (
        "下一场日程是下午三点的版本发布排期会，帮我做个卡片，看会议开始时间和地点，点击导航去公司。"
    ),
    "Q023": (
        "下一场日程是下周一上午九点的全球项目周会，帮我做个卡片，看会议标题、会议日期、结束时间和所在时区。"
    ),
    "Q024": (
        "下一场日程是下午两点的需求评审会，帮我做个卡片，看会议发起人、"
        "是不是重要日程、提前提醒时间和日程信息更新时间，开会前可以打开免打扰设置。"
    ),
    "Q030": (
        "帮我做个日程卡片，下午两点有需求评审会，卡片可以看会议名称、开始和结束时间，点击按钮一键入会。"
    ),
    "Q033": (
        "帮我做个卡片，我明天上午10点要去医院复查，卡片展示日程信息、时间信息，点一下能进闹钟。"
    ),
    "Q035": (
        "帮我做个日程卡片，看看未来7天一共安排了几件事和最近一件的标题、开始时间、备注，点一下进日程详情。"
    ),
    "Q041": "帮我做个日程卡片，下周一要和美国团队开会，展示标题、时区、是不是全天、开会地点。",
}

_PROJECTED_FIELDS = {
    "Q006": ("title", "timeText"),
    "Q007": ("eventLocation", "description", "dtEnd"),
    "Q017": ("title", "startDate", "isAllDay"),
    "Q018": ("eventLocation", "dtStart"),
    "Q023": ("title", "timeZone", "startDate", "dtEnd"),
    "Q024": ("senderName", "importantEventType", "remindTime", "updatedAt"),
    "Q030": ("title", "timeText"),
    "Q033": ("title", "timeText"),
    "Q035": ("eventCount", "title", "dtStart", "description"),
    "Q041": ("title", "timeZone", "isAllDay", "location"),
}

_ACTION_REFS = {
    "event.viewCalendarEvent": "{{ ${/data/calendar/events/0/entityId} }}",
    "event.enter.meeting": "{{ ${/data/calendar/events/0/oneClickServiceLink} }}",
}
_INTENT_ACTIONS = frozenset({"event.viewCalendarEvent", "event.startNavigate"})


def _schema(fields: tuple[str, ...]) -> dict[str, Any]:
    calendar: dict[str, Any] = {}
    for path in fields:
        sample = _SAMPLES.get(path)
        assert sample is not None
        value, data_type = sample
        leaf = {"type": data_type, "description": "可信日历字段", "sampleValue": value}
        parts = path.strip("/").split("/")
        if parts[0] != "events":
            calendar[parts[0]] = leaf
            continue
        events = calendar.setdefault("events", [])
        assert isinstance(events, list)
        index = int(parts[1])
        while len(events) <= index:
            events.append({})
        event = events[index]
        assert isinstance(event, dict)
        event[parts[2]] = leaf if len(parts) == 3 else [leaf]
    return {"data": {"calendar": calendar}}


def _action(action_id: str | None) -> EventAction | None:
    if action_id is None:
        return None
    call = "clickToIntent" if action_id in _INTENT_ACTIONS else "clickToDeeplink"
    value = _ACTION_REFS.get(action_id, action_id)
    return EventAction(id=action_id, call=call, args={"value": value})


def _task(case: CalendarCase) -> TaskSpec:
    action = _action(case.action_id)
    return TaskSpec(
        userQuery=_QUERIES.get(case.case_id, "展示日程标题、地点和开始时间"),
        size="2x2",
        eventCandidates=[] if action is None else [action],
        dataModelSchema=_schema(case.fields),
    )


def _selection(case: CalendarCase, *, task: TaskSpec | None = None) -> Any:
    selected_task = task or _task(case)
    binding = CandidateDataBinding(
        capabilityId=_CAPABILITY_ID,
        writeResultTo=_DATA_ROOT,
        candidateOutputFields=list(case.fields),
    )
    query = TemplateRetrievalQuery(
        themeId=_THEME_ID,
        requiredOutputFieldsByCapability={_CAPABILITY_ID: case.fields},
        action=() if case.action_id is None else (case.action_id,),
    )
    return retrieve_template_variants(
        query,
        selected_task,
        _registry(),
        (binding,),
        {
            "suggestSize": "2x2",
            "dataBindings": [{"capabilityId": _CAPABILITY_ID, "writeResultTo": _DATA_ROOT}],
        },
    )


def _expanded(
    template_id: str,
    *,
    omitted: frozenset[str] = frozenset(),
    props: dict[str, Any] | None = None,
) -> Nested2Node:
    registry = _registry()
    definition = registry.require_template(template_id)
    bindings = {
        name: "${data.calendar" + binding.path.replace("/", ".") + "}"
        for name, binding in definition.bindings.items()
        if name not in omitted
    }
    return _instantiate_blueprint(
        definition.variants[0].root,
        props or {},
        bindings,
        registry.theme_reference_values(_THEME_ID),
    )


def _walk(node: Nested2Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _options(node: Nested2Node) -> dict[str, Any]:
    return next((value for value in node.values if isinstance(value, dict)), {})


def _node_payload(node: Nested2Node) -> dict[str, Any]:
    """把 Nested2Node 蓝图树转成可冻结的 canonical JSON 结构。"""
    return {
        "component": node.component_type,
        "values": [
            json.loads(json.dumps(value, ensure_ascii=False, default=str))
            for value in node.values
        ],
        "children": [_node_payload(child) for child in node.children],
    }


def _template_slug(template_id: str) -> str:
    """模板 ID（或其后缀）转 snake_case 场景键；ScheduleOverview 前缀可缺省。"""
    name = template_id.split("@", 1)[0].removeprefix("ScheduleOverview")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _case_by_id(case_id: str) -> CalendarCase:
    return next(case for case in _CASES if case.case_id == case_id)


def _a2ui(case: CalendarCase) -> str:
    definition = _registry().require_template(case.template_id)
    available = set(case.fields)
    omitted = frozenset(
        name for name, binding in definition.bindings.items() if binding.path not in available
    )
    root = _strip_advanced_component_markers(_expanded(case.template_id, omitted=omitted))
    source = _serialize_effective_document(
        Nested2Node("Column", ("card",), (root,)),
        _task(case),
        True,
    )
    return convert_tersel_to_a2ui(
        source,
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec=_task(case).model_dump(mode="json"),
    )


def _components(a2ui: str) -> list[dict[str, Any]]:
    for line in a2ui.splitlines():
        update = json.loads(line).get("updateComponents")
        if isinstance(update, dict):
            components = update.get("components")
            assert isinstance(components, list)
            return components
    raise AssertionError("A2UI 缺少 updateComponents")


_BINDING_REF_PATTERNS = (
    re.compile(r"/data/calendar(?:/[A-Za-z0-9_]+)*"),
    re.compile(r"data\.calendar(?:\.[A-Za-z0-9_]+)*"),
)


@scenario("calendar_reqcase__a2ui_bindings")
def _build_case_a2ui_bindings() -> dict[str, Any]:
    """十个用例最终 A2UI 中实际出现的全部日历运行时绑定引用矩阵。"""
    payload: dict[str, Any] = {}
    for case in _CASES:
        rendered = json.dumps(_components(_a2ui(case)), ensure_ascii=False)
        refs = {
            match.group(0)
            for pattern in _BINDING_REF_PATTERNS
            for match in pattern.finditer(rendered)
        }
        payload[case.case_id] = {
            "templateId": case.template_id,
            "runtimeBindings": sorted(refs),
        }
    return payload


@scenario("calendar_reqcase__q024_blueprint")
def _build_q024_blueprint() -> dict[str, Any]:
    """Q024 ReminderDetailsHero 无缺省绑定的完整参考几何蓝图。"""
    return {"root": _node_payload(_expanded("ScheduleOverviewReminderDetailsHero@1"))}


@scenario("calendar_reqcase__q035_badge")
def _build_q035_badge() -> dict[str, Any]:
    """Q035 事件数角标的完整 A2UI 组件列表（含 action 主题配色）。"""
    return {"components": _components(_a2ui(_case_by_id("Q035")))}


@scenario("calendar_reqcase__q041_allday")
def _build_q041_allday() -> dict[str, Any]:
    """Q041 全天行的行高选项与运行时三元表达 A2UI 组件。"""
    case = _case_by_id("Q041")
    return {
        "secondRowOptions": _options(_expanded(case.template_id).children[1]),
        "components": _components(_a2ui(case)),
    }


_GOLDEN_SCENARIOS = (
    "calendar_reqcase__a2ui_bindings",
    "calendar_reqcase__q024_blueprint",
    "calendar_reqcase__q035_badge",
    "calendar_reqcase__q041_allday",
)

@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.case_id)
def test_real_case_retrieves_and_projects_target_template(case: CalendarCase) -> None:
    task = _task(case)
    selection = _selection(case, task=task)

    assert len(selection.component_candidates) == 1
    candidate = selection.component_candidates[0]
    assert candidate.component_id == "CalendarOverview"
    assert case.template_id in candidate.available_template_ids
    assert selection.required_template_groups
    assert all(case.template_id in group for group in selection.required_template_groups)
    complete_template_ids = set(candidate.available_template_ids)
    for group in selection.required_template_groups:
        complete_template_ids.intersection_update(group)
    expected_ids = {case.template_id}
    if case.case_id == "Q024":
        expected_ids.add("ScheduleOverviewReminderDetailsFull@1")
    assert complete_template_ids == expected_ids

    capabilities = {_CAPABILITY_ID}
    selected = apply_content_selectors(task, capabilities)
    assert schedule_overview_is_eligible(selected, capabilities)
    projected = project_content_component_facts(
        selected,
        capabilities,
        ("CalendarOverview",),
    )
    data = projected.dataModelSchema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("CalendarOverview")
    assert isinstance(calendar, dict)
    assert set(_PROJECTED_FIELDS[case.case_id]) <= set(calendar)


_CONTRACTS = {
    "TwoEventsFull": ("/events/0/title /events/1/title|/events/0/dtStart /events/1/dtStart|"),
    "LocationDescriptionEndFull": (
        "/events/0/description|/events/0/dtEnd /events/0/eventLocation|"
    ),
    "LocationHero": "/events/0/eventLocation /events/0/dtStart||/events/0/dtEnd",
    "TitleHero": "/events/0/title /events/0/dtStart||/events/0/dtEnd",
    "ReminderDetailsHero": (
        "/events/0/senderName|/events/0/importantEventType /events/0/remindTime/0 /updatedAt|"
    ),
    "TimezoneDateEndFull": (
        "/events/0/timeZone /events/0/title|/events/0/startDate /events/0/dtEnd|"
    ),
    "TimezoneAllDayFull": (
        "/events/0/timeZone /events/0/title|/events/0/isAllDay /events/0/eventLocation|"
    ),
    "EventCountDetailsHero": (
        "/eventCount /events/0/title|/events/0/dtStart /events/0/description|"
    ),
    "DatedAllDayHero": "/events/0/startDate /events/0/title|/events/0/isAllDay|",
}


@pytest.mark.parametrize("suffix", tuple(_CONTRACTS))
def test_new_template_provider_contract_is_exact(suffix: str) -> None:
    template_id = f"ScheduleOverview{suffix}@1"
    definition = _registry().require_template(template_id)
    primary, secondary, optional = tuple(
        tuple(group.split()) for group in _CONTRACTS[suffix].split("|")
    )

    assert definition.primary_data == primary
    assert definition.secondary_data == secondary
    assert definition.optional_data == optional
    declared = {*primary, *secondary, *optional}
    assert "/events/0/entityId" not in declared
    assert "/events/0/oneClickServiceLink" not in declared


@pytest.mark.parametrize("suffix", ("Title", "Location"))
@pytest.mark.parametrize("with_end", (False, True), ids=("start", "range"))
def test_title_and_location_hero_expand_optional_end_branch(
    suffix: str,
    with_end: bool,
) -> None:
    template_id = f"ScheduleOverview{suffix}Hero@1"
    field = "title" if suffix == "Title" else "eventLocation"
    headline = "${data.calendar.events.0." + field + "}"
    root = _expanded(template_id, omitted=frozenset() if with_end else frozenset({"end"}))
    texts = [node.values[0] for node in _walk(root) if node.component_type == "Text"]

    assert headline in texts
    time = next(value for value in texts if isinstance(value, str) and "dtStart" in value)
    assert ("dtEnd" in time) is with_end
    assert (" + ' - ' + " in time) is with_end
    serialized = _serialize_node(root)
    assert "IfPresent" not in serialized
    assert "IfAbsent" not in serialized


def test_title_and_location_are_mutually_exclusive_for_new_hero_templates() -> None:
    case = _case(
        "both",
        "unused",
        "/events/0/title /events/0/eventLocation /events/0/dtStart",
        "event.open.clock.alarm",
    )
    selection = _selection(case)
    complete = set(selection.component_candidates[0].available_template_ids)
    for group in selection.required_template_groups:
        complete.intersection_update(group)
    assert complete == {"ScheduleOverviewNextEventLocationFull@1"}


def test_q006_keeps_two_event_indices_distinct_and_rejects_short_array() -> None:
    case = _CASES[0]
    root = _expanded(case.template_id)
    texts = [node.values[0] for node in _walk(root) if node.component_type == "Text"]
    assert texts == [
        "${data.calendar.events.0.title}",
        "${data.calendar.events.0.dtStart}",
        "${data.calendar.events.1.title}",
        "${data.calendar.events.1.dtStart}",
    ]
    assert len(root.children) == 2
    assert all(
        panel.component_type == "Stack"
        and _options(panel).items() >= {"width": "matchParent", "layoutWeight": 1}.items()
        for panel in root.children
    )

    short_task = _task(case)
    calendar = short_task.dataModelSchema.get("data", {}).get("calendar", {})
    events = calendar.get("events")
    assert isinstance(events, list)
    events.pop()
    with pytest.raises(TemplateRetrievalMiss):
        _selection(case, task=short_task)


@pytest.mark.parametrize("scenario_id", _GOLDEN_SCENARIOS)
def test_case_renderings_match_golden_scenarios(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
