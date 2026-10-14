"""参数片段保留、机械修复边界与失败终态回归，不调用真实模型。"""

import json

import pytest

from models.generation import ModelRequestContext
from services import compact_dsl_argument_repair as repair
from services.argument_json_recovery import DECODER, extract_fragments, repair_syntax
from services.capability_registry import CapabilityRegistry


def _content():
    return {
        "userQuery": "天气与拨号卡片",
        "title": "天气",
        "description": "查看天气",
        "size": "2x2",
        "candidateDataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {"forecastDays": 1},
                "writeResultTo": "/data/weather",
                "candidateOutputFields": ["/current/temperatureText"],
            }
        ],
        "candidateAssetIds": ["asset.local_fill"],
    }


@pytest.fixture
def registry():
    return CapabilityRegistry(version="app-11.7.5.205_rom-6.0")


def _payload(raw):
    return {"content": {"arguments": raw}, "deviceInfo": {"prdVer": "11.7.7.225"}}


def _context():
    return ModelRequestContext(
        session_id="test",
        interaction_id="1",
        device_id="test",
        country_code="CN",
        app_version="11.7.7.225",
        app_name="test",
    )


@pytest.mark.parametrize(
    "raw",
    [
        '{"x":1',
        '{"x":[1,2,]}',
        '{"x":true "y":null}',
        '{"x":"中文","y":false,}',
    ],
)
def test_syntax_repair_preserves_values(raw):
    result = DECODER.decode(repair_syntax(raw))
    assert isinstance(result, dict) and "x" in result


@pytest.mark.parametrize(
    "raw",
    [
        '{"x":}',
        "{x:1}",
        '{"x":"unfinished}',
        '{"x":NaN}',
        '{"x":1,"x":2}',
        '{"x":1} explanation',
        '{"x":1e999}',
    ],
)
def test_syntax_repair_rejects_value_guessing_and_loss(raw):
    with pytest.raises(ValueError):
        repair_syntax(raw)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_strict_model_parser_rejects_ambiguous_json(raw):
    with pytest.raises(repair.CompactDslArgumentRepairError):
        repair._strict_json_object(raw)


def test_extraction_does_not_read_nested_or_quoted_keys():
    raw = json.dumps(
        {
            "description": 'text "candidateAssetIds":["not-real"]',
            "nested": {"candidateAssetIds": ["nested"]},
            "candidateAssetIds": ["real"],
        }
    )
    fragments = extract_fragments(raw)
    assert fragments.fields.get("candidateAssetIds") == ["real"]


def test_duplicate_top_level_field_is_not_locked():
    fragments = extract_fragments('{"title":"one","title":"two"}')
    assert "title" not in fragments.fields
    assert fragments.damaged_fields == ["title"]


def test_truncated_array_keeps_only_complete_prefix():
    fragments = extract_fragments('{"candidateAssetIds":["first","broken')
    assert fragments.array_prefixes.get("candidateAssetIds") == ["first"]
    assert fragments.damaged_fields == ["candidateAssetIds"]


def test_candidate_fragment_is_validated_before_locking(registry):
    original = _content()
    original["candidateDataBindings"] = [
        {
            "capabilityId": "ViewWeather",
            "arguments": {"forecastDays": "invalid"},
            "writeResultTo": "/data/weather",
            "candidateOutputFields": [],
        }
    ]
    original["candidateAssetIds"] = ["unknown.asset"]
    guard = repair._preserve_valid_fragments(json.dumps(original), registry)
    assert "candidateDataBindings" not in guard.fields
    assert "candidateAssetIds" not in guard.fields


