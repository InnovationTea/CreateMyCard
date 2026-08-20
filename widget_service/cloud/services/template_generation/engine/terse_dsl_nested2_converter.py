# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Parse TerseDSL-Nested-2 as data and convert it to standard A2UI JSONL."""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from dataclasses import dataclass
from typing import Any

from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)

MAX_INPUT_LENGTH = 1_048_576
MAX_COMPONENTS = 256
MAX_NESTING_DEPTH = 32
MAX_STRING_LENGTH = 65_536
MAX_COLLECTION_ITEMS = 256
MAX_OBJECT_FIELDS = 128

_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_CONTAINERS = frozenset({"Row", "Column", "List", "Stack"})
_LEAVES = frozenset({"Text", "Image", "Divider", "Progress", "Button", "Checkbox"})
_COMPONENTS = _CONTAINERS | _LEAVES
_DATA_PLACEHOLDER = re.compile(r"^\$\{(data(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\d+)+)\}$")
_TEXT_DESIGNS = {
    "title": {"fontSize": 20, "fontWeight": 700, "fontColor": "font_primary"},
    "compact-title": {"fontSize": 14, "fontWeight": 700, "fontColor": "font_primary"},
    "compact-action": {"fontSize": 12, "fontWeight": 600, "fontColor": "font_primary"},
    "body": {"fontSize": 14, "fontWeight": 400, "fontColor": "font_primary"},
    "subtitle": {"fontSize": 12, "fontWeight": 500, "fontColor": "font_secondary"},
    "success": {"fontSize": 14, "fontWeight": 600, "fontColor": "confirm"},
    "warning": {"fontSize": 14, "fontWeight": 600, "fontColor": "warning"},
}
_IMAGE_DESIGNS = {
    "icon": {"width": 24, "height": 24, "objectFit": "contain"},
    "compact-icon": {"width": 16, "height": 16, "objectFit": "contain"},
    "thumbnail": {"width": 40, "height": 40, "objectFit": "cover", "borderRadius": 10},
    "hero": {"width": 64, "height": 64, "objectFit": "contain"},
}
_BUTTON_DESIGNS = {
    "default": {
        "height": 32,
        "padding": {"left": 10, "top": 0, "right": 10, "bottom": 0},
        "borderRadius": 16,
        "backgroundColor": "comp_background_tertiary",
        "fontColor": "font_emphasize",
        "fontSize": 12,
    },
    "primary": {
        "height": 32,
        "padding": {"left": 10, "top": 0, "right": 10, "bottom": 0},
        "borderRadius": 16,
        "backgroundColor": "background_emphasize",
        "fontColor": "font_on_primary",
        "fontSize": 12,
    },
    "small": {
        "height": 28,
        "padding": {"left": 8, "top": 0, "right": 8, "bottom": 0},
        "borderRadius": 14,
        "backgroundColor": "comp_background_tertiary",
        "fontColor": "font_emphasize",
        "fontSize": 10,
    },
}


class TerseDslNested2ConversionError(ValueError):
    """Raised when Nested-2 cannot be safely converted to A2UI."""


@dataclass(frozen=True)
class Nested2Node:
    component_type: str
    values: tuple[Any, ...]
    children: tuple[Nested2Node, ...]


def convert_terse_dsl_nested2_to_a2ui(
    source: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    task_spec: dict[str, Any] | None = None,
) -> str:
    """Convert one literal-only Nested-2 component tree to three A2UI messages."""
    root, data_model = _parse_terse_dsl_nested2_document(source)
    allowed_binding_paths = _task_spec_leaf_paths(task_spec)
    compact_rows: list[list[Any]] = []
    _append_compact_rows(root, "root", size, compact_rows, allowed_binding_paths)
    if data_model is not None:
        compact_rows.append(["/data", data_model])
    elif task_spec is not None:
        compact_rows.append(["/", _task_spec_sample_data(task_spec)])
    else:
        compact_rows.append(["/ui/state", "ready"])
    compact_dsl = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in compact_rows
    )
    try:
        return convert_compact_dsl_to_a2ui(
            compact_dsl,
            size=size,
            protocol_profile=protocol_profile,
        )
    except CompactDslConversionError as exc:
        raise TerseDslNested2ConversionError(str(exc)) from exc


