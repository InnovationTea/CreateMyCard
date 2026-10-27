"""将模板定稿 A2UI 适配为公共图片事实；不保存逐图/逐业务模板白名单。"""

from __future__ import annotations

import json

from services.compact_high_level_components import ComponentRow
from services.content_business import BusinessContext
from services.theme_content_regions import body_text_flow_evidence, top_content_evidence
from services.theme_photo_eligibility import _fully_centered
from services.theme_photo_matching import PhotoMatchFacts, PhotoScopeFacts
from services.theme_texture_eligibility import holiday_countdown

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
        if node.get("onClick") or _surface(node) or not _neutral_alignment(node, child):
            break
        node = child
    return node


def _neutral_alignment(node: dict, child: dict) -> bool:
    styles = normalize_photo_styles(node.get("styles", {}))
    child_styles = child.get("styles", {})
    fills_width = child_styles.get("width") in {"matchParent", "100%"}
    fills_height = child_styles.get("height") in {"matchParent", "100%"}
    kind = node.get("component")
    if kind == "Stack":
        if styles.get("alignContent", "center") == "topStart":
            return True
        return fills_width and fills_height
    if kind == "Column":
        horizontal = styles.get("alignItems", "start") in {"start", "stretch"} or fills_width
        vertical = styles.get("justifyContent", "start") == "start" or fills_height
    else:
        horizontal = styles.get("justifyContent", "start") == "start" or fills_width
        vertical = styles.get("alignItems", "center") in {"start", "top", "stretch"} or fills_height
    return horizontal and vertical


def _surface(node: dict) -> bool:
    background = node.get("styles", {}).get("backgroundColor")
    return isinstance(background, str) and background.startswith("#") and background[1:3] != "00"


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
    titles = []
    for node in nodes:
        if node.get("component") == "Text" and title and node.get("content") == title:
            titles.append(node.get("id"))
    # 只排除上层已确认且能唯一对应的标题；左右位置不影响标题身份。
    if len(titles) == 1:
        excluded.add(titles[0])
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


def _flatten_values(value: object, path: str, result: dict) -> None:
    result[path] = value
    if isinstance(value, dict):
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            _flatten_values(child, path + "/" + escaped, result)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _flatten_values(child, path + "/" + str(index), result)


def template_photo_facts(
    source: str, task: dict, title: str | None = None, *, button_ids: frozenset[str] = frozenset(),
) -> PhotoMatchFacts:
    nodes = []
    data_model = None
    for line in source.splitlines():
        record = json.loads(line)
        nodes.extend(record.get("updateComponents", {}).get("components", []))
        update = record.get("updateDataModel", {})
        if update.get("path") == "/":
            data_model = update.get("value")
    by_id = {node.get("id"): node for node in nodes}
    size = task.get("size")
    if len(by_id) != len(nodes) or "template_root" not in by_id:
        return PhotoMatchFacts(size, error="模板定稿缺少唯一内容树")
    canvas = by_id.get("root", {}).get("styles", {})
    if canvas.get("width") != "matchParent" or canvas.get("height") != "matchParent":
        return PhotoMatchFacts(size, error="背景需要自适应前景根节点")
    root = _unwrap(by_id.get("template_root"), by_id)
    scoped = _scope_nodes(root, by_id)
    if not scoped:
        return PhotoMatchFacts(size, error="模板内容树不完整")
    excluded = _body_exclusions(scoped, title)
    excluded.update(button_ids)
    # 标题和按钮是读取期排除，不从交付树删除。
    flow_nodes = _flow_nodes(scoped)
    # 公共文字分析以 root 为入口；只在只读分析副本上替换作用域 ID。
    scoped_id = root.get("id")
    analysis = []
    top_analysis = []
    for node in flow_nodes:
        if node.get("id") == scoped_id:
            analyzed = {**node, "id": "root"}
        else:
            analyzed = node
        analysis.append(analyzed)
        original = by_id.get(node.get("id"), {})
        original_styles = normalize_photo_styles(original.get("styles", {}))
        top_analysis.append({**analyzed, "styles": original_styles})
    flows = body_text_flow_evidence(
        analysis, data_model, include_buttons=True, exclude_ids=excluded,
    )
    if scoped_id != "root":
        flows[scoped_id] = flows.get("root", {})
    values = {}
    _flatten_values(data_model, "", values)
    catalog = BusinessContext.from_task(task)

    def scope_facts(scope: dict) -> PhotoScopeFacts:
        visible = _scope_nodes(scope, by_id)
        rows = []
        for node in visible:
            props = {**node.get("styles", {}), **node}
            props.pop("styles", None)
            rows.append(ComponentRow(node.get("id"), node.get("component"), props,
                                     tuple(node.get("children", []))))
        businesses = catalog.visible(rows)
        flow = flows.get(scope.get("id"), {})
        return PhotoScopeFacts(
            businesses, body_flow=flow, texture_flow=flow,
            centered=bool(rows) and _fully_centered(rows[0], rows),
            bottom=_bottom_left(scope, flows, by_id),
            holiday=holiday_countdown(rows, values, businesses=businesses),
        )

    scopes = {"card": scope_facts(root)}
    count = _panel_count(root, by_id)
    if size == "2x4":
        main, orientation = _main_scope(root, by_id, excluded)
        if main is not None:
            facts = scope_facts(main)
            scopes["main-focus"] = facts
            if orientation in {"left", "right"}:
                scopes["side-focus"] = facts
            if orientation == "left":
                scopes["left-main-dual"] = facts
    top = top_content_evidence(top_analysis, flows, excluded)
    split = "2x4左右两个大背板布局不使用图片背景" if count == 2 and size == "2x4" else None
    return PhotoMatchFacts(size, scopes=scopes, panel_count=count,
                           top_content=top, subject_exclusion=split)


