"""从定稿实际结构识别图片宽卡主区，仅在模板内使用。"""

from services.compact_dsl_a2ui_converter import ComponentRow


def _surface(row: ComponentRow) -> bool:
    color = row.props.get("backgroundColor")
    if not isinstance(color, str) or not color.startswith("#"):
        return False
    if len(color) not in {7, 9}:
        return False
    if any(character not in "0123456789abcdefABCDEF" for character in color[1:]):
        return False
    return len(color) == 7 or color[1:3] != "00"


def _unwrap(row: ComponentRow, by_id: dict[str, ComponentRow]) -> ComponentRow:
    visited = set()
    while row.component_type in {"Row", "Column", "Stack"}:
        if len(row.children) != 1 or row.component_id in visited:
            break
        visited.add(row.component_id)
        child = by_id.get(row.children[0])
        if child is None or child.component_type not in {"Row", "Column", "Stack"}:
            break
        if row.props.get("onClick") or _surface(row):
            break
        row = child
    return row


def _side_surfaces(side: ComponentRow, by_id: dict[str, ComponentRow]) -> list[ComponentRow]:
    supports = [side] if _surface(side) else []
    if not supports:
        for identity in side.children:
            child = by_id.get(identity)
            if child is None or not _surface(child):
                return []
            supports.append(child)
    return supports


def wide_photo_main(
    root: ComponentRow, by_id: dict[str, ComponentRow],
) -> ComponentRow | None:
    """只认可左侧无整块背板的主内容和右侧实际单／双背板，不猜宿主尺寸。"""
    root = _unwrap(root, by_id)
    result: ComponentRow | None = None
    if root.component_type == "Row" and len(root.children) == 2:
        main = by_id.get(root.children[0])
        side = by_id.get(root.children[1])
        if main is not None and side is not None:
            main = _unwrap(main, by_id)
            side = _unwrap(side, by_id)
            if not _surface(main) and side.component_type == "Column":
                supports = _side_surfaces(side, by_id)
                if len(supports) in {1, 2}:
                    result = main
    return result
