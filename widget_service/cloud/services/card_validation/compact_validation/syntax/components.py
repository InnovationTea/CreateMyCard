# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：syntax.components。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.compact_dsl_a2ui_converter import ComponentRow

_NON_EMPTY_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})


@dataclass(frozen=True)
class OnClickShape:
    handler: dict[str, Any] | None = None


def _collect_component_parent_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child: dict[str, str] = {}
    for component in components:
        children_seen: set[str] = set()
        for child_id in component.children:
            if child_id in children_seen:
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_COMPONENT_DUPLICATE_CHILD",
                        validation_class="syntax",
                        category="component",
                        message=f"父组件 {component.component_id} 重复引用子组件 {child_id}。",
                        expected={"uniqueChildReferences": True},
                        actual={"childId": child_id, "children": list(component.children)},
                        component_id=component.component_id,
                        legacy_message=f"component {component.component_id}.children references "
                        f"{child_id} more than once.",
                    ),
                )
                continue
            children_seen.add(child_id)
            existing_parent = parent_by_child.get(child_id)
            if existing_parent is None:
                parent_by_child[child_id] = component.component_id
                continue
            if existing_parent == component.component_id:
                continue
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_COMPONENT_MULTIPLE_PARENTS",
                    validation_class="syntax",
                    category="component",
                    message=f"组件 {child_id} 被多个父组件引用。",
                    expected={"parentCount": 1},
                    actual={"parents": [existing_parent, component.component_id]},
                    component_id=child_id,
                    legacy_message=f"component {child_id} has multiple parents: {existing_parent} "
                    f"and {component.component_id}. Each component may appear in "
                    "exactly one parent children list.",
                ),
            )


def _collect_container_errors(
    component: ComponentRow,
    errors: list[str],
) -> None:
    if component.component_type not in _NON_EMPTY_CONTAINER_TYPES:
        return
    if component.children:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_COMPONENT_EMPTY_CONTAINER",
            validation_class="syntax",
            category="component",
            message=(
                f"组件 {component.component_id} 是没有子节点的 {component.component_type} 容器。"
            ),
            expected={"minimumChildren": 1, "emptySpacerContainerAllowed": False},
            actual={"childCount": 0},
            component_id=component.component_id,
            legacy_message=f"component {component.component_id}: "
            f"{component.component_type}.children "
            "must be non-empty; use parent itemMargin, padding, or layout alignment "
            "instead of an empty spacer container.",
        ),
    )


def _collect_action_unit_errors(
    component: ComponentRow,
    errors: list[str],
) -> None:
    location = f"component {component.component_id}"
    state = component.props.get("state")
    if state not in {"capsule", "icon-round"}:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_ACTION_STATE_INVALID",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的 ActionUnit.state 不在允许集合内。",
                expected={"states": ["capsule", "icon-round"]},
                actual=state,
                component_id=component.component_id,
                property_path="/state",
                legacy_message=f'{location}: ActionUnit.state must be "capsule" or "icon-round".',
            ),
        )
        return
    if component.children:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_ACTION_CHILDREN_FORBIDDEN",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的 ActionUnit 声明了不允许的子组件。",
                expected={"childrenAllowed": False},
                actual=list(component.children),
                component_id=component.component_id,
                legacy_message=f"{location}: ActionUnit must not declare children.",
            ),
        )
    if "onClick" not in component.props:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_ACTION_CLICK_REQUIRED",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的 ActionUnit 缺少点击事件。",
                expected={"onClickRequired": True},
                actual={"onClickPresent": False},
                component_id=component.component_id,
                legacy_message=f"{location}: ActionUnit.onClick is required.",
            ),
        )
    if state == "capsule":
        _collect_required_non_empty_string(
            component.props.get("label"),
            f"{location}: capsule ActionUnit.label",
            errors,
            component_id=component.component_id,
            property_path="/label",
        )
        icon = component.props.get("icon")
        if icon is not None and (not isinstance(icon, str) or not icon.strip()):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_ACTION_ICON_INVALID",
                    validation_class="syntax",
                    category="component",
                    message=f"组件 {component.component_id} 的胶囊动作 icon 不是有效的非空字符串。",
                    expected={"type": "string", "nonBlank": True},
                    actual=icon,
                    component_id=component.component_id,
                    property_path="/icon",
                    legacy_message=f"{location}: capsule ActionUnit.icon must be "
                    "a non-empty string when provided.",
                ),
            )
        return
    _collect_required_non_empty_string(
        component.props.get("icon"),
        f"{location}: icon-round ActionUnit.icon",
        errors,
        component_id=component.component_id,
        property_path="/icon",
    )
    if "label" in component.props:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_ACTION_ICON_LABEL_FORBIDDEN",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的 icon-round 动作声明了不允许的 label。",
                expected={"labelAllowed": False},
                actual=component.props.get("label"),
                component_id=component.component_id,
                property_path="/label",
                legacy_message=f"{location}: icon-round ActionUnit must not declare label.",
            ),
        )


