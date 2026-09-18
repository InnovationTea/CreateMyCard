"""检查 2x2 双胶囊动作的固定空间预算，不估算动态文字排版。"""

from services.compact_dsl_a2ui_converter import ComponentRow


def collect_dual_action_errors(
    components: list[ComponentRow], size: object, errors: list[str]
) -> None:
    if size != "2x2":
        return
    actions = []
    for component in components:
        is_action = component.component_type == "ActionUnit"
        if is_action and component.props.get("state") == "capsule":
            actions.append(component.component_id)
    if len(actions) != 2:
        return
    by_id = {component.component_id: component for component in components}
    root = by_id.get("root")
    reason = _structure_error(root, by_id, actions)
    if reason:
        errors.append(
            "S3_DUAL_ACTION_LAYOUT: " + reason + " Use a root Column with a 136x48 "
            "information Column and a 136x80 action Column, root padding 12 and gap 8; "
            "place one 14fp main Text and an optional 12fp status Text in the information "
            "group, and two 36vp capsules with gap 8 in the action group. Remove the "
            "separate CardHeader and large-number region; preserve both event handlers."
        )


def _structure_error(
    root: ComponentRow | None, by_id: dict[str, ComponentRow], actions: list[str]
) -> str:
    if root is None:
        return "Missing root."
    if root.component_type != "Column" or len(root.children) != 2:
        return "Two capsules require exactly two root regions."
    if not _padding_is_twelve(root.props.get("padding")) or _gap(root) != 8:
        return "Root padding or gap violates the 136vp budget."
    info = by_id.get(root.children[0])
    action = by_id.get(root.children[1])
    if info is None or action is None:
        return "Missing information or action region."
    for region, height in ((info, 48), (action, 80)):
        geometry = (region.component_type, region.props.get("width"), region.props.get("height"))
        if geometry != ("Column", 136, height):
            return f"Region {region.component_id} must be 136x{height}."
    if len(action.children) != 2 or set(action.children) != set(actions):
        return "Capsules must be direct children of the last region."
    if _gap(action) != 8:
        return "Capsule gap must be 8vp."
    if len(info.children) not in (1, 2):
        return "Information must contain one or two direct text lines."
    for index, child_id in enumerate(info.children):
        child = by_id.get(child_id)
        if child is None or child.component_type != "Text":
            return "No CardHeader, icon or nested large-number region is allowed."
        limit = 14 if index == 0 else 12
        font = child.props.get("fontSize")
        height = child.props.get("height")
        if not _number(font) or not 12 <= font <= limit:
            return f"Text {child_id} must use 12..{limit}fp."
        if not _number(height) or height < font * 1.4:
            return f"Text {child_id} needs an explicit height of at least {font * 1.4}vp."
        if child.props.get("maxLines") != 1:
            return f"Text {child_id} must be single-line."
    return ""


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _gap(component: ComponentRow) -> object:
    return component.props.get("itemMargin", component.props.get("space", 0))


def _padding_is_twelve(value: object) -> bool:
    if isinstance(value, dict):
        return all(value.get(side) == 12 for side in ("top", "right", "bottom", "left"))
    return value == 12
