# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Normalize the restricted Tersel/CardTemplate expression syntax to A2UI."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

MAX_EXPRESSION_LENGTH = 2048
MAX_EXPRESSION_DEPTH = 20

_DATA_DOT_PATH_RE = re.compile(r"^data(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\d+)+$")
_DATA_POINTER_RE = re.compile(r"^/data(?:/[A-Za-z_][A-Za-z0-9_]*|/\d+)+$")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class A2UIExpressionError(ValueError):
    """Raised when an expression cannot be represented by the Form runtime."""


@dataclass(frozen=True)
class NormalizedExpression:
    """One validated A2UI expression and its normalized JSON Pointer references."""

    value: str
    references: tuple[str, ...]


@dataclass(frozen=True)
class _ExpressionToken:
    kind: str
    value: str
    start: int
    end: int


def normalize_tersel_expression(body: str) -> NormalizedExpression:
    """Validate one Expr body and wrap it as a complete A2UI expression."""
    if not isinstance(body, str) or not body.strip():
        raise A2UIExpressionError("Expr requires one non-empty string body.")
    if "{{" in body or "}}" in body:
        raise A2UIExpressionError("Expr body must not contain the outer {{ }} wrapper.")
    tokens = _tokenize(body)
    _ExpressionParser(tokens).parse()
    references = tuple(token.value for token in tokens if token.kind == "binding")
    if not references:
        raise A2UIExpressionError("Expr must reference at least one DataModel path.")
    normalized_body = _replace_bindings(body, tokens).strip()
    value = "{{ " + normalized_body + " }}"
    if len(value) > MAX_EXPRESSION_LENGTH:
        raise A2UIExpressionError(
            f"Expression exceeds the {MAX_EXPRESSION_LENGTH}-character limit."
        )
    return NormalizedExpression(value=value, references=references)


def normalize_wrapped_expression(value: str) -> NormalizedExpression:
    """Validate and normalize an existing complete A2UI expression string."""
    if not isinstance(value, str):
        raise A2UIExpressionError("A2UI expression must be a string.")
    stripped = value.strip()
    has_bounds = stripped.startswith("{{") and stripped.endswith("}}")
    has_single_wrapper = stripped.count("{{") == 1 and stripped.count("}}") == 1
    if not has_bounds or not has_single_wrapper:
        raise A2UIExpressionError("A2UI expression must occupy the complete string value.")
    body = stripped.removeprefix("{{").removesuffix("}}")
    return normalize_tersel_expression(body)


def _tokenize(body: str) -> tuple[_ExpressionToken, ...]:
    tokens: list[_ExpressionToken] = []
    index = 0
    depth = 0
    while True:
        index = _skip_space(body, index)
        if index >= len(body):
            break
        start = index
        if body.startswith("${", index):
            token, index = _read_braced_reference(body, index)
        elif body.startswith("$__dataModel", index):
            token, index = _read_data_model_reference(body, index)
        elif body[index] == "'":
            literal, index = _read_string(body, index)
            token = _ExpressionToken("literal", literal, start, index)
        elif body[index].isdigit():
            token, index = _read_number(body, index)
        elif body[index].isalpha() or body[index] == "_":
            token, index = _read_identifier(body, index)
        else:
            token, index = _read_operator(body, index)
        tokens.append(token)
        if token.kind == "operator" and token.value == "(":
            depth += 1
            if depth > MAX_EXPRESSION_DEPTH:
                raise A2UIExpressionError(
                    f"Expression nesting exceeds the {MAX_EXPRESSION_DEPTH}-level limit."
                )
        elif token.kind == "operator" and token.value == ")":
            depth -= 1
            if depth < 0:
                raise A2UIExpressionError("Expression parentheses are inconsistent.")
    if not tokens:
        raise A2UIExpressionError("Expr body must not be empty.")
    if depth != 0:
        raise A2UIExpressionError("Expression parentheses are inconsistent.")
    return tuple(tokens)


def _read_braced_reference(body: str, index: int) -> tuple[_ExpressionToken, int]:
    end = body.find("}", index + 2)
    if end < 0:
        raise A2UIExpressionError("Expression contains an unclosed ${...} reference.")
    source_path = body[slice(index + 2, end)]
    path = _normalize_source_path(source_path)
    return _ExpressionToken("binding", path, index, end + 1), end + 1


def _read_data_model_reference(body: str, index: int) -> tuple[_ExpressionToken, int]:
    cursor = index + len("$__dataModel")
    parts: list[str] = []
    while cursor < len(body):
        if body[cursor] == ".":
            match = _IDENTIFIER_RE.match(body, cursor + 1)
            if match is None:
                raise A2UIExpressionError("DataModel member access is invalid.")
            parts.append(match.group(0))
            cursor = match.end()
            continue
        if body[cursor] == "[":
            end = body.find("]", cursor + 1)
            index_value = body[slice(cursor + 1, end)] if end >= 0 else ""
            if end < 0 or not index_value.isdigit():
                raise A2UIExpressionError("DataModel array access requires a numeric index.")
            parts.append(index_value)
            cursor = end + 1
            continue
        break
    if not parts:
        raise A2UIExpressionError("$__dataModel must reference a concrete path.")
    path = "/" + "/".join(parts)
    if _DATA_POINTER_RE.fullmatch(path) is None:
        raise A2UIExpressionError("Expr may only read paths below /data.")
    return _ExpressionToken("binding", path, index, cursor), cursor


