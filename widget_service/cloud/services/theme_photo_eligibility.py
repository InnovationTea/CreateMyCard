"""融合定稿事实适配；图片规则由公共纯算法模块统一执行。"""

from services.compact_dsl_a2ui_converter import ComponentRow
from services.content_business import BusinessContext, FinalBusinessContext
from services.post_layout_theme_registry import load_theme_registry
from services.theme_content_regions import layout_evidence_reason, photo_layout_exclusion_reason
from services.theme_layout_summary import matches_subjectless_layout
from services.theme_photo_matching import PhotoMatchFacts, PhotoScopeFacts
from services.theme_photo_matching import photo_content_reason as match_content
from services.theme_texture_eligibility import holiday_countdown, subtree


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


def fusion_photo_facts(
    task: dict, evidence: dict, final_layout: str | None, *,
    business_context: FinalBusinessContext | None = None,
) -> PhotoMatchFacts:
    context = business_context or FinalBusinessContext.from_layout(
        final_layout, BusinessContext.from_task(task),
    )
    layout_error = layout_evidence_reason(evidence)
    if layout_error:
        return PhotoMatchFacts(task.get("size"), error=layout_error)
    root = context.by_id.get("root")
    if context.error or root is None:
        return PhotoMatchFacts(task.get("size"), error=context.error or "图片缺少定稿根节点")

    def scope_facts(scope: ComponentRow) -> PhotoScopeFacts:
        rows = subtree(scope.component_id, context.by_id)
        businesses = context.scope(scope.component_id)
        return PhotoScopeFacts(
            businesses,
            body_flow=evidence.get("photoBodyTextFlow", {}).get(scope.component_id, {}),
            texture_flow=evidence.get("textureBodyTextFlow", {}).get(scope.component_id, {}),
            centered=_fully_centered(scope, rows),
            bottom=(scope.component_type == "Region"
                    and scope.props.get("variant") == "title-content"),
            holiday=holiday_countdown(rows, context.values, businesses=businesses),
        )

    scopes = {"card": scope_facts(root)}
    if task.get("size") == "2x4":
        rules = load_theme_registry().get("photoEligibility", {})
        for layout in ("left-main-dual", "main-focus", "side-focus"):
            policy = {} if layout == "left-main-dual" else {"wideLayout": layout}
            main = _wide_scope(root, context.by_id, final_layout, rules, policy)
            if main is not None:
                scopes[layout] = scope_facts(main)
    count = None
    if root.component_type == "Layout":
        expected = {"W-split-panels": 2, "W-four-slots": 4}.get(root.props.get("layout"))
        if expected is not None and len(root.children) == expected:
            count = expected
    return PhotoMatchFacts(
        task.get("size"), scopes=scopes, panel_count=count,
        top_content=evidence.get("photoTopContent", {}),
        body_regions=evidence.get("photoBodyRegions", {}),
        subject_exclusion=photo_layout_exclusion_reason(task, evidence, final_layout),
    )


def photo_content_reason(
    photo: dict, task: dict, evidence: dict, final_layout: str | None, *,
    business_context: FinalBusinessContext | None = None,
) -> str | None:
    facts = fusion_photo_facts(task, evidence, final_layout, business_context=business_context)
    return match_content(photo, facts)