def parse_terse_dsl_nested2(source: str) -> Nested2Node:
    """Parse Nested-2 with Python's AST parser, then enforce a closed data grammar."""
    root, _data_model = _parse_terse_dsl_nested2_document(source)
    return root


def _parse_terse_dsl_nested2_document(
    source: str,
) -> tuple[Nested2Node, dict[str, Any] | None]:
    """解析组件树以及模板可选的静态示例 ``data`` 对象。"""
    if not isinstance(source, str) or not source.strip():
        raise TerseDslNested2ConversionError("TerseDSL-Nested-2 output is empty.")
    if len(source) > MAX_INPUT_LENGTH:
        raise TerseDslNested2ConversionError("TerseDSL-Nested-2 input exceeds the size limit.")
    try:
        module = ast.parse(_python_compatible_source(source), mode="exec")
    except SyntaxError as exc:
        raise TerseDslNested2ConversionError(
            f"TerseDSL-Nested-2 syntax error at line {exc.lineno}: {exc.msg}."
        ) from exc
    if len(module.body) not in {1, 2} or not isinstance(module.body[0], ast.Expr):
        raise TerseDslNested2ConversionError(
            "TerseDSL-Nested-2 must contain one component call and optional data assignment."
        )
    state = {"components": 0}
    root = _parse_component(module.body[0].value, 1, state)
    if root.component_type != "Column":
        raise TerseDslNested2ConversionError("The root component must be Column.")
    if not root.values or root.values[0] != "card":
        raise TerseDslNested2ConversionError('The root must use Column("card", ...).')
    data_model = None
    if len(module.body) == 2:
        assignment = module.body[1]
        if (
            not isinstance(assignment, ast.Assign)
            or len(assignment.targets) != 1
            or not isinstance(assignment.targets[0], ast.Name)
            or assignment.targets[0].id != "data"
        ):
            raise TerseDslNested2ConversionError(
                "The optional second statement must assign one object to data."
            )
        parsed_data = _literal_value(assignment.value, 1)
        if not isinstance(parsed_data, dict):
            raise TerseDslNested2ConversionError("data must be one object.")
        data_model = parsed_data
    return root, data_model


