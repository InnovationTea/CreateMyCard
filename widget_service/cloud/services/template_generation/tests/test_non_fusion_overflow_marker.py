"""非融球固定布局的防溢出标识、安全边距和双业务编译回归。"""

import json
from copy import deepcopy
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import _serialize_node
from services.template_generation.engine.cardplan.fusion_ball_background import (
    apply_content_safe_inset,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.tersel_converter import Nested2Node, convert_tersel_to_a2ui
from services.template_generation.tests.test_template_generation import (
    _FixedTemplateModel,
    _provider_field,
)

_SKELETON_ID = "__genui_render_component__root_1"


@pytest.mark.parametrize("component_type", ["Column", "Row", "Stack"])
@pytest.mark.parametrize("padding", [None, 12, {"left": 8, "right": 8, "top": 12, "bottom": 12}])
def test_non_fusion_marks_actual_skeleton_and_preserves_geometry(
    component_type: str, padding: int | dict[str, int] | None,
) -> None:
    skeleton_options = {
        "_id": "template_root",
        "width": "matchParent",
        "height": "matchParent",
        "clip": True,
        "padding": 4,
    }
    content = Nested2Node("Text", ("示例", {"_id": "business_title", "fontSize": 14}), ())
    nested = Nested2Node("Column", (), (Nested2Node("Text", ("辅助",), ()),))
    skeleton = Nested2Node(component_type, (skeleton_options,), (content, nested))
    root_options = {
        "_id": "root",
        "backgroundColor": "#FFF0FFE6",
        "linearGradient": {"colors": [["#FFF0FFE6", 0], ["#FFFFFFFF", 1]]},
        "borderRadius": 20,
        "clip": True,
    }
    if padding is not None:
        root_options["padding"] = padding
    column_options = {
        **root_options, "itemMargin": 4, "alignItems": "start", "justifyContent": "spaceBetween",
    }
    original = Nested2Node("Column", ("card", column_options), (skeleton,))
    snapshot = deepcopy(original)

    wrapped = apply_content_safe_inset(original, size="2x2")

    assert original == snapshot
    assert wrapped.component_type == "Stack"
    assert wrapped.values == ("card", {
        **root_options, "padding": 0, "alignContent": "topStart",
    })
    assert len(wrapped.children) == 1
    foreground = wrapped.children[0]
    assert foreground.component_type == "Stack"
    assert foreground.values == ("overlay", {
        "_id": "template_root", "padding": 12 if padding is None else padding,
    })
    assert len(foreground.children) == 1
    marked = foreground.children[0]
    assert marked.component_type == component_type
    assert marked.values == ({**skeleton_options, "_id": _SKELETON_ID},)
    assert marked.children == skeleton.children
    assert "__genui_render_component__template_root" not in str(wrapped)
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(wrapped) + ";", size="2x2",
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    ids = [component.get("id") for component in components]
    assert ids == [
        "root", "template_root", _SKELETON_ID, "business_title", "root_1_1", "root_1_1_0",
    ]
    marked_component = components[2]
    assert marked_component.get("children") == ["business_title", "root_1_1"]
    nested_component = components[4]
    assert nested_component.get("children") == ["root_1_1_0"]


@pytest.mark.parametrize("children", [(), (Nested2Node("Text", ("正文",), ()),), (
    Nested2Node("Text", ("标题",), ()), Nested2Node("Column", (), ()),
)])
def test_legacy_shell_without_single_layout_skeleton_is_unchanged(
    children: tuple[Nested2Node, ...],
) -> None:
    card = Nested2Node("Column", ("card", {"_id": "root", "padding": 12}), children)
    assert apply_content_safe_inset(card, size="2x2") is card


def test_non_2x2_layout_is_unchanged() -> None:
    card = Nested2Node("Column", ("card", {"_id": "root"}), (
        Nested2Node("Column", ({"_id": "template_root"},), ()),
    ))
    assert apply_content_safe_inset(card, size="2x4") is card


@pytest.mark.asyncio
async def test_two_support_compilation_marks_one_shared_skeleton() -> None:
    templates = ("BatteryOverviewSupport@1", "ActivityOverviewSupport@1")
    task = TaskSpec(
        userQuery="显示手机电量、充电状态和今天步数",
        size="2x2",
        dataModelSchema={"data": {
            "healthSport": {"dailySteps": _provider_field(6200, "integer")},
            "phoneBattery": {
                "batterySOC": _provider_field(82, "integer"),
                "chargingStatusDesc": _provider_field("充电中", "string"),
            },
        }},
    )
    activity_binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary", writeResultTo="/data/healthSport",
        candidateOutputFields=["/dailySteps"],
    )
    battery_binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/phoneBattery",
        candidateOutputFields=["/batterySOC", "/chargingStatusDesc"],
    )
    card_spec = {
        "title": "电量和活动", "description": "电量和步数", "suggestSize": "2x2",
        "dataBindings": [{
            "capabilityId": "GetHealthAndSportSummary", "writeResultTo": "/data/healthSport",
        }, {
            "capabilityId": "GetPhoneBatteryInfo", "writeResultTo": "/data/phoneBattery",
        }],
    }

    class TwoSupportModel(_FixedTemplateModel):
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "requiredOutputFieldsByCapability": {
                    "GetHealthAndSportSummary": ["/dailySteps"],
                    "GetPhoneBatteryInfo": ["/batterySOC", "/chargingStatusDesc"],
                },
                "action": [],
            }

    model = TwoSupportModel(
        theme_id="2x2-two-support", component_id="BatteryOverview",
        available_template_ids=templates, capability_id="GetHealthAndSportSummary",
        required_fields=("/dailySteps",),
        body=(
            'Template("TwoSupportLayout@1",{},'
            'Template("BatteryOverviewSupport@1",{}),'
            'Template("ActivityOverviewSupport@1",{}));'
        ),
    )

    output = await generate_template_a2ui(
        task, card_spec, (activity_binding, battery_binding), model,
        enable_fusion_ball=False, trusted_template_candidate_ids=templates,
    )

    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    by_id = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        assert component_id not in by_id
        by_id[component_id] = component
    marked_ids = [key for key in by_id if key.startswith("__genui_render_component__")]
    assert marked_ids == [_SKELETON_ID]
    foreground = by_id.get("template_root")
    assert foreground is not None
    assert foreground.get("children") == [_SKELETON_ID]
    skeleton = by_id.get(_SKELETON_ID)
    assert skeleton is not None
    assert skeleton.get("component") == "Column"
    assert len(skeleton.get("children", [])) == 2
    for field in (
        "/data/healthSport/dailySteps", "/data/phoneBattery/batterySOC",
        "/data/phoneBattery/chargingStatusDesc",
    ):
        assert field in output.a2ui
    assert "fusionBallBackground" not in by_id
