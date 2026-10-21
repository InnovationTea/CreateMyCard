"""所有主体图和抽象图共用正文准入，只读取定稿布局，不调整前景。"""

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow, parse_compact_dsl_rows
from services.post_layout_theme_registry import load_theme_registry
from services.theme_layout_summary import matches_subjectless_layout
from services.theme_texture_eligibility import holiday_countdown, subtree, visible_business


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
    elif placement in {"bottom-left", "not-bottom-left"}:
        bottom = scope.component_type == "Region" and scope.props.get("variant") == "title-content"
        bottom_left = bottom and flow.get("leftAligned") is True
        if placement == "bottom-left" and not bottom_left:
            reason = "此会议图片要求左侧主区正文全部居左贴底"
        elif placement == "not-bottom-left" and bottom_left:
            reason = "居左贴底会议使用A19，不匹配会议室横图"
    return reason


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
    scope = root
    if task.get("size") == "2x4":
        if not matches_subjectless_layout(final_layout, rules.get("wideLayout", {})):
            return "2x4图片需要左主焦点和右侧上下两个背板"
        scope = by_id.get(root.children[0])
    elif task.get("size") != "2x2":
        return "图片只支持2x2和2x4"
    if scope is None:
        return "图片缺少主内容区"
    rows = subtree(scope.component_id, by_id)
    if not rows:
        return "图片内容树不完整"
    policy = photo.get("contentEligibility", {})
    business = visible_business(rows)
    if "holiday" in policy.get("businesses", []):
        business = "holiday" if holiday_countdown(rows, values) else None
    if business not in policy.get("businesses", []):
        return "图片业务与实际可见的单业务内容不匹配"
    flow = evidence.get("photoBodyTextFlow", {}).get(scope.component_id, {})
    lines = flow.get("lineCount")
    if type(lines) is not int or lines < 0:
        return "无法确认图片正文行数"
    max_lines = min(rules.get("maxTextLines", 0), policy.get("maxTextLines", 3))
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
