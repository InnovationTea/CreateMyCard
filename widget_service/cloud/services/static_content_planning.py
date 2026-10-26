"""静态计划仅试排，不识别语义或替模型删改展示内容。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StaticPlanSelection:
    facts: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    notes: list[str]
    omitted_contents: tuple[str, ...] = ()
    presentation: str | None = None
    trial_errors: tuple[str, ...] = ()


def select_static_plan_content(
    facts: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    query: str,
    size: str,
    *,
    presentation_style: str = "auto",
) -> StaticPlanSelection:
    """有界候选只作为排版参考，未找到不证明所有合法排版不可行。"""
    from services.static_content_presentation import trial_static_presentation

    trial = trial_static_presentation(
        {
            "info_required": facts,
            "contentGroups": groups,
            "presentationStyle": presentation_style,
        },
        query,
        size,
    )
    feedback = tuple(error[:900] for error in trial.errors[:3])
    return StaticPlanSelection(
        facts, groups, [], presentation=trial.source, trial_errors=feedback,
    )


def normalize_static_record_table(source: str) -> str:
    """四至六条带值的记录改为属性表；仅改形态，所有原文字和顺序保留。"""
    import json

    from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows

    rows = parse_compact_dsl_rows(source, expand_layouts=False)
    changed = False
    encoded = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            encoded.append([row.path, row.value])
            continue
        props = row.props
        items = props.get("items")
        eligible = row.component_type == "RecordList" and isinstance(items, list)
        shape_allowed = not set(props) - {"items", "variant"} and not row.children
        if eligible and shape_allowed and 4 <= len(items) <= 6:
            attributes = _record_attributes(items)
            if attributes is not None and props.get("variant", "plain") in {"plain", "panel"}:
                row = ComponentRow(row.component_id, "ContentBlock", {"attributes": attributes}, ())
                changed = True
        output = [row.component_id, row.component_type, row.props]
        if row.children:
            output.append(list(row.children))
        encoded.append(output)
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in encoded) if changed else source


def _record_attributes(items: list[Any]) -> list[dict[str, str]] | None:
    attributes = []
    for item in items:
        if not isinstance(item, dict):
            return None
        if set(item) - {"title", "description", "leading", "trailing"}:
            return None
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        values = []
        for key in ("leading", "description", "trailing"):
            if key not in item:
                continue
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                return None
            values.append(value)
        if not values:
            return None
        attributes.append({"label": title, "value": " · ".join(values)})
    return attributes
