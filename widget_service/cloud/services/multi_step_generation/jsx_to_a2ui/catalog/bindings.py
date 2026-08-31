from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from ..exceptions import ValidationError
from ..parser.jsx_ast import JSXElement
from .display_values import normalize_display_value


_STRING = frozenset({"string"})
_NUMBER = frozenset({"integer", "number"})
_SCALAR_TEXT = frozenset({"string", "integer", "number"})
_BOOLEAN = frozenset({"boolean"})
_FORMATTED_PERCENTAGE = re.compile(r"^\s*\d+(?:\.\d+)?\s*%\s*$")
EVENT_TIME_RANGE_SEPARATOR = " – "

# One executable source of truth for both literal Props and data bindings.
# Booleans are intentionally excluded from visible text/value Props: Python's
# bool is a subclass of int, but rendering True/False as business copy is not a
# valid numeric or textual presentation.
BINDABLE_PROP_TYPES: dict[str, dict[str, frozenset[str]]] = {
    "SingleLineTitle": {"title": _SCALAR_TEXT},
    "DoubleLineTitle": {"title": _SCALAR_TEXT, "secondaryInfo": _SCALAR_TEXT},
    "Badge": {"value": _SCALAR_TEXT},
    "DataDisplay": {"value": _SCALAR_TEXT},
    "InfoBlock": {
        "primaryText": _SCALAR_TEXT,
        "secondaryText": _SCALAR_TEXT,
    },
    "TopTextBottomValue": {"items[].value": _SCALAR_TEXT},
    "TableText": {"items[].parameter": _SCALAR_TEXT},
    "TextBlock": {"items[].parameter": _SCALAR_TEXT},
    "EmphasizedData": {
        "value": _SCALAR_TEXT,
        "unit": _STRING,
        "items[].value": _SCALAR_TEXT,
        "items[].unit": _STRING,
    },
    "EmphasisText": {"mainText": _SCALAR_TEXT, "secondaryText": _SCALAR_TEXT},
    "SecondaryBody": {"body": _SCALAR_TEXT, "items[].value": _SCALAR_TEXT},
    "Summary": {"content": _SCALAR_TEXT, "items[].value": _SCALAR_TEXT},
    "ProgressLine1": {
        "currentValue": _NUMBER,
        "totalValue": _NUMBER,
        "leftLabel": _SCALAR_TEXT,
        "rightLabel": _SCALAR_TEXT,
    },
    "ProgressLine2": {
        "currentValue": _NUMBER,
        "totalValue": _NUMBER,
        "value": _SCALAR_TEXT,
        "unit": _STRING,
        "items[].value": _SCALAR_TEXT,
        "items[].unit": _STRING,
    },
    "ProgressLine2WithData": {
        "currentValue": _NUMBER,
        "totalValue": _NUMBER,
        "value": _SCALAR_TEXT,
        "unit": _STRING,
        "items[].value": _SCALAR_TEXT,
        "items[].unit": _STRING,
    },
    "H_BarChart": {"items[].valueUnit": _SCALAR_TEXT},
    "Gauge": {"value": _SCALAR_TEXT},
    "ProgressCircleSingle": {
        "value": _SCALAR_TEXT,
        "displayValue": _SCALAR_TEXT,
        "label": _SCALAR_TEXT,
        "secondaryLabel": _SCALAR_TEXT,
    },
    "ProgressCircle": {"externalText": _SCALAR_TEXT},
    "NumericRatio": {"value": _SCALAR_TEXT},
    "NumericRatioStack": {"items[].value": _SCALAR_TEXT},
    "ChecklistItem": {"title": _SCALAR_TEXT, "meta": _SCALAR_TEXT, "done": _BOOLEAN},
    "EventCard": {"title": _SCALAR_TEXT, "time": _SCALAR_TEXT, "location": _SCALAR_TEXT},
}

BINDABLE_PROPS: dict[str, frozenset[str]] = {
    tag: frozenset(props)
    for tag, props in BINDABLE_PROP_TYPES.items()
}


def data_binding_ids(tag: str, prop: str, value: Any) -> tuple[str, ...] | None:
    """Normalize one display Prop's public dataIds value.

    Most display Props bind one ID. EventCard.time additionally accepts the
    ordered pair [dtStartId, dtEndId] so one visible time range can remain
    responsive to both source fields.
    """
    if isinstance(value, str):
        return (value,)
    if (
        tag == "EventCard"
        and prop == "time"
        and isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, str) for item in value)
    ):
        return tuple(value)
    return None

