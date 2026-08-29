"""Restricted CardPlan/Nested-2 parser that never evaluates model output."""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from typing import Any, Literal

from services.template_generation.engine.advanced.models import (
    UX_DIRECT_BUSINESS_COMPONENT_IDS,
    UX_LAYOUT_COMPONENT_IDS,
)
from services.template_generation.engine.terse_dsl_nested2_converter import (
    MAX_COMPONENTS,
    MAX_INPUT_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_OBJECT_FIELDS,
    MAX_STRING_LENGTH,
    Nested2Node,
    TerseDslNested2ConversionError,
)

from .models import SourceSpan

_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_CONTAINERS = frozenset({"Row", "Column", "List", "Stack"}) | UX_LAYOUT_COMPONENT_IDS
_UX_ACTION_COMPONENTS = frozenset({"PillAction", "IconAction", "ActionTile"})
_LEAVES = (
    frozenset({"Text", "Image", "Divider", "Progress", "Button", "Checkbox"})
    | _UX_ACTION_COMPONENTS
    | UX_DIRECT_BUSINESS_COMPONENT_IDS
)
_COMPONENTS = _CONTAINERS | _LEAVES


@dataclass(frozen=True)
class ParsedCall:
    kind: Literal["component", "template"]
    name: str
    values: tuple[Any, ...]
    children: tuple[ParsedCall, ...]
    span: SourceSpan


def normalize_hybrid_source(source: str) -> str:
    value = source.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        raise TerseDslNested2ConversionError("CardPlan Markdown fence is not closed.")
    return "\n".join(lines[1:-1]).strip()


def parse_hybrid_card(source: str) -> ParsedCall:
    source, root, state = _parse_program(source)
    if root.kind != "template" or root.name != "card@1":
        raise TerseDslNested2ConversionError('CardPlan root must be Template("card@1", ...).')
    if len(root.values) != 1 or len(root.children) != 1:
        raise TerseDslNested2ConversionError("card@1 requires params and one content child.")
    if not isinstance(root.values[0], dict):
        raise TerseDslNested2ConversionError("card@1 params must be one object.")
    content = root.children[0]
    if content.kind == "template":
        state["components"] += 1
        if state["components"] > MAX_COMPONENTS:
            raise TerseDslNested2ConversionError("CardPlan component count exceeds 256.")
        content = ParsedCall(
            "component",
            "Column",
            (),
            (content,),
            content.span,
        )
        root = ParsedCall(root.kind, root.name, root.values, (content,), root.span)
    if content.kind != "component" or content.name not in _CONTAINERS:
        raise TerseDslNested2ConversionError("card@1 content must be one Catalog container.")
    return root


def parse_ux_layout_card(source: str) -> ParsedCall:
    """Parse the fifth-interface layout-root program without a ``card@1`` wrapper."""
    _source, root, _state = _parse_program(source)
    if not (
        (root.kind == "component" and root.name in UX_LAYOUT_COMPONENT_IDS)
        or (root.kind == "template" and root.name.endswith("Layout@1"))
    ):
        raise TerseDslNested2ConversionError("UX Mixed root must be one Layout Template.")
    if len(root.values) > 1 or (root.values and not isinstance(root.values[0], dict)):
        raise TerseDslNested2ConversionError(
            "UX Layout configuration must be one optional object argument."
        )
    return root


def _parse_program(source: str) -> tuple[str, ParsedCall, dict[str, int]]:
    source = normalize_hybrid_source(source)
    if not source:
        raise TerseDslNested2ConversionError("CardPlan output is empty.")
    if len(source) > MAX_INPUT_LENGTH:
        raise TerseDslNested2ConversionError("CardPlan output exceeds the size limit.")
    translated = _python_compatible_source(source)
    try:
        module = ast.parse(translated, mode="exec")
    except SyntaxError as exc:
        raise TerseDslNested2ConversionError(
            f"CardPlan syntax error at line {exc.lineno}: {exc.msg}."
        ) from exc
    if len(module.body) != 1 or not isinstance(module.body[0], ast.Expr):
        raise TerseDslNested2ConversionError("CardPlan must contain exactly one call.")
    state = {"components": 0}
    root = _parse_call(module.body[0].value, source, 1, state)
    return source, root, state


def parsed_component_to_nested(node: ParsedCall) -> Nested2Node:
    if node.kind != "component":
        raise TerseDslNested2ConversionError("Template must be expanded before Catalog lowering.")
    return Nested2Node(
        component_type=node.name,
        values=node.values,
        children=tuple(parsed_component_to_nested(child) for child in node.children),
    )


def _parse_call(
    node: ast.AST,
    source: str,
    depth: int,
    state: dict[str, int],
) -> ParsedCall:
    if depth > MAX_NESTING_DEPTH:
        raise TerseDslNested2ConversionError("CardPlan nesting exceeds 32 levels.")
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
        raise TerseDslNested2ConversionError("Only direct CardPlan calls are allowed.")
    name = node.func.id
    span = _span(node, source)
    if name == "Template":
        return _parse_template_call(node, source, depth, state, span)
    if name not in _COMPONENTS:
        raise TerseDslNested2ConversionError(f'Unsupported component type "{name}".')
    state["components"] += 1
    if state["components"] > MAX_COMPONENTS:
        raise TerseDslNested2ConversionError("CardPlan component count exceeds 256.")
    values: list[Any] = []
    children: list[ParsedCall] = []
    child_started = False
    for argument in node.args:
        if isinstance(argument, ast.Call):
            child_started = True
            children.append(_parse_call(argument, source, depth + 1, state))
        elif _is_wrapped_layout_config(name, argument, values, child_started):
            values.append(_literal_value(argument.elts[0], depth + 1))
        elif isinstance(argument, ast.List) and argument.elts:
            if not all(isinstance(child, ast.Call) for child in argument.elts):
                raise TerseDslNested2ConversionError(
                    "Component child arrays may contain calls only."
                )
            child_started = True
            children.extend(_parse_call(child, source, depth + 1, state) for child in argument.elts)
        else:
            if child_started:
                raise TerseDslNested2ConversionError(
                    "Value arguments must appear before the first child."
                )
            values.append(_literal_value(argument, depth + 1))
    if children and name not in _CONTAINERS:
        raise TerseDslNested2ConversionError(f"{name} cannot contain child components.")
    return ParsedCall("component", name, tuple(values), tuple(children), span)


