"""名称与左右耳电量 Hero 的离线检索、编译检查，不调用模型。

Hero 计划的模板选择与必需字段目录、以及蓝图直接编译出的完整 A2UI 消息，
已固化为场景金样（Layer C）：
- ``earbud__pair_hero_plan``：三字段 + 一动作解析出的模板 ID 与
  ``required_data`` 目录；
- ``earbud__pair_hero_compiled__without_icons`` /
  ``earbud__pair_hero_compiled__with_icons``：不带/带左右耳图标参数时
  ``convert_tersel_to_a2ui`` 的完整消息（数据路径、无 isConnected、百分比
  符号与合法字号都由快照整体冻结）。

引擎或模板改动后按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

import json
from typing import Any

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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

TEMPLATE = "BluetoothDeviceOverviewEarbudPairHero@1"
FIELDS = ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]

_TASK_SPEC = {
    "dataModelSchema": {"data": {"earphone": {
        "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
        "leftBatteryLevel": {"type": "integer", "sampleValue": 0},
        "rightBatteryLevel": {"type": "integer", "sampleValue": 100},
    }}},
}


def _hero_task() -> TaskSpec:
    return TaskSpec(
        userQuery="显示耳机名称和左右耳电量", size="2x2",
        eventCandidates=[EventAction(
            id="event.open.settings.bluetooth", call="clickToDeeplink",
            args={"intentName": "Settings", "uri": "bluetooth_entry"},
        )],
        dataModelSchema=_TASK_SPEC["dataModelSchema"],
    )


@scenario("earbud__pair_hero_plan")
def _build_pair_hero_plan() -> dict[str, Any]:
    task = _hero_task()
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
    assert plans
    template_id = plans[0].business_slots[0].template_id
    definition = registry.require_template(template_id)
    return {
        "templateId": template_id,
        "requiredData": sorted(definition.required_data),
    }


def _compile_pair_hero(with_icons: bool) -> dict[str, Any]:
    registry = get_cardplan_registry()
    definition = registry.require_template(TEMPLATE)
    bindings: dict[str, str] = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.earphone." + binding.path.removeprefix("/") + "}"
    params: dict[str, str] = {}
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
        task_spec=_TASK_SPEC,
    )
    return {
        "a2ui": [json.loads(line) for line in output.splitlines() if line.strip()],
    }


@scenario("earbud__pair_hero_compiled__without_icons")
def _build_pair_hero_compiled_without_icons() -> dict[str, Any]:
    return _compile_pair_hero(False)


@scenario("earbud__pair_hero_compiled__with_icons")
def _build_pair_hero_compiled_with_icons() -> dict[str, Any]:
    return _compile_pair_hero(True)


def test_earbud_pair_hero_offline_scenarios() -> None:
    assert_golden_scenario("earbud__pair_hero_plan")
    assert_golden_scenario("earbud__pair_hero_compiled__without_icons")
    assert_golden_scenario("earbud__pair_hero_compiled__with_icons")