def _normalize_source_path(path: str) -> str:
    if _DATA_POINTER_RE.fullmatch(path) is not None:
        return path
    if _DATA_DOT_PATH_RE.fullmatch(path) is not None:
        return "/" + path.replace(".", "/")
    raise A2UIExpressionError(
        "Expr references must use data.path, /data/path, or $__dataModel.data.path."
    )


def _read_string(body: str, index: int) -> tuple[str, int]:
    cursor = index + 1
    escaped = False
    while cursor < len(body):
        char = body[cursor]
        if escaped:
            if char not in {"\\", "'", "n", "r", "t"}:
                raise A2UIExpressionError("Expression string contains an unsupported escape.")
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "'":
            return body[slice(index, cursor + 1)], cursor + 1
        cursor += 1
    raise A2UIExpressionError("Expression string literal is not closed.")


def _read_number(body: str, index: int) -> tuple[_ExpressionToken, int]:
    cursor = index + 1
    while cursor < len(body) and body[cursor].isdigit():
        cursor += 1
    if cursor < len(body) and body[cursor] == ".":
        cursor += 1
        fraction_start = cursor
        while cursor < len(body) and body[cursor].isdigit():
            cursor += 1
        if fraction_start == cursor:
            raise A2UIExpressionError("Expression number is invalid.")
    return _ExpressionToken("number", body[slice(index, cursor)], index, cursor), cursor


def _read_identifier(body: str, index: int) -> tuple[_ExpressionToken, int]:
    match = _IDENTIFIER_RE.match(body, index)
    assert match is not None
    value = match.group(0)
    kind = "atom" if value in {"true", "false"} else "function"
    if kind == "function" and value != "size":
        raise A2UIExpressionError(f'Expression identifier "{value}" is not supported.')
    return _ExpressionToken(kind, value, index, match.end()), match.end()


def _read_operator(body: str, index: int) -> tuple[_ExpressionToken, int]:
    operator = next(
        (item for item in ("&&", "||", "==", "!=", "<=", ">=") if body.startswith(item, index)),
        None,
    )
    if operator is None and body[index] in "+-*/%<>!?:()":
        operator = body[index]
    if operator is None:
        raise A2UIExpressionError(f"Expression contains unsupported syntax at offset {index}.")
    end = index + len(operator)
    return _ExpressionToken("operator", operator, index, end), end


def _replace_bindings(body: str, tokens: tuple[_ExpressionToken, ...]) -> str:
    parts: list[str] = []
    cursor = 0
    for token in tokens:
        if token.kind != "binding":
            continue
        parts.append(body[slice(cursor, token.start)])
        parts.append("${" + token.value + "}")
        cursor = token.end
    parts.append(body[cursor:])
    return "".join(parts)


def _skip_space(value: str, index: int) -> int:
    while index < len(value) and value[index].isspace():
        index += 1
    return index


class _ExpressionParser:
    def __init__(self, tokens: tuple[_ExpressionToken, ...]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse(self) -> None:
        self._conditional()
        if self.index != len(self.tokens):
            self._invalid("unexpected token")

    def _conditional(self) -> None:
        self._logical_or()
        if self._accept("?"):
            self._conditional()
            self._expect(":")
            self._conditional()

    def _logical_or(self) -> None:
        self._binary(self._logical_and, ("||",))

    def _logical_and(self) -> None:
        self._binary(self._equality, ("&&",))

    def _equality(self) -> None:
        self._binary(self._relational, ("==", "!="))

    def _relational(self) -> None:
        self._binary(self._additive, ("<", ">", "<=", ">="))

    def _additive(self) -> None:
        self._binary(self._multiplicative, ("+", "-"))

    def _multiplicative(self) -> None:
        self._binary(self._unary, ("*", "/", "%"))

    def _unary(self) -> None:
        if self._accept("!", "-"):
            self._unary()
            return
        self._primary()

    def _primary(self) -> None:
        token = self._peek()
        if token is None:
            self._invalid("missing operand")
        if token.kind in {"binding", "literal", "number", "atom"}:
            self.index += 1
            return
        if token.kind == "function":
            self.index += 1
            self._expect("(")
            self._conditional()
            self._expect(")")
            return
        if self._accept("("):
            self._conditional()
            self._expect(")")
            return
        self._invalid("expected an operand")

    def _binary(
        self,
        child: Callable[[], None],
        operators: tuple[str, ...],
    ) -> None:
        child()
        while self._accept(*operators):
            child()

    def _accept(self, *values: str) -> bool:
        token = self._peek()
        if token is None or token.kind != "operator" or token.value not in values:
            return False
        self.index += 1
        return True

    def _expect(self, value: str) -> None:
        if not self._accept(value):
            self._invalid(f'expected "{value}"')

    def _peek(self) -> _ExpressionToken | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _invalid(self, detail: str) -> None:
        token = self._peek()
        offset = token.start if token is not None else self.tokens[-1].end
        raise A2UIExpressionError(f"Invalid A2UI expression ({detail}) at offset {offset}.")