def _python_compatible_source(source: str) -> str:
    """Translate only Nested-2 literal tokens; strings and component names stay untouched."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        raise TerseDslNested2ConversionError(
            f"TerseDSL-Nested-2 tokenization failed: {exc.args[0]}."
        ) from exc
    translated: list[tokenize.TokenInfo] = []
    literal_names = {"true": "True", "false": "False", "null": "None"}
    for index, token in enumerate(tokens):
        value = literal_names.get(token.string, token.string)
        if token.type == tokenize.NAME and _next_token_is_colon(tokens, index):
            value = repr(token.string)
            token_type = tokenize.STRING
        else:
            token_type = token.type
        translated.append(
            tokenize.TokenInfo(
                token_type,
                value,
                token.start,
                token.end,
                token.line,
            )
        )
    return tokenize.untokenize(translated)


def _next_token_is_colon(
    tokens: list[tokenize.TokenInfo],
    index: int,
) -> bool:
    ignored = {
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
    }
    for candidate in tokens[index + 1 :]:
        if candidate.type in ignored:
            continue
        return candidate.type == tokenize.OP and candidate.string == ":"
    return False


def _parse_component(node: ast.AST, depth: int, state: dict[str, int]) -> Nested2Node:
    if depth > MAX_NESTING_DEPTH:
        raise TerseDslNested2ConversionError("Component nesting exceeds 32 levels.")
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise TerseDslNested2ConversionError("Only direct Catalog component calls are allowed.")
    component_type = node.func.id
    if component_type not in _COMPONENTS:
        raise TerseDslNested2ConversionError(f'Unsupported component type "{component_type}".')
    if node.keywords:
        raise TerseDslNested2ConversionError("Keyword arguments are not allowed.")
    state["components"] += 1
    if state["components"] > MAX_COMPONENTS:
        raise TerseDslNested2ConversionError("Component count exceeds 256.")

    values: list[Any] = []
    children: list[Nested2Node] = []
    child_started = False
    for argument in node.args:
        if isinstance(argument, ast.Call):
            child_started = True
            children.append(_parse_component(argument, depth + 1, state))
            continue
        if child_started:
            raise TerseDslNested2ConversionError(
                "Value arguments must appear before the first child."
            )
        values.append(_literal_value(argument, depth))
    if children and component_type not in _CONTAINERS:
        raise TerseDslNested2ConversionError(f"{component_type} cannot contain child components.")
    return Nested2Node(component_type, tuple(values), tuple(children))


def _literal_value(node: ast.AST, depth: int) -> Any:
    if depth > MAX_NESTING_DEPTH:
        raise TerseDslNested2ConversionError("Literal nesting exceeds 32 levels.")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and len(node.value) > MAX_STRING_LENGTH:
            raise TerseDslNested2ConversionError("String literal exceeds the size limit.")
        if node.value is None or isinstance(node.value, (str, int, float, bool)):
            return node.value
    if isinstance(node, ast.List):
        if len(node.elts) > MAX_COLLECTION_ITEMS:
            raise TerseDslNested2ConversionError("Array literal exceeds the item limit.")
        return [_literal_value(item, depth + 1) for item in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _literal_value(node.operand, depth + 1)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            raise TerseDslNested2ConversionError(
                "Unary signs are only allowed on numeric literals."
            )
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.Dict):
        if len(node.keys) > MAX_OBJECT_FIELDS:
            raise TerseDslNested2ConversionError("Object literal exceeds the field limit.")
        result: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            key = _literal_value(key_node, depth + 1)
            if not isinstance(key, str):
                raise TerseDslNested2ConversionError("Object keys must be strings.")
            if key in _FORBIDDEN_KEYS:
                raise TerseDslNested2ConversionError(f'Forbidden object key "{key}".')
            if key in result:
                raise TerseDslNested2ConversionError(f'Duplicate object key "{key}".')
            result[key] = _literal_value(value_node, depth + 1)
        return result
    raise TerseDslNested2ConversionError(
        "Only string, number, boolean, null, array, and object literals are allowed."
    )


def _append_compact_rows(
    node: Nested2Node,
    component_id: str,
    size: str,
    rows: list[list[Any]],
    allowed_binding_paths: frozenset[str],
) -> None:
    child_ids = [
        _explicit_component_id(child) or f"{component_id}_{index}"
        for index, child in enumerate(node.children)
    ]
    props = _convert_data_placeholders(
        _component_props(node, component_id, size),
        allowed_binding_paths,
    )
    row: list[Any] = [component_id, node.component_type, props]
    if node.component_type in _CONTAINERS:
        row.append(child_ids)
    rows.append(row)
    for child, child_id in zip(node.children, child_ids, strict=True):
        _append_compact_rows(child, child_id, size, rows, allowed_binding_paths)


def bind_task_spec_values(root: Nested2Node, task_spec: dict[str, Any]) -> Nested2Node:
    """Bind exact advanced-component facts to their declared TaskSpec leaf paths."""
    bindings = _unique_task_spec_sample_bindings(task_spec)
    counters: dict[str, int] = {}

    def consume(key: str) -> str | None:
        paths = bindings.get(key)
        if not paths:
            return None
        if len(paths) == 1:
            return paths[0]
        idx = counters.get(key, 0)
        if idx >= len(paths):
            return None
        counters[key] = idx + 1
        return paths[idx]

    def bind(node: Nested2Node) -> Nested2Node:
        children = tuple(bind(child) for child in node.children)
        values = list(node.values)
        if node.component_type == "Text" and values:
            placeholder = consume(_stable_sample_key(values[0]))
            if placeholder is None:
                placeholder = _coerced_consume(values[0], consume)
            if placeholder is not None:
                values[0] = placeholder
        if node.component_type in {"Progress", "Checkbox"}:
            values = [_bind_numeric_semantic_fields(value, consume) for value in values]
        return Nested2Node(node.component_type, tuple(values), children)

    return bind(root)


def _coerced_consume(value: Any, consume) -> str | None:
    """Try numeric coercion so templates that str() an integer can still bind."""
    if not isinstance(value, str):
        return None
    try:
        coerced = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(coerced, bool) or not isinstance(coerced, (int, float)):
        return None
    return consume(_stable_sample_key(coerced))


def _bind_numeric_semantic_fields(value: Any, consume) -> Any:
    if not isinstance(value, dict):
        return value
    result = dict(value)
    for field in ("value", "total", "select"):
        if field not in result:
            continue
        placeholder = consume(_stable_sample_key(result[field]))
        if placeholder is None:
            placeholder = _coerced_consume(result[field], consume)
        if placeholder is not None:
            result[field] = placeholder
    return result


def _unique_task_spec_sample_bindings(task_spec: dict[str, Any]) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {}
    _collect_task_spec_samples(task_spec.get("dataModelSchema"), "", candidates)
    bindings: dict[str, list[str]] = {}
    for key, paths in candidates.items():
        bound: list[str] = []
        for path in paths:
            placeholder = _pointer_to_placeholder(path)
            if placeholder is not None:
                bound.append(placeholder)
        if bound:
            bindings[key] = bound
    return bindings


def _collect_task_spec_samples(
    value: Any,
    path: str,
    candidates: dict[str, list[str]],
) -> None:
    if isinstance(value, dict) and "type" in value:
        is_runtime_path = path.startswith("/data/")
        is_internal_selector = "/_advancedSelectors/" in path
        if is_runtime_path and not is_internal_selector and "sampleValue" in value:
            candidates.setdefault(_stable_sample_key(value["sampleValue"]), []).append(path)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _collect_task_spec_samples(child, f"{path}/{key}", candidates)
        return
    if isinstance(value, list) and value:
        for index, item in enumerate(value):
            _collect_task_spec_samples(item, f"{path}/{index}", candidates)


def _stable_sample_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pointer_to_placeholder(path: str) -> str | None:
    parts = path.removeprefix("/").split("/")
    valid_parts = all(
        part.isdigit() or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
        for part in parts
    )
    if not parts or parts[0] != "data" or not valid_parts:
        return None
    return "${" + ".".join(parts) + "}"


def _convert_data_placeholders(value: Any, allowed_paths: frozenset[str]) -> Any:
    if isinstance(value, str):
        match = _DATA_PLACEHOLDER.fullmatch(value)
        if match is None:
            return value
        path = "/" + match.group(1).replace(".", "/")
        if path not in allowed_paths:
            raise TerseDslNested2ConversionError(
                f"Data binding path is not a TaskSpec leaf: {path}."
            )
        return {"path": path}
    if isinstance(value, dict):
        return {
            key: _convert_data_placeholders(child, allowed_paths)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_convert_data_placeholders(child, allowed_paths) for child in value]
    return value


def _task_spec_leaf_paths(task_spec: dict[str, Any] | None) -> frozenset[str]:
    if task_spec is None:
        return frozenset()
    paths: set[str] = set()

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict) and "type" in value:
            paths.add(path)
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "_advancedSelectors":
                    continue
                visit(child, f"{path}/{key}")
        elif isinstance(value, list) and value:
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")

    visit(task_spec.get("dataModelSchema"), "")
    return frozenset(paths)


def _task_spec_sample_data(task_spec: dict[str, Any]) -> Any:
    def sample(value: Any) -> Any:
        if isinstance(value, dict) and "type" in value:
            return value.get("sampleValue")
        if isinstance(value, dict):
            return {
                key: sample(child)
                for key, child in value.items()
                if key != "_advancedSelectors"
            }
        if isinstance(value, list):
            return [sample(child) for child in value]
        return value

    return sample(task_spec.get("dataModelSchema", {}))


def _explicit_component_id(node: Nested2Node) -> str | None:
    for value in reversed(node.values):
        if not isinstance(value, dict) or "_id" not in value:
            continue
        component_id = value["_id"]
        if not isinstance(component_id, str) or not component_id:
            raise TerseDslNested2ConversionError("Internal component _id must be non-empty.")
        return component_id
    return None


def _component_props(
    node: Nested2Node,
    component_id: str,
    size: str,
) -> dict[str, Any]:
    if node.component_type in _CONTAINERS:
        return _container_props(node, component_id, size)
    if node.component_type == "Text":
        return _designed_leaf_props(node, "content", _TEXT_DESIGNS)
    if node.component_type == "Image":
        return _designed_leaf_props(node, "src", _IMAGE_DESIGNS)
    if node.component_type == "Button":
        return _designed_leaf_props(node, "label", _BUTTON_DESIGNS)
    if node.component_type == "Progress":
        props: dict[str, Any] = {}
        _merge_options(props, node.values)
        return props
    if node.component_type == "Checkbox":
        props = {}
        _merge_options(props, node.values)
        return props
    if node.component_type == "Divider":
        props = {"strokeWidth": 1, "vertical": False, "color": "comp_divider"}
        _merge_options(props, node.values)
        return props
    raise TerseDslNested2ConversionError(f"{component_id}: unsupported component conversion.")


def _designed_leaf_props(
    node: Nested2Node,
    required_name: str,
    designs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not node.values:
        raise TerseDslNested2ConversionError(f"{node.component_type} requires {required_name}.")
    props = {required_name: node.values[0]}
    remaining = list(node.values[1:])
    if remaining and isinstance(remaining[0], str):
        design = remaining.pop(0)
        if design not in designs:
            raise TerseDslNested2ConversionError(
                f'Unsupported {node.component_type} design "{design}".'
            )
        props.update(designs[design])
    _merge_options(props, remaining)
    return props


def _merge_options(props: dict[str, Any], values: Any) -> None:
    values = list(values)
    if not values:
        return
    if len(values) != 1 or not isinstance(values[0], dict) or not values[0]:
        raise TerseDslNested2ConversionError(
            "Options must be one non-empty object in the final value position."
        )
    props.update({key: value for key, value in values[0].items() if key != "_id"})


def _container_props(
    node: Nested2Node,
    component_id: str,
    size: str,
) -> dict[str, Any]:
    values = list(node.values)
    layout = values.pop(0) if values and isinstance(values[0], str) else None
    props: dict[str, Any] = {}
    _merge_options(props, values)
    layouts = {
        ("Column", "section"): {"width": "matchParent", "itemMargin": 6},
        ("Column", "compact"): {"width": "matchParent", "itemMargin": 4},
        ("Row", "between"): {
            "width": "matchParent",
            "itemMargin": 4,
            "justifyContent": "spaceBetween",
            "alignItems": "center",
        },
        ("Row", "actions"): {
            "width": "matchParent",
            "itemMargin": 4,
            "justifyContent": "end",
            "alignItems": "center",
        },
        ("List", "list"): {"width": "matchParent", "space": 6},
        ("List", "dense"): {"width": "matchParent", "space": 4},
        ("Stack", "overlay"): {"width": "matchParent", "height": "matchParent"},
    }
    if component_id == "root":
        dimensions = {
            "2x2": {"width": 160, "height": 160},
            "2x4": {"width": 320, "height": 160},
        }.get(size)
        if node.component_type != "Column" or layout != "card" or dimensions is None:
            raise TerseDslNested2ConversionError(
                'Root must be Column("card", ...) with a supported size.'
            )
        locked = {
            **dimensions,
            "padding": 12,
            "borderRadius": 20,
            "clip": True,
            "backgroundColor": "background_primary",
            "itemMargin": 8,
        }
        if "width" in props or "height" in props:
            raise TerseDslNested2ConversionError(
                "Root options cannot override the size-locked width or height."
            )
        return {**locked, **props}
    if layout is None:
        return props
    preset = layouts.get((node.component_type, layout))
    if preset is None:
        raise TerseDslNested2ConversionError(
            f'Unsupported {node.component_type} layout "{layout}".'
        )
    return {**preset, **props}
