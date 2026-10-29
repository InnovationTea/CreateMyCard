"""已有路线失败后，尝试定长无动作列表或明确标注首项范围的单项摘要。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.logger import logger
from core.json_pointer import parse_json_pointer
from models.generation import CandidateDataBinding, TaskSpec

from .calendar_field_paths import CALENDAR_CAPABILITY_ID
from .calendar_no_action_policy import (
    _ACTION_QUERY,
    _CALENDAR_FAIL_EXCLUDED_CONTEXT_QUERY,
    _EXCLUSIVE_CONTEXT_QUERY,
    _NEGATIVE_ACTION,
    CalendarNoActionFallback,
    _calendar_fail_context_fields,
    _single_calendar_request,
)
from .registry import CardPlanRegistry
from .template_plan_planner import plan_template_candidates
from .template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    _task_spec_schema_leaf,
    search_template_variants,
)

_EVENT_PATH = re.compile(r"/events/(0|[1-9][0-9]*)(?:/[^/]+)+")
_QUERY_EVENT_COUNT = re.compile(
    r"([0-9零一二两三四五六七八九十百千万]+)\s*(?:个|条|项|场)\s*"
    r"(?:日程|会议|活动|安排)(?!的?(?:卡片|列表))"
)
_ALL_EVENTS_QUERY = re.compile(
    r"每(?:个|条|项|场)(?:日程|会议|活动|安排)|"
    r"各(?:个|条|项|场)?(?:日程|会议|活动|安排)|"
    r"(?:全部|所有)的?(?:日程|会议|活动|安排)|"
    r"\b(?:each|every)\s+(?:event|meeting)|\ball\s+(?:events|meetings)\b",
    re.IGNORECASE,
)
_NEGATED_ALL_QUERY = re.compile(
    r"(?:不要|无需|不必|不用|不需要|别|不)(?:再)?(?:显示|展示|列出|看|列)?"
    r"(?:全部|所有|每个|各条)的?(?:日程|会议|活动|安排)"
)
_QUERY_ROW_LIMIT = re.compile(
    r"(?:前\s*([0-9零一二两三四五六七八九十百千万几]+)|"
    r"第\s*[0-9零一二两三四五六七八九十百千万]+|首)\s*(?:个|条|项|场)"
)
_FULL_TEXT_QUERY = re.compile(
    r"全文|(?:不要|不能|不许|禁止|不得)(?:省略|截断|截字)|"
    r"(?:完整|全部)(?:显示|展示|呈现)(?:所有|全部|每条|各条)?的?(?:文字|文本|备注文字)|"
    r"(?:文字|文本|备注)(?:要|需|必须)?(?:完整显示|完整展示|不省略)|"
    r"完整的?(?:备注|文字|文本)|完整(?:显示|展示)"
    r"(?:[0-9零一二两三四五六七八九十]+(?:条|项|个|场)(?:日程|会议|活动|安排))?的?备注|"
    r"\b(?:full\s+text|without\s+(?:truncation|ellipsis))\b",
    re.IGNORECASE,
)
_TIME_NOTES_ALL_QUERY = re.compile(r"各是|(?:每|各)(?:条|项|场)|逐条|逐项|各自")
_TIME_NOTES_NEGATED_LIST_QUERY = re.compile(
    r"(?:不要|无需|不必|不用|不需要|别|不)(?:再)?(?:显示|展示|列出|看|列|按|用)?"
    r"(?:全部|所有|每(?:个|条|项|场)|各(?:个|条|项|场)|逐条|逐项|各自|列表|清单)"
)
_TIME_NOTES_FIRST_ONLY_QUERY = re.compile(
    r"(?:只|仅)(?:要|需|需要|看|显示|展示|保留)?"
    r"(?:首|下(?:一)?(?:个|条|项|场)|最近的?(?:一|1|日程|会议|活动|安排))"
)


@dataclass(frozen=True)
class _ListShape:
    template_id: str
    event_count: int
    event_fields: tuple[str, ...]
    with_count: bool = False

    def ordered_fields(self) -> tuple[str, ...]:
        paths: list[str] = ["/eventCount"] if self.with_count else []
        for index in range(self.event_count):
            for field in self.event_fields:
                paths.append(f"/events/{index}/{field}")
        return tuple(paths)

    def required_fields(self) -> frozenset[str]:
        return frozenset(self.ordered_fields())


@dataclass(frozen=True)
class _ListSelection:
    shape: _ListShape
    intent: TemplateSearchIntent


_LIST_SHAPES = (
    _ListShape(
        "ScheduleOverviewTimezoneThreeEventsWideFull@1",
        3,
        ("timeZone", "title", "dtStart", "dtEnd", "eventLocation"),
    ),
    _ListShape(
        "ScheduleOverviewEventCountFourDetailsWideFull@1",
        4,
        ("title", "dtStart", "description"),
        with_count=True,
    ),
    _ListShape(
        "ScheduleOverviewEventCountThreeNotesWideFull@1",
        3,
        ("description",),
        with_count=True,
    ),
)
_THREE_TIME_NOTES_SHAPE = _ListShape(
    "ScheduleOverviewEventCountThreeTimeNotesWideFull@1",
    3,
    ("dtStart", "description"),
    with_count=True,
)
_THREE_DETAILS_SHAPE = _ListShape(
    "ScheduleOverviewEventCountThreeDetailsWideFull@1",
    3,
    ("title", "dtStart", "description"),
    with_count=True,
)
_TWO_EVENTS_TARGET = "ScheduleOverviewTwoEventsWideFull@1"
_QUERY_MATTER_COUNT = re.compile(r"([0-9零一二两三四五六七八九十百千万]+)\s*件事")
_RECENT_SUMMARY_SHAPE = _ListShape(
    "ScheduleOverviewEventCountDetailsWideFull@1",
    1,
    ("title", "dtStart", "description"),
    with_count=True,
)
_RECENT_COMPLETE_QUERY = re.compile(
    r"全部|所有|完整|逐条|逐项|各自|每(?:个|条|项|场)|列表|清单|"
    r"(?:不能|不许|禁止|不要|不得|不允许)(?:只|仅)(?:显示|展示|看|列出|保留)?"
    r"(?:首|第一|最近|下一)|"
    r"(?:不能|不许|禁止|不要|不得|不允许)(?:省略|漏掉|遗漏|丢失).{0,8}"
    r"(?:日程|会议|活动|安排)|"
    r"\b(?:all|every|complete|entire)\b",
    re.IGNORECASE,
)


def plan_calendar_list_no_action_fallback(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
    *,
    enable_fusion_ball: bool = False,
    trusted_template_candidate_ids: tuple[str, ...] = (),
    trusted_template_action_ids: tuple[str, ...] = (),
    trusted_template_layout_ids: tuple[str, ...] = (),
) -> CalendarNoActionFallback | None:
    """不删减原意图；调用方仅在旧 Search/Planner 与单条补充分支均未命中后调用。"""
    result: CalendarNoActionFallback | None = None
    if task_spec.size != "2x4":
        return result
    if not _single_calendar_request(intent, coverage_bindings, card_spec):
        return result
    if intent.action_ids or trusted_template_action_ids:
        return result
    query = _NEGATIVE_ACTION.sub("", task_spec.userQuery)
    if _ACTION_QUERY.search(query) or _FULL_TEXT_QUERY.search(query):
        return result
    if _NEGATED_ALL_QUERY.search(query):
        return result
    selection = _select_list_shape(intent, query)
    if selection is None or not _complete_list_input(
        selection.shape, task_spec, coverage_bindings[0]
    ):
        selection = _select_recent_summary_shape(
            intent, query, task_spec, coverage_bindings[0], registry
        )
    if selection is None:
        return result
    shape = selection.shape
    if shape.template_id not in registry.templates:
        return result
    if not _complete_list_input(shape, task_spec, coverage_bindings[0]):
        return result
    if not _query_count_fits(query, shape.event_count):
        return result
    target = shape.template_id
    if target in {_TWO_EVENTS_TARGET, _THREE_DETAILS_SHAPE.template_id}:
        if not _new_list_context_fits(selection, query, task_spec, coverage_bindings[0], registry):
            return result
    if trusted_template_candidate_ids and set(trusted_template_candidate_ids) != {target}:
        return result
    fallback_registry = CardPlanRegistry(
        source_root=registry.source_root,
        disabled_provider_ids=tuple(registry.disabled_provider_ids),
        disabled_template_ids=tuple(registry.disabled_template_ids),
        enable_fusion_ball=enable_fusion_ball,
        enabled_calendar_fallback_template_ids=(target,),
    )
    if not fallback_registry.template_is_enabled(target):
        return result
    try:
        found = search_template_variants(
            selection.intent,
            task_spec,
            fallback_registry,
            coverage_bindings,
            card_spec,
            preferred_template_ids=(target,),
        )
        plans = plan_template_candidates(
            selection.intent,
            found,
            task_spec,
            fallback_registry,
            allowed_layout_ids=trusted_template_layout_ids,
        )
    except TemplateRetrievalMiss as exc:
        logger.info(
            "[Template Generation] calendar_list_no_action_fallback selected=False "
            f"template_id={target} reason={exc}"
        )
        return result
    if selection.intent is not intent:
        logger.info(
            "[Template Generation] calendar_list_no_action_fallback expanded=True "
            f"template_id={target} "
            f"original_fields={intent.required_output_fields_by_capability} "
            f"expanded_fields={selection.intent.required_output_fields_by_capability}"
        )
    result = CalendarNoActionFallback(selection.intent, fallback_registry, found, plans)
    return result


def _select_recent_summary_shape(
    intent: TemplateSearchIntent,
    query: str,
    task_spec: TaskSpec,
    binding: CandidateDataBinding,
    registry: CardPlanRegistry,
) -> _ListSelection | None:
    """仅单项投影的数量/时间/备注摘要，沿用模板固定的首项范围标识。"""
    result: _ListSelection | None = None
    if _ALL_EVENTS_QUERY.search(query) or _RECENT_COMPLETE_QUERY.search(query):
        return result
    for match in _QUERY_MATTER_COUNT.finditer(query):
        if not _same_count(match.group(1), 1):
            return result
    requested = frozenset(
        intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    )
    required = {"/eventCount", "/events/0/dtStart", "/events/0/description"}
    title_path = "/events/0/title"
    if not required <= requested <= required | {title_path}:
        return result
    shape = _RECENT_SUMMARY_SHAPE
    if shape.template_id not in registry.templates:
        return result
    if not _complete_list_input(shape, task_spec, binding):
        return result
    title = _task_spec_schema_leaf(
        task_spec.dataModelSchema, f"{binding.writeResultTo.rstrip('/')}{title_path}"
    )
    if title is None or title.get("type") != "string":
        return result
    displayed = _calendar_fail_context_fields(shape.template_id, task_spec, binding, registry)
    if displayed is None or not displayed.issubset(binding.candidateOutputFields):
        return result
    exclusive = _EXCLUSIVE_CONTEXT_QUERY.search(query)
    excluded = _CALENDAR_FAIL_EXCLUDED_CONTEXT_QUERY.search(query)
    if exclusive or excluded:
        if not displayed.issubset(requested):
            return result
    result = _ListSelection(shape, intent)
    return result


def _select_list_shape(intent: TemplateSearchIntent, query: str) -> _ListSelection | None:
    selection = _select_existing_list_shape(intent, query)
    if selection is None:
        selection = _select_three_time_notes_shape(intent, query)
    if selection is None:
        selection = _select_calendar_fail_list_shape(intent)
    return selection


def _select_calendar_fail_list_shape(intent: TemplateSearchIntent) -> _ListSelection | None:
    """只接完整三项详情或同角色的两项时间，不扩张首层的列表范围。"""
    requested = frozenset(
        intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    )
    selection: _ListSelection | None = None
    if requested == _THREE_DETAILS_SHAPE.required_fields():
        selection = _ListSelection(_THREE_DETAILS_SHAPE, intent)
    else:
        roles: dict[str, set[str]] = {"0": set(), "1": set()}
        for path in requested:
            parts = path.split("/")
            if len(parts) != 4 or parts[1] != "events":
                return selection
            selected_roles = roles.get(parts[2])
            if selected_roles is None:
                return selection
            selected_roles.add(parts[3])
        first = roles.get("0", set())
        second = roles.get("1", set())
        allowed = ("title", "dtStart", "dtEnd", "eventLocation")
        if first != second or "dtStart" not in first:
            return selection
        if not first.issubset(allowed):
            return selection
        fields = tuple(field for field in allowed if field in first)
        shape = _ListShape(_TWO_EVENTS_TARGET, 2, fields)
        selection = _ListSelection(shape, intent)
    return selection


def _new_list_context_fits(
    selection: _ListSelection,
    query: str,
    task_spec: TaskSpec,
    binding: CandidateDataBinding,
    registry: CardPlanRegistry,
) -> bool:
    if _TIME_NOTES_FIRST_ONLY_QUERY.search(query):
        return False
    for match in _QUERY_MATTER_COUNT.finditer(query):
        if not _same_count(match.group(1), selection.shape.event_count):
            return False
    displayed = _calendar_fail_context_fields(
        selection.shape.template_id, task_spec, binding, registry
    )
    if displayed is None or not displayed.issubset(binding.candidateOutputFields):
        return False
    exclusive = _EXCLUSIVE_CONTEXT_QUERY.search(query)
    excluded = _CALENDAR_FAIL_EXCLUDED_CONTEXT_QUERY.search(query)
    if exclusive or excluded:
        if not displayed.issubset(selection.shape.required_fields()):
            return False
    return True


def _select_existing_list_shape(intent: TemplateSearchIntent, query: str) -> _ListSelection | None:
    result: _ListSelection | None = None
    original = intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    requested = frozenset(original)
    for shape in _LIST_SHAPES:
        if requested == shape.required_fields():
            return _ListSelection(shape, intent)
    if _ALL_EVENTS_QUERY.search(query) is None:
        return result
    if _QUERY_ROW_LIMIT.search(query):
        return result
    for shape in _LIST_SHAPES:
        if not _uniform_partial_list(requested, shape):
            continue
        expanded = list(original)
        for path in shape.ordered_fields():
            if path not in requested:
                expanded.append(path)
        required = dict(intent.required_output_fields_by_capability)
        required[CALENDAR_CAPABILITY_ID] = tuple(expanded)
        normalized = intent.model_copy(update={"required_output_fields_by_capability": required})
        result = _ListSelection(shape, normalized)
        break
    return result


def _select_three_time_notes_shape(
    intent: TemplateSearchIntent, query: str
) -> _ListSelection | None:
    """只补齐明确逐条的时间和备注；候选标题、结束时间不变成额外展示。"""
    result: _ListSelection | None = None
    if not (_ALL_EVENTS_QUERY.search(query) or _TIME_NOTES_ALL_QUERY.search(query)):
        return result
    if _QUERY_ROW_LIMIT.search(query) or _TIME_NOTES_FIRST_ONLY_QUERY.search(query):
        return result
    if _TIME_NOTES_NEGATED_LIST_QUERY.search(query):
        return result
    original = intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    requested = frozenset(original)
    shape = _THREE_TIME_NOTES_SHAPE
    if requested == shape.required_fields():
        return _ListSelection(shape, intent)
    if not _uniform_partial_list(requested, shape):
        return result
    expanded = list(original)
    for path in shape.ordered_fields():
        if path not in requested:
            expanded.append(path)
    required = dict(intent.required_output_fields_by_capability)
    required[CALENDAR_CAPABILITY_ID] = tuple(expanded)
    normalized = intent.model_copy(update={"required_output_fields_by_capability": required})
    result = _ListSelection(shape, normalized)
    return result


def _uniform_partial_list(requested: frozenset[str], shape: _ListShape) -> bool:
    if not requested < shape.required_fields():
        return False
    if shape.with_count and "/eventCount" not in requested:
        return False
    selected_roles: dict[str, set[str]] = {}
    for path in requested:
        if path == "/eventCount":
            continue
        parts = path.split("/")
        # 真子集检查已经保证是本形态中的 /events/{index}/{field} 路径。
        selected_roles.setdefault(parts[2], set()).add(parts[3])
    if not selected_roles:
        return False
    expected_roles = set(shape.event_fields)
    return all(roles == expected_roles for roles in selected_roles.values())


def _complete_list_input(
    shape: _ListShape,
    task_spec: TaskSpec,
    binding: CandidateDataBinding,
) -> bool:
    candidates = set(binding.candidateOutputFields)
    if not shape.required_fields().issubset(candidates):
        return False
    candidate_indices: set[int] = set()
    for path in candidates:
        if path != "/events" and not path.startswith("/events/"):
            continue
        match = _EVENT_PATH.fullmatch(path)
        if match is None:
            return False
        candidate_indices.add(int(match.group(1)))
    if candidate_indices != set(range(shape.event_count)):
        return False
    provider = _provider_schema(task_spec.dataModelSchema, binding.writeResultTo)
    if provider is None:
        return False
    events = provider.get("events")
    if not isinstance(events, list) or len(events) != shape.event_count:
        return False
    # eventCount 的样例是展示数据，不能证明数组条数；字段类型由正式 Search 再校验。
    return all(isinstance(event, dict) for event in events)


def _provider_schema(schema: dict[str, Any], root: str) -> dict[str, Any] | None:
    result: dict[str, Any] | None = None
    parts = parse_json_pointer(root)
    if parts is None:
        return result
    current: Any = schema
    for part in parts:
        if not isinstance(current, dict):
            return result
        current = current.get(part)
    if isinstance(current, dict):
        result = current
    return result


def _query_count_fits(query: str, event_count: int) -> bool:
    for match in _QUERY_EVENT_COUNT.finditer(query):
        if not _same_count(match.group(1), event_count):
            return False
    for match in _QUERY_ROW_LIMIT.finditer(query):
        count = match.group(1)
        if count is None or not _same_count(count, event_count):
            return False
    return True


def _same_count(raw: str, event_count: int) -> bool:
    chinese_counts = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4}
    # 五及以上的中文数量均超过本分支容量；不把“未来七天”当作日程条数。
    if raw.isascii() and raw.isdigit():
        return raw.lstrip("0") == str(event_count)
    return chinese_counts.get(raw) == event_count
