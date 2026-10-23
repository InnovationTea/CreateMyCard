"""八类开关的可选标记贯穿入口、Plan、DSL、转换和交付校验。"""

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from api.schemas import CandidateEventCandidate, GenerateWidgetCardRequest
from models.capability import EventCapability
from services.capability_registry import CapabilityRegistry
from services.card_validation import validate_card
from services.compact_composition_context import repair_action_labels
from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
from services.compact_high_level_components import ComponentRow
from services.compact_plan import compact_plan_coverage_errors, parse_compact_plan_call
from services.event_matching import event_handlers_match
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.generation_preflight import GenerationPreflight
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan.action_labels import parameter_action_label

_ROOT = Path(__file__).resolve().parents[2]
_OMITTED = object()
_FLAGS = (pytest.param(_OMITTED, id="omitted"), 0, 1)
_EVENTS = (
    "event.setPowerSavingMode", "event.setNearLinkMode", "event.setBluetoothMode",
    "event.setWifiMode", "event.setMobileData", "event.setLocationSwitch",
    "event.setScreenUseTimeManageSwitch", "event.setMicPermissionSwitch",
)


@dataclass(frozen=True)
class _PipelineInputs:
    task: dict
    plan: dict
    source: str


@pytest.fixture(scope="module")
def registry() -> CapabilityRegistry:
    return CapabilityRegistry(version="app-11.7.7.300_rom-7.0")


def _handler(registry: CapabilityRegistry, event_id: str, flag: object = _OMITTED) -> dict:
    capability = registry.get_event_capability(event_id)
    assert capability is not None
    handler = capability.actionTemplate.model_dump(mode="json")
    args = handler.get("args")
    assert isinstance(args, dict)
    params = args.get("params")
    assert isinstance(params, dict)
    assert "switchFlag" not in params
    if flag is not _OMITTED:
        params["switchFlag"] = flag
    return handler


def _request(event_id: str, handler: dict) -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="optional-switch", userQuery="开关操作", title="开关", description="开关操作",
        size="2x2", prdVer="11.7.7.300", device={"romVersion": "7.0"},
        candidateEventCandidates=[{"capabilityId": event_id, "action": handler}],
    )


def _params(handler: dict) -> dict:
    args = handler.get("args")
    assert isinstance(args, dict)
    params = args.get("params")
    assert isinstance(params, dict)
    return params


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("expected_flag", _FLAGS)
@pytest.mark.parametrize("actual_flag", _FLAGS)
def test_optional_flags_match_without_mutating_either_handler(
    registry: CapabilityRegistry, event_id: str, expected_flag: object, actual_flag: object,
) -> None:
    actual = _handler(registry, event_id, actual_flag)
    expected = _handler(registry, event_id, expected_flag)
    original = copy.deepcopy((actual, expected))
    assert event_handlers_match(actual, expected)
    assert (actual, expected) == original


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", _FLAGS)
def test_preflight_accepts_optional_flag_and_keeps_submitted_form(
    registry: CapabilityRegistry, event_id: str, flag: object,
) -> None:
    handler = _handler(registry, event_id, flag)
    result = GenerationPreflight(registry).run(_request(event_id, handler))
    assert not result.blocking_issues
    assert len(result.effective_events) == 1
    assert result.effective_events[0].args == handler.get("args")


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", [None, True, False, "0", "1", 0.0, 1.0, -1, 2])
def test_invalid_explicit_flags_are_never_equivalent(
    registry: CapabilityRegistry, event_id: str, flag: object,
) -> None:
    invalid = _handler(registry, event_id, flag)
    assert not event_handlers_match(invalid, _handler(registry, event_id))
    assert not event_handlers_match(invalid, invalid)


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", [None, True, False, "0", "1", 0.0, 1.0, -1, 2])
def test_preflight_rejects_invalid_explicit_flags(
    registry: CapabilityRegistry, event_id: str, flag: object,
) -> None:
    handler = _handler(registry, event_id, flag)
    result = GenerationPreflight(registry).run(_request(event_id, handler))
    assert any(issue.code == "EVENT_ARGUMENT_SCHEMA_INVALID" for issue in result.blocking_issues)


@pytest.mark.parametrize("event_id", _EVENTS)
def test_params_object_remains_required(registry: CapabilityRegistry, event_id: str) -> None:
    handler = _handler(registry, event_id)
    args = handler.get("args")
    assert isinstance(args, dict)
    args.pop("params")
    result = GenerationPreflight(registry).run(_request(event_id, handler))
    assert result.blocking_issues


@pytest.mark.parametrize("event_id", _EVENTS)
def test_extra_parameters_do_not_gain_authorization(
    registry: CapabilityRegistry, event_id: str,
) -> None:
    actual = _handler(registry, event_id)
    _params(actual)["unexpected"] = 1
    assert not event_handlers_match(actual, _handler(registry, event_id))
    result = GenerationPreflight(registry).run(_request(event_id, actual))
    assert result.blocking_issues


