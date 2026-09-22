from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .bindings import (
    BINDABLE_PROP_TYPES,
    collect_display_prop_type_errors,
    data_binding_ids,
    indexed_value_template_tokens,
)
from ..exceptions import ValidationError
from ..parser.jsx_ast import JSXElement


@dataclass(frozen=True, slots=True)
class Contract:
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    enums: dict[str, frozenset[object]] | None = None
    required_one_of: frozenset[str] = frozenset()


def contract(required=(), optional=(), required_one_of=(), **enums) -> Contract:
    optional_props = frozenset(optional)
    if "dataIds" in optional_props:
        optional_props |= {"dataValueMaps"}
    return Contract(
        frozenset(required),
        optional_props,
        {key: frozenset(value) for key, value in enums.items()},
        frozenset(required_one_of),
    )


CONTRACTS = {
    "Card": contract(optional=("size", "appearance", "background", "padding", "direction", "gap", "align", "justify")),
    "Stack": contract(
        optional=(
            "direction",
            "gap",
            "align",
            "justify",
            "wrap",
            "flex",
            "basis",
            "width",
            "minWidth",
            "height",
            "minHeight",
            "mt",
            "mb",
            "ml",
            "mr",
            "position",
            "top",
            "right",
            "bottom",
            "left",
            "alignSelf",
            "surface",
        ),
        direction=("column", "row"),
        align=("stretch", "flex-start", "center", "flex-end", "start", "end", "top", "bottom", "baseline"),
        justify=(
            "start",
            "center",
            "end",
            "between",
            "flex-start",
            "flex-end",
            "space-between",
            "space-around",
            "space-evenly",
        ),
        position=("relative", "absolute"),
        surface=("backplate",),
    ),
    "Grid": contract(
        optional=(
            "columns",
            "rows",
            "gap",
            "rowGap",
            "columnGap",
            "flex",
            "basis",
            "width",
            "minWidth",
            "height",
            "minHeight",
            "align",
            "justify",
            "mt",
            "mb",
        )
    ),
    "Icon": contract(optional=("name", "src", "size", "alt", "decorative")),
    "AppIcon": contract(optional=("name", "src", "alt")),
    "WeatherIcon": contract(optional=("name", "src", "alt")),
    "SingleLineTitle": contract(required=("title",), optional=("titleTemplate", "dataIds")),
    "DoubleLineTitle": contract(
        required=("title", "secondaryInfo"),
        optional=("titleTemplate", "secondaryInfoTemplate", "dataIds"),
    ),
    "Badge": contract(
        required=("value",),
        optional=("color", "dataIds"),
        color=("blue", "orange", "green", "red", "purple", "cyan", "pink"),
    ),
    "DataDisplay": contract(required=("label", "value", "supportingText"), optional=("dataIds",)),
    "InfoBlock": contract(
        required=("primaryText", "secondaryText"),
        optional=("primaryTextTemplate", "secondaryTextTemplate", "unit", "visual", "dataIds"),
    ),
    "TopTextBottomValue": contract(required=("items",)),
    "TableText": contract(required=("items",)),
    "TextBlock": contract(required=("items",)),
    "EmphasizedData": contract(optional=("unit", "dataIds"), required_one_of=("value", "items")),
    "EmphasisText": contract(
        required=("mainText",),
        optional=("secondaryText", "secondaryTextTemplate", "dataIds"),
    ),
    "SecondaryBody": contract(required=("items",), optional=("separator",)),
    "WeatherSummaryCard": contract(
        required=("city", "temperature", "condition", "airQuality", "high", "low", "icon"), optional=("ariaLabel",)
    ),
    "SecondaryBodyCard": contract(required=("title", "lines"), optional=("value",)),
    "ProgressLine1": contract(
        required=("currentValue", "totalValue", "leftLabel", "rightLabel"),
        optional=("color", "dataIds"),
        color=("blue", "orange", "yellow", "purple", "red", "green", "pink"),
    ),
    "ProgressLine2": contract(
        required=("currentValue", "totalValue"),
        optional=("mode", "barColor", "value", "unit", "items", "dataIds"),
        mode=("light", "dark"),
    ),
    "ProgressLine2WithData": contract(
        required=("currentValue", "totalValue", "value"), optional=("mode", "barColor", "unit", "items", "dataIds")
    ),
    "H_BarChart": contract(required=("items",), optional=("mode",), mode=("light", "dark")),
    "Gauge": contract(required=("value", "label"), optional=("min", "max", "mode", "dataIds"), mode=("light", "dark")),
    "ProgressRing": contract(
        required=("value", "icon"),
        optional=(
            "size",
            "strokeWidth",
            "trackColor",
            "barColor",
            "iconSize",
            "visibleOverflow",
            "precision",
            "appearance",
        ),
    ),
    "ProgressCircleSingle": contract(
        required=("value", "icon", "label"),
        optional=(
            "displayValue", "secondaryLabel", "ariaLabel", "appearance",
            "size", "trackColor", "barColor", "dataIds",
        ),
        size=("compact",),
    ),
    "ProgressCircle": contract(
        required=("icon", "externalText"),
        optional=("value", "size", "density", "ariaLabel", "appearance", "trackColor", "barColor", "dataIds"),
        size=("sm", "md"),
    ),
    "NumericRatio": contract(required=("icon", "value"), optional=("unit", "appearance", "dataIds")),
    "NumericRatioStack": contract(
        required=("items",),
        optional=("appearance", "direction"),
        direction=("column", "row"),
    ),
    "ChecklistItem": contract(required=("title", "meta"), optional=("done", "dataIds")),
    "EventCard": contract(
        required_one_of=("items", "title"),
        optional=("time", "location", "density", "dataIds"),
        density=("compact",),
    ),
    "PillButton": contract(
        required=("label",),
        optional=("icon", "appearance", "disabled", "variant", "color", "actionId"),
        variant=("emphasis", "normal"),
        color=("primary", "secondary", "success", "discovery", "danger", "warning", "caution"),
    ),
    "CircleButton": contract(
        required=("icon", "ariaLabel"),
        optional=("appearance", "disabled", "variant", "color", "actionId"),
        variant=("emphasis", "normal"),
        color=("primary", "secondary", "success", "discovery", "danger", "warning", "caution"),
    ),
    "CardButton": contract(required=("text",), optional=("icon", "disabled", "actionId")),
}


