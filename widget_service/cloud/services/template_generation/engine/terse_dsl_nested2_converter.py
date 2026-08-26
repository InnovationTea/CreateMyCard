# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Parse the restricted Tersel data protocol and convert it to A2UI JSONL.

The module path and legacy public names are retained for callers that still use
the former ``TerseDSL-Nested-2`` identifier.
"""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from dataclasses import dataclass
from typing import Any

from services.a2ui_expression import (
    A2UIExpressionError,
    normalize_terse_expression,
    normalize_wrapped_expression,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.template_generation.engine.theme_reference import (
    THEME_REFERENCE_PATHS,
    ThemeReferenceSyntaxError,
    translate_theme_reference_calls,
)

MAX_INPUT_LENGTH = 1_048_576
MAX_COMPONENTS = 256
MAX_NESTING_DEPTH = 32
MAX_STRING_LENGTH = 65_536
MAX_COLLECTION_ITEMS = 256
MAX_OBJECT_FIELDS = 128

_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_INTERNAL_DATA_KEYS = frozenset({"_advancedSelectors", "_templateProjection"})
_CONTAINERS = frozenset({"Row", "Column", "List", "Stack"})
_LEAVES = frozenset({"Text", "Image", "Divider", "Progress", "Button", "Checkbox"})
_COMPONENTS = _CONTAINERS | _LEAVES
_DATA_PLACEHOLDER = re.compile(r"^\$\{(data(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\d+)+)\}$")
_A2UI_DATA_REFERENCE = re.compile(
    r"\$\{(/data(?:/[A-Za-z_][A-Za-z0-9_]*|/\d+)+)\}"
)
_THEME_COLOR = re.compile(r"^#[0-9A-Fa-f]{8}$")
_THEME_REFERENCE_CALL = "_TerselTheme"
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
_CONTAINER_DESIGNS = {
    "Column": {
        "card": {},
        "section": {"width": "matchParent", "itemMargin": 6},
        "compact": {"width": "matchParent", "itemMargin": 4},
    },
    "Row": {
        "between": {
            "width": "matchParent",
            "itemMargin": 4,
            "justifyContent": "spaceBetween",
            "alignItems": "center",
        },
        "actions": {
            "width": "matchParent",
            "itemMargin": 4,
            "justifyContent": "end",
            "alignItems": "center",
        },
    },
    "List": {
        "list": {"width": "matchParent", "space": 6},
        "dense": {"width": "matchParent", "space": 4},
    },
    "Stack": {
        "card": {},
        "overlay": {"width": "matchParent", "height": "matchParent"},
    },
}
_DESIGN_TOKEN_ALIASES = {
    ("Column", "Card"): "card",
    ("Column", "Section"): "section",
    ("Column", "Compact"): "compact",
    ("Row", "Between"): "between",
    ("Row", "Actions"): "actions",
    ("List", "List"): "list",
    ("List", "Dense"): "dense",
    ("Stack", "Card"): "card",
    ("Stack", "Overlay"): "overlay",
}


class TerseDslNested2ConversionError(ValueError):
    """Raised when Tersel cannot be safely converted to A2UI."""


@dataclass(frozen=True)
class Nested2Node:
    component_type: str
    values: tuple[Any, ...]
    children: tuple[Nested2Node, ...]


def convert_tersel_to_a2ui(
    source: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    task_spec: dict[str, Any] | None = None,
    theme_values: dict[str, str] | None = None,
) -> str:
    """Convert one restricted Tersel component tree to three A2UI messages."""
    root, data_model = _parse_terse_dsl_nested2_document(source, theme_values)
    allowed_binding_paths = _task_spec_leaf_paths(task_spec)
    allowed_expression_paths = _task_spec_paths(task_spec)
    referenced_paths = _node_binding_paths(root)
    if task_spec is not None:
        unknown_paths = referenced_paths - allowed_expression_paths
        if unknown_paths:
            raise TerseDslNested2ConversionError(
                f"Expression references paths outside TaskSpec: {sorted(unknown_paths)}."
            )
    if data_model is not None:
        data_paths = _validate_data_model(
            data_model,
            allowed_expression_paths,
            allowed_binding_paths,
            task_spec is not None,
        )
        missing_paths = referenced_paths - data_paths
        if missing_paths:
            raise TerseDslNested2ConversionError(
                f"Data document is missing component binding paths: {sorted(missing_paths)}."
            )
    compact_rows: list[list[Any]] = []
    _append_compact_rows(
        root,
        "root",
        size,
        compact_rows,
        allowed_binding_paths,
        allowed_expression_paths,
    )
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


def convert_terse_dsl_nested2_to_a2ui(
    source: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    task_spec: dict[str, Any] | None = None,
    theme_values: dict[str, str] | None = None,
) -> str:
    """Compatibility alias for :func:`convert_tersel_to_a2ui`."""
    return convert_tersel_to_a2ui(
        source,
        size=size,
        protocol_profile=protocol_profile,
        task_spec=task_spec,
        theme_values=theme_values,
    )


def parse_tersel(
    source: str,
    *,
    theme_values: dict[str, str] | None = None,
) -> Nested2Node:
    """Parse Tersel with Python's AST parser and enforce a closed data grammar."""
    root, _data_model = _parse_terse_dsl_nested2_document(source, theme_values)
    return root


