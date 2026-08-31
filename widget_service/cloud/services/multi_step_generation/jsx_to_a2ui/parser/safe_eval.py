from __future__ import annotations

import ast
import re
from typing import Any

from ..exceptions import ParseError


class LiteralParser:
    """Parse the JSON-like JavaScript literals allowed in generated card props."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0

    def parse(self) -> Any:
        value = self._value()
        self._space()
        if self.pos != len(self.source):
            raise self._error("unsupported JavaScript expression")
        return value

    def _value(self) -> Any:
        self._space()
        if self.pos >= len(self.source):
            raise self._error("expected a literal value")
        ch = self.source[self.pos]
        if ch in "\"'":
            return self._string()
        if ch == "[":
            return self._array()
        if ch == "{":
            return self._object()
        number = re.match(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", self.source[self.pos :])
        if number:
            raw = number.group(0)
            self.pos += len(raw)
            return float(raw) if any(c in raw for c in ".eE") else int(raw)
        name = self._identifier()
        values = {"true": True, "false": False, "null": None, "undefined": None}
        if name in values:
            return values[name]
        raise self._error(f"identifier {name!r} is not a safe literal")

    def _array(self) -> list[Any]:
        self.pos += 1
        result: list[Any] = []
        while True:
            self._space()
            if self._take("]"):
                return result
            result.append(self._value())
            self._space()
            if self._take("]"):
                return result
            self._expect(",")
            self._space()
            if self._take("]"):
                return result

    def _object(self) -> dict[str, Any]:
        self.pos += 1
        result: dict[str, Any] = {}
        while True:
            self._space()
            if self._take("}"):
                return result
            key = self._string() if self.source[self.pos] in "\"'" else self._identifier()
            self._space()
            self._expect(":")
            result[str(key)] = self._value()
            self._space()
            if self._take("}"):
                return result
            self._expect(",")
            self._space()
            if self._take("}"):
                return result

    def _string(self) -> str:
        quote = self.source[self.pos]
        start = self.pos
        self.pos += 1
        escaped = False
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            self.pos += 1
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                raw = self.source[start : self.pos]
                try:
                    return ast.literal_eval(raw)
                except (SyntaxError, ValueError) as exc:
                    raise self._error("invalid string literal") from exc
        raise self._error("unterminated string literal")

    def _identifier(self) -> str:
        self._space()
        match = re.match(r"[A-Za-z_$][A-Za-z0-9_$-]*", self.source[self.pos :])
        if not match:
            raise self._error("expected an identifier")
        value = match.group(0)
        self.pos += len(value)
        return value

    def _space(self) -> None:
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            self.pos += 1

    def _take(self, token: str) -> bool:
        if self.source.startswith(token, self.pos):
            self.pos += len(token)
            return True
        return False

    def _expect(self, token: str) -> None:
        if not self._take(token):
            raise self._error(f"expected {token!r}")

    def _error(self, message: str) -> ParseError:
        return ParseError(f"{message} at expression offset {self.pos}: {self.source!r}")


def parse_literal(source: str) -> Any:
    return LiteralParser(source.strip()).parse()
