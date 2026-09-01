"""Deterministic framing repairs that are exclusive to the new UX mixed entry."""

from __future__ import annotations

import json
import re
from typing import Any

from models.generation import WidgetSize
from services.template_generation.engine.cardplan.parser import (
    ParsedCall,
    normalize_hybrid_source,
    parse_ux_layout_card,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import (
    TerselConversionError,
)

_UX_ACTION_COMPONENTS = frozenset(
    {"PillAction", "IconAction", "LargeIconAction", "ActionTile"}
)
_UX_ACTION_TEMPLATE_IDS = frozenset(
    {"PillAction@1", "IconAction@1", "LargeIconAction@1"}
)
_UNQUOTED_TEMPLATE_CALL = re.compile(
    r"Template(\s*\(\s*)([A-Za-z][A-Za-z0-9_.-]*@[A-Za-z0-9_.-]+)(\s*,)"
)


def _is_ux_action_call(call: ParsedCall) -> bool:
    return (
        call.kind == "component" and call.name in _UX_ACTION_COMPONENTS
    ) or (call.kind == "template" and call.name in _UX_ACTION_TEMPLATE_IDS)


def frame_ux_layout_root_children(
    source: str,
    *,
    size: WidgetSize,
    registry: CardPlanRegistry,
    allowed_layout_ids: tuple[str, ...] | None = None,
) -> tuple[str, bool]:
    """Frame overflow for the direct layout-root protocol without touching Action."""
    normalized = normalize_hybrid_source(source)
    normalized, template_ids_repaired = _quote_unquoted_template_ids(normalized)
    normalized, trailing_delimiters_repaired = _close_trailing_delimiters(normalized)
    framing_repaired = template_ids_repaired or trailing_delimiters_repaired
    try:
        root = parse_ux_layout_card(normalized)
    except TerselConversionError:
        framed = _reparent_wrapped_layout_call(
            normalized,
            registry,
            allowed_layout_ids,
        )
        if framed is None:
            framed = _select_single_top_level_layout_call(
                normalized,
                registry,
                allowed_layout_ids,
            )
        if framed is None:
            raise
        normalized = framed
        root = parse_ux_layout_card(normalized)
        framing_repaired = True
    layout_id = _layout_id(root)
    layout = registry.require_ux_layout_component(layout_id)
    if size not in layout.supported_card_sizes:
        raise TerselConversionError("UX Layout does not support the target card size.")
    maximum = layout.max_children_by_size[size]
    actions = tuple(
        child
        for child in root.children
        if _is_ux_action_call(child)
    )
    content = tuple(child for child in root.children if child not in actions)
    if len(content) <= maximum:
        return normalized, framing_repaired
    business_children = tuple(
        child
        for child in content
        if _is_ux_business_call(child, registry)
    )
    if len(business_children) >= maximum:
        framed_root = ParsedCall(
            kind=root.kind,
            name=root.name,
            values=root.values,
            children=(*business_children[:maximum], *actions),
            span=root.span,
        )
        return _serialize_call(framed_root) + ";", True
    retained = content[: max(maximum - 1, 0)]
    overflow = content[slice(max(maximum - 1, 0), None)]
    grouped = ParsedCall(
        kind="component",
        name="Column",
        values=("section",),
        children=overflow,
        span=root.span,
    )
    framed_root = ParsedCall(
        kind=root.kind,
        name=root.name,
        values=root.values,
        children=(*retained, grouped, *actions),
        span=root.span,
    )
    return _serialize_call(framed_root) + ";", True


def _quote_unquoted_template_ids(source: str) -> tuple[str, bool]:
    """Quote a bare first Template argument without touching string literals."""
    parts: list[str] = []
    cursor = 0
    index = 0
    in_string: str | None = None
    escaped = False
    repaired = False
    while index < len(source):
        char = source[index]
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            index += 1
            continue
        if char in {'"', "'"}:
            in_string = char
            index += 1
            continue
        previous_is_identifier = index > 0 and (
            source[index - 1].isalnum() or source[index - 1] == "_"
        )
        if previous_is_identifier:
            index += 1
            continue
        match = _UNQUOTED_TEMPLATE_CALL.match(source, index)
        if match is None:
            index += 1
            continue
        parts.append(source[cursor:index])
        parts.append(
            f'Template{match.group(1)}"{match.group(2)}"{match.group(3)}'
        )
        index = match.end()
        cursor = index
        repaired = True
    if not repaired:
        return source, False
    parts.append(source[cursor:])
    return "".join(parts), True


def _reparent_wrapped_layout_call(
    source: str,
    registry: CardPlanRegistry,
    allowed_layout_ids: tuple[str, ...] | None,
) -> str | None:
    """Move an outer direct business leaf into its sole nested approved Layout."""
    stripped = source.strip().rstrip(";").strip()
    open_index = stripped.find("(")
    if open_index <= 0 or not stripped.endswith(")"):
        return None
    component_id = stripped[:open_index].strip()
    capability = registry.ux_business_components.get(component_id)
    if capability is None or capability.implementation != "terse-dsl":
        return None
    arguments = _split_top_level_calls(stripped[slice(open_index + 1, -1)])
    if len(arguments) != 2:
        return None
    try:
        parameters = json.loads(arguments[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(parameters, dict):
        return None
    try:
        layout = parse_ux_layout_card(arguments[1].strip() + ";")
    except TerselConversionError:
        return None
    if allowed_layout_ids is not None and _layout_id(layout) not in allowed_layout_ids:
        return None
    actions = tuple(
        child
        for child in layout.children
        if _is_ux_action_call(child)
    )
    business = ParsedCall(
        kind="component",
        name=component_id,
        values=(parameters,),
        children=(),
        span=layout.span,
    )
    framed = ParsedCall(
        kind=layout.kind,
        name=layout.name,
        values=layout.values,
        children=(business, *actions),
        span=layout.span,
    )
    return _serialize_call(framed) + ";"


def _select_single_top_level_layout_call(
    source: str,
    registry: CardPlanRegistry,
    allowed_layout_ids: tuple[str, ...] | None,
) -> str | None:
    """Select one valid layout when the model prefixes or suffixes sibling roots."""
    layout_candidates: list[ParsedCall] = []
    business_candidates: list[ParsedCall] = []
    for part in _split_top_level_calls(source.rstrip(";")):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            root = parse_ux_layout_card(candidate + ";")
        except TerselConversionError:
            if candidate.startswith("Template("):
                template = _parse_single_wrapped_child(candidate)
                if template is not None and _is_ux_business_call(template, registry):
                    business_candidates.append(template)
                continue
            for component_id, capability in registry.ux_business_components.items():
                if capability.implementation != "terse-dsl" or not candidate.startswith(
                    component_id + "("
                ):
                    continue
                try:
                    wrapper = parse_ux_layout_card(
                        "SingleFocusLayout(" + candidate + ");"
                    )
                except TerselConversionError:
                    break
                if len(wrapper.children) == 1:
                    business_candidates.append(wrapper.children[0])
                break
            continue
        if allowed_layout_ids is None or _layout_id(root) in allowed_layout_ids:
            layout_candidates.append(root)
    if len(layout_candidates) != 1:
        return None
    layout = layout_candidates[0]
    existing_business = tuple(
        child for child in layout.children if _is_ux_business_call(child, registry)
    )
    if existing_business or len(business_candidates) != 1:
        return _serialize_call(layout) + ";"
    actions = tuple(
        child
        for child in layout.children
        if _is_ux_action_call(child)
    )
    framed = ParsedCall(
        kind=layout.kind,
        name=layout.name,
        values=layout.values,
        children=(business_candidates[0], *actions),
        span=layout.span,
    )
    return _serialize_call(framed) + ";"


def _parse_single_wrapped_child(source: str) -> ParsedCall | None:
    try:
        wrapper = parse_ux_layout_card("SingleFocusLayout(" + source + ");")
    except TerselConversionError:
        return None
    if len(wrapper.children) != 1:
        return None
    return wrapper.children[0]


def _is_ux_business_call(call: ParsedCall, registry: CardPlanRegistry) -> bool:
    if call.kind == "template":
        if call.name in registry.provider_template_ids:
            return True
        return any(
            component.local_template_ids
            and call.name == component.local_template_ids[0]
            for component in registry.ux_business_components.values()
        )
    return call.name in registry.ux_business_components


def _split_top_level_calls(source: str) -> tuple[str, ...]:
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    in_string: str | None = None
    escaped = False
    for index, char in enumerate(source):
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {'"', "'"}:
            in_string = char
        elif char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif char == "," and not stack:
            parts.append(source[start:index])
            start = index + 1
    parts.append(source[start:])
    return tuple(parts)


def _close_trailing_delimiters(source: str) -> tuple[str, bool]:
    """Close a small, typed EOF-only delimiter suffix; never repair crossed input."""
    stripped = source.strip()
    if not stripped.endswith(";"):
        return source, False
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    stack: list[str] = []
    in_string: str | None = None
    escaped = False
    for char in stripped[:-1]:
        if in_string is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {'"', "'"}:
            in_string = char
        elif char in pairs:
            stack.append(pairs[char])
        elif char in closers:
            if not stack or stack[-1] != char:
                return source, False
            stack.pop()
    if in_string is not None or not stack or len(stack) > 4:
        return source, False
    return stripped[:-1] + "".join(reversed(stack)) + ";", True


def _serialize_call(call: ParsedCall) -> str:
    values: list[str]
    if call.kind == "template":
        if call.name == "card@1":
            values = [_literal(call.name), _literal(call.values[0])]
        else:
            values = [_literal(call.name), *(_literal(value) for value in call.values)]
        values.extend(_serialize_call(child) for child in call.children)
        return f"Template({', '.join(values)})"
    values = [_literal(value) for value in call.values]
    values.extend(_serialize_call(child) for child in call.children)
    return f"{call.name}({', '.join(values)})"


def _layout_id(call: ParsedCall) -> str:
    return call.name.removesuffix("@1") if call.kind == "template" else call.name


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
