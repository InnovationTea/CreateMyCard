"""本次静态展示的只读来源证据与保存前复核，不进入端侧动态契约。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _SourceOffsets:
    text: str
    positions: tuple[tuple[int, int], ...]


def _source_offsets(source: str) -> _SourceOffsets:
    characters = []
    positions = []
    index = 0
    while index < len(source):
        character = source[index]
        end = index + 1
        if character == "\r":
            character = "\n"
            if end < len(source) and source[end] == "\n":
                end += 1
        characters.append(character)
        positions.append((index, end))
        index = end
    return _SourceOffsets("".join(characters), tuple(positions))


@dataclass(frozen=True)
class StaticContentContext:
    policy_version: str
    source_positions: tuple[dict[str, Any], ...]
    input_chars: int
    display_chars: int
    protected_count: int

    @classmethod
    def from_plan(cls, source: str, plan: dict[str, Any]) -> StaticContentContext:
        from config.config import get_settings

        normalized = _source_offsets(source)
        positions = []
        display_chars = 0
        protected_count = 0
        position_count = 0
        for index, fact in enumerate(plan.get("info_required", [])):
            text = fact.get("text")
            if isinstance(text, str):
                display_chars += len(text)
            protected_count += len(fact.get("protectedTexts", []))
            for reference in fact.get("sourceTexts", []):
                if not isinstance(reference, str) or not reference:
                    raise ValueError("静态引用必须是非空原文字符串。")
                normalized_reference = reference.replace("\r\n", "\n").replace("\r", "\n")
                start = 0
                locations = []
                while True:
                    position = normalized.text.find(normalized_reference, start)
                    if position < 0:
                        break
                    position_count += 1
                    if position_count > get_settings().static_content_max_source_positions:
                        raise ValueError("来源位置数量超过预算，请使用更明确、较长的来源引用。")
                    source_start, _source_end = normalized.positions[position]
                    end_position = position + len(normalized_reference) - 1
                    _source_start, source_end = normalized.positions[end_position]
                    locations.append({"start": source_start, "end": source_end})
                    start = position + 1
                positions.append(
                    {"factIndex": index, "sourceText": reference, "positions": locations}
                )
        return cls(
            "static-content-v1", tuple(positions), len(source), display_chars, protected_count
        )


def standard_components(source: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line in source.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        update = record.get("updateComponents")
        if not isinstance(update, dict):
            continue
        for node in update.get("components", []):
            identifier = node.get("id")
            if isinstance(identifier, str):
                result[identifier] = node
    return result


def final_static_display_errors(before: str, after: str) -> list[str]:
    """主题可改颜色及背景，但不能移动、隐藏或改变已通过的文字结构。"""
    baseline = standard_components(before)
    final = standard_components(after)
    reachable: set[str] = set()
    visiting: set[str] = set()
    errors = []
    from services.post_layout_theme import foreground_signature

    if foreground_signature(before) != foreground_signature(after):
        errors.append("COMPACT_STATIC_TEXT_CAPACITY: 主题后前景结构或容量参数发生改变。")

    def visit(identifier: str, hidden: bool) -> None:
        if identifier in visiting or identifier in reachable:
            errors.append("静态最终组件存在循环或重复引用。")
            return
        node = final.get(identifier)
        if node is None:
            errors.append("静态最终组件引用缺失。")
            return
        visiting.add(identifier)
        styles = node.get("styles", {})
        invisible = styles.get("visibility") in {"none", "hidden", "gone", "invisible"}
        invisible = invisible or styles.get("opacity") == 0
        concealed = hidden or invisible
        if not concealed:
            reachable.add(identifier)
        for child in node.get("children", []):
            if isinstance(child, str):
                visit(child, concealed)
        visiting.remove(identifier)

    visit("root", False)
    for identifier, original in baseline.items():
        if original.get("component") not in {"Text", "Button"}:
            continue
        node = final.get(identifier)
        if node is None or identifier not in reachable:
            errors.append(f"COMPACT_STATIC_CORE_MISSING: 最终文字 {identifier} 不可见或不可达。")
            continue
        for key in ("content", "label", "component"):
            if original.get(key) != node.get(key):
                errors.append(
                    f"COMPACT_STATIC_PROTECTED_TEXT_CHANGED: 最终文字 {identifier} 改变。"
                )
        for key in ("fontSize", "lineHeight", "maxLines", "height", "width"):
            old_styles = original.get("styles", {})
            new_styles = node.get("styles", {})
            if old_styles.get(key) != new_styles.get(key):
                errors.append(
                    f"COMPACT_STATIC_TEXT_CAPACITY: 最终文字 {identifier} 的 {key} 改变。"
                )
    return errors
