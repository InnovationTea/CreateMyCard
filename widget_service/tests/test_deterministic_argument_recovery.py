"""确定性恢复的内容保真、结构兼容与真实路由边界；不调用真实模型。"""

import copy
import json
import re
from pathlib import Path

import pytest

from services import compact_dsl_argument_repair as repair
from services.argument_json_recovery import DECODER, repair_syntax
from services.capability_registry import CapabilityRegistry


@pytest.fixture
def registry():
    return CapabilityRegistry(version="app-11.7.7.300_rom-7.0")


def _content(registry):
    weather = registry.get_event_capability("event.open.weather")
    assert weather is not None
    return {
        "userQuery": '明天天气；原文含 "引号"、换行\n、{括号} 与 JSON 文字 {"x":1}。',
        "title": "明日天气",
        "description": "明日出行速览",
        "size": "2x2",
        "candidateDataBindings": [{
            "capabilityId": "ViewWeather", "arguments": {"forecastDays": 2},
            "writeResultTo": "/data/weather", "candidateOutputFields": ["/daily/1/weekday"],
        }],
        "candidateEventCandidates": [{
            "capabilityId": weather.id, "action": weather.actionTemplate.model_dump(mode="json"),
        }],
        "candidateAssetIds": ["asset.ic_weather_monochrome"],
    }


def _payload(content):
    return {
        "content": content,
        "deviceInfo": {"prdVer": "11.7.7.330", "romVersion": "7.0"},
    }


def _recover(content):
    return repair.recover_deterministic_content(_payload(content))


def _damaged_event(content):
    source = copy.deepcopy(content)
    events = source.get("candidateEventCandidates")
    assert isinstance(events, list)
    event = events[0]
    action = event.pop("action")
    assert isinstance(action, dict)
    action["dynamicArguments"] = [{"path": "/uri", "type": "string"}]
    event["actionTemplate"] = action
    raw = json.dumps(source, ensure_ascii=False)
    broken = raw.replace('"type": "string"}]}}]', '"type": "string"}]}]')
    assert broken != raw
    return broken


@pytest.mark.parametrize("syntax", [False, True])
def test_stringified_request_restores_exact_business_values(registry, syntax):
    source = _content(registry)
    raw = json.dumps(source, ensure_ascii=False)
    if syntax:
        raw = raw.removesuffix("}")
    outer = {"arguments": raw, "uid": "transport-user", "romVersion": "7.0"}
    before = copy.deepcopy(outer)
    result = _recover(outer)
    assert result is not None
    assert result.mode == ("syntax" if syntax else "decoded")
    assert result.attempts == 0
    assert result.dropped_candidates == ()
    for name, value in source.items():
        assert result.content.get(name) == value
    assert result.content.get("uid") == "transport-user"
    assert outer == before


def test_missing_event_brace_does_not_swallow_following_assets(registry):
    source = _content(registry)
    raw = _damaged_event(source)
    parsed = DECODER.decode(repair_syntax(raw))
    assert parsed.get("candidateAssetIds") == source.get("candidateAssetIds")
    result = _recover({"arguments": raw})
    assert result is not None
    assert result.content == source


@pytest.mark.parametrize("location", ["data", "action", "args", "alias"])
def test_only_registered_object_locations_are_decoded(registry, location):
    source = _content(registry)
    original = copy.deepcopy(source)
    data = source.get("candidateDataBindings")
    events = source.get("candidateEventCandidates")
    assert isinstance(data, list)
    assert isinstance(events, list)
    event = events[0]
    action = event.get("action")
    assert isinstance(action, dict)
    if location == "data":
        data[0]["arguments"] = json.dumps(data[0].get("arguments"))
    elif location == "action":
        event["action"] = json.dumps(action)
    elif location == "args":
        action["args"] = json.dumps(action.get("args"))
    else:
        event["actionTemplate"] = event.pop("action")
    result = _recover(source)
    assert result is not None
    assert result.content == original


@pytest.mark.parametrize("kind", ["unknown", "fixed", "missing", "type", "alias_conflict"])
def test_action_repair_never_discards_or_substitutes_business_values(registry, kind):
    source = _content(registry)
    events = source.get("candidateEventCandidates")
    assert isinstance(events, list)
    event = events[0]
    action = event.get("action")
    assert isinstance(action, dict)
    args = action.get("args")
    assert isinstance(args, dict)
    if kind == "unknown":
        event["candidateAssetIds"] = ["asset.ic_weather_monochrome"]
    elif kind == "fixed":
        args["intentName"] = "wrong-intent"
    elif kind == "missing":
        args.pop("uri")
    elif kind == "type":
        args["uri"] = 123
    else:
        event["actionTemplate"] = copy.deepcopy(action)
    with pytest.raises(ValueError):
        _recover({"arguments": json.dumps(source)})


