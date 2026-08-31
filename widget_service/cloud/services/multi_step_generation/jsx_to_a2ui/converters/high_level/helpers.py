from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ...catalog.tokens import normalize_color
from ...catalog.bindings import (
    a2ui_expression,
    boolean_text_map_for,
    data_model_expression_reference,
    expression_string_literal,
)
from ...exceptions import ValidationError
from ..base.image import image
from ..base.layout import stack
from ..base.text import text
from ..base.progress import progress
from ..common import accessibility, palette


def clamp_percent(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, min(100, value))
    return value


def collect_segmented_text_conversion_errors(node: JSXElement) -> list[str]:
    errors: list[str] = []
    items = node.props.get("items")
    if not isinstance(items, list) or not items:
        return [f"{node.tag}.items must be a non-empty array"]
    separator = node.props.get("separator", " ｜ ")
    if not isinstance(separator, str) or "\n" in separator or "\r" in separator:
        errors.append(f"{node.tag}.separator must be a single-line string")
    elif "${" in separator:
        errors.append(
            f"{node.tag}.separator must not contain the reserved A2UI expression marker '${{'; "
            "use ordinary visible text"
        )

    for index, item in enumerate(items):
        where = f"{node.tag}.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        label = item.get("label")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            errors.append(f"{where}.label must be omitted or a non-empty string")
        elif isinstance(label, str) and "${" in label:
            errors.append(
                f"{where}.label must not contain the reserved A2UI expression marker '${{'; "
                "use ordinary visible text"
            )
        value = item.get("value")
        if "value" not in item or isinstance(value, (dict, list, bool)) or value is None:
            errors.append(f"{where}.value must be a string or number")
        else:
            data_ids = item.get("dataIds")
            value_is_bound = isinstance(data_ids, dict) and "value" in data_ids
            if not value_is_bound and "${" in str(value):
                errors.append(
                    f"{where}.value must not contain the reserved A2UI expression marker '${{'; "
                    "use ordinary visible text"
                )
        if "unit" in item:
            errors.append(
                f"{where}.unit is not supported; keep the complete input display "
                "value, including its unit, in value"
            )
    return list(dict.fromkeys(errors))


