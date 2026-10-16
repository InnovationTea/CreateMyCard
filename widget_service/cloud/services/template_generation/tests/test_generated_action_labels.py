"""缺失映射时第二层命名的上下文、生成产物和局部权限回归。"""

import json
from pathlib import Path
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.cardplan.action_labels import (
    action_label_candidate,
    action_label_request,
    validate_action_label,
)
from services.template_generation.engine.cardplan.compiler import (
    _validate_card_params,
    _validate_template_params,
)
from services.template_generation.engine.cardplan.models import ActionBinding, HybridBodyContract
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.tests.test_focus_action_label import focus_task as focus_task
from services.template_generation.tests.test_template_generation import _FixedTemplateModel


def _registered_events(
    snapshot: str = "app-11.7.7.300_rom-7.0",
) -> dict[str, dict[str, Any]]:
    path = (
        Path(__file__).parents[3] / "data" / "capabilities"
        / snapshot / "event_capabilities.json"
    )
    events: dict[str, dict[str, Any]] = {}
    for event in json.loads(path.read_text(encoding="utf-8")):
        event_id = event.get("id")
        assert isinstance(event_id, str)
        events[event_id] = event
    return events


def _event(event_id: str, snapshot: str = "app-11.7.7.300_rom-7.0") -> EventAction:
    definition = _registered_events(snapshot).get(event_id)
    assert definition is not None
    action = definition.get("actionTemplate")
    assert isinstance(action, dict)
    return EventAction(id=event_id, description=definition.get("description"), **action)


@pytest.mark.parametrize(("snapshot", "event_id"), [
    *(('app-11.7.5.205_rom-6.0', event_id)
      for event_id in sorted(_registered_events("app-11.7.5.205_rom-6.0"))),
    *(("app-11.7.7.300_rom-7.0", event_id) for event_id in sorted(_registered_events())),
])
def test_registered_events_have_default_labels(
    focus_task: TaskSpec, snapshot: str, event_id: str,
) -> None:
    event = _event(event_id, snapshot)
    focus_task.eventCandidates = [event]
    binding = action_bindings(focus_task)[0]
    candidate = action_label_candidate(binding)
    assert isinstance(binding.display_label, str)
    assert binding.display_label.strip()
    assert candidate.get("label") == binding.display_label
    assert "labelPolicy" not in candidate
    assert action_label_request(focus_task.userQuery, (binding,)) == ()


def _unmapped_binding() -> ActionBinding:
    event = _event("event.setWifiMode")
    return ActionBinding(
        action_id=event.id, event_id=event.id, display_label=None,
        description=event.description, call=event.call, args=event.args,
    )


@pytest.mark.parametrize("label", [
    None, 1, False, [], {}, "", " ", " 开启无线网络", "开启无线网络\n", "开\t启",
    "开\u2028启", "开\u200b启", "${data.x}", "{{x}}", "https://a.cn", "<打开>",
    "打开详情", "查看详情", "开" * 21,
])
def test_generated_label_rejects_invalid_text(label: Any) -> None:
    with pytest.raises(TerselConversionError):
        validate_action_label(_unmapped_binding(), label)


@pytest.mark.parametrize("label", ["开启无线网络", "关闭无线网络", "无线网络设置", "设为静音"])
def test_generated_label_accepts_plain_action_text(label: str) -> None:
    assert validate_action_label(_unmapped_binding(), label) == label


def test_fixed_label_cannot_be_replaced() -> None:
    binding = _unmapped_binding().model_copy(update={"display_label": "无线网络设置"})
    with pytest.raises(TerselConversionError, match="pair is not approved"):
        validate_action_label(binding, "开启无线网络")


@pytest.mark.parametrize("template_id", ["PillAction@1", "CompactAction@1"])
def test_generated_label_is_local_to_selected_action(template_id: str) -> None:
    binding = _unmapped_binding()
    contract = HybridBodyContract.model_construct(
        action_bindings=(binding,), content_action_ids=(binding.action_id,),
        trusted_literals=(), trusted_numbers=(),
    )
    params = {"actionId": binding.action_id, "label": "开启无线网络"}
    _validate_template_params(params, {}, contract, action_template_id=template_id)
    assert contract.trusted_literals == ()
    with pytest.raises(TerselConversionError, match="not trusted"):
        _validate_template_params(params, {}, contract, action_template_id="Business@1")
    with pytest.raises(TerselConversionError, match="not trusted"):
        _validate_template_params({"title": "开启无线网络"}, {}, contract)
    with pytest.raises(TerselConversionError, match="not trusted|approved content Action"):
        _validate_template_params(
            {"actionId": "unselected", "label": "开启无线网络"}, {}, contract,
            action_template_id=template_id,
        )
    unselected = contract.model_copy(update={"content_action_ids": ()})
    with pytest.raises(TerselConversionError, match="approved content Action"):
        _validate_template_params(params, {}, unselected, action_template_id=template_id)


