"""日历 Full 扩展模板的检索准入、投影与页眉几何回归。

五个 Full 扩展模板在 3 组 headerLabel（缺省 / 短 / 长）× 日历图标开关
下的完整蓝图渲染已固化为场景金样（Layer C，``calendar_fullext__*``）：
标题文本与缺省文案、layoutWeight 让位、可选 20x20 图标占位及页眉间距由
快照整体冻结。原始模板的整卡 sha256 预览钉死由 Layer A 字节级模板金样
取代，已删除。检索准入与拒绝矩阵、投影集合、动作路由与合同隔离仍为
内联精度断言，保持不变。
"""

from __future__ import annotations

from typing import Any, NamedTuple

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced import content_selectors
from services.template_generation.engine.cardplan.calendar_action_policy import (
    resolve_calendar_view_fallback,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_calendar_requested_case_templates import (
    _expanded,
    _node_payload,
    _schema,
    _template_slug,
    _walk,
)

_CAPABILITY = "GetCalendarEvents"
_VIEW = "event.viewCalendarEvent"
_CASES = {
    "NextEventLocationFull": (
        "/events/0/title", "/events/0/dtStart", "/events/0/eventLocation",
    ),
    "TimezoneTimeFull": (
        "/events/0/title", "/events/0/timeZone", "/events/0/dtStart", "/events/0/dtEnd",
    ),
    "DateLocationFull": (
        "/events/0/title", "/events/0/startDate", "/events/0/eventLocation",
    ),
    "ReminderDetailsFull": (
        "/events/0/senderName", "/events/0/importantEventType", "/events/0/remindTime/0",
        "/updatedAt",
    ),
}
_HEADER_SUFFIXES = (
    "TimezoneTimeFull", "DateLocationFull", "ReminderDetailsFull",
    "LocationDescriptionEndFull", "NextEventLocationFull",
)
_HEADER_LABELS = (
    (None, "default"),
    ("我的日程详情", "short"),
    ("跨时区项目联合评审及下一阶段计划安排", "long"),
)


class CalendarInputs(NamedTuple):
    task: TaskSpec
    bindings: tuple[CandidateDataBinding, ...]
    card: dict[str, Any]
    intent: TemplateSearchIntent


def _inputs(fields: tuple[str, ...], *, view_candidate: bool = False) -> CalendarInputs:
    data_fields = (*fields, "/events/0/entityId") if view_candidate else fields
    events = [EventAction(
        id=_VIEW, call="clickToIntent", args={"intentName": "ViewCalendarEvent", "params": {
            "entityId": "{{ ${/data/calendar/events/0/entityId} }}",
        }},
    )] if view_candidate else []
    task = TaskSpec(
        userQuery="展示日程字段", size="2x2", dataModelSchema=_schema(data_fields),
        eventCandidates=events,
    )
    bindings = (CandidateDataBinding(
        capabilityId=_CAPABILITY, writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    ),)
    card = {
        "title": "日程详情", "description": "展示日程字段", "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": _CAPABILITY, "writeResultTo": "/data/calendar"}],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={_CAPABILITY: fields}, allowCalendarViewFallback=True,
    )
    return CalendarInputs(task, bindings, card, intent)


def _header_payload(suffix: str) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for header_label, label_slug in _HEADER_LABELS:
        for with_icon in (False, True):
            props: dict[str, Any] = {}
            if header_label is not None:
                props["headerLabel"] = header_label
            if with_icon:
                props["calendarIcon"] = "calendar"
            root = _expanded(f"ScheduleOverview{suffix}@1", props=props)
            variants[f"{label_slug}__{'icon' if with_icon else 'no_icon'}"] = {
                "props": props,
                "root": _node_payload(root),
            }
    return {"templateId": f"ScheduleOverview{suffix}@1", "variants": variants}


def _register_header_scenarios() -> None:
    for suffix in _HEADER_SUFFIXES:
        def _build(suffix: str = suffix) -> dict[str, Any]:
            return _header_payload(suffix)

        scenario(f"calendar_fullext__{_template_slug(suffix)}")(_build)


_register_header_scenarios()


@pytest.mark.parametrize("suffix", _HEADER_SUFFIXES)
def test_full_extension_headers_match_golden_scenarios(suffix: str) -> None:
    assert_golden_scenario(f"calendar_fullext__{_template_slug(suffix)}")


