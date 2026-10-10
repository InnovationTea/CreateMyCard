# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Executable data-binding contracts for semantic Compact components."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

BindingMode = Literal["path", "expression"]
SchemaTypeResolver = Callable[[str], str | None]

_PATH = "path"
_EXPRESSION = "expression"
_SCALAR_TYPES = frozenset({"string", "integer", "number"})
_STRING_TYPES = frozenset({"string"})
_PROGRESS_TYPES = frozenset({"string", "integer", "number"})


@dataclass(frozen=True)
class CompactPropBindingContract:
    """Binding modes and direct PathBinding source types accepted by one Prop."""

    modes: frozenset[BindingMode]
    path_types: frozenset[str]


def _display_contract() -> CompactPropBindingContract:
    return CompactPropBindingContract(
        modes=frozenset({_PATH, _EXPRESSION}),
        path_types=_SCALAR_TYPES,
    )


def _string_contract() -> CompactPropBindingContract:
    return CompactPropBindingContract(
        modes=frozenset({_PATH, _EXPRESSION}),
        path_types=_STRING_TYPES,
    )


def _progress_contract() -> CompactPropBindingContract:
    return CompactPropBindingContract(
        modes=frozenset({_PATH}),
        path_types=_PROGRESS_TYPES,
    )


DISPLAY_BINDING = _display_contract()
STRING_BINDING = _string_contract()
PROGRESS_BINDING = _progress_contract()

# This registry is the executable source of truth for semantic Compact Props.
# It intentionally does not include Row/Column/Stack, converter-internal Text,
# or onClick args. Event argument bindings remain governed by event schemas.
COMPACT_COMPONENT_BINDING_CONTRACTS: dict[
    str,
    dict[str, CompactPropBindingContract],
] = {
    "SingleLineTitle": {"title": DISPLAY_BINDING},
    "DoubleLineTitle": {
        "title": DISPLAY_BINDING,
        "secondaryInfo": DISPLAY_BINDING,
    },
    "Badge": {"value": DISPLAY_BINDING},
    "EmphasizedData": {
        "value": DISPLAY_BINDING,
        "unit": STRING_BINDING,
    },
    "EmphasisText": {
        "mainText": DISPLAY_BINDING,
        "secondaryText": DISPLAY_BINDING,
    },
    "SecondaryBody": {"items[].value": DISPLAY_BINDING},
    "DataDisplay": {"value": DISPLAY_BINDING},
    "InfoBlock": {
        "primaryText": DISPLAY_BINDING,
        "secondaryText": DISPLAY_BINDING,
    },
    "TableText": {
        "items[].label": DISPLAY_BINDING,
        "items[].value": DISPLAY_BINDING,
    },
    "SummaryList": {"items[]": DISPLAY_BINDING},
    "ProgressCircle": {"externalText": PROGRESS_BINDING},
    "ProgressLine2": {
        "value": PROGRESS_BINDING,
        "displayValue": DISPLAY_BINDING,
        "unit": STRING_BINDING,
    },
    "H_BarChart": {"items[].valueUnit": DISPLAY_BINDING},
    "ProgressCircleSingle": {
        "value": PROGRESS_BINDING,
        "displayValue": DISPLAY_BINDING,
        "label": DISPLAY_BINDING,
        "secondaryLabel": DISPLAY_BINDING,
    },
    "NumericRatioStack": {
        "items[].value": DISPLAY_BINDING,
    },
    "EventCard": {
        "title": DISPLAY_BINDING,
        "time": DISPLAY_BINDING,
        "location": DISPLAY_BINDING,
        "items[].title": DISPLAY_BINDING,
        "items[].time": DISPLAY_BINDING,
        "items[].location": DISPLAY_BINDING,
    },
    "PillButton": {},
    "CircleButton": {},
    "TopTextBottomValue": {"items[].value": DISPLAY_BINDING},
    "TextBlock": {"items[].value": DISPLAY_BINDING},
    "CardButton": {},
}


def collect_compact_component_binding_errors(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    *,
    schema_type_resolver: SchemaTypeResolver | None = None,
) -> list[str]:
    """Return binding-contract errors for one unexpanded semantic component."""
    contracts = COMPACT_COMPONENT_BINDING_CONTRACTS.get(component_type)
    if contracts is None:
        return []

    errors: list[str] = []
    for prop_name, value in props.items():
        if prop_name == "onClick":
            continue
        for prop_path, mode, binding_path in _walk_bindings(value, prop_name):
            contract = contracts.get(prop_path)
            location = f"component {component_id}.props.{prop_path}"
            if contract is None:
                errors.append(
                    f"{location}: {component_type}.{prop_path} only accepts a static value."
                )
                continue
            if mode not in contract.modes:
                errors.append(
                    f"{location}: {component_type}.{prop_path} does not accept {mode} bindings."
                )
                continue
            if mode != _PATH or schema_type_resolver is None:
                continue
            schema_type = schema_type_resolver(binding_path)
            if schema_type is None or schema_type in contract.path_types:
                continue
            expected = ", ".join(sorted(contract.path_types))
            errors.append(
                f"{location}: PathBinding {binding_path} has schema type {schema_type}; "
                f"expected one of {expected}."
            )
    return errors


def _walk_bindings(
    value: Any,
    prop_path: str,
) -> Iterator[tuple[str, BindingMode, str]]:
    binding_path = _path_binding(value)
    if binding_path is not None:
        yield prop_path, _PATH, binding_path
        return
    if _is_expression(value):
        yield prop_path, _EXPRESSION, ""
        return
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_bindings(child, f"{prop_path}.{key}")
        return
    if isinstance(value, list):
        item_path = f"{prop_path}[]"
        for child in value:
            yield from _walk_bindings(child, item_path)


def _path_binding(value: Any) -> str | None:
    if not isinstance(value, dict) or set(value) != {"path"}:
        return None
    path = value.get("path")
    if isinstance(path, str) and path.startswith("/"):
        return path
    return None


def _is_expression(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return stripped.startswith("{{") and stripped.endswith("}}")