_VALUE_UNIT_COMPONENTS = frozenset({
    "ProgressLine2",
    "ProgressLine2WithData",
})
_STATUS_ID_MARKERS = frozenset({"status", "state", "condition", "connected", "charging"})
_STATUS_DESCRIPTION_MARKERS = ("状态", "是否", "天气现象", "连接活跃")


def value_type(value: Any) -> str:
    """Return a schema-style type name without treating bool as a number."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _is_path_binding(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"path"}
        and isinstance(value.get("path"), str)
        and value["path"].startswith("/")
    )


def _type_label(allowed: frozenset[str]) -> str:
    names: list[str] = []
    if "string" in allowed:
        names.append("string")
    if allowed.intersection({"integer", "number"}):
        names.append("number")
    if "boolean" in allowed:
        names.append("boolean")
    names.extend(sorted(allowed - {"string", "integer", "number", "boolean"}))
    return " | ".join(names)


def _error_type_label(allowed: frozenset[str]) -> str:
    return _type_label(allowed).replace(" | ", " or ")


def bindable_prop_type_labels(tag: str) -> dict[str, str]:
    return {
        prop: _type_label(allowed)
        for prop, allowed in BINDABLE_PROP_TYPES.get(tag, {}).items()
    }


def _type_is_allowed(actual: str, allowed: frozenset[str]) -> bool:
    return actual in allowed


def is_formatted_percentage(value: Any) -> bool:
    return isinstance(value, str) and _FORMATTED_PERCENTAGE.fullmatch(value) is not None


def _formatted_progress_value_error(
    tag: str,
    prop: str,
    actual: str,
    value: Any,
) -> str | None:
    if tag != "ProgressCircleSingle" or prop != "value" or actual != "string":
        return None
    if is_formatted_percentage(value):
        return None
    return (
        "<ProgressCircleSingle> prop 'value' accepts string data only when it is a "
        "complete formatted percentage such as '68%' or '43.75%'"
    )


def collect_display_prop_type_errors(element: JSXElement) -> list[str]:
    """Validate literal display Props that are not supplied through dataIds."""
    errors: list[str] = []
    expected = BINDABLE_PROP_TYPES.get(element.tag, {})
    data_ids = element.props.get("dataIds")
    bound = set(data_ids) if isinstance(data_ids, dict) else set()
    for prop, allowed in expected.items():
        if prop.startswith("items[].") or prop not in element.props or prop in bound:
            continue
        literal = element.props[prop]
        if _is_path_binding(literal):
            continue
        actual = value_type(literal)
        if not _type_is_allowed(actual, allowed):
            errors.append(
                f"<{element.tag}> prop {prop!r} expects {_error_type_label(allowed)}, "
                f"received {actual}"
            )
            continue
        formatted_error = _formatted_progress_value_error(
            element.tag,
            prop,
            actual,
            literal,
        )
        if formatted_error is not None:
            errors.append(formatted_error)

    item_expected = {
        prop.removeprefix("items[]."): allowed
        for prop, allowed in expected.items()
        if prop.startswith("items[].")
    }
    items = element.props.get("items")
    if not isinstance(items, list):
        return errors
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_ids = item.get("dataIds")
        item_bound = set(item_ids) if isinstance(item_ids, dict) else set()
        for prop, allowed in item_expected.items():
            if prop not in item or prop in item_bound:
                continue
            literal = item[prop]
            if _is_path_binding(literal):
                continue
            actual = value_type(literal)
            if not _type_is_allowed(actual, allowed):
                errors.append(
                    f"<{element.tag}> items[{index}].{prop} expects "
                    f"{_error_type_label(allowed)}, received {actual}"
                )
    return errors


def binding_value_type_error(
    tag: str,
    prop: str,
    binding_id: str,
    declared_type: str | None,
    sample_value: Any,
) -> str | None:
    allowed = BINDABLE_PROP_TYPES.get(tag, {}).get(prop)
    if allowed is None:
        return None
    actual = declared_type or value_type(sample_value)
    if _type_is_allowed(actual, allowed):
        return _formatted_progress_value_error(tag, prop, actual, sample_value)
    return (
        f"<{tag}> prop {prop!r} expects {_error_type_label(allowed)}, but data id "
        f"{binding_id!r} has type {actual}. Boolean data can only bind to a "
        "boolean Prop; use a compatible descriptive string or numeric field, "
        "or omit it."
        if actual == "boolean" and "boolean" not in allowed
        else f"<{tag}> prop {prop!r} expects {_error_type_label(allowed)}, but data id "
        f"{binding_id!r} has type {actual}"
    )


def is_boolean_text_mapping_target(tag: str, prop: str) -> bool:
    """Return whether ``prop`` is visible text that can map a boolean source."""
    allowed = BINDABLE_PROP_TYPES.get(tag, {}).get(prop, frozenset())
    return (
        "string" in allowed
        and "boolean" not in allowed
        # These Props drive progress geometry as well as text presentation.
        and (tag, prop) not in {
            ("ProgressCircleSingle", "value"),
            ("ProgressCircle", "externalText"),
        }
    )


def normalized_boolean_text_map(value: Any) -> dict[bool, str] | None:
    """Normalize the public ``{true, false}`` JSX object when it is complete."""
    if not isinstance(value, dict) or set(value) != {"true", "false"}:
        return None
    true_text = value.get("true")
    false_text = value.get("false")
    if (
        not isinstance(true_text, str)
        or not isinstance(false_text, str)
    ):
        return None
    true_text = true_text.strip()
    false_text = false_text.strip()
    if not true_text or not false_text or true_text == false_text:
        return None
    return {True: true_text, False: false_text}


def boolean_text_map_for(owner: dict[str, Any], prop: str) -> dict[bool, str] | None:
    maps = owner.get("dataValueMaps")
    if not isinstance(maps, dict):
        return None
    return normalized_boolean_text_map(maps.get(prop))


def _relocate_unambiguous_item_value_maps(
    element: JSXElement,
    allowed: frozenset[str],
) -> None:
    """Move a misplaced top-level value map to its only bound item target.

    Models occasionally put ``dataValueMaps.value`` on ``Summary`` or
    ``SecondaryBody`` while the matching ``dataIds.value`` belongs to one item.
    Moving it is structure-only and safe only when exactly one item can own it.
    Ambiguous shapes remain untouched for normal contract validation.
    """

    maps = element.props.get("dataValueMaps")
    items = element.props.get("items")
    if not isinstance(maps, dict) or not isinstance(items, list):
        return
    item_props = {
        name.removeprefix("items[].")
        for name in allowed
        if name.startswith("items[].")
    }
    top_level_props = {
        name for name in allowed if not name.startswith("items[].")
    }
    remaining = dict(maps)
    for prop, value_map in maps.items():
        if prop in top_level_props or prop not in item_props:
            continue
        owners = [
            item
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("dataIds"), dict)
            and prop in item["dataIds"]
        ]
        if len(owners) != 1:
            continue
        owner = owners[0]
        item_maps = owner.get("dataValueMaps")
        if item_maps is None:
            item_maps = {}
            owner["dataValueMaps"] = item_maps
        if not isinstance(item_maps, dict) or prop in item_maps:
            continue
        item_maps[prop] = copy.deepcopy(value_map)
        remaining.pop(prop, None)
    if remaining:
        element.props["dataValueMaps"] = remaining
    else:
        element.props.pop("dataValueMaps", None)


def data_model_expression_reference(path: str) -> str:
    """Return an A2UI Expression reference for an absolute JSON Pointer."""
    _pointer_segments(path)
    if "}" in path:
        raise ValidationError(
            f"data binding path cannot contain '}}' inside an A2UI Expression: {path!r}"
        )
    return f"${{{path}}}"


def expression_string_literal(value: str) -> str:
    """Quote one static string for the restricted A2UI Expression grammar."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f"'{escaped}'"


