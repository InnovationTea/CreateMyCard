# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：syntax.components。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.card_validation.compact_validation.constants import _NON_EMPTY_CONTAINER_TYPES
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.compact_dsl_a2ui_converter import (
    MODEL_COMPACT_INPUT_COMPONENT_TYPES,
    ComponentRow,
)

from ..diagnostics import DiagnosticCollector


def _collect_component_parent_errors(components: list[ComponentRow], errors: list[str]) -> None:
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
                        legacy_message=(
                            f"component {component.component_id}.children references "
                            f"{child_id} more than once."
                        ),
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
                    legacy_message=(
                        f"component {child_id} has multiple parents: {existing_parent} and "
                        f"{component.component_id}. Each component may appear in exactly "
                        f"one parent children list."
                    ),
                ),
            )


def _collect_container_errors(component: ComponentRow, errors: list[str]) -> None:
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
            legacy_message=(
                f"component {component.component_id}: {component.component_type}.children "
                f"must be non-empty; use parent itemMargin, padding, or layout alignment "
                f"instead of an empty spacer container."
            ),
        ),
    )


def _collect_on_click_structure_errors(component: ComponentRow, errors: list[str]) -> OnClickShape:
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


@dataclass(frozen=True)
class OnClickShape:
    handler: dict[str, Any] | None = None


def collect_model_component_errors(components: list[ComponentRow]) -> DiagnosticCollector:
    from services.generation_content_policy import (
        STATIC_COMPONENTS,
        STATIC_SUPPORT_COMPONENTS,
        current_content_policy,
    )

    allowed_types = MODEL_COMPACT_INPUT_COMPONENT_TYPES
    if current_content_policy().is_static:
        allowed_types = STATIC_COMPONENTS | STATIC_SUPPORT_COMPONENTS | {"Layout"}
    errors = DiagnosticCollector()
    for row in components:
        if row.component_type in allowed_types:
            continue
        legacy = (
            f"component {row.component_id}: {row.component_type} is converter-internal and "
            f"cannot be generated directly; use a semantic Compact component."
        )
        message = f"模型直接输出了仅供转换器内部使用的 {row.component_type} 组件。"
        if current_content_policy().is_static:
            message = (
                f"开域正文不允许 {row.component_type}；"
                "使用静态文本列表、单行列表、对比、强调文本及标题。"
            )
            legacy = message
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_MODEL_COMPONENT_FORBIDDEN",
                validation_class="syntax",
                category="component",
                message=message,
                legacy_message=legacy,
                expected={"allowedComponentTypes": sorted(allowed_types)},
                actual=row.component_type,
                component_id=row.component_id,
            ),
        )
    return errors
