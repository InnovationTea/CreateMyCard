"""非融球固定布局的防溢出标识、安全边距和双业务编译回归。

防溢出包装与双业务编译的完整产物已固化为场景金样（Layer C）：3 种容器
（Column/Row/Stack）× 3 种 padding（无/统一 12/四边 8-8-12-12）各一份，
快照整体冻结包装几何（tersel 树 + A2UI 消息）；TwoSupportLayout 双业务
共享骨架渲染一份；无单一骨架的旧壳（空/单文本/文本+列）与 2x4 尺寸的
「不包装」语义各固化一份（``non_fusion__legacy_*``，快照同时记录包装
是否返回原对象）。`__genui_render_component__` 标记恰好一个的属性仍保留
显式断言（这是本测试的核心属性，快照只固定其余细节）。引擎或模板改动后
按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

import asyncio
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
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_template_generation import (
    _FixedTemplateModel,
    _provider_field,
)

_SKELETON_ID = "__genui_render_component__root_1"
_PER_SIDE_PADDING = {"left": 8, "right": 8, "top": 12, "bottom": 12}


def _padding_slug(padding: int | dict[str, int] | None) -> str:
    if padding is None:
        return "nopadding"
    if isinstance(padding, dict):
        return "perside"
    return "uniform12"


def _build_non_fusion_geometry(
    component_type: str, padding: int | dict[str, int] | None,
) -> dict[str, Any]:
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

    assert original == snapshot  # 输入树不得被原地修改（非输出结构的保留属性）
    tersel = _serialize_node(wrapped) + ";"
    a2ui = convert_tersel_to_a2ui(
        tersel, size="2x2",
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
    )
    return {
        "terselTree": tersel,
        "a2uiMessages": [json.loads(line) for line in a2ui.splitlines() if line.strip()],
    }


@scenario("non_fusion__column__nopadding")
def _build_column_nopadding() -> dict:
    return _build_non_fusion_geometry("Column", None)


@scenario("non_fusion__column__uniform12")
def _build_column_uniform12() -> dict:
    return _build_non_fusion_geometry("Column", 12)


@scenario("non_fusion__column__perside")
def _build_column_perside() -> dict:
    return _build_non_fusion_geometry("Column", _PER_SIDE_PADDING)


@scenario("non_fusion__row__nopadding")
def _build_row_nopadding() -> dict:
    return _build_non_fusion_geometry("Row", None)


@scenario("non_fusion__row__uniform12")
def _build_row_uniform12() -> dict:
    return _build_non_fusion_geometry("Row", 12)


@scenario("non_fusion__row__perside")
def _build_row_perside() -> dict:
    return _build_non_fusion_geometry("Row", _PER_SIDE_PADDING)


@scenario("non_fusion__stack__nopadding")
def _build_stack_nopadding() -> dict:
    return _build_non_fusion_geometry("Stack", None)


@scenario("non_fusion__stack__uniform12")
def _build_stack_uniform12() -> dict:
    return _build_non_fusion_geometry("Stack", 12)


@scenario("non_fusion__stack__perside")
def _build_stack_perside() -> dict:
    return _build_non_fusion_geometry("Stack", _PER_SIDE_PADDING)


async def _render_two_support_shared_skeleton() -> dict[str, Any]:
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
    return a2ui_messages(output)


@scenario("non_fusion__two_support_shared_skeleton")
def _build_two_support_shared_skeleton() -> dict:
    return asyncio.run(_render_two_support_shared_skeleton())


def _build_legacy_shell(
    children: tuple[Nested2Node, ...],
    size: str = "2x2",
    root_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = Nested2Node("Column", ("card", root_options or {"_id": "root", "padding": 12}), children)
    snapshot = deepcopy(card)
    wrapped = apply_content_safe_inset(card, size=size)
    assert card == snapshot  # 输入树不得被原地修改（非输出结构的保留属性）
    tersel = _serialize_node(wrapped) + ";"
    a2ui = convert_tersel_to_a2ui(
        tersel, size=size,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
    )
    return {
        "returnedSameObject": wrapped is card,
        "terselTree": tersel,
        "a2uiMessages": [json.loads(line) for line in a2ui.splitlines() if line.strip()],
    }


@scenario("non_fusion__legacy_shell_no_children")
def _build_legacy_no_children() -> dict[str, Any]:
    return _build_legacy_shell(())


@scenario("non_fusion__legacy_shell_single_text")
def _build_legacy_single_text() -> dict[str, Any]:
    return _build_legacy_shell((Nested2Node("Text", ("正文",), ()),))


@scenario("non_fusion__legacy_shell_text_and_column")
def _build_legacy_text_and_column() -> dict[str, Any]:
    return _build_legacy_shell(
        (Nested2Node("Text", ("标题",), ()), Nested2Node("Column", (), ()))
    )


@scenario("non_fusion__legacy_shell_non_2x2_size")
def _build_legacy_non_2x2_size() -> dict[str, Any]:
    return _build_legacy_shell(
        (Nested2Node("Column", ({"_id": "template_root"},), ()),),
        size="2x4", root_options={"_id": "root"},
    )


@pytest.mark.parametrize("component_type", ["Column", "Row", "Stack"])
@pytest.mark.parametrize("padding", [None, 12, _PER_SIDE_PADDING])
def test_non_fusion_marks_actual_skeleton_and_preserves_geometry(
    component_type: str, padding: int | dict[str, int] | None,
) -> None:
    assert_golden_scenario(
        f"non_fusion__{component_type.lower()}__{_padding_slug(padding)}"
    )


def test_two_support_compilation_marks_one_shared_skeleton() -> None:
    payload = _build_two_support_shared_skeleton()
    components = payload["a2ui"][1]["updateComponents"]["components"]
    by_id = {component["id"]: component for component in components}
    marked_ids = [key for key in by_id if key.startswith("__genui_render_component__")]
    assert marked_ids == [_SKELETON_ID]  # 共享骨架恰好一个防溢出标记（本测试的核心属性）
    assert_golden_scenario("non_fusion__two_support_shared_skeleton")