def _pipeline_inputs(expected: dict, actual: dict, size: str) -> _PipelineInputs:
    events = [
        {"id": "switch", "description": "开关操作", **expected},
        {"id": "phone", "description": "拨号", "call": "clickToCallPhone",
         "args": {"phoneNumber": "10086"}},
    ]
    layout = "S-content-dual-action" if size == "2x2" else "W-content-side-slots"
    task = {
        "size": size, "appVersion": "99.0", "userQuery": "开关操作和拨号",
        "dataModelSchema": {"data": {}}, "eventCandidates": events,
        "assetCandidates": [
            {"id": "switch-icon", "src": "resources/base/media/ic_switch.svg"},
            {"id": "phone-icon", "src": "resources/base/media/phone_fill.svg"},
        ],
    }
    facts = []
    for event in events:
        facts.append({"actionId": event.get("id"), "requirement": "操作", "priority": "must"})
    plan = parse_compact_plan_call(json.dumps({"name": "submit_card_plan", "arguments": {
        "info_required": facts, "layoutHints": [layout],
        "assetAssignments": {
            "actions": [{"actionId": "switch", "assetId": "switch-icon"},
                        {"actionId": "phone", "assetId": "phone-icon"}],
            "title": {"assetId": None, "reason": "动作布局无标题"},
        },
    }}), task).plan
    if size == "2x2":
        root = ["root", "Layout", {"layout": layout, "variant": "actions-only"},
                ["switch", "phone"]]
    else:
        root = ["root", "Layout", {"layout": "W-content-side-slots"},
                ["content", "switch", "phone"]]
    rows = [root]
    if size == "2x4":
        rows.append(["content", "Region", {"variant": "center"}, ["body"]])
        rows.append(["body", "EmphasisText", {"mainText": "快捷操作"}])
    action_type = "PillButton" if size == "2x2" else "CardButton"
    rows.extend([
        ["switch", action_type, {"label": "开关", "icon": "resources/base/media/ic_switch.svg",
                                 "onClick": [actual]}],
        ["phone", action_type, {"label": "拨号", "icon": "resources/base/media/phone_fill.svg",
                                 "onClick": [{
                                     "call": "clickToCallPhone",
                                     "args": {"phoneNumber": "10086"},
                                 }]}],
    ])
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    return _PipelineInputs(task=task, plan=plan, source=source)


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("expected_flag", _FLAGS)
@pytest.mark.parametrize("actual_flag", _FLAGS)
@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_pipeline_preserves_optional_form_through_plan_assets_and_final_validation(
    registry: CapabilityRegistry, event_id: str, expected_flag: object, actual_flag: object,
    size: str,
) -> None:
    actual = _handler(registry, event_id, actual_flag)
    expected = _handler(registry, event_id, expected_flag)
    inputs = _pipeline_inputs(expected, actual, size)
    assert not compact_plan_coverage_errors(inputs.source, inputs.plan, inputs.task)
    assert repair_action_labels(inputs.source, inputs.task).get("switch") == "开关"
    result = DesignCompactProcessor().process(inputs.source, DslProcessingContext(
        size=size, card_spec={"suggestSize": size}, task_spec=inputs.task, protocol_profile={},
        compact_plan=inputs.plan,
        layout_scope="S-content-dual-action" if size == "2x2" else "W-content-side-slots",
    ))
    assert not result.errors
    for row in parse_compact_dsl_rows(result.source_dsl):
        if isinstance(row, ComponentRow) and row.component_id == "switch":
            assert row.props.get("onClick") == [actual]
    for effective in (None, {"data": [], "event": inputs.task.get("eventCandidates"),
                             "asset": inputs.task.get("assetCandidates")}):
        report = validate_card(dsl_text=result.standard_dsl, effective_capabilities=effective)
        assert not report.has_code("EFFECTIVE_EVENT_NOT_ALLOWED", "EVENT_ARGUMENT_INVALID")


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", [None, True, "0", 0.0, 2])
def test_binding_repair_does_not_replace_invalid_flag_with_candidate(
    registry: CapabilityRegistry, event_id: str, flag: object,
) -> None:
    inputs = _pipeline_inputs(
        _handler(registry, event_id), _handler(registry, event_id, flag), "2x2",
    )
    assert "switch" not in repair_action_labels(inputs.source, inputs.task)
    result = DesignCompactProcessor().process(inputs.source, DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"}, task_spec=inputs.task, protocol_profile={},
        compact_plan=inputs.plan, layout_scope="S-content-dual-action",
    ))
    assert result.errors


@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", _FLAGS)
def test_action_labels_do_not_infer_direction_from_equivalent_flag(
    registry: CapabilityRegistry, event_id: str, flag: object,
) -> None:
    handler = _handler(registry, event_id, flag)
    assert parameter_action_label(event_id, handler.get("args")) is None


