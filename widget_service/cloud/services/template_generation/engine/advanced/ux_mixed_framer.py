"""Deterministic framing repairs that are exclusive to the new UX mixed entry."""

from __future__ import annotations

import json
from typing import Any

from models.generation import WidgetSize
from services.template_generation.engine.advanced.models import UX_LAYOUT_COMPONENT_IDS
from services.template_generation.engine.cardplan.parser import (
    ParsedCall,
    normalize_hybrid_source,
    parse_hybrid_card,
    parse_ux_layout_card,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
)

_UX_ACTION_COMPONENTS = frozenset({"PillAction", "IconAction", "ActionTile"})


def frame_ux_layout_root_children(
    source: str,
    *,
    size: WidgetSize,
    registry: CardPlanRegistry,
    allowed_layout_ids: tuple[str, ...] | None = None,
) -> tuple[str, bool]:
    """Frame overflow for the direct layout-root protocol without touching Action."""
    normalized = normalize_hybrid_source(source)
    normalized, trailing_delimiters_repaired = _close_trailing_delimiters(normalized)
    try:
        root = parse_ux_layout_card(normalized)
    except TerseDslNested2ConversionError:
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
        trailing_delimiters_repaired = True
    layout_id = _layout_id(root)
    maximum = registry.require_ux_layout_component(layout_id).max_children_by_size[size]
    actions = tuple(
        child
        for child in root.children
        if child.kind == "component" and child.name in _UX_ACTION_COMPONENTS
    )
    content = tuple(child for child in root.children if child not in actions)
    if len(content) <= maximum:
        return normalized, trailing_delimiters_repaired
    if layout_id in {"SingleFocusLayout", "HeroActionLayout"}:
        expanded_layout_id = (
            "HeroSupportActionLayout" if actions else "HeroSupportLayout"
        )
        expanded_layout = registry.require_ux_layout_component(expanded_layout_id)
        expanded_maximum = expanded_layout.max_children_by_size[size]
        if (
            (allowed_layout_ids is None or expanded_layout_id in allowed_layout_ids)
            and len(content) <= expanded_maximum
        ):
            framed_root = ParsedCall(
                kind="template",
                name=expanded_layout_id + "@1",
                values=({},),
                children=(*content, *actions),
                span=root.span,
            )
            return _serialize_call(framed_root) + ";", True
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
    overflow = content[max(maximum - 1, 0) :]
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
    arguments = _split_top_level_calls(stripped[open_index + 1 : -1])
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
    except TerseDslNested2ConversionError:
        return None
    if allowed_layout_ids is not None and _layout_id(layout) not in allowed_layout_ids:
        return None
    actions = tuple(
        child
        for child in layout.children
        if child.kind == "component" and child.name in _UX_ACTION_COMPONENTS
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
        except TerseDslNested2ConversionError:
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
                except TerseDslNested2ConversionError:
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
        if child.kind == "component" and child.name in _UX_ACTION_COMPONENTS
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
    except TerseDslNested2ConversionError:
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


def frame_ux_layout_children(
    source: str,
    *,
    size: WidgetSize,
    registry: CardPlanRegistry,
) -> tuple[str, bool]:
    """Group layout overflow into a standard Column without changing any facts."""
    normalized = normalize_hybrid_source(source)
    normalized, trailing_delimiters_repaired = _close_trailing_delimiters(normalized)
    root = parse_hybrid_card(normalized)
    layout = root.children[0]
    if not (
        (layout.kind == "component" and layout.name in UX_LAYOUT_COMPONENT_IDS)
        or (layout.kind == "template" and _layout_id(layout) in UX_LAYOUT_COMPONENT_IDS)
    ):
        return normalized, trailing_delimiters_repaired
    maximum = registry.require_ux_layout_component(_layout_id(layout)).max_children_by_size[size]
    if len(layout.children) <= maximum:
        return normalized, trailing_delimiters_repaired
    retained = layout.children[: max(maximum - 1, 0)]
    overflow = layout.children[max(maximum - 1, 0) :]
    grouped = ParsedCall(
        kind="component",
        name="Column",
        values=("section",),
        children=overflow,
        span=layout.span,
    )
    framed_layout = ParsedCall(
        kind=layout.kind,
        name=layout.name,
        values=layout.values,
        children=(*retained, grouped),
        span=layout.span,
    )
    framed_root = ParsedCall(
        kind=root.kind,
        name=root.name,
        values=root.values,
        children=(framed_layout,),
        span=root.span,
    )
    return _serialize_call(framed_root) + ";", True


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
