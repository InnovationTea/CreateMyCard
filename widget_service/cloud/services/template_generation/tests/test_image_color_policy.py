"""Image 显式着色、原色保护及真实双业务编译回归。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import (
    _apply_theme_content_color,
    _expand_weather_overview_call,
    _lower_action_template_tree,
    _strip_advanced_component_markers,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, SourceSpan
from services.template_generation.engine.cardplan.parser import ParsedCall
from services.template_generation.engine.cardplan.preview_dataset import _build_data_schema
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchCandidate,
    TemplateSearchIntent,
    TemplateSearchResult,
)
from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

_EXPLICIT = "#FF123456"
_ROOT = Path(__file__).resolve().parents[1]
_ASSETS = _ROOT.parents[1] / "data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json"


def _template_source(options: str) -> str:
    return (
        '#Template ImagePolicy@1(props: {})\ndata = {}\n'
        'Column(Image("resources/base/media/icon_weather_thermometer.svg", {'
        + options + '}))\n#End\n'
    )


@pytest.mark.parametrize("color", ('"#FF123456"', "$theme('supportContentColor')"))
@pytest.mark.parametrize("inherited", (False, True))
def test_template_rejects_original_color_and_explicit_fill(color: str, inherited: bool) -> None:
    source = _template_source('"_preserveOriginalColor": true, "fillColor": ' + color)
    if inherited:
        source = _template_source('"fillColor": ' + color).replace(
            "Column(", 'Column({"_preserveOriginalColor": true},',
        )
    with pytest.raises(ValueError, match="_preserveOriginalColor.*fillColor"):
        compile_card_template(
            source, provider_id="example.image", business_id=None,
            expected_wire_id="ImagePolicy@1", expected_capability_id=None,
            data_domain=None, description="Image 着色冲突", supported_card_sizes=("2x2",),
            primary_data=(), secondary_data=(), optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


@pytest.mark.parametrize(("options", "expected"), (
    ({"_preserveOriginalColor": True}, None),
    ({"fillColor": _EXPLICIT}, _EXPLICIT),
    ({"_preserveOriginalColor": False, "fillColor": _EXPLICIT}, _EXPLICIT),
    ({}, "#E61F4595"),
))
def test_image_uses_only_declared_color_policy(
    options: dict[str, Any], expected: str | None,
) -> None:
    node = Nested2Node("Image", ("resources/base/media/icon_weather1.svg", options), ())
    contract = HybridBodyContract.model_construct(theme_profile_id="2x2-two-support")
    styled = _apply_theme_content_color(node, contract, get_cardplan_registry())
    cleaned = _strip_advanced_component_markers(styled)
    final_options = cleaned.values[-1]
    assert isinstance(final_options, dict)
    assert final_options.get("fillColor") == expected
    assert "_preserveOriginalColor" not in final_options
    assert node.values[-1] == options


@pytest.mark.parametrize("inherited", (False, True))
def test_runtime_rejects_conflicting_image_color_even_in_action(inherited: bool) -> None:
    image_options: dict[str, Any] = {"fillColor": _EXPLICIT}
    parent_options: dict[str, Any] = {"_boundTemplateAction": "event.open"}
    if inherited:
        parent_options["_preserveOriginalColor"] = True
    else:
        image_options["_preserveOriginalColor"] = True
    root = Nested2Node("Row", (parent_options,), (
        Nested2Node("Image", ("resources/base/media/icon_phone.svg", image_options), ()),
    ))
    contract = HybridBodyContract.model_construct(theme_profile_id="2x2-two-support")
    with pytest.raises(TerselConversionError, match="_preserveOriginalColor.*fillColor"):
        _apply_theme_content_color(root, contract, get_cardplan_registry())


@pytest.mark.parametrize(("options", "expected"), (
    ({"_preserveOriginalColor": True}, None),
    ({"fillColor": _EXPLICIT}, _EXPLICIT),
    ({}, "#FFABCDEF"),
))
def test_action_image_respects_original_and_explicit_color(
    options: dict[str, Any], expected: str | None,
) -> None:
    image = Nested2Node("Image", ("resources/base/media/icon_phone.svg", options), ())
    root = Nested2Node("Action", (), (
        Nested2Node("Stack", ({"onClick": [{"call": "open"}]},), (image,)),
    ))
    styled = _lower_action_template_tree(root, background="#FFFFFFFF", foreground="#FFABCDEF")
    final_options = styled.children[0].values[-1]
    assert isinstance(final_options, dict)
    assert final_options.get("fillColor") == expected


@pytest.mark.parametrize("conflict", (False, True))
def test_action_image_inherits_original_color_protection(conflict: bool) -> None:
    options = {"fillColor": _EXPLICIT} if conflict else {}
    image = Nested2Node("Image", ("resources/base/media/icon_phone.svg", options), ())
    action_options = {"onClick": [{"call": "open"}], "_preserveOriginalColor": True}
    root = Nested2Node("Action", (), (Nested2Node("Stack", (action_options,), (image,)),))
    if conflict:
        with pytest.raises(TerselConversionError, match="_preserveOriginalColor.*fillColor"):
            _lower_action_template_tree(root, background="#FFFFFFFF", foreground="#FFABCDEF")
    else:
        styled = _lower_action_template_tree(
            root, background="#FFFFFFFF", foreground="#FFABCDEF",
        )
        final_options = styled.children[0].values[-1]
        assert isinstance(final_options, dict)
        assert "fillColor" not in final_options


@pytest.mark.parametrize(("filename", "tags"), (
    ("icon_weather_thermometer.svg", ("temperature",)),
    ("sun_max.svg", ("sun", "sunny")),
    ("rain.svg", ("cloud", "rain")),
))
def test_legacy_weather_entry_does_not_infer_image_color(
    filename: str, tags: tuple[str, ...],
) -> None:
    registry = get_cardplan_registry()
    source = "resources/base/media/" + filename
    contract = HybridBodyContract.model_construct(
        theme_profile_id="2x2-two-support",
        allowed_business_component_ids=("WeatherOverview",),
        asset_semantic_tags_by_source={source: tags},
    )
    samples = {
        "city": "深圳", "temperature": "29°C", "condition": "多云",
        "airQuality": "良", "coldLevel": "低", "temperatureRange": "25° / 32°",
    }
    schema = {key: {"type": "string", "sampleValue": value} for key, value in samples.items()}
    task = TaskSpec(userQuery="天气", size="2x2", dataModelSchema=schema)
    call = ParsedCall(
        kind="component", name="WeatherOverview",
        values=({"role": "support", "conditionIcon": source},), children=(),
        span=SourceSpan(start=0, end=1),
    )
    root = _expand_weather_overview_call(
        call, task_spec=task, contract=contract, registry=registry, layout_id=None,
    )
    styled = _apply_theme_content_color(root, contract, registry)
    pending = [styled]
    images: list[Nested2Node] = []
    while pending:
        node = pending.pop()
        if node.component_type == "Image":
            images.append(node)
        pending.extend(node.children)
    assert len(images) == 1
    options = images[0].values[-1]
    assert isinstance(options, dict)
    assert options.get("fillColor") == "#E61F4595"
    assert "_preserveOriginalColor" not in options


@pytest.mark.parametrize("filename", (
    "icon_weather_thermometer.svg", "icon_weather_thermometer_medium.svg",
    "sun_max.svg", "icon_weather_wind.svg",
))
def test_two_support_final_a2ui_preserves_weather_template_fill(filename: str) -> None:
    registry = get_cardplan_registry()
    catalog = json.loads(_ASSETS.read_text(encoding="utf-8"))
    source = "resources/base/media/" + filename
    asset = next(item for item in catalog if item.get("src") == source)
    data: dict[str, Any] = {}
    bindings: list[dict[str, str]] = []
    groups: list[TemplateBusinessCandidates] = []
    required: dict[str, tuple[str, ...]] = {}
    for template_id in ("BatteryOverviewSupport@1", "WeatherOverviewTemperatureSupport@1"):
        definition = registry.require_template(template_id)
        sample = _build_data_schema(definition).get("data")
        assert isinstance(sample, dict)
        data.update(sample)
        capability_id = definition.capability_id
        business_id = definition.business_id
        domain = definition.data_domain
        assert capability_id is not None
        assert business_id is not None
        assert domain is not None
        bindings.append({"capabilityId": capability_id, "writeResultTo": domain})
        required[capability_id] = definition.required_data
        groups.append(TemplateBusinessCandidates(
            capabilityId=capability_id, businessId=business_id,
            explicitFields=definition.required_data,
            candidates=(TemplateSearchCandidate(
                templateId=template_id, coveredExplicitFields=definition.required_data,
            ),),
        ))
    data["weather"]["location"]["cityCode"] = {"type": "string", "sampleValue": "021"}
    task = TaskSpec(
        userQuery="展示手机电量与天气", size="2x2", dataModelSchema={"data": data},
        assetCandidates=[asset],
        eventCandidates=[EventAction(
            id="event.open.weather", call="clickToDeeplink",
            args={"uri": (
                "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                "+ ${/data/weather/location/cityCode} }}"
            )},
        )],
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability=required,
        action_ids=("event.open.weather",),
    )
    search = TemplateSearchResult(cardSize="2x2", businessCandidates=tuple(groups))
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    card_spec = {
        "title": "电量与天气", "description": "Image 着色回归",
        "suggestSize": "2x2", "dataBindings": bindings,
    }
    projection = build_ux_mixed_prompt(
        task_spec=task, card_spec=card_spec, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )
    children: list[str] = []
    for slot in plans[0].business_slots:
        params = (
            {"conditionIcon": source, "actionId": "event.open.weather"}
            if slot.business_id == "WeatherOverview" else {}
        )
        children.append(f'Template("{slot.template_id}",{json.dumps(params)})')
    composition = 'Template("TwoSupportLayout@1",{},' + ",".join(children) + ");"
    result = compile_ux_layout_card(
        composition, task_spec=task, contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry, card_spec=card_spec, enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in result.a2ui.splitlines() if line.strip()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    images = [node for node in components if node.get("component") == "Image"]
    assert len(images) == 1
    image = images[0]
    assert image.get("src") == source
    styles = image.get("styles")
    assert isinstance(styles, dict)
    assert styles.get("fillColor") == "#991F4595"
    assert styles.get("width") == styles.get("height") == 24
    assert "_preserveOriginalColor" not in result.effective_output
    assert "_preserveOriginalColor" not in result.a2ui
