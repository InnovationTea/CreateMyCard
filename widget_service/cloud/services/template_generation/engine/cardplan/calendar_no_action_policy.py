"""旧检索或规划失败后，隔离尝试单条无动作日程的补充 Full。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.logger import logger
from models.generation import CandidateDataBinding, TaskSpec

from .calendar_field_paths import (
    CALENDAR_CAPABILITY_ID,
    calendar_wide_fallback_reminder_aliases,
)
from .models import TemplatePlan
from .registry import CardPlanRegistry
from .template_plan_planner import plan_template_candidates
from .template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    TemplateSearchResult,
    normalize_calendar_reminder_intent,
    search_template_variants,
)

_EVENT = "/events/0/"
_NEGATIVE_ACTION = re.compile(
    r"(?:不要|无需|不需要|不提供|不带|不加|不显示|不允许|禁止)(?:任何)?"
    r"(?:(?:查看(?:日程)?详情|打开(?:日历|日程))(?:按钮)?|按钮|操作|交互|点击|跳转)"
)
_ACTION_QUERY = re.compile(
    r"按钮|点击|点按|点一下|轻触|点开(?!始|会)|单击|双击|长按|一键|跳转|直达|跳到|打开|"
    r"进入|入会|拨打|打电话|查看详情|切换|开启|关闭|"
    r"(?:创建|新建|删除|修改|编辑|添加|取消)"
    r"(?:(?:一下|一个|一条|这个|这条|这项|那个|那条|该|新的|今天的|明天的)){0,3}"
    r"(?:日程|会议|提醒)(?!的?卡片)|设置(?:提前.{0,8}|一个|新的|日程|会议)?提醒|"
    r"\b(?:button|click|tap|open|join|switch|enable|disable)\b",
    re.IGNORECASE,
)
_MULTIPLE_EVENTS_QUERY = re.compile(
    r"每(?:个|条|项|场)|各(?:个|条|项|场)|(?:全部|所有)(?:的)?(?:日程|会议|活动|安排)|"
    r"(?:日程|会议|活动|安排)(?:完整)?列表|完整列表|分别|逐条|一一|各是|"
    r"(?:全部|所有)(?:的)?(?:提前)?提醒|提醒(?:时间|设置)?列表|"
    r"[两二三四五六七八九十\d]+(?:个|条|项|场)(?:日程|会议|活动|安排)|"
    r"\b(?:each|every|all\s+(?:events|meetings)|list\s+of)\b",
    re.IGNORECASE,
)
_ADDITIONAL_MULTIPLE_EVENTS_QUERY = re.compile(
    r"各(?:日程|会议|活动|安排)|"
    r"[两二三四五六七八九十\d]+(?:条|项)"
    r"(?:日程|会议|活动|安排|都|的(?:日期|标题|时间|地点|提醒)|(?=[，。；、\s]|$))"
)


@dataclass(frozen=True)
class CalendarNoActionFallback:
    intent: TemplateSearchIntent
    registry: CardPlanRegistry
    search_result: TemplateSearchResult
    plans: tuple[TemplatePlan, ...]


def plan_calendar_no_action_fallback(
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
    """仅重试一次；保留全部首层字段和动作，不合适时保留原失败。"""
    result: CalendarNoActionFallback | None = None
    if not _single_calendar_request(intent, coverage_bindings, card_spec):
        return result
    if intent.action_ids or trusted_template_action_ids:
        return result
    query = _NEGATIVE_ACTION.sub("", task_spec.userQuery)
    if _ACTION_QUERY.search(query) or _MULTIPLE_EVENTS_QUERY.search(query):
        return result
    normalized = normalize_calendar_reminder_intent(intent, task_spec, coverage_bindings)
    normalized, bindings = _wide_reminder_inputs(normalized, task_spec, coverage_bindings)
    requested = normalized.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    target = _fallback_template(task_spec.size, frozenset(requested))
    if target is None and not _ADDITIONAL_MULTIPLE_EVENTS_QUERY.search(query):
        target = _additional_fallback_template(task_spec.size, frozenset(requested))
    if target is None or target not in registry.templates:
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
            normalized,
            task_spec,
            fallback_registry,
            bindings,
            card_spec,
            preferred_template_ids=(target,),
        )
        plans = plan_template_candidates(normalized, found, task_spec, fallback_registry)
    except TemplateRetrievalMiss as exc:
        # 受控重试未能覆盖原意图，由调用方继续报告原 Search/Planner 失败。
        logger.info(
            "[Template Generation] calendar_no_action_fallback selected=False "
            f"template_id={target} reason={exc}"
        )
        return result
    result = CalendarNoActionFallback(normalized, fallback_registry, found, plans)
    return result


def _single_calendar_request(
    intent: TemplateSearchIntent,
    bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
) -> bool:
    if tuple(intent.required_output_fields_by_capability) != (CALENDAR_CAPABILITY_ID,):
        return False
    if len(bindings) != 1 or bindings[0].capabilityId != CALENDAR_CAPABILITY_ID:
        return False
    card_bindings = card_spec.get("dataBindings")
    if not isinstance(card_bindings, list) or len(card_bindings) != 1:
        return False
    binding = card_bindings[0]
    if not isinstance(binding, dict):
        return False
    return (
        binding.get("capabilityId") == CALENDAR_CAPABILITY_ID
        and binding.get("writeResultTo") == bindings[0].writeResultTo
    )


def _wide_reminder_inputs(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    bindings: tuple[CandidateDataBinding, ...],
) -> tuple[TemplateSearchIntent, tuple[CandidateDataBinding, ...]]:
    fields = intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID, ())
    aliases = calendar_wide_fallback_reminder_aliases(task_spec, bindings, fields)
    if not aliases:
        return intent, bindings
    required = dict(intent.required_output_fields_by_capability)
    normalized_fields: list[str] = []
    for path in fields:
        canonical = aliases.get(path, path)
        if canonical not in normalized_fields:
            normalized_fields.append(canonical)
    required[CALENDAR_CAPABILITY_ID] = tuple(normalized_fields)
    primary = dict(intent.primary_output_field_by_capability)
    focus = primary.get(CALENDAR_CAPABILITY_ID)
    if focus in aliases:
        primary[CALENDAR_CAPABILITY_ID] = aliases[focus]
    normalized = intent.model_copy(
        update={
            "required_output_fields_by_capability": required,
            "primary_output_field_by_capability": primary,
        }
    )
    candidate_fields: list[str] = []
    for path in bindings[0].candidateOutputFields:
        canonical = aliases.get(path, path)
        if canonical not in candidate_fields:
            candidate_fields.append(canonical)
    binding = bindings[0].model_copy(update={"candidateOutputFields": candidate_fields})
    return normalized, (binding,)


def _fallback_template(size: str, requested: frozenset[str]) -> str | None:
    target: str | None = None
    title = f"{_EVENT}title"
    start = f"{_EVENT}dtStart"
    reminder = f"{_EVENT}remindTime/0"
    if size == "2x2":
        required = frozenset({f"{_EVENT}senderName", reminder})
        if required <= requested <= required | {title}:
            target = "ScheduleOverviewSourceReminderFull@1"
    elif size == "2x4":
        variants = (
            (
                "ScheduleOverviewTimezoneWideFull@1",
                frozenset({f"{_EVENT}timeZone", start, f"{_EVENT}eventLocation"}),
                frozenset({title, f"{_EVENT}dtEnd"}),
            ),
            (
                "ScheduleOverviewEventCountDetailsWideFull@1",
                frozenset({"/eventCount", f"{_EVENT}description"}),
                frozenset({title, start}),
            ),
            (
                "ScheduleOverviewReminderWideFull@1",
                frozenset({start, reminder}),
                frozenset({title}),
            ),
        )
        for wire_id, required, optional in variants:
            if required <= requested <= required | optional:
                target = wire_id
                break
    return target


def _additional_fallback_template(size: str, requested: frozenset[str]) -> str | None:
    """旧形态优先后，按尺寸与完整字段集合选择新增的隔离变体。"""
    title = f"{_EVENT}title"
    start = f"{_EVENT}dtStart"
    end = f"{_EVENT}dtEnd"
    date = f"{_EVENT}startDate"
    location = f"{_EVENT}eventLocation"
    all_day = f"{_EVENT}isAllDay"
    reminder = f"{_EVENT}remindTime/0"
    variants = (
        ("2x2", "TitleStartFull", {title, start}, set()),
        ("2x2", "ReminderStartFull", {start, reminder}, {title}),
        ("2x2", "DateAllDayFull", {date, title, all_day}, set()),
        ("2x2", "DateEndFull", {title, date, end}, set()),
        ("2x2", "AllDayLocationFull", {all_day, location}, {title}),
        ("2x2", "DateStartLocationFull", {date, start, location}, {title, end}),
        (
            "2x4",
            "ReminderDetailsWideFull",
            {f"{_EVENT}senderName", f"{_EVENT}importantEventType", reminder, "/updatedAt"},
            set(),
        ),
        ("2x4", "DatedMeetingWideFull", {date, title, start, end, location}, set()),
    )
    target: str | None = None
    for card_size, suffix, required, optional in variants:
        if size == card_size and required <= requested <= required | optional:
            target = f"ScheduleOverview{suffix}@1"
            break
    return target