def _is_wrapped_layout_config(
    name: str,
    argument: ast.AST,
    values: list[Any],
    child_started: bool,
) -> bool:
    """Accept the recurrent model form Layout([{...}], child) as one config object."""
    if name not in UX_LAYOUT_COMPONENT_IDS or values or child_started:
        return False
    return (
        isinstance(argument, ast.List)
        and len(argument.elts) == 1
        and isinstance(argument.elts[0], ast.Dict)
    )


def _parse_template_call(
    node: ast.Call,
    source: str,
    depth: int,
    state: dict[str, int],
    span: SourceSpan,
) -> ParsedCall:
    if not node.args:
        raise TerseDslNested2ConversionError("Template requires a versioned ID.")
    template_id = _literal_value(node.args[0], depth + 1)
    if not isinstance(template_id, str):
        raise TerseDslNested2ConversionError("Template ID must be a string.")
    if template_id == "card@1":
        if len(node.args) != 3 or not isinstance(node.args[2], ast.Call):
            raise TerseDslNested2ConversionError("card@1 requires params and one content child.")
        params = _literal_value(node.args[1], depth + 1)
        content = _parse_call(node.args[2], source, depth + 1, state)
        return ParsedCall("template", template_id, (params,), (content,), span)
    second = _literal_value(node.args[1], depth + 1) if len(node.args) >= 2 else None
    if isinstance(second, dict):
        children: list[ParsedCall] = []
        for child in node.args[2:]:
            if not isinstance(child, ast.Call):
                raise TerseDslNested2ConversionError(
                    "UI Template children must be direct component or Template calls."
                )
            children.append(_parse_call(child, source, depth + 1, state))
        return ParsedCall("template", template_id, (second,), tuple(children), span)
    raise TerseDslNested2ConversionError(
        "Local Template requires a versioned ID, one props object and optional children."
    )


def _literal_value(node: ast.AST, depth: int) -> Any:
    if depth > MAX_NESTING_DEPTH:
        raise TerseDslNested2ConversionError("CardPlan literal nesting exceeds 32 levels.")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and len(node.value) > MAX_STRING_LENGTH:
            raise TerseDslNested2ConversionError("CardPlan string exceeds the size limit.")
        if node.value is None or isinstance(node.value, (str, int, float, bool)):
            return node.value
    if isinstance(node, ast.List):
        return [_literal_value(item, depth + 1) for item in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _literal_value(node.operand, depth + 1)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            raise TerseDslNested2ConversionError("Unary signs require numeric literals.")
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.Dict):
        if len(node.keys) > MAX_OBJECT_FIELDS:
            raise TerseDslNested2ConversionError("CardPlan object exceeds the field limit.")
        result: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            if key_node is None:
                raise TerseDslNested2ConversionError(
                    "CardPlan does not allow dictionary unpacking."
                )
            key = _literal_value(key_node, depth + 1)
            if not isinstance(key, str):
                raise TerseDslNested2ConversionError("CardPlan object keys must be strings.")
            if key in _FORBIDDEN_KEYS:
                raise TerseDslNested2ConversionError(f'Forbidden object key "{key}".')
            if key in result:
                raise TerseDslNested2ConversionError(f'Duplicate object key "{key}".')
            result[key] = _literal_value(value_node, depth + 1)
        return result
    raise TerseDslNested2ConversionError("CardPlan accepts literal data only.")


def _python_compatible_source(source: str) -> str:
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        raise TerseDslNested2ConversionError(
            f"CardPlan tokenization failed: {exc.args[0]}."
        ) from exc
    translated: list[tokenize.TokenInfo] = []
    literals = {"true": "True", "false": "False", "null": "None"}
    for index, token in enumerate(tokens):
        value = literals.get(token.string, token.string)
        token_type = token.type
        if token.type == tokenize.NAME and _next_token_is_colon(tokens, index):
            value = repr(token.string)
            token_type = tokenize.STRING
        translated.append(tokenize.TokenInfo(token_type, value, token.start, token.end, token.line))
    return tokenize.untokenize(translated)


def _next_token_is_colon(tokens: list[tokenize.TokenInfo], index: int) -> bool:
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


def _span(node: ast.AST, source: str) -> SourceSpan:
    lines = source.splitlines(keepends=True)
    starts: list[int] = []
    offset = 0
    for source_line in lines:
        starts.append(offset)
        offset += len(source_line)
    line_number = max(1, getattr(node, "lineno", 1))
    end_line = max(line_number, getattr(node, "end_lineno", line_number))
    start = starts[min(line_number - 1, len(starts) - 1)] + getattr(node, "col_offset", 0)
    end = starts[min(end_line - 1, len(starts) - 1)] + getattr(node, "end_col_offset", 0)
    return SourceSpan(start=start, end=end)
