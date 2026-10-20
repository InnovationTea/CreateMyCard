"""2x4 无损紧凑候选；只改语义源树，不编辑展开后的几何。"""

from __future__ import annotations

import copy
import json
from collections import deque
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

from services.card_validation.base import expression_references
from services.card_validation.compact_validation.schema import _schema_node_at_path
from services.compact_component_runtime import secondary_body_variant, visual_recipe_part
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow
from services.compact_outer_recomposition import _joined_value

Rows = tuple[ComponentRow | DataRow, ...]
_RELATED_FIELDS = {
    ("date", "weekday"): frozenset({"星期", "周几"}),
    ("condition", "temperatureRangeText"): frozenset({"温度范围", "气温", "今日", "温度"}),
}


def serialize_rows(rows: Rows) -> str:
    lines = []
    for row in rows:
        if isinstance(row, DataRow):
            value = [row.path, row.value]
        else:
            value = [row.component_id, row.component_type, row.props]
            if row.children:
                value.append(list(row.children))
        lines.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def _rewrite(rows: Rows, changes: dict[str, ComponentRow], removed: set[str]) -> Rows:
    result = []
    for row in rows:
        if isinstance(row, ComponentRow):
            if row.component_id in removed:
                continue
            row = changes.get(row.component_id, row)
        result.append(row)
    return tuple(result)


def binding_paths(value: Any) -> set[str]:
    paths: set[str] = set()
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str):
                paths.add(path)
            for key, child in item.items():
                if key != "onClick":
                    pending.append(child)
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, str):
            paths.update(expression_references(item))
    return paths


def _owner(items: list[dict[str, Any]]) -> str | None:
    paths = binding_paths(items)
    owners: set[str] = set()
    for path in paths:
        if not path.startswith("/data/"):
            return None
        owners.add(path.rpartition("/")[0])
    return next(iter(owners)) if len(owners) == 1 else None


def _items(row: ComponentRow) -> list[dict[str, Any]] | None:
    if row.component_type != "SecondaryBody" or row.children:
        return None
    if set(row.props) - {"items", "columns", "separator", "fontSize"}:
        return None
    columns = row.props.get("columns", 2)
    if isinstance(columns, bool) or not isinstance(columns, int) or columns not in {1, 2}:
        return None
    items = row.props.get("items")
    if not isinstance(items, list) or not items:
        return None
    for item in items:
        if not isinstance(item, dict) or "value" not in item:
            return None
        if set(item) - {"label", "value", "maxLines"}:
            return None
    return items


def _with_items(row: ComponentRow, items: list[dict[str, Any]], columns: int) -> ComponentRow:
    props = copy.deepcopy(row.props)
    props.update(items=copy.deepcopy(items), columns=columns)
    variant = secondary_body_variant(items, columns)
    _, styles = visual_recipe_part("SecondaryBody", "text", size="2x4", variant=variant)
    props["fontSize"] = styles.get("fontSize")
    return replace(row, props=props)


def _related_pair(left: dict, right: dict, task: dict) -> dict | None:
    first, second = left.get("value"), right.get("value")
    if not isinstance(first, dict) or not isinstance(second, dict):
        return None
    if set(first) != {"path"} or set(second) != {"path"}:
        return None
    a, b = first.get("path"), second.get("path")
    if not isinstance(a, str) or not isinstance(b, str):
        return None
    if a.rpartition("/")[0] != b.rpartition("/")[0]:
        return None
    labels = _RELATED_FIELDS.get((a.rpartition("/")[2], b.rpartition("/")[2]))
    label = right.get("label")
    if labels is None or not isinstance(label, str) or label.strip() not in labels:
        return None
    schema = task.get("dataModelSchema")
    for path in (a, b):
        node = _schema_node_at_path(schema, path)
        if not isinstance(node, dict) or node.get("type") != "string":
            return None
    if left.get("maxLines", 1) != 1 or right.get("maxLines", 1) != 1:
        return None
    joined = copy.deepcopy(left)
    joined["value"] = "{{ ${" + a + "} + ' ' + ${" + b + "} }}"
    return joined


def _related_items(items: list[dict], task: dict) -> list[dict]:
    result = []
    index = 0
    while index < len(items):
        current = items[index]
        following = index + 1
        joined = None
        if following < len(items):
            joined = _related_pair(current, items[following], task)
        if joined is not None:
            result.append(joined)
            index += 2
        else:
            result.append(copy.deepcopy(current))
            index += 1
    return result


def _secondary_options(row: ComponentRow, task: dict, wrap: bool) -> list[ComponentRow]:
    items = _items(row)
    if items is None:
        return [row]
    groups = []
    related = _related_items(items, task)
    if related != items:
        groups.append(related)
    unique = []
    for item in items:
        if item not in unique or not binding_paths(item):
            unique.append(copy.deepcopy(item))
    if unique != items:
        groups.append(unique)
    groups.append(items)
    options = [row]
    for group in groups:
        for columns in (2, 1):
            candidate = _with_items(row, group, columns)
            if candidate not in options:
                options.append(candidate)
        if wrap:
            multiline = copy.deepcopy(group)
            for item in multiline:
                item["maxLines"] = 2
            candidate = _with_items(row, multiline, 1)
            if candidate not in options:
                options.append(candidate)
    return options


