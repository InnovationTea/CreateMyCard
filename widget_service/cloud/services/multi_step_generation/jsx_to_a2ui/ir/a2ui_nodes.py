from __future__ import annotations

import re
import copy
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from ..catalog.bindings import (
    BINDABLE_PROPS,
    CompileContext,
    DataBinding,
    EVENT_TIME_RANGE_SEPARATOR,
    a2ui_expression,
    boolean_text_expression,
    boolean_text_map_for,
    binding_value_type_error,
    collect_display_semantic_errors,
    data_binding_ids,
    data_model_expression_reference,
    expression_string_literal,
    is_boolean_text_mapping_target,
    normalized_boolean_text_map,
    value_type,
)
from ..catalog.display_values import (
    DisplayPlan,
    derived_path_for_source,
    normalize_display_value,
    set_pointer_value,
)
from ..exceptions import ValidationError
from ..parser.jsx_ast import JSXElement


BASE_COMPONENTS = frozenset({
    "Text", "Image", "Divider", "Progress", "Button", "Checkbox",
    "Row", "Column", "List", "Stack",
})


class IdAllocator:
    def __init__(self, prefix: str = ""):
        self.prefix = _slug(prefix)
        self.counts: dict[str, int] = {}

    def next(self, hint: str) -> str:
        base = _slug(hint) or "node"
        self.counts[base] = self.counts.get(base, 0) + 1
        suffix = "" if self.counts[base] == 1 else f"_{self.counts[base]}"
        return "_".join(part for part in (self.prefix, base + suffix) if part)


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_").lower()
    return text or ""


@dataclass(slots=True)
class A2UINode:
    id: str
    component: str
    props: dict[str, Any] = field(default_factory=dict)
    styles: dict[str, Any] = field(default_factory=dict)
    children: list["A2UINode"] = field(default_factory=list)

    def wire(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "component": self.component}
        result.update(self.props)
        if self.styles:
            result["styles"] = self.styles
        if self.children:
            result["children"] = [child.id for child in self.children]
        return result


Converter = Callable[[JSXElement, "ConversionContext"], A2UINode]