def _children(node: dict, by_id: dict) -> list[dict]:
    return [_unwrap(by_id.get(identity, {}), by_id) for identity in node.get("children", [])]


def _two_surfaces(node: dict, by_id: dict) -> bool:
    children = _children(node, by_id)
    return len(children) == 2 and all(_surface(child) for child in children)


def _panel_count(root: dict, by_id: dict) -> int | None:
    children = _children(root, by_id)
    result = None
    if root.get("component") == "Row" and len(children) == 2:
        if all(_surface(child) for child in children):
            result = 2
    if root.get("component") in {"Column", "Row"} and len(children) == 2:
        expected = "Row" if root.get("component") == "Column" else "Column"
        if all(child.get("component") == expected for child in children):
            if all(_two_surfaces(child, by_id) for child in children):
                result = 4
    return result


def _title_only(root: dict, by_id: dict, excluded: set[str]) -> bool:
    text_found = False
    for node in _scope_nodes(root, by_id):
        if node.get("component") == "Button" or node.get("onClick"):
            return False
        if node.get("component") == "Text":
            if node.get("id") not in excluded:
                return False
            text_found = True
    return text_found


def _main_scope(root: dict, by_id: dict, excluded: set[str]) -> tuple[dict | None, str | None]:
    result: tuple[dict | None, str | None] = (None, None)
    visited = set()
    while root.get("id") not in visited:
        visited.add(root.get("id"))
        children = []
        for child in _children(root, by_id):
            if not _title_only(child, by_id, excluded):
                children.append(child)
        if len(children) != 1 or _surface(root) or root.get("onClick"):
            break
        child = children[0]
        if not _neutral_alignment(root, child):
            break
        root = child
    if root.get("component") in {"Row", "Column"} and len(children) == 2:
        matches: list[tuple[dict, str]] = []
        for index, child in enumerate(children):
            other = children[1 - index]
            side_kind = "Column" if root.get("component") == "Row" else "Row"
            if _surface(child) or other.get("component") != side_kind:
                continue
            if side_kind == "Column" and not _two_surfaces(other, by_id):
                continue
            directions = ("left", "right") if side_kind == "Column" else ("top", "bottom")
            matches.append((child, directions[index]))
        if len(matches) == 1:
            result = matches[0]
    return result
