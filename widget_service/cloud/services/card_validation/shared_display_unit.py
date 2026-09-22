"""在最近的同业务双指标分区内识别共享标题单位。"""

from .base import expression_references
from .display_unit_rules import title_has_display_unit, unit_rule_for_path


def _references(value):
    return expression_references(value) if isinstance(value, str) else []


def _texts_in_tree(component, components_by_id, visited):
    component_id = component.get("id")
    if component_id in visited:
        return []
    visited.add(component_id)
    texts = []
    if component.get("component") == "Text":
        texts.append(component)
    for child_id in component.get("children", []):
        child = components_by_id.get(child_id)
        if child is not None:
            texts.extend(_texts_in_tree(child, components_by_id, visited))
    return texts


def _title_texts(component, components_by_id):
    if component.get("component") == "Text":
        return [component.get("content")]
    if component.get("component") != "Row":
        return []
    texts = []
    for child_id in component.get("children", []):
        child = components_by_id.get(child_id)
        if child is None or child.get("component") not in {"Text", "Image"}:
            return []
        content = child.get("content")
        if _references(content):
            return []
        if child.get("component") == "Text":
            texts.append(content)
    return texts


def _same_binding(paths, cardspec):
    if paths[0].rsplit("/", 1)[0] != paths[1].rsplit("/", 1)[0]:
        return False
    roots = []
    for binding in cardspec.get("dataBindings", []):
        root = binding.get("writeResultTo")
        if not isinstance(root, str):
            continue
        if all(path.startswith(root.rstrip("/") + "/") for path in paths):
            roots.append(root)
    return len(roots) == 1


def _scope_accepts_title(scope, paths, unit_rules, context):
    if len(paths) != 2 or paths[0] == paths[1]:
        return False
    if not _same_binding(paths, context.cardspec):
        return False
    rules = []
    for path in paths:
        rule = unit_rule_for_path(path, unit_rules)
        if rule is None or rule.unit_included:
            return False
        rules.append(rule)
    for child_id in scope.get("children", []):
        child = context.components_by_id.get(child_id)
        if child is None:
            return False
        texts = _texts_in_tree(child, context.components_by_id, set())
        if any(_references(text.get("content")) for text in texts):
            break
        for title in _title_texts(child, context.components_by_id):
            if all(title_has_display_unit(title, rule) for rule in rules):
                return True
    return False


def has_shared_title_unit(component_id, unit_rules, parents_by_child, context):
    """不跨越最近的多指标容器向其它分区寻找单位。"""
    visited = set()
    current = component_id
    while current not in visited:
        visited.add(current)
        parents = parents_by_child.get(current, [])
        if len(parents) != 1:
            return False
        scope = parents[0]
        current = scope.get("id")
        texts = _texts_in_tree(scope, context.components_by_id, set())
        paths = []
        for text in texts:
            paths.extend(_references(text.get("content")))
        if len(paths) < 2:
            continue
        # 允许双列 Row 上方紧邻的分区 Column 放标题，但不跨越其它业务分区。
        if _scope_accepts_title(scope, paths, unit_rules, context):
            return True
        parents = parents_by_child.get(current, [])
        if scope.get("component") != "Row" or len(parents) != 1:
            return False
        outer = parents[0]
        outer_paths = []
        for text in _texts_in_tree(outer, context.components_by_id, set()):
            outer_paths.extend(_references(text.get("content")))
        if outer.get("component") != "Column" or outer_paths != paths:
            return False
        return _scope_accepts_title(outer, paths, unit_rules, context)
    return False