def _collect_required_non_empty_string(
    value: Any,
    field: str,
    errors: list[str],
    *,
    component_id: str | None = None,
    property_path: str | None = None,
) -> None:
    if isinstance(value, str) and value.strip():
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_COMPONENT_REQUIRED_STRING",
            validation_class="syntax",
            category="component",
            message=f"{field} 不是有效的非空字符串。",
            expected={"type": "string", "nonBlank": True},
            actual=value,
            component_id=component_id,
            property_path=property_path,
            legacy_message=f"{field} must be a non-empty string.",
        ),
    )


def _collect_on_click_structure_errors(
    component: ComponentRow,
    errors: list[str],
) -> OnClickShape:
    if "onClick" not in component.props:
        return OnClickShape()
    location = f"component {component.component_id}.props.onClick"
    handlers = component.props.get("onClick")
    if not isinstance(handlers, list) or len(handlers) != 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CLICK_HANDLER_COUNT",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的 onClick 未提供恰好一个 handler。",
                expected={"type": "array", "handlerCount": 1},
                actual=handlers,
                component_id=component.component_id,
                property_path="/onClick",
                legacy_message=f"{location}: onClick must contain exactly one handler.",
            ),
        )
        return OnClickShape()
    handler = handlers[0]
    if not isinstance(handler, dict):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CLICK_HANDLER_OBJECT",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的点击 handler 不是对象。",
                expected={"type": "object"},
                actual=handler,
                component_id=component.component_id,
                property_path="/onClick/0",
                legacy_message=f"{location}[0]: handler must be an object.",
            ),
        )
        return OnClickShape()
    if set(handler) != {"call", "args"}:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CLICK_HANDLER_FIELDS",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的点击 handler 字段集合不合法。",
                expected={"exactFields": ["call", "args"]},
                actual={"fields": list(handler)},
                component_id=component.component_id,
                property_path="/onClick/0",
                legacy_message=f"{location}[0]: handler must contain only call and args.",
            ),
        )
        return OnClickShape()
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not call.strip():
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CLICK_CALL_INVALID",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的点击 call 不是有效的非空字符串。",
                expected={"type": "string", "nonBlank": True},
                actual=call,
                component_id=component.component_id,
                property_path="/onClick/0/call",
                legacy_message=f"{location}[0].call: call must be a non-empty string.",
            ),
        )
        return OnClickShape()
    if not isinstance(args, dict):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CLICK_ARGS_INVALID",
                validation_class="syntax",
                category="component",
                message=f"组件 {component.component_id} 的点击 args 不是对象。",
                expected={"type": "object"},
                actual=args,
                component_id=component.component_id,
                property_path="/onClick/0/args",
                legacy_message=f"{location}[0].args: args must be an object.",
            ),
        )
        return OnClickShape()
    return OnClickShape(handler)
