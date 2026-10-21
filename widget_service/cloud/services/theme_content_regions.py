"""识别布局内容与完整按钮，不推测端侧 matchParent 的真实尺寸。"""

from __future__ import annotations

from services.card_validation.base import read_pointer
from services.display_text import concatenated_display_text
from services.theme_style_roles import ROLE_PATTERN, is_role


def panel_ids(nodes: list[dict]) -> list[str]:
    result = []
    for node in nodes:
        background = node.get("styles", {}).get("backgroundColor")
        if node.get("component") not in {"Row", "Column", "Stack"} or not is_role(background):
            continue
        match = ROLE_PATTERN.fullmatch(background)
        if match is not None and match[1] == "panel" and float(match[2] or 1) > 0:
            result.append(node.get("id"))
    return result


def button_ids(nodes: list[dict]) -> list[str]:
    result = []
    for node in nodes:
        if node.get("component") != "Button" and not node.get("onClick"):
            continue
        identity = node.get("id")
        # 整卡点击是画布事件，不将整个卡片误识别成按钮。
        if isinstance(identity, str) and identity != "root":
            result.append(identity)
    return result


def photo_layout_evidence(nodes: list[dict], data_model: dict | None = None,
                          *, final_layout: str | None = None) -> dict:
    roots = [node for node in nodes if node.get("id") == "root"]
    content_ids = []
    non_text_ids = []
    for node in nodes:
        if node.get("component") not in {"Row", "Column", "Stack"} and node.get("id"):
            content_ids.append(node.get("id"))
        if node.get("component") not in {"Text", "Row", "Column", "Stack"}:
            non_text_ids.append(node.get("id"))
    reason = None
    if len(roots) != 1 or not content_ids:
        reason = "缺少定稿内容"
    else:
        styles = roots[0].get("styles", {})
        if styles.get("width") != "matchParent" or styles.get("height") != "matchParent":
            reason = "背景需要自适应前景根节点"
    result = {"basis": "layout-only", "complete": reason is None, "reason": reason,
              "contentIds": content_ids, "buttonIds": button_ids(nodes),
              "panelIds": panel_ids(nodes),
              "sideBySidePanels": _side_by_side_panels(nodes),
              "nonTextIds": non_text_ids,
              "nonTextAncestors": _non_text_ancestors(nodes, non_text_ids),
              "textFlow": text_flow_evidence(nodes),
              "deviceGeometryKnown": False}
    if data_model is not None:
        result["bodyTextFlow"] = body_text_flow_evidence(nodes, data_model)
        title_ids = _layout_title_ids(final_layout)
        if title_ids is not None:
            result["photoBodyTextFlow"] = body_text_flow_evidence(
                nodes, data_model, include_buttons=True, exclude_ids=title_ids,
            )
            result["photoTopContent"] = top_content_evidence(
                nodes, result.get("photoBodyTextFlow", {}), title_ids,
            )
    return result


def _top_flow_alignment_reason(node: dict, children: list[dict], stretched: bool) -> str | None:
    styles = node.get("styles", {})
    kind = node.get("component")
    reason: str | None = None
    if kind == "Column" and styles.get("justifyContent", "start") != "start":
        reason = "存在居中、贴底或上下分散的内容"
    elif kind == "Stack" and styles.get("alignContent", "center") != "topStart":
        reason = "存在非左上锚定的叠层内容"
    elif kind == "Row":
        alignment = styles.get("alignItems", "center")
        if stretched and alignment not in {"top", "start"}:
            reason = "横排内容没有固定在顶部"
    if kind == "Column" and reason is None:
        reserved = False
        body_seen = False
        for child in children:
            if child.get("visible") and reserved:
                reason = "伸展区域或占位之后还有前景内容"
                break
            if child.get("visible") and body_seen and not child.get("bodyLines"):
                reason = "正文下方还有独立图标、按钮或背板等内容"
                break
            reserved = reserved or child.get("reserved", False)
            body_seen = body_seen or bool(child.get("bodyLines"))
    return reason