def test_date_location_projection_only_runs_when_existing_shapes_miss() -> None:
    fields = _CASES.get("DateLocationFull")
    assert fields is not None
    schema = _schema(fields)
    selected = content_selectors.extract_schedule_template_variant_fields(schema)
    assert set(selected) == {"title", "startDate", "eventLocation"}
    old_shape = _schema((*fields, "/events/0/dtStart"))
    existing = content_selectors.extract_schedule_template_variant_fields(old_shape)
    assert set(existing) == {"eventLocation", "dtStart"}


@pytest.mark.parametrize("suffix", tuple(_CASES))
@pytest.mark.parametrize("view_candidate", [False, True])
@pytest.mark.asyncio
async def test_full_extensions_plan_and_compile_all_requested_fields_without_default_button(
    monkeypatch: pytest.MonkeyPatch, suffix: str, view_candidate: bool,
) -> None:
    fields = _CASES.get(suffix)
    assert fields is not None
    task, bindings, card, intent = _inputs(fields, view_candidate=view_candidate)
    registry = get_cardplan_registry()
    found = search_template_variants(intent, task, registry, bindings, card)
    resolved = resolve_calendar_view_fallback(intent, found, task, registry)
    assert resolved.action_ids == ()
    plans = plan_template_candidates(resolved, found, task, registry)
    target = f"ScheduleOverview{suffix}@1"
    assert any(plan.business_slots[0].template_id == target for plan in plans)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("SingleFocusLayout@1",{{}},Template("{target}",{{}}));'

    output = await pipeline.generate_template_a2ui(task, card, bindings, Model())
    assert target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"call":"clickToIntent"' not in output.a2ui
    for field in fields:
        assert f"/data/calendar{field}" in output.a2ui


_MISSING_CASES = []
for _suffix, _fields in _CASES.items():
    for _missing in _fields:
        _MISSING_CASES.append((_suffix, _fields, _missing))


@pytest.mark.parametrize(("suffix", "fields", "missing"), _MISSING_CASES)
def test_new_full_cannot_admit_incomplete_field_combinations(
    suffix: str, fields: tuple[str, ...], missing: str,
) -> None:
    remaining = tuple(field for field in fields if field != missing)
    task, bindings, card, intent = _inputs(remaining)
    registry = get_cardplan_registry()
    # Explicitly asking for a missing field must still be rejected.
    original_binding = bindings[0].model_copy(update={"candidateOutputFields": list(fields)})
    original_intent = intent.model_copy(update={
        "required_output_fields_by_capability": {_CAPABILITY: fields},
    })
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(original_intent, task, registry, (original_binding,), card)
    try:
        found = search_template_variants(intent, task, registry, bindings, card)
    except TemplateRetrievalMiss:
        return
    for group in found.business_candidates:
        assert all(c.template_id != f"ScheduleOverview{suffix}@1" for c in group.candidates)


@pytest.mark.parametrize("with_end", [False, True])
def test_next_event_full_only_uses_else_when_end_binding_is_absent(with_end: bool) -> None:
    omitted = frozenset() if with_end else frozenset({"end"})
    root = _expanded("ScheduleOverviewNextEventLocationFull@1", omitted=omitted)
    values = [node.values[0] for node in _walk(root) if node.component_type == "Text"]
    time = next(value for value in values if isinstance(value, str) and "dtStart" in value)
    assert ("dtEnd" in time) is with_end
    assert (" - " in time) is with_end
    assert any("eventLocation" in str(value) for value in values)


def test_reminder_details_explicit_action_keeps_the_existing_hero_route() -> None:
    fields = _CASES.get("ReminderDetailsFull")
    assert fields is not None
    task, bindings, card, intent = _inputs(fields, view_candidate=True)
    intent = intent.model_copy(update={"action_ids": (_VIEW,)})
    registry = get_cardplan_registry()
    found = search_template_variants(intent, task, registry, bindings, card)
    plans = plan_template_candidates(intent, found, task, registry)
    assert all(plan.layout_template_id == "HeroActionLayout@1" for plan in plans)
    assert all(
        plan.business_slots[0].template_id == "ScheduleOverviewReminderDetailsHero@1"
        for plan in plans
    )


def test_different_full_contracts_cannot_merge_field_coverage() -> None:
    fields = (
        "/events/0/title", "/events/0/startDate", "/events/0/eventLocation",
        "/events/0/timeZone", "/events/0/senderName", "/events/0/importantEventType",
        "/events/0/remindTime/0", "/updatedAt",
    )
    task, bindings, card, intent = _inputs(fields)
    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        search_template_variants(intent, task, get_cardplan_registry(), bindings, card)
