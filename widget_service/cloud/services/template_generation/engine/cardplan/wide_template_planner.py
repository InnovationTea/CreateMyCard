"""横版完整组合枚举：Search 只提供数据候选，本模块固定实例、字段和动作位置。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import combinations, permutations, product

from models.generation import TaskSpec

from .business_actions import matches_business_data, supports_business_action
from .models import ActionBinding, TemplatePlanActionAssignment, TemplatePlanBusinessSlot
from .prompt import _asset_semantic_tags, _parameter_value_kind, action_bindings
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchIntent,
    TemplateSearchResult,
)

_GENERIC_BUSINESS = "GenericMetricOverview"
_CALENDAR_COUNTDOWN_FULL_IDS = frozenset(
    {
        "CountdownOverviewTargetDetailFull@1",
        "ScheduleOverviewEventCountTwoEventsFull@1",
    }
)


@dataclass(frozen=True)
class WideLayoutOption:
    layout_id: str
    roles: tuple[str, ...]
    action_templates: tuple[str, ...] = ()
    # 有归属的按钮区按 child 位置绑定业务；None 表示独立共享操作区。
    action_owners: tuple[int | None, ...] = ()


# 顺序只用于同分方案的稳定择优；不得因前一形态不成立而拒绝后续形态。
_WIDE_LAYOUTS = (
    WideLayoutOption("WideFullOnlyLayout", ("WideFull",)),
    WideLayoutOption("WideTwoFocusLayout", ("Hero", "Hero")),
    WideLayoutOption("WideTwoFullLayout", ("Full", "Full")),
    WideLayoutOption("WideTwoHalfLayout", ("WideHalf", "WideHalf")),
    WideLayoutOption("WideHeroCompactLayout", ("Hero", "Compact")),
    WideLayoutOption("WideFullTwoCompactLayout", ("Full", "Compact", "Compact")),
    WideLayoutOption("WideHalfTwoCompactLayout", ("WideHalf", "Compact", "Compact")),
    WideLayoutOption("WideFourCompactLayout", ("Compact",) * 4),
    WideLayoutOption("WideSingleFocusLayout", ("WideHero",), ("PillAction",), (None,)),
    WideLayoutOption("WideTwoFocusActionLayout", ("Hero", "Hero"), ("PillAction",), (0,)),
    WideLayoutOption("WideFullHeroActionLayout", ("Full", "Hero"), ("PillAction",), (1,)),
    WideLayoutOption("WideHeroActionFullLayout", ("Full", "Hero"), ("PillAction",), (1,)),
    WideLayoutOption(
        "WideHalfTwoCompactLayout", ("WideHalf", "Compact"), ("CompactAction",), (None,)
    ),
    WideLayoutOption("WideFullTwoCompactLayout", ("Full", "Compact"), ("CompactAction",), (None,)),
    WideLayoutOption("WideFullTwoCompactLayout", ("Hero", "Compact"), ("CompactAction",), (None,)),
    WideLayoutOption("WideTwoFocusTwoActionLayout", ("Hero", "Hero"), ("PillAction",) * 2, (0, 1)),
    WideLayoutOption("WideTwoHeroActionLayout", ("Hero", "Hero"), ("PillAction",) * 2, (0, 1)),
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
        capability_options.append(_capability_covers(groups, intent, task, registry))
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
        for layout in _WIDE_LAYOUTS:
            if len(layout.roles) != len(slots):
                continue
            embedded = len(actions) == 1 and (
                layout.layout_id == "WideFullOnlyLayout"
                or (
                    layout.layout_id == "WideTwoFullLayout"
                    and {slot.template_id for slot in slots} == _CALENDAR_COUNTDOWN_FULL_IDS
                )
            )
            if not embedded and len(layout.action_templates) != len(actions):
                continue
            for ordered in _ordered_slots(slots, layout.roles):
                for assignments in _action_assignments(
                    layout, ordered, actions, registry, task, embedded
                ):
                    yield WidePlanComposition(f"{layout.layout_id}@1", ordered, assignments)


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
    if kind not in {"Full", "Compact"}:
        return False
    same_business = [
        item
        for item in selected
        if item.business_id == slot.business_id and not item.field_bindings
    ]
    if len(same_business) != 1:
        return False
    other_kind = provider_template_layout_kind(same_business[0].template_id)
    return other_kind in {"Full", "Compact"} and other_kind != kind


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
            if supports_business_action(definition, actions[0], "2x4"):
                yield (
                    TemplatePlanActionAssignment(
                        actionId=actions[0].action_id,
                        consumer="business-template",
                        businessPosition=slot.position,
                    ),
                )
        return
    # effective_ids 今天与逐模板检查完全等价：CompactAction@1 与
    # PlaylistCompactAction@1 的必填 icon 签名相同（语义标签为空），
    # 因此跨 action×template 的并集只会放大、不会放行原本会被拒绝的计划。
    effective_ids = {
        f"{_root_action_template(layout.layout_id, action, template)}@1"
        for action in actions
        for template in layout.action_templates
    }
    if any(
        not _action_template_has_complete_signature(template_id, task, registry)
        for template_id in effective_ids
    ):
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
            assignments.append(
                TemplatePlanActionAssignment(
                    actionId=action.action_id,
                    consumer="root-action",
                    businessPosition=position,
                    actionTemplateId=(
                        f"{_root_action_template(layout.layout_id, action, template)}@1"
                    ),
                )
            )
        if len(assignments) == len(actions):
            yield tuple(assignments)
        # 共享操作区保持输入事件顺序；只有成对按钮需要按业务重排。
        if all(owner is None for owner in layout.action_owners):
            break


def _root_action_template(layout_id: str, action: ActionBinding, template: str) -> str:
    """歌单专用动作在 Planner 阶段确定，贯穿计划、提示词与编译契约。"""
    if (
        layout_id == "WideHalfTwoCompactLayout"
        and template == "CompactAction"
        and action.event_id == "event.open.music.daily"
    ):
        return "PlaylistCompactAction"
    return template


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
            if _parameter_value_kind(name, properties.get(name, {})) != "asset-source":
                continue
            required_tags = set(definition.asset_parameter_semantic_tags.get(name, ()))
            if not any(required_tags.issubset(_asset_semantic_tags(asset)) for asset in assets):
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