def parse_terse_dsl_nested2(
    source: str,
    *,
    theme_values: dict[str, str] | None = None,
) -> Nested2Node:
    """Compatibility alias for :func:`parse_tersel`."""
    return parse_tersel(source, theme_values=theme_values)


def _parse_terse_dsl_nested2_document(
    source: str,
    theme_values: dict[str, str] | None = None,
) -> tuple[Nested2Node, dict[str, Any] | None]:
    """解析组件树以及模板可选的静态示例 ``data`` 对象。"""
    if not isinstance(source, str) or not source.strip():
        raise TerseDslNested2ConversionError("Tersel output is empty.")
    if len(source) > MAX_INPUT_LENGTH:
        raise TerseDslNested2ConversionError("Tersel input exceeds the size limit.")
    try:
        translated = translate_theme_reference_calls(source, _THEME_REFERENCE_CALL)
        module = ast.parse(_python_compatible_source(translated), mode="exec")
    except ThemeReferenceSyntaxError as exc:
        raise TerseDslNested2ConversionError(str(exc)) from exc
    except SyntaxError as exc:
        raise TerseDslNested2ConversionError(
            f"Tersel syntax error at line {exc.lineno}: {exc.msg}."
        ) from exc
    if len(module.body) not in {1, 2} or not isinstance(module.body[0], ast.Expr):
        raise TerseDslNested2ConversionError(
            "Tersel must contain one component call and optional data assignment."
        )
    state = {"components": 0}
    root = _parse_component(module.body[0].value, 1, state, theme_values or {})
    if root.component_type not in {"Column", "Stack"}:
        raise TerseDslNested2ConversionError("The root component must be Column or Stack.")
    data_model = None
    if len(module.body) == 2:
        assignment = module.body[1]
        is_single_assignment = isinstance(assignment, ast.Assign) and len(assignment.targets) == 1
        target = assignment.targets[0] if is_single_assignment else None
        is_data_target = isinstance(target, ast.Name) and target.id == "data"
        if not is_single_assignment or not is_data_target:
            raise TerseDslNested2ConversionError(
                "The optional second statement must assign one object to data."
            )
        assert isinstance(assignment, ast.Assign)
        parsed_data = _literal_value(assignment.value, 1)
        if not isinstance(parsed_data, dict):
            raise TerseDslNested2ConversionError("data must be one object.")
        data_model = parsed_data
    return root, data_model