def segmented_text(
    node: JSXElement,
    ctx: ConversionContext,
    *,
    hint: str,
    font_size: int,
    line_height: int,
    font_color: str | None = None,
) -> A2UINode:
    """Lower segmented JSX text to one naturally wrapping A2UI Text.

    A single Text preserves the JSX component's inline text flow. A pure
    single-source value uses PathBinding; labels, separators, multiple paths,
    or mapped values are lowered to one responsive A2UI Expression.
    """
    errors = collect_segmented_text_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    separator = node.props.get("separator", " ｜ ")

    text_styles = {
        "fontSize": font_size,
        "fontWeight": 400,
        "fontColor": font_color or palette(ctx).secondary,
        "textAlign": "start",
        "flexShrink": 1,
        "constraintSize": {"minWidth": 0, "minHeight": line_height},
    }
    fragments: list[tuple[str, Any]] = []

    def append_static(value: Any, where: str) -> None:
        rendered = str(value)
        if "${" in rendered:
            raise ValidationError(
                f"{where} must not contain the reserved A2UI expression marker '${{'; "
                "use ordinary visible text"
            )
        fragments.append(("literal", rendered))

    for index, item in enumerate(items):
        where = f"{node.tag}.items[{index}]"
        if not isinstance(item, dict):
            raise ValidationError(f"{where} must be an object")
        label = item.get("label")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise ValidationError(f"{where}.label must be omitted or a non-empty string")
        if "value" not in item or isinstance(item["value"], (dict, list, bool)) or item["value"] is None:
            raise ValidationError(f"{where}.value must be a string or number")
        if index and separator:
            append_static(separator, f"{node.tag}.separator")
        if label is not None:
            append_static(label, f"{where}.label")
        value = ctx.item_prop(node.tag, item, index, "value")
        if isinstance(value, dict) and set(value) == {"path"}:
            path = value["path"]
            data_model_expression_reference(path)
            fragments.append(("path", path))
        elif (
            isinstance(value, str)
            and value.strip().startswith("{{")
            and value.strip().endswith("}}")
        ):
            # item_prop only returns an Expression here for a complete Boolean
            # dataValueMaps mapping. Keep its structure instead of embedding the
            # complete ternary inside parentheses: the target device parser
            # rejects a whole conditional grouped in this property position.
            binding = ctx.bound_data(item, "value")
            value_map = boolean_text_map_for(item, "value")
            if binding is None or value_map is None:
                raise ValidationError(
                    f"{where}.value produced an unsupported nested A2UI Expression"
                )
            fragments.append(
                ("conditional", (binding.path, value_map[True], value_map[False]))
            )
        else:
            append_static(value, f"{where}.value")

    dynamic = any(kind != "literal" for kind, _ in fragments)
    if len(fragments) == 1 and fragments[0][0] == "path":
        content = {"path": fragments[0][1]}
    elif dynamic:
        def render_expression(parts: list[tuple[str, Any]]) -> str:
            for index, (kind, fragment) in enumerate(parts):
                if kind != "conditional":
                    continue
                condition_path, true_text, false_text = fragment
                true_parts = parts[:index] + [("literal", true_text)] + parts[index + 1:]
                false_parts = parts[:index] + [("literal", false_text)] + parts[index + 1:]
                return (
                    f"{data_model_expression_reference(condition_path)} ? "
                    f"{render_expression(true_parts)} : {render_expression(false_parts)}"
                )

            atoms: list[str] = []
            pending_literal = ""
            for kind, fragment in parts:
                if kind == "literal":
                    pending_literal += fragment
                    continue
                if pending_literal:
                    atoms.append(expression_string_literal(pending_literal))
                    pending_literal = ""
                atoms.append(data_model_expression_reference(fragment))
            if pending_literal:
                atoms.append(expression_string_literal(pending_literal))
            return " + ".join(atoms)

        if any(kind == "conditional" for kind, _ in fragments):
            # Conditional expressions associate from the right, so recursively
            # distributing the surrounding fragments into each branch supports
            # multiple mapped Boolean values without grouping parentheses.
            content = "{{ " + render_expression(fragments) + " }}"
        else:
            expression_parts: list[str] = []
            for kind, fragment in fragments:
                if kind == "path":
                    expression_parts.append(data_model_expression_reference(fragment))
                else:
                    expression_parts.append(expression_string_literal(fragment))
            content = a2ui_expression(expression_parts)
    else:
        content = "".join(fragment for _, fragment in fragments)
    return text(ctx, hint, content, styles=text_styles)


def ring_with_icon(
    ctx: ConversionContext,
    *,
    value: Any,
    icon: str,
    size: int,
    stroke_width: int,
    icon_size: int,
    hint: str,
    aria_label: str | None = None,
    bar_color: str = "#FF64BB5C",
    track_color: str | None = None,
    icon_color: str | None = None,
) -> A2UINode:
    ring_styles = {"width": size, "height": size, "flexShrink": 0}
    if track_color:
        ring_styles["backgroundColor"] = normalize_color(track_color)
    ring = progress(ctx, f"{hint}_progress", clamp_percent(value), 100, kind="ring", color=normalize_color(bar_color), stroke_width=stroke_width, styles=ring_styles)
    icon_node = image(ctx, f"{hint}_icon", icon, styles={"width": icon_size, "height": icon_size, "objectFit": "contain"}, fill_color=icon_color or palette(ctx).secondary)
    props = {"accessibility": accessibility(aria_label)} if aria_label else {}
    return stack(ctx, hint, [ring, icon_node], align="center", styles={"width": size, "height": size, "flexShrink": 0}, props=props)
