"""横版完整组合枚举：Search 只提供数据候选，本模块固定实例、字段和动作位置。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations, permutations, product
from typing import Any

from models.generation import TaskSpec

from .business_actions import matches_business_data, supports_business_action
from .models import (
    ActionBinding,
    TemplateDefinition,
    TemplateNode,
    TemplatePlanActionAssignment,
    TemplatePlanBusinessSlot,
)
from .prompt import action_bindings
from .provider_bundle import (
    asset_semantic_tags,
    parameter_value_kind,
    provider_template_layout_kind,
)
from .registry import CardPlanRegistry
from .template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchIntent,
    TemplateSearchResult,
    _template_available_data_fields,
    template_required_assets_are_available,
)

_GENERIC_BUSINESS = "GenericMetricOverview"
_CALENDAR_COUNTDOWN_FULL_IDS = frozenset(
    {
        "CountdownOverviewTargetDetailFull@1",
        "ScheduleOverviewEventCountTwoEventsFull@1",
    }
)

# 这些布局允许单动作内嵌进业务模板根节点（底板事件），不产生布局根的 Action 槽位。
_EMBEDDED_ACTION_LAYOUT_IDS = frozenset({"WideFullOnlyLayout", "WideTwoFocusLayout"})


@dataclass(frozen=True)
class WideLayoutOption:
    layout_id: str
    roles: tuple[str, ...]
    action_templates: tuple[str, ...] = ()
    # 有归属的按钮区按 child 位置绑定业务；None 表示独立共享操作区。
    action_owners: tuple[int | None, ...] = ()
    # 该形态没有独立 Action 槽位，允许单动作内嵌进某个业务模板根节点。
    allows_embedded_action: bool = False
    # 部分布局的槽位高度是固定预算。声明后，Planner 会在生成组合时先做
    # 业务模板的静态最小高度预检，避免把必然溢出的组合交给第二层模型。
    slot_height_budgets: tuple[int | None, ...] = ()


# 顺序只用于同分方案的稳定择优；不得因前一形态不成立而拒绝后续形态。
_WIDE_LAYOUTS = (
    WideLayoutOption("WideFullOnlyLayout", ("WideFull",)),
    WideLayoutOption("WideTwoFocusLayout", ("Hero", "Hero")),
    WideLayoutOption("WideTwoFullLayout", ("Full", "Full")),
    WideLayoutOption("WideTwoHalfLayout", ("WideHalf", "WideHalf")),
    WideLayoutOption("WideHeroCompactLayout", ("Hero", "Compact")),
    # 2x4 的窄业务槽位语义是 Support。旧 Compact 形态保留在后面，
    # 仅用于兼容尚未迁移的历史 Provider。
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Full", "Support"), ("CompactSubtitleAction",), (None,)
    ),
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Full", "Support", "Support"), allows_embedded_action=True
    ),
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Hero", "Support"), ("CompactAction",), (None,)
    ),
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Full", "Support", "Support"), allows_embedded_action=True
    ),
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Full", "Compact", "Compact"), allows_embedded_action=True
    ),
    WideLayoutOption("WideHalfTwoCompactLayout", ("WideHalf", "Compact", "Compact")),
    WideLayoutOption("WideFourCompactLayout", ("Compact",) * 4),
    WideLayoutOption("WideSingleFocusLayout", ("WideHero",), ("PillAction",), (None,)),
    WideLayoutOption("WideTwoFocusActionLayout", ("Hero", "Hero"), ("PillAction",), (0,)),
    # 右列"2x1 业务 + 2x1 动作"与"整块 Hero + 按钮行"同分时，优先前者。
    WideLayoutOption(
        "WideFullTwoCompactLayout", ("Full", "Compact"), ("CompactSubtitleAction",), (None,)
    ),
    WideLayoutOption("WideFullHeroActionLayout", ("Full", "Hero"), ("PillAction",), (1,)),
    WideLayoutOption("WideFullHeroActionLayout", ("Full", "Hero"), ("PillAction",), (None,)),
    WideLayoutOption("WideHeroActionFullLayout", ("Full", "Hero"), ("PillAction",), (1,)),
    WideLayoutOption(
        "WideHalfTwoCompactLayout", ("WideHalf", "Compact"), ("CompactAction",), (None,)
    ),
    WideLayoutOption("WideFullTwoCompactLayout", ("Hero", "Compact"), ("CompactAction",), (None,)),
    WideLayoutOption(
        "WideTwoFocusTwoActionLayout",
        ("Hero", "Hero"),
        ("PillAction",) * 2,
        (0, 1),
        slot_height_budgets=(66, 66),
    ),
    WideLayoutOption(
        "WideTwoHeroActionLayout",
        ("Hero", "Hero"),
        ("PillAction",) * 2,
        (0, 1),
        slot_height_budgets=(58, 58),
    ),
    WideLayoutOption("WideFullHeroTwoActionLayout", ("Full", "Hero"), ("PillAction",) * 2, (1, 1)),
    WideLayoutOption("WideFullTwoCompactLayout", ("Full",), ("CompactAction",) * 2, (None, None)),
    WideLayoutOption(
        "WideHalfCompactTwoLargeActionLayout",
        ("WideHalf", "Compact"),
        ("LargeIconAction",) * 2,
        (None, None),
    ),
    WideLayoutOption("WideFullFourActionLayout", ("Full",), ("LargeIconAction",) * 4, (None,) * 4),
    WideLayoutOption(
        "WideHalfFourLargeActionLayout", ("WideHalf",), ("LargeIconAction",) * 4, (None,) * 4
    ),
)


@dataclass(frozen=True)
class WidePlanComposition:
    layout_template_id: str
    slots: tuple[TemplatePlanBusinessSlot, ...]
    assignments: tuple[TemplatePlanActionAssignment, ...]
    # 同分 Plan 用 _WIDE_LAYOUTS 位次稳定择优，避免依赖覆盖组合的枚举顺序。
    layout_rank: int


def wide_plan_compositions(
    intent: TemplateSearchIntent,
    search_result: TemplateSearchResult,
    task: TaskSpec,
    registry: CardPlanRegistry,
) -> Iterator[WidePlanComposition]:
    """枚举完整覆盖的实例组合，再匹配布局和事件，绝不改写请求的业务集合。"""
    if len(intent.required_output_fields_by_capability) > 4:
        return
    groups_by_capability: dict[str, list[TemplateBusinessCandidates]] = {}
    for group in search_result.business_candidates:
        groups_by_capability.setdefault(group.capability_id, []).append(group)
    capability_options = []
    for capability_id in intent.required_output_fields_by_capability:
        groups = groups_by_capability.get(capability_id, [])
        capability_options.append(
            _capability_covers(
                groups,
                intent,
                task,
                registry,
            )
        )
    actions = tuple(
        action for action in action_bindings(task) if action.event_id in intent.action_ids
    )
    for covers in product(*capability_options):
        combined_slots: list[TemplatePlanBusinessSlot] = []
        for cover in covers:
            combined_slots.extend(cover)
        slots = tuple(combined_slots)
        if len(slots) > 4:
            continue
        # 单动作时允许为已选业务追加一个可内嵌动作的伴生 2x1 槽位（如歌单入口），
        # 动作不必再挤进 PillAction 行；伴生槽位不承载显式字段。
        slot_options: tuple[tuple[TemplatePlanBusinessSlot, ...], ...] = (slots,)
        if len(actions) == 1 and len(slots) < 4:
            available_fields_by_capability: dict[str, set[str]] = {}
            for group in search_result.business_candidates:
                available_fields_by_capability.setdefault(group.capability_id, set()).update(
                    path
                    for candidate in group.candidates
                    for path in candidate.available_data_fields
                )
            companions = _companion_action_slots(
                slots,
                actions,
                registry,
                task,
                available_fields_by_capability,
            )
            slot_options += tuple((*slots, companion) for companion in companions)
        for option_slots in slot_options:
            for layout_rank, layout in enumerate(_WIDE_LAYOUTS):
                if len(layout.roles) != len(option_slots):
                    continue
                embedded = len(actions) == 1 and (
                    layout.allows_embedded_action
                    or layout.layout_id in _EMBEDDED_ACTION_LAYOUT_IDS
                    or (
                        layout.layout_id == "WideTwoFullLayout"
                        and {slot.template_id for slot in option_slots}
                        == _CALENDAR_COUNTDOWN_FULL_IDS
                    )
                )
                if not embedded and len(layout.action_templates) != len(actions):
                    continue
                for ordered in _ordered_slots(option_slots, layout.roles):
                    if not _layout_geometry_fits(layout, ordered, registry):
                        continue
                    for assignments in _action_assignments(
                        layout, ordered, actions, registry, task, embedded
                    ):
                        if not _required_business_actions_are_assigned(
                            ordered, assignments, registry
                        ):
                            continue
                        yield WidePlanComposition(
                            f"{layout.layout_id}@1", ordered, assignments, layout_rank
                        )


def _layout_geometry_fits(
    layout: WideLayoutOption,
    slots: tuple[TemplatePlanBusinessSlot, ...],
    registry: CardPlanRegistry,
) -> bool:
    """Reject deterministic geometry overflows before second-layer selection.

    The prediction intentionally uses the provider blueprint rather than the
    LLM-filled parameters. Fixed text/icon heights and vertical gaps are
    already part of the trusted template definition, so this is conservative:
    a template is rejected when its declared minimum content cannot fit the
    slot, while flexible templates remain eligible.
    """
    if not layout.slot_height_budgets:
        return True
    if len(layout.slot_height_budgets) != len(slots):
        return False
    for slot, budget in zip(slots, layout.slot_height_budgets, strict=True):
        if budget is None:
            continue
        required_height = _template_intrinsic_height(slot.template_id, registry)
        if required_height > budget:
            return False
    return True


def _template_intrinsic_height(template_id: str, registry: CardPlanRegistry) -> int:
    """Estimate a business template's natural vertical requirement.

    ``matchParent`` is deliberately ignored here: it is a flexible request,
    not an intrinsic minimum. Numeric heights, vertical padding, item margins,
    and the largest branch of paired template conditionals are retained.
    """
    definition = registry.require_template(template_id)
    variants = tuple(
        variant
        for variant in definition.variants
        if not variant.supported_card_sizes or "2x4" in variant.supported_card_sizes
    ) or definition.variants
    return max((_template_node_intrinsic_height(variant.root) for variant in variants), default=0)


def _template_node_intrinsic_height(node: TemplateNode) -> int:
    if node.component in {
        "IfParam",
        "IfMissingParam",
        "IfBind",
        "IfMissingBind",
        "IfAllBind",
        "IfAnyBind",
        "IfAllMissingBind",
        "IfAnyMissingBind",
    }:
        return _template_sequence_intrinsic_height(node.children)

    options = _template_node_options(node)
    explicit_height = options.get("height")
    fixed_height = int(explicit_height) if isinstance(explicit_height, (int, float)) else 0
    children_height = _template_sequence_intrinsic_height(node.children)
    component = node.component
    if component in {"Row", "Stack"}:
        natural_height = max((
            _template_node_intrinsic_height(child) for child in node.children
        ), default=24)
    elif component in {"Column", "List"}:
        margin = options.get("itemMargin", options.get("space", 4))
        margin_value = int(margin) if isinstance(margin, (int, float)) else 4
        natural_height = children_height + max(
            0, _template_sequence_effective_count(node.children) - 1
        ) * margin_value
    else:
        natural_height = {
            "Text": 20,
            "Image": 24,
            "Progress": 40,
            "Button": 32,
            "Divider": 0,
        }.get(component, 20)
        if node.children:
            natural_height = max(natural_height, children_height)

    # A primitive's explicit height is its actual line/icon height. For
    # containers, retain the larger of the fixed slot and natural children so
    # the predictor remains conservative when a blueprint itself is too tight.
    if component not in {"Row", "Stack", "Column", "List"} and fixed_height:
        natural_height = fixed_height

    padding = options.get("padding")
    if isinstance(padding, dict):
        natural_height += sum(
            int(padding.get(edge, 0))
            for edge in ("top", "bottom")
            if isinstance(padding.get(edge, 0), (int, float))
        )
    return max(fixed_height, natural_height)


def _template_sequence_intrinsic_height(children: tuple[TemplateNode, ...]) -> int:
    total = 0
    index = 0
    while index < len(children):
        current = children[index]
        if index + 1 < len(children) and _are_conditional_pair(current, children[index + 1]):
            total += max(
                _template_node_intrinsic_height(current),
                _template_node_intrinsic_height(children[index + 1]),
            )
            index += 2
            continue
        total += _template_node_intrinsic_height(current)
        index += 1
    return total


def _template_sequence_effective_count(children: tuple[TemplateNode, ...]) -> int:
    """Count rendered children while collapsing paired conditional branches."""
    count = 0
    index = 0
    while index < len(children):
        count += 1
        if index + 1 < len(children) and _are_conditional_pair(
            children[index], children[index + 1]
        ):
            index += 2
        else:
            index += 1
    return count


def _are_conditional_pair(first: TemplateNode, second: TemplateNode) -> bool:
    complements = {
        "IfParam": "IfMissingParam",
        "IfMissingParam": "IfParam",
        "IfBind": "IfMissingBind",
        "IfMissingBind": "IfBind",
        "IfAllBind": "IfAnyMissingBind",
        "IfAnyMissingBind": "IfAllBind",
        "IfAnyBind": "IfAllMissingBind",
        "IfAllMissingBind": "IfAnyBind",
    }
    if complements.get(first.component) != second.component:
        return False
    if not first.values or not second.values:
        return True
    return first.values[0].model_dump(mode="json") == second.values[0].model_dump(mode="json")


def _template_node_options(node: TemplateNode) -> dict[str, object]:
    for value in node.values:
        if value.kind == "object":
            return {
                key: _template_value_literal(item)
                for key, item in value.properties.items()
                if item.kind in {"literal", "object"}
            }
    return {}


def _template_value_literal(value: object) -> object:
    if not hasattr(value, "kind"):
        return None
    if value.kind == "literal":
        return value.value
    if value.kind == "object":
        return {
            key: _template_value_literal(item)
            for key, item in value.properties.items()
        }
    return None


def _required_business_actions_are_assigned(
    slots: tuple[TemplatePlanBusinessSlot, ...],
    assignments: tuple[TemplatePlanActionAssignment, ...],
    registry: CardPlanRegistry,
) -> bool:
    """必填动作必须分配到业务模板本身，不能以根动作替代。"""
    assigned_positions: set[int] = set()
    for assignment in assignments:
        if assignment.consumer == "business-template":
            position = assignment.business_position
            if position is not None:
                assigned_positions.add(position)
    for slot in slots:
        definition = registry.require_template(slot.template_id)
        variants = [
            variant for variant in definition.variants if "2x4" in variant.supported_card_sizes
        ]
        if not variants:
            variants = list(definition.variants)
        permits_no_action = False
        for variant in variants:
            if "actionId" not in variant.parameters_schema.get("required", ()):
                permits_no_action = True
                break
        if not permits_no_action and slot.position not in assigned_positions:
            return False
    return True


def _companion_action_slots(
    slots: tuple[TemplatePlanBusinessSlot, ...],
    actions: tuple[ActionBinding, ...],
    registry: CardPlanRegistry,
    task: TaskSpec,
    available_fields_by_capability: dict[str, set[str]],
) -> tuple[TemplatePlanBusinessSlot, ...]:
    """为已选业务枚举可承载单动作的伴生 Compact 或 Support 槽位。

    伴生模板虽然不承载显式字段、不进入 Search 显式字段候选，仍必须先通过
    与普通候选等价的准入检查（尺寸、必需数据、必需素材、事件），
    禁止把缺少必需素材的模板放进计划后等待第二层整条失败。
    """
    results: list[TemplatePlanBusinessSlot] = []
    seen: set[tuple[str, str]] = {(slot.business_id, slot.template_id) for slot in slots}
    capability_by_business = {slot.business_id: slot.capability_id for slot in slots}
    already_rendered_fields: set[str] = set()
    for slot in slots:
        definition = registry.require_template(slot.template_id)
        already_rendered_fields.update(
            _rendered_template_fields(
                definition,
                task,
                available_fields_by_capability.get(slot.capability_id, set()),
            )
        )
        already_rendered_fields.update(slot.field_bindings.values())
    for action in actions:
        for business_id in sorted(capability_by_business):
            component = registry.require_ux_business_component(business_id)
            companion_template_ids = tuple(
                sorted(
                    registry.enabled_template_ids(component.local_template_ids),
                    key=lambda template_id: (
                        provider_template_layout_kind(template_id) != "Support",
                        template_id,
                    ),
                )
            )
            for template_id in companion_template_ids:
                if (business_id, template_id) in seen:
                    continue
                template_kind = provider_template_layout_kind(template_id)
                if template_kind not in {"Support", "Compact"}:
                    continue
                definition = registry.require_template(template_id)
                if not template_required_assets_are_available(definition, task):
                    continue
                if not _required_data_available(definition, task):
                    continue
                if template_kind == "Support":
                    support_fields = _rendered_template_fields(
                        definition,
                        task,
                        available_fields_by_capability.get(
                            capability_by_business[business_id], set()
                        ),
                    )
                    # A layout-owned Support must add a metric or consume its own action.
                    # a Support that only repeats the Full's city/temperature/
                    # condition fields to fill an empty action-side slot.
                    adds_information = bool(support_fields.difference(already_rendered_fields))
                    consumes_action = supports_business_action(definition, action, "2x4")
                    if not adds_information and not consumes_action:
                        continue
                # A Support companion is rendered in a layout-owned slot and
                # the action is consumed by the sibling root Action slot. It
                # therefore does not need to declare the event itself. Legacy
                # Compact companions still require their historical business
                # action contract.
                if template_kind != "Support" and not supports_business_action(
                    definition, action, "2x4"
                ):
                    continue
                seen.add((business_id, template_id))
                results.append(
                    TemplatePlanBusinessSlot(
                        position=0,
                        businessId=business_id,
                        capabilityId=capability_by_business[business_id],
                        templateId=template_id,
                        layoutRole=template_kind,
                        coveredExplicitFields=(),
                        primaryMatchedFields=(),
                    )
                )
    return tuple(results)


def _rendered_template_fields(
    definition: TemplateDefinition,
    task: TaskSpec,
    candidate_paths: set[str],
) -> set[str]:
    """Return only fields whose conditional branch actually renders this input.

    Provider ``primaryData``/``secondaryData`` describes coverage eligibility,
    not necessarily the fields emitted by every conditional branch.  Companion
    Support selection must use the latter, otherwise an optional field already
    rendered by the main template looks like new information.
    """
    if not definition.data_domain:
        return set()
    rendered = _template_available_data_fields(
        definition,
        task,
        (definition.data_domain,),
        candidate_paths,
        rendered_only=True,
    )
    prefix = definition.data_domain.rstrip("/")
    return {
        path.removeprefix(prefix)
        for path in rendered
        if path.startswith(f"{prefix}/")
    }


def _required_data_available(definition: TemplateDefinition, task: TaskSpec) -> bool:
    """伴生模板的必需数据路径必须能在 TaskSpec 数据模型中解析到。"""
    data = task.dataModelSchema.get("data") if isinstance(task.dataModelSchema, dict) else None

    def resolves(node: Any, segments: list[str]) -> bool:
        for segment in segments:
            if isinstance(node, list):
                if not segment.isdigit() or int(segment) >= len(node):
                    return False
                node = node[int(segment)]
                continue
            if not isinstance(node, dict) or segment not in node:
                return False
            node = node[segment]
        return True

    for path in definition.required_data:
        segments = path.strip("/").split("/")
        # Provider paths are relative to the capability root (for example
        # ``/current/humidityPercent``), while TaskSpec stores that root below
        # ``data.weather``. Try the complete data object and each capability
        # root; the previous implementation skipped the first path segment and
        # incorrectly rejected valid Support companions.
        roots = [data]
        if isinstance(data, dict):
            roots.extend(value for value in data.values() if isinstance(value, (dict, list)))
        if not any(resolves(root, segments) for root in roots):
            return False
    return True


def _capability_covers(
    groups: list[TemplateBusinessCandidates],
    intent: TemplateSearchIntent,
    task: TaskSpec,
    registry: CardPlanRegistry,
) -> tuple[tuple[TemplatePlanBusinessSlot, ...], ...]:
    if not groups:
        return ()
    explicit = groups[0].explicit_fields
    available: list[TemplatePlanBusinessSlot] = []
    for group in groups:
        for candidate in group.candidates:
            definition = registry.require_template(candidate.template_id)
            role = provider_template_layout_kind(candidate.template_id)
            if role is None:
                continue
            field_options: tuple[dict[str, str], ...] = ({},)
            if group.business_id == _GENERIC_BUSINESS:
                field_options = _generic_field_options(
                    candidate.template_id, candidate.covered_explicit_fields, task
                )
            for fields in field_options:
                covered = tuple(fields.values()) if fields else candidate.covered_explicit_fields
                focus = intent.primary_output_field_by_capability.get(group.capability_id)
                primary = tuple(
                    path for path in definition.primary_data if path in explicit or path == focus
                )
                available.append(
                    TemplatePlanBusinessSlot(
                        position=0,
                        businessId=group.business_id,
                        capabilityId=group.capability_id,
                        templateId=candidate.template_id,
                        layoutRole=role,
                        coveredExplicitFields=covered,
                        primaryMatchedFields=primary,
                        fieldBindings=fields,
                    )
                )
    if not explicit:
        return tuple((slot,) for slot in available if not slot.field_bindings)
    results: dict[tuple[str, ...], tuple[TemplatePlanBusinessSlot, ...]] = {}

    def extend(selected: tuple[TemplatePlanBusinessSlot, ...], covered: frozenset[str]) -> None:
        missing = tuple(path for path in explicit if path not in covered)
        if not missing:
            ordered = tuple(
                sorted(selected, key=lambda slot: (bool(slot.field_bindings), _slot_key(slot)))
            )
            results.setdefault(tuple(_slot_key(slot) for slot in ordered), ordered)
            return
        if len(selected) == 4:
            return
        business_ids = {slot.business_id for slot in selected if not slot.field_bindings}
        generic_fields: set[str] = set()
        for slot in selected:
            generic_fields.update(slot.field_bindings.values())
        for slot in available:
            fields = set(slot.covered_explicit_fields)
            if missing[0] not in fields:
                continue
            if slot.business_id in business_ids and not _may_pair_with_selected(selected, slot):
                continue
            if slot.field_bindings and covered.intersection(fields):
                continue
            if generic_fields.intersection(fields):
                continue
            extend((*selected, slot), covered.union(fields))

    extend((), frozenset())
    return tuple(results.values())


def _may_pair_with_selected(
    selected: tuple[TemplatePlanBusinessSlot, ...],
    slot: TemplatePlanBusinessSlot,
) -> bool:
    """单业务 Full + Compact 拆槽：同一业务允许恰好占两个宽窄槽位。

    仅当该业务已选中恰好一个非 Generic 槽位，且新槽位与其构成
    Full + Compact 互补对时放行；第三个同业务槽位仍被拒绝，
    双 Hero、双 Full 等混拼依旧不成立。
    """
    if slot.field_bindings:
        return False
    kind = provider_template_layout_kind(slot.template_id)
    if kind not in {"Full", "Compact", "Support"}:
        return False
    same_business = [
        item
        for item in selected
        if item.business_id == slot.business_id and not item.field_bindings
    ]
    if len(same_business) != 1:
        return False
    other_kind = provider_template_layout_kind(same_business[0].template_id)
    return other_kind in {"Full", "Compact", "Support"} and other_kind != kind


def _generic_field_options(
    template_id: str,
    fields: tuple[str, ...],
    task: TaskSpec,
) -> tuple[dict[str, str], ...]:
    if template_id == "GenericMetricOverviewCompact@1":
        has_icon = any(isinstance(asset.get("src"), str) for asset in task.assetCandidates)
        if not has_icon:
            return ()
        return tuple({"valuePath": field} for field in fields)
    return tuple(
        {"firstValuePath": first, "secondValuePath": second}
        for first, second in combinations(fields, 2)
    )


def _slot_key(slot: TemplatePlanBusinessSlot) -> str:
    return slot.template_id + ":" + ",".join(slot.field_bindings.values())


def _ordered_slots(
    slots: tuple[TemplatePlanBusinessSlot, ...],
    roles: tuple[str, ...],
) -> Iterator[tuple[TemplatePlanBusinessSlot, ...]]:
    seen: set[tuple[str, ...]] = set()
    for ordered in permutations(slots):
        if tuple(slot.layout_role for slot in ordered) != roles:
            continue
        key = tuple(_slot_key(slot) for slot in ordered)
        if key in seen:
            continue
        seen.add(key)
        yield tuple(
            slot.model_copy(update={"position": index}) for index, slot in enumerate(ordered)
        )


def _action_assignments(
    layout: WideLayoutOption,
    slots: tuple[TemplatePlanBusinessSlot, ...],
    actions: tuple[ActionBinding, ...],
    registry: CardPlanRegistry,
    task: TaskSpec,
    embedded: bool,
) -> Iterator[tuple[TemplatePlanActionAssignment, ...]]:
    if embedded:
        for slot in slots:
            definition = registry.require_template(slot.template_id)
            if not supports_business_action(definition, actions[0], "2x4"):
                continue
            yield (
                TemplatePlanActionAssignment(
                    actionId=actions[0].action_id,
                    consumer="business-template",
                    businessPosition=slot.position,
                ),
            )
        return
    if any(
        not _action_template_has_complete_signature(f"{template}@1", task, registry)
        for template in layout.action_templates
    ):
        return
    if _is_unreviewed_countdown_shared_action_pair(layout, slots):
        return
    owners = {
        action.action_id: _action_owner_positions(action, slots, registry) for action in actions
    }
    for ordered in permutations(actions):
        assignments: list[TemplatePlanActionAssignment] = []
        for action, template, owner in zip(
            ordered, layout.action_templates, layout.action_owners, strict=True
        ):
            positions = owners.get(action.action_id, ())
            # Only the migrated weather/countdown pair permits either mirrored
            # layout: the visual Action slot may differ from its data owner.
            if _is_weather_countdown_action_layout(layout, slots):
                owner = None
            if owner is not None and owner not in positions:
                break
            position = owner
            if position is None and len(positions) == 1:
                position = positions[0]
            # 双行动作模板的 subtitle 为必选 Props：动作没有批准副标题时
            # 回退单行 CompactAction，保证第二层能填满模板签名。
            plan_template = (
                "CompactAction"
                if template == "CompactSubtitleAction" and not action.display_subtitle
                else template
            )
            assignments.append(
                TemplatePlanActionAssignment(
                    actionId=action.action_id,
                    consumer="root-action",
                    businessPosition=position,
                    actionTemplateId=f"{plan_template}@1",
                )
            )
        if len(assignments) == len(actions):
            yield tuple(assignments)
        # 共享操作区保持输入事件顺序；只有成对按钮需要按业务重排。
        if all(owner is None for owner in layout.action_owners):
            break


def _action_template_has_complete_signature(
    template_id: str,
    task: TaskSpec,
    registry: CardPlanRegistry,
) -> bool:
    """Exclude plans whose root Action cannot receive its required trusted asset."""
    definition = registry.require_template(template_id)
    assets = tuple(
        asset
        for asset in task.assetCandidates
        if isinstance(asset, dict) and isinstance(asset.get("src"), str) and asset["src"]
    )
    for variant in definition.variants:
        properties = variant.parameters_schema.get("properties", {})
        for name in variant.parameters_schema.get("required", ()):
            if parameter_value_kind(name, properties.get(name, {})) != "asset-source":
                continue
            required_tags = set(definition.asset_parameter_semantic_tags.get(name, ()))
            if not any(required_tags.issubset(asset_semantic_tags(asset)) for asset in assets):
                break
        else:
            return True
    return False


def _is_weather_countdown_action_layout(
    layout: WideLayoutOption,
    slots: tuple[TemplatePlanBusinessSlot, ...],
) -> bool:
    return (
        layout.layout_id in {"WideFullHeroActionLayout", "WideHeroActionFullLayout"}
        and len(slots) == 2
        and slots[0].template_id
        in {
            "WeatherOverviewThreeDayForecastFull@1",
            "WeatherOverviewDestinationDayFull@1",
        }
        and slots[1].template_id
        in {"CountdownOverviewEventHero@1", "CountdownOverviewDepartureHero@1"}
    )


def _is_unreviewed_countdown_shared_action_pair(
    layout: WideLayoutOption,
    slots: tuple[TemplatePlanBusinessSlot, ...],
) -> bool:
    """共享操作区布局不得搭配倒计时 Hero 槽位生成未经评审的组合。

    倒计时业务的宽版 Hero 组合按镜像白名单评审（Event/Departure Hero 走
    归属按钮镜像）；健康+倒计时的 Compact 组合走 Q084 评审过的
    CompactSubtitleAction/CompactAction 计划。共享操作区（ownerless）布局
    与倒计时 Hero 的其余搭配不属于上述任一评审边界。
    """
    if layout.action_owners != (None,):
        return False
    return any(
        slot.template_id.startswith("CountdownOverview")
        and provider_template_layout_kind(slot.template_id) == "Hero"
        for slot in slots
    )


def _action_owner_positions(
    action: ActionBinding,
    slots: tuple[TemplatePlanBusinessSlot, ...],
    registry: CardPlanRegistry,
) -> tuple[int, ...]:
    positions: list[int] = []
    for slot in slots:
        business = registry.require_ux_business_component(slot.business_id)
        supported_events: set[str] = set()
        for template_id in registry.enabled_template_ids(business.local_template_ids):
            supported_events.update(registry.require_template(template_id).supported_event_ids)
        if action.event_id not in supported_events:
            continue
        definition = registry.require_template(slot.template_id)
        if matches_business_data(definition, action, allow_static_target=True):
            positions.append(slot.position)
    return tuple(positions)