def top_content_evidence(nodes: list[dict], body_flows: dict, opaque_ids: set[str]) -> dict:
    """按组件树确认顶部连续内容流；不将标题/按钮从实际占位检查中删除。"""
    by_id = {node.get("id"): node for node in nodes}
    containers = {"Row", "Column", "Stack"}
    leaves = {"Text", "Image", "Icon", "Divider", "Button", "Progress"}

    def visit(identity: str, ancestors: set[str], parent: str | None) -> dict:
        node = by_id.get(identity)
        if node is None or identity in ancestors:
            return {"reason": "内容树不完整或存在循环", "visible": True}
        styles = node.get("styles", {})
        kind = node.get("component")
        height = styles.get("height")
        weight = styles.get("layoutWeight", 0)
        weighted = parent == "Column" and isinstance(weight, (int, float)) and weight > 0
        stretched = weighted or height == "matchParent"
        if isinstance(height, str) and height.endswith("%"):
            stretched = True
        fixed_block = kind in {"Column", "Stack"} and height not in (None, "wrapContent")
        child_ids = node.get("children", [])
        opaque = identity in opaque_ids
        if kind == "Stack" and len(child_ids) == 1:
            opaque = opaque or child_ids[0] in opaque_ids
        children = []
        if not opaque:
            for child in child_ids:
                children.append(visit(child, ancestors | {identity}, kind))
        body_lines = body_flows.get(identity, {}).get("lineCount", 0)
        surface = styles.get("backgroundColor") not in (None, "transparent", "#00000000")
        surface = surface or bool(styles.get("linearGradient") or styles.get("backdropBlur"))
        surface = surface and identity != "root"
        visible = surface or kind not in containers
        child_visible = any(child.get("visible") for child in children)
        visible = visible or opaque or child_visible
        if kind == "Text" and body_lines == 0 and not opaque:
            visible = surface
        reason = next((child.get("reason") for child in children if child.get("reason")), None)
        if any(key in styles for key in ("position", "offset", "translate", "alignSelf")):
            reason = "存在无法确认顶部位置的独立定位"
        elif not opaque and visible and reason is None:
            if kind in containers:
                reason = _top_flow_alignment_reason(node, children, stretched)
            elif kind not in leaves or stretched:
                reason = "无法确认前景元素只占用顶部"
        if surface and (stretched or fixed_block):
            reason = "背板覆盖了伸展或固定高度区域"
        if opaque and stretched:
            reason = "标题或按钮占用了无法确认位置的伸展高度"
        reserved = stretched or (fixed_block and not opaque)
        reserved = reserved or any(child.get("reserved") for child in children)
        return {"reason": reason, "visible": visible, "reserved": reserved,
                "bodyLines": body_lines}

    root = visit("root", set(), None)
    return {"topOnly": root.get("reason") is None, "reason": root.get("reason"),
            "basis": "layout-structure", "deviceGeometryKnown": False}


def _side_by_side_panels(nodes: list[dict]) -> bool:
    by_id = {node.get("id"): node for node in nodes}
    panels = set(panel_ids(nodes))

    def unwrap(identity: str) -> dict:
        visited = set()
        node = by_id.get(identity, {})
        while node.get("component") in {"Row", "Column", "Stack"}:
            current = node.get("id")
            if current in visited or current in panels:
                break
            visited.add(current)
            child_ids = node.get("children", [])
            if len(child_ids) != 1:
                break
            node = by_id.get(child_ids[0], {})
        return node

    root = unwrap("root")
    children = root.get("children", [])
    if root.get("component") != "Row" or len(children) != 2:
        return False
    return all(unwrap(identity).get("id") in panels for identity in children)


def photo_layout_exclusion_reason(task: dict, evidence: dict,
                                  final_layout: str | None = None) -> str | None:
    reason: str | None = None
    if task.get("size") == "2x4":
        split = evidence.get("sideBySidePanels") is True
        if final_layout:
            from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows

            try:
                rows = parse_compact_dsl_rows(final_layout, expand_layouts=False)
            except ValueError:
                reason = "无法确认图片的定稿宽卡布局"
            else:
                for row in rows:
                    if isinstance(row, ComponentRow) and row.component_id == "root":
                        split = split or row.props.get("layout") == "W-split-panels"
        if split:
            reason = "2x4左右两个大背板布局不使用图片背景"
    return reason


def _non_text_ancestors(nodes: list[dict], identities: list[str]) -> dict:
    """用真实组件树区分标题装饰图标与内容视觉，不依赖生成ID的命名。"""
    parents = {}
    for node in nodes:
        for child in node.get("children", []):
            parents.setdefault(child, []).append(node.get("id"))
    result = {}
    for identity in identities:
        found = set()
        pending = list(parents.get(identity, []))
        while pending:
            parent = pending.pop()
            if not isinstance(parent, str) or parent in found:
                continue
            found.add(parent)
            pending.extend(parents.get(parent, []))
        result[identity] = sorted(found)
    return result


def _layout_title_ids(final_layout: str | None) -> set[str] | None:
    from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows

    result: set[str] | None = None
    if final_layout:
        try:
            rows = parse_compact_dsl_rows(final_layout, expand_layouts=False)
        except ValueError:
            return result
        by_id = {}
        for row in rows:
            if isinstance(row, ComponentRow):
                by_id[row.component_id] = row
        scope = by_id.get("root")
        if scope is None:
            return result
        result = set()
        for row in by_id.values():
            if row.component_type in {"PillButton", "CircleButton", "CardButton", "Button"}:
                result.add(row.component_id)
        if scope.props.get("layout") == "W-content-side-slots" and scope.children:
            scope = by_id.get(scope.children[0])
        if scope is not None and scope.children:
            first = by_id.get(scope.children[0])
            if first is not None and first.component_type in {"SingleLineTitle", "DoubleLineTitle"}:
                result.add(first.component_id)
    return result