def collect_binding_validation_errors(
    element: JSXElement,
    compile_context: CompileContext,
) -> list[str]:
    """Return all binding-contract errors for one JSX element."""
    errors: list[str] = []

    def validate(
        tag: str,
        prop: str,
        contract_prop: str,
        binding_id: Any,
        present: bool,
        literal: Any,
        owner: dict[str, Any],
    ) -> None:
        binding_ids = data_binding_ids(tag, contract_prop, binding_id)
        if binding_ids is None:
            if tag == "EventCard" and contract_prop == "time":
                errors.append(
                    "<EventCard> dataIds.time must be a non-empty string or an "
                    "ordered array of exactly two IDs: [dtStartId, dtEndId]"
                )
            else:
                errors.append(f"<{tag}> dataIds.{prop} must be a non-empty string")
            return
        if any(not item.strip() for item in binding_ids):
            errors.append(f"<{tag}> dataIds.{prop} contains an empty data ID")
            return
        if len(set(binding_ids)) != len(binding_ids):
            errors.append(f"<{tag}> dataIds.{prop} must not repeat the same data ID")
            return
        if not present:
            errors.append(f"<{tag}> dataIds.{prop} requires the corresponding display prop")
            return
        raw_maps = owner.get("dataValueMaps")
        display_prop = prop.rsplit(".", 1)[-1]
        owner_path = prop.rsplit(".", 1)[0] if prop.startswith("items[") else ""
        map_location = (
            f"{owner_path}.dataValueMaps.{display_prop}"
            if owner_path
            else f"dataValueMaps.{display_prop}"
        )
        has_value_map = isinstance(raw_maps, dict) and display_prop in raw_maps
        value_map = raw_maps.get(display_prop) if has_value_map else None
        for item in binding_ids:
            try:
                binding = compile_context.data_binding(item)
            except ValidationError as exc:
                errors.append(str(exc))
                continue
            actual = binding.data_type or value_type(binding.value)
            if actual == "boolean" and is_boolean_text_mapping_target(tag, contract_prop):
                if not has_value_map:
                    errors.append(
                        f"<{tag}> {prop} binds boolean data {binding.id!r} to visible text. "
                        f"Add {map_location} with distinct non-empty "
                        "true and false strings; direct boolean-to-text binding is not allowed"
                    )
                elif normalized_boolean_text_map(value_map) is None:
                    errors.append(
                        f"<{tag}> {map_location} must be an object containing exactly "
                        "distinct non-empty string values for true and false"
                    )
                continue
            if has_value_map:
                errors.append(
                    f"<{tag}> {map_location} can only transform a boolean data binding "
                    "used by a visible text-only Prop"
                )
            type_error = binding_value_type_error(
                tag,
                contract_prop,
                binding.id,
                binding.data_type,
                binding.value,
            )
            if type_error is not None:
                errors.append(type_error)

    def validate_map_keys(
        tag: str,
        owner: dict[str, Any],
        allowed: set[str],
        where: str,
    ) -> None:
        if "dataValueMaps" not in owner:
            return
        maps = owner.get("dataValueMaps")
        if not isinstance(maps, dict):
            errors.append(f"<{tag}> {where}dataValueMaps must be an object")
            return
        data_ids = owner.get("dataIds")
        for prop in maps:
            location = f"{where}dataValueMaps.{prop}"
            if prop not in allowed:
                errors.append(f"<{tag}> {location} targets a Prop that cannot be data-bound")
            elif not isinstance(data_ids, dict) or prop not in data_ids:
                errors.append(f"<{tag}> {location} requires the same Prop in dataIds")

    data_ids = element.props.get("dataIds")
    if data_ids is not None:
        if not isinstance(data_ids, dict):
            errors.append(f"<{element.tag}> dataIds must be an object")
        else:
            allowed = {
                name
                for name in BINDABLE_PROPS.get(element.tag, frozenset())
                if not name.startswith("items[].")
            }
            validate_map_keys(element.tag, element.props, allowed, "")
            for prop, binding_id in data_ids.items():
                if prop not in allowed:
                    errors.append(f"<{element.tag}> prop {prop!r} cannot be data-bound")
                    continue
                validate(
                    element.tag,
                    prop,
                    prop,
                    binding_id,
                    prop in element.props,
                    element.props.get(prop),
                    element.props,
                )
    elif "dataValueMaps" in element.props:
        validate_map_keys(
            element.tag,
            element.props,
            {
                name
                for name in BINDABLE_PROPS.get(element.tag, frozenset())
                if not name.startswith("items[].")
            },
            "",
        )

    items = element.props.get("items")
    allowed_items = {
        name.removeprefix("items[].")
        for name in BINDABLE_PROPS.get(element.tag, frozenset())
        if name.startswith("items[].")
    }
    if isinstance(items, list):
        for index, item in enumerate(items):
            if not isinstance(item, dict) or "dataIds" not in item:
                continue
            item_ids = item["dataIds"]
            if not isinstance(item_ids, dict):
                errors.append(f"<{element.tag}> items[{index}].dataIds must be an object")
                continue
            validate_map_keys(element.tag, item, allowed_items, f"items[{index}].")
            for prop, binding_id in item_ids.items():
                if prop not in allowed_items:
                    errors.append(
                        f"<{element.tag}> items[{index}].{prop} cannot be data-bound"
                    )
                    continue
                validate(
                    element.tag,
                    f"items[{index}].{prop}",
                    f"items[].{prop}",
                    binding_id,
                    prop in item,
                    item.get(prop),
                    item,
                )
        for index, item in enumerate(items):
            if (
                isinstance(item, dict)
                and "dataValueMaps" in item
                and "dataIds" not in item
            ):
                validate_map_keys(element.tag, item, allowed_items, f"items[{index}].")
    errors.extend(collect_display_semantic_errors(element, compile_context))
    return errors


