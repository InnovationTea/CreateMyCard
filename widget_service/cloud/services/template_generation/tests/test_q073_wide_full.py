"""Q073 完整模板通过既有检索与编译链路覆盖全部输入字段。"""

import json
from pathlib import Path

import pytest

from models.generation import TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_effective_document,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    _binding_placeholder,
    _build_data_schema,
    _preview_root,
    _preview_theme,
    _template_parameters,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui
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


@pytest.mark.parametrize("with_music_icon", (False, True))
def test_wide_full_without_action_hides_entire_playlist_panel(with_music_icon: bool) -> None:
    registry = CardPlanRegistry()
    definition = registry.require_template("BluetoothDeviceOverviewEarbudsChargingWideFull@1")
    task = TaskSpec(
        userQuery="显示耳机名称、连接状态和耳机仓及左右耳的电量与充电状态",
        size="2x4",
        dataModelSchema=_build_data_schema(definition),
        eventCandidates=[],
        assetCandidates=[],
    )
    bindings: dict[str, str] = {}
    for name, binding in definition.bindings.items():
        bindings[name] = _binding_placeholder(definition, binding)
    params = _template_parameters(definition)
    params.pop("actionId", None)
    if not with_music_icon:
        params.pop("musicIcon", None)
    theme = _preview_theme(definition, registry)
    content = _instantiate_blueprint(
        definition.variants[0].root, params, bindings, theme.reference_values,
    )
    root = _preview_root(_strip_advanced_component_markers(content), 136, theme.root_style)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    a2ui = convert_tersel_to_a2ui(
        _serialize_effective_document(root, task, True),
        size="2x4", protocol_profile=profile, task_spec=task.model_dump(mode="json"),
    )
    nodes = []
    for line in a2ui.splitlines():
        nodes.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    assert not any(node.get("onClick") for node in nodes)
    assert "打开歌单" not in a2ui
    assert "播放每日30首" not in a2ui
    assert "music_fill.svg" not in a2ui
    assert "耳机仓" in a2ui
    for binding in definition.bindings.values():
        assert binding.path in a2ui
    assert len([node for node in nodes if node.get("component") == "Progress"]) == 2


@pytest.mark.parametrize("example_id", ("connected", "disconnected"))
def test_ear123_connection_examples_keep_runtime_header_and_playlist(
    tmp_path: Path, example_id: str,
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
