"""已有日程路线失败后，仅尝试完整、定长、无动作的日程列表。"""

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
    _NEGATIVE_ACTION,
    CalendarNoActionFallback,
    _single_calendar_request,
)
from .registry import CardPlanRegistry
from .template_plan_planner import plan_template_candidates
from .template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
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
        plans = plan_template_candidates(selection.intent, found, task_spec, fallback_registry)
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


def _select_list_shape(intent: TemplateSearchIntent, query: str) -> _ListSelection | None:
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
