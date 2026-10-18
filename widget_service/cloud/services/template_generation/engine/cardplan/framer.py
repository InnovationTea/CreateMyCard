"""Typed delimiter streaming framer for CardPlan compositions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from services.template_generation.engine.tersel_converter import (
    MAX_INPUT_LENGTH,
    TerselConversionError,
)


@dataclass(frozen=True)
class FramedUnit:
    kind: Literal["root", "child", "program"]
    source: str


class HybridCardFramer:
    """Accept arbitrary chunks and emit stable root/child/program boundaries once."""

    _PAIRS = {"(": ")", "[": "]", "{": "}"}

    def __init__(self) -> None:
        self._source = ""
        self._scan_offset = 0
        self._stack: list[str] = []
        self._in_string: str | None = None
        self._escaped = False
        self._top_level_commas = 0
        self._root_emitted = False
        self._child_emitted = False
        self._program_emitted = False

    def push(self, chunk: str) -> tuple[FramedUnit, ...]:
        if not isinstance(chunk, str):
            raise TypeError("CardPlan stream chunks must be strings")
        self._source += chunk
        if len(self._source) > MAX_INPUT_LENGTH:
            raise TerselConversionError("CardPlan stream exceeds the size limit.")
        emitted: list[FramedUnit] = []
        while self._scan_offset < len(self._source):
            char = self._source[self._scan_offset]
            self._scan_offset += 1
            if self._in_string is not None:
                if self._escaped:
                    self._escaped = False
                elif char == "\\":
                    self._escaped = True
                elif char == self._in_string:
                    self._in_string = None
                continue
            if char in {'"', "'"}:
                self._in_string = char
                continue
            if char in self._PAIRS:
                self._stack.append(self._PAIRS[char])
                continue
            if char in self._PAIRS.values():
                if not self._stack or self._stack[-1] != char:
                    raise TerselConversionError("CardPlan stream has crossed delimiters.")
                self._stack.pop()
                if not self._stack and not self._child_emitted:
                    self._child_emitted = True
                    emitted.append(FramedUnit("child", self._source[: self._scan_offset]))
                continue
            if char == "," and self._stack == [")"]:
                self._top_level_commas += 1
                if self._top_level_commas == 2 and not self._root_emitted:
                    self._root_emitted = True
                    emitted.append(FramedUnit("root", self._source[: self._scan_offset]))
            if char == ";" and not self._stack and not self._program_emitted:
                self._program_emitted = True
                emitted.append(FramedUnit("program", self._source[: self._scan_offset]))
        return tuple(emitted)

    def finish(self) -> str:
        if self._in_string is not None:
            raise TerselConversionError("CardPlan stream ended in a string.")
        if self._stack:
            raise TerselConversionError("CardPlan stream ended before delimiters closed.")
        source = self._source.strip()
        if not source.endswith(";"):
            raise TerselConversionError("CardPlan stream must end with a semicolon.")
        return source