def binding_contract_sync_errors() -> list[str]:
    """Report drift between executable binding types and JSX contracts."""
    errors: list[str] = []
    for tag, typed_props in BINDABLE_PROP_TYPES.items():
        item = CONTRACTS.get(tag)
        if item is None:
            errors.append(f"binding types reference unknown component {tag}")
            continue
        contract_props = set(item.required) | set(item.optional) | set(item.required_one_of)
        top_level = {name for name in typed_props if not name.startswith("items[].")}
        item_level = {name for name in typed_props if name.startswith("items[].")}
        for prop in sorted(top_level - contract_props):
            errors.append(f"binding types reference unknown prop {tag}.{prop}")
        if top_level and "dataIds" not in contract_props:
            errors.append(f"{tag} has top-level binding types but its contract has no dataIds")
        if top_level and "dataValueMaps" not in contract_props:
            errors.append(f"{tag} has top-level binding types but its contract has no dataValueMaps")
        if item_level and "items" not in contract_props:
            errors.append(f"{tag} has item binding types but its contract has no items prop")

    for tag, item in CONTRACTS.items():
        contract_props = set(item.required) | set(item.optional) | set(item.required_one_of)
        if "dataIds" in contract_props and tag not in BINDABLE_PROP_TYPES:
            errors.append(f"{tag} accepts dataIds but has no binding type definitions")
    return errors


def collect_jsx_component_errors(
    node: JSXElement,
    contracts: Mapping[str, Contract] | None = None,
) -> list[str]:
    """Return every deterministic contract error for one JSX node.

    ``contracts`` lets callers validate the same JSX against a narrower
    surface, such as the model-facing generation contract, without copying
    the executable contract rules.
    """
    active_contracts = CONTRACTS if contracts is None else contracts
    item = active_contracts.get(node.tag)
    if item is None:
        return [f"unsupported JSX component <{node.tag}>"]
    errors: list[str] = []
    names = set(node.props)
    missing = item.required - names
    if missing:
        errors.append(f"<{node.tag}> is missing required props: {', '.join(sorted(missing))}")
    if item.required_one_of and not names.intersection(item.required_one_of):
        choices = ", ".join(sorted(item.required_one_of))
        errors.append(f"<{node.tag}> requires at least one of these props: {choices}")
    unknown = names - item.required - item.optional - item.required_one_of
    if unknown:
        errors.append(f"<{node.tag}> has unsupported props: {', '.join(sorted(unknown))}")
    for name, allowed in (item.enums or {}).items():
        if name in node.props and node.props[name] not in allowed:
            errors.append(f"<{node.tag}> prop {name} has invalid value {node.props[name]!r}")
    template_props = {
        "SingleLineTitle": {"titleTemplate": "title"},
        "DoubleLineTitle": {
            "titleTemplate": "title",
            "secondaryInfoTemplate": "secondaryInfo",
        },
        "InfoBlock": {
            "primaryTextTemplate": "primaryText",
            "secondaryTextTemplate": "secondaryText",
        },
        "EmphasisText": {"secondaryTextTemplate": "secondaryText"},
    }.get(node.tag, {})
    for template_prop, value_prop in template_props.items():
        if template_prop not in node.props:
            continue
        template = node.props[template_prop]
        data_ids = node.props.get("dataIds")
        raw_binding_ids = data_ids.get(value_prop) if isinstance(data_ids, dict) else None
        binding_ids = data_binding_ids(node.tag, value_prop, raw_binding_ids)
        indexed_template = (
            node.tag in {"InfoBlock", "EmphasisText"}
            and value_prop == "secondaryText"
            and binding_ids is not None
            and len(binding_ids) > 1
        )
        if indexed_template:
            if indexed_value_template_tokens(template, len(binding_ids)) is None:
                placeholders = "、".join(f"{{{index}}}" for index in range(len(binding_ids)))
                errors.append(
                    f"<{node.tag}> prop {template_prop} must contain {placeholders} exactly once in dataIds order"
                )
        elif not isinstance(template, str) or template.count("{value}") != 1:
            errors.append(
                f"<{node.tag}> prop {template_prop} must be a string containing exactly one {{value}} placeholder"
            )
        if binding_ids is None or (not indexed_template and len(binding_ids) != 1):
            errors.append(
                f"<{node.tag}> prop {template_prop} requires dataIds.{value_prop} to bind one non-empty data ID"
            )
        data_value_maps = node.props.get("dataValueMaps")
        if isinstance(data_value_maps, dict) and value_prop in data_value_maps:
            errors.append(
                f"<{node.tag}> prop {template_prop} cannot be combined with dataValueMaps.{value_prop}"
            )
    errors.extend(collect_display_prop_type_errors(node))
    return list(dict.fromkeys(errors))


def validate_jsx_component(node: JSXElement) -> None:
    errors = collect_jsx_component_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