def body_text_flow_evidence(nodes: list[dict], data_model: dict | None,
                            *, include_buttons: bool = False,
                            exclude_ids: set[str] | None = None) -> dict:
    """当前文字行数，可排除标题或按钮；不推测端侧自动折行。"""
    if data_model is None:
        return {}
    flows = text_flow_evidence(nodes, current_data=data_model, include_buttons=include_buttons,
                               exclude_ids=exclude_ids)
    result = {}
    for identity, flow in flows.items():
        result[identity] = {"lineCount": flow.get("maxLines"),
                            "leftAligned": flow.get("leftAligned"), "basis": "current-text"}
    return result


def _current_text_lines(node: dict, data_model: dict) -> int | None:
    def lookup(path: str):
        exists, value = read_pointer(data_model, path)
        return value if exists else None

    content = node.get("content")
    if type(content) in {int, float}:
        content = str(content)
    text = concatenated_display_text(content, lookup)
    result: int | None = None
    if text is not None:
        result = len(text.replace("\r\n", "\n").replace("\r", "\n").split("\n")) if text else 0
        limit = node.get("styles", {}).get("maxLines")
        if type(limit) is int and limit > 0:
            result = min(result, limit)
    return result


def text_flow_evidence(nodes: list[dict], *, current_data: dict | None = None,
                       include_buttons: bool = False, exclude_ids: set[str] | None = None) -> dict:
    """默认保留行数上界；当前数据模式供所有图片正文准入，不使用像素尺寸。"""
    by_id = {node.get("id"): node for node in nodes}
    flows = {}
    excluded = set(exclude_ids or ())
    if current_data is not None and not include_buttons:
        excluded.update(button_ids(nodes))

    def visit(identity: str, ancestors: set[str]) -> dict:
        unknown = {"maxLines": None, "leftAligned": False}
        if identity in ancestors or identity not in by_id:
            return unknown
        if identity in flows:
            return flows.get(identity, unknown)
        node = by_id.get(identity, {})
        kind = node.get("component")
        styles = node.get("styles", {})
        flow = unknown
        if identity in excluded:
            flow = {"maxLines": 0, "leftAligned": True}
        elif kind == "Text":
            limit = styles.get("maxLines")
            if current_data is not None:
                limit = _current_text_lines(node, current_data)
            valid_limit = type(limit) is int and limit > 0
            if valid_limit or (current_data is not None and limit == 0):
                flow = {"maxLines": limit,
                        "leftAligned": styles.get("textAlign", "start") in {"start", "left"}}
        elif kind == "Button":
            label = node.get("label")
            limit = styles.get("maxLines", 1)
            static_label = isinstance(label, str) and bool(label.strip())
            if current_data is not None:
                count = _current_text_lines({**node, "content": label}, current_data)
                flow = {"maxLines": count, "leftAligned": styles.get("textAlign") == "start"}
            elif static_label and len(label.splitlines()) == 1 and "{{" not in label:
                if type(limit) is int and limit > 0:
                    flow = {"maxLines": limit,
                            "leftAligned": styles.get("textAlign", "center") in {"start", "left"}}
        elif kind in {"Image", "Icon", "Divider"}:
            flow = {"maxLines": 0, "leftAligned": True}
        elif kind == "Progress" and styles.get("type", node.get("type")) == "ring":
            flow = {"maxLines": 0, "leftAligned": True}
        elif kind == "Progress" and current_data is not None:
            if styles.get("type", node.get("type")) == "linear":
                flow = {"maxLines": 0, "leftAligned": True}
        elif kind in {"Row", "Column", "Stack"}:
            children = node.get("children", [])
            child_flows = [visit(child, ancestors | {identity}) for child in children]
            flow = _container_text_flow(kind, styles, child_flows,
                                        current_text=current_data is not None)
        flows[identity] = flow
        return flow

    visit("root", set())
    return flows


def _container_text_flow(kind: str, styles: dict, children: list[dict],
                         *, current_text: bool = False) -> dict:
    limits = [child.get("maxLines") for child in children]
    result = {"maxLines": None, "leftAligned": False}
    if any(limit is None for limit in limits):
        return result
    text_children = [child for child in children if child.get("maxLines", 0) > 0]
    total = sum(limits)
    if kind == "Row" and (current_text or all(limit <= 1 for limit in limits)):
        total = max(limits, default=0)
    if kind == "Stack" and len(text_children) > 1:
        return result
    left = all(child.get("leftAligned") for child in text_children)
    if kind == "Column" and styles.get("alignItems", "start") not in {"start", "stretch"}:
        left = not text_children
    if kind == "Row":
        alignment = styles.get("justifyContent", "start")
        if alignment not in {"start", "spaceBetween"}:
            left = not text_children
        if alignment == "spaceBetween" and len(text_children) > 1:
            left = False
    if kind == "Stack" and styles.get("alignContent") not in {"start", "topStart", "bottomStart"}:
        left = not text_children
    return {"maxLines": total, "leftAligned": left}


def layout_evidence_reason(evidence: dict) -> str | None:
    if evidence.get("basis") != "layout-only" or evidence.get("deviceGeometryKnown") is not False:
        return "云侧不能使用参考画布测量作为真实卡片几何依据"
    if evidence.get("complete") is not True or not evidence.get("contentIds"):
        return evidence.get("reason") or "缺少定稿内容"
    return None
