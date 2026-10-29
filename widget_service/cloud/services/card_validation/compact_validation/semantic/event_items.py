"""EventCard 详情点击的有效候选、记录归属与重复入口检查。"""

from __future__ import annotations

from typing import Any

from services.card_validation.binding_validator import BindingValidator
from services.compact_action_instances import (
    event_card_detail_action,
    event_card_item_handlers,
    plan_action_handlers,
)
from services.compact_dsl_a2ui_converter import ComponentRow
from services.event_matching import event_handlers_match

from ..diagnostics import CompactDiagnostic, emit_error


def collect_event_item_errors(
    components: list[ComponentRow],
    task: dict[str, Any],
    errors: list[str],
) -> None:
    """仅新增条目点击进入此规则；历史无点击日程与独立按钮保持原判定。"""
    details: list[dict[str, Any]] = []
    for reference, handler in plan_action_handlers(task).items():
        if event_card_detail_action(task, reference):
            details.append(handler)
    existing_handlers: list[dict[str, Any]] = []
    for component in components:
        handlers = component.props.get("onClick")
        if isinstance(handlers, list):
            existing_handlers.extend(h for h in handlers if isinstance(h, dict))
    for component in components:
        if component.component_type != "EventCard":
            continue
        items = component.props.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            handlers = event_card_item_handlers({"items": [item]})
            if len(handlers) != 1:
                continue  # handler 形状仍由共享组件合同及展开后语法检查裁决。
            handler = handlers[0]
            display = {key: item.get(key) for key in ("title", "time", "location")}
            display_slots = BindingValidator._array_item_slots(
                BindingValidator._value_references(display),
            )
            event_slots = BindingValidator._array_item_slots(
                BindingValidator._value_references(handler.get("args")),
            )
            allowed = any(event_handlers_match(handler, detail) for detail in details)
            if not allowed or len(display_slots) != 1 or event_slots != display_slots:
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_EVENT_ITEM_MISMATCH",
                        validation_class="semantic",
                        category="effective",
                        message="日程条目的详情点击未匹配同一记录的合法候选。",
                        expected={
                            "recordPaths": [
                                BindingValidator._slot_text(slot) for slot in sorted(display_slots)
                            ],
                            "detailCandidates": details,
                        },
                        actual=handler,
                        component_id=component.component_id,
                        property_path=f"/items/{index}/onClick",
                        legacy_message=(
                            f"component {component.component_id}.items[{index}].onClick: "
                            "must match an allowed calendar detail handler for the same displayed "
                            "array record; copy its complete call and args."
                        ),
                    ),
                )
            if any(event_handlers_match(handler, other) for other in existing_handlers):
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_EVENT_ITEM_DUPLICATE",
                        validation_class="semantic",
                        category="effective",
                        message="日程条目详情已被其它点击区域重复承载。",
                        expected={"detailEntryCount": 1},
                        actual=handler,
                        component_id=component.component_id,
                        property_path=f"/items/{index}/onClick",
                        legacy_message=(
                            f"component {component.component_id}.items[{index}].onClick: "
                            "duplicate detail entry; retain the item click "
                            "without a duplicate button."
                        ),
                    ),
                )
            existing_handlers.append(handler)
