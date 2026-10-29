"""从最终组件树识别连续正文与贴底区；不猜测像素、不依赖ID或业务文案。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Block:
    node: dict
    lines: int | None
    buttons: int = 0
    children: list[_Block] = field(default_factory=list)
    error: str | None = None

    @property
    def active(self) -> bool:
        return bool(self.lines or self.buttons)


def _fills_height(node: dict) -> bool:
    styles = node.get("styles", {})
    weight = styles.get("layoutWeight")
    weighted = type(weight) in {int, float} and weight > 0
    return weighted or styles.get("height") in {"matchParent", "100%"}


def _build_tree(
    identity: str, by_id: dict, flows: dict, excluded: set[str], buttons: set[str],
    ancestors: set[str],
) -> _Block:
    node = by_id.get(identity)
    if node is None or identity in ancestors:
        return _Block({}, None, error="正文分区内容树不完整或存在循环")
    styles = node.get("styles", {})
    if any(key in styles for key in ("position", "offset", "translate", "alignSelf")):
        return _Block(node, None, error="正文分区含独立定位，无法确认底部位置")
    if identity in buttons or node.get("component") == "Button":
        return _Block(node, 0, buttons=1)
    if identity in excluded:
        return _Block(node, 0)
    lines = flows.get(identity, {}).get("lineCount")
    if type(lines) is not int or lines < 0:
        return _Block(node, None, error="无法确认正文分区行数")
    children = []
    for child in node.get("children", []):
        children.append(_build_tree(child, by_id, flows, excluded, buttons,
                                    ancestors | {identity}))
    error = next((child.error for child in children if child.error), None)
    counts = [child.buttons for child in children]
    button_rows = sum(counts)
    kind = node.get("component")
    if kind == "Row":
        button_rows = max(counts, default=0)
    elif kind == "Stack" and sum(bool(count) for count in counts) > 1:
        error = "按钮叠放，无法确认底部行数"
    return _Block(node, lines, button_rows, children, error)


def _continuous(block: _Block) -> bool:
    styles = block.node.get("styles", {})
    if block.node.get("component") == "Column":
        if styles.get("justifyContent") in {"spaceBetween", "spaceAround", "spaceEvenly"}:
            if sum(child.active for child in block.children) > 1:
                return False
    return all(_continuous(child) for child in block.children)


def _split_index(block: _Block, full_height: bool) -> dict:
    result = {"index": None, "error": None}
    if not full_height or block.node.get("component") != "Column":
        return result
    active = []
    stretched = []
    for index, child in enumerate(block.children):
        if child.active:
            active.append(index)
        if _fills_height(child.node):
            stretched.append(index)
    if not active:
        return result
    before_last = [index for index in stretched if index < active[-1]]
    if before_last:
        if len(stretched) != 1:
            result["error"] = "多个伸展区，无法唯一确认底部区域"
        else:
            result["index"] = before_last[0]
    elif block.node.get("styles", {}).get("justifyContent") == "spaceBetween":
        if len(active) == 2:
            result["index"] = active[0]
        elif len(active) > 2:
            result["error"] = "多个分散内容区，无法唯一确认正文与底部"
    return result


def _region_result(block: _Block, full_height: bool) -> dict:
    if block.error:
        return {"complete": False, "reason": block.error}
    split = _split_index(block, full_height)
    if split.get("error"):
        return {"complete": False, "reason": split.get("error")}
    index = split.get("index")
    if index is not None:
        main = block.children[:index + 1]
        footer = block.children[index + 1:]
        if any(child.buttons for child in main):
            return {"complete": False, "reason": "按钮不在独立底部区域"}
        if not all(_continuous(child) for child in block.children):
            return {"complete": False, "reason": "正文或底部含多个分散区域"}
        return {"complete": True, "mainLines": sum(child.lines for child in main),
                "footerTextLines": sum(child.lines for child in footer),
                "footerButtonRows": sum(child.buttons for child in footer)}
    active = [child for child in block.children if child.active]
    if len(active) == 1:
        child = active[0]
        # 只沿实际伸展关系传递卡片底部，不把wrapContent区域误当整卡。
        fills = full_height and _fills_height(child.node)
        return _region_result(child, fills)
    if block.buttons:
        return {"complete": False, "reason": "按钮未确认位于独立底部区域"}
    if not _continuous(block):
        return {"complete": False, "reason": "无法确认连续正文区域"}
    return {"complete": True, "mainLines": block.lines,
            "footerTextLines": 0, "footerButtonRows": 0}


def body_region_evidence(
    nodes: list[dict], flows: dict, excluded_ids: set[str], button_ids: set[str],
) -> dict:
    """标题不计正文，按钮不计文字行但单独记录其底部占位。"""
    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes):
        return {"complete": False, "reason": "正文分区存在重复节点"}
    tree = _build_tree("root", by_id, flows, excluded_ids, button_ids, set())
    result = _region_result(tree, _fills_height(tree.node))
    return {**result, "basis": "layout-structure", "deviceGeometryKnown": False}
