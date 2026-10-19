"""识别布局内容与完整按钮，不推测端侧 matchParent 的真实尺寸。"""

from __future__ import annotations


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


def photo_layout_evidence(nodes: list[dict]) -> dict:
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
    return {"basis": "layout-only", "complete": reason is None, "reason": reason,
            "contentIds": content_ids, "buttonIds": button_ids(nodes),
            "nonTextIds": non_text_ids,
            "nonTextAncestors": _non_text_ancestors(nodes, non_text_ids),
            "textFlow": text_flow_evidence(nodes),
            "deviceGeometryKnown": False}


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


def text_flow_evidence(nodes: list[dict]) -> dict:
    """仅计算已声明的行数上界和对齐语义，不使用任何像素尺寸。"""
    by_id = {node.get("id"): node for node in nodes}
    flows = {}

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
        if kind == "Text":
            limit = styles.get("maxLines")
            if type(limit) is int and limit > 0:
                flow = {"maxLines": limit,
                        "leftAligned": styles.get("textAlign", "start") in {"start", "left"}}
        elif kind in {"Image", "Icon", "Divider"}:
            flow = {"maxLines": 0, "leftAligned": True}
        elif kind in {"Row", "Column", "Stack"}:
            children = node.get("children", [])
            child_flows = [visit(child, ancestors | {identity}) for child in children]
            flow = _container_text_flow(kind, styles, child_flows)
        flows[identity] = flow
        return flow

    visit("root", set())
    return flows


def _container_text_flow(kind: str, styles: dict, children: list[dict]) -> dict:
    limits = [child.get("maxLines") for child in children]
    result = {"maxLines": None, "leftAligned": False}
    if any(limit is None for limit in limits):
        return result
    text_children = [child for child in children if child.get("maxLines", 0) > 0]
    total = sum(limits)
    if kind == "Row" and all(limit <= 1 for limit in limits):
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
    if kind == "Stack" and styles.get("alignContent") not in {"topStart", "bottomStart"}:
        left = not text_children
    return {"maxLines": total, "leftAligned": left}


def layout_evidence_reason(evidence: dict) -> str | None:
    if evidence.get("basis") != "layout-only" or evidence.get("deviceGeometryKnown") is not False:
        return "云侧不能使用参考画布测量作为真实卡片几何依据"
    if evidence.get("complete") is not True or not evidence.get("contentIds"):
        return evidence.get("reason") or "缺少定稿内容"
    return None
