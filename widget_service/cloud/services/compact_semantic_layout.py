"""按卡片尺寸展开语义布局；固定几何由模板拥有，业务行和绑定不改写。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import NoReturn

from services.compact_component_runtime import visual_recipe_part
from services.compact_high_level_components import (
    CompactDslConversionError,
    CompactRow,
    ComponentRow,
)
from services.theme_style_roles import in_layout_phase

SEMANTIC_LAYOUT_TYPES = frozenset({"Layout", "Region", "Group"})
LAYOUT_IDS = frozenset({
    "W-top-bottom", "W-split-panels", "W-content-side-slots", "W-four-slots",
})
COMPACT_VARIANTS = frozenset({
    "center", "title-content", "title-hero-support", "title-content-action",
})
WIDE_VARIANTS = COMPACT_VARIANTS | {
    "title-two-ratios", "title-hero-support-action", "four-ratios", "four-items",
}
GEOMETRY_PROPS = frozenset({
    "width", "height", "padding", "margin", "itemMargin", "layoutWeight", "flexShrink",
    "alignItems", "justifyContent", "alignSelf", "minWidth", "maxWidth", "minHeight",
    "maxHeight", "constraintSize", "aspectRatio",
})
GENERATED_PREFIX = "__layout__"
_BACKGROUND_PROPS = frozenset({"linearGradient", "backgroundColor", "backgroundImage"})
MIXED_FIXED_SLOT_ORDER_WARNING = (
    "W-content-side-slots 混合固定槽建议将 InfoBlock 放在 CardButton 上方；"
    "当前顺序仍允许转换。"
)
SMALL_CHILD_ROLES = {
    "S-center": (1, "[content]"),
    "S-title-content": (2, "[title, content]"),
    "S-title-dual-content": (3, "[title, primary, support]"),
    "S-quad-content": (4, "[top-left, top-right, bottom-left, bottom-right]"),
    "S-title-content-action": (3, "[title, content, PillButton]"),
    "S-title-primary-secondary-action": (4, "[title, primary, support, PillButton]"),
    "S-title-dual-column-action": (3, "[title, ProgressCircle, ProgressCircle, PillButton?]"),
    "S-title-anchor": (4, "[title, primary, support, CircleButton]"),
    "S-content-dual-action": (3, "[content, PillButton, PillButton]"),
    "S-dual-info": (2, "[InfoBlock, InfoBlock]"),
}

# 有序角色只用于解释既有 count 门禁，不参与几何展开或案例选型。
_CHILD_ROLES = {
    "Layout": {
        "W-top-bottom": "[title?, primary, details]",
        "W-split-panels": "[左侧 Region, 右侧 Region]",
        "W-content-side-slots": (
            "[内容 Region, 上方 InfoBlock/CardButton, 下方 InfoBlock/CardButton]"
        ),
        "W-four-slots": "[左上槽、右上槽、左下槽、右下槽]",
    },
    "Region": {
        "center": "[content]",
        "title-content": "[title, content]",
        "title-hero-support": "[title, hero, support]",
        "title-content-action": "[title, content, PillButton]",
        "title-two-ratios": "[title, ProgressCircle, ProgressCircle, PillButton?]",
        "title-hero-support-action": "[title, hero, support, PillButton]",
        "four-ratios": "[ProgressCircle, ProgressCircle, ProgressCircle, ProgressCircle]",
        "four-items": "[peer content, peer content, peer content, peer content]",
    },
    "Group": {
        "hero-support": "[hero, support]",
        "label-value": "[label, value]",
        "peer-pair": "[peer content, peer content]",
        "title-count": "[SingleLineTitle, Badge]",
    },
}


@dataclass(frozen=True)
class SemanticLayoutExpansion:
    rows: tuple[CompactRow, ...]
    origins: dict[str, str]
    layout_id: str | None = None


def has_semantic_layout(rows: list[CompactRow] | tuple[CompactRow, ...]) -> bool:
    return any(isinstance(row, ComponentRow) and row.component_type in SEMANTIC_LAYOUT_TYPES
               for row in rows)


def collect_semantic_layout_warnings(
    rows: list[CompactRow] | tuple[CompactRow, ...],
) -> tuple[str, ...]:
    """返回不阻断确定性展开的语义布局建议。"""
    components = {
        row.component_id: row for row in rows if isinstance(row, ComponentRow)
    }
    root = components.get("root")
    if root is None or root.props.get("layout") != "W-content-side-slots":
        return ()
    if len(root.children) != 3:
        return ()
    upper = components.get(root.children[1])
    lower = components.get(root.children[2])
    if upper is None or lower is None:
        return ()
    if upper.component_type == "CardButton" and lower.component_type == "InfoBlock":
        return (MIXED_FIXED_SLOT_ORDER_WARNING,)
    return ()


def _fail(identifier: str, message: str) -> NoReturn:
    raise CompactDslConversionError(
        f"语义布局不符合合同：节点 {identifier}：{message}。"
        "请选择已登记的 Layout、Region 或 Group 变体，不要修改展开后的几何。"
    )


def _prop_fail(identifier: str, message: str) -> NoReturn:
    raise CompactDslConversionError(
        f"组件 {identifier} 的语义属性无效：{message}。"
        "只修复已报告的属性，并保留当前布局、事实和 Action。"
    )


class _Compiler:
    size = "2x4"

    def __init__(self, rows: list[CompactRow] | tuple[CompactRow, ...]) -> None:
        self.source = rows
        self.by_id = {}
        for row in rows:
            if isinstance(row, ComponentRow):
                self.by_id[row.component_id] = row
        self.result: list[ComponentRow] = []
        self.origins: dict[str, str] = {}
        self.seen: set[str] = set()
        self.ratio_cells: dict[str, str] = {}

    def validate_tree(self, identifier: str, visiting: set[str], visited: set[str]) -> None:
        if identifier in visiting:
            _fail(identifier, "组件引用形成循环")
        if identifier in visited:
            _fail(identifier, "组件被多个父节点同时引用")
        if len(visiting) >= 64:
            _fail(identifier, "语义组件树嵌套超过安全深度")
        row = self.node(identifier)
        visiting.add(identifier)
        for child in row.children:
            self.validate_tree(child, visiting, visited)
        visiting.remove(identifier)
        visited.add(identifier)

    def node(self, identifier: str) -> ComponentRow:
        row = self.by_id.get(identifier)
        if row is None:
            _fail(identifier, "引用了不存在的组件")
        return row

    def generated(self, origin: str, suffix: str) -> str:
        identifier = f"{GENERATED_PREFIX}{origin}__{suffix}"
        if identifier in self.by_id or identifier in self.origins:
            _fail(origin, "生成的组件 ID 发生冲突")
        self.origins[identifier] = origin
        return identifier

    def add(self, identifier: str, kind: str, props: dict, children: tuple[str, ...],
            origin: str) -> None:
        self.origins[identifier] = origin
        self.result.append(ComponentRow(identifier, kind, props, children))

    @staticmethod
    def props(row: ComponentRow, allowed: set[str] | frozenset[str]) -> None:
        unknown = set(row.props) - allowed
        if unknown:
            _prop_fail(
                row.component_id,
                "不支持以下语义属性：" + ", ".join(sorted(unknown)),
            )

    @staticmethod
    def count(row: ComponentRow, allowed: set[int]) -> None:
        if len(row.children) not in allowed:
            message = f"子组件数量应为 {sorted(allowed)}，实际为 {len(row.children)}"
            key = "layout" if row.component_type == "Layout" else "variant"
            name = row.props.get(key)
            roles_by_name = _CHILD_ROLES.get(row.component_type, {})
            roles = roles_by_name.get(name) if isinstance(name, str) else None
            if roles is not None:
                message += (
                    f"；{row.component_type}.{key}={name!r} 要求的 children 角色为 {roles}"
                )
            _fail(row.component_id, message)

    def title(self, identifier: str) -> None:
        row = self.node(identifier)
        if row.component_type in {"SingleLineTitle", "DoubleLineTitle"}:
            return
        if row.component_type == "Group" and row.props.get("variant") == "title-count":
            return
        _fail(identifier, "标题槽必须使用标题组件或 title-count Group")

    def wrap(self, origin: str, suffix: str, child: str, props: dict) -> str:
        identifier = self.generated(origin, suffix)
        self.add(identifier, "Column", {"width": "matchParent", "alignItems": "start",
                                       "justifyContent": "start", **props}, (child,), origin)
        return identifier

    def body(self, origin: str, children: tuple[str, ...], gap: int, props: dict) -> str:
        identifier = self.generated(origin, "body")
        self.add(identifier, "Column", {"width": "matchParent", "itemMargin": gap,
                                       "alignItems": "start", "justifyContent": "start",
                                       "layoutWeight": 1, **props}, children, origin)
        return identifier

    def content(self, identifier: str, *, compact: bool, fixed: bool = False) -> None:
        row = self.node(identifier)
        if identifier in self.seen:
            _fail(identifier, "组件被多个父节点同时引用")
        self.seen.add(identifier)
        if row.component_type == "Group":
            self.group(row, compact=compact, fixed=fixed)
            return
        if row.component_type in {"Layout", "Region", "Row", "Column", "Stack"}:
            _fail(identifier, "内容槽必须使用业务组件或受控 Group")
        unknown = GEOMETRY_PROPS.intersection(row.props)
        if unknown:
            _prop_fail(
                identifier,
                "以下业务几何由模板负责，模型不能声明：" + ", ".join(sorted(unknown)),
            )
        if row.children:
            _fail(identifier, "业务组件不能声明 children")
        props = deepcopy(row.props)
        if fixed:
            props.update(width="matchParent", height="matchParent", layoutWeight=1)
        self.result.append(ComponentRow(identifier, row.component_type, props, row.children))

    def group(self, row: ComponentRow, *, compact: bool, fixed: bool = False) -> None:
        self.props(row, {"variant"})
        self.count(row, {2})
        variant = row.props.get("variant")
        group_variants = {"hero-support", "label-value", "peer-pair", "title-count"}
        if not isinstance(variant, str) or variant not in group_variants:
            _fail(row.component_id, "Group.variant 未登记")
        if fixed and self.action_nodes(row.children):
            _fail(row.component_id, "动作固定槽必须使用一个完整的 CardButton")
        props = {"width": "matchParent", "alignItems": "start", "justifyContent": "start",
                 "itemMargin": 2}
        children = row.children
        kind = "Column"
        if variant == "title-count":
            if self.node(children[0]).component_type != "SingleLineTitle":
                _fail(row.component_id, "title-count 的第一个子组件必须是 SingleLineTitle")
            if self.node(children[1]).component_type != "Badge":
                _fail(row.component_id, "title-count 的最后一个子组件必须是 Badge")
            kind = "Row"
            props.update(itemMargin=4, alignItems="center")
            title = self.wrap(row.component_id, "title", children[0], {"layoutWeight": 1})
            children = (title, children[1])
        if variant == "peer-pair":
            kind = "Row"
            props.update(itemMargin=8, alignItems="center", justifyContent="center")
            wrapped = []
            for index, child in enumerate(children):
                wrapped.append(self.wrap(row.component_id, f"peer{index}", child,
                                         {"layoutWeight": 1, "alignItems": "center"}))
            children = tuple(wrapped)
        if fixed:
            props.update(height="matchParent", layoutWeight=1)
        self.add(row.component_id, kind, props, children, row.component_id)
        for child in row.children:
            self.content(child, compact=compact)

    def region(self, identifier: str, *, compact: bool) -> None:
        row = self.node(identifier)
        if row.component_type != "Region":
            _fail(identifier, "父级内容区必须使用 Region")
        self.props(row, {"variant"})
        variant = row.props.get("variant")
        allowed = COMPACT_VARIANTS if compact else WIDE_VARIANTS
        if not isinstance(variant, str) or variant not in allowed:
            area = "compact" if compact else "wide"
            area_label = "紧凑版" if area == "compact" else "宽版"
            message = (
                f"当前父区域不支持 Region.variant（实际为 {variant!r}）；"
                f"{area_label} Region 允许的变体：" + ", ".join(sorted(allowed))
            )
            _fail(identifier, message)
        expected = {"center": {1}, "title-content": {2}, "title-hero-support": {3},
                    "title-content-action": {3}, "title-two-ratios": {3, 4},
                    "title-hero-support-action": {4}, "four-ratios": {4}, "four-items": {4}}
        self.count(row, expected.get(variant, set()))
        children = row.children
        gap = 6 if compact else 8
        if variant not in {"center", "four-ratios", "four-items"}:
            self.title(children[0])
        if variant in {"title-content-action", "title-hero-support-action"}:
            if self.node(children[-1]).component_type != "PillButton":
                _fail(identifier, "底部动作槽必须使用 PillButton")
        if variant == "title-two-ratios" and len(children) == 4:
            if self.node(children[-1]).component_type != "PillButton":
                _fail(identifier, "可选底部动作槽必须使用 PillButton")
        allowed_actions = ()
        if variant in {"title-content-action", "title-hero-support-action"}:
            allowed_actions = (children[-1],)
        elif variant == "title-two-ratios" and len(children) == 4:
            allowed_actions = (children[-1],)
        if self.action_nodes(children) != set(allowed_actions):
            _fail(identifier, "Action 必须放在所选 Region 的底部动作角色中")
        if self.contains_type(children, "InfoBlock"):
            _fail(identifier, "InfoBlock 只能放在固定槽，不能进入 Region 或其 Group")
        sub_id = self.generated(identifier, "sub")
        outer_props = {"width": "matchParent", "height": "matchParent", "layoutWeight": 1}
        if compact:
            outer_props.update(padding=self.panel_padding, borderRadius=16, clip=True)
            if in_layout_phase():
                outer_props["surfaceRole"] = "panel"
            else:
                outer_props["backgroundColor"] = "#99FFFFFF"
        self.add(identifier, "Column", outer_props, (sub_id,), identifier)
        sub_props = {"width": "matchParent", "height": "matchParent", "alignItems": "start",
                     "justifyContent": "start", "itemMargin": gap}
        sub_children = children
        if variant == "center":
            sub_props.update(alignItems="center", justifyContent="center", itemMargin=0)
        elif variant == "title-content":
            body = self.body(identifier, (children[1],), 0, {"justifyContent": "end"})
            sub_children = (children[0], body)
        elif variant == "title-content-action":
            body = self.body(identifier, (children[1],), 0, {})
            sub_children = (children[0], body, children[2])
        elif variant == "title-hero-support":
            primary = self.wrap(identifier, "primary", children[1], {"layoutWeight": 1})
            details = self.wrap(identifier, "details", children[2], {"flexShrink": 0})
            body = self.body(identifier, (primary, details), gap, {})
            sub_children = (children[0], body)
        elif variant == "title-hero-support-action":
            body = self.body(identifier, children[1:3], 2, {})
            sub_children = (children[0], body, children[3])
        else:
            ratio_children = children[1:3] if variant == "title-two-ratios" else children
            is_grid = variant in {"four-ratios", "four-items"}
            ratios = self.ratios(identifier, ratio_children, grid=is_grid,
                                 require_ratio=variant != "four-items")
            sub_children = (children[0], ratios, *children[3:])
            if is_grid:
                sub_children = (ratios,)
        self.add(sub_id, "Column", sub_props, sub_children, identifier)
        for child in children:
            if self.node(child).component_type == "InfoBlock":
                _fail(child, "InfoBlock 只能放在固定槽")
            self.content(child, compact=compact)

    def ratios(self, origin: str, children: tuple[str, ...], *, grid: bool,
               require_ratio: bool = True) -> str:
        cells = []
        for index, child in enumerate(children):
            if require_ratio and self.node(child).component_type != "ProgressCircle":
                _fail(child, "比例槽必须使用 ProgressCircle")
            cell = self.wrap(origin, f"ratio{index}", child,
                             {"height": "matchParent", "alignItems": "center",
                              "justifyContent": "center", "layoutWeight": 1})
            cells.append(cell)
            if self.node(child).component_type == "ProgressCircle":
                self.ratio_cells[child] = cell
        rows = []
        for index in range(2 if grid else 1):
            pair = tuple(cells[index * 2:index * 2 + 2])
            row_id = self.generated(origin, f"ratiorow{index}")
            self.add(row_id, "Row", {"width": "matchParent", "itemMargin": 8,
                                     "alignItems": "center", "justifyContent": "center",
                                     "layoutWeight": 1}, pair, origin)
            rows.append(row_id)
        if not grid and self.size == "2x2":
            return rows[0]
        identifier = self.generated(origin, "ratios")
        self.add(identifier, "Column", {"width": "matchParent", "itemMargin": 8,
                                        "layoutWeight": 1}, tuple(rows), origin)
        return identifier

    def inject_ratio_geometry(self) -> None:
        """只为模板登记的环形槽位补几何，源文仍不接受业务宽高。"""
        if not self.ratio_cells:
            return
        from services.compact_region_layout import reference_region_boxes

        nodes = []
        for row in self.result:
            styles = deepcopy(row.props)
            if row.component_type in {"SingleLineTitle", "DoubleLineTitle", "Badge", "PillButton"}:
                variant = None
                if row.component_type == "SingleLineTitle" and row.props.get("icon"):
                    variant = "withIcon"
                _, recipe_styles = visual_recipe_part(
                    row.component_type, "root", size=self.size, variant=variant,
                )
                styles = {**recipe_styles, **styles}
                if row.component_type == "DoubleLineTitle":
                    _, title_styles = visual_recipe_part("DoubleLineTitle", "title", size=self.size)
                    _, secondary = visual_recipe_part(
                        "DoubleLineTitle", "secondary", size=self.size,
                    )
                    constraint = secondary.get("constraintSize")
                    secondary_height = None
                    if isinstance(constraint, dict):
                        secondary_height = constraint.get("maxHeight")
                    title_height = title_styles.get("height")
                    gap = recipe_styles.get("itemMargin")
                    if not all(isinstance(value, (int, float))
                               for value in (title_height, secondary_height, gap)):
                        _fail(row.component_id,
                              "DoubleLineTitle Recipe 缺少可确定的参考高度")
                    styles["height"] = title_height + secondary_height + gap
            nodes.append({"id": row.component_id, "component": row.component_type,
                          "styles": styles, "children": list(row.children)})
        boxes = reference_region_boxes(nodes, size=self.size)
        resolved = []
        for row in self.result:
            cell_id = self.ratio_cells.get(row.component_id)
            if cell_id is None:
                resolved.append(row)
                continue
            box = boxes.get(cell_id)
            if box is None or box.width is None or box.height is None:
                _fail(row.component_id, "比例槽缺少可确定的参考尺寸")
            if box.width <= 0 or box.height <= 0:
                _fail(row.component_id, "比例槽没有有效的正数容量")
            props = {**row.props, "width": box.width, "height": box.height}
            resolved.append(ComponentRow(row.component_id, row.component_type, props, row.children))
        self.result = resolved

    def contains_type(self, identifiers: tuple[str, ...], kind: str) -> bool:
        for identifier in identifiers:
            row = self.node(identifier)
            if row.component_type == kind or self.contains_type(row.children, kind):
                return True
        return False

    def action_nodes(self, identifiers: tuple[str, ...]) -> set[str]:
        actions: set[str] = set()
        for identifier in identifiers:
            row = self.node(identifier)
            if row.component_type in {"PillButton", "CardButton"} or row.props.get("onClick"):
                actions.add(identifier)
            actions.update(self.action_nodes(row.children))
        return actions

    def top_bottom(self, root: ComponentRow) -> tuple[str, ...]:
        self.count(root, {2, 3})
        variant = root.props.get("variant", "continuous")
        if not isinstance(variant, str) or variant not in {"continuous", "bottom-details", "equal"}:
            _fail("root", "W-top-bottom.variant 未登记")
        children = root.children
        title = ()
        if len(children) == 3:
            self.title(children[0])
            title = (children[0],)
        primary, details = children[-2:]
        if self.contains_type(children, "PillButton") or self.contains_type(children, "CardButton"):
            _fail("root", "W-top-bottom 不提供共享按钮角色")
        details_type = self.node(details).component_type
        if details_type not in {"TextBlock", "TopTextBottomValue", "SummaryList"}:
            _fail(details, "details 槽必须使用 TextBlock、TopTextBottomValue 或 SummaryList")
        primary_props = {"flexShrink": 0} if variant == "continuous" else {"layoutWeight": 1}
        details_props = {"flexShrink": 0} if variant == "bottom-details" else {"layoutWeight": 1}
        primary_id = self.wrap("root", "primary", primary, primary_props)
        details_id = self.wrap("root", "details", details, details_props)
        body = self.body("root", (primary_id, details_id), 8, {})
        for child in children:
            self.content(child, compact=False)
        return (*title, body)

    def fixed_slot(self, identifier: str, *, combination: bool) -> None:
        kind = self.node(identifier).component_type
        allowed = {"InfoBlock", "CardButton"}
        if combination:
            allowed.add("Group")
        if kind not in allowed:
            _fail(identifier, "固定槽必须使用 InfoBlock、CardButton 或已登记的槽位 Group")
        self.content(identifier, compact=False, fixed=True)

    def compile(self) -> SemanticLayoutExpansion:
        self.validate_tree("root", set(), set())
        # 延迟导入公共布局注册表，避免转换器/布局匹配入口的初始化循环。
        from services.compact_layout_runtime import load_layout_contract

        contract = load_layout_contract()
        layouts = contract.get("layouts", {})
        split = layouts.get("W-split-panels", {}).get("patterns", [])[0].get("rules", [])
        root_props = split[0].get("props", {})
        panel_props = split[1].get("props", {})
        self.padding = root_props.get("padding")
        self.parent_gap = root_props.get("itemMargin")
        self.panel_padding = panel_props.get("padding")
        if any(value is None for value in (self.padding, self.parent_gap, self.panel_padding)):
            raise ValueError("2×4 已登记布局的几何定义不完整")
        root = self.node("root")
        if root.component_type != "Layout":
            _fail("root", "语义组件树的根节点必须是 Layout")
        layout = root.props.get("layout")
        if not isinstance(layout, str) or layout not in LAYOUT_IDS:
            _fail("root", "Layout.layout 未登记")
        allowed_props = _BACKGROUND_PROPS | {"layout"}
        if layout == "W-top-bottom":
            allowed_props = allowed_props | {"variant"}
        if layout == "W-content-side-slots":
            allowed_props = allowed_props | {"orientation"}
        self.props(root, allowed_props)
        props = {"width": "matchParent", "height": "matchParent", "padding": self.padding,
                 "borderRadius": 20, "clip": True, "alignItems": "start",
                 "justifyContent": "start"}
        for key in _BACKGROUND_PROPS:
            if key in root.props:
                props[key] = deepcopy(root.props[key])
        kind = "Row"
        children = root.children
        if layout == "W-top-bottom":
            kind = "Column"
            props["itemMargin"] = 6
            children = self.top_bottom(root)
        elif layout == "W-split-panels":
            self.count(root, {2})
            props.update(itemMargin=self.parent_gap, alignItems="center")
            for child in children:
                self.region(child, compact=True)
        elif layout == "W-content-side-slots":
            self.count(root, {3})
            props.update(itemMargin=self.parent_gap, alignItems="center")
            orientation = root.props.get("orientation", "content-left")
            orientations = {"content-left", "content-right"}
            if not isinstance(orientation, str) or orientation not in orientations:
                _fail("root", "orientation 未登记")
            content, upper, lower = children
            self.region(content, compact=False)
            self.fixed_slot(upper, combination=False)
            self.fixed_slot(lower, combination=False)
            slots = self.generated("root", "slots")
            self.add(slots, "Column", {"width": "matchParent", "height": "matchParent",
                                       "itemMargin": self.parent_gap, "layoutWeight": 1},
                     (upper, lower), "root")
            children = (content, slots) if orientation == "content-left" else (slots, content)
        else:
            self.count(root, {4})
            kind = "Column"
            props["itemMargin"] = self.parent_gap
            row_ids = []
            for index in range(2):
                pair = children[index * 2:index * 2 + 2]
                for child in pair:
                    self.fixed_slot(child, combination=True)
                row_id = self.generated("root", f"row{index}")
                self.add(row_id, "Row", {"width": "matchParent", "itemMargin": self.parent_gap,
                                         "layoutWeight": 1}, pair, "root")
                row_ids.append(row_id)
            children = tuple(row_ids)
        self.add("root", kind, props, children, "root")
        return self.finish(layout)

    def finish(self, layout: str) -> SemanticLayoutExpansion:
        self.inject_ratio_geometry()
        compiled = {row.component_id for row in self.result}
        missing = set(self.by_id) - compiled
        if missing:
            _fail("root", "以下组件未接入已展开的组件树：" + ", ".join(sorted(missing)))
        data_rows = []
        for row in self.source:
            if not isinstance(row, ComponentRow):
                data_rows.append(row)
        return SemanticLayoutExpansion(tuple(self.result + data_rows), self.origins, str(layout))


class _SmallCompiler(_Compiler):
    """S 系列原角色和几何；不复用宽卡 Region 的业务权限。"""

    size = "2x2"

    def title(self, identifier: str) -> None:
        if self.node(identifier).component_type != "SingleLineTitle":
            _fail(identifier, "小卡标题槽必须使用 SingleLineTitle")

    def content(self, identifier: str, *, compact: bool, fixed: bool = False) -> None:
        super().content(identifier, compact=compact, fixed=fixed)
        if self.node(identifier).component_type not in {"PillButton", "CircleButton"}:
            self.geometry(identifier, {"width": "matchParent"})

    def geometry(self, identifier: str, props: dict) -> None:
        for index, row in enumerate(self.result):
            if row.component_id == identifier:
                self.result[index] = ComponentRow(
                    identifier, row.component_type, {**row.props, **props}, row.children,
                )
                return
        _fail(identifier, "缺少已展开的槽位")

    def group(self, row: ComponentRow, *, compact: bool, fixed: bool = False) -> None:
        self.props(row, {"variant"})
        variant = row.props.get("variant")
        if not isinstance(variant, str):
            _fail(row.component_id, "小卡 Group.variant 必须是已登记的字符串")
        counts = {2, 3, 4} if variant == "supporting-items" else {2}
        self.count(row, counts)
        if variant not in {"hero-support", "label-value", "peer-pair", "supporting-items"}:
            _fail(row.component_id, "小卡 Group.variant 未登记")
        if self.action_nodes(row.children) or self.contains_type(row.children, "InfoBlock"):
            _fail(row.component_id, "小卡 Group 只能包含同一区域内的只读内容")
        props = {"width": "matchParent", "alignItems": "start",
                 "justifyContent": "start", "itemMargin": 2}
        children = row.children
        kind = "Column"
        if variant == "peer-pair":
            kind = "Row"
            props.update(itemMargin=8, alignItems="bottom")
            wrapped = []
            for index, child in enumerate(children):
                wrapped.append(self.wrap(row.component_id, f"peer{index}", child,
                                         {"layoutWeight": 1}))
            children = tuple(wrapped)
        self.add(row.component_id, kind, props, children, row.component_id)
        for child in row.children:
            self.content(child, compact=True)

    def action(self, identifier: str, kind: str = "PillButton") -> None:
        row = self.node(identifier)
        if row.component_type != kind or not row.props.get("onClick"):
            _fail(identifier, f"动作角色必须使用带 onClick 的 {kind}")

    def standard_action_body(self, primary: str, action: str, gap: int) -> str:
        content = self.wrap("root", "content", primary, {"layoutWeight": 1})
        action_area = self.wrap("root", "action", action, {"height": 36, "flexShrink": 0})
        return self.body("root", (content, action_area), gap, {})

    def compile(self) -> SemanticLayoutExpansion:
        from services.compact_layout_runtime import load_layout_contract

        self.validate_tree("root", set(), set())
        root = self.node("root")
        layout = root.props.get("layout")
        roles = SMALL_CHILD_ROLES.get(layout) if isinstance(layout, str) else None
        if root.component_type != "Layout" or roles is None:
            _fail("root", "2x2 必须选择已登记的 S 系列 Layout")
        self.props(root, _BACKGROUND_PROPS | {"layout", "variant", "design", "onClick"})
        count, description = roles
        counts = {count, count + 1} if layout == "S-title-dual-column-action" else {count}
        if len(root.children) not in counts:
            _fail(
                "root",
                f"子组件数量应为 {sorted(counts)}；要求的 children 角色为 {description}",
            )
        contract = load_layout_contract()
        layouts = contract.get("layouts", {})
        registered = layouts.get(layout, {})
        patterns = registered.get("patterns", [])
        if not patterns:
            raise ValueError("已登记小卡布局的几何定义不完整")
        rules = patterns[0].get("rules", [])
        if not rules:
            raise ValueError("已登记小卡布局的规则定义不完整")
        root_design = rules[0].get("props", {})
        props = {"width": "matchParent", "height": "matchParent", "borderRadius": 20,
                 "clip": True, "alignItems": "start", "justifyContent": "start", **root_design}
        for key in _BACKGROUND_PROPS | {"design", "onClick"}:
            if key in root.props:
                props[key] = deepcopy(root.props[key])
        variant = root.props.get("variant", "standard")
        allowed = {"standard"}
        if layout in {"S-title-content-action", "S-title-primary-secondary-action"}:
            allowed.add("dense")
        if layout == "S-title-content-action":
            allowed.update({"direct", "direct-tight", "direct-dense", "direct-flush"})
        if layout == "S-title-dual-content":
            allowed.add("stacked-info")
        if not isinstance(variant, str) or variant not in allowed:
            _fail("root", "小卡允许的 variant：" + ", ".join(sorted(allowed)))
        children = root.children
        expected_actions: set[str] = set()
        if layout.startswith("S-title-"):
            self.title(children[0])
        if layout in {"S-title-content-action", "S-title-primary-secondary-action",
                      "S-title-anchor"}:
            kind = "CircleButton" if layout == "S-title-anchor" else "PillButton"
            self.action(children[-1], kind)
            expected_actions.add(children[-1])
        if layout == "S-content-dual-action":
            for child in children[1:]:
                self.action(child)
                expected_actions.add(child)
        if layout == "S-title-dual-column-action" and len(children) == 4:
            self.action(children[-1])
            expected_actions.add(children[-1])
        if self.action_nodes(children) != expected_actions:
            _fail("root", "Action 必须放在所选小卡布局的动作角色中")
        for child in children:
            self.content(child, compact=True)
        if self.contains_type(children, "InfoBlock"):
            if layout not in {"S-dual-info", "S-title-dual-content"}:
                _fail("root", "InfoBlock 必须放在已登记的小卡固定槽")
        if layout == "S-center":
            if self.node(children[0]).component_type != "DataDisplay":
                _fail(children[0], "S-center 必须使用一个完整的 DataDisplay")
        elif layout == "S-title-content":
            content = self.wrap("root", "content", children[1],
                                {"layoutWeight": 1, "justifyContent": "end"})
            children = (children[0], content)
        elif layout == "S-title-dual-content":
            if variant == "stacked-info":
                for child in children[1:]:
                    row = self.node(child)
                    if row.component_type != "InfoBlock" or row.props.get("visual"):
                        _fail(child, "stacked-info 必须使用两个不含 visual 的 InfoBlock")
                    if row.props.get("variant") != "stacked":
                        _fail(child, "stacked-info 要求 InfoBlock.variant='stacked'")
                    self.geometry(child, {"height": 50})
                body = self.body("root", children[1:], 8, {"height": 108})
            else:
                if self.contains_type(children[1:], "InfoBlock"):
                    _fail("root", "两个 InfoBlock 必须使用 stacked-info 变体")
                primary = self.wrap("root", "primary", children[1], {"layoutWeight": 1})
                support = self.wrap("root", "support", children[2],
                                    {"layoutWeight": 1, "justifyContent": "end"})
                body = self.body("root", (primary, support), 8, {})
            children = (children[0], body)
        elif layout == "S-quad-content":
            row_ids = []
            for index in range(2):
                pair = children[index * 2:index * 2 + 2]
                for child in pair:
                    self.geometry(child, {"width": 59, "height": 59})
                identifier = self.generated("root", f"row{index}")
                self.add(identifier, "Row", {"width": "matchParent", "itemMargin": 8,
                                             "layoutWeight": 1}, pair, "root")
                row_ids.append(identifier)
            children = tuple(row_ids)
        elif layout in {"S-title-content-action", "S-title-primary-secondary-action"}:
            props["itemMargin"] = 4 if variant == "dense" else 6
            primary = children[1]
            if layout == "S-title-primary-secondary-action":
                primary = self.generated("root", "primary_support")
                self.add(primary, "Column", {"width": "matchParent", "itemMargin": 2,
                                             "alignItems": "start", "justifyContent": "start",
                                             "layoutWeight": 1},
                         children[1:3], "root")
            if variant.startswith("direct"):
                gaps = {"direct": 6, "direct-dense": 4, "direct-tight": 2, "direct-flush": 0}
                props["itemMargin"] = gaps.get(variant, 6)
                self.geometry(primary, {"layoutWeight": 1})
                children = (children[0], primary, children[-1])
            else:
                if layout == "S-title-primary-secondary-action":
                    action = self.wrap("root", "action", children[-1],
                                       {"height": 36, "flexShrink": 0})
                    body = self.body("root", (primary, action), 8, {})
                else:
                    body = self.standard_action_body(primary, children[-1], 8)
                children = (children[0], body)
        elif layout == "S-title-dual-column-action":
            metrics = self.ratios("root", children[1:3], grid=False)
            if len(children) == 4:
                action = self.wrap("root", "action", children[-1],
                                   {"height": 36, "flexShrink": 0})
                body = self.body("root", (metrics, action), 8, {})
                children = (children[0], body)
            else:
                children = (children[0], metrics)
        elif layout == "S-title-anchor":
            support = self.node(children[2])
            height = 40
            if support.component_type == "NumericRatioStack":
                if support.props.get("direction", "column") == "column":
                    height = 56
                    self.geometry(children[2], {"height": 56})
            self.geometry(children[2], {"width": 78})
            action_slot = self.generated("root", "action_slot")
            self.add(action_slot, "Stack", {"width": 40, "height": 40,
                                            "alignContent": "center"}, (children[-1],), "root")
            bottom = self.generated("root", "bottom")
            self.add(bottom, "Row", {"width": "matchParent", "height": height, "flexShrink": 0,
                                     "itemMargin": 8, "alignItems": "bottom",
                                     "justifyContent": "spaceBetween"},
                     (children[2], action_slot), "root")
            primary = self.wrap("root", "primary", children[1], {"layoutWeight": 1})
            body = self.body("root", (primary, bottom), 8, {})
            children = (children[0], body)
        elif layout == "S-content-dual-action":
            content = self.wrap("root", "content", children[0],
                                {"layoutWeight": 1, "flexShrink": 0})
            children = (content, *children[1:])
        elif layout == "S-dual-info":
            for child in children:
                if self.node(child).component_type != "InfoBlock":
                    _fail(child, "S-dual-info 必须使用两个 InfoBlock")
                self.geometry(child, {"layoutWeight": 1})
        self.add("root", "Column", props, children, "root")
        return self.finish(layout)


def expand_semantic_layout_rows(
    rows: list[CompactRow] | tuple[CompactRow, ...], *, size: str | None = None,
) -> SemanticLayoutExpansion:
    if not has_semantic_layout(rows):
        return SemanticLayoutExpansion(tuple(rows), {})
    root = next((row for row in rows if isinstance(row, ComponentRow)
                 and row.component_id == "root"), None)
    layout = root.props.get("layout") if root is not None else None
    inferred = "2x2" if isinstance(layout, str) and layout in SMALL_CHILD_ROLES else "2x4"
    target = inferred if size is None else size
    if target != inferred:
        _fail("root", f"该布局仅适用于尺寸 {inferred}，不能用于 {target}")
    compiler = _SmallCompiler(rows) if target == "2x2" else _Compiler(rows)
    return compiler.compile()
