"""位图后处理仅移除位图染色，不改变 SVG、绑定、数据和异常语义。"""

import json
from types import SimpleNamespace

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan import preview_dataset
from services.template_generation.engine.cardplan.compiler import _normalize_template_asset_params
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)
from services.template_generation.postprocessing import remove_bitmap_fill_colors


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
