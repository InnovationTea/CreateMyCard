"""候选别名恢复必须无损、确定且不能绕过正式校验。"""

import copy
import json

import pytest
from pydantic import ValidationError

from api.routes import _normalize_payload
from api.schemas import GenerateWidgetCardRequest
from services import candidate_argument_normalizer as normalizer
from services.agent_error_view import agent_error_view
from services.agent_feedback import request_validation_feedback
from services.capability_registry import CapabilityRegistry
from services.generation_preflight import GenerationPreflight

DATA = {
    "capabilityId": "ViewWeather",
    "arguments": {"districtName": "雨花台区", "prefectureName": "南京市", "forecastDays": 1},
    "writeResultTo": "/data/weather",
    "candidateOutputFields": ["/current/temperatureText"],
}
EVENT = {
    "capabilityId": "event.open.weather",
    "action": {"call": "clickToDeeplink", "args": {"bundleName": ""}},
}


def _request(**fields):
    return {
        "uid": "test", "device": {"romVersion": "7.0"},
        "prdVer": "11.7.7.330",
        "userQuery": "天气与会议速览", "title": "雨天出行", "description": "速览",
        "size": "2x4", **fields,
    }


@pytest.mark.parametrize("alias", normalizer.CANDIDATE_ALIASES.get("candidateDataBindings", ()))
@pytest.mark.parametrize("encoded", [False, True])
def test_data_aliases_preserve_values_and_order(alias, encoded):
    first = copy.deepcopy(DATA)
    first["arguments"] = {"zero": 0, "enabled": False, "empty": "", "data": ["nested"]}
    first["candidateOutputFields"] = ["/value"]
    second = copy.deepcopy(DATA)
    candidates = [first, second]
    values = [json.dumps(item) for item in candidates] if encoded else candidates
    arguments = _request(**{alias: values})
    original = copy.deepcopy(arguments)
    result = normalizer.normalize_candidate_arguments(arguments)
    assert result.get("candidateDataBindings") == candidates
    assert alias not in result
    assert arguments == original
    assert normalizer.normalize_candidate_arguments(result) == result


@pytest.mark.parametrize("alias", normalizer.CANDIDATE_ALIASES.get("candidateEventCandidates", ()))
def test_event_aliases(alias):
    result = normalizer.normalize_candidate_arguments({alias: [json.dumps(EVENT)]})
    assert result.get("candidateEventCandidates") == [EVENT]


@pytest.mark.parametrize("alias", normalizer.CANDIDATE_ALIASES.get("candidateAssetIds", ()))
def test_asset_aliases(alias):
    values = ["asset.icon_car", "asset.drop_1", "asset.icon_car"]
    result = normalizer.normalize_candidate_arguments(_request(**{alias: values}))
    assert result.get("candidateAssetIds") == values


@pytest.mark.parametrize("value", [
    [], None, ["ViewWeather"], [{"id": "ViewWeather", "inputSchema": {}}],
    [DATA, {}], ["{}"], ['{"capabilityId":"x","capabilityId":"y"}'],
    ['{"value":NaN}'], ['{"value":1e999}'], ['{"value":'],
    [" " * 131073], ["[" * 70 + "0" + "]" * 70],
])
def test_invalid_alias_remains_visible_to_request_validation(value):
    arguments = _request(data=value)
    original = copy.deepcopy(arguments)
    result = normalizer.normalize_candidate_arguments(arguments)
    assert result == original
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**result)
    locations = [item.get("loc") for item in caught.value.errors()]
    assert ("data",) in locations


@pytest.mark.parametrize("fields", [
    {"data": [DATA], "candidateDataBindings": []},
    {"data": [DATA], "candidateDataBindings": None},
    {"data": [DATA], "candidateDataBindings": [DATA]},
    {"data": [DATA], "dataList": [DATA]},
    {"events": [EVENT], "candidateEvents": [EVENT]},
    {"assets": ["a"], "candidateAssetIds": ["a"]},
])
def test_conflicts_are_never_merged_or_overwritten(fields):
    arguments = _request(**fields)
    assert normalizer.normalize_candidate_arguments(arguments) == arguments
    with pytest.raises(ValidationError):
        GenerateWidgetCardRequest(**normalizer.normalize_candidate_arguments(arguments))


