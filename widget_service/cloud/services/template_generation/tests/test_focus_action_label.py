"""免打扰入口的批准文案、模型输入及最终按钮事件回归。"""

import json
from pathlib import Path

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_template_generation import _FixedTemplateModel

_EVENT_ID = "event.open.settings.dndMode"
_LABEL = "免打扰设置"


@pytest.fixture
def focus_task() -> TaskSpec:
    path = Path(__file__).parent / "fixtures" / "focus_dnd_mode.json"
    return TaskSpec.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("event_id", [_EVENT_ID, "event.open.settings.dnd"])
def test_dnd_action_names_settings_and_preserves_event(
    focus_task: TaskSpec, event_id: str,
) -> None:
    event = focus_task.eventCandidates[0].model_copy(update={"id": event_id})
    focus_task.eventCandidates = [event]
    actions = action_bindings(focus_task)
    assert len(actions) == 1
    action = actions[0]
    assert action.display_label == _LABEL
    assert action.display_subtitle == "勿扰模式"
    assert action.action_id == action.event_id == event_id
    assert action.call == event.call
    assert action.args == event.args


def test_dnd_action_preserves_explicit_trusted_label(focus_task: TaskSpec) -> None:
    event = focus_task.eventCandidates[0].model_copy(update={"displayLabel": "进入免打扰"})
    focus_task.eventCandidates = [event]
    assert action_bindings(focus_task)[0].display_label == "进入免打扰"


def test_unknown_action_requires_generated_label(focus_task: TaskSpec) -> None:
    event = focus_task.eventCandidates[0].model_copy(update={"id": "event.unknown"})
    focus_task.eventCandidates = [event]
    assert action_bindings(focus_task)[0].display_label is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
async def test_focus_request_generates_specific_button_without_changing_action(
    focus_task: TaskSpec, fusion: bool,
) -> None:
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=["/events/0/title", "/events/0/dtStart", "/events/0/dtEnd"],
    )
    card_spec = {
        "title": "专注模式",
        "description": "今天的日程与免打扰设置",
        "suggestSize": "2x2",
        "dataBindings": [{
            "capabilityId": binding.capabilityId,
            "writeResultTo": binding.writeResultTo,
        }],
    }
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral",
        component_id="CalendarOverview",
        available_template_ids=("ScheduleOverviewTitleHero@1",),
        capability_id=binding.capabilityId,
        required_fields=tuple(binding.candidateOutputFields),
        action_id=_EVENT_ID,
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("ScheduleOverviewTitleHero@1",{}),'
            f'Template("PillAction@1",{{"actionId":"{_EVENT_ID}","label":"{_LABEL}"}}));'
        ),
    )
    output = await generate_template_a2ui(
        focus_task, card_spec, (binding,), model, enable_fusion_ball=fusion,
    )
    assert model.second_layer_prompt is not None
    prompt = json.dumps(model.second_layer_prompt, ensure_ascii=False)
    assert _EVENT_ID in prompt
    assert _LABEL in prompt
    candidates = None
    for message in model.second_layer_prompt:
        for line in message.get("content", "").splitlines():
            if line.startswith("selectedActionCandidates="):
                candidates = json.loads(line.removeprefix("selectedActionCandidates="))
    assert candidates == [{"actionId": _EVENT_ID, "label": _LABEL, "subtitle": "勿扰模式"}]
    clickable = []
    for line in output.a2ui.splitlines():
        message = json.loads(line)
        update = message.get("updateComponents")
        if update is None:
            continue
        for component in update.get("components", []):
            if component.get("onClick"):
                clickable.append(component)
    assert len(clickable) == 1
    button = clickable[0]
    assert button.get("component") == "Button"
    assert button.get("label") == _LABEL
    event = focus_task.eventCandidates[0]
    assert button.get("onClick") == [{"call": event.call, "args": event.args}]
