"""为显式声明内置操作的完整横版模板补充规划，不改变旧检索规则。"""

from models.generation import TaskSpec
from services.template_generation.engine.advanced.models import TemplateRouteSelection

from .business_actions import supports_business_action
from .models import TemplatePlan, TemplatePlanActionAssignment, TemplatePlanBusinessSlot
from .prompt import action_bindings
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .template_retrieval import TemplateRetrievalQuery


def plan_embedded_wide_full(
    query: TemplateRetrievalQuery,
    selection: TemplateRouteSelection,
    task: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[TemplatePlan, ...]:
    """只对单业务、单操作且完整覆盖字段的显式候选启用内置按钮。"""
    if task.size != "2x4" or len(query.action_ids) != 1:
        return ()
    if len(selection.component_candidates) != 1:
        return ()
    if len(query.required_output_fields_by_capability) != 1:
        return ()
    actions = [item for item in action_bindings(task) if item.event_id in query.action_ids]
    if len(actions) != 1:
        return ()
    capability_id, fields = next(iter(query.required_output_fields_by_capability.items()))
    candidate = selection.component_candidates[0]
    plans: list[TemplatePlan] = []
    for template_id in candidate.available_template_ids:
        definition = registry.require_template(template_id)
        if provider_template_layout_kind(template_id) != "WideFull":
            continue
        if definition.capability_id != capability_id:
            continue
        if not set(fields).issubset(definition.primary_data + definition.secondary_data):
            continue
        if not supports_business_action(definition, actions[0], task.size):
            continue
        plans.append(TemplatePlan(
            planId=f"wide-full-{len(plans) + 1}",
            themeId=selection.scope.theme_id,
            layoutTemplateId="WideFullOnlyLayout@1",
            businessSlots=(TemplatePlanBusinessSlot(
                position=0, businessId=candidate.component_id, capabilityId=capability_id,
                templateId=template_id, layoutRole="WideFull", coveredExplicitFields=fields,
                primaryMatchedFields=tuple(field for field in fields
                                           if field in definition.primary_data),
            ),),
            actionAssignments=(TemplatePlanActionAssignment(
                actionId=actions[0].action_id, consumer="business-template", businessPosition=0,
            ),),
        ))
        if len(plans) == 3:
            break
    return tuple(plans)
