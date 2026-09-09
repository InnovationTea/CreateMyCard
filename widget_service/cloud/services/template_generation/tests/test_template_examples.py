"""模版场景示例页签的输入、事件和批跑回归。"""

import json
from datetime import date
from pathlib import Path

import pytest

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.pipeline import _with_trusted_sample_overrides
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.test_support.template_examples import (
    EXAMPLE_PROVIDER_ID,
    append_template_examples,
    load_template_examples,
)
from services.template_generation.tests.test_provider_gallery_batch import _GalleryService


def test_weather_details_label_preserves_explicit_label() -> None:
    event = EventAction(id="event.open.weather", call="clickToDeeplink", args={})
    task = TaskSpec(userQuery="查看详情", size="2x2", dataModelSchema={}, eventCandidates=[event])
    assert action_bindings(task)[0].display_label == "查看详情"
    explicit = event.model_copy(update={"displayLabel": "查看天气"})
    task.eventCandidates = [explicit]
    assert action_bindings(task)[0].display_label == "查看天气"


@pytest.mark.parametrize("index", range(8))
def test_examples_preserve_requested_fields_samples_and_registered_actions(
    tmp_path: Path, index: int,
) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    manifest = append_template_examples(tmp_path)
    provider = manifest.providers[-1]
    assert provider.providerId == EXAMPLE_PROVIDER_ID
    assert provider.providerName == "模版场景示例"
    assert len(provider.cases) == 8
    example = load_template_examples()[index]
    case = provider.cases[index]
    assert case.caseId == "template-example-" + example.id
    assert case.targetTemplateId == example.template_id
    assert case.prdVer == "11.7.5.206"
    payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
    request = gallery._request_from_envelope(payload)
    assert request.title == (example.card_title or example.title.split(" ", maxsplit=1)[-1])
    bindings = request.candidateDataBindings
    assert bindings is not None and len(bindings) == 1
    binding = bindings[0]
    assert binding.arguments == example.arguments
    assert binding.candidateOutputFields == example.fields
    events = request.candidateEventCandidates
    assert events is not None
    assert [event.capabilityId for event in events] == example.event_ids
    assert len(events) == gallery._expected_action_count(case.scenarioId)
    expected_samples = {}
    for path, value in example.samples.items():
        expected_samples[binding.writeResultTo + path] = value
    assert gallery._gallery_sample_overrides_from_envelope(payload) == expected_samples
    assert example.user_query in request.userQuery
    if example.asset_ids is not None:
        assert request.candidateAssetIds == example.asset_ids
    registered = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    for event in events:
        definition = registered.get(event.capabilityId)
        assert definition is not None
        action = definition.get("actionTemplate")
        assert isinstance(action, dict)
        assert event.action.call == action.get("call")
        assert event.action.args == action.get("args")


def test_examples_append_idempotently_without_changing_original_requests(tmp_path: Path) -> None:
    before = gallery.write_gallery_input_dataset(tmp_path)
    original = {}
    for provider in before.providers:
        for case in provider.cases:
            original[case.requestFile] = (tmp_path / case.requestFile).read_bytes()
    first = append_template_examples(tmp_path)
    second = append_template_examples(tmp_path)
    assert first == second
    assert second.providers[:-1] == before.providers
    for path, value in original.items():
        assert (tmp_path / path).read_bytes() == value


def test_example_dates_and_enabled_power_mode_are_consistent(tmp_path: Path) -> None:
    examples = load_template_examples()
    assert examples[1].card_title == "周五"
    assert examples[1].samples.get("/events/0/startDate") == "25"
    assert examples[6].template_id == "BatteryOverviewFull@1"
    assert examples[6].icon_action is True
    assert examples[7].template_id == "WeatherOverviewHero@1"
    assert examples[7].event_ids == ["event.open.weather"]
    assert "查看详情" in examples[7].context
    assert examples[7].samples.get("/current/condition") == "晴"
    assert examples[7].asset_ids == ["asset.sun_max"]
    assert date(2026, 9, 25).weekday() == 4
    assert (date(2026, 12, 13) - date(2026, 9, 9)).days == 95
    assert examples[5].samples.get("/countdownDays") == 95
    assert examples[7].arguments.get("prefectureName") == "深圳市"
    assert "不展示明日预报" in examples[7].context
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    power = events.get("event.setPowerSavingMode")
    assert power is not None
    action = power.get("actionTemplate")
    assert isinstance(action, dict)
    args = action.get("args")
    assert isinstance(args, dict)
    params = args.get("params")
    assert isinstance(params, dict)
    assert params.get("switchFlag") == 0