def _merge_supporting(rows: Rows) -> Rows:
    nodes = {row.component_id: row for row in rows if isinstance(row, ComponentRow)}
    changes = {}
    removed: set[str] = set()
    for parent in nodes.values():
        if len(parent.children) != 2 or parent.component_type != "Group":
            continue
        if parent.props.get("variant") not in {"hero-support", "peer-pair"}:
            continue
        left, right = nodes.get(parent.children[0]), nodes.get(parent.children[1])
        if left is None or right is None:
            continue
        a, b = _items(left), _items(right)
        if a is None or b is None:
            continue
        owner = _owner(a)
        if owner is None or owner != _owner(b) or len(a) + len(b) > 6:
            continue
        first_style, second_style = dict(left.props), dict(right.props)
        for key in ("items", "fontSize"):
            first_style.pop(key, None)
            second_style.pop(key, None)
        if first_style != second_style:
            continue
        merged = _with_items(left, [*a, *b], int(left.props.get("columns", 2)))
        changes[parent.component_id] = replace(merged, component_id=parent.component_id)
        removed.update(parent.children)
    return _rewrite(rows, changes, removed)


def _region_variants(rows: Rows) -> Iterator[tuple[str, Rows]]:
    changes = {}
    added = []
    ids = {row.component_id for row in rows if isinstance(row, ComponentRow)}
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "Region":
            continue
        if row.props.get("variant") != "title-hero-support" or len(row.children) != 3:
            continue
        identifier = row.component_id + "_compact_group"
        while identifier in ids:
            identifier += "_"
        ids.add(identifier)
        props = copy.deepcopy(row.props)
        props["variant"] = "title-content"
        changes[row.component_id] = replace(
            row, props=props, children=(row.children[0], identifier),
        )
        added.append(ComponentRow(
            identifier, "Group", {"variant": "hero-support"}, row.children[1:],
        ))
    if changes:
        yield "semantic_region_regroup", (*_rewrite(rows, changes, set()), *added)
    root = next((row for row in rows if isinstance(row, ComponentRow)), None)
    if root is not None and root.props.get("layout") == "W-top-bottom":
        for variant in ("continuous", "bottom-details", "equal"):
            if root.props.get("variant", "continuous") == variant:
                continue
            props = copy.deepcopy(root.props)
            props["variant"] = variant
            yield "semantic_layout_variant", _rewrite(
                rows, {root.component_id: replace(root, props=props)}, set(),
            )


def core_role_variants(rows: Rows, plan: dict[str, Any] | None) -> Iterator[tuple[str, Rows]]:
    """只迁移 Plan 已推荐 EmphasisText 的唯一既有事实，不补造核心。"""
    eligible: set[str] = set()
    for fact in (plan or {}).get("info_required", []):
        path = fact.get("dataId")
        if isinstance(path, str) and "EmphasisText" in fact.get("componentHints", []):
            eligible.add(path)
    nodes = {row.component_id: row for row in rows if isinstance(row, ComponentRow)}
    for parent in nodes.values():
        if parent.component_type != "Region" or parent.props.get("variant") != "title-content":
            continue
        if len(parent.children) != 2:
            continue
        body = nodes.get(parent.children[1])
        items = _items(body) if body is not None else None
        if items is None or len(items) < 2:
            continue
        for index, item in enumerate(items):
            paths = binding_paths(item.get("value"))
            if len(paths) != 1 or not paths <= eligible:
                continue
            value = copy.deepcopy(item.get("value"))
            label = item.get("label", "")
            if not isinstance(label, str):
                continue
            if label:
                value = _joined_value(label, value)
                if value is None:
                    continue
            identifier = body.component_id + "_compact_core"
            while identifier in nodes:
                identifier += "_"
            _, styles = visual_recipe_part("EmphasisText", "main", size="2x4")
            core = ComponentRow(identifier, "EmphasisText", {
                "mainText": value, "fontSize": styles.get("fontSize"),
            })
            remaining = []
            for item_index, remaining_item in enumerate(items):
                if item_index != index:
                    remaining.append(remaining_item)
            props = copy.deepcopy(parent.props)
            props["variant"] = "title-hero-support"
            changes = {
                parent.component_id: replace(
                    parent, props=props,
                    children=(parent.children[0], identifier, body.component_id),
                ),
                body.component_id: _with_items(body, remaining, int(body.props.get("columns", 2))),
            }
            yield "restore_core_role", (*_rewrite(rows, changes, set()), core)


def simplification_variants(
    rows: Rows, task: dict[str, Any], *, wrap: bool = False,
) -> Iterator[tuple[str, Rows]]:
    """宽度/关系候选按广度联合，避免仅修改一个超限分区。"""
    seeds = [("existing_components", rows)]
    merged = _merge_supporting(rows)
    if merged != rows:
        seeds.insert(0, ("merge_supporting", merged))
    for seed_reason, seed in seeds:
        options = []
        for row in seed:
            if isinstance(row, ComponentRow):
                variants = _secondary_options(row, task, wrap)
                if len(variants) > 1:
                    options.append(variants)
        initial = tuple(0 for _ in options)
        pending = deque([initial])
        seen = {initial}
        while pending:
            indexes = pending.popleft()
            changes = {}
            for index, group in enumerate(options):
                selected = group[indexes[index]]
                changes[selected.component_id] = selected
            candidate = _rewrite(seed, changes, set())
            yield seed_reason + "+complete_text_reflow", candidate
            yield from _region_variants(candidate)
            for index, group in enumerate(options):
                following = list(indexes)
                following[index] += 1
                state = tuple(following)
                if following[index] < len(group) and state not in seen:
                    seen.add(state)
                    pending.append(state)