def test_intact_data_and_assets_survive_damaged_event_and_model_overwrite(registry):
    original = _content()
    raw = json.dumps(original).removesuffix("}") + ',"candidateEventCandidates":[broken'
    guard = repair._preserve_valid_fragments(raw, registry)
    assert guard.fields.get("candidateDataBindings") == original.get("candidateDataBindings")
    assert guard.fields.get("candidateAssetIds") == original.get("candidateAssetIds")
    event = {
        "capabilityId": "event.call.phone",
        "action": {
            "call": "clickToApi",
            "args": {
                "intentName": "CallPhone",
                "params": {
                    "phoneNumber": "122",
                    "relationship": "",
                },
            },
        },
    }
    output = {
        "candidateDataBindings": [],
        "candidateAssetIds": [],
        "candidateEventCandidates": [event],
    }
    normalized, dropped, _warnings = repair._normalize_model_output(
        json.dumps(output),
        {},
        _payload(raw),
        registry,
        preserved=guard,
    )
    assert normalized.get("candidateDataBindings") == original.get("candidateDataBindings")
    assert normalized.get("candidateAssetIds") == original.get("candidateAssetIds")
    assert not dropped


@pytest.mark.parametrize("output", [{}, {"candidateEventCandidates": []}])
def test_model_cannot_erase_damaged_array(registry, output):
    raw = json.dumps(_content()).removesuffix("}") + ',"candidateEventCandidates":[broken'
    guard = repair._preserve_valid_fragments(raw, registry)
    with pytest.raises(repair.CompactDslArgumentRepairError, match="damaged field"):
        repair._normalize_model_output(
            json.dumps(output), {}, _payload(raw), registry, preserved=guard
        )


def test_missing_brace_model_output_is_repaired_without_changing_data(registry):
    content = _content()
    raw = json.dumps(content).removesuffix("}")
    result, _dropped, _warnings = repair._normalize_model_output(raw, {}, _payload(raw), registry)
    assert result.get("candidateDataBindings") == content.get("candidateDataBindings")


def test_empty_patch_allowed_when_entire_original_request_is_locked(registry):
    content = _content()
    raw = json.dumps(content)
    guard = repair._preserve_valid_fragments(raw, registry)
    normalized, _dropped, _warnings = repair._normalize_model_output(
        "{}",
        {},
        _payload(raw),
        registry,
        preserved=guard,
    )
    assert normalized.get("candidateDataBindings") == content.get("candidateDataBindings")


def test_valid_prefix_data_item_cannot_be_overwritten(registry):
    content = _content()
    bindings = content.get("candidateDataBindings")
    assert isinstance(bindings, list)
    first = bindings[0]
    raw = '{"candidateDataBindings":[' + json.dumps(first) + ',{"broken":'
    guard = repair._preserve_valid_fragments(raw, registry)
    assert guard.items.get("candidateDataBindings") == {0: first}
    changed = {"candidateDataBindings": [{"capabilityId": "wrong"}, {"repaired": True}]}
    merged = guard.merge(changed)
    values = merged.get("candidateDataBindings")
    assert isinstance(values, list)
    assert values[0] == first


def test_invalid_output_field_is_not_locked(registry):
    content = _content()
    bindings = content.get("candidateDataBindings")
    assert isinstance(bindings, list)
    bindings[0]["candidateOutputFields"] = ["/not/a/real/field"]
    guard = repair._preserve_valid_fragments(json.dumps(content), registry)
    assert "candidateDataBindings" not in guard.fields
    assert "candidateDataBindings" in guard.required_fields


def test_losing_all_invalid_candidates_is_failure_not_static_success(registry):
    content = _content()
    content["candidateDataBindings"] = []
    content["candidateAssetIds"] = ["unknown.asset"]
    with pytest.raises(repair.CompactDslArgumentRepairError, match="no usable candidates"):
        repair._normalize_model_output(json.dumps(content), {}, {}, registry)


def test_raw_client_output_logged_even_if_empty(monkeypatch):
    from custom import a2ui_model_client

    messages = []
    monkeypatch.setattr(a2ui_model_client.logger, "info", messages.append)
    client = a2ui_model_client.A2UIModelClient(use_mock=True)
    client._process_model_output("", {"format": "raw-json"})
    assert any('raw_output=""' in message for message in messages)


@pytest.mark.parametrize(
    "raw",
    [
        '{"uid":"secret-id","title":"keep"}',
        '{"odid":"secret-id","broken":',
        '{"callingUid":"secret-id',
    ],
)
def test_model_output_logs_redact_identity_even_for_invalid_json(monkeypatch, raw):
    from app.logger import get_settings, json_text_for_log

    monkeypatch.setattr(get_settings(), "enable_sensitive_log_fields", False)
    assert "secret-id" not in json_text_for_log(raw)


