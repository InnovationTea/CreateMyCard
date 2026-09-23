from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced import content_selectors
from services.template_generation.engine.cardplan import preview_dataset
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
from services.template_generation.tests.test_calendar_requested_case_templates import (
    _expanded,
    _options,
    _schema,
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
_SNAPSHOTS = json.loads(
    (Path(__file__).parent / "fixtures/calendar_existing_preview_hashes.json").read_text(
        encoding="utf-8",
    )
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


@pytest.mark.parametrize("template_id", tuple(_SNAPSHOTS))
def test_original_templates_match_approved_previews(
    monkeypatch: pytest.MonkeyPatch, template_id: str,
) -> None:
    registry = get_cardplan_registry(True)
    definition = registry.require_template(template_id)
    index = list(_SNAPSHOTS).index(template_id)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    preview = preview_dataset._build_case(f"snapshot-{index}", definition, profile, registry)
    payload = json.dumps(list(preview.messages), ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(payload.encode()).hexdigest() == _SNAPSHOTS.get(template_id)
    schema = preview_dataset._build_data_schema(definition)
    projected = content_selectors.extract_schedule_template_variant_fields(schema)
    with monkeypatch.context() as context:
        context.setattr(content_selectors, "_schedule_date_location_fields", lambda _p: {})
        previous = content_selectors.extract_schedule_template_variant_fields(schema)
    assert projected == previous


def test_date_location_projection_only_runs_when_existing_shapes_miss() -> None:
    fields = _CASES.get("DateLocationFull")
    assert fields is not None
    schema = _schema(fields)
    selected = content_selectors.extract_schedule_template_variant_fields(schema)
    assert set(selected) == {"title", "startDate", "eventLocation"}
    old_shape = _schema((*fields, "/events/0/dtStart"))
    existing = content_selectors.extract_schedule_template_variant_fields(old_shape)
    assert set(existing) == {"eventLocation", "dtStart"}


@pytest.mark.parametrize("suffix", (
    "TimezoneTimeFull", "DateLocationFull", "ReminderDetailsFull",
    "LocationDescriptionEndFull", "NextEventLocationFull",
))
@pytest.mark.parametrize("header_label", [
    None, "我的日程详情", "跨时区项目联合评审及下一阶段计划安排",
])
@pytest.mark.parametrize("with_icon", [False, True])
def test_new_full_headers_reserve_space_for_optional_icon(
    suffix: str, header_label: str | None, with_icon: bool,
) -> None:
    props: dict[str, Any] = {}
    if header_label is not None:
        props["headerLabel"] = header_label
    if with_icon:
        props["calendarIcon"] = "calendar"
    root = _expanded(f"ScheduleOverview{suffix}@1", props=props)
    if suffix == "ReminderDetailsFull":
        header = root.children[0]
        default_label = "日程详情"
    else:
        top = root.children[0]
        assert top.component_type == "Column"
        assert _options(top).get("itemMargin") == 8
        header = top.children[0]
        default_label = "下一个日程"
    assert header.component_type == "Row"
    assert _options(header).get("width") == "matchParent"
    title = header.children[0]
    assert title.component_type == "Text"
    assert title.values[0] == (header_label or default_label)
    # 150vp 卡片内宽只有 126vp；标题必须让出可选图标和间距所占的空间。
    title_options = _options(title)
    assert title_options.get("layoutWeight") == 1
    assert "width" not in title_options
    assert title_options.get("maxLines") == 1
    assert title_options.get("textOverflow") == "ellipsis"
    assert len(header.children) == (2 if with_icon else 1)
    if with_icon:
        icon = header.children[1]
        assert icon.component_type == "Image"
        assert _options(icon).get("width") == _options(icon).get("height") == 20
        assert _options(icon).get("flexShrink") == 0
        assert _options(header).get("itemMargin") == 4


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