def _python_compatible_source(source: str) -> str:
    """Translate only Tersel literal tokens; strings and component names stay untouched."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        raise TerseDslNested2ConversionError(
            f"Tersel tokenization failed: {exc.args[0]}."
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
    for candidate in tokens[slice(index + 1, None)]:
        if candidate.type in ignored:
            continue
        return candidate.type == tokenize.OP and candidate.string == ":"
    return False


def _parse_component(
    node: ast.AST,
    depth: int,
    state: dict[str, int],
    theme_values: dict[str, str],
) -> Nested2Node:
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
        if _is_expression_call(argument) or _is_theme_reference_call(argument):
            if child_started:
                raise TerseDslNested2ConversionError(
                    "Value arguments must appear before the first child."
                )
            values.append(
                _literal_value(
                    argument,
                    depth,
                    allow_expression=True,
                    theme_values=theme_values,
                )
            )
            continue
        if isinstance(argument, ast.Call):
            child_started = True
            children.append(_parse_component(argument, depth + 1, state, theme_values))
            continue
        if child_started:
            raise TerseDslNested2ConversionError(
                "Value arguments must appear before the first child."
            )
        values.append(
            _literal_value(
                argument,
                depth,
                allow_expression=True,
                theme_values=theme_values,
            )
        )
    if children and component_type not in _CONTAINERS:
        raise TerseDslNested2ConversionError(f"{component_type} cannot contain child components.")
    return Nested2Node(component_type, tuple(values), tuple(children))


def _literal_value(
    node: ast.AST,
    depth: int,
    *,
    allow_expression: bool = False,
    theme_values: dict[str, str] | None = None,
) -> Any:
    if depth > MAX_NESTING_DEPTH:
        raise TerseDslNested2ConversionError("Literal nesting exceeds 32 levels.")
    if allow_expression and _is_expression_call(node):
        return _parse_expression_call(node)
    if allow_expression and _is_theme_reference_call(node):
        return _parse_theme_reference_call(node, theme_values or {})
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and len(node.value) > MAX_STRING_LENGTH:
            raise TerseDslNested2ConversionError("String literal exceeds the size limit.")
        if node.value is None or isinstance(node.value, (str, int, float, bool)):
            return node.value
    if isinstance(node, ast.List):
        if len(node.elts) > MAX_COLLECTION_ITEMS:
            raise TerseDslNested2ConversionError("Array literal exceeds the item limit.")
        return [
            _literal_value(
                item,
                depth + 1,
                allow_expression=allow_expression,
                theme_values=theme_values,
            )
            for item in node.elts
        ]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _literal_value(
            node.operand,
            depth + 1,
            allow_expression=allow_expression,
            theme_values=theme_values,
        )
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
            result[key] = _literal_value(
                value_node,
                depth + 1,
                allow_expression=allow_expression,
                theme_values=theme_values,
            )
        return result
    raise TerseDslNested2ConversionError(
        "Only string, number, boolean, null, array, and object literals are allowed."
    )


def _is_expression_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Expr"
    )


def _is_theme_reference_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _THEME_REFERENCE_CALL
    )


def _parse_theme_reference_call(
    node: ast.AST,
    theme_values: dict[str, str],
) -> str:
    assert isinstance(node, ast.Call)
    valid_argument = len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
    path = node.args[0].value if valid_argument else None
    if node.keywords or not isinstance(path, str) or path not in THEME_REFERENCE_PATHS:
        raise TerseDslNested2ConversionError(
            "$theme requires exactly one approved Theme path."
        )
    value = theme_values.get(path)
    if not isinstance(value, str) or _THEME_COLOR.fullmatch(value) is None:
        raise TerseDslNested2ConversionError(f"Theme reference is unavailable: {path}.")
    return value


def _parse_expression_call(node: ast.AST) -> str:
    assert isinstance(node, ast.Call)
    valid_argument = len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
    body = node.args[0].value if valid_argument else None
    if node.keywords or not isinstance(body, str):
        raise TerseDslNested2ConversionError(
            "Expr requires exactly one string argument and no keyword arguments."
        )
    try:
        return normalize_terse_expression(body).value
    except A2UIExpressionError as exc:
        raise TerseDslNested2ConversionError(f"Invalid Expr: {exc}") from exc


def _append_compact_rows(
    node: Nested2Node,
    component_id: str,
    size: str,
    rows: list[list[Any]],
    allowed_binding_paths: frozenset[str],
    allowed_expression_paths: frozenset[str],
) -> None:
    child_ids = [
        _explicit_component_id(child) or f"{component_id}_{index}"
        for index, child in enumerate(node.children)
    ]
    props = _convert_data_placeholders(
        _component_props(node, component_id, size),
        allowed_binding_paths,
        allowed_expression_paths,
    )
    row: list[Any] = [component_id, node.component_type, props]
    if node.component_type in _CONTAINERS:
        row.append(child_ids)
    rows.append(row)
    for child, child_id in zip(node.children, child_ids, strict=True):
        _append_compact_rows(
            child,
            child_id,
            size,
            rows,
            allowed_binding_paths,
            allowed_expression_paths,
        )


def _convert_data_placeholders(
    value: Any,
    allowed_binding_paths: frozenset[str],
    allowed_expression_paths: frozenset[str],
) -> Any:
    if isinstance(value, str):
        match = _DATA_PLACEHOLDER.fullmatch(value)
        if match is not None:
            path = "/" + match.group(1).replace(".", "/")
            if path not in allowed_binding_paths:
                raise TerseDslNested2ConversionError(
                    f"Data binding path is not a TaskSpec leaf: {path}."
                )
            return {"path": path}
        if "{{" in value or "}}" in value:
            try:
                normalized = normalize_wrapped_expression(value)
            except A2UIExpressionError as exc:
                raise TerseDslNested2ConversionError(f"Invalid A2UI expression: {exc}") from exc
            unknown_paths = set(normalized.references) - allowed_expression_paths
            if unknown_paths:
                raise TerseDslNested2ConversionError(
                    f"Expression references paths outside TaskSpec: {sorted(unknown_paths)}."
                )
            return normalized.value
        if "${" in value:
            raise TerseDslNested2ConversionError(
                "Data binding references must be one complete path or appear inside Expr."
            )
        return value
    if isinstance(value, dict):
        return {
            key: _convert_data_placeholders(
                child,
                allowed_binding_paths,
                allowed_expression_paths,
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _convert_data_placeholders(
                child,
                allowed_binding_paths,
                allowed_expression_paths,
            )
            for child in value
        ]
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
                if key in _INTERNAL_DATA_KEYS:
                    continue
                visit(child, f"{path}/{key}")
        elif isinstance(value, list) and value:
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")

    visit(task_spec.get("dataModelSchema"), "")
    return frozenset(paths)


def _task_spec_paths(task_spec: dict[str, Any] | None) -> frozenset[str]:
    if task_spec is None:
        return frozenset()
    paths: set[str] = set()

    def visit(value: Any, path: str) -> None:
        if path:
            paths.add(path)
        if isinstance(value, dict) and "type" not in value:
            for key, child in value.items():
                if key in _INTERNAL_DATA_KEYS:
                    continue
                visit(child, f"{path}/{key}")
        elif isinstance(value, list):
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
                if key not in _INTERNAL_DATA_KEYS
            }
        if isinstance(value, list):
            return [sample(child) for child in value]
        return value

    return sample(task_spec.get("dataModelSchema", {}))


def serialize_task_spec_data(task_spec: dict[str, Any]) -> str:
    """Serialize only the public ``/data`` preview object for a full Tersel document."""
    sample_data = _task_spec_sample_data(task_spec)
    data = sample_data.get("data", {}) if isinstance(sample_data, dict) else {}
    if not isinstance(data, dict):
        raise TerseDslNested2ConversionError("TaskSpec dataModelSchema.data must be one object.")
    _reject_internal_data_keys(data)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _validate_data_model(
    data_model: dict[str, Any],
    allowed_paths: frozenset[str],
    leaf_paths: frozenset[str],
    validate_paths: bool,
) -> frozenset[str]:
    _reject_internal_data_keys(data_model)
    data_paths: set[str] = set()

    def visit(value: Any, path: str) -> None:
        if validate_paths and path not in allowed_paths:
            raise TerseDslNested2ConversionError(
                f"Data document path is not declared by TaskSpec: {path}."
            )
        data_paths.add(path)
        if path in leaf_paths:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{path}/{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}/{index}")
            return

    visit(data_model, "/data")
    return frozenset(data_paths)


def _node_binding_paths(root: Nested2Node) -> frozenset[str]:
    paths: set[str] = set()

    def visit_value(value: Any) -> None:
        if isinstance(value, str):
            placeholder = _DATA_PLACEHOLDER.fullmatch(value)
            if placeholder is not None:
                paths.add("/" + placeholder.group(1).replace(".", "/"))
            paths.update(match.group(1) for match in _A2UI_DATA_REFERENCE.finditer(value))
        elif isinstance(value, dict):
            binding_path = value.get("path") if set(value) == {"path"} else None
            if isinstance(binding_path, str) and binding_path.startswith("/data/"):
                paths.add(binding_path)
            for child in value.values():
                visit_value(child)
        elif isinstance(value, list):
            for child in value:
                visit_value(child)

    def visit_node(node: Nested2Node) -> None:
        for value in node.values:
            visit_value(value)
        for child in node.children:
            visit_node(child)

    visit_node(root)
    return frozenset(paths)


def _reject_internal_data_keys(value: Any) -> None:
    if isinstance(value, dict):
        internal = _INTERNAL_DATA_KEYS.intersection(value)
        if internal:
            raise TerseDslNested2ConversionError(
                f"Data document contains internal projection keys: {sorted(internal)}."
            )
        for child in value.values():
            _reject_internal_data_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_internal_data_keys(child)


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
        design_token = remaining.pop(0)
        props.update(_resolve_design_token(node.component_type, design_token, designs))
    _merge_options(props, remaining)
    return props


def _resolve_design_token(
    component_type: str,
    design_token: str,
    designs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    normalized = _DESIGN_TOKEN_ALIASES.get(
        (component_type, design_token),
        design_token,
    )
    design = designs.get(normalized)
    if design is None:
        raise TerseDslNested2ConversionError(
            f'Unsupported {component_type} designToken "{design_token}".'
        )
    return dict(design)


def _merge_options(props: dict[str, Any], values: Any) -> None:
    values = list(values)
    if not values:
        return
    if len(values) != 1 or not isinstance(values[0], dict):
        raise TerseDslNested2ConversionError(
            "Inline styles must be one object in the final value position."
        )
    props.update({key: value for key, value in values[0].items() if key != "_id"})


def _container_props(
    node: Nested2Node,
    component_id: str,
    size: str,
) -> dict[str, Any]:
    values = list(node.values)
    design_token = values.pop(0) if values and isinstance(values[0], str) else None
    designs = _CONTAINER_DESIGNS[node.component_type]
    design_props = (
        _resolve_design_token(node.component_type, design_token, designs)
        if design_token is not None
        else {}
    )
    inline_props: dict[str, Any] = {}
    _merge_options(inline_props, values)
    if component_id == "root":
        dimensions = {
            "2x2": {"width": 160, "height": 160},
            "2x4": {"width": 320, "height": 160},
        }.get(size)
        if node.component_type not in {"Column", "Stack"} or dimensions is None:
            raise TerseDslNested2ConversionError(
                "Tersel root must be Column or Stack with a supported size."
            )
        if "width" in inline_props or "height" in inline_props:
            raise TerseDslNested2ConversionError(
                "Root inline styles cannot override the size-locked width or height."
            )
        locked = {
            **dimensions,
            "padding": 12,
            "borderRadius": 20,
            "clip": True,
        }
        if node.component_type == "Column":
            locked["itemMargin"] = 8
            locked["backgroundColor"] = "background_primary"
        root_design_props = {
            key: value
            for key, value in design_props.items()
            if key not in {"width", "height"}
        }
        return {**locked, **root_design_props, **inline_props}
    return {**design_props, **inline_props}


TerselConversionError = TerseDslNested2ConversionError
TerselNode = Nested2Node

__all__ = [
    "MAX_COMPONENTS",
    "MAX_INPUT_LENGTH",
    "MAX_NESTING_DEPTH",
    "MAX_OBJECT_FIELDS",
    "MAX_STRING_LENGTH",
    "Nested2Node",
    "TerseDslNested2ConversionError",
    "TerselConversionError",
    "TerselNode",
    "convert_terse_dsl_nested2_to_a2ui",
    "convert_tersel_to_a2ui",
    "parse_terse_dsl_nested2",
    "parse_tersel",
    "serialize_task_spec_data",
]
