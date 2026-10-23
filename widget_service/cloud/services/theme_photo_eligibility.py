"""主体图按主区、抽象图按整卡准入，只读取定稿布局，不调整前景。"""

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow, parse_compact_dsl_rows
from services.post_layout_theme_registry import load_theme_registry
from services.theme_layout_summary import matches_subjectless_layout
from services.theme_texture_eligibility import (
    holiday_countdown,
    subtree,
    texture_business_reason,
    visible_business,
)


def _fully_centered(root: ComponentRow, rows: list[ComponentRow]) -> bool:
    if root.component_type == "Layout":
        return root.props.get("layout") == "S-center"
    if root.component_type != "Column":
        return False
    if root.props.get("alignItems") != "center" or root.props.get("justifyContent") != "center":
        return False
    # 兼容基础组件根，但局部文字居中或嵌套伸展区贴顶不等于整卡全居中。
    for row in rows:
        if any(key in row.props for key in ("position", "offset", "translate", "alignSelf")):
            return False
        if row.component_type in {"DataDisplay", "Image", "Icon", "Divider"}:
            continue
        if row.component_type == "Text":
            if row.props.get("textAlign") != "center":
                return False
        elif row.component_type == "Column":
            if row.props.get("alignItems") != "center":
                return False
            stretches = row.props.get("height") == "matchParent" or row.props.get("layoutWeight")
            if stretches and row.props.get("justifyContent") != "center":
                return False
        else:
            return False
    return True


def _placement_reason(policy: dict, scope: ComponentRow, rows: list[ComponentRow],
                      flow: dict) -> str | None:
    placement = policy.get("placement")
    reason: str | None = None
    if placement in {"center", "not-center"}:
        if _fully_centered(scope, rows) != (placement == "center"):
            reason = "2x2全居中只用同心圆，其余布局只用菱形或斜纹"
    elif placement == "bottom":
        bottom = scope.component_type == "Region" and scope.props.get("variant") == "title-content"
        if not bottom or flow.get("lineCount", 0) == 0:
            reason = "此图片要求主区正文整体居下，不能仅辅助内容贴底"
    elif placement in {"bottom-left", "not-bottom-left"}:
        bottom = scope.component_type == "Region" and scope.props.get("variant") == "title-content"
        bottom_left = bottom and flow.get("leftAligned") is True
        if placement == "bottom-left" and not bottom_left:
            reason = "此会议图片要求左侧主区正文全部居左贴底"
        elif placement == "not-bottom-left" and bottom_left:
            reason = "居左贴底会议使用A19，不匹配会议室横图"
    return reason


def _wide_scope(root: ComponentRow, by_id: dict, final_layout: str,
                rules: dict, policy: dict) -> ComponentRow | None:
    """只读已登记主次槽位，不用组件大小或请求文案猜测主焦点。"""
    result: ComponentRow | None = None
    requirement = rules.get("wideLayout", {})
    layout_policy = policy.get("wideLayout")
    flexible = layout_policy == "main-focus"
    if root.component_type != "Layout":
        return result
    layout = root.props.get("layout")
    if layout == "W-content-side-slots":
        orientation = root.props.get("orientation", "content-left")
        both_sides = layout_policy in {"main-focus", "side-focus"}
        if both_sides and orientation in ("content-left", "content-right"):
            requirement = {**requirement, "orientation": orientation}
        if matches_subjectless_layout(final_layout, requirement):
            result = by_id.get(root.children[0])
    elif flexible and layout == "W-top-bottom" and len(root.children) in {2, 3}:
        if root.props.get("variant", "continuous") in ("continuous", "bottom-details", "equal"):
            result = by_id.get(root.children[-2])
    if result is not None:
        if result.component_type in {"SingleLineTitle", "DoubleLineTitle"}:
            result = None
        elif result.component_type == "Group" and result.props.get("variant") == "title-count":
            result = None
    return result


def photo_content_reason(photo: dict, task: dict, evidence: dict,
                         final_layout: str | None) -> str | None:
    if not final_layout:
        return "图片内容限制需要定稿布局"
    try:
        parsed = parse_compact_dsl_rows(final_layout, expand_layouts=False)
    except ValueError:
        return "无法解析图片内容限制所需的定稿布局"
    by_id = {}
    values = {}
    for row in parsed:
        if isinstance(row, ComponentRow):
            by_id[row.component_id] = row
        elif isinstance(row, DataRow):
            values[row.path] = row.value
    root = by_id.get("root")
    if root is None:
        return "图片缺少定稿根节点"
    rules = load_theme_registry().get("photoEligibility", {})
    policy = photo.get("contentEligibility", {})
    wide = task.get("size") == "2x4"
    is_texture = photo.get("pool") == "texturePhotos"
    scope = root
    if wide and not is_texture:
        scope = _wide_scope(root, by_id, final_layout, rules, policy)
        if scope is None:
            if policy.get("wideLayout") == "main-focus":
                return "2x4图片需要明确主焦点，不支持双大背板或无主次布局"
            if policy.get("wideLayout") == "side-focus":
                return "2x4图片需要左右主焦点加另一侧上下双槽，不支持上下或双大背板布局"
            return "2x4图片需要左主焦点和右侧上下两个背板"
    elif task.get("size") not in {"2x2", "2x4"}:
        return "图片只支持2x2和2x4"
    if scope is None:
        return "图片缺少主内容区"
    rows = subtree(scope.component_id, by_id)
    if not rows:
        return "图片内容树不完整"
    if is_texture:
        reason = texture_business_reason(photo, rows)
        if reason is not None:
            return reason
    else:
        business = visible_business(rows)
        if "holiday" in policy.get("businesses", []):
            business = "holiday" if holiday_countdown(rows, values) else None
        if business not in policy.get("businesses", []):
            return "图片业务与实际可见的单业务内容不匹配"
    flow_key = "textureBodyTextFlow" if is_texture else "photoBodyTextFlow"
    flow = evidence.get(flow_key, {}).get(scope.component_id, {})
    lines = flow.get("lineCount")
    if type(lines) is not int or lines < 0:
        return "无法确认图片正文行数"
    wide_subject = wide and not is_texture
    limit = rules.get("wideMaxTextLines" if wide_subject else "maxTextLines", 0)
    max_lines = min(limit, policy.get("maxTextLines", limit))
    if lines > max_lines:
        return f"图片正文超过{max_lines}行（不含顶部标题和按钮文案）"
    subject_square = photo.get("pool") == "photos" and task.get("size") == "2x2"
    if subject_square and flow.get("leftAligned") is not True:
        return "2x2主体图片要求正文整体居左，不能居中或两端对齐"
    placement_reason = _placement_reason(policy, scope, rows, flow)
    if placement_reason is not None:
        return placement_reason
    if policy.get("placement") == "top-left-empty-bottom":
        top = evidence.get("photoTopContent", {})
        if lines == 0:
            return "蓝天白云需要1至2行正文"
        if top.get("topOnly") is not True:
            return "蓝天白云要求正文居左居上且下方留空：" + str(top.get("reason"))
    return None
