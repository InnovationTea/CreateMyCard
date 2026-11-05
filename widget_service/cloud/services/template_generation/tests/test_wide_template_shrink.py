"""静态高度预检允许显式收缩，仍拒绝不可收缩内容超出预算。"""

import pytest

from services.template_generation.engine.cardplan.models import (
    TemplateNode,
    TemplatePlanBusinessSlot,
    TemplateValue,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.wide_template_planner import (
    _WIDE_LAYOUTS,
    _layout_geometry_fits,
    _template_node_intrinsic_height,
)


def _box(
    component: str = "Text",
    *,
    height: int = 120,
    shrink: TemplateValue | None = None,
    children: tuple[TemplateNode, ...] = (),
) -> TemplateNode:
    properties = {"height": TemplateValue(kind="literal", value=height)}
    if shrink is not None:
        properties["flexShrink"] = shrink
    return TemplateNode(
        component=component,
        values=(TemplateValue(kind="object", properties=properties),),
        children=children,
    )


@pytest.mark.parametrize("shrink", [1, 0.5, 2.0])
@pytest.mark.parametrize("component", ["Text", "Column"])
def test_explicit_shrink_does_not_impose_a_static_height_minimum(shrink, component):
    node = _box(
        component,
        shrink=TemplateValue(kind="literal", value=shrink),
        children=(_box(height=180),) if component == "Column" else (),
    )
    assert _template_node_intrinsic_height(node) == 0


@pytest.mark.parametrize("shrink", [0, -1, False, True, "1", None, float("inf"), float("nan")])
def test_non_positive_or_invalid_shrink_keeps_the_height_check(shrink):
    node = _box(shrink=TemplateValue(kind="literal", value=shrink))
    assert _template_node_intrinsic_height(node) == 120


@pytest.mark.parametrize("shrink", [None, TemplateValue(kind="binding", name="shrink")])
def test_missing_or_dynamic_shrink_keeps_the_height_check(shrink):
    assert _template_node_intrinsic_height(_box(shrink=shrink)) == 120


@pytest.mark.parametrize(
    "fixed_height, expected_height, partner_template, fits",
    [
        (20, 32, "HeartRateOverviewHero@1", True),
        (60, 72, "HeartRateOverviewHero@1", False),
        (20, 32, "CountdownOverviewEventHero@1", False),
    ],
)
def test_shrink_does_not_exempt_fixed_content_or_other_slots(
    fixed_height, expected_height, partner_template, fits,
):
    root = TemplateNode(
        component="Column",
        values=(
            TemplateValue(
                kind="object",
                properties={
                    "itemMargin": TemplateValue(kind="literal", value=4),
                    "padding": TemplateValue(
                        kind="object",
                        properties={
                            "top": TemplateValue(kind="literal", value=3),
                            "bottom": TemplateValue(kind="literal", value=5),
                        },
                    ),
                },
            ),
        ),
        children=(
            _box(shrink=TemplateValue(kind="literal", value=1)),
            _box(height=fixed_height),
        ),
    )
    assert _template_node_intrinsic_height(root) == expected_height
    registry = CardPlanRegistry()
    definition = registry.require_template("BluetoothDeviceOverviewEarbudPairHero@1")
    variant = definition.variants[0].model_copy(update={"root": root})
    registry.templates[definition.wire_id] = definition.model_copy(update={"variants": (variant,)})
    slots = (
        TemplatePlanBusinessSlot(
            position=0,
            businessId="BluetoothDeviceOverview",
            capabilityId="GetEarphoneInfo",
            templateId=definition.wire_id,
            layoutRole="Hero",
        ),
        TemplatePlanBusinessSlot(
            position=1,
            businessId="HeartRateOverview",
            capabilityId="GetHealthAndSportSummary",
            templateId=partner_template,
            layoutRole="Hero",
        ),
    )
    layout = next(item for item in _WIDE_LAYOUTS if item.layout_id == "WideTwoHeroActionLayout")
    assert _layout_geometry_fits(layout, slots, registry) is fits


def test_a_shrinkable_conditional_branch_does_not_hide_the_fixed_branch():
    condition = TemplateValue(kind="parameter", name="showDetails")
    flexible = TemplateNode(
        component="IfParam",
        values=(condition,),
        children=(_box(shrink=TemplateValue(kind="literal", value=1)),),
    )
    fixed = TemplateNode(
        component="IfMissingParam",
        values=(condition,),
        children=(_box(height=80),),
    )
    root = TemplateNode(component="Column", children=(flexible, fixed))
    assert _template_node_intrinsic_height(root) == 80
