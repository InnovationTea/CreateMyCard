"""Q073 完整模板通过既有检索与编译链路覆盖全部输入字段。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    _template_parameters,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.tests.helpers.generate_q073_preview import generate


def test_q073_full_fields_and_embedded_daily_action(tmp_path):
    output = tmp_path / "preview.json"
    generate(Path(__file__).parent / "fixtures/q073.json", output)
    text = output.read_text(encoding="utf-8")
    messages = json.loads(text)
    update = messages[1].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    rings = [node for node in nodes if node.get("component") == "Progress"]
    assert len(rings) == 2
    assert "打开歌单" in text
    assert "播放每日30首" in text
    clickable = [node for node in nodes if node.get("onClick")]
    assert len(clickable) == 1
    panel = clickable[0]
    assert panel.get("component") == "Stack"
    assert panel.get("styles", {}).get("borderRadius") == 16
    assert panel.get("styles", {}).get("layoutWeight") == 1
    children = panel.get("children")
    assert isinstance(children, list) and len(children) == 1
    child = next(node for node in nodes if node.get("id") == children[0])
    assert child.get("component") == "Row"
    assert not any(node.get("content") == "" for node in nodes)
    assert "code=a001" in text
    for field in ("chargingStatusDesc", "leftChargingStatusDesc", "rightChargingStatusDesc"):
        assert field in text
    assert "示例数据" not in text
    images = [node for node in nodes if node.get("component") == "Image"]
    assert len(images) == 4
    assert "resources/base/media/music_fill.svg" in [node.get("src") for node in images]


@pytest.mark.parametrize(
    ("candidate_event", "selected_event", "expected_selected"),
    (
        (None, None, False),
        ("event.open.music.daily", None, False),
        ("event.open.music.favorite", "event.open.music.favorite", False),
        ("event.open.music.daily", "event.open.music.daily", True),
    ),
)
def test_wide_full_requires_selected_daily_action(
    candidate_event: str | None,
    selected_event: str | None,
    expected_selected: bool,
) -> None:
    registry = CardPlanRegistry()
    template_id = "BluetoothDeviceOverviewEarbudsChargingWideFull@1"
    definition = registry.require_template(template_id)
    source = Path(__file__).parent / "fixtures/ear123_connection_examples.json"
    fixture = json.loads(source.read_text(encoding="utf-8"))
    content = fixture.get("content")
    assert isinstance(content, dict)
    bindings = tuple(
        CandidateDataBinding.model_validate(item)
        for item in content.get("candidateDataBindings", [])
    )
    assert len(bindings) == 1
    events = []
    if candidate_event is not None:
        events.append(
            EventAction(
                id=candidate_event,
                call="clickToDeeplink",
                args={"uri": "music:test"},
            )
        )
    task = TaskSpec(
        userQuery="查看耳机名称、连接状态和三处电量及充电状态",
        size="2x4",
        dataModelSchema=_build_data_schema(definition),
        eventCandidates=events,
        assetCandidates=[],
    )
    card_spec = {"suggestSize": "2x4", "dataBindings": [item.model_dump() for item in bindings]}
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": bindings[0].candidateOutputFields},
        action=() if selected_event is None else (selected_event,),
    )
    search = search_template_variants(intent, task, registry, bindings, card_spec)
    try:
        plans = plan_template_candidates(intent, search, task, registry)
    except TemplateRetrievalMiss as exc:
        assert not expected_selected, str(exc)
        return
    matching_plans = []
    for plan in plans:
        for slot in plan.business_slots:
            if slot.template_id == template_id:
                matching_plans.append(plan)
                break
    assert bool(matching_plans) == expected_selected
    for plan in matching_plans:
        assert len(plan.action_assignments) == 1
        assignment = plan.action_assignments[0]
        assert assignment.consumer == "business-template"
        assert assignment.action_id == "event.open.music.daily"


def test_wide_full_schema_rejects_missing_action() -> None:
    definition = CardPlanRegistry().require_template(
        "BluetoothDeviceOverviewEarbudsChargingWideFull@1"
    )
    params = _template_parameters(definition)
    Draft202012Validator(definition.variants[0].parameters_schema).validate(params)
    params.pop("actionId", None)
    with pytest.raises(ValidationError, match="actionId"):
        Draft202012Validator(definition.variants[0].parameters_schema).validate(params)


@pytest.mark.parametrize("example_id", ("connected", "disconnected"))
def test_ear123_connection_examples_keep_runtime_header_and_playlist(
    tmp_path: Path,
    example_id: str,
) -> None:
    source = Path(__file__).parent / "fixtures/ear123_connection_examples.json"
    fixture = json.loads(source.read_text(encoding="utf-8"))
    examples = fixture.get("examples")
    assert isinstance(examples, list)
    example = next(item for item in examples if item.get("id") == example_id)
    earphone_sample = example.get("earphoneData")
    assert isinstance(earphone_sample, dict)
    output = tmp_path / f"{example_id}.json"
    generate(source, output, earphone_sample=earphone_sample)
    messages = json.loads(output.read_text(encoding="utf-8"))
    nodes = []
    for message in messages:
        nodes.extend(message.get("updateComponents", {}).get("components", []))
    header = next(node for node in nodes if "/isConnected" in node.get("content", ""))
    assert header.get("content") == (
        "{{ ${/data/earphone/isConnected} ? '已连接 ' + "
        "${/data/earphone/earphoneName} : '未连接' }}"
    )
    initial = next(
        message.get("updateDataModel") for message in messages if message.get("updateDataModel")
    )
    assert isinstance(initial, dict)
    value = initial.get("value")
    assert isinstance(value, dict)
    data = value.get("data")
    assert isinstance(data, dict)
    assert data.get("earphone") == earphone_sample
    clickable = [node for node in nodes if node.get("onClick")]
    assert len(clickable) == 1
    content = fixture.get("content")
    assert isinstance(content, dict)
    events = content.get("candidateEventCandidates")
    assert isinstance(events, list) and len(events) == 1
    assert clickable[0].get("onClick") == [events[0].get("action")]
    assert len([node for node in nodes if node.get("component") == "Progress"]) == 2


def test_ear123_preview_rejects_unknown_sample_field(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures/ear123_connection_examples.json"
    with pytest.raises(ValueError, match="Unknown earphone preview field"):
        generate(source, tmp_path / "invalid.json", earphone_sample={"fakeField": "fake"})