def test_existing_event_array_cannot_be_omitted(registry):
    raw = json.dumps({**_content(), "candidateEventCandidates": [{"broken": True}]})
    guard = repair._preserve_valid_fragments(raw, registry)
    with pytest.raises(ValueError, match="omitted damaged field"):
        guard.merge({})


def test_explicit_empty_events_and_options_are_preserved(registry):
    original = {**_content(), "candidateEventCandidates": [], "options": {}}
    raw = json.dumps(original)
    guard = repair._preserve_valid_fragments(raw, registry)
    merged = guard.merge({})
    assert merged.get("candidateEventCandidates") == []
    assert merged.get("options") == {}


@pytest.mark.asyncio
async def test_transport_errors_are_bounded_and_fail_closed(monkeypatch, registry):
    calls = []

    async def generate(*_args, **_kwargs):
        calls.append(True)
        raise TimeoutError("test timeout")

    async def close(_self):
        return None

    monkeypatch.setattr(repair.A2UIModelClient, "generate", generate)
    monkeypatch.setattr(repair.A2UIModelClient, "aclose", close)
    monkeypatch.setattr(repair, "_select_capability_registry", lambda *_: (registry, []))
    with pytest.raises(repair.CompactDslArgumentRepairExhaustedError):
        await repair.recover_compact_dsl_content(
            _payload("broken"),
            backend="mep",
            model_runtime=None,
            request_context=_context(),
            max_attempts=2,
        )
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_every_attempt_is_logged_and_exhaustion_never_returns_minimal(monkeypatch, registry):
    outputs = iter(['{"broken":', "not json"])
    messages = []
    closed = []

    async def generate(*_args, **_kwargs):
        return next(outputs)

    async def close(_self):
        closed.append(True)

    monkeypatch.setattr(repair.A2UIModelClient, "generate", generate)
    monkeypatch.setattr(repair.A2UIModelClient, "aclose", close)
    monkeypatch.setattr(repair, "_select_capability_registry", lambda *_: (registry, []))
    monkeypatch.setattr(repair.logger, "info", messages.append)
    with pytest.raises(repair.CompactDslArgumentRepairExhaustedError):
        await repair.recover_compact_dsl_content(
            _payload("broken"),
            backend="mep",
            model_runtime=None,
            request_context=_context(),
            max_attempts=2,
        )
    output_logs = [message for message in messages if " model_output " in message]
    assert len(output_logs) == 2
    assert "attempt=1" in output_logs[0] and "broken" in output_logs[0]
    assert "attempt=2" in output_logs[1] and "not json" in output_logs[1]
    assert closed == [True]


@pytest.mark.asyncio
async def test_repair_attempts_include_errors_and_locked_fields(monkeypatch, registry):
    prompts = []
    outputs = iter(["not json", "{}"])

    async def generate(_self, prompt, _profile, **_kwargs):
        prompts.append(prompt)
        return next(outputs)

    async def close(_self):
        return None

    monkeypatch.setattr(repair.A2UIModelClient, "generate", generate)
    monkeypatch.setattr(repair.A2UIModelClient, "aclose", close)
    monkeypatch.setattr(repair, "_select_capability_registry", lambda *_: (registry, []))
    original = _content()
    original["romVersion"] = "7.0"
    payload = _payload(json.dumps(original))
    content = payload.get("content")
    assert isinstance(content, dict)
    content["romVersion"] = "6.0"
    result = await repair.recover_compact_dsl_content(
        payload,
        backend="mep",
        model_runtime=None,
        request_context=_context(),
        max_attempts=2,
    )
    assert result.mode == "model_retry" and result.attempts == 2
    assert result.content.get("romVersion") == "6.0"
    assert result.content.get("candidateDataBindings") == original.get("candidateDataBindings")
    retry_input = json.loads(prompts[1][1].get("content", ""))
    assert retry_input.get("previousOutput") == "not json"
    assert retry_input.get("validationErrors")
    assert retry_input.get("lockedFields")
