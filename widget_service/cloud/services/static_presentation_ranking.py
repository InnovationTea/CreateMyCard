"""仅对已通过公共校验的静态布局排序，不判断来源语义或改写事实。"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_high_level_components import expand_high_level_component_rows
from services.static_text_capacity import text_width


@dataclass(frozen=True)
class StaticPresentationScore:
    omitted_indexes: tuple[int, ...]
    readability: float
    structure: float
    hierarchy: float
    spacing: float
    wrapped_lines: int
    orphan_lines: int
    flattened_facts: int
    duplicate_fields: int

    @property
    def total(self) -> float:
        return round(self.readability + self.structure + self.hierarchy + self.spacing, 3)

    def order_key(self, source: str) -> tuple[int, float, str]:
        # 覆盖优先于视觉分数；同分按源排序，避免生成顺序决定结果。
        return len(self.omitted_indexes), -self.total, source

    def summary(self, source: str) -> dict[str, Any]:
        return {
            "version": "static-layout-v1",
            "sourceDigest": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "omittedFactIndexes": list(self.omitted_indexes),
            "score": self.total,
            "readability": round(self.readability, 3),
            "structure": self.structure,
            "hierarchy": self.hierarchy,
            "spacing": self.spacing,
            "wrappedLines": self.wrapped_lines,
            "orphanLines": self.orphan_lines,
            "flattenedFacts": self.flattened_facts,
            "duplicateFields": self.duplicate_fields,
        }


@dataclass(frozen=True)
class _TextMetrics:
    font_deficit: float
    wrapped_lines: int
    orphan_lines: int


def _text_metrics(rows: list[ComponentRow]) -> _TextMetrics:
    deficit = 0.0
    characters = 0
    wrapped: dict[str, list[float]] = {}
    for row in rows:
        if row.component_type != "Text":
            continue
        text = row.props.get("content")
        font = row.props.get("fontSize")
        if not isinstance(text, str) or not isinstance(font, (int, float)):
            continue
        characters += len(text)
        deficit += len(text) * max(0.0, 12.0 - font)
        prefix, marker, suffix = row.component_id.rpartition("_line")
        if marker and suffix.isdigit():
            wrapped.setdefault(prefix, []).append(text_width(text, font))
    extra_lines = 0
    orphan_lines = 0
    for widths in wrapped.values():
        if len(widths) < 2:
            continue
        extra_lines += len(widths) - 1
        if widths[-1] < max(widths) * 0.35:
            orphan_lines += 1
    return _TextMetrics(deficit / max(1, characters), extra_lines, orphan_lines)


def _display_strings(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, list):
        for item in value:
            result.extend(_display_strings(item))
    elif isinstance(value, dict):
        keys = (
            "title", "body", "label", "value", "description", "leading", "trailing",
            "primaryText", "secondaryText", "details", "items", "attributes",
        )
        for key in keys:
            result.extend(_display_strings(value.get(key)))
    return result


def _hierarchy_metrics(source: str, props: dict, plan: dict) -> tuple[int, int]:
    from services.card_validation.compact_validation.semantic.static_content import (
        static_display_groups,
    )

    texts: set[str] = set()
    for fact in plan.get("info_required", []):
        text = fact.get("text")
        if isinstance(text, str):
            texts.add(text)
    flattened = 0
    for field_text in _display_strings(props):
        matches = 0
        for text in texts:
            if text in field_text:
                matches += 1
        flattened += max(0, matches - 1)
    object_count = 0
    for group in plan.get("contentGroups", []):
        if group.get("kind") == "object":
            object_count += 1
    objects, shared = static_display_groups(source, attribute_objects=object_count > 1)
    duplicates = 0
    for group in [*objects, *shared]:
        for count in Counter(group.parts).values():
            duplicates += max(0, count - 1)
    return flattened, duplicates


def _presentation_style(body: ComponentRow) -> str:
    if body.component_type == "RecordList":
        return "records"
    if body.component_type == "ComparisonGroup":
        return "comparison"
    if "attributes" in body.props:
        return "attributes"
    return "content"


def score_static_presentation(
    source: str, plan: dict, size: str, preferred: str, omitted_indexes: tuple[int, ...],
) -> StaticPresentationScore:
    """分数只比较已合法的候选；尺寸由既有展开合同解析，不另猜参考画布。"""
    original = parse_compact_dsl_rows(source, expand_layouts=False)
    body = None
    root = None
    for row in original:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_id == "body":
            body = row
        elif row.component_id == "root":
            root = row
    if body is None or root is None:
        raise ValueError("静态候选缺少正文或布局根节点。")
    components = []
    for row in parse_compact_dsl_rows(source, size=size):
        if isinstance(row, ComponentRow):
            components.append(row)
    expanded = expand_high_level_component_rows(components, size=size, data_model={})
    metrics = _text_metrics(expanded)
    flattened, duplicates = _hierarchy_metrics(source, body.props, plan)
    readability = 40.0 - min(18.0, metrics.font_deficit * 9.0)
    readability -= min(12.0, metrics.wrapped_lines * 1.5)
    readability -= min(6.0, metrics.orphan_lines * 3.0)
    structure = 25.0 if _presentation_style(body) == preferred else 15.0
    hierarchy = 25.0 - min(15.0, flattened * 2.0) - min(10.0, duplicates * 3.0)
    spacing = 8.0 if root.props.get("variant") == "compact" else 10.0
    return StaticPresentationScore(
        omitted_indexes, readability, structure, hierarchy, spacing,
        metrics.wrapped_lines, metrics.orphan_lines, flattened, duplicates,
    )
