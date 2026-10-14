"""失败后的语义组合候选与精简合同说明；固定几何仍由公共编译器维护。"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass

from app.logger import logger
from services.card_validation.base import expression_references, read_pointer
from services.card_validation.compact_validation.schema import _schema_node_at_path, _schema_type
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    build_compact_data_model,
    parse_compact_dsl_rows,
)
from services.compact_semantic_layout import region_variant_contracts

_Rows = list[ComponentRow | DataRow]
_TITLE_TYPES = frozenset({"SingleLineTitle", "DoubleLineTitle"})
_GROUP_VARIANTS = ("hero-support", "peer-pair")


@dataclass(frozen=True)
class _Change:
    rows: dict[str, ComponentRow]
    added: tuple[ComponentRow, ...] = ()


def _components(rows: _Rows) -> dict[str, ComponentRow]:
    result = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            result[row.component_id] = row
    return result


def _title(row: ComponentRow) -> bool:
    return row.component_type in _TITLE_TYPES or (
        row.component_type == "Group" and row.props.get("variant") == "title-count"
    )


def _leaves(identifier: str, nodes: dict[str, ComponentRow], visiting: tuple[str, ...] = ()):
    if identifier in visiting or len(visiting) >= 64:
        return ()
    row = nodes.get(identifier)
    if row is None:
        return ()
    if row.component_type != "Group":
        return (identifier,)
    if row.props.get("variant") == "title-count":
        return (identifier,)
    if set(row.props) != {"variant"}:
        return ()
    result = []
    for child in row.children:
        leaves = _leaves(child, nodes, (*visiting, identifier))
        if not leaves or len(result) + len(leaves) > 4:
            return ()
        result.extend(leaves)
    return tuple(result)


def _rewrite(rows: _Rows, changes: tuple[_Change, ...]) -> _Rows:
    updates = {}
    added = []
    for change in changes:
        updates.update(change.rows)
        added.extend(change.added)
    components = []
    data = []
    for row in rows:
        if isinstance(row, ComponentRow):
            components.append(updates.get(row.component_id, row))
        else:
            data.append(row)
    components.extend(added)
    nodes = _components(components)
    reachable = set()
    pending = ["root"]
    while pending:
        identifier = pending.pop()
        if identifier in reachable:
            continue
        reachable.add(identifier)
        node = nodes.get(identifier)
        if node is not None:
            pending.extend(node.children)
    result = []
    for row in components:
        unused_group = row.component_type == "Group" and row.component_id not in reachable
        if not unused_group:
            result.append(row)
    result.extend(data)
    return result


def _group_content(
    region: ComponentRow,
    children: tuple[str, ...],
    nodes: dict[str, ComponentRow],
    variant: str,
) -> tuple[str, tuple[ComponentRow, ...]]:
    added = []
    content = children[-1]
    for index in range(len(children) - 2, -1, -1):
        identifier = f"{region.component_id}_repair_group_{index}"
        while identifier in nodes:
            identifier += "_"
        added.append(
            ComponentRow(identifier, "Group", {"variant": variant}, (children[index], content))
        )
        content = identifier
    return content, tuple(added)


def _region_changes(region: ComponentRow, nodes: dict[str, ComponentRow]) -> Iterator[_Change]:
    children = list(region.children)
    if not children:
        return
    header = nodes.get(children[0])
    title = children.pop(0) if header is not None and _title(header) else None
    action = None
    if children:
        last = nodes.get(children[-1])
        if last is not None and last.component_type == "PillButton":
            action = children.pop()
    contents = []
    for identifier in children:
        leaves = _leaves(identifier, nodes)
        if not leaves:
            return
        contents.extend(leaves)
    if action is None and contents:
        last = nodes.get(contents[-1])
        if last is not None and last.component_type == "PillButton":
            action = contents.pop()
    if not 1 <= len(contents) <= 4:
        return
    for identifier in contents:
        row = nodes.get(identifier)
        if row is None:
            return
        invalid_content = row.component_type in {"Region", "Layout", "InfoBlock", "CardButton"}
        if invalid_content or row.component_type == "PillButton" or row.props.get("onClick"):
            return
    if title is None and action is not None:
        return
    for group_variant in _GROUP_VARIANTS:
        content, added = _group_content(region, tuple(contents), nodes, group_variant)
        variant = "center"
        references = (content,)
        if title is not None:
            variant = "title-content"
            references = (title, content)
        if action is not None:
            variant = "title-content-action"
            references = (*references, action)
        replacement = ComponentRow(region.component_id, "Region", {"variant": variant}, references)
        yield _Change({region.component_id: replacement}, added)
    if title is not None and action is None and len(contents) == 2:
        replacement = ComponentRow(
            region.component_id, "Region", {"variant": "title-primary-details"}, (title, *contents)
        )
        yield _Change({region.component_id: replacement})


def semantic_layout_variants(rows: _Rows) -> Iterator[tuple[str, _Rows]]:
    """只改变已有语义组合；业务行、数据行和对象所属 Region 保留。"""
    nodes = _components(rows)
    root = nodes.get("root")
    if root is None or root.component_type != "Layout":
        return
    if root.props.get("layout") == "W-top-bottom":
        for variant in ("continuous", "bottom-details", "equal"):
            props = copy.deepcopy(root.props)
            props["variant"] = variant
            changed = ComponentRow("root", "Layout", props, root.children)
            yield "semantic_layout_variant", _rewrite(rows, (_Change({"root": changed}),))
    region_options = []
    for row in nodes.values():
        if row.component_type == "Group" and row.props.get("variant") in _GROUP_VARIANTS:
            for variant in _GROUP_VARIANTS:
                if variant == row.props.get("variant"):
                    continue
                changed = ComponentRow(
                    row.component_id, "Group", {"variant": variant}, row.children
                )
                patch = _Change({row.component_id: changed})
                yield "semantic_group_reflow", _rewrite(rows, (patch,))
        if row.component_type != "Region":
            continue
        options = list(_region_changes(row, nodes))
        if options:
            region_options.append(options)
    # 先同时闭合两个区域，避免只改一侧被另一侧的容量错误持续拒绝。
    if len(region_options) == 2:
        left, right = region_options
        for left_patch in left:
            for right_patch in right:
                yield "semantic_region_regroup", _rewrite(rows, (left_patch, right_patch))
    for options in region_options:
        for patch in options:
            yield "semantic_region_regroup", _rewrite(rows, (patch,))


def _binding_paths(value: object) -> set[str]:
    paths = set()
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            path = current.get("path")
            if isinstance(path, str):
                paths.add(path)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, str):
            paths.update(expression_references(current))
    return paths


def _detail_items(row: ComponentRow) -> list[dict] | None:
    result = None
    if row.component_type != "TextBlock" or row.children:
        return result
    if set(row.props) - {"items", "fontColor"}:
        return result
    items = row.props.get("items")
    if not isinstance(items, list) or len(items) not in (2, 3):
        return result
    for item in items:
        if not isinstance(item, dict) or set(item) != {"label", "value"}:
            return result
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            return result
        value = item.get("value")
        if not isinstance(value, dict) or set(value) != {"path"}:
            return result
        if not isinstance(value.get("path"), str):
            return result
    result = items
    return result


def _unique_id(base: str, nodes: dict[str, ComponentRow]) -> str:
    while base in nodes:
        base += "_"
    return base


def _same_object_content(
    root: ComponentRow, items: list[dict], nodes: dict[str, ComponentRow]
) -> bool:
    owners = set()
    for item in items:
        value = item.get("value")
        if not isinstance(value, dict):
            return False
        path = value.get("path")
        if not isinstance(path, str):
            return False
        owner = path.rpartition("/")[0]
        if not owner.startswith("/data/"):
            return False
        owners.add(owner)
    if len(owners) != 1:
        return False
    owner = next(iter(owners))
    primary_paths = set()
    for identifier in _leaves(root.children[-2], nodes):
        node = nodes.get(identifier)
        if node is not None:
            primary_paths.update(_binding_paths(node.props))
    if not primary_paths:
        return False
    for node in nodes.values():
        if node.props.get("onClick") or node.component_type in {
            "Region",
            "PillButton",
            "CardButton",
        }:
            return False
        for path in _binding_paths(node.props):
            if path.rpartition("/")[0] != owner:
                return False
    return root.props.get("layout") == "W-top-bottom"


def semantic_detail_variants(rows: _Rows, task_spec: dict) -> Iterator[tuple[str, _Rows]]:
    """同对象单区核心／属性详情拆入登记的双区，完整保留数值核心及格式化文本。"""
    nodes = _components(rows)
    root = nodes.get("root")
    if root is None or root.props.get("layout") != "W-top-bottom":
        return
    if len(root.children) not in (2, 3):
        return
    details = nodes.get(root.children[-1])
    if details is None:
        return
    items = _detail_items(details)
    if items is None or not _same_object_content(root, items, nodes):
        return
    schema = task_spec.get("dataModelSchema")
    data_rows = []
    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
    try:
        data = build_compact_data_model(data_rows)
    except CompactDslConversionError as exc:
        logger.debug(f"[Semantic repair] invalid data model: {exc}")
        return
    left_id = _unique_id("root_repair_core", nodes)
    right_id = _unique_id("root_repair_details", nodes)
    main_id = _unique_id(details.component_id + "_repair_main", nodes)
    support_id = _unique_id(details.component_id + "_repair_support", nodes)
    for index, item in enumerate(items):
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        path = value.get("path")
        if (
            not isinstance(path, str)
            or _schema_type(_schema_node_at_path(schema, path)) != "string"
        ):
            continue
        found, sample = read_pointer(data, path)
        if not found:
            continue
        if not isinstance(sample, str) or re.fullmatch(r"\s*[+-]?[\d.]+\s*", sample):
            continue
        support_items = []
        for other_index, other_item in enumerate(items):
            if other_index != index:
                support = copy.deepcopy(other_item)
                support["maxLines"] = 2
                support_items.append(support)
        main_props = {"mainText": copy.deepcopy(value), "secondaryText": item.get("label")}
        support_props = {"items": support_items, "columns": 1}
        if "fontColor" in details.props:
            main_props["fontColor"] = details.props.get("fontColor")
            support_props["fontColor"] = details.props.get("fontColor")
        props = copy.deepcopy(root.props)
        props["layout"] = "W-split-panels"
        props.pop("variant", None)
        left_children = root.children[:-1]
        left_variant = "title-content" if len(left_children) == 2 else "center"
        changed = {
            "root": ComponentRow("root", "Layout", props, (left_id, right_id)),
            details.component_id: ComponentRow(
                details.component_id, "Group", {"variant": "hero-support"}, (main_id, support_id)
            ),
        }
        added = (
            ComponentRow(left_id, "Region", {"variant": left_variant}, left_children),
            ComponentRow(right_id, "Region", {"variant": "center"}, (details.component_id,)),
            ComponentRow(main_id, "EmphasisText", main_props),
            ComponentRow(support_id, "SecondaryBody", support_props),
        )
        yield "semantic_core_details", _rewrite(rows, (_Change(changed, added),))


def semantic_repair_context(source: str) -> dict | None:
    """说明当前父区允许的真实变体，不注入完整候选或模板几何。"""
    result = None
    try:
        rows = list(parse_compact_dsl_rows(source, expand_layouts=False))
    except CompactDslConversionError as exc:
        logger.debug(f"[Semantic repair] context unavailable: {exc}")
        return result
    nodes = _components(rows)
    root = nodes.get("root")
    if root is None or root.component_type != "Layout":
        return result
    layout = root.props.get("layout")
    regions = []
    compact = layout == "W-split-panels"
    identifiers = ()
    if layout == "W-split-panels":
        identifiers = root.children[:2]
    elif layout == "W-content-side-slots":
        identifiers = root.children[:1]
    for identifier in identifiers:
        row = nodes.get(identifier)
        if row is None or row.component_type != "Region":
            continue
        regions.append(
            {
                "componentId": identifier,
                "area": "compact" if compact else "wide",
                "currentVariant": row.props.get("variant"),
                "allowedVariants": region_variant_contracts(compact=compact),
            }
        )
    result = {"layout": layout, "regions": regions}
    if layout == "W-top-bottom":
        result["detailsTypes"] = ["TextBlock", "TopTextBottomValue", "SummaryList"]
        result["sharedButtonAllowed"] = False
    return result
