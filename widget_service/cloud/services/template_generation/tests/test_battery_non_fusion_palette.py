"""手机电量非融球配色与耳机一致，同时隔离内存、融球和双业务主题。"""

import json

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.cardplan.compiler import _provider_layout_action_background
from services.template_generation.engine.cardplan.models import (
    HybridBodyContract,
    TemplateLayoutActionStyle,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_template_generation import (
    _battery_card_spec,
    _battery_task,
    _FixedTemplateModel,
)


def test_battery_green_palette_matches_earphone_without_changing_layout() -> None:
    registry = get_cardplan_registry(False)
    battery = registry.require_theme("battery-device-green")
    earphone = registry.require_theme("audio-product-neutral-violet")
    memory = registry.require_theme("device-clean-blue-teal")

    assert battery.reference_values == earphone.reference_values
    assert battery.root_style.get("backgroundColor") == earphone.root_style.get("backgroundColor")
    assert "linearGradient" not in battery.root_style
    assert battery.supported_capability_ids == ("GetPhoneBatteryInfo",)
    assert memory.supported_capability_ids == ("GetSystemMemInfo",)
    for key in ("padding", "borderRadius", "justifyContent", "alignItems", "clip"):
        assert battery.root_style.get(key) == memory.root_style.get(key)


def test_battery_green_theme_does_not_change_other_routes() -> None:
    registry = get_cardplan_registry(False)
    assert registry.first_layer_theme_ids(("BatteryOverview",)) == ("battery-device-green",)
    assert registry.first_layer_theme_ids(("BluetoothDeviceOverview",)) == (
        "audio-product-neutral-violet",
    )
    assert registry.first_layer_theme_ids(("ResourceUsageOverview",)) == (
        "device-clean-blue-teal",
    )
    assert registry.require_layout_theme(
        "TwoSupportLayout", ("GetPhoneBatteryInfo", "ViewWeather"),
    ) == "2x2-two-support"
    fusion_registry = get_cardplan_registry(True)
    assert fusion_registry.first_layer_theme_ids(("BatteryOverview",)) == ("fusion-battery-teal",)


def test_only_battery_green_disables_template_action_background_override() -> None:
    registry = get_cardplan_registry(True)
    for theme_id in ("battery-device-green", "fusion-battery-teal"):
        theme = registry.require_theme(theme_id)
        contract = HybridBodyContract.model_construct(
            theme_profile_id=theme_id,
            allowed_template_ids=("BatteryOverviewChargingRingHero@1",),
            allowed_business_component_ids=("BatteryOverview",),
        )
        background = _provider_layout_action_background(
            contract, registry, foreground=theme.action_style.content_color,
            default=theme.action_style.background_color,
        )
        if theme_id == "battery-device-green":
            assert theme.allow_template_action_background_override is False
            assert background == theme.action_style.background_color
        else:
            assert theme.allow_template_action_background_override is True
            assert background == "#33CCFFF6"


@pytest.mark.asyncio
async def test_battery_green_keeps_fusion_a2ui_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template_id = "BatteryOverviewChargingRingHero@1"
    registry = get_cardplan_registry(True)
    fields = ("/batterySOC", "/chargingStatusDesc")
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal", component_id="BatteryOverview",
        available_template_ids=(template_id,), capability_id="GetPhoneBatteryInfo",
        required_fields=fields, action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewChargingRingHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"省电模式"}));'
        ),
    )
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/phoneBattery",
        candidateOutputFields=list(fields),
    )
    task = _battery_task().model_copy(update={"appVersion": "11.7.5.206"})
    current = await generate_template_a2ui(
        task, _battery_card_spec(), (binding,), model,
        enable_fusion_ball=True, trusted_template_candidate_ids=(template_id,),
    )
    previous_definition = registry.require_template(template_id).model_copy(update={
        "layout_action_style": TemplateLayoutActionStyle(backgroundOpacity=0.2),
    })
    monkeypatch.setitem(registry.templates, template_id, previous_definition)
    previous = await generate_template_a2ui(
        task, _battery_card_spec(), (binding,), model,
        enable_fusion_ball=True, trusted_template_candidate_ids=(template_id,),
    )
    assert "fusionBallBackground" in current.a2ui
    assert current.a2ui == previous.a2ui


@pytest.mark.asyncio
@pytest.mark.parametrize(("template_id", "layout_id", "action_template"), [
    ("BatteryOverviewFull@1", "SingleFocusLayout@1", None),
    ("BatteryOverviewFull@1", "FullIconActionLayout@1", "IconAction@1"),
    ("BatteryOverviewChargingRingHero@1", "HeroActionLayout@1", "PillAction@1"),
])
async def test_battery_compiles_green_full_and_hero(
    template_id: str, layout_id: str, action_template: str | None,
) -> None:
    fields = ("/batterySOC", "/batterySOCText", "/batteryCapacityLevelDesc", "/chargingStatusDesc")
    action_id = "event.setPowerSavingMode" if action_template is not None else None
    body = f'Template("{layout_id}",{{}},Template("{template_id}",{{}})'
    if action_template is not None:
        props = {"actionId": action_id}
        if action_template == "IconAction@1":
            props["icon"] = "resources/base/media/battery_leaf_fill.svg"
        else:
            props["label"] = "省电模式"
        body += f',Template("{action_template}",{json.dumps(props, ensure_ascii=False)})'
    body += ");"
    model = _FixedTemplateModel(
        theme_id="battery-device-green", component_id="BatteryOverview",
        available_template_ids=(template_id,), capability_id="GetPhoneBatteryInfo",
        required_fields=fields, action_id=action_id, body=body,
    )
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/phoneBattery",
        candidateOutputFields=list(fields),
    )
    output = await generate_template_a2ui(
        _battery_task(), _battery_card_spec(), (binding,), model,
        enable_fusion_ball=False, trusted_template_candidate_ids=(template_id,),
    )
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    root = next(component for component in components if component.get("id") == "root")
    styles = root.get("styles")
    assert isinstance(styles, dict)
    assert styles.get("backgroundColor") == "#FFF0FFE6"
    assert "linearGradient" not in styles
    assert "fusionBall" not in output.a2ui
    marked_ids = []
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        if component_id.startswith("__genui_render_component__"):
            marked_ids.append(component_id)
        if component_id == "template_root":
            assert component.get("children") == ["__genui_render_component__root_1"]
    assert marked_ids == ["__genui_render_component__root_1"]
    assert "#FFF9A01E" not in output.a2ui
    assert "0A59F7" not in output.a2ui
    for component in components:
        component_styles = component.get("styles", {})
        if component.get("component") == "Progress":
            assert component_styles.get("color") == "#FF52991F"
            assert component_styles.get("backgroundColor") == "#3364BB5C"
        if component.get("onClick"):
            assert component_styles.get("backgroundColor") == "#3364BB5C"