def test_example_full_icon_action_uses_matching_layout_and_registered_asset(tmp_path: Path) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    case = append_template_examples(tmp_path).providers[-1].cases[6]
    assert case.expectedLayout == "FullIconActionLayout"
    assert case.scenarioId == "single-icon-action"
    request = gallery._request_from_envelope(json.loads((tmp_path / case.requestFile).read_text()))
    assert "asset.battery_leaf_fill" in (request.candidateAssetIds or [])


@pytest.mark.parametrize("extra_fields", [(), ("airQuality",), ("coldLevel",),
                                         ("airQuality", "coldLevel")])
def test_weather_hero_retains_available_air_quality_and_cold_risk(
    extra_fields: tuple[str, ...],
) -> None:
    from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
    from services.template_generation.engine.cardplan.registry import get_cardplan_registry

    definition = get_cardplan_registry().require_template("WeatherOverviewHero@1")
    assert "/current/airQuality" in definition.optional_data
    bindings = {
        "temperature": "${data.weather.current.temperatureText}",
        "condition": "${data.weather.current.condition}",
    }
    for name in extra_fields:
        bindings[name] = "${data.weather.current." + name + "}"
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, bindings,
        {"primaryColor": "#FF000000", "supportContentColor": "#99000000"},
    )
    serialized = str(root)
    for name in ("airQuality", "coldLevel"):
        assert (name in serialized) == (name in extra_fields)


@pytest.mark.asyncio
async def test_example_runner_uses_public_service_and_keeps_all_eight_cases(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    gallery.write_gallery_input_dataset(inputs)
    append_template_examples(inputs)
    service = _GalleryService()
    summary = await gallery.ProviderGalleryBatchRunner(service).run(
        inputs, tmp_path / "output", provider_ids={EXAMPLE_PROVIDER_ID}
    )
    assert summary.total == 8
    assert summary.success == 8
    assert summary.failed == 0
    assert len(service.requests) == 8
    assert len(list((tmp_path / "output" / "providers").rglob("*.json"))) == 8


def test_example_unknown_event_fails_without_publishing_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(gallery, "_load_event_capabilities", lambda _root: {})
    with pytest.raises(ValueError, match="示例事件未注册"):
        append_template_examples(tmp_path)
    assert (tmp_path / "manifest.json").read_bytes() == original


def test_example_unknown_asset_fails_without_publishing_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(gallery, "_load_asset_capabilities", lambda _root: {})
    with pytest.raises(ValueError, match="示例素材未注册"):
        append_template_examples(tmp_path)
    assert (tmp_path / "manifest.json").read_bytes() == original


def test_sample_overrides_support_array_items_without_mutating_original() -> None:
    spec = TaskSpec(userQuery="演示", size="2x2", dataModelSchema={
        "data": {"calendar": {"events": [
            {"title": {"type": "string", "sampleValue": "原会议"}},
            {"title": {"type": "string", "sampleValue": "另一场会议"}},
        ]}},
    })
    original = spec.model_dump_json()
    changed = _with_trusted_sample_overrides(
        spec, {"/data/calendar/events/0/title": "UI需求评审会"}
    )
    assert spec.model_dump_json() == original
    serialized = changed.model_dump_json()
    assert "UI需求评审会" in serialized
    assert "另一场会议" in serialized
    assert "原会议" not in serialized


@pytest.mark.parametrize("path", [
    "/data/calendar/events/1/title", "/data/calendar/events/-1/title",
    "/data/calendar/events/01/title", "/data/calendar/events/0/unknown",
    "/data/calendar/events/0", "/outside/calendar/events/0/title",
])
def test_sample_override_rejects_invalid_array_paths(path: str) -> None:
    spec = TaskSpec(userQuery="演示", size="2x2", dataModelSchema={
        "data": {"calendar": {"events": [
            {"title": {"type": "string", "sampleValue": "原会议"}},
        ]}},
    })
    original = spec.model_dump_json()
    with pytest.raises(ValueError, match="trusted sample override"):
        _with_trusted_sample_overrides(spec, {path: "替换"})
    assert spec.model_dump_json() == original