def a2ui_expression(parts: list[str]) -> str:
    """Wrap already-safe atoms as one complete responsive A2UI Expression."""
    if not parts:
        raise ValidationError("A2UI Expression requires at least one atom")
    return "{{ " + " + ".join(parts) + " }}"


def boolean_text_expression(path: str, value_map: dict[bool, str]) -> str:
    """Lower one complete boolean text map to a responsive A2UI expression."""
    reference = data_model_expression_reference(path)
    return (
        f"{{{{ {reference} ? {expression_string_literal(value_map[True])} "
        f": {expression_string_literal(value_map[False])} }}}}"
    )


def _resolved_display_value(
    element: JSXElement,
    compile_context: CompileContext,
    prop: str,
    *,
    item: dict[str, Any] | None = None,
) -> tuple[Any, DataBinding | None]:
    owner = item if item is not None else element.props
    data_ids = owner.get("dataIds")
    binding_id = data_ids.get(prop) if isinstance(data_ids, dict) else None
    if isinstance(binding_id, str):
        try:
            binding = compile_context.data_binding(binding_id)
        except ValidationError:
            binding = None
        if binding is not None:
            return binding.value, binding
    return owner.get(prop), None


def status_binding_evidence(binding: DataBinding) -> tuple[bool, bool]:
    """Return independent identifier and description evidence for status semantics."""
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", binding.id)
    identifier_words = {
        word.casefold()
        for word in re.split(r"[^A-Za-z0-9]+", separated)
        if word
    }
    identifier_match = bool(identifier_words & _STATUS_ID_MARKERS)
    description = binding.description.casefold()
    description_match = any(
        marker in description for marker in _STATUS_DESCRIPTION_MARKERS
    )
    return identifier_match, description_match


