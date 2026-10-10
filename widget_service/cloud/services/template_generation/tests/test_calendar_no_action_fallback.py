"""无按钮日程仅在旧路失败后尝试，保留字段、动作和候选授权边界。"""

from __future__ import annotations

from typing import Any

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_field_paths import (
    calendar_wide_fallback_reminder_aliases,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import (
    CALENDAR_NO_ACTION_FALLBACK_TEMPLATE_IDS,
    CardPlanRegistry,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    build_template_retrieval_prompt,
    normalize_calendar_reminder_intent,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_PARENT = "/events/0/remindTime"
_LEAF = f"{_PARENT}/0"
_SOURCE = "ScheduleOverviewSourceReminderFull@1"
_CASES = (
    ("2x2", _SOURCE, ("/events/0/senderName", _LEAF)),
    (
        "2x4",
        "ScheduleOverviewTimezoneWideFull@1",
        ("/events/0/timeZone", "/events/0/dtStart", "/events/0/eventLocation"),
    ),
    (
        "2x4",
        "ScheduleOverviewEventCountDetailsWideFull@1",
        ("/eventCount", "/events/0/description"),
    ),
    ("2x4", "ScheduleOverviewReminderWideFull@1", ("/events/0/dtStart", _LEAF)),
)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _case(size: str, fields: tuple[str, ...], *, parent: bool = False) -> CalendarInputs:
    task, bindings, card, intent = _inputs(fields, view_candidate=True)
    task = task.model_copy(update={"size": size, "userQuery": "展示下个日程的信息"})
    card["suggestSize"] = size
    if parent:
        requested = tuple(_PARENT if field == _LEAF else field for field in fields)
        bindings = (bindings[0].model_copy(update={"candidateOutputFields": list(requested)}),)
        intent = intent.model_copy(
            update={
                "required_output_fields_by_capability": {_CAP: requested},
                "primary_output_field_by_capability": {_CAP: _PARENT},
            }
        )
    return CalendarInputs(task, bindings, card, intent)


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    return plan_calendar_no_action_fallback(
        inputs.intent,
        inputs.task,
        registry,
        inputs.bindings,
        inputs.card,
        **kwargs,
    )


@pytest.mark.parametrize(("size", "target", "fields"), _CASES)
@pytest.mark.asyncio
async def test_pipeline_compiles_new_full_only_after_original_miss(
    monkeypatch: pytest.MonkeyPatch,
    registry: CardPlanRegistry,
    size: str,
    target: str,
    fields: tuple[str, ...],
) -> None:
    inputs = _case(size, fields, parent=_LEAF in fields)
    if target == "ScheduleOverviewReminderWideFull@1":
        inputs = inputs._replace(
            task=inputs.task.model_copy(
                update={
                    "userQuery": "我老忘事，帮我弄个卡片看看下个日程几点开始、提前多久提醒我",
                }
            )
        )
    snapshot = inputs.task.model_dump(), inputs.bindings[0].model_dump(), inputs.intent.model_dump()
    controls = TemplateControls(
        schemaVersion="template-controls/1",
        firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)
    fallback_calls: list[Any] = []

    def record_fallback(*args: Any, **kwargs: Any) -> Any:
        fallback_calls.append(args[0])
        return plan_calendar_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", record_fallback)
    layout = "SingleFocusLayout@1" if size == "2x2" else "WideFullOnlyLayout@1"

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("{layout}",{{}},Template("{target}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task,
        inputs.card,
        inputs.bindings,
        Model(),
    )
    assert len(fallback_calls) == 1
    assert fallback_calls[0] == inputs.intent
    assert target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"call":"clickToIntent"' not in output.a2ui
    assert snapshot == (
        inputs.task.model_dump(),
        inputs.bindings[0].model_dump(),
        inputs.intent.model_dump(),
    )


def test_default_registry_and_first_layer_hide_new_templates(registry: CardPlanRegistry) -> None:
    assert not any(
        registry.template_is_enabled(wire) for wire in CALENDAR_NO_ACTION_FALLBACK_TEMPLATE_IDS
    )
    inputs = _case("2x2", ("/events/0/senderName", _LEAF))
    prompt = str(build_template_retrieval_prompt(inputs.task, registry, inputs.bindings))
    assert not any(wire in prompt for wire in CALENDAR_NO_ACTION_FALLBACK_TEMPLATE_IDS)
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            inputs.intent,
            inputs.task,
            registry,
            inputs.bindings,
            inputs.card,
            preferred_template_ids=(_SOURCE,),
        )


@pytest.mark.parametrize(
    "query",
    [
        "展示来源和提醒，点击查看详情",
        "下个日程，加一个按钮",
        "一键打开日历",
        "点一下能进闹钟",
        "不需要按钮但要点击卡片打开日历",
        "列出每条日程来源和提醒",
        "显示所有日程来源和提醒",
        "展示两条日程来源和提醒",
        "完整列表的来源和提醒",
        "显示所有安排的开始时间和提醒设置",
        "显示三项安排的开始时间和提醒设置",
        "分别显示今天的安排何时开始、提前多久提醒",
        "显示下个日程开始时间和全部提醒设置",
        "显示开始时间和提醒，再创建一个日程",
        "显示开始时间和提醒，并编辑这个日程",
        "显示下个日程开始时间，并设置提前十分钟的提醒",
    ],
)
def test_query_gate_rejects_actions_and_lists(registry: CardPlanRegistry, query: str) -> None:
    inputs = _case("2x2", ("/events/0/senderName", _LEAF))
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "query",
    [
        "看看下个日程来源和提醒",
        "提前多久提醒我",
        "不要按钮，只看来源和提醒",
        "不要查看详情按钮",
        "无需打开日历，展示来源和提醒",
        "创建一个卡片，显示下个日程开始和提醒",
        "添加卡片到桌面，看看下个日程来源和提醒",
        "创建一个日程卡片，展示来源和提醒",
    ],
)
def test_query_gate_allows_display_and_explicit_no_action(
    registry: CardPlanRegistry,
    query: str,
) -> None:
    inputs = _case("2x2", ("/events/0/senderName", _LEAF))
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is not None


@pytest.mark.parametrize("extra", ["/events/1/title", "/events/0/importantEventType", "/updatedAt"])
def test_never_drops_an_extra_original_field(registry: CardPlanRegistry, extra: str) -> None:
    inputs = _case("2x2", ("/events/0/senderName", _LEAF, extra))
    assert _fallback(inputs, registry) is None


def test_original_actions_and_trusted_restrictions_remain_effective(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case("2x2", ("/events/0/senderName", _LEAF))
    action_intent = inputs.intent.model_copy(update={"action_ids": ("event.viewCalendarEvent",)})
    assert _fallback(inputs._replace(intent=action_intent), registry) is None
    assert (
        _fallback(inputs, registry, trusted_template_action_ids=("event.viewCalendarEvent",))
        is None
    )
    assert (
        _fallback(inputs, registry, trusted_template_candidate_ids=("ScheduleOverviewTitleHero@1",))
        is None
    )
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_SOURCE,)) is not None
    disabled = CardPlanRegistry(disabled_template_ids=(_SOURCE,))
    assert _fallback(inputs, disabled) is None
    provider_disabled = CardPlanRegistry(disabled_provider_ids=("com.huawei.calendar.cli",))
    assert _fallback(inputs, provider_disabled) is None