@pytest.mark.parametrize("skill", [
    "harmony-card-generation-online", "harmony-card-generation-offline",
])
def test_skill_schemas_match_cloud_optional_switch_contract(skill: str) -> None:
    cloud_path = _ROOT / "widget_service/cloud/data/validator_rules/schemas/event.click.schema.json"
    skill_path = _ROOT / "skills" / skill / "scripts/rules/schemas/event.click.schema.json"
    cloud_functions = json.loads(cloud_path.read_text(encoding="utf-8")).get("functions")
    skill_functions = json.loads(skill_path.read_text(encoding="utf-8")).get("functions")
    assert isinstance(cloud_functions, dict)
    assert isinstance(skill_functions, dict)
    targets = (
        ("clickToApi", "SetMobileData"), ("clickToIntent", "SetSettingSwitch"),
        ("clickToIntent", "SetLocationSettingSwicth"),
        ("clickToIntent", "SetScreenUseTimeManageSwitch"),
        ("clickToIntent", "SetMicSettingSwicth"),
    )
    for call, intent in targets:
        cloud = cloud_functions.get(call)
        skill_function = skill_functions.get(call)
        assert isinstance(cloud, dict)
        assert isinstance(skill_function, dict)
        cloud_intents = cloud.get("supportedIntents")
        skill_intents = skill_function.get("supportedIntents")
        assert isinstance(cloud_intents, dict)
        assert isinstance(skill_intents, dict)
        assert skill_intents.get(intent) == cloud_intents.get(intent)


@pytest.mark.parametrize("event_id", _EVENTS)
def test_registry_does_not_declare_legacy_flag(
    registry: CapabilityRegistry, event_id: str,
) -> None:
    capability = registry.get_event_capability(event_id)
    assert capability is not None
    assert not capability.dynamicArguments
    Draft202012Validator.check_schema(capability.parametersSchema)
    assert "switchFlag" not in capability.model_dump_json()
    assert "x-compatibility-only" not in capability.model_dump_json()
    handler = _handler(registry, event_id)
    errors = Draft202012Validator(capability.parametersSchema).iter_errors(handler.get("args"))
    assert not list(errors)


def test_model_prompts_do_not_embed_switch_compatibility_rules() -> None:
    for size in ("2x2", "2x4"):
        prompt = A2UIProtocolRegistry.read_design_prompt("design-compact-dsl", size=size)
        assert "switchFlag" not in prompt
    assert "switchFlag" not in A2UIProtocolRegistry.read_design_repair_prompt("design-compact-dsl")
    guide = _ROOT / "skills/harmony-card-generation-online/references/runtime-guide.md"
    assert "switchFlag" not in guide.read_text(encoding="utf-8")


@pytest.mark.parametrize("required", [False, True])
def test_registry_does_not_relax_other_template_completeness(
    registry: CapabilityRegistry, required: bool,
) -> None:
    capability = registry.get_event_capability("event.setWifiMode")
    assert capability is not None
    declaration = capability.model_dump(mode="json")
    schema = declaration.get("parametersSchema")
    assert isinstance(schema, dict)
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    params = properties.get("params")
    assert isinstance(params, dict)
    param_properties = params.get("properties")
    assert isinstance(param_properties, dict)
    param_properties["extra"] = {"type": "integer", "description": "未在模板中声明的参数"}
    if required:
        required_names = params.get("required")
        assert isinstance(required_names, list)
        required_names.append("extra")
    with pytest.raises(ValueError, match="schema field is missing from actionTemplate.args"):
        EventCapability.model_validate(declaration)


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
@pytest.mark.parametrize("event_id", _EVENTS)
@pytest.mark.parametrize("flag", _FLAGS)
async def test_registered_optional_switch_completes_service_without_repair(
    registry: CapabilityRegistry, event_id: str, flag: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from models.service import ArtifactSaveResult
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    request = _request(event_id, _handler(registry, event_id))
    flashlight = registry.get_event_capability("event.openFlashlight")
    assert flashlight is not None
    second_handler = flashlight.actionTemplate.model_dump(mode="json")
    request.candidateEventCandidates.append(CandidateEventCandidate(
        capabilityId=flashlight.id, action=second_handler,
    ))
    facts = []
    for selected_id in (event_id, flashlight.id):
        facts.append({"actionId": selected_id, "requirement": "操作", "priority": "must"})
    rows = [
        ["root", "Layout", {"layout": "S-content-dual-action", "variant": "actions-only"},
         ["switch", "flashlight"]],
        ["switch", "PillButton", {
            "label": "开关", "onClick": [_handler(registry, event_id, flag)],
        }],
        ["flashlight", "PillButton", {"label": "手电筒", "onClick": [second_handler]}],
    ]
    calls = []

    async def generate(_self, _prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        calls.append(model_format)
        if model_format == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": {
                "info_required": facts, "layoutHints": ["S-content-dual-action"],
            }})
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: False)
    monkeypatch.setattr(ArtifactStore, "save", lambda *_args: ArtifactSaveResult(
        artifactUrl="https://artifact.test/optional-switch", artifactDigest="sha256:test",
    ))
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status.value == "success"
    assert calls == ["raw-json", "compact-dsl"]
