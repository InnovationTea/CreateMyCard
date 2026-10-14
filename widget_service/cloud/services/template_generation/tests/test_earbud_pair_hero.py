"""名称与左右耳电量 Hero 的离线检索、编译检查，不调用模型。"""

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    _compile_ux_layout_shell,
    _instantiate_blueprint,
    _serialize_node,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui

TEMPLATE = "BluetoothDeviceOverviewEarbudPairHero@1"
FIELDS = ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]


def test_three_fields_and_one_action_produce_hero_plan() -> None:
    task = TaskSpec(
        userQuery="显示耳机名称和左右耳电量", size="2x2",
        dataModelSchema={"data": {"earphone": {
            "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
            "leftBatteryLevel": {"type": "integer", "sampleValue": 0},
            "rightBatteryLevel": {"type": "integer", "sampleValue": 100},
        }}},
        eventCandidates=[EventAction(
            id="event.open.settings.bluetooth", call="clickToDeeplink",
            args={"intentName": "Settings", "uri": "bluetooth_entry"},
        )],
    )
    bindings = (CandidateDataBinding(
        capabilityId="GetEarphoneInfo", writeResultTo="/data/earphone",
        candidateOutputFields=FIELDS,
    ),)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": FIELDS},
        action=["event.open.settings.bluetooth"],
    )
    registry = get_cardplan_registry()
    card = {"suggestSize": "2x2", "dataBindings": [{
        "capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone",
    }]}
    search = search_template_variants(intent, task, registry, bindings, card)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans[0].business_slots[0].template_id == TEMPLATE
    definition = registry.require_template(TEMPLATE)
    assert set(definition.required_data) == set(FIELDS)


@pytest.mark.parametrize("with_icons", [False, True])
def test_hero_compiles_with_both_battery_bindings_and_valid_font_sizes(with_icons: bool) -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template(TEMPLATE)
    bindings: dict[str, str] = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.earphone." + binding.path.removeprefix("/") + "}"
    params = {}
    if with_icons:
        params = {"leftEarIcon": "resources/base/media/icon_left.svg",
                  "rightEarIcon": "resources/base/media/icon_right.svg"}
    content = _instantiate_blueprint(
        definition.variants[0].root, params, bindings,
        registry.theme_reference_values("family-weather-care-blue"),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id="family-weather-care-blue")
    root = _strip_advanced_component_markers(_compile_ux_layout_shell(content, contract, registry))
    output = convert_tersel_to_a2ui(
        _serialize_node(root) + ";", size="2x2",
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        task_spec={"dataModelSchema": {"data": {"earphone": {
            "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
            "leftBatteryLevel": {"type": "integer", "sampleValue": 0},
            "rightBatteryLevel": {"type": "integer", "sampleValue": 100},
        }}}},
    )
    assert "/data/earphone/leftBatteryLevel" in output
    assert "/data/earphone/rightBatteryLevel" in output
    assert "/data/earphone/earphoneName" in output
    assert "isConnected" not in output
    assert "%" in output
