"""将模板定稿树适配为公共图片准入事实，不使用模板名称或参考像素推断。"""

from __future__ import annotations

import json
from dataclasses import replace

from services.compact_high_level_components import ComponentRow
from services.theme_content_regions import body_text_flow_evidence, top_content_evidence
from services.theme_photo_eligibility import _fully_centered
from services.theme_texture_eligibility import (
    holiday_countdown,
    subtree,
    texture_business_reason,
    visible_business,
)

from .photo_layout import wide_photo_main
from .photo_policy import PhotoContentFacts, photo_facts_reason
from .photo_theme import normalize_photo_styles


def _unwrap(node: dict, by_id: dict) -> dict:
    visited = set()
    while node.get("component") in {"Row", "Column", "Stack"}:
        identity = node.get("id")
        children = node.get("children", [])
        if len(children) != 1 or identity in visited:
            break
        visited.add(identity)
        child = by_id.get(children[0])
        if child is None:
            break
        if child.get("component") not in {"Row", "Column", "Stack"}:
            break
        if node.get("onClick") or _surface(node):
            break
        node = child
    return node


def _surface(node: dict) -> bool:
    background = node.get("styles", {}).get("backgroundColor")
    return isinstance(background, str) and background.startswith("#") and background[1:3] != "00"


def _wide_main(root: dict, by_id: dict) -> dict:
    rows = {}
    for identity, node in by_id.items():
        props = {**node.get("styles", {}), **node}
        rows[identity] = ComponentRow(
            identity, node.get("component"), props, tuple(node.get("children", [])),
        )
    row = rows.get(root.get("id"))
    main = wide_photo_main(row, rows) if row is not None else None
    return by_id.get(main.component_id, {}) if main is not None else {}


def _scope_nodes(root: dict, by_id: dict) -> list[dict]:
    result = []
    pending = [root.get("id")]
    visited = set()
    while pending:
        identity = pending.pop()
        node = by_id.get(identity)
        if node is None or identity in visited:
            return []
        visited.add(identity)
        result.append(node)
        pending.extend(reversed(node.get("children", [])))
    return result


def _body_exclusions(nodes: list[dict], title: str | None) -> set[str]:
    excluded = set()
    first_text = next((node for node in nodes if node.get("component") == "Text"), None)
    # 只排除上层已确认的标题；未知静态标签保守计入正文，不按字号猜标题。
    if title and first_text is not None and first_text.get("content") == title:
        excluded.add(first_text.get("id"))
    for node in nodes:
        if node.get("component") == "Button":
            excluded.add(node.get("id"))
    return excluded


def _has_text(node: dict, by_id: dict) -> bool:
    return any(item.get("component") == "Text" for item in _scope_nodes(node, by_id))


def _flow_nodes(nodes: list[dict]) -> list[dict]:
    """满宽子项的居中槽不改变正文对齐；仅归一化可从树中证明的情况。"""
    by_id = {node.get("id"): node for node in nodes}
    result = []
    for node in nodes:
        styles = normalize_photo_styles(node.get("styles", {}))
        children = node.get("children", [])
        fills = bool(children)
        for identity in children:
            child = by_id.get(identity, {})
            fills = fills and child.get("styles", {}).get("width") in {"matchParent", "100%"}
        if node.get("component") == "Column" and fills:
            styles["alignItems"] = "stretch"
        if node.get("component") == "Stack":
            text_children = []
            for identity in children:
                child = by_id.get(identity, {})
                if _has_text(child, by_id):
                    text_children.append(child)
            if len(text_children) == 1:
                text_style = text_children[0].get("styles", {})
                if text_style.get("width") in {"matchParent", "100%"}:
                    styles["alignContent"] = "topStart"
        result.append({**node, "styles": styles})
    return result


def _bottom_left(root: dict, flows: dict, by_id: dict) -> bool:
    styles = root.get("styles", {})
    if root.get("component") != "Column":
        return False
    if styles.get("alignItems", "start") not in {"start", "stretch"}:
        return False
    children = root.get("children", [])
    body = [identity for identity in children if flows.get(identity, {}).get("lineCount")]
    if not body:
        return False
    placement = styles.get("justifyContent", "start")
    if placement == "end":
        return True
    if placement == "spaceBetween":
        return len(body) == 1 and body[0] == children[-1]
    if len(body) == 1:
        child = by_id.get(body[0], {})
        if child.get("styles", {}).get("height") == "matchParent":
            return _bottom_left(child, flows, by_id)
    return False


def template_photo_reason(photo: dict, source: str, size: str, title: str | None) -> str | None:
    nodes = []
    data_model = None
    for line in source.splitlines():
        record = json.loads(line)
        nodes.extend(record.get("updateComponents", {}).get("components", []))
        update = record.get("updateDataModel", {})
        if update.get("path") == "/" and isinstance(update.get("value"), dict):
            data_model = update.get("value")
    by_id = {node.get("id"): node for node in nodes}
    root = _unwrap(by_id.get("template_root", {}), by_id)
    if size == "2x4":
        main = _wide_main(root, by_id)
        if not main:
            return "定稿模板没有可确认的主内容区或右侧单／双背板结构"
        if photo.get("pool") != "texturePhotos":
            root = main
    if not root:
        return "定稿模板没有可确认的主内容区或右侧单／双背板结构"
    scoped = _scope_nodes(root, by_id)
    if not scoped:
        return "模板主内容树不完整"
    excluded = _body_exclusions(scoped, title)
    # 公共流检查从 root 遍历；作用域换名只用于事实提取，不改动交付节点。
    scoped_root = {**root, "id": "root"}
    scoped = [scoped_root, *scoped[1:]]
    flows = body_text_flow_evidence(
        _flow_nodes(scoped), data_model, include_buttons=True, exclude_ids=excluded,
    )
    flow = flows.get("root", {})
    rows = []
    for node in scoped:
        props = {**node.get("styles", {}), **node}
        props.pop("styles", None)
        rows.append(ComponentRow(node.get("id"), node.get("component"), props,
                                 tuple(node.get("children", []))))
    row_map = {row.component_id: row for row in rows}
    visible = subtree("root", row_map)
    if photo.get("pool") == "texturePhotos":
        reason = texture_business_reason(photo, visible)
        if reason is not None:
            return reason
    facts = PhotoContentFacts(
        size=size, business=visible_business(visible), line_count=flow.get("lineCount"),
        left_aligned=flow.get("leftAligned") is True, centered=_fully_centered(rows[0], visible),
        bottom_left=_bottom_left(scoped_root, flows, by_id) and flow.get("leftAligned") is True,
        wide_layout=size == "2x4", top_content=top_content_evidence(scoped, flows, excluded),
    )
    if "holiday" in photo.get("contentEligibility", {}).get("businesses", []):
        values = {}
        _flatten_values(data_model, "", values)
        business = "holiday" if holiday_countdown(visible, values) else None
        facts = replace(facts, business=business)
    return photo_facts_reason(photo, facts)


def _flatten_values(value: object, path: str, result: dict) -> None:
    result[path] = value
    if isinstance(value, dict):
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            _flatten_values(child, path + "/" + escaped, result)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _flatten_values(child, path + "/" + str(index), result)