def test_model_postprocessing_rejects_field_reparenting(registry):
    source = _content(registry)
    raw = _damaged_event(source)
    guard = repair._preserve_valid_fragments(raw, registry)
    output = copy.deepcopy(source)
    events = output.get("candidateEventCandidates")
    assert isinstance(events, list)
    events[0]["candidateAssetIds"] = output.pop("candidateAssetIds")
    with pytest.raises(ValueError):
        repair._normalize_model_output(
            json.dumps(output), {}, _payload({"arguments": raw}), registry, preserved=guard,
        )


@pytest.mark.parametrize("field_name", ["candidateDataBindings", "candidateAssetIds"])
def test_invalid_candidate_cannot_be_removed_even_when_others_are_valid(registry, field_name):
    source = _content(registry)
    values = source.get(field_name)
    assert isinstance(values, list)
    if field_name == "candidateAssetIds":
        values.append("unknown.asset")
    else:
        values.append({"capabilityId": "unknown.data", "arguments": {}, "writeResultTo": "/data/x"})
    with pytest.raises(ValueError, match="preflight rejected"):
        _recover({"arguments": json.dumps(source)})


@pytest.mark.parametrize("field_name,value", [
    ("title", "conflict"), ("size", "2x4"), ("sourceArtifactUrl", "https://test.invalid/a"),
])
def test_conflicting_outer_business_fields_fail_without_mutation(registry, field_name, value):
    source = _content(registry)
    source[field_name] = "original"
    payload = _payload({"arguments": json.dumps(source), field_name: value})
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError, match="conflicting outer field"):
        repair.recover_deterministic_content(payload)
    assert payload == before


def test_model_fallback_cannot_ignore_conflicting_outer_business_field(registry):
    source = _content(registry)
    raw = json.dumps(source)
    outer = {"arguments": raw, "title": "不同的标题"}
    guard = repair._preserve_valid_fragments(raw, registry)
    with pytest.raises(ValueError, match="conflicting outer field"):
        repair._normalize_model_output(
            json.dumps(source), outer, _payload(outer), registry, preserved=guard,
        )


def test_model_fallback_retains_business_fields_present_only_outside_arguments(registry):
    source = _content(registry)
    source.pop("candidateAssetIds")
    raw = json.dumps(source)
    outer = {
        "arguments": raw,
        "candidateAssetIds": ["asset.ic_weather_monochrome", "asset.local_fill"],
    }
    guard = repair._preserve_valid_fragments(raw, registry)
    normalized, _dropped, _warnings = repair._normalize_model_output(
        json.dumps(source), outer, _payload(outer), registry, preserved=guard,
    )
    assert normalized.get("candidateAssetIds") == outer.get("candidateAssetIds")


def test_edit_omission_and_explicit_empty_lists_remain_distinct():
    source = {"userQuery": "改颜色", "sourceArtifactUrl": "https://test.invalid/original"}
    result = _recover({"arguments": json.dumps(source)})
    assert result is not None
    assert result.content == source
    source["candidateDataBindings"] = []
    result = _recover({"arguments": json.dumps(source)})
    assert result is not None
    assert result.content.get("candidateDataBindings") == []
    source["candidateDataBindings"] = None
    with pytest.raises(ValueError):
        _recover({"arguments": json.dumps(source)})


@pytest.mark.parametrize("raw", [
    '{"title":"one","title":"two"}', '{"x":NaN}', '{"x":1e999}',
    '{"x":}', '{"x":"unfinished}', '{"x":1} {"y":2}',
])
def test_ambiguous_or_incomplete_values_are_not_autoaccepted(raw):
    with pytest.raises(ValueError):
        _recover({"arguments": raw})


def test_ordinary_valid_request_does_not_enter_recovery(registry):
    source = _content(registry)
    assert _recover(source) is None


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.asyncio
async def test_deterministic_route_precedes_model_gate_without_request_id(
    monkeypatch, registry, enabled,
):
    from api import routes
    from config.config import get_settings

    async def unexpected_model(*_args, **_kwargs):
        pytest.fail("deterministic recovery must not call the repair model")

    monkeypatch.setattr(get_settings(), "enable_compact_dsl_argument_repair_fallback", enabled)
    monkeypatch.setattr(routes, "recover_compact_dsl_content", unexpected_model)
    source = _content(registry)
    payload = _payload({"arguments": _damaged_event(source)})
    recovered = await routes._repair_compact_dsl_content_if_needed(
        payload, "generateWidgetCardCompactDsl", None, None,
    )
    assert recovered
    assert payload.get("content") == source