def test_unknown_fields_survive_normalization_and_are_rejected():
    binding = {**DATA, "inputSchema": {}}
    arguments = normalizer.normalize_candidate_arguments(_request(data=[binding]))
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    locations = [item.get("loc") for item in caught.value.errors()]
    assert ("candidateDataBindings", 0, "inputSchema") in locations


def test_normalization_does_not_grant_capability_or_skip_preflight():
    binding = {**DATA, "capabilityId": "not-registered"}
    arguments = normalizer.normalize_candidate_arguments(_request(data=[binding]))
    request = GenerateWidgetCardRequest(**arguments)
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    result = GenerationPreflight(registry).run(request)
    assert result.blocking_issues
    assert result.card_spec is None


@pytest.mark.parametrize("envelope", [True, False])
def test_compact_route_recovers_reported_shapes_and_keeps_context(envelope):
    arguments = _request(
        data=[json.dumps(DATA), json.dumps({
            "capabilityId": "GetCalendarEvents", "arguments": {"futureDays": 1},
            "writeResultTo": "/data/calendar",
            "candidateOutputFields": ["/eventCount"],
        })],
        candidateEventCandidates=[EVENT],
        candidateAssetCandidates=["asset.icon_car", "asset.drop_1"],
    )
    payload = {"arguments": arguments, "requestId": "request"}
    if envelope:
        payload = {"content": arguments, "deviceInfo": {"romVersion": "7.0"}}
    _, result = _normalize_payload(payload, "generateWidgetCardCompactDsl")
    request = GenerateWidgetCardRequest(**result)
    assert request.uid == "test"
    assert request.device.romVersion == "7.0"
    assert request.candidateDataBindings is not None
    assert len(request.candidateDataBindings) == 2
    assert request.candidateAssetIds == ["asset.icon_car", "asset.drop_1"]
    assert request.candidateEventCandidates is not None


def test_other_routes_and_nested_business_fields_are_unchanged():
    arguments = _request(data=[DATA], arbitraryAlias=[DATA])
    _, result = _normalize_payload({"arguments": arguments}, "generateWidgetCard")
    assert result == arguments
    normalized = normalizer.normalize_candidate_arguments(arguments)
    assert normalized.get("arbitraryAlias") == [DATA]


def test_edit_preserves_source_and_omitted_categories():
    source = "https://example.test/source"
    arguments = {"sourceArtifactUrl": source, "data": [DATA]}
    result = normalizer.normalize_candidate_arguments(arguments)
    assert result.get("sourceArtifactUrl") == source
    assert result.get("candidateDataBindings") == [DATA]
    assert "candidateEventCandidates" not in result
    assert "candidateAssetIds" not in result


def test_normal_logs_do_not_contain_business_values(monkeypatch):
    messages = []
    monkeypatch.setattr(normalizer.logger, "info", messages.append)
    normalizer.normalize_candidate_arguments({"data": [DATA]})
    normalizer.normalize_candidate_arguments({"data": ['{"private":"x","private":"y"}']})
    normalizer.normalize_candidate_arguments({"data": [DATA], "dataList": [DATA]})
    text = "\n".join(messages)
    assert 'candidate_alias_normalized source="data" target=candidateDataBindings' in text
    assert "invalid_structure_or_encoding" in text
    assert "field_conflict" in text
    assert "private" not in text
    assert "雨花台区" not in text


def test_new_alias_feedback_guides_reconstruction_when_not_recoverable():
    arguments = _request(dataIds=["ViewWeather"], candidateAssetCandidates=[])
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**normalizer.normalize_candidate_arguments(arguments))
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    assert result.get("retryable") is True
    assert "candidateDataBindings" in str(result)
    assert "candidateAssetIds" in str(result)


