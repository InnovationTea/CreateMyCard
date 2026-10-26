"""验证关联字段、数值绑定和连续刷新，使用非电池对象防止业务特判。"""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.schemas import GenerateWidgetCardRequest
from models.capability import DataCapability
from models.generation import CandidateDataBinding
from services.card_validation import validate_card
from services.card_validation.base import expression_references, read_pointer
from services.card_validation.compact_validation.semantic.bindings import (
    _compact_component_binding_errors,
)
from services.card_validation.progress_sources import progress_source_errors
from services.compact_component_bindings import collect_compact_component_binding_errors
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
)
from services.compact_prompt_loader import assemble_prompts
from services.generation_preflight import GenerationPreflight
from services.related_output_fields import complete_related_output_fields
from services.task_spec_builder import TaskSpecBuilder


def _properties():
    return {
        "levelText": {
            "type": "string", "description": "水箱水位", "sampleValue": "60%",
            "numericSource": "level",
        },
        "level": {"type": "integer", "description": "当前水位", "sampleValue": 6},
        "other": {"type": "integer", "description": "其它指标", "sampleValue": 8},
    }


def _capability(*, array=False, properties=None):
    content = {"type": "object", "properties": properties or _properties()}
    if array:
        content = {
            "type": "object",
            "properties": {"tanks": {"type": "array", "items": content}},
        }
    return DataCapability(id="TankInfo", description="水箱状态", outputSchema=content)


def _binding(fields=None):
    return CandidateDataBinding(
        capabilityId="TankInfo", arguments={}, writeResultTo="/data/custom",
        candidateOutputFields=fields if fields is not None else ["/levelText"],
    )


def test_completion_is_ordered_idempotent_and_does_not_mutate_request():
    original = _binding(["/other", "/levelText"])
    completed = complete_related_output_fields([original], [_capability()])
    assert original.candidateOutputFields == ["/other", "/levelText"]
    assert completed[0].candidateOutputFields == ["/other", "/levelText", "/level"]
    assert complete_related_output_fields(completed, [_capability()]) == completed
    assert completed[0].arguments == original.arguments
    assert completed[0].writeResultTo == original.writeResultTo


def test_array_completion_preserves_object_index_and_projects_absolute_source():
    capability = _capability(array=True)
    binding = _binding(["/tanks/2/levelText"])
    completed = complete_related_output_fields([binding], [capability])
    assert completed[0].candidateOutputFields == ["/tanks/2/levelText", "/tanks/2/level"]
    task = TaskSpecBuilder().build("水位", "2x4", completed, [capability], [], [])
    found, leaf = read_pointer(task.dataModelSchema, "/data/custom/tanks/2/levelText")
    assert found
    assert leaf.get("numericSource") == "/data/custom/tanks/2/level"
    found, numeric = read_pointer(task.dataModelSchema, "/data/custom/tanks/2/level")
    assert found
    assert numeric.get("type") == "integer"


def test_preflight_completes_only_registered_selected_fields():
    class Registry:
        def get_data_capability(self, _identifier):
            return _capability()

    request = GenerateWidgetCardRequest(
        uid="test", userQuery="水位", size="2x4", title="水位", description="水位",
        device={"romVersion": "7.0"},
        prdVer="11.7.8.354",
        candidateDataBindings=[_binding()], candidateEventCandidates=[], candidateAssetIds=[],
    )
    result = GenerationPreflight(Registry()).run(request)
    assert result.blocking_issues == ()
    assert result.effective_bindings[0].candidateOutputFields == ["/levelText", "/level"]
    assert request.candidateDataBindings[0].candidateOutputFields == ["/levelText"]
    assert result.task_spec is not None
    found, leaf = read_pointer(result.task_spec.dataModelSchema, "/data/custom/levelText")
    assert found
    assert leaf.get("numericSource") == "/data/custom/level"


@pytest.mark.parametrize("source", ["missing", "levelText", "/other/level", 3, None])
def test_registry_rejects_invalid_numeric_relationship(source):
    properties = _properties()
    text = properties.get("levelText")
    assert text is not None
    text["numericSource"] = source
    with pytest.raises(ValidationError, match="numericSource"):
        _capability(properties=properties)


def test_unregistered_text_does_not_infer_related_fields_from_names_or_samples():
    properties = _properties()
    text = properties.get("levelText")
    assert text is not None
    text.pop("numericSource")
    binding = _binding()
    result = complete_related_output_fields([binding], [_capability(properties=properties)])
    assert result[0].candidateOutputFields == ["/levelText"]


def _line(value):
    return ["line", "ProgressLine2", {
        "value": value, "total": 10,
        "displayValue": {"path": "/data/custom/levelText"},
        "fontColor": "#FF000000", "color": "#FF000000", "backgroundColor": "#33000000",
    }]


