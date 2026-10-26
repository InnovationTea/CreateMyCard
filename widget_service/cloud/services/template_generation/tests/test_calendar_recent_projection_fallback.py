"""只有首项数据的近期日程摘要须标明范围，并保留明确的列表与授权边界。"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

import pytest

from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_list_no_action_policy import (
    plan_calendar_list_no_action_fallback,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import TemplateRetrievalMiss
from services.template_generation.tests.test_calendar_additional_no_action_fallback import (
    _old_plans,
    _pipeline_registry,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_TITLE = "/events/0/title"
_START = "/events/0/dtStart"
_NOTES = "/events/0/description"
_FIELDS = ("/eventCount", _START, _NOTES)
_TARGET = "ScheduleOverviewEventCountDetailsWideFull@1"
_LAYOUT = "WideFullOnlyLayout@1"
_VIEW = "event.viewCalendarEvent"
_QUERY = "显示今天有几条日程，各是几点、有无备注"


@lru_cache(maxsize=4)
def _registry(**kwargs: Any) -> CardPlanRegistry:
    return CardPlanRegistry(**kwargs)


def _case(*, selected_title: bool = False, view_candidate: bool = False) -> CalendarInputs:
    task, bindings, card, intent = _inputs((*_FIELDS, _TITLE), view_candidate=view_candidate)
    task = task.model_copy(update={"size": "2x4", "userQuery": _QUERY})
    card["suggestSize"] = "2x4"
    requested = (*_FIELDS, _TITLE) if selected_title else _FIELDS
    intent = intent.model_copy(
        update={
            "required_output_fields_by_capability": {_CAP: requested},
            "allow_calendar_view_fallback": False,
        }
    )
    return CalendarInputs(task, bindings, card, intent)


def _provider(inputs: CalendarInputs) -> dict[str, Any]:
    data = inputs.task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    provider = data.get("calendar")
    assert isinstance(provider, dict)
    return provider


def _rows(inputs: CalendarInputs) -> list[dict[str, Any]]:
    rows = _provider(inputs).get("events")
    assert isinstance(rows, list)
    return rows


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    original = deepcopy(inputs)
    result = plan_calendar_list_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs
    )
    assert inputs == original
    return result


async def _compile(inputs: CalendarInputs, target: str) -> Any:
    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("{_LAYOUT}",{{}},Template("{target}",{{}}));'

    return await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())


@pytest.mark.parametrize("selected_title", (False, True))
@pytest.mark.parametrize("view_candidate", (False, True))
@pytest.mark.asyncio
async def test_first_event_summary_compiles_after_miss_with_visible_scope_and_total(
    monkeypatch: pytest.MonkeyPatch, selected_title: bool, view_candidate: bool
) -> None:
    inputs = _case(selected_title=selected_title, view_candidate=view_candidate)
    original = deepcopy(inputs)
    registry = _registry()
    with pytest.raises(TemplateRetrievalMiss):
        _old_plans(inputs, registry)
    assert (
        plan_calendar_no_action_fallback(
            inputs.intent, inputs.task, registry, inputs.bindings, inputs.card
        )
        is None
    )
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent == inputs.intent
    assert result.plans[0].business_slots[0].template_id == _TARGET
    assert result.plans[0].action_assignments == ()
    _pipeline_registry(monkeypatch, registry)
    calls: list[Any] = []

    def record(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return plan_calendar_list_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", record)
    output = await _compile(inputs, _TARGET)
    assert calls == [inputs.intent]
    assert _TARGET in output.template_ids
    assert "首项：" in output.a2ui
    assert "首项备注：" in output.a2ui
    for path in (*_FIELDS, _TITLE):
        assert f"/data/calendar{path}" in output.a2ui
    assert "/events/1/" not in output.a2ui
    assert output.projected_task_spec.eventCandidates == []
    assert '"Button"' not in output.a2ui
    assert "clickToIntent" not in output.a2ui
    assert inputs == original


@pytest.mark.parametrize("sample_count", (0, 1, 8))
def test_total_sample_value_does_not_invent_list_entries(sample_count: int) -> None:
    inputs = _case()
    count = _provider(inputs).get("eventCount")
    assert isinstance(count, dict)
    count["sampleValue"] = sample_count
    result = _fallback(inputs, _registry())
    assert result is not None
    assert result.intent.required_output_fields_by_capability.get(_CAP) == _FIELDS
    assert len(_rows(inputs)) == 1


@pytest.mark.parametrize(
    "query",
    (
        "显示今天全部日程的数量、开始时间和备注",
        "完整显示日程列表及各条时间和备注",
        "显示每条日程的时间和备注，并显示数量",
        "逐条展示日程时间和备注，并显示数量",
        "逐项展示日程时间和备注，并显示数量",
        "显示日程各自的时间和备注，并显示数量",
        "显示两条日程的开始时间、备注和数量",
        "显示3场会议的开始时间、备注和数量",
        "显示两件事的开始时间、备注和日程数量",
        "只显示日程数量、开始时间和备注",
        "显示日程数量、开始时间和备注，不要标题",
        "显示日程数量、开始时间和备注，不要只显示首条",
        "显示日程数量、开始时间和备注，不允许仅显示首条",
        "显示日程数量、开始时间和备注全文，不要省略",
        "显示日程数量、开始时间和备注，并打开日历",
    ),
)
def test_summary_does_not_replace_explicit_list_scope_or_excluded_content(query: str) -> None:
    inputs = _case()
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, _registry()) is None


@pytest.mark.parametrize(
    "reason",
    (
        "title_not_authorized",
        "title_absent",
        "title_bad_type",
        "start_not_authorized",
        "notes_not_authorized",
        "count_not_authorized",
        "extra_candidate_index",
        "extra_schema_index",
        "schema_gap",
        "wrong_size",
        "selected_action",
        "wrong_root",
        "extra_binding",
        "extra_required",
    ),
)
def test_summary_preserves_typed_schema_candidate_scope_and_original_intent(reason: str) -> None:
    inputs = _case(view_candidate=True)
    rows = _rows(inputs)
    first_binding = inputs.bindings[0]
    removed = {
        "title_not_authorized": _TITLE,
        "start_not_authorized": _START,
        "notes_not_authorized": _NOTES,
        "count_not_authorized": "/eventCount",
    }.get(reason)
    if removed is not None:
        fields = [path for path in first_binding.candidateOutputFields if path != removed]
        inputs = inputs._replace(
            bindings=(first_binding.model_copy(update={"candidateOutputFields": fields}),)
        )
    elif reason == "title_absent":
        rows[0].pop("title")
    elif reason == "title_bad_type":
        rows[0]["title"] = {"type": "array", "items": {"type": "string"}}
    elif reason == "extra_candidate_index":
        fields = [*first_binding.candidateOutputFields, "/events/1/dtStart"]
        inputs = inputs._replace(
            bindings=(first_binding.model_copy(update={"candidateOutputFields": fields}),)
        )
    elif reason == "extra_schema_index":
        rows.append(deepcopy(rows[0]))
    elif reason == "schema_gap":
        rows.insert(0, {})
    elif reason == "wrong_size":
        inputs = inputs._replace(task=inputs.task.model_copy(update={"size": "2x2"}))
    elif reason == "selected_action":
        inputs = inputs._replace(intent=inputs.intent.model_copy(update={"action_ids": (_VIEW,)}))
    elif reason == "wrong_root":
        card_bindings = inputs.card.get("dataBindings")
        assert isinstance(card_bindings, list)
        card_bindings[0]["writeResultTo"] = "/data/otherCalendar"
    elif reason == "extra_binding":
        inputs = inputs._replace(bindings=(*inputs.bindings, first_binding))
    else:
        rows[0]["dtEnd"] = {"type": "string", "sampleValue": "18:00"}
        fields = [*first_binding.candidateOutputFields, "/events/0/dtEnd"]
        binding = first_binding.model_copy(update={"candidateOutputFields": fields})
        intent = inputs.intent.model_copy(
            update={
                "required_output_fields_by_capability": {_CAP: (*_FIELDS, "/events/0/dtEnd")},
            }
        )
        inputs = inputs._replace(bindings=(binding,), intent=intent)
    assert _fallback(inputs, _registry()) is None


@pytest.mark.parametrize(
    "restriction", ("template", "provider", "trusted_template", "trusted_action", "trusted_layout")
)
def test_summary_keeps_provider_controls_and_trusted_selection(restriction: str) -> None:
    registry = _registry()
    kwargs: dict[str, Any] = {}
    if restriction == "template":
        registry = _registry(disabled_template_ids=(_TARGET,))
    elif restriction == "provider":
        registry = _registry(disabled_provider_ids=("com.huawei.calendar.cli",))
    elif restriction == "trusted_template":
        kwargs["trusted_template_candidate_ids"] = ("ScheduleOverviewTitleHero@1",)
    elif restriction == "trusted_action":
        kwargs["trusted_template_action_ids"] = (_VIEW,)
    else:
        kwargs["trusted_template_layout_ids"] = ("SingleFocusLayout@1",)
    assert _fallback(_case(), registry, **kwargs) is None


@pytest.mark.asyncio
async def test_complete_three_event_list_remains_a_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _case()
    rows = _rows(inputs)
    rows[0].pop("title")
    fields = list(_FIELDS)
    for index in (1, 2):
        rows.append(deepcopy(rows[0]))
        fields.extend((f"/events/{index}/dtStart", f"/events/{index}/description"))
    binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": fields})
    inputs = inputs._replace(bindings=(binding,))
    original = deepcopy(inputs)
    result = _fallback(inputs, _registry())
    assert result is not None
    target = "ScheduleOverviewEventCountThreeTimeNotesWideFull@1"
    assert result.plans[0].business_slots[0].template_id == target
    assert result.intent.required_output_fields_by_capability.get(_CAP) == tuple(fields)
    _pipeline_registry(monkeypatch, _registry())
    output = await _compile(inputs, target)
    assert target in output.template_ids
    assert _TARGET not in output.template_ids
    for path in fields:
        assert f"/data/calendar{path}" in output.a2ui
    assert inputs == original


@pytest.mark.asyncio
async def test_existing_single_summary_route_still_precedes_list_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _case()
    inputs = inputs._replace(
        task=inputs.task.model_copy(
            update={
                "userQuery": "显示日程数量以及下一项日程的开始时间和备注",
            }
        )
    )
    original = deepcopy(inputs)
    registry = _registry()
    result = plan_calendar_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card
    )
    assert result is not None
    _pipeline_registry(monkeypatch, registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("原单项路线已成功，不应再尝试列表或首项投影分支")

    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", forbidden)
    output = await _compile(inputs, _TARGET)
    assert _TARGET in output.template_ids
    for path in (*_FIELDS, _TITLE):
        assert f"/data/calendar{path}" in output.a2ui
    assert inputs == original
