"""恢复布局输出中可证明安全的静态越界属性和漏挂载引用。"""

import copy

from app.logger import json_for_log, logger
from services.card_validation.edit_validation.structure import validate_edit_structure
from services.single_step_edit import _same
from services.widget_edit_contract import (
    _TOP_LAYOUT_FIELDS,
    EditIntent,
    _allowed_styles,
    _dynamic,
    _node_changes,
    _tree,
    dump_rows,
    scope_ids,
)


def recover_layout(original: str, candidate: str, intent: EditIntent) -> str:
    before_rows, before = _tree(original)
    rows, after = _tree(candidate)
    allowed = scope_ids(intent, before)
    style_fields = _allowed_styles(intent)
    restored: list[str] = []
    for identity, old in before.items():
        node = after.get(identity)
        if node is None:
            continue
        old_styles = old.get("styles", {})
        styles = node.get("styles", {})
        if not isinstance(old_styles, dict) or not isinstance(styles, dict):
            continue
        restored_style = False
        for prop in sorted(_node_changes(old_styles, styles)):
            background_removal = identity in intent.backgroundTargets
            background_removal = background_removal and prop == "backgroundImage"
            background_removal = background_removal and prop not in styles
            permitted = identity in allowed and (prop in style_fields or background_removal)
            if permitted or _dynamic(old_styles.get(prop)) or _dynamic(styles.get(prop)):
                continue
            _restore(old_styles, styles, prop)
            restored_style = True
            restored.append(f"{identity}.styles.{prop}")
        if restored_style:
            node["styles"] = styles
        for prop in sorted(_TOP_LAYOUT_FIELDS):
            if identity in allowed or _same(old.get(prop), node.get(prop)):
                continue
            if _dynamic(old.get(prop)) or _dynamic(node.get(prop)):
                continue
            _restore(old, node, prop)
            restored.append(f"{identity}.{prop}")
    root = before_rows[1].get("updateComponents", {}).get("root")
    if not isinstance(root, str):
        raise ValueError("原卡缺少根节点")
    _restore_mounts(before, after, root, restored)
    if restored:
        logger.info(f"[Widget Edit] safe_recovery details={json_for_log(restored)}")
    return dump_rows(rows)


def _restore(old: dict, current: dict, prop: str) -> None:
    if prop in old:
        current[prop] = copy.deepcopy(old.get(prop))
    else:
        current.pop(prop, None)


def _restore_mounts(before: dict, after: dict, root: str, restored: list[str]) -> None:
    source_reached = validate_edit_structure(before, root)
    reached = validate_edit_structure(after, root)
    for identity, old in before.items():
        node = after.get(identity)
        if node is None or identity not in reached:
            continue
        children = old.get("children")
        current = node.get("children")
        if not isinstance(children, list) or not isinstance(current, list):
            continue
        # 仅恢复原有子序列中被遗漏的引用；重排、新增或重新挂载均不猜测。
        retained = []
        for child in children:
            if child in current:
                retained.append(child)
        if retained != current:
            continue
        missing = []
        for child in children:
            if child not in current:
                missing.append(child)
        if not missing:
            continue
        safe = True
        for child in missing:
            if child in reached or child not in after or child not in source_reached:
                safe = False
        if not safe:
            continue
        node["children"] = list(children)
        # 完整树检查不通过则拒绝该候选，绝不将恢复当作校验豁免。
        reached = validate_edit_structure(after, root)
        restored.append(f"{identity}.children")
