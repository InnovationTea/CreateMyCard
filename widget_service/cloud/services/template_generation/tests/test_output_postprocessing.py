"""模板后处理保护位图及禁染 SVG 的原色，不改变绑定、数据和异常语义。"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from config.config import get_settings
from models.generation import CandidateDataBinding
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan import preview_dataset
from services.template_generation.engine.cardplan.compiler import _normalize_template_asset_params
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.postprocessing import (
    remove_bitmap_fill_colors,
    remove_disallowed_image_fill_colors,
)

_ASSET_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "data/capabilities/app-11.7.7.300_rom-7.0/asset_capabilities.json"
)
_ASSETS = json.loads(_ASSET_REGISTRY.read_text(encoding="utf-8"))
_NATIVE_SVG_IDS = frozenset({
    "asset.icon_id", "asset.ic_charge", "asset.ic_weatherWarning", "asset.ic_uv_color",
    "asset.ic_warning_color", "asset.ic_hotspot", "asset.ic_call_bule", "asset.ic_call_yellow",
    "asset.ic_ring_bule", "asset.ic_ring_yellow", "asset.ic_sportsHealth_bule",
    "asset.ic_sportsHealth_yellow", "asset.ic_sun", "asset.ic_calender", "asset.ic_sun_monochrome",
})


@pytest.mark.parametrize("source", [
    "icons/a.png", "icons/A.PNG?version=2#icon", "icons/a.jpg", "icons/a.jpeg",
    "icons/a.webp", "icons/a.gif", "icons/a.bmp", "icons/A.WEBP?version=2#icon",
])
def test_bitmap_colors_removed_from_flat_and_nested_nodes(source: str) -> None:
    bitmap = {
        "component": "Image", "src": source, "fillColor": "#123456",
        "styles": {"fillColor": "#123456", "width": 20},
    }
    messages = [
        {"updateComponents": {"components": [
            bitmap, {"component": "Column", "children": [bitmap]},
        ]}},
        {"updateDataModel": {"value": bitmap}},
    ]
    raw = "\n".join(json.dumps(message) for message in messages)
    output = remove_bitmap_fill_colors(raw)
    actual = [json.loads(line) for line in output.splitlines()]
    expected_bitmap = {"component": "Image", "src": source, "styles": {"width": 20}}
    assert actual == [
        {"updateComponents": {"components": [
            expected_bitmap, {"component": "Column", "children": [expected_bitmap]},
        ]}},
        {"updateDataModel": {"value": bitmap}},
    ]
    assert remove_bitmap_fill_colors(output) == output


@pytest.mark.parametrize("source", ["icons/a.svg", "{{ /data/icon }}", {"path": "/data/icon"}])
def test_non_bitmap_output_is_unchanged(source: object) -> None:
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": source, "styles": {"fillColor": "#123456"},
    }]}})
    assert remove_bitmap_fill_colors(raw) == raw


def test_invalid_json_still_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        remove_bitmap_fill_colors("{")
    with pytest.raises(json.JSONDecodeError):
        remove_disallowed_image_fill_colors("{", _ASSETS)


@pytest.mark.parametrize("asset", _ASSETS, ids=lambda asset: asset.get("id"))
def test_registered_asset_color_contract_and_nested_nodes(asset: dict) -> None:
    source = asset.get("src")
    assert isinstance(source, str)
    native = asset.get("id") in _NATIVE_SVG_IDS or not source.endswith(".svg")
    icon = {
        "component": "Image", "src": source, "fillColor": "#FFFF0000",
        "styles": {"fillColor": {"path": "/data/color"}, "width": 20},
        "onClick": [{"call": "open"}],
    }
    other = {"component": "Text", "src": source, "styles": {"fillColor": "#FFFF0000"}}
    messages = [
        {"updateComponents": {"components": [
            icon, {"component": "Column", "children": [icon, other]},
        ]}},
        {"updateDataModel": {"value": icon}},
    ]
    raw = "\n".join(json.dumps(message) for message in messages)
    output = remove_disallowed_image_fill_colors(raw, [asset])
    expected_icon = icon
    if native:
        expected_icon = {
            "component": "Image", "src": source, "styles": {"width": 20},
            "onClick": [{"call": "open"}],
        }
    else:
        assert output == raw
    assert [json.loads(line) for line in output.splitlines()] == [
        {"updateComponents": {"components": [
            expected_icon, {"component": "Column", "children": [expected_icon, other]},
        ]}},
        {"updateDataModel": {"value": icon}},
    ]
    assert remove_disallowed_image_fill_colors(output, [asset]) == output


@pytest.mark.parametrize("description", [
    "保留原色与透明度", "禁止染色", "不可染色", "禁止fillColor", "禁止使用 fillColor",
    "不可使用fillColor属性", "不允许 fillColor", "不允许使用 FILLCOLOR",
])
def test_explicit_native_color_descriptions(description: str) -> None:
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": "icon.svg", "fillColor": "#FF123456",
    }]}})
    result = remove_disallowed_image_fill_colors(raw, [{
        "src": "icon.svg", "description": description,
    }])
    assert "fillColor" not in result


@pytest.mark.parametrize("source", [
    "unknown.svg", "another/path/icon.svg", "{{ /data/icon }}", {"path": "/data/icon"},
])
def test_native_color_cleanup_does_not_guess_sources(source: object) -> None:
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": source, "styles": {"fillColor": "#FF123456"},
    }]}})
    assert remove_disallowed_image_fill_colors(raw, [{
        "src": "icon.svg", "description": "保留原色，禁止染色",
    }]) == raw


@pytest.mark.parametrize("description", [None, "", "支持 fillColor", "彩色渐变品牌图标"])
def test_cleanup_requires_explicit_native_color_constraint(description: object) -> None:
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": "icon.svg", "styles": {"fillColor": "#FF123456"},
    }]}})
    assert remove_disallowed_image_fill_colors(raw, [{
        "src": "icon.svg", "description": description,
    }]) == raw


def test_native_color_cleanup_logs_counts_without_trace(monkeypatch) -> None:
    from services.template_generation import postprocessing

    logs: list[str] = []
    monkeypatch.setattr(postprocessing.logger, "info", logs.append)
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": "icon.svg", "fillColor": None,
        "styles": {"fillColor": "#FF123456"},
    }]}})
    output = remove_disallowed_image_fill_colors(raw, [{
        "src": "icon.svg", "description": "禁止染色",
    }])
    assert "fillColor" not in output
    assert len(logs) == 1
    assert "native_source_count=1 changed_image_count=1 removed_property_count=2" in logs[0]
    assert "icon.svg" not in logs[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_id", ["asset.ic_sun_monochrome", "asset.drop_1"])
async def test_second_layer_native_color_cleanup_survives_public_conversion(monkeypatch, asset_id):
    from services.template_generation.tests.test_template_generation import (
        WeatherTemplateModel,
        _weather_card_spec,
        _weather_task_spec,
    )

    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    asset = next(item for item in _ASSETS if item.get("id") == asset_id)
    source = asset.get("src")
    assert isinstance(source, str)
    task = _weather_task_spec().model_copy(update={"assetCandidates": [asset]})
    if asset_id in _NATIVE_SVG_IDS:
        condition = task.dataModelSchema.get("data", {}).get("weather", {}).get("current", {}).get(
            "condition",
        )
        assert isinstance(condition, dict)
        condition["sampleValue"] = "晴天"
    model = WeatherTemplateModel(body=(
        'Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",'
        + json.dumps({"conditionIcon": source}) + '));'
    ))
    binding = CandidateDataBinding(
        capabilityId="ViewWeather", writeResultTo="/data/weather",
        candidateOutputFields=["/current/temperatureText", "/current/condition"],
    )
    output = await generate_template_a2ui(task, _weather_card_spec(), (binding,), model)
    assert model.body_called
    compact = convert_a2ui_to_compact_dsl(output.a2ui, size=task.size)
    standard = convert_compact_dsl_to_a2ui(
        compact, size=task.size, skip_compact_dsl_validation=True,
    )
    for document in (output.a2ui, standard):
        images = []
        for line in document.splitlines():
            for node in json.loads(line).get("updateComponents", {}).get("components", []):
                if node.get("component") == "Image" and node.get("src") == source:
                    images.append(node)
        assert images
        for image in images:
            if asset_id in _NATIVE_SVG_IDS:
                assert "fillColor" not in image
                assert "fillColor" not in image.get("styles", {})
            else:
                assert image.get("styles", {}).get("fillColor")


@pytest.mark.parametrize("suffix", ["png", "jpg", "jpeg", "webp", "gif", "bmp"])
def test_wide_earphone_bitmap_survives_real_template_and_public_conversion(monkeypatch, suffix):
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    definition = registry.require_template("BluetoothDeviceOverviewEarbudsPhoneWideFull@1")
    parameters = preview_dataset._template_parameters(definition)
    bitmap_source = f"resources/base/media/user-left-ear.{suffix}"
    parameters["leftEarIcon"] = bitmap_source
    tags = {}
    for name, semantic_tags in definition.asset_parameter_semantic_tags.items():
        source = parameters.get(name)
        if isinstance(source, str):
            tags[source] = semantic_tags
    contract = SimpleNamespace(
        allowed_asset_sources=tuple(tags), asset_semantic_tags_by_source=tags,
    )
    normalized = _normalize_template_asset_params(
        parameters, definition.asset_parameter_semantic_tags, contract,
        required_parameters=frozenset(definition.variants[0].parameters_schema.get("required", [])),
    )
    assert normalized.get("leftEarIcon") == bitmap_source
    monkeypatch.setattr(preview_dataset, "_template_parameters", lambda _definition: normalized)
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    case = preview_dataset._build_case("bitmap", definition, profile, registry)
    a2ui = "\n".join(json.dumps(message) for message in case.messages)
    compact = convert_a2ui_to_compact_dsl(remove_bitmap_fill_colors(a2ui), size=case.size)
    standard = convert_compact_dsl_to_a2ui(
        compact, size=case.size, skip_compact_dsl_validation=True,
    )
    images = []
    for line in standard.splitlines():
        for component in json.loads(line).get("updateComponents", {}).get("components", []):
            if component.get("component") == "Image" and component.get("src") == bitmap_source:
                images.append(component)
    assert images
    for image in images:
        assert "fillColor" not in image
        assert "fillColor" not in image.get("styles", {})