def _value_has_exact_trailing_unit(value: str, unit: str) -> bool:
    """Return true only when rendering ``value + unit`` provably repeats the unit."""
    normalized_value = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized_unit = unicodedata.normalize("NFKC", unit).strip().casefold()
    if not normalized_unit or not normalized_value.endswith(normalized_unit):
        return False
    prefix = normalized_value[:-len(normalized_unit)].rstrip()
    return bool(prefix) and prefix[-1].isdigit()


def collect_display_semantic_errors(
    element: JSXElement,
    compile_context: CompileContext,
) -> list[str]:
    """Validate value/unit meaning without guessing visual text geometry."""
    if element.tag not in _VALUE_UNIT_COMPONENTS:
        return []

    errors: list[str] = []

    def validate_pair(owner: dict[str, Any], where: str) -> None:
        value, _value_binding = _resolved_display_value(
            element,
            compile_context,
            "value",
            item=owner,
        )
        unit, _unit_binding = _resolved_display_value(
            element,
            compile_context,
            "unit",
            item=owner,
        )
        if not isinstance(value, str) or not isinstance(unit, str):
            return
        if _value_has_exact_trailing_unit(value, unit):
            errors.append(
                f"<{element.tag}> {where}value={value!r} already contains the exact trailing "
                f"unit {unit!r}; do not append the same unit again"
            )

    items = element.props.get("items")
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                validate_pair(item, f"items[{index}].")
    elif "value" in element.props:
        validate_pair(element.props, "")
    return errors


def _json_safe_copy(value: Any, where: str) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{where} must be JSON serializable") from exc
    return copy.deepcopy(value)


