from __future__ import annotations

import re
from typing import Any

from ..exceptions import ValidationError
from ..ir.a2ui_nodes import BASE_COMPONENTS

COMMON_PROPS = {"id", "component", "accessibility", "onClick"}
COMMON_STYLES = {
    "backgroundImageSizeWithStyle",
    "flexShrink",
    "width",
    "height",
    "constraintSize",
    "backgroundImage",
    "margin",
    "borderRadius",
    "visibility",
    "clip",
    "backgroundColor",
    "borderWidth",
    "borderColor",
    "padding",
    "layoutWeight",
    "shadow",
    "linearGradient",
    "aspectRatio",
}
PROPS = {
    "Text": {"content"},
    "Image": {"src"},
    "Divider": set(),
    "Progress": {"value", "total"},
    "Button": {"label", "enabled"},
    "Checkbox": {"label", "value", "select"},
    "Row": {"children", "itemMargin"},
    "Column": {"children", "itemMargin"},
    "List": {"children", "space"},
    "Stack": {"children"},
}
STYLES = {
    "Text": {
        "textOverflow",
        "fontSize",
        "fontWeight",
        "fontColor",
        "textAlign",
        "maxLines",
        "maxFontSize",
        "minFontSize",
    },
    "Image": {"objectFit", "fillColor"},
    "Divider": {"strokeWidth", "vertical", "color"},
    "Progress": {"color", "type", "strokeWidth"},
    "Button": {"fontColor", "fontSize", "fontWeight", "maxFontSize", "minFontSize"},
    "Checkbox": {"selectedColor", "shape"},
    "Row": {"justifyContent", "alignItems"},
    "Column": {"justifyContent", "alignItems"},
    "List": {"listDirection", "scrollBar"},
    "Stack": {"alignContent"},
}


def _is_dynamic(value: Any) -> bool:
    return isinstance(value, dict) or (
        isinstance(value, str) and value.strip().startswith("{{") and value.strip().endswith("}}")
    )


def _validate_dynamic_binding(value: Any, where: str) -> None:
    if not isinstance(value, dict):
        return
    if set(value) == {"path"}:
        if isinstance(value.get("path"), str) and value["path"].startswith("/"):
            return
        raise ValidationError(f"{where} PathBinding.path must start with '/'")
    if set(value) == {"call", "args"}:
        raise ValidationError(
            f"{where} must not use FunctionCall for a dynamic property; "
            "use PathBinding for one source or Expression for multiple sources"
        )
    raise ValidationError(f"{where} dynamic binding must be a PathBinding or Expression")