def test_mixed_capabilities_and_distinct_roots_do_not_enter_fallback(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case("2x2", ("/events/0/senderName", _LEAF))
    battery = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/battery"
    )
    assert _fallback(inputs._replace(bindings=(*inputs.bindings, battery)), registry) is None
    other_card = {
        **inputs.card,
        "dataBindings": [
            {
                "capabilityId": _CAP,
                "writeResultTo": "/data/anotherCalendar",
            }
        ],
    }
    assert _fallback(inputs._replace(card=other_card), registry) is None
    mixed_intent = inputs.intent.model_copy(
        update={
            "required_output_fields_by_capability": {
                **inputs.intent.required_output_fields_by_capability,
                "GetPhoneBatteryInfo": ("/level",),
            }
        }
    )
    assert _fallback(inputs._replace(intent=mixed_intent), registry) is None


def test_wide_alias_is_local_requested_authorized_and_deduplicated(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case("2x4", ("/events/0/dtStart", _LEAF), parent=True)
    original = inputs.intent.model_copy(
        update={
            "required_output_fields_by_capability": {
                _CAP: ("/events/0/dtStart", _PARENT, _LEAF),
            }
        }
    )
    inputs = inputs._replace(intent=original)
    assert normalize_calendar_reminder_intent(original, inputs.task, inputs.bindings) == original
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent.required_output_fields_by_capability.get(_CAP) == (
        "/events/0/dtStart",
        _LEAF,
    )
    assert result.intent.primary_output_field_by_capability.get(_CAP) == _LEAF
    assert calendar_wide_fallback_reminder_aliases(inputs.task, inputs.bindings, ()) == {}
    unauthorized = inputs.bindings[0].model_copy(
        update={"candidateOutputFields": ["/events/0/dtStart"]}
    )
    assert _fallback(inputs._replace(bindings=(unauthorized,)), registry) is None


@pytest.mark.parametrize("reminders", [[], [{"type": "object"}], [{"type": "string"}, []]])
def test_wide_parent_requires_nonempty_scalar_array(
    registry: CardPlanRegistry,
    reminders: list[Any],
) -> None:
    inputs = _case("2x4", ("/events/0/dtStart", _LEAF), parent=True)
    schema = {
        "data": {
            "calendar": {
                "events": [
                    {
                        "dtStart": {"type": "string", "sampleValue": "14:00"},
                        "remindTime": reminders,
                    }
                ]
            }
        }
    }
    task = inputs.task.model_copy(update={"dataModelSchema": schema})
    assert _fallback(inputs._replace(task=task), registry) is None


def test_wide_alias_never_collapses_explicit_second_reminder_or_event(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case("2x4", ("/events/0/dtStart", _LEAF), parent=True)
    for extra in ("/events/0/remindTime/1", "/events/1/remindTime"):
        requested = ("/events/0/dtStart", _PARENT, extra)
        intent = inputs.intent.model_copy(
            update={
                "required_output_fields_by_capability": {_CAP: requested},
            }
        )
        binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": list(requested)})
        assert _fallback(inputs._replace(intent=intent, bindings=(binding,)), registry) is None


@pytest.mark.asyncio
async def test_old_success_and_compile_errors_do_not_invoke_fallback(
    monkeypatch: pytest.MonkeyPatch,
    registry: CardPlanRegistry,
) -> None:
    inputs = _case("2x2", ("/events/0/title", "/events/0/dtStart", "/events/0/eventLocation"))
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search"
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("旧规划成功或编译失败不得调用补充分支")

    async def broken_compile(**_kwargs: Any) -> Any:
        raise ValueError("deliberate compile error")

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "_generate_selected_templates", broken_compile)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

    with pytest.raises(
        pipeline.TemplateGenerationError, match="selected template generation failed"
    ):
        await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())
