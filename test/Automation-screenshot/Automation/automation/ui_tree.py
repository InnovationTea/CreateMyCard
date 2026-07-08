from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.right) // 2, (self.top + self.bottom) // 2

    @classmethod
    def parse(cls, value: object) -> "Bounds | None":
        nums = [int(n) for n in re.findall(r"-?\d+", str(value or ""))]
        if len(nums) < 4:
            return None
        left, top, right, bottom = nums[:4]
        if right <= left or bottom <= top:
            return None
        return cls(left, top, right, bottom)


@dataclass(frozen=True)
class UiNode:
    attrs: dict[str, Any]
    depth: int
    in_keyboard: bool

    @property
    def node_type(self) -> str:
        return str(self.attrs.get("type", "") or "")

    @property
    def node_id(self) -> str:
        return str(self.attrs.get("id", "") or "")

    @property
    def text(self) -> str:
        return str(self.attrs.get("text", "") or "")

    @property
    def hint(self) -> str:
        return str(self.attrs.get("hint", "") or "")

    @property
    def description(self) -> str:
        return str(self.attrs.get("description", "") or "")

    @property
    def bounds(self) -> Bounds | None:
        return Bounds.parse(self.attrs.get("bounds"))

    @property
    def enabled(self) -> bool:
        return str(self.attrs.get("enabled", "true")).lower() != "false"

    @property
    def visible(self) -> bool:
        return str(self.attrs.get("visible", "true")).lower() != "false"

    @property
    def clickable(self) -> bool:
        return str(self.attrs.get("clickable", "")).lower() == "true"

    @property
    def searchable(self) -> str:
        return "\n".join([self.text, self.node_id, self.description, self.hint])


@dataclass(frozen=True)
class Candidate:
    score: int
    node: UiNode

    @property
    def center(self) -> tuple[int, int]:
        bounds = self.node.bounds
        if bounds is None:
            raise ValueError("Candidate has no bounds")
        return bounds.center


class UiTree:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.nodes = list(self._walk(data))

    @classmethod
    def from_file(cls, path: Path) -> "UiTree":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return cls(json.load(f))

    def _walk(self, raw: Any, depth: int = 0, in_keyboard: bool = False) -> Iterator[UiNode]:
        if not isinstance(raw, dict):
            return
        attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else raw
        node_id = str(attrs.get("id", "") or "").lower()
        now_in_keyboard = in_keyboard or node_id == "keyboard_builder"
        yield UiNode(attrs=attrs, depth=depth, in_keyboard=now_in_keyboard)
        for child in raw.get("children") or []:
            yield from self._walk(child, depth + 1, now_in_keyboard)

    def actionable(self) -> Iterable[UiNode]:
        return (n for n in self.nodes if n.enabled and n.visible and n.bounds is not None)

    def is_chat_ready(self) -> bool:
        haystack = "\n".join(n.searchable.lower() for n in self.nodes)
        has_chat = "chat" in haystack or "keyboard_builder" in haystack
        return has_chat and (self.locate_control("input") is not None or self.locate_control("keyboard_toggle") is not None)

    def locate_control(self, mode: str) -> Candidate | None:
        candidates: list[Candidate] = []
        for node in self.actionable():
            node_id = node.node_id.lower()
            score = 0
            if mode == "input":
                if node.node_type == "TextArea":
                    score += 100
                if node.node_type in {"TextInput", "TextField", "Search"}:
                    score += 80
                if "input" in node_id or "text_input" in node_id:
                    score += 50
                if node.hint:
                    score += 20
                if score and node.clickable:
                    score += 5
            elif mode == "keyboard_toggle":
                if node_id == "chat_page.key_board.icon24":
                    score += 120
                if "keyboard" in node_id or "key_board" in node_id:
                    score += 80
                if node.in_keyboard and node.clickable and node.bounds and node.bounds.left <= 250:
                    score += 40
            elif mode == "send":
                if node_id == "send_hot_area":
                    score += 140
                if "send" in node_id or "arrow_up" in node_id:
                    score += 90
                if node.text in {"发送", "Send"}:
                    score += 80
                if node.in_keyboard and node.clickable and node.node_type == "Stack" and node.bounds and node.bounds.left >= 1000:
                    score += 40
            if score:
                candidates.append(Candidate(score, node))
        return best_candidate(candidates)

    def reply_state(self, dsl_keywords: tuple[str, ...]) -> tuple[bool, bool, int]:
        texts = [n.text for n in self.nodes if n.text.strip()]
        joined = "\n".join(texts)
        busy_terms = ("正在使用工具", "正在思考", "生成中", "执行中", "处理中")
        busy = any(term in joined for term in busy_terms)
        has_dsl = any(keyword in joined for keyword in dsl_keywords)
        return busy, has_dsl, len(joined)


def best_candidate(candidates: Iterable[Candidate]) -> Candidate | None:
    items = list(candidates)
    if not items:
        return None
    return max(
        items,
        key=lambda c: (
            c.score,
            c.node.bounds.top if c.node.bounds else -1,
            c.node.bounds.left if c.node.bounds else -1,
        ),
    )

