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
    for node in nodes:
        if node.get("component") not in {"Row", "Column", "Stack"} and node.get("id"):
            content_ids.append(node.get("id"))
    reason = None
    if len(roots) != 1 or not content_ids:
        reason = "缺少定稿内容"
    else:
        styles = roots[0].get("styles", {})
        if styles.get("width") != "matchParent" or styles.get("height") != "matchParent":
            reason = "背景需要自适应前景根节点"
    return {"basis": "layout-only", "complete": reason is None, "reason": reason,
            "contentIds": content_ids, "buttonIds": button_ids(nodes),
            "deviceGeometryKnown": False}


def layout_evidence_reason(evidence: dict) -> str | None:
    if evidence.get("basis") != "layout-only" or evidence.get("deviceGeometryKnown") is not False:
        return "云侧不能使用参考画布测量作为真实卡片几何依据"
    if evidence.get("complete") is not True or not evidence.get("contentIds"):
        return evidence.get("reason") or "缺少定稿内容"
    return None
