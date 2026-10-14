"""2×4 语义布局展开；固定几何由模板拥有，原业务行和绑定不改写。"""

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

SEMANTIC_LAYOUT_TYPES = frozenset({"Layout", "Region", "Group"})
LAYOUT_IDS = frozenset({
    "W-top-bottom", "W-split-panels", "W-content-side-slots", "W-four-slots",
})
COMPACT_VARIANTS = frozenset({
    "center", "title-content", "title-primary-details", "title-content-action",
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
_REGION_CHILD_COUNTS = {
    "center": {1}, "title-content": {2}, "title-primary-details": {3},
    "title-content-action": {3}, "title-two-ratios": {3, 4},
    "title-hero-support-action": {4}, "four-ratios": {4}, "four-items": {4},
}

# 有序角色只用于解释既有 count 门禁，不参与几何展开或案例选型。
_CHILD_ROLES = {
    "Layout": {
        "W-top-bottom": "[title?, primary, details]",
        "W-split-panels": "[left Region, right Region]",
        "W-content-side-slots": (
            "[content Region, upper InfoBlock/CardButton, lower InfoBlock/CardButton]"
        ),
        "W-four-slots": "[top-left slot, top-right slot, bottom-left slot, bottom-right slot]",
    },
    "Region": {
        "center": "[content]",
        "title-content": "[title, content]",
        "title-primary-details": "[title, primary, details]",
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


def region_variant_contracts(*, compact: bool) -> dict[str, dict]:
    """修复与模型说明复用编译器的变体、数量和角色合同。"""
    allowed = COMPACT_VARIANTS if compact else WIDE_VARIANTS
    roles = _CHILD_ROLES.get("Region", {})
    result = {}
    for variant in sorted(allowed):
        counts = _REGION_CHILD_COUNTS.get(variant)
        child_roles = roles.get(variant)
        if counts is None or child_roles is None:
            raise ValueError("Region variant contract is incomplete: " + variant)
        result[variant] = {"childCounts": sorted(counts), "childRoles": child_roles}
    return result


def _fail(identifier: str, message: str) -> NoReturn:
    raise CompactDslConversionError(
        f"layout does not match semantic contract: {identifier}: {message}. "
        "Choose a registered Layout/Region/Group variant; do not edit expanded geometry."
    )


def _prop_fail(identifier: str, message: str) -> NoReturn:
    raise CompactDslConversionError(
        f"component {identifier}: invalid semantic props: {message}. "
        "Fix only the reported properties; preserve the current layout, facts and Actions."
    )


class _Compiler:
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
            _fail(identifier, "cyclic component reference")
        if identifier in visited:
            _fail(identifier, "component has multiple parents")
        if len(visiting) >= 64:
            _fail(identifier, "semantic tree nesting exceeds safe depth")
        row = self.node(identifier)
        visiting.add(identifier)
        for child in row.children:
            self.validate_tree(child, visiting, visited)
        visiting.remove(identifier)
        visited.add(identifier)

    def node(self, identifier: str) -> ComponentRow:
        row = self.by_id.get(identifier)
        if row is None:
            _fail(identifier, "missing component reference")
        return row

    def generated(self, origin: str, suffix: str) -> str:
        identifier = f"{GENERATED_PREFIX}{origin}__{suffix}"
        if identifier in self.by_id or identifier in self.origins:
            _fail(origin, "generated component id collision")
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
            _prop_fail(row.component_id, "unsupported semantic properties " +
                       ", ".join(sorted(unknown)))

    @staticmethod
    def count(row: ComponentRow, allowed: set[int]) -> None:
        if len(row.children) not in allowed:
            message = f"expected child count {sorted(allowed)}, got {len(row.children)}"
            key = "layout" if row.component_type == "Layout" else "variant"
            name = row.props.get(key)
            roles_by_name = _CHILD_ROLES.get(row.component_type, {})
            roles = roles_by_name.get(name) if isinstance(name, str) else None
            if roles is not None:
                message += f"; {row.component_type}.{key}={name!r} requires children {roles}"
            _fail(row.component_id, message)

    def title(self, identifier: str) -> None:
        row = self.node(identifier)
        if row.component_type in {"SingleLineTitle", "DoubleLineTitle"}:
            return
        if row.component_type == "Group" and row.props.get("variant") == "title-count":
            return
        _fail(identifier, "title slot requires a title component or title-count Group")

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
            _fail(identifier, "component has multiple parents")
        self.seen.add(identifier)
        if row.component_type == "Group":
            self.group(row, compact=compact, fixed=fixed)
            return
        if row.component_type in {"Layout", "Region", "Row", "Column", "Stack"}:
            _fail(identifier, "content slot requires a business component or controlled Group")
        unknown = GEOMETRY_PROPS.intersection(row.props)
        if unknown:
            _prop_fail(identifier, "business geometry is template-owned: " +
                       ", ".join(sorted(unknown)))
        if row.children:
            _fail(identifier, "business component cannot have children")
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
            _fail(row.component_id, "unknown Group.variant")
        if fixed and self.action_nodes(row.children):
            _fail(row.component_id, "action fixed slot requires one complete CardButton")
        props = {"width": "matchParent", "alignItems": "start", "justifyContent": "start",
                 "itemMargin": 2}
        children = row.children
        kind = "Column"
        if variant == "title-count":
            if self.node(children[0]).component_type != "SingleLineTitle":
                _fail(row.component_id, "title-count starts with SingleLineTitle")
            if self.node(children[1]).component_type != "Badge":
                _fail(row.component_id, "title-count ends with Badge")
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
            _fail(identifier, "parent content area requires Region")
        self.props(row, {"variant"})
        variant = row.props.get("variant")
        allowed = COMPACT_VARIANTS if compact else WIDE_VARIANTS
        if not isinstance(variant, str) or variant not in allowed:
            area = "compact" if compact else "wide"
            message = (
                f"Region.variant is not supported in this parent area (got {variant!r}); "
                f"{area} Region variants: " + ", ".join(sorted(allowed))
            )
            _fail(identifier, message)
        self.count(row, _REGION_CHILD_COUNTS.get(variant, set()))
        children = row.children
        gap = 6 if compact else 8
        if variant not in {"center", "four-ratios", "four-items"}:
            self.title(children[0])
        if variant in {"title-content-action", "title-hero-support-action"}:
            if self.node(children[-1]).component_type != "PillButton":
                _fail(identifier, "bottom action requires PillButton")
        if variant == "title-two-ratios" and len(children) == 4:
            if self.node(children[-1]).component_type != "PillButton":
                _fail(identifier, "optional bottom action requires PillButton")
        allowed_actions = ()
        if variant in {"title-content-action", "title-hero-support-action"}:
            allowed_actions = (children[-1],)
        elif variant == "title-two-ratios" and len(children) == 4:
            allowed_actions = (children[-1],)
        if self.action_nodes(children) != set(allowed_actions):
            _fail(identifier, "Action must occupy the selected Region bottom-action role")
        if self.contains_type(children, "InfoBlock"):
            _fail(identifier, "InfoBlock belongs only in fixed slots, not Region or its Groups")
        sub_id = self.generated(identifier, "sub")
        outer_props = {"width": "matchParent", "height": "matchParent", "layoutWeight": 1}
        if compact:
            outer_props.update(padding=self.panel_padding, backgroundColor="#99FFFFFF",
                               borderRadius=16, clip=True)
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
        elif variant == "title-primary-details":
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
                _fail(child, "InfoBlock belongs only in fixed slots")
            self.content(child, compact=compact)

    def ratios(self, origin: str, children: tuple[str, ...], *, grid: bool,
               require_ratio: bool = True) -> str:
        cells = []
        for index, child in enumerate(children):
            if require_ratio and self.node(child).component_type != "ProgressCircle":
                _fail(child, "ratio slot requires ProgressCircle")
            cell = self.wrap(origin, f"ratio{index}", child,
                             {"height": "matchParent", "alignItems": "center",
                              "justifyContent": "center", "layoutWeight": 1})
            cells.append(cell)
            if self.node(child).component_type == "ProgressCircle":
                self.ratio_cells[child] = cell
        identifier = self.generated(origin, "ratios")
        rows = []
        for index in range(2 if grid else 1):
            pair = tuple(cells[index * 2:index * 2 + 2])
            row_id = self.generated(origin, f"ratiorow{index}")
            self.add(row_id, "Row", {"width": "matchParent", "itemMargin": 8,
                                     "alignItems": "center", "justifyContent": "center",
                                     "layoutWeight": 1}, pair, origin)
            rows.append(row_id)
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
                    row.component_type, "root", size="2x4", variant=variant,
                )
                styles = {**recipe_styles, **styles}
                if row.component_type == "DoubleLineTitle":
                    _, title_styles = visual_recipe_part("DoubleLineTitle", "title", size="2x4")
                    _, secondary = visual_recipe_part("DoubleLineTitle", "secondary", size="2x4")
                    constraint = secondary.get("constraintSize")
                    secondary_height = None
                    if isinstance(constraint, dict):
                        secondary_height = constraint.get("maxHeight")
                    title_height = title_styles.get("height")
                    gap = recipe_styles.get("itemMargin")
                    if not all(isinstance(value, (int, float))
                               for value in (title_height, secondary_height, gap)):
                        _fail(row.component_id,
                              "DoubleLineTitle recipe has unknown reference height")
                    styles["height"] = title_height + secondary_height + gap
            nodes.append({"id": row.component_id, "component": row.component_type,
                          "styles": styles, "children": list(row.children)})
        boxes = reference_region_boxes(nodes, size="2x4")
        resolved = []
        for row in self.result:
            cell_id = self.ratio_cells.get(row.component_id)
            if cell_id is None:
                resolved.append(row)
                continue
            box = boxes.get(cell_id)
            if box is None or box.width is None or box.height is None:
                _fail(row.component_id, "ratio slot has unknown reference dimensions")
            if box.width <= 0 or box.height <= 0:
                _fail(row.component_id, "ratio slot has no positive reference capacity")
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
            _fail("root", "unknown W-top-bottom variant")
        children = root.children
        title = ()
        if len(children) == 3:
            self.title(children[0])
            title = (children[0],)
        primary, details = children[-2:]
        if self.contains_type(children, "PillButton") or self.contains_type(children, "CardButton"):
            _fail("root", "W-top-bottom does not have shared button roles")
        details_type = self.node(details).component_type
        if details_type not in {"TextBlock", "TopTextBottomValue", "SummaryList"}:
            _fail(details, "details slot requires TextBlock/TopTextBottomValue/SummaryList")
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
            _fail(identifier, "fixed slot requires InfoBlock/CardButton or registered slot Group")
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
            raise ValueError("2×4 registered layout geometry is incomplete")
        root = self.node("root")
        if root.component_type != "Layout":
            _fail("root", "semantic tree must start with Layout")
        layout = root.props.get("layout")
        if not isinstance(layout, str) or layout not in LAYOUT_IDS:
            _fail("root", "unknown Layout.layout")
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
                _fail("root", "unknown orientation")
            content, upper, lower = children
            self.region(content, compact=False)
            self.fixed_slot(upper, combination=False)
            self.fixed_slot(lower, combination=False)
            if self.node(upper).component_type == "CardButton":
                if self.node(lower).component_type == "InfoBlock":
                    _fail("root", "mixed fixed slots require InfoBlock above CardButton")
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
        self.inject_ratio_geometry()
        compiled = {row.component_id for row in self.result}
        missing = set(self.by_id) - compiled
        if missing:
            _fail("root", "uncompiled component(s): " + ", ".join(sorted(missing)))
        data_rows = []
        for row in self.source:
            if not isinstance(row, ComponentRow):
                data_rows.append(row)
        return SemanticLayoutExpansion(tuple(self.result + data_rows), self.origins, str(layout))


def expand_semantic_layout_rows(
    rows: list[CompactRow] | tuple[CompactRow, ...], *, size: str | None = None,
) -> SemanticLayoutExpansion:
    if not has_semantic_layout(rows):
        return SemanticLayoutExpansion(tuple(rows), {})
    if size not in {None, "2x4"}:
        _fail("root", "semantic layout is available only for size 2x4")
    return _Compiler(rows).compile()
