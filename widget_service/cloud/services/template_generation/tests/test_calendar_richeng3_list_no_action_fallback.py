"""三项时间备注列表只补齐明确逐条需求，不删字段、动作或真实条目。"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_list_no_action_policy import (
    plan_calendar_list_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    build_template_retrieval_prompt,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs
from services.template_generation.tests.test_calendar_list_no_action_fallback import (
    _case,
    _rows,
    _with_requested,
)

_CAP = "GetCalendarEvents"
_ROOT = "/data/calendar"
_TARGET = "ScheduleOverviewEventCountThreeTimeNotesWideFull@1"
_QUERY = "今天排得满满的，帮我弄个卡片看看有几件事、各是几点、有没有备注"
_FIRST_FIELDS = ("/eventCount", "/events/0/dtStart", "/events/0/description")
_ALL_FIELDS = (
    "/eventCount",
    "/events/0/dtStart",
    "/events/0/description",
    "/events/1/dtStart",
    "/events/1/description",
    "/events/2/dtStart",
    "/events/2/description",
)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _inputs(*, complete: bool = False, candidate_action: bool = True) -> CalendarInputs:
    inputs = _case()
    task = inputs.task.model_copy(update={"userQuery": _QUERY})
    if not candidate_action:
        task = task.model_copy(update={"eventCandidates": []})
    fields = _ALL_FIELDS if complete else _FIRST_FIELDS
    inputs = _with_requested(inputs._replace(task=task), fields)
    intent = inputs.intent.model_copy(update={"allow_calendar_view_fallback": True})
    return inputs._replace(intent=intent)


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    return plan_calendar_list_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs
    )


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize("candidate_action", [False, True])
def test_time_notes_complete_only_authorized_rows_and_preserve_input(
    registry: CardPlanRegistry, complete: bool, candidate_action: bool
) -> None:
    inputs = _inputs(complete=complete, candidate_action=candidate_action)
    snapshot = copy.deepcopy(inputs)
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.registry.enabled_calendar_fallback_template_ids == {_TARGET}
    assert result.intent.required_output_fields_by_capability.get(_CAP) == _ALL_FIELDS
    assert (result.intent is inputs.intent) is complete
    assert result.intent.allow_calendar_view_fallback is True
    assert result.plans
    assert inputs == snapshot


@pytest.mark.parametrize(
    "query",
    [
        _QUERY,
        "看看有几件事、各条日程的开始时间和备注，不要按钮",
        "展示数量，逐条显示日程开始时间和备注",
        "显示所有日程的数量、时间和备注",
    ],
)
def test_explicit_each_row_wording_allows_completion(
    registry: CardPlanRegistry, query: str
) -> None:
    inputs = _inputs()
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is not None


@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize(
    "query",
    [
        "看看有几件事、几点、有没有备注",
        "各条日程的时间和备注，只要前三条",
        "各条日程的时间和备注，只看首项",
        "各条日程的时间和备注，仅首",
        "各条日程的时间和备注，只看第一条",
        "各条日程的时间和备注，只要一条日程",
        "各条日程的时间和备注，仅下一个日程",
        "各条日程的时间和备注，只看最近的日程",
        "不要逐条显示，看看数量、开始时间和备注",
        "不用列出全部日程，只看数量、开始时间和备注",
        "各条日程的时间和备注，别看各条",
        "各条日程的时间和备注，不要列表",
        "各条日程的时间和备注，别用列表",
        "显示四条日程各自的时间和备注",
        "各条日程的时间和备注，点击打开日历",
        "各条日程的时间和备注，并编辑日程",
        "各条日程的时间和备注全文",
    ],
)
def test_query_limits_and_operations_cannot_be_ignored(
    registry: CardPlanRegistry, query: str, complete: bool
) -> None:
    inputs = _inputs(complete=complete)
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "fields",
    [
        ("/events/0/dtStart", "/events/0/description"),
        ("/eventCount", "/events/0/dtStart", "/events/1/description"),
        (*_FIRST_FIELDS, "/events/0/title"),
        (*_FIRST_FIELDS, "/events/0/dtEnd"),
        (*_ALL_FIELDS, "/events/3/description"),
    ],
)
def test_missing_count_nonuniform_roles_and_extra_selected_fields_are_not_rewritten(
    registry: CardPlanRegistry, fields: tuple[str, ...]
) -> None:
    inputs = _with_requested(_inputs(), fields)
    snapshot = copy.deepcopy(inputs)
    assert _fallback(inputs, registry) is None
    assert inputs == snapshot


@pytest.mark.parametrize(
    "variant",
    [
        "schema_row_missing",
        "schema_row_extra",
        "candidate_row_extra",
        "candidate_gap",
        "candidate_parent",
        "candidate_field_missing",
        "candidate_count_missing",
        "schema_field_missing",
        "schema_count_missing",
        "schema_type",
        "schema_untyped",
        "schema_scalar",
    ],
)
def test_three_real_typed_rows_and_every_candidate_are_required(
    registry: CardPlanRegistry, variant: str
) -> None:
    inputs = _inputs()
    rows = _rows(inputs)
    candidates = list(inputs.bindings[0].candidateOutputFields)
    if variant == "schema_row_missing":
        rows.pop()
    elif variant == "schema_row_extra":
        rows.append(copy.deepcopy(rows[0]))
    elif variant == "candidate_row_extra":
        candidates.append("/events/3/description")
    elif variant == "candidate_gap":
        candidates = [path.replace("/events/2/", "/events/3/") for path in candidates]
    elif variant == "candidate_parent":
        candidates.append("/events")
    elif variant == "candidate_field_missing":
        candidates.remove("/events/2/dtStart")
    elif variant == "candidate_count_missing":
        candidates.remove("/eventCount")
    elif variant == "schema_field_missing":
        rows[1].pop("description")
    elif variant == "schema_count_missing":
        data = inputs.task.dataModelSchema.get("data")
        assert isinstance(data, dict)
        provider = data.get("calendar")
        assert isinstance(provider, dict)
        provider.pop("eventCount")
    elif variant == "schema_type":
        rows[1]["dtStart"] = {"type": "integer", "sampleValue": 3}
    elif variant == "schema_untyped":
        rows[1]["dtStart"] = {"sampleValue": "14:00"}
    else:
        rows[1]["dtStart"] = "14:00"
    binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": candidates})
    inputs = inputs._replace(bindings=(binding,))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize("variant", ["size", "binding", "intent", "card", "root"])
def test_single_calendar_and_binding_root_cannot_be_bypassed(
    registry: CardPlanRegistry, variant: str
) -> None:
    inputs = _inputs()
    battery = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/battery"
    )
    if variant == "size":
        inputs = inputs._replace(task=inputs.task.model_copy(update={"size": "2x2"}))
    elif variant == "binding":
        inputs = inputs._replace(bindings=(*inputs.bindings, battery))
    elif variant == "intent":
        intent = inputs.intent.model_copy(
            update={
                "required_output_fields_by_capability": {
                    _CAP: _FIRST_FIELDS,
                    "GetPhoneBatteryInfo": ("/level",),
                }
            }
        )
        inputs = inputs._replace(intent=intent)
    elif variant == "card":
        inputs.card["dataBindings"] = [
            {"capabilityId": _CAP, "writeResultTo": _ROOT},
            {"capabilityId": "GetPhoneBatteryInfo", "writeResultTo": "/data/battery"},
        ]
    else:
        inputs.card["dataBindings"] = [{"capabilityId": _CAP, "writeResultTo": "/data/other"}]
    assert _fallback(inputs, registry) is None


def test_trusted_scopes_and_selected_actions_remain_binding(registry: CardPlanRegistry) -> None:
    inputs = _inputs()
    action = "event.viewCalendarEvent"
    selected = inputs.intent.model_copy(update={"action_ids": (action,)})
    assert _fallback(inputs._replace(intent=selected), registry) is None
    assert _fallback(inputs, registry, trusted_template_action_ids=(action,)) is None
    assert (
        _fallback(inputs, registry, trusted_template_candidate_ids=("MeetingWideFull@1",)) is None
    )
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_TARGET, "other")) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_TARGET,)) is not None


@pytest.mark.parametrize("disabled", ["template", "provider"])
def test_disabled_configuration_cannot_be_bypassed(disabled: str) -> None:
    kwargs: dict[str, Any] = {"disabled_template_ids": (_TARGET,)}
    if disabled == "provider":
        kwargs = {"disabled_provider_ids": ("com.huawei.calendar.cli",)}
    assert _fallback(_inputs(), CardPlanRegistry(**kwargs)) is None


def test_new_template_is_hidden_from_default_prompt(registry: CardPlanRegistry) -> None:
    inputs = _inputs()
    prompt = str(build_template_retrieval_prompt(inputs.task, registry, inputs.bindings))
    assert not registry.template_is_enabled(_TARGET)
    assert _TARGET not in prompt


@pytest.mark.asyncio
async def test_pipeline_compiles_count_and_all_three_rows_without_candidate_extras(
    monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry
) -> None:
    inputs = _inputs()
    snapshot = copy.deepcopy(inputs)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search"
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)
    calls: list[Any] = []

    def record_fallback(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return plan_calendar_list_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", record_fallback)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("WideFullOnlyLayout@1",{{}},Template("{_TARGET}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task, inputs.card, inputs.bindings, Model()
    )
    assert calls == [inputs.intent]
    assert _TARGET in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"Button"' not in output.a2ui
    assert '"onClick"' not in output.a2ui
    for path in _ALL_FIELDS:
        assert f"{_ROOT}{path}" in output.a2ui
    for index in range(3):
        assert f"{_ROOT}/events/{index}/title" not in output.a2ui
        assert f"{_ROOT}/events/{index}/dtEnd" not in output.a2ui
    assert inputs == snapshot
