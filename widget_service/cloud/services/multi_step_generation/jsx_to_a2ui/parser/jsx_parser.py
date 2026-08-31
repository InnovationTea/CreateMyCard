from __future__ import annotations

import re
from typing import Any

from ..exceptions import ParseError
from .jsx_ast import JSXElement
from .safe_eval import parse_literal


def _balanced(source: str, start: int, opening: str, closing: str) -> tuple[str, int]:
    if start >= len(source) or source[start] != opening:
        raise ParseError(f"expected {opening!r} at source offset {start}")
    depth = 1
    pos = start + 1
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    while pos < len(source):
        ch = source[pos]
        nxt = source[pos + 1] if pos + 1 < len(source) else ""
        if line_comment:
            if ch in "\r\n":
                line_comment = False
        elif block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                pos += 1
        elif quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch == "/" and nxt == "/":
            line_comment = True
            pos += 1
        elif ch == "/" and nxt == "*":
            block_comment = True
            pos += 1
        elif ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return source[start + 1 : pos], pos + 1
        pos += 1
    raise ParseError(f"unterminated {opening}{closing} block at source offset {start}")


class JSXParser:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0

    def parse(self) -> JSXElement:
        self._space()
        element = self._element()
        self._space()
        if self.pos != len(self.source):
            raise self._error("unexpected content after JSX element")
        return element

    def _element(self) -> JSXElement:
        offset = self.pos
        self._expect("<")
        tag = self._name()
        props: dict[str, Any] = {}
        while True:
            self._space()
            if self._take("/>"):
                return JSXElement(tag=tag, props=props, offset=offset)
            if self._take(">"):
                break
            if self.source.startswith("{...", self.pos):
                raise self._error("spread attributes are not supported")
            name = self._name()
            self._space()
            if not self._take("="):
                props[name] = True
                continue
            self._space()
            if self.pos >= len(self.source):
                raise self._error("missing attribute value")
            if self.source[self.pos] in "\"'":
                props[name] = self._quoted()
            elif self.source[self.pos] == "{":
                expression, self.pos = _balanced(self.source, self.pos, "{", "}")
                props[name] = self._expression(expression)
            else:
                raise self._error("attribute values must be quoted or wrapped in braces")

        children: list[JSXElement | str] = []
        while True:
            if self.pos >= len(self.source):
                raise self._error(f"unterminated <{tag}> element")
            if self.source.startswith("</", self.pos):
                self.pos += 2
                closing = self._name()
                self._space()
                self._expect(">")
                if closing != tag:
                    raise self._error(f"closing tag </{closing}> does not match <{tag}>")
                return JSXElement(tag=tag, props=props, children=children, offset=offset)
            if self.source[self.pos] == "<":
                children.append(self._element())
                continue
            if self.source[self.pos] == "{":
                expression, self.pos = _balanced(self.source, self.pos, "{", "}")
                value = self._expression(expression)
                if isinstance(value, JSXElement):
                    children.append(value)
                elif isinstance(value, str) and value.strip():
                    children.append(value)
                elif value is not None:
                    raise self._error("only JSX elements or text are supported as JSX children")
                continue
            start = self.pos
            while self.pos < len(self.source) and self.source[self.pos] not in "<{":
                self.pos += 1
            text = re.sub(r"\s+", " ", self.source[start : self.pos]).strip()
            if text:
                children.append(text)

    def _expression(self, source: str) -> Any:
        stripped = source.strip()
        if not stripped:
            return None
        if stripped.startswith("<"):
            return JSXParser(stripped).parse()
        return parse_literal(stripped)

    def _quoted(self) -> str:
        quote = self.source[self.pos]
        self.pos += 1
        result: list[str] = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            self.pos += 1
            if ch == quote:
                return "".join(result)
            if ch == "\\" and self.pos < len(self.source):
                result.append(self.source[self.pos])
                self.pos += 1
            else:
                result.append(ch)
        raise self._error("unterminated attribute string")

    def _name(self) -> str:
        match = re.match(r"[A-Za-z_$][A-Za-z0-9_$.-]*", self.source[self.pos :])
        if not match:
            raise self._error("expected a JSX name")
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
        line = self.source.count("\n", 0, self.pos) + 1
        return ParseError(f"{message} at JSX line {line}, offset {self.pos}")


def parse_jsx(source: str) -> JSXElement:
    return JSXParser(source.strip()).parse()


def extract_card_functions(source: str) -> dict[str, JSXElement]:
    cards: dict[str, JSXElement] = {}
    pattern = re.compile(r"\bfunction\s+(Card[A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{")
    for match in pattern.finditer(source):
        body_start = source.find("{", match.start())
        body, _ = _balanced(source, body_start, "{", "}")
        returned = re.search(r"\breturn\s*\(", body)
        if not returned:
            continue
        paren = body.find("(", returned.start())
        jsx_source, _ = _balanced(body, paren, "(", ")")
        cards[match.group(1)] = parse_jsx(jsx_source)
    if not cards:
        raise ParseError("no function Card*() returning parenthesized JSX was found")
    return cards