@pytest.mark.parametrize("name,target,value", [
    ("WeatherDATA", "candidateDataBindings", DATA),
    ("myDataList", "candidateDataBindings", DATA),
    ("DATA", "candidateDataBindings", DATA),
    ("CLICKevents", "candidateEventCandidates", EVENT),
    ("EventList", "candidateEventCandidates", EVENT),
    ("chosenASSETS", "candidateAssetIds", "asset.icon_car"),
])
def test_keyword_and_structure_must_agree(name, target, value):
    arguments = _request(**{name: [value]})
    result = normalizer.normalize_candidate_arguments(arguments)
    assert name not in result
    assert result.get(target) == [value]
    GenerateWidgetCardRequest(**result)


@pytest.mark.parametrize("fields", [
    {"metadata": {"version": 1}},
    {"myDATA": [EVENT]},
    {"myEVENT": [DATA]},
    {"dataEventList": [DATA]},
    {"eventAssetList": [EVENT]},
    {"myData": [DATA], "data": [DATA]},
    {"myData": [DATA], "DATA": [DATA]},
    {"myData": [DATA], "candidateDataBindings": None},
    {"myData": [DATA], "candidateDataBindings": [DATA]},
    {"dataCapabilityIds": [DATA]},
    {"eventCapabilityIds": [EVENT]},
    {"options": {"myData": [DATA]}},
    {"sourceArtifactUrl": [DATA]},
    {"candidateDataBindings": [json.dumps(DATA)]},
])
def test_ambiguous_conflicting_or_protected_fields_are_not_reinterpreted(fields):
    arguments = _request(**fields)
    original = copy.deepcopy(arguments)
    assert normalizer.normalize_candidate_arguments(arguments) == original
    assert arguments == original


@pytest.mark.parametrize("name", ["assetCandidates", "myASSETList"])
@pytest.mark.parametrize("values", [["unknown-asset"], ["asset.icon_car", "unknown-asset"]])
def test_assets_require_all_registered_ids(name, values):
    arguments = _request(**{name: values})
    assert normalizer.normalize_candidate_arguments(arguments) == arguments


@pytest.mark.parametrize("fallback", [False, True])
def test_asset_version_selection_obeys_existing_fallback(monkeypatch, fallback):
    from config.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_default_capability_registry_fallback", fallback)
    monkeypatch.setattr(settings, "capability_registry_version", "app-11.7.7.300_rom-7.0")
    arguments = _request(prdVer="99.0", myAssets=["asset.icon_car"])
    result = normalizer.normalize_candidate_arguments(arguments)
    assert ("candidateAssetIds" in result) is fallback
    if not fallback:
        assert result == arguments


@pytest.mark.parametrize("context", [
    {"uid": None}, {"device": None}, {"prdVer": []},
    {"device": {"romVersion": "7.0", "_sourceRomVersion": []}},
])
def test_invalid_asset_context_is_not_guessed(context):
    arguments = _request(myAssets=["asset.icon_car"], **context)
    assert normalizer.normalize_candidate_arguments(arguments) == arguments


def test_registry_unavailable_preserves_original_asset_field(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OSError("private_registry_path")

    monkeypatch.setattr(CapabilityRegistry, "get_asset_capability", unavailable)
    arguments = _request(myAssets=["asset.icon_car"])
    assert normalizer.normalize_candidate_arguments(arguments) == arguments


def test_version_selection_prefers_original_rom_context(monkeypatch):
    from config.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_default_capability_registry_fallback", False)
    arguments = _request(
        myAssets=["asset.icon_car"],
        device={"romVersion": "99.0", "_sourceRomVersion": "7.0"},
    )
    result = normalizer.normalize_candidate_arguments(arguments)
    assert result.get("candidateAssetIds") == ["asset.icon_car"]