def _pointer_segments(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise ValidationError(f"data binding path must be an absolute non-root JSON Pointer; found {path!r}")
    segments: list[str] = []
    for raw in path[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValidationError(f"data binding path has an invalid JSON Pointer escape: {path!r}")
        segments.append(raw.replace("~1", "/").replace("~0", "~"))
    return segments


def _set_pointer(root: dict[str, Any], path: str, value: Any) -> None:
    segments = _pointer_segments(path)
    node: Any = root
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if isinstance(node, list):
            if not segment.isdigit():
                raise ValidationError(f"data binding path expects an array index at {path!r}")
            item_index = int(segment)
            while len(node) <= item_index:
                node.append(None)
            if last:
                existing = node[item_index]
                if existing is not None and existing != value:
                    raise ValidationError(f"conflicting data binding values at {path!r}")
                node[item_index] = copy.deepcopy(value)
                return
            next_container: Any = [] if segments[index + 1].isdigit() else {}
            existing = node[item_index]
            if existing is None:
                node[item_index] = next_container
            elif not isinstance(existing, (dict, list)):
                raise ValidationError(f"data binding path conflicts with a scalar parent at {path!r}")
            node = node[item_index]
            continue

        if not isinstance(node, dict):
            raise ValidationError(f"data binding path conflicts with a scalar parent at {path!r}")
        if last:
            if segment in node and node[segment] != value:
                raise ValidationError(f"conflicting data binding values at {path!r}")
            node[segment] = copy.deepcopy(value)
            return
        next_container = [] if segments[index + 1].isdigit() else {}
        if segment not in node:
            node[segment] = next_container
        elif not isinstance(node[segment], (dict, list)):
            raise ValidationError(f"data binding path conflicts with a scalar parent at {path!r}")
        node = node[segment]


@dataclass(frozen=True, slots=True)
class DataBinding:
    id: str
    path: str
    value: Any
    description: str = ""
    data_type: str | None = None

    @classmethod
    def from_payload(cls, value: Any, index: int) -> "DataBinding":
        if not isinstance(value, dict):
            raise ValidationError(f"compile context data[{index}] must be an object")
        binding_id = value.get("id")
        if not isinstance(binding_id, str) or not binding_id.strip():
            raise ValidationError(f"compile context data[{index}].id must be a non-empty string")
        if binding_id != binding_id.strip():
            raise ValidationError(f"compile context data[{index}].id must not contain surrounding whitespace")
        path = value.get("path")
        _pointer_segments(path)
        if "value" not in value:
            raise ValidationError(f"compile context data[{index}] requires value")
        description = value.get("description", "")
        if not isinstance(description, str):
            raise ValidationError(f"compile context data[{index}].description must be a string")
        data_type = value.get("type")
        if data_type is not None and (not isinstance(data_type, str) or not data_type.strip()):
            raise ValidationError(f"compile context data[{index}].type must be a non-empty string")
        return cls(
            id=binding_id.strip(),
            path=path,
            value=_json_safe_copy(value["value"], f"compile context data[{index}].value"),
            description=description,
            data_type=data_type.strip().lower() if isinstance(data_type, str) else None,
        )

    def payload(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "path": self.path,
            "description": self.description,
            "value": copy.deepcopy(self.value),
        }
        if self.data_type is not None:
            result["type"] = self.data_type
        return result


@dataclass(frozen=True, slots=True)
class ActionBinding:
    id: str
    handler: dict[str, Any]
    description: str | None = None

    @classmethod
    def from_payload(cls, value: Any, index: int) -> "ActionBinding":
        if not isinstance(value, dict):
            raise ValidationError(f"compile context actions[{index}] must be an object")
        action_id = value.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise ValidationError(f"compile context actions[{index}].id must be a non-empty string")
        if action_id != action_id.strip():
            raise ValidationError(f"compile context actions[{index}].id must not contain surrounding whitespace")
        description = value.get("description")
        if description is not None and (not isinstance(description, str) or not description.strip()):
            raise ValidationError(f"compile context actions[{index}].description must be a non-empty string")
        handler = {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key not in {"id", "description"}
        }
        if not isinstance(handler.get("call"), str) or not handler["call"].strip():
            raise ValidationError(f"compile context actions[{index}].call must be a non-empty string")
        if not isinstance(handler.get("args"), dict):
            raise ValidationError(f"compile context actions[{index}].args must be an object")
        return cls(
            id=action_id.strip(),
            handler=_json_safe_copy(handler, f"compile context actions[{index}]"),
            description=description,
        )

    def payload(self) -> dict[str, Any]:
        result = {"id": self.id}
        if self.description is not None:
            result["description"] = self.description
        result.update(copy.deepcopy(self.handler))
        return result


@dataclass(slots=True)
class CompileContext:
    data: dict[str, DataBinding] = field(default_factory=dict)
    actions: dict[str, ActionBinding] = field(default_factory=dict)
    data_model: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, value: Any) -> "CompileContext":
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValidationError("compile context must be an object")
        unknown = set(value) - {"data", "actions"}
        if unknown:
            raise ValidationError(f"compile context has unsupported fields {sorted(unknown)}")
        raw_data = value.get("data", [])
        raw_actions = value.get("actions", [])
        if not isinstance(raw_data, list):
            raise ValidationError("compile context data must be an array")
        if not isinstance(raw_actions, list):
            raise ValidationError("compile context actions must be an array")

        data: dict[str, DataBinding] = {}
        paths: dict[str, str] = {}
        data_model: dict[str, Any] = {}
        for index, item in enumerate(raw_data):
            binding = DataBinding.from_payload(item, index)
            if binding.id in data:
                raise ValidationError(f"duplicate data binding id {binding.id!r}")
            if binding.path in paths:
                raise ValidationError(
                    f"duplicate data binding path {binding.path!r} for {paths[binding.path]!r} and {binding.id!r}"
                )
            data[binding.id] = binding
            paths[binding.path] = binding.id
            _set_pointer(data_model, binding.path, binding.value)

        actions: dict[str, ActionBinding] = {}
        for index, item in enumerate(raw_actions):
            action = ActionBinding.from_payload(item, index)
            if action.id in actions:
                raise ValidationError(f"duplicate action id {action.id!r}")
            actions[action.id] = action
        return cls(data=data, actions=actions, data_model=data_model)

    def payload(self) -> dict[str, Any]:
        return {
            "data": [item.payload() for item in self.data.values()],
            "actions": [item.payload() for item in self.actions.values()],
        }

    def data_binding(self, binding_id: str) -> DataBinding:
        try:
            return self.data[binding_id]
        except KeyError as exc:
            raise ValidationError(f"unknown data binding id {binding_id!r}") from exc

    def action_binding(self, action_id: str) -> ActionBinding:
        try:
            return self.actions[action_id]
        except KeyError as exc:
            raise ValidationError(f"unknown action id {action_id!r}") from exc


def materialize_binding_literals(element: JSXElement, compile_context: CompileContext) -> None:
    """Make bound samples authoritative in normalized JSX and A2UI output."""

    allowed = BINDABLE_PROPS.get(element.tag, frozenset())
    _relocate_unambiguous_item_value_maps(element, allowed)
    data_ids = element.props.get("dataIds")
    if isinstance(data_ids, dict):
        top_level = {name for name in allowed if not name.startswith("items[].")}
        for prop, binding_id in data_ids.items():
            binding_ids = data_binding_ids(element.tag, prop, binding_id)
            if prop not in top_level or binding_ids is None:
                continue
            if len(binding_ids) > 1:
                try:
                    bindings = [
                        compile_context.data_binding(item)
                        for item in binding_ids
                    ]
                except ValidationError:
                    continue
                element.props[prop] = EVENT_TIME_RANGE_SEPARATOR.join(
                    str(binding.value) for binding in bindings
                )
                continue
            try:
                binding = compile_context.data_binding(binding_ids[0])
            except ValidationError:
                continue
            value_map = boolean_text_map_for(element.props, prop)
            if value_map is not None and isinstance(binding.value, bool):
                element.props[prop] = value_map[binding.value]
            else:
                element.props[prop] = copy.deepcopy(binding.value)
        if element.tag == "EmphasizedData":
            value_id = data_ids.get("value")
            if isinstance(value_id, str):
                try:
                    value_binding = compile_context.data_binding(value_id)
                except ValidationError:
                    value_binding = None
                if (
                    value_binding is not None
                    and isinstance(value_binding.value, str)
                    and normalize_display_value(value_binding.value).mode == "parts"
                    and "unit" not in data_ids
                ):
                    element.props.pop("unit", None)

    item_props = {
        name.removeprefix("items[].")
        for name in allowed
        if name.startswith("items[].")
    }
    items = element.props.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            item_ids = item.get("dataIds")
            if not isinstance(item_ids, dict):
                continue
            for prop, binding_id in item_ids.items():
                if prop not in item_props or not isinstance(binding_id, str):
                    continue
                try:
                    binding = compile_context.data_binding(binding_id)
                except ValidationError:
                    continue
                value_map = boolean_text_map_for(item, prop)
                if value_map is not None and isinstance(binding.value, bool):
                    item[prop] = value_map[binding.value]
                else:
                    item[prop] = copy.deepcopy(binding.value)
            if element.tag == "EmphasizedData":
                value_id = item_ids.get("value")
                if isinstance(value_id, str):
                    try:
                        value_binding = compile_context.data_binding(value_id)
                    except ValidationError:
                        value_binding = None
                    if (
                        value_binding is not None
                        and isinstance(value_binding.value, str)
                        and normalize_display_value(value_binding.value).mode == "parts"
                        and "unit" not in item_ids
                    ):
                        item.pop("unit", None)

    # Legacy model output sometimes split one complete formatted string into a
    # bound first item plus invented, unbound sibling items.  Canonicalize that
    # shape to the new single-source contract before validation and lowering.
    if element.tag == "EmphasizedData" and isinstance(items, list):
        bound_formatted: list[tuple[str, DataBinding]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_ids = item.get("dataIds")
            binding_id = item_ids.get("value") if isinstance(item_ids, dict) else None
            if not isinstance(binding_id, str):
                continue
            try:
                binding = compile_context.data_binding(binding_id)
            except ValidationError:
                continue
            if (
                isinstance(binding.value, str)
                and normalize_display_value(binding.value).mode == "parts"
            ):
                bound_formatted.append((binding_id, binding))
        if len(bound_formatted) == 1 and all(
            not isinstance(item, dict)
            or not isinstance(item.get("dataIds"), dict)
            or item["dataIds"].get("value") == bound_formatted[0][0]
            for item in items
        ):
            binding_id, binding = bound_formatted[0]
            element.props.pop("items", None)
            element.props.pop("unit", None)
            element.props["value"] = copy.deepcopy(binding.value)
            element.props["dataIds"] = {"value": binding_id}

    for child in element.child_elements():
        materialize_binding_literals(child, compile_context)