def _source(value):
    rows = [
        ["root", "Column", {}, ["line"]], _line(value),
        ["/data/custom/level", 6], ["/data/custom/levelText", "60%"],
    ]
    return "\n".join(json.dumps(row) for row in rows)


def test_converted_progress_preserves_live_source_across_repeated_updates():
    standard = convert_compact_dsl_to_a2ui(_source({"path": "/data/custom/level"}), size="2x4")
    messages = [json.loads(line) for line in standard.splitlines()]
    updates = messages[1].get("updateComponents")
    data_update = messages[2].get("updateDataModel")
    assert updates is not None and data_update is not None
    components = updates.get("components")
    assert isinstance(components, list)
    progress = next(item for item in components if item.get("component") == "Progress")
    refs = expression_references(progress.get("value"))
    assert refs == ["/data/custom/level"]
    assert "__display" not in standard
    data = copy.deepcopy(data_update.get("value"))
    for level in (3, 9, 0, 10):
        custom = {"level": level, "levelText": f"{level * 10}%"}
        data_root = data.get("data")
        assert isinstance(data_root, dict)
        data_root["custom"] = custom
        found, value = read_pointer(data, refs[0])
        assert found and value == level


@pytest.mark.parametrize("text", ["60%", "60％", "60", "水位60%"])
def test_converter_rejects_dynamic_text_even_when_initial_text_is_parseable(text):
    source = _source({"path": "/data/custom/levelText"}).replace('"60%"', json.dumps(text))
    with pytest.raises(CompactDslConversionError, match="number/integer"):
        convert_compact_dsl_to_a2ui(source, size="2x4")


@pytest.mark.parametrize("component,prop", [
    ("ProgressCircle", "externalText"), ("ProgressLine2", "value"),
    ("ProgressCircleSingle", "value"),
])
def test_progress_contract_rejects_text_and_unknown_source_types(component, prop):
    for schema_type in ("string", "boolean", None):
        errors = collect_compact_component_binding_errors(
            "progress", component, {prop: {"path": "/data/custom/levelText"}},
            schema_type_resolver=lambda _path, resolved_type=schema_type: resolved_type,
        )
        assert errors


def test_registered_readout_cannot_borrow_another_numeric_metric():
    schema = {"data": {"custom": {
        "levelText": {"type": "string", "numericSource": "/data/custom/level"},
        "level": {"type": "integer"}, "other": {"type": "integer"},
    }}}
    row = _line({"path": "/data/custom/other"})
    component = ComponentRow("line", "ProgressLine2", row[2], ())
    errors = _compact_component_binding_errors([component], schema)
    assert any("registered numeric source" in message for message in errors)


def test_unregistered_formatted_readout_does_not_authorize_other_numeric_metric():
    schema = {"data": {"custom": {
        "levelText": {"type": "string"}, "other": {"type": "integer"},
    }}}
    row = _line({"path": "/data/custom/other"})
    component = ComponentRow("line", "ProgressLine2", row[2], ())
    errors = _compact_component_binding_errors([component], schema)
    assert any("no registered numeric source" in message for message in errors)


def test_standard_artifact_rejects_legacy_private_progress_path():
    path = "/__display/data/custom/levelText/progressValue"
    components = [{"id": "ring", "component": "Progress", "value": f"{{{{ ${{{path}}} }}}}"}]
    assert progress_source_errors(components, None)
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "surface_card"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "surface_card", "root": "ring", "components": components,
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "surface_card", "path": "/", "value": {},
        }},
    ]
    reporter = validate_card(dsl_text="\n".join(json.dumps(message) for message in messages))
    assert any(item.code == "BINDING_PROGRESS_SOURCE_INVALID" for item in reporter.diagnostics)


def test_numeric_expression_does_not_accept_string_or_unregistered_dependencies():
    schema = {"data": {"custom": {"level": {"type": "integer"}}}}
    component = {"id": "ring", "component": "Progress", "value": "{{ ${/data/custom/text} }}"}
    assert progress_source_errors([component], schema)
    component["value"] = "{{ ${/data/custom/level} * 10 }}"
    assert progress_source_errors([component], schema) == []


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_registered_source_contract_is_in_assembled_model_prompts(size):
    root = (
        Path(__file__).resolve().parents[1] / "cloud/data/protocol_profiles"
        / "design-compact-dsl-fusion/prompt_source"
    )
    prompts = assemble_prompts(root, size)
    create = prompts.get("create")
    repair = prompts.get("repair")
    assert create is not None and repair is not None
    assert "numericSource 是同对象同指标" in create
    assert "动态进度约束" in create
    assert "未登记关系时不猜测" in repair
