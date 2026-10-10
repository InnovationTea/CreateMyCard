"""日程列表只在原路线失败后补充，且不得遗漏原请求的条目、字段或动作。"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_list_no_action_policy import (
    plan_calendar_list_no_action_fallback,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_ROOT = "/data/calendar"
_VIEW = "event.viewCalendarEvent"
_TIMEZONE = "ScheduleOverviewTimezoneThreeEventsWideFull@1"
_DETAILS = "ScheduleOverviewEventCountFourDetailsWideFull@1"
_NOTES = "ScheduleOverviewEventCountThreeNotesWideFull@1"
_TARGETS = (_TIMEZONE, _DETAILS, _NOTES)
_ROW_VALUES = {
    "title": "项目例会",
    "timeZone": "Asia/Shanghai",
    "dtStart": "14:00",
    "dtEnd": "15:00",
    "eventLocation": "会议室",
    "description": "核对项目进度",
    "entityId": "calendar-event",
}


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _case(target: str = _NOTES, *, extras: bool = True) -> CalendarInputs:
    fields = ("description",)
    count = 3
    query = "展示今天所有日程的数量和各条备注"
    if target == _TIMEZONE:
        fields = ("timeZone", "title", "dtStart", "dtEnd", "eventLocation")
        query = "展示每个日程的时区、标题、时间段和地点"
    elif target == _DETAILS:
        fields = ("title", "dtStart", "description")
        count = 4
        query = "展示今天所有日程的数量、标题、各是几点、有没有备注"
    requested: list[str] = [] if target == _TIMEZONE else ["/eventCount"]
    candidates = list(requested)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        row: dict[str, Any] = {}
        for name, value in _ROW_VALUES.items():
            path = f"/events/{index}/{name}"
            if name in fields:
                requested.append(path)
            if name in fields or extras:
                candidates.append(path)
                row[name] = {"type": "string", "sampleValue": f"{value}{index + 1}"}
        rows.append(row)
    provider: dict[str, Any] = {"events": rows}
    if target != _TIMEZONE:
        # 真实三例也使用通用样例 1；禁止据此裁掉列表中的其余条目。
        provider["eventCount"] = {"type": "integer", "sampleValue": 1}
    task = TaskSpec(
        userQuery=query,
        size="2x4",
        dataModelSchema={"data": {"calendar": provider}},
        eventCandidates=[
            EventAction(
                id=_VIEW,
                call="clickToIntent",
                args={
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": "{{ ${/data/calendar/events/0/entityId} }}"},
                },
            )
        ]
        if extras
        else [],
    )
    binding = CandidateDataBinding(
        capabilityId=_CAP, writeResultTo=_ROOT, candidateOutputFields=candidates
    )
    card = {
        "title": "日程列表",
        "description": query,
        "suggestSize": "2x4",
        "dataBindings": [{"capabilityId": _CAP, "writeResultTo": _ROOT}],
    }
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={_CAP: tuple(requested)})
    return CalendarInputs(task, (binding,), card, intent)


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    return plan_calendar_list_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs
    )


def _rows(inputs: CalendarInputs) -> list[dict[str, Any]]:
    data = inputs.task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    provider = data.get("calendar")
    assert isinstance(provider, dict)
    rows = provider.get("events")
    assert isinstance(rows, list)
    return rows


def _with_requested(inputs: CalendarInputs, fields: tuple[str, ...]) -> CalendarInputs:
    intent = inputs.intent.model_copy(
        update={"required_output_fields_by_capability": {_CAP: fields}}
    )
    return inputs._replace(intent=intent)


@pytest.mark.parametrize("target", _TARGETS)
@pytest.mark.parametrize("extras", [False, True])
def test_exact_lists_preserve_original_intent_and_authorized_fields(
    registry: CardPlanRegistry, target: str, extras: bool
) -> None:
    inputs = _case(target, extras=extras)
    snapshot = copy.deepcopy(inputs)
    assert (
        plan_calendar_no_action_fallback(
            inputs.intent, inputs.task, registry, inputs.bindings, inputs.card
        )
        is None
    )
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent is inputs.intent
    assert result.plans
    assert result.registry.enabled_calendar_fallback_template_ids == {target}
    assert inputs == snapshot


@pytest.mark.parametrize(
    ("target", "first_row_only"),
    [
        (_TIMEZONE, False),
        (_DETAILS, False),
        (_NOTES, False),
        (_TIMEZONE, True),
    ],
)
@pytest.mark.asyncio
async def test_production_pipeline_compiles_every_requested_list_path(
    monkeypatch: pytest.MonkeyPatch,
    registry: CardPlanRegistry,
    target: str,
    first_row_only: bool,
) -> None:
    inputs = _case(target)
    all_fields = inputs.intent.required_output_fields_by_capability.get(_CAP)
    assert all_fields is not None
    if first_row_only:
        inputs = _with_requested(
            inputs, tuple(path for path in all_fields if path.startswith("/events/0/"))
        )
    snapshot = copy.deepcopy(inputs)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search"
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)
    calls: list[TemplateSearchIntent] = []

    def record_fallback(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return plan_calendar_list_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", record_fallback)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("WideFullOnlyLayout@1",{{}},Template("{target}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task, inputs.card, inputs.bindings, Model()
    )
    assert calls == [inputs.intent]
    assert target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"call":"clickToIntent"' not in output.a2ui
    for path in all_fields:
        assert f"{_ROOT}{path}" in output.a2ui
    if target == _NOTES:
        for index in range(3):
            assert f"{_ROOT}/events/{index}/title" not in output.a2ui
            assert f"{_ROOT}/events/{index}/dtStart" not in output.a2ui
    assert inputs == snapshot


def test_templates_stay_hidden_from_default_search_and_prompt(registry: CardPlanRegistry) -> None:
    inputs = _case()
    prompt = str(build_template_retrieval_prompt(inputs.task, registry, inputs.bindings))
    for target in _TARGETS:
        assert not registry.template_is_enabled(target)
        assert target not in prompt
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            inputs.intent,
            inputs.task,
            registry,
            inputs.bindings,
            inputs.card,
            preferred_template_ids=(_NOTES,),
        )


@pytest.mark.parametrize("variant", ["missing", "gap", "fifth", "extra_field"])
def test_incomplete_or_oversized_requested_fields_are_not_rewritten(
    registry: CardPlanRegistry, variant: str
) -> None:
    inputs = _case()
    fields = inputs.intent.required_output_fields_by_capability.get(_CAP)
    assert fields is not None
    if variant == "missing":
        fields = tuple(path for path in fields if path != "/events/1/description")
        inputs = inputs._replace(
            task=inputs.task.model_copy(update={"userQuery": "展示日程数量和备注"})
        )
    elif variant == "gap":
        fields = tuple(path.replace("/events/1/", "/events/3/") for path in fields)
    elif variant == "fifth":
        fields = (*fields, "/events/3/description", "/events/4/description")
    else:
        fields = (*fields, "/events/0/title")
    assert _fallback(_with_requested(inputs, fields), registry) is None


@pytest.mark.parametrize("target", _TARGETS)
@pytest.mark.parametrize("source", ["schema", "candidate", "both"])
def test_upstream_extra_row_cannot_be_hidden_by_first_layer(
    registry: CardPlanRegistry, target: str, source: str
) -> None:
    inputs = _case(target)
    next_index = len(_rows(inputs))
    if source in {"schema", "both"}:
        _rows(inputs).append(copy.deepcopy(_rows(inputs)[0]))
    if source in {"candidate", "both"}:
        binding = inputs.bindings[0].model_copy(
            update={
                "candidateOutputFields": [
                    *inputs.bindings[0].candidateOutputFields,
                    f"/events/{next_index}/title",
                ]
            }
        )
        inputs = inputs._replace(bindings=(binding,))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "variant", ["schema_row", "schema_field", "candidate_field", "type", "untyped", "scalar"]
)
def test_missing_or_untyped_requested_data_cannot_match(
    registry: CardPlanRegistry, variant: str
) -> None:
    inputs = _case()
    rows = _rows(inputs)
    if variant == "schema_row":
        rows.pop()
    elif variant == "schema_field":
        rows[1].pop("description")
    elif variant == "type":
        rows[1]["description"] = {"type": "integer", "sampleValue": 1}
    elif variant == "untyped":
        rows[1]["description"] = {"sampleValue": "没有类型的备注"}
    elif variant == "scalar":
        rows[1]["description"] = "未声明类型的备注"
    else:
        candidates = list(inputs.bindings[0].candidateOutputFields)
        candidates.remove("/events/1/description")
        binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": candidates})
        inputs = inputs._replace(bindings=(binding,))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "query",
    [
        "显示所有日程备注，点击查看详情",
        "显示所有日程备注，再创建一个日程",
        "显示所有日程备注，并编辑这个日程",
        "不需要按钮但要点击卡片打开日历",
        "显示所有日程备注，并设置提前十分钟的提醒",
        "显示五条日程的备注",
        "显示第 5 条日程备注",
        "显示4项安排的备注",
        "显示所有日程备注全文",
        "显示所有日程备注，不要省略",
        "完整显示全部文字",
        "显示三条日程的完整备注",
        "完整显示三条日程的备注",
    ],
)
def test_explicit_operation_or_capacity_demand_cannot_be_ignored(
    registry: CardPlanRegistry, query: str
) -> None:
    inputs = _case()
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "query",
    [
        "创建一个卡片，展示所有日程的备注",
        "展示完整列表的日程备注，不要按钮",
        "显示三项安排的备注，无需打开日历",
        "未来7天所有日程各自的备注",
        "显示全部日程备注内容",
        "创建一个日程卡片，显示全部日程备注内容",
    ],
)
def test_display_lists_and_explicit_no_action_are_allowed(
    registry: CardPlanRegistry, query: str
) -> None:
    inputs = _case()
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is not None


def test_selected_actions_and_trusted_template_scope_remain_effective(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case()
    selected = inputs.intent.model_copy(update={"action_ids": (_VIEW,)})
    assert _fallback(inputs._replace(intent=selected), registry) is None
    assert _fallback(inputs, registry, trusted_template_action_ids=(_VIEW,)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_TIMEZONE,)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_NOTES, _TIMEZONE)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_NOTES,)) is not None


@pytest.mark.parametrize("disabled", ["template", "provider"])
def test_registry_disable_cannot_be_bypassed(disabled: str) -> None:
    kwargs: dict[str, Any] = {"disabled_template_ids": (_NOTES,)}
    if disabled == "provider":
        kwargs = {"disabled_provider_ids": ("com.huawei.calendar.cli",)}
    assert _fallback(_case(), CardPlanRegistry(**kwargs)) is None


@pytest.mark.parametrize("variant", ["size", "binding", "intent", "card", "root"])
def test_wrong_size_mixed_business_and_distinct_root_are_rejected(
    registry: CardPlanRegistry, variant: str
) -> None:
    inputs = _case()
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
                    **inputs.intent.required_output_fields_by_capability,
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


def test_old_single_item_fallback_still_owns_its_original_shape(registry: CardPlanRegistry) -> None:
    inputs = _inputs(("/events/0/senderName", "/events/0/remindTime/0"))
    assert _fallback(inputs, registry) is None
    old = plan_calendar_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card
    )
    assert old is not None
    assert old.registry.enabled_calendar_fallback_template_ids == {
        "ScheduleOverviewSourceReminderFull@1"
    }


@pytest.mark.parametrize("target", _TARGETS)
def test_explicit_all_rows_request_can_extend_same_roles_without_mutating_first_layer(
    registry: CardPlanRegistry, target: str
) -> None:
    inputs = _case(target)
    all_fields = inputs.intent.required_output_fields_by_capability.get(_CAP)
    assert all_fields is not None
    selected = []
    for path in all_fields:
        if path == "/eventCount" or path.startswith("/events/0/"):
            selected.append(path)
    inputs = _with_requested(inputs, tuple(selected))
    if target == _TIMEZONE:
        # 9d91 的真实 query 要求每个日程，但首层曾只选首项的五种同类字段。
        inputs = inputs._replace(
            task=inputs.task.model_copy(
                update={
                    "userQuery": "搞个卡片，看看跨时区日程的时区、标题、时间段和地点\n"
                    "本轮卡片静态内容（用作展示的外部事实）：\n"
                    "展示用户日历中的跨时区日程信息，包括每个日程的时区、标题、时间段和地点。",
                }
            )
        )
    snapshot = copy.deepcopy(inputs)
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent is not inputs.intent
    expanded = result.intent.required_output_fields_by_capability.get(_CAP)
    assert expanded is not None
    assert set(expanded) == set(all_fields)
    assert expanded[: len(selected)] == tuple(selected)
    assert set(selected).issubset(expanded)
    assert inputs == snapshot


@pytest.mark.parametrize(
    "variant",
    [
        "no_all_query",
        "different_roles",
        "candidate_row",
        "schema_row",
        "count_not_selected",
    ],
)
def test_list_completion_needs_explicit_all_rows_and_uniform_authorized_shape(
    registry: CardPlanRegistry, variant: str
) -> None:
    target = _NOTES if variant == "count_not_selected" else _TIMEZONE
    inputs = _case(target)
    all_fields = inputs.intent.required_output_fields_by_capability.get(_CAP)
    assert all_fields is not None
    first_fields = tuple(path for path in all_fields if path.startswith("/events/0/"))
    inputs = _with_requested(inputs, first_fields)
    if variant == "no_all_query":
        inputs = inputs._replace(
            task=inputs.task.model_copy(update={"userQuery": "显示日程时区、标题、时间段和地点"})
        )
    elif variant == "different_roles":
        fields = (
            "/events/0/timeZone",
            "/events/0/title",
            "/events/1/dtStart",
            "/events/1/dtEnd",
            "/events/1/eventLocation",
        )
        inputs = _with_requested(inputs, fields)
    elif variant == "candidate_row":
        candidates = []
        for path in inputs.bindings[0].candidateOutputFields:
            if not path.startswith("/events/2/"):
                candidates.append(path)
        binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": candidates})
        inputs = inputs._replace(bindings=(binding,))
    elif variant == "schema_row":
        _rows(inputs).pop()
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize(
    "query",
    [
        "所有日程各自的备注，只要前两条",
        "展示所有日程备注，只看第一条",
        "不要显示所有日程，只要第一条备注",
        "不用列出全部日程，显示备注",
        "展示所有日程备注，只看前几条",
    ],
)
def test_explicit_subset_or_negated_all_never_expands_or_ignores_the_limit(
    registry: CardPlanRegistry, query: str, partial: bool
) -> None:
    inputs = _case()
    if partial:
        inputs = _with_requested(inputs, ("/eventCount", "/events/0/description"))
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize("old_fallback", [False, True])
@pytest.mark.asyncio
async def test_existing_success_or_compile_error_never_enters_list_fallback(
    monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry, old_fallback: bool
) -> None:
    fields = ("/events/0/title", "/events/0/dtStart", "/events/0/eventLocation")
    if old_fallback:
        fields = ("/events/0/senderName", "/events/0/remindTime/0")
    inputs = _inputs(fields)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search"
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("已有计划或编译错误不能进入列表补充分支")

    async def broken_compile(**_kwargs: Any) -> Any:
        raise ValueError("deliberate compile error")

    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "_generate_selected_templates", broken_compile)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

    with pytest.raises(
        pipeline.TemplateGenerationError, match="selected template generation failed"
    ):
        await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())
