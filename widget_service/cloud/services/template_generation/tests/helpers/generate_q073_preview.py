"""从 Q073 输入经正式检索、规划、编译生成本地预览，不调用模型。"""

import json
from pathlib import Path

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    _preview_theme,
    _template_parameters,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalQuery,
    retrieve_template_variants,
)
from services.template_generation.engine.cardplan.wide_full_planner import plan_embedded_wide_full

TEMPLATE_ID = "BluetoothDeviceOverviewEarbudsChargingWideFull@1"


def generate(source: Path, output: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    content = payload.get("content", payload)
    registry = CardPlanRegistry()
    definition = registry.require_template(TEMPLATE_ID)
    events = content.get("candidateEventCandidates", [])
    event = next(item for item in events if item.get("capabilityId") == "event.open.music.daily")
    action = event.get("action")
    assert isinstance(action, dict)
    asset_file = (
        Path(__file__).resolve().parents[4]
        / "data/capabilities/app-11.7.7.300_rom-7.0/asset_capabilities.json"
    )
    catalog = json.loads(asset_file.read_text(encoding="utf-8"))
    assets = [item for item in catalog if item.get("id") in content.get("candidateAssetIds", [])]
    task = TaskSpec(
        userQuery=content.get("userQuery"),
        size=content.get("size"),
        dataModelSchema=_build_data_schema(definition),
        eventCandidates=[EventAction(id="event.open.music.daily", **action)],
        assetCandidates=assets,
    )
    theme = _preview_theme(definition, registry)
    bindings = tuple(
        CandidateDataBinding.model_validate(item)
        for item in content.get("candidateDataBindings", [])
    )
    card_spec = {"suggestSize": "2x4", "dataBindings": [item.model_dump() for item in bindings]}
    query = TemplateRetrievalQuery(
        themeId=theme.theme_profile_id,
        requiredOutputFieldsByCapability={
            "GetEarphoneInfo": tuple(bindings[0].candidateOutputFields),
        },
        action=["event.open.music.daily"],
    )
    selection = retrieve_template_variants(query, task, registry, bindings, card_spec)
    plans = plan_embedded_wide_full(query, selection, task, registry)
    assert plans and plans[0].business_slots[0].template_id == TEMPLATE_ID
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card_spec,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    parameters = _template_parameters(definition)
    parameters.update(
        {
            "leftEarIcon": "resources/base/media/icon_left.svg",
            "rightEarIcon": "resources/base/media/icon_right.svg",
        }
    )
    parameters["actionId"] = plans[0].action_assignments[0].action_id
    program = (
        'Template("WideFullOnlyLayout@1",{},'
        f'Template("{TEMPLATE_ID}",{json.dumps(parameters, ensure_ascii=False)}));'
    )
    protocol = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    result = compile_ux_layout_card(
        program,
        task_spec=task,
        card_spec=card_spec,
        contract=projection.contract,
        protocol_profile=protocol,
        registry=registry,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in result.a2ui.splitlines() if line.strip()]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(messages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Q073 matched; WideFullOnlyLayout + embedded favorite action compiled")