def test_card_action_allows_only_its_own_generated_label(focus_task: TaskSpec) -> None:
    focus_task.eventCandidates = [
        _event("event.setWifiMode").model_copy(update={"id": "event.future.wifi"}),
    ]
    binding = action_bindings(focus_task)[0]
    contract = HybridBodyContract.model_construct(
        action_bindings=(binding,), content_action_ids=(), trusted_literals=(),
    )
    _validate_card_params(
        {"action": {"id": binding.action_id, "label": "开启无线网络"}}, focus_task, contract,
    )
    with pytest.raises(TerselConversionError, match="not approved"):
        _validate_card_params(
            {"action": {"id": "unselected", "label": "开启无线网络"}}, focus_task, contract,
        )
    with pytest.raises(TerselConversionError, match="not trusted"):
        _validate_card_params({"title": "开启无线网络"}, focus_task, contract)


def test_duplicate_event_instances_keep_distinct_context(focus_task: TaskSpec) -> None:
    event = _event("event.setWifiMode")
    params = event.args.get("params")
    assert isinstance(params, dict)
    other = event.model_copy(update={
        "args": {**event.args, "params": {**params, "switchFlag": 1}},
    })
    focus_task.eventCandidates = [event, other]
    bindings = action_bindings(focus_task)
    assert [item.action_id for item in bindings] == [event.id + "#1", event.id + "#2"]
    assert bindings[0].args == event.args
    assert bindings[1].args == other.args
    assert [item.display_label for item in bindings] == ["开启Wi-Fi", "关闭Wi-Fi"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("mapped", [False, True])
@pytest.mark.parametrize(("event_id", "query", "fixed_label", "generated_label"), [
    (
        "event.open.settings.sleepMode", "显示今日日程并打开睡眠模式设置",
        "睡眠模式设置", "睡眠模式设置",
    ),
    ("event.open.settings.wifi", "显示今日日程并进入无线网络设置", "Wi-Fi设置", "无线网络设置"),
    ("event.setWifiMode", "显示今日日程并开启无线网络", "开启Wi-Fi", "开启无线网络"),
])
async def test_second_layer_keeps_mapped_or_generated_label_with_original_event(
    focus_task: TaskSpec, fusion: bool, mapped: bool, event_id: str, query: str,
    fixed_label: str, generated_label: str,
) -> None:
    event = _event(event_id)
    if not mapped:
        event = event.model_copy(update={"id": event_id + ".future"})
    event_id = event.id
    label = fixed_label if mapped else generated_label
    focus_task.eventCandidates = [event]
    focus_task.userQuery = query
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents", writeResultTo="/data/calendar",
        candidateOutputFields=["/events/0/title", "/events/0/dtStart", "/events/0/dtEnd"],
    )
    card_spec = {
        "title": "今日日程", "description": "日程与快捷操作", "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": binding.capabilityId,
                          "writeResultTo": binding.writeResultTo}],
    }
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral", component_id="CalendarOverview",
        available_template_ids=("ScheduleOverviewTitleHero@1",),
        capability_id=binding.capabilityId, required_fields=tuple(binding.candidateOutputFields),
        action_id=event_id,
        body=(
            'Template("HeroActionLayout@1",{},Template("ScheduleOverviewTitleHero@1",{}),'
            f'Template("PillAction@1",{{"actionId":"{event_id}","label":"{label}"}}));'
        ),
    )
    output = await generate_template_a2ui(
        focus_task, card_spec, (binding,), model, enable_fusion_ball=fusion,
    )
    assert model.second_layer_prompt is not None
    prompt_lines: dict[str, Any] = {}
    for message in model.second_layer_prompt:
        for line in message.get("content", "").splitlines():
            if line.startswith(("actionLabelRequest=", "selectedActionCandidates=")):
                key, value = line.split("=", 1)
                prompt_lines[key] = json.loads(value)
    if mapped:
        assert "actionLabelRequest" not in prompt_lines
    else:
        assert prompt_lines.get("actionLabelRequest") == query
        candidate = action_label_candidate(action_bindings(focus_task)[0])
        assert candidate.get("label") is None
        assert candidate.get("labelPolicy") == "generate-from-request"
        assert candidate.get("description") == event.description
        assert candidate.get("readOnlyAction") == {"call": event.call, "args": event.args}
    actions = prompt_lines.get("selectedActionCandidates")
    assert actions == [action_label_candidate(action_bindings(focus_task)[0])]
    clickable = []
    for line in output.a2ui.splitlines():
        update = json.loads(line).get("updateComponents")
        if not isinstance(update, dict):
            continue
        for component in update.get("components", []):
            if component.get("onClick"):
                clickable.append(component)
    assert len(clickable) == 1
    assert clickable[0].get("label") == label
    assert clickable[0].get("onClick") == [{"call": event.call, "args": event.args}]