@dataclass(slots=True)
class ConversionContext:
    allocator: IdAllocator
    convert_fn: Converter
    appearance: str = "blue-soft"
    card_size: str | None = None
    card_content_width: int | float | None = None
    card_content_height: int | float | None = None
    compile_context: CompileContext = field(default_factory=CompileContext)
    used_data_ids: set[str] = field(default_factory=set)
    used_action_ids: set[str] = field(default_factory=set)
    derived_data_model: dict[str, Any] = field(default_factory=dict)

    def make(
        self,
        component: str,
        hint: str,
        *,
        props: dict[str, Any] | None = None,
        styles: dict[str, Any] | None = None,
        children: list[A2UINode | None] | None = None,
    ) -> A2UINode:
        if component not in BASE_COMPONENTS:
            raise ValidationError(f"converter attempted to emit non-standard component {component!r}")
        return A2UINode(
            id=self.allocator.next(hint),
            component=component,
            props={key: value for key, value in (props or {}).items() if value is not None},
            styles={key: value for key, value in (styles or {}).items() if value is not None},
            children=[child for child in (children or []) if child is not None],
        )

    def convert(self, element: JSXElement) -> A2UINode:
        return self.convert_fn(element, self)

    def validate_bindings(self, element: JSXElement) -> None:
        errors = collect_binding_validation_errors(element, self.compile_context)
        if errors:
            raise ValidationError(errors[0])

    def prop(self, element: JSXElement, name: str, default: Any = None) -> Any:
        literal = element.props[name] if name in element.props else default
        data_ids = element.props.get("dataIds")
        if not isinstance(data_ids, dict) or name not in data_ids:
            return literal
        binding_ids = data_binding_ids(element.tag, name, data_ids[name])
        if binding_ids is None:
            raise ValidationError(
                f"<{element.tag}> dataIds.{name} has an invalid binding shape"
            )
        if len(binding_ids) > 1:
            bindings = [self.compile_context.data_binding(item) for item in binding_ids]
            self.used_data_ids.update(binding.id for binding in bindings)
            parts: list[str] = []
            for index, binding in enumerate(bindings):
                if index:
                    parts.append(expression_string_literal(EVENT_TIME_RANGE_SEPARATOR))
                parts.append(data_model_expression_reference(binding.path))
            return a2ui_expression(parts)
        binding = self.compile_context.data_binding(binding_ids[0])
        self.used_data_ids.add(binding.id)
        value_map = boolean_text_map_for(element.props, name)
        if value_map is not None and (
            binding.data_type == "boolean" or isinstance(binding.value, bool)
        ):
            return boolean_text_expression(binding.path, value_map)
        return {"path": binding.path}

    def item_prop(self, tag: str, item: dict[str, Any], index: int, name: str, default: Any = None) -> Any:
        literal = item[name] if name in item else default
        data_ids = item.get("dataIds")
        if not isinstance(data_ids, dict) or name not in data_ids:
            return literal
        binding_id = data_ids[name]
        binding = self.compile_context.data_binding(binding_id)
        self.used_data_ids.add(binding.id)
        value_map = boolean_text_map_for(item, name)
        if value_map is not None and (
            binding.data_type == "boolean" or isinstance(binding.value, bool)
        ):
            return boolean_text_expression(binding.path, value_map)
        return {"path": binding.path}

    def bound_data(
        self,
        owner: dict[str, Any],
        name: str,
    ) -> DataBinding | None:
        data_ids = owner.get("dataIds")
        if not isinstance(data_ids, dict) or name not in data_ids:
            return None
        binding = self.compile_context.data_binding(data_ids[name])
        self.used_data_ids.add(binding.id)
        return binding

    def register_derived_display(self, binding: DataBinding) -> tuple[str, DisplayPlan]:
        """Register one private display model derived from an original binding."""
        plan = normalize_display_value(binding.value)
        path = derived_path_for_source(binding.path)
        set_pointer_value(self.derived_data_model, path, plan.data_model_value())
        self.used_data_ids.add(binding.id)
        return path, plan

    def action_props(self, element: JSXElement) -> dict[str, Any]:
        action_id = element.props.get("actionId")
        if action_id is None:
            return {}
        if not isinstance(action_id, str) or not action_id.strip():
            raise ValidationError(f"<{element.tag}> actionId must be a non-empty string")
        if element.props.get("disabled"):
            raise ValidationError(f"disabled <{element.tag}> cannot declare actionId")
        if action_id in self.used_action_ids:
            raise ValidationError(f"action id {action_id!r} is used by more than one control")
        action = self.compile_context.action_binding(action_id)
        self.used_action_ids.add(action.id)
        return {"onClick": [copy.deepcopy(action.handler)]}

    def with_appearance(self, appearance: str) -> "ConversionContext":
        return replace(self, appearance=appearance)

    def with_card_surface(
        self,
        size: str | None,
        width: int | float | None,
        height: int | float | None,
    ) -> "ConversionContext":
        return replace(
            self,
            card_size=size,
            card_content_width=width,
            card_content_height=height,
        )


def flatten_tree(root: A2UINode) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(node: A2UINode) -> None:
        if node.id in seen:
            raise ValidationError(f"duplicate A2UI component id {node.id!r}")
        seen.add(node.id)
        rows.append(node.wire())
        for child in node.children:
            visit(child)

    visit(root)
    return rows
