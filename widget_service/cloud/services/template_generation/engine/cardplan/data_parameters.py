"""通用模板的数据参数：声明、编译期数组分支和受限运行时绑定。"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from services.template_generation.engine.a2ui_expression import normalize_tersel_expression
from services.template_generation.engine.tersel_converter import TerselConversionError

from .expression_types import expression_result_types
from .models import TemplateNode, TemplateValue
from .runtime_expression import parse_runtime_expression

MAX_DATA_ARRAY_ITEMS = 2
DATA_SIZE_CONDITIONS = frozenset({"IfDataSize", "IfNotDataSize"})
_FIELD = re.compile(
    r"(\.\.\.)?([A-Za-z][A-Za-z0-9_]*)(\?)?\s*:\s*"
    r"(string|number|integer|boolean)(\[\])?"
)
_FORBIDDEN_NAMES = frozenset({"__proto__", "prototype", "constructor"})


@dataclass(frozen=True)
class DataParameterType:
    """无固定路径的数据符号，仅用于模板加载时的类型与作用域校验。"""

    data_type: str


@dataclass(frozen=True)
class DataPathArgument:
    path: str


@dataclass(frozen=True)
class DataExpressionArgument:
    source: str


def split_data_signature(signature: str) -> tuple[dict[str, Any], str]:
    """提取可选 data 签名；数组是最多两个显示项的编译期参数列表。"""
    match = re.fullmatch(r"data\s*:\s*\{([^{}]*)\}\s*,\s*(props\s*:.*)", signature, re.S)
    schema: dict[str, Any] = {}
    remaining = signature
    if match is not None:
        properties: dict[str, Any] = {}
        required: list[str] = []
        array_count = 0
        for declaration in match.group(1).split(","):
            if not declaration.strip():
                continue
            field = _FIELD.fullmatch(declaration.strip())
            if field is None:
                raise ValueError(f"invalid Template data parameter: {declaration}")
            spread, name, optional, data_type, array = field.groups()
            if name in properties or name in _FORBIDDEN_NAMES:
                raise ValueError(f"invalid or duplicate Template data parameter: {name}")
            if spread and not array:
                raise ValueError("Template spread data parameter must be an array")
            item_schema: dict[str, Any] = {"type": data_type}
            if array:
                array_count += 1
                item_schema = {
                    "type": "array",
                    "items": item_schema,
                    "maxItems": MAX_DATA_ARRAY_ITEMS,
                }
            properties[name] = item_schema
            if optional is None:
                required.append(name)
        if not properties or array_count > 1:
            raise ValueError("Template data requires fields and at most one array")
        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        Draft202012Validator.check_schema(schema)
        remaining = match.group(2)
    return schema, remaining


def data_symbols(schema: dict[str, Any], count: int) -> dict[str, DataParameterType]:
    symbols: dict[str, DataParameterType] = {}
    for name, field in schema.get("properties", {}).items():
        if field.get("type") == "array":
            item_type = field.get("items", {}).get("type")
            for index in range(count):
                symbols[f"{name}[{index}]"] = DataParameterType(item_type)
        else:
            symbols[name] = DataParameterType(field.get("type"))
    return symbols


def select_data_size(root: TemplateNode, schema: dict[str, Any], count: int) -> TemplateNode:
    """在模板加载与实例化时按参数列表长度裁剪分支，不读取端侧样例值。"""
    children: list[TemplateNode] = []
    for child in root.children:
        if child.component in DATA_SIZE_CONDITIONS:
            name = child.values[0].value
            size = child.values[1].value
            field = schema.get("properties", {}).get(name, {})
            if field.get("type") != "array":
                raise ValueError(f"Template size condition requires a data array: {name}")
            selected = count == size
            if child.component == "IfNotDataSize":
                selected = not selected
            # 即使分支不可达，也验证其内部数组条件的声明。
            resolved = select_data_size(child, schema, count)
            if selected:
                children.extend(resolved.children)
        else:
            children.append(select_data_size(child, schema, count))
    return root.model_copy(update={"children": tuple(children)})


def array_size(schema: dict[str, Any], data: dict[str, Any]) -> int:
    count = 0
    for name, field in schema.get("properties", {}).items():
        if field.get("type") == "array":
            values = data.get(name, [])
            if not isinstance(values, list):
                raise TerselConversionError(f"Template data array is invalid: {name}")
            count = len(values)
    return count


def data_argument_from_ast(node: ast.Call) -> DataPathArgument | DataExpressionArgument:
    if not isinstance(node.func, ast.Name) or node.keywords or len(node.args) != 1:
        raise TerselConversionError("Template data call requires exactly one argument")
    argument = node.args[0]
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        raise TerselConversionError("Template data call requires a string argument")
    result: DataPathArgument | DataExpressionArgument
    if node.func.id == "_CardPlanDataPath":
        result = DataPathArgument(argument.value)
    elif node.func.id == "_CardTplRuntimeExpr":
        result = DataExpressionArgument(argument.value)
    else:
        raise TerselConversionError("Only $path and Expr are allowed in Template data")
    return result


def resolve_data_arguments(
    schema: dict[str, Any],
    arguments: Any,
    allowed_paths: dict[str, str],
    data_root: str,
) -> dict[str, Any]:
    """独立校验每个参数，保留字面量类型，仅受批准路径可形成动态值。"""
    if not isinstance(arguments, dict):
        raise TerselConversionError("Template data must be an object")
    properties = schema.get("properties", {})
    if set(arguments) - set(properties):
        raise TerselConversionError("Template data contains undeclared parameters")
    if set(schema.get("required", ())) - set(arguments):
        raise TerselConversionError("Template data is missing required parameters")
    resolved: dict[str, Any] = {}
    for name, argument in arguments.items():
        field = properties.get(name)
        if not isinstance(field, dict):
            raise TerselConversionError(f"Template data schema is missing: {name}")
        if field.get("type") == "array":
            if not isinstance(argument, list) or len(argument) > MAX_DATA_ARRAY_ITEMS:
                raise TerselConversionError(f"Template data array exceeds its budget: {name}")
            item_schema = field.get("items", {})
            for index, item in enumerate(argument):
                resolved[f"{name}[{index}]"] = _resolve_argument(
                    item,
                    item_schema,
                    allowed_paths,
                    data_root,
                )
        else:
            resolved[name] = _resolve_argument(argument, field, allowed_paths, data_root)
    return resolved


def _resolve_argument(
    argument: Any,
    schema: dict[str, Any],
    paths: dict[str, str],
    root: str,
) -> Any:
    result: Any
    if isinstance(argument, DataPathArgument):
        actual_type = paths.get(argument.path)
        if actual_type is None:
            raise TerselConversionError(f"Template data path is not approved: {argument.path}")
        expected = schema.get("type")
        if actual_type != expected and not (expected == "number" and actual_type == "integer"):
            raise TerselConversionError(f"Template data path type mismatch: {argument.path}")
        result = "${" + root.lstrip("/").replace("/", ".")
        result += argument.path.replace("/", ".") + "}"
    elif isinstance(argument, DataExpressionArgument):
        if schema.get("type") != "string":
            raise TerselConversionError("Template data Expr is supported for display strings only")
        result = _resolve_expression(argument.source, paths, root)
    else:
        errors = list(Draft202012Validator(schema).iter_errors(argument))
        if errors:
            raise TerselConversionError(f"Template data type mismatch: {errors[0].message}")
        if isinstance(argument, str) and any(token in argument for token in ("${", "{{", "}}")):
            raise TerselConversionError("Template literal data cannot contain binding syntax")
        if isinstance(argument, float) and not math.isfinite(argument):
            raise TerselConversionError("Template numeric data must be finite")
        result = argument
    return result


def _resolve_expression(source: str, paths: dict[str, str], root: str) -> str:
    expression = parse_runtime_expression(source, allow_data_paths=True)
    parts: list[str] = []
    for item in expression.items:
        if item.kind == "binding":
            relative = _expression_path(item.name or "", paths)
            parts.append("${" + root + relative + "}")
        elif isinstance(item.value, str):
            parts.append(item.value)
        else:
            raise TerselConversionError("Template data Expr contains an invalid operand")
    normalized = normalize_tersel_expression("".join(parts))
    absolute_types = {root + path: data_type for path, data_type in paths.items()}
    body = normalized.value.removeprefix("{{").removesuffix("}}")
    if expression_result_types(body, absolute_types) != {"string"}:
        raise TerselConversionError("Template data Expr result must have the declared string type")
    return normalized.value


def _expression_path(name: str, paths: dict[str, str]) -> str:
    relative = "/" + name.replace(".", "/")
    if relative in paths:
        return relative
    matches: list[str] = []
    if "." not in name:
        for path in paths:
            if path.rsplit("/", 1)[-1] == name:
                matches.append(path)
    if len(matches) != 1:
        raise TerselConversionError(f"Template data Expr path is unknown or ambiguous: {name}")
    return matches[0]


def materialize_data_root(root: TemplateNode, values: dict[str, Any]) -> TemplateNode:
    """把已校验的数据参数绑定到可信树；最终仍使用原有模板实例化与 A2UI 链路。"""
    children: list[TemplateNode] = []
    for child in root.children:
        if child.component in {"IfBind", "IfMissingBind"}:
            name = child.values[0].value
            present = name in values
            selected = present if child.component == "IfBind" else not present
            if selected:
                children.extend(materialize_data_root(child, values).children)
        elif child.component in {"IfAllBind", "IfAnyMissingBind"}:
            names = [item.value for item in child.values[0].items]
            present = all(name in values for name in names)
            selected = present if child.component == "IfAllBind" else not present
            if selected:
                children.extend(materialize_data_root(child, values).children)
        else:
            children.append(materialize_data_root(child, values))
    return root.model_copy(
        update={
            "values": tuple(_materialize_value(value, values) for value in root.values),
            "children": tuple(children),
        }
    )


def _materialize_value(value: TemplateValue, values: dict[str, Any]) -> TemplateValue:
    result = value
    if value.kind == "compile-time-conditional" and value.items[0].kind == "binding":
        condition, present, missing = value.items
        branch = present if condition.name in values else missing
        result = _materialize_value(branch, values)
    elif value.kind == "binding":
        if value.name not in values:
            raise TerselConversionError(f"Template data reference is missing: {value.name}")
        result = TemplateValue(kind="literal", value=values[value.name])
    elif value.kind in {"interpolation", "expression"}:
        parts: list[str] = []
        static_parts: list[str] = []
        dynamic = False
        for item in value.items:
            if item.kind == "binding":
                if item.name not in values:
                    raise TerselConversionError(f"Template data reference is missing: {item.name}")
                resolved = values[item.name]
                operand, is_dynamic = _expression_operand(resolved)
                dynamic = dynamic or is_dynamic
                parts.append(operand)
                if isinstance(resolved, str):
                    static_parts.append(resolved)
            elif item.kind == "literal" and isinstance(item.value, str):
                operand = item.value
                if value.kind == "interpolation":
                    operand, _is_dynamic = _expression_operand(item.value)
                parts.append(operand)
                static_parts.append(item.value)
            else:
                raise TerselConversionError(
                    "Parameterized interpolation accepts data and text only"
                )
        separator = " + " if value.kind == "interpolation" else ""
        if not dynamic and value.kind == "interpolation":
            rendered = "".join(static_parts)
        else:
            rendered = normalize_tersel_expression(separator.join(parts)).value
        result = TemplateValue(kind="literal", value=rendered)
    else:
        result = value.model_copy(
            update={
                "items": tuple(_materialize_value(item, values) for item in value.items),
                "properties": {
                    name: _materialize_value(item, values)
                    for name, item in value.properties.items()
                },
            }
        )
    return result


def _expression_operand(value: Any) -> tuple[str, bool]:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return value, True
    if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
        return "(" + value.removeprefix("{{").removesuffix("}}").strip() + ")", True
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return "'" + escaped + "'", False
    if isinstance(value, bool):
        return "true" if value else "false", False
    if isinstance(value, (int, float)):
        return str(value), False
    raise TerselConversionError("Template data operand is not a scalar")