def test_transport_identity_is_not_taken_from_stringified_arguments(registry):
    source = _content(registry)
    source["uid"] = "nested-user"
    source["odid"] = "nested-device"
    result = _recover({
        "arguments": json.dumps(source), "uid": "outer-user", "odid": "outer-device",
    })
    assert result is not None
    assert result.content.get("uid") == "outer-user"
    assert result.content.get("odid") == "outer-device"


def test_model_cannot_drop_original_unknown_root_field(registry):
    source = _content(registry)
    source["unknown"] = "must not disappear"
    raw = json.dumps(source)
    guard = repair._preserve_valid_fragments(raw, registry)
    source.pop("unknown")
    with pytest.raises(ValueError, match="unknown fields"):
        repair._normalize_model_output(
            json.dumps(source), {}, _payload({"arguments": raw}), registry, preserved=guard,
        )


def test_recovery_does_not_coerce_string_into_business_boolean(registry):
    source = _content(registry)
    source["options"] = {"allowDegradation": "false"}
    with pytest.raises(ValueError, match="allowDegradation"):
        _recover({"arguments": json.dumps(source)})


@pytest.mark.parametrize("oversized", [False, True])
def test_recovery_input_budget_is_bounded(oversized):
    raw = '{"x":' + "[" * 65 + "0" + "]" * 65 + "}"
    if oversized:
        raw = '{"userQuery":"' + "x" * 131072 + '"}'
    with pytest.raises(ValueError, match="limit"):
        _recover({"arguments": raw})


def test_generation_tool_nested_contract_matches_skill():
    root = Path(__file__).resolve().parents[2]
    skill_root = root / "skills" / "harmony-card-generation-online"
    snapshot = skill_root / "references" / "tools"
    tool = json.loads((snapshot / "com.omega_w_0823.hmservice__generateWidgetCardCompactDsl.json")
                      .read_text(encoding="utf-8"))
    schema = tool.get("arguments")
    assert isinstance(schema, dict)
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    events = properties.get("candidateEventCandidates")
    assert isinstance(events, dict)
    item = events.get("properties", {}).get("ArrayItem")
    assert isinstance(item, dict)
    assert item.get("required") == ["capabilityId", "action"]
    assert item.get("additionalProperties") is False
    action = item.get("properties", {}).get("action")
    assert isinstance(action, dict)
    assert action.get("required") == ["call", "args"]
    assert action.get("additionalProperties") is False
    entry = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    section = entry.split("### Function: generateWidgetCardCompactDsl", 1)[1]
    line = section.split("- **参数**: ", 1)[1].splitlines()[0]
    assert json.loads(line) == schema


def test_skill_event_example_passes_current_preflight(registry):
    from api.schemas import GenerateWidgetCardRequest
    from services.edit_request_normalizer import EditRequestNormalizer
    from services.generation_preflight import GenerationPreflight

    root = Path(__file__).resolve().parents[2]
    entry = (root / "skills/harmony-card-generation-online/SKILL.md").read_text(encoding="utf-8")
    examples = re.findall(r"```json\n(.*?)\n```", entry, re.DOTALL)
    assert examples
    for example in examples:
        call = json.loads(example)
        arguments = call.get("arguments")
        assert isinstance(arguments, dict)
        request = GenerateWidgetCardRequest(
            uid="test", prdVer="11.7.7.330", device={"romVersion": "7.0"}, **arguments,
        )
        result = GenerationPreflight(registry).run(EditRequestNormalizer.normalize_create(request))
        assert result.blocking_issues == ()


def test_conflicting_event_alias_feedback_explains_value_mapping(registry):
    from pydantic import ValidationError

    from api.schemas import GenerateWidgetCardRequest
    from services.agent_feedback import request_validation_feedback

    source = _content(registry)
    events = source.get("candidateEventCandidates")
    assert isinstance(events, list)
    events[0]["actionTemplate"] = copy.deepcopy(events[0].get("action"))
    with pytest.raises(ValidationError) as error:
        GenerateWidgetCardRequest(
            uid="test", device={"romVersion": "7.0"}, prdVer="11.7.7.330", **source,
        )
    feedback = request_validation_feedback(error.value, "generateWidgetCardCompactDsl")
    issues = feedback.get("issues")
    assert isinstance(issues, list)
    matches = []
    for issue in issues:
        if issue.get("path") == "/candidateEventCandidates/0/actionTemplate":
            matches.append(issue)
    assert len(matches) == 1
    assert "完整值放入 action" in matches[0].get("repairInstruction", "")