def _validate_on_click(value: Any, where: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{where} must be a non-empty handler array")
    for index, handler in enumerate(value):
        if not isinstance(handler, dict):
            raise ValidationError(f"{where}[{index}] must be an object")
        if not isinstance(handler.get("call"), str) or not handler["call"]:
            raise ValidationError(f"{where}[{index}].call must be a non-empty string")
        if "args" in handler and not isinstance(handler["args"], dict):
            raise ValidationError(f"{where}[{index}].args must be an object")


def _reject_dynamic_function_calls(value: Any, where: str) -> None:
    """Reject FunctionCall-shaped dynamic values outside interaction handlers."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_dynamic_function_calls(item, f"{where}[{index}]")
        return
    if not isinstance(value, dict):
        return
    if set(value) == {"call", "args"}:
        raise ValidationError(
            f"{where} must not use FunctionCall for a dynamic property; "
            "use PathBinding for one source or Expression for multiple sources"
        )
    for key, item in value.items():
        _reject_dynamic_function_calls(item, f"{where}.{key}")


def _validate_color(value: Any, where: str) -> None:
    if _is_dynamic(value):  # Resolved type is catalog-checked at runtime.
        return
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{8}", value):
        raise ValidationError(f"{where} must use #AARRGGBB; found {value!r}")


def _validate_enum(value: Any, allowed: set[str], where: str) -> None:
    if value is not None and not _is_dynamic(value) and value not in allowed:
        raise ValidationError(f"{where} has invalid value {value!r}")


def _validate_number(value: Any, where: str, *, minimum: float | None = None, maximum: float | None = None) -> None:
    if value is None or _is_dynamic(value):
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{where} must be a number or dynamic binding")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{where} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{where} must be <= {maximum}")


def _validate_common_styles(styles: dict[str, Any], node_id: str) -> None:
    _validate_enum(styles.get("visibility"), {"visible", "hidden", "none"}, f"{node_id}.styles.visibility")
    _validate_number(styles.get("flexShrink"), f"{node_id}.styles.flexShrink", minimum=0, maximum=1)
    _validate_number(styles.get("layoutWeight"), f"{node_id}.styles.layoutWeight", minimum=0)
    for key in ("borderWidth", "aspectRatio"):
        _validate_number(styles.get(key), f"{node_id}.styles.{key}", minimum=0)
    shadow = styles.get("shadow")
    if shadow is not None:
        if not isinstance(shadow, (dict, str)):
            raise ValidationError(f"{node_id}.styles.shadow must be an object or enum string")
        if isinstance(shadow, dict):
            if "radius" not in shadow:
                raise ValidationError(f"{node_id}.styles.shadow.radius is required")
            _validate_number(shadow.get("radius"), f"{node_id}.styles.shadow.radius", minimum=0)
            if "color" in shadow:
                _validate_color(shadow["color"], f"{node_id}.styles.shadow.color")
    gradient = styles.get("linearGradient")
    if gradient is not None:
        if not isinstance(gradient, dict) or not isinstance(gradient.get("colors"), list):
            raise ValidationError(f"{node_id}.styles.linearGradient requires a colors array")
        for index, stop in enumerate(gradient["colors"]):
            if not isinstance(stop, list) or len(stop) != 2:
                raise ValidationError(f"{node_id}.styles.linearGradient.colors[{index}] must be [color, stop]")
            _validate_color(stop[0], f"{node_id}.styles.linearGradient.colors[{index}][0]")
            _validate_number(stop[1], f"{node_id}.styles.linearGradient.colors[{index}][1]", minimum=0, maximum=1)


def validate_components(components: list[dict[str, Any]]) -> None:
    if not components:
        raise ValidationError("updateComponents.components must not be empty")
    ids: set[str] = set()
    referenced: set[str] = set()
    for item in components:
        component = item.get("component")
        node_id = item.get("id")
        if component not in BASE_COMPONENTS:
            raise ValidationError(f"component {node_id!r} uses non-standard type {component!r}")
        if not isinstance(node_id, str) or not node_id:
            raise ValidationError("every component requires a non-empty string id")
        if node_id in ids:
            raise ValidationError(f"duplicate component id {node_id!r}")
        ids.add(node_id)
        allowed_props = COMMON_PROPS | PROPS[component] | {"styles"}
        unknown_props = set(item) - allowed_props
        if unknown_props:
            raise ValidationError(f"{node_id}: unsupported {component} properties {sorted(unknown_props)}")
        if "onClick" in item:
            _validate_on_click(item["onClick"], f"{node_id}.onClick")
        for key, value in item.items():
            if key != "onClick":
                _reject_dynamic_function_calls(value, f"{node_id}.{key}")
        styles = item.get("styles", {})
        if not isinstance(styles, dict):
            raise ValidationError(f"{node_id}.styles must be an object")
        unknown_styles = set(styles) - COMMON_STYLES - STYLES[component]
        if unknown_styles:
            raise ValidationError(f"{node_id}: unsupported {component} styles {sorted(unknown_styles)}")
        for key, value in styles.items():
            if "Color" in key or key == "color":
                _validate_color(value, f"{node_id}.styles.{key}")
        _validate_common_styles(styles, node_id)
        if component == "Text":
            _validate_enum(styles.get("textOverflow"), {"clip", "ellipsis"}, f"{node_id}.styles.textOverflow")
            _validate_enum(
                styles.get("textAlign"), {"start", "center", "end", "justify"}, f"{node_id}.styles.textAlign"
            )
            _validate_number(styles.get("fontSize"), f"{node_id}.styles.fontSize", minimum=0)
            _validate_number(styles.get("maxLines"), f"{node_id}.styles.maxLines", minimum=0)
            weight = styles.get("fontWeight")
            if weight is not None and not _is_dynamic(weight):
                weight_out_of_range = not isinstance(weight, int) or weight < 100 or weight > 900
                if weight_out_of_range or weight % 100:
                    raise ValidationError(f"{node_id}.styles.fontWeight must be 100..900 in steps of 100")
        if component == "Image":
            _validate_enum(
                styles.get("objectFit"),
                {
                    "fill",
                    "contain",
                    "cover",
                    "auto",
                    "none",
                    "scaleDown",
                    "topStart",
                    "top",
                    "topEnd",
                    "start",
                    "center",
                    "end",
                    "bottomStart",
                    "bottom",
                    "bottomEnd",
                    "matrix",
                },
                f"{node_id}.styles.objectFit",
            )
        if component == "Row":
            if styles.get("alignItems") not in {None, "top", "center", "bottom"}:
                raise ValidationError(f"{node_id}.styles.alignItems is invalid for Row")
        if component == "Column":
            if styles.get("alignItems") not in {None, "start", "center", "end"}:
                raise ValidationError(f"{node_id}.styles.alignItems is invalid for Column")
        if component in {"Row", "Column"}:
            if styles.get("justifyContent") not in {
                None,
                "start",
                "center",
                "end",
                "spaceBetween",
                "spaceAround",
                "spaceEvenly",
            }:
                raise ValidationError(f"{node_id}.styles.justifyContent is invalid")
        if component == "Progress" and styles.get("type") not in {
            None,
            "linear",
            "ring",
            "eclipse",
            "scaleRing",
            "capsule",
        }:
            raise ValidationError(f"{node_id}.styles.type is invalid")
        if component == "Stack":
            _validate_enum(
                styles.get("alignContent"),
                {"topStart", "top", "topEnd", "start", "center", "end", "bottomStart", "bottom", "bottomEnd"},
                f"{node_id}.styles.alignContent",
            )
        children = item.get("children", [])
        if children and not isinstance(children, list):
            raise ValidationError(f"{node_id}.children must be an array")
        referenced.update(str(child) for child in children)
        if component == "Text" and "content" not in item:
            raise ValidationError(f"{node_id}: Text requires content")
        if component == "Text":
            _validate_dynamic_binding(item.get("content"), f"{node_id}.content")
        if component == "Image" and not item.get("src"):
            raise ValidationError(f"{node_id}: Image requires src")
        if component == "Progress" and "value" not in item:
            raise ValidationError(f"{node_id}: Progress requires value")
        if component == "Progress":
            _validate_dynamic_binding(item.get("value"), f"{node_id}.value")
            _validate_dynamic_binding(item.get("total"), f"{node_id}.total")
            _validate_number(item.get("value"), f"{node_id}.value", minimum=0)
            _validate_number(item.get("total"), f"{node_id}.total", minimum=0)
            value = item.get("value")
            total = item.get("total")
            value_is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            total_is_number = isinstance(total, (int, float)) and not isinstance(total, bool)
            if value_is_number and total_is_number and value > total:
                raise ValidationError(f"{node_id}.value must not exceed total")
            _validate_number(styles.get("strokeWidth"), f"{node_id}.styles.strokeWidth", minimum=0)
        if component == "Button" and "label" not in item:
            raise ValidationError(f"{node_id}: Button requires label")
        if component == "Checkbox":
            _validate_dynamic_binding(item.get("select"), f"{node_id}.select")
    missing = referenced - ids
    if missing:
        raise ValidationError(f"children reference missing component ids: {sorted(missing)}")
    roots = ids - referenced
    if len(roots) != 1:
        raise ValidationError(f"surface must have exactly one root component; found {sorted(roots)}")


def validate_messages(messages: list[dict[str, Any]]) -> None:
    if len(messages) < 2:
        raise ValidationError("A2UI output requires createSurface and updateComponents")
    create = messages[0].get("createSurface")
    update = messages[1].get("updateComponents")
    if not isinstance(create, dict) or not isinstance(update, dict):
        raise ValidationError("first two messages must be createSurface and updateComponents")
    if messages[0].get("version") != "v0.9" or messages[1].get("version") != "v0.9":
        raise ValidationError("A2UI messages must use version v0.9")
    if not isinstance(create.get("surfaceId"), str) or not create["surfaceId"]:
        raise ValidationError("createSurface requires a non-empty surfaceId")
    if create.get("catalogId") != "ohos.a2ui.extended.catalog.form":
        raise ValidationError("createSurface uses the wrong Form catalogId")
    if create.get("surfaceId") != update.get("surfaceId"):
        raise ValidationError("surfaceId differs between protocol messages")
    validate_components(update.get("components") or [])
    for index, message in enumerate(messages[2:], start=2):
        if message.get("version") != "v0.9":
            raise ValidationError(f"message {index} must use version v0.9")
        data_update = message.get("updateDataModel")
        if not isinstance(data_update, dict):
            raise ValidationError(f"message {index} must be updateDataModel")
        if data_update.get("surfaceId") != create["surfaceId"]:
            raise ValidationError(f"message {index} has the wrong surfaceId")
        if not isinstance(data_update.get("path"), str) or not data_update["path"].startswith("/"):
            raise ValidationError(f"message {index} updateDataModel.path must start with /")
        if "value" not in data_update:
            raise ValidationError(f"message {index} updateDataModel.value is required")
