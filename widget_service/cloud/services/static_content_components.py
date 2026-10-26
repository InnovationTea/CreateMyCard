"""三类静态内容语义的受控展开；布局与文字规格统一读取增量合同。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.card_validation.compact_validation.semantic.layout.text_capacity import (
    require_static_text_capacity,
)
from services.generation_content_policy import STATIC_COMPONENTS, current_content_policy
from services.static_text_capacity import (
    component_spec,
    measure_text,
    number,
    text_spec,
    text_width,
)
from services.theme_style_roles import alpha_role, is_role


def _fail(message: str) -> None:
    from services.compact_high_level_components import CompactDslConversionError

    raise CompactDslConversionError(message)


def static_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{location} 必须是非空静态文字。")
    if "{{" in value or "${" in value:
        _fail(f"{location} 不支持动态表达式。")
    return value


def _fields(value: Any, allowed: set[str], location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed:
        _fail(f"{location} 只允许字段 {sorted(allowed)}。")
    return value


def _color_alpha(color: str) -> str:
    if is_role(color):
        return alpha_role(color, 0.6)
    if len(color) == 9 and color.startswith("#"):
        return "#99" + color[3:]
    _fail("静态组件缺少合法主题文字色。")
    return color


def _record_row_fits(
    item: dict[str, Any], widths: dict[str, float], main_width: float, compact: bool
) -> bool:
    """侧栏导致主区不可读时改为本条目内纵排，不删字段或缩小文字。"""
    styles = {"title": "compactTitle" if compact else "recordTitle"}
    styles["description"] = "compactDescription" if compact else "recordDescription"
    try:
        for key, style in styles.items():
            if key in item and not measure_text(item.get(key), main_width, text_spec(style)).fits:
                return False
        for key, extent in widths.items():
            if not measure_text(item.get(key), extent, text_spec("side")).fits:
                return False
    except ValueError:
        return False
    return True


class _Builder:
    def __init__(
        self, component: Any, width: float, palette: dict[str, str], font_size: int = 12,
    ) -> None:
        self.component = component
        self.font_size = font_size
        self.width = width
        self.rows: list[Any] = []
        self.ink = palette.get("primary")
        self.panel = palette.get("componentSecondary")
        from services.theme_style_roles import in_layout_phase, role

        if in_layout_phase():
            self.panel = role("panel")
        if not isinstance(self.ink, str) or not isinstance(self.panel, str):
            _fail("静态组件缺少主题角色。")
        self.secondary = _color_alpha(self.ink)

    def spec(self, name: str) -> dict[str, Any]:
        return text_spec(name, self.font_size)

    def identifier(self, suffix: str) -> str:
        return f"{self.component.component_id}__static_{suffix}"

    def add(self, identifier: str, kind: str, props: dict, children: list[str]) -> None:
        from services.compact_high_level_components import ComponentRow

        self.rows.append(ComponentRow(identifier, kind, props, tuple(children)))

    def text(
        self, suffix: str, value: Any, width: float, style: str, *, secondary: bool = False
    ) -> tuple[str, float]:
        identifier = self.identifier(suffix)
        content = static_string(value, f"{self.component.component_id}.{suffix}")
        spec = self.spec(style)
        capacity = require_static_text_capacity(
            content,
            width,
            spec,
            f"{self.component.component_id}.{suffix}",
        )
        props = {
            "fontSize": number(spec, "fontSize"),
            "fontWeight": int(number(spec, "fontWeight")),
            "lineHeight": number(spec, "lineHeight") / number(spec, "fontSize"),
            "maxLines": 1,
            "height": number(spec, "lineHeight"),
            "width": "matchParent",
            "flexShrink": 0,
            "wordBreak": "normal",
            "fontColor": self.secondary if secondary else self.ink,
            "_visualRecipe": f"static-content-v1:{self.component.component_type}.{suffix}",
        }
        if capacity.lines == 1:
            self.add(identifier, "Text", {**props, "content": content}, [])
        else:
            children = []
            for index, line in enumerate(capacity.wrapped_lines):
                line_id = self.identifier(f"{suffix}_line{index}")
                self.add(line_id, "Text", {**props, "content": line}, [])
                children.append(line_id)
            self.column(identifier, children, capacity.height, 0.0)
        return identifier, capacity.height

    def column(
        self,
        identifier: str,
        children: list[str],
        height: float,
        gap: float,
        *,
        extra: dict | None = None,
    ) -> None:
        props = {
            "width": "matchParent",
            "height": height,
            "itemMargin": gap,
            "alignItems": "start",
            "justifyContent": "start",
            "flexShrink": 0,
        }
        props.update(extra or {})
        self.add(identifier, "Column", props, children)

    def header(self, props: dict[str, Any]) -> None:
        if self.font_size != 12:
            _fail("静态单行标题固定12字号，不能缩小标题以通过容量。")
        values = _fields(props, {"title", "icon", "fillColor"}, "静态标题")
        spec = component_spec("StaticHeader")
        icon = values.get("icon")
        extent = number(spec, "iconSize") if icon is not None else 0.0
        gap = number(spec, "iconGap") if icon is not None else 0.0
        title_id, height = self.text(
            "title", values.get("title"), self.width - extent - gap, "header",
        )
        if icon is None:
            if "fillColor" in values:
                _fail("静态标题fillColor需要图标。")
            self.column(self.component.component_id, [title_id], height, 0.0)
            return
        icon = static_string(icon, "静态标题图标")
        icon_id = self.identifier("icon")
        image_props = {"src": icon, "width": extent, "height": extent, "flexShrink": 0}
        if "fillColor" in values:
            image_props["fillColor"] = values.get("fillColor")
        self.add(icon_id, "Image", image_props, [])
        for row in self.rows:
            if row.component_id == title_id:
                row.props["width"] = "matchParent"
                row.props["layoutWeight"] = 1
        self.add(
            self.component.component_id, "Row",
            {"width": "matchParent", "height": max(height, extent), "itemMargin": gap,
             "alignItems": "center", "flexShrink": 0},
            [title_id, icon_id],
        )

    def block(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"title", "body", "attributes", "variant"}, "ContentBlock")
        if not any(key in values for key in ("title", "body", "attributes")):
            _fail("ContentBlock 至少包含标题、正文或属性。")
        variant = values.get("variant", "flow")
        if not isinstance(variant, str) or variant not in {"flow", "bottom-attributes"}:
            _fail("ContentBlock.variant 未登记。")
        spec = component_spec("ContentBlock")
        gap = number(spec, "gap")
        children: list[str] = []
        heights: list[float] = []
        for key in ("title", "body"):
            if key not in values:
                continue
            identifier, height = self.text(key, values.get(key), self.width, key)
            children.append(identifier)
            heights.append(height)
        attributes = values.get("attributes")
        attribute_id = self.identifier("attributes")
        if attributes is not None:
            if not isinstance(attributes, list) or not attributes:
                _fail("ContentBlock.attributes 必须是非空数组。")
            if len(attributes) > number(spec, "maximumAttributes"):
                _fail("ContentBlock.attributes 超过登记数量。")
            attribute_children: list[str] = []
            attribute_heights: list[float] = []
            label_area = 0.0
            for raw in attributes:
                item = _fields(raw, {"label", "value", "valueRole"}, "属性行")
                if "label" in item:
                    label = static_string(item.get("label"), "属性标签")
                    extent = text_width(label, number(self.spec("attribute"), "fontSize"))
                    label_area = max(label_area, extent)
            for index, raw in enumerate(attributes):
                item = _fields(raw, {"label", "value", "valueRole"}, f"attributes[{index}]")
                value = static_string(item.get("value"), "属性值")
                value_role = item.get("valueRole", "body")
                if value_role not in ("body", "value"):
                    _fail("属性valueRole只允许body或value。")
                if "label" not in item:
                    value_id, value_height = self.text(
                        f"attr{index}_value", value, self.width, "attributeBody"
                    )
                    attribute_children.append(value_id)
                    attribute_heights.append(value_height)
                    continue
                label = static_string(item.get("label"), "属性标签")
                value_width = text_width(value, number(self.spec("attribute"), "fontSize"))
                inline = label_area + value_width + gap <= self.width
                if inline:
                    current_label_area = label_area
                    value_area = self.width - current_label_area - gap
                else:
                    current_label_area = self.width
                    value_area = self.width
                label_id, label_height = self.text(
                    f"attr{index}_label",
                    label,
                    current_label_area,
                    "attribute",
                    secondary=True,
                )
                value_id, value_height = self.text(
                    f"attr{index}_value",
                    value,
                    value_area,
                    "attribute",
                )
                row_id = self.identifier(f"attr{index}")
                height = max(label_height, value_height) if inline else label_height + value_height
                if inline:
                    for row in self.rows[-2:]:
                        row.props["width"] = (
                            current_label_area if row.component_id == label_id else value_area
                        )
                        if row.component_id == value_id and value_role == "value":
                            row.props["textAlign"] = "end"
                    self.add(
                        row_id,
                        "Row",
                        {
                            "width": "matchParent",
                            "height": height,
                            "itemMargin": gap,
                            "alignItems": "start",
                        },
                        [label_id, value_id],
                    )
                else:
                    self.column(row_id, [label_id, value_id], height, 0.0)
                attribute_children.append(row_id)
                attribute_heights.append(height)
            gap_key = "compactAttributeGap" if len(attributes) >= 4 else "attributeGap"
            attribute_gap = number(spec, gap_key)
            total = sum(attribute_heights) + attribute_gap * max(0, len(attribute_heights) - 1)
            self.column(attribute_id, attribute_children, total, attribute_gap)
            children.append(attribute_id)
            heights.append(total)
        if variant == "bottom-attributes" and attributes is None:
            _fail("bottom-attributes 必须包含属性。")
        total = sum(heights) + gap * max(0, len(heights) - 1)
        extra = None
        if variant == "bottom-attributes":
            extra = {"height": "matchParent", "constraintSize": {"minHeight": total}}
            if len(children) > 1:
                top_id = self.identifier("top")
                top_height = sum(heights[:-1]) + gap * max(0, len(heights) - 2)
                self.column(top_id, children[:-1], top_height, gap, extra={"layoutWeight": 1})
                children = [top_id, attribute_id]
        self.column(self.component.component_id, children, total, gap, extra=extra)

    def records(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"items", "variant"}, "RecordList")
        items = values.get("items")
        spec = component_spec("RecordList")
        if not isinstance(items, list):
            _fail("RecordList.items 必须为记录数组。")
        if not number(spec, "minimumItems") <= len(items) <= number(spec, "maximumItems"):
            _fail("RecordList.items 必须为 1–3 个记录。")
        variant = values.get("variant", "plain")
        if not isinstance(variant, str) or variant not in {"plain", "panel"}:
            _fail("RecordList.variant 未登记。")
        compact = len(items) == 3
        gap = number(spec, "compactGap" if compact else "gap")
        padding = number(spec, "panelPadding") if variant == "panel" else 0.0
        children: list[str] = []
        heights: list[float] = []
        for index, raw in enumerate(items):
            item = _fields(raw, {"title", "description", "leading", "trailing"}, "记录")
            width = self.width - padding * 2
            side_widths: dict[str, float] = {}
            for side in ("leading", "trailing"):
                if side not in item:
                    continue
                content = static_string(item.get(side), f"记录 {side}")
                desired = text_width(content, number(self.spec("side"), "fontSize"))
                limit = number(spec, "leadingMax" if side == "leading" else "trailingMax")
                side_widths[side] = min(desired, limit)
            side_gap = number(spec, "sideGap")
            main_width = width - sum(side_widths.values()) - side_gap * len(side_widths)
            stacked = bool(side_widths) and not _record_row_fits(
                item, side_widths, main_width, compact
            )
            if stacked:
                main_width = width
            title_id, title_height = self.text(
                f"item{index}_title",
                item.get("title"),
                main_width,
                "compactTitle" if compact else "recordTitle",
            )
            main_children = [title_id]
            main_height = title_height
            if "description" in item:
                description_id, description_height = self.text(
                    f"item{index}_description",
                    item.get("description"),
                    main_width,
                    "compactDescription" if compact else "recordDescription",
                    secondary=True,
                )
                main_children.append(description_id)
                main_height += description_height + number(spec, "innerGap")
            if stacked:
                for side in side_widths:
                    side_id, side_height = self.text(
                        f"item{index}_{side}", item.get(side), width, "side", secondary=True
                    )
                    main_children.append(side_id)
                    main_height += side_height + number(spec, "innerGap")
                side_widths = {}
            main_id = self.identifier(f"item{index}_main")
            self.column(
                main_id,
                main_children,
                main_height,
                number(spec, "innerGap"),
                extra={"layoutWeight": 1},
            )
            row_children = [main_id]
            height = main_height
            for side, extent in side_widths.items():
                side_id, side_height = self.text(
                    f"item{index}_{side}",
                    item.get(side),
                    extent,
                    "side",
                    secondary=True,
                )
                self.rows[-1].props["width"] = extent
                height = max(height, side_height)
                if side == "leading":
                    row_children.insert(0, side_id)
                else:
                    row_children.append(side_id)
            row_id = self.identifier(f"item{index}")
            if variant == "plain" and index:
                divider_id = self.identifier(f"divider{index}")
                thickness = number(spec, "dividerWidth")
                divider_color = "#1F" + self.ink[3:]
                if is_role(self.ink):
                    divider_color = alpha_role(self.ink, number(spec, "dividerAlpha"))
                self.add(
                    divider_id,
                    "Divider",
                    {
                        "width": "matchParent",
                        "height": thickness,
                        "strokeWidth": thickness,
                        "flexShrink": 0,
                        "color": divider_color,
                    },
                    [],
                )
                children.append(divider_id)
                heights.append(thickness)
            row_props = {
                "width": "matchParent",
                "height": height + padding * 2,
                "padding": padding,
                "itemMargin": side_gap,
                "alignItems": "center",
            }
            if variant == "panel":
                row_props.update(
                    backgroundColor=self.panel, borderRadius=number(spec, "panelRadius")
                )
            self.add(row_id, "Row", row_props, row_children)
            children.append(row_id)
            heights.append(height + padding * 2)
        outer_gap = gap / 2 if variant == "plain" else gap
        self.column(
            self.component.component_id,
            children,
            sum(heights) + outer_gap * max(0, len(heights) - 1),
            outer_gap,
        )

    def comparison(self, props: dict[str, Any], size: str) -> None:
        values = _fields(props, {"items"}, "ComparisonGroup")
        items = values.get("items")
        spec = component_spec("ComparisonGroup")
        if size != "2x4" or not isinstance(items, list):
            _fail("ComparisonGroup 仅支持 2x4 的静态对象数组。")
        if not number(spec, "minimumItems") <= len(items) <= number(spec, "maximumItems"):
            _fail("ComparisonGroup 仅支持 2x4 的 2–3 个等权对象。")
        gap = number(spec, "gap")
        padding = number(spec, "padding")
        inner_gap = number(spec, "innerGap")
        column_width = (self.width - gap * (len(items) - 1)) / len(items)
        text_area = column_width - padding * 2
        children: list[str] = []
        heights: list[float] = []
        for index, raw in enumerate(items):
            item = _fields(raw, {"primaryText", "secondaryText", "details"}, "对比对象")
            parts: list[str] = []
            part_heights: list[float] = []
            for key, style in (
                ("primaryText", "comparisonPrimary"),
                ("secondaryText", "comparisonSecondary"),
            ):
                if key == "secondaryText" and key not in item:
                    continue
                part_id, height = self.text(
                    f"item{index}_{key}",
                    item.get(key),
                    text_area,
                    style,
                    secondary=key == "secondaryText",
                )
                parts.append(part_id)
                part_heights.append(height)
            if "details" in item:
                details = item.get("details")
                if not isinstance(details, list) or not 1 <= len(details) <= 2:
                    _fail("ComparisonGroup.details 只允许 1–2 条静态辅助内容。")
                for detail_index, detail in enumerate(details):
                    part_id, height = self.text(
                        f"item{index}_detail{detail_index}",
                        detail,
                        text_area,
                        "detail",
                        secondary=True,
                    )
                    parts.append(part_id)
                    part_heights.append(height)
            column_id = self.identifier(f"item{index}")
            height = sum(part_heights) + inner_gap * max(0, len(parts) - 1) + padding * 2
            self.column(
                column_id,
                parts,
                height,
                inner_gap,
                extra={
                    "padding": padding,
                    "layoutWeight": 1,
                    "backgroundColor": self.panel,
                    "borderRadius": number(spec, "radius"),
                },
            )
            children.append(column_id)
            heights.append(height)
        for row in self.rows:
            if row.component_id in children:
                row.props["height"] = max(heights)
        self.add(
            self.component.component_id,
            "Row",
            {
                "width": "matchParent",
                "height": max(heights),
                "itemMargin": gap,
                "alignItems": "start",
            },
            children,
        )

    def support(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"items", "columns", "fontSize"}, "静态共享说明")
        if values.get("columns", 1) != 1 or values.get("fontSize", 12) != 12:
            _fail("静态共享说明使用单列12字号，不承担正文对象。")
        items = values.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 2:
            _fail("静态共享说明仅允许1–2条必要说明。")
        children = []
        heights = []
        for index, raw in enumerate(items):
            item = _fields(raw, {"label", "value", "maxLines"}, "静态共享说明条目")
            maximum = item.get("maxLines", 3)
            if type(maximum) is not int or maximum not in {1, 2, 3}:
                _fail("静态共享说明最多三行，不能通过maxLines放宽容量。")
            label = static_string(item.get("label"), "说明标签") if "label" in item else ""
            value = static_string(item.get("value"), "说明文字")
            identifier, height = self.text(
                f"note{index}", label + value, self.width, "note", secondary=True
            )
            children.append(identifier)
            heights.append(height)
        self.column(self.component.component_id, children, sum(heights) + 4 * (len(items) - 1), 4)


def expand_static_component(
    component: Any, size: str, *, width: float, palette: dict[str, str]
) -> list[Any]:
    if not current_content_policy().is_static:
        _fail("静态内容组件需要服务端请求上下文授权。")
    if component.component_type not in STATIC_COMPONENTS | {"SecondaryBody", "SingleLineTitle"}:
        _fail("静态组件未登记。")
    props = deepcopy(component.props)
    if component.component_type in {"SecondaryBody", "SingleLineTitle"}:
        props.pop("fontColor", None)
    for key in ("width", "height", "layoutWeight", "flexShrink"):
        props.pop(key, None)
    font_size = props.pop("fontSize", 12)
    if not isinstance(font_size, (int, float)) or font_size not in (12, 11, 10):
        _fail("静态字号只允许12、11、10，最小为10。")
    builder = _Builder(component, width, palette, int(font_size))
    try:
        if component.component_type == "SingleLineTitle":
            builder.header(props)
        elif component.component_type == "ContentBlock":
            builder.block(props)
        elif component.component_type == "RecordList":
            builder.records(props)
        elif component.component_type == "ComparisonGroup":
            builder.comparison(props, size)
        else:
            builder.support(props)
    except ValueError as exc:
        _fail(f"COMPACT_STATIC_TEXT_CAPACITY: {component.component_id}: {exc}")
    root_id = component.component_id
    roots = []
    others = []
    for row in builder.rows:
        if row.component_id == root_id:
            roots.append(row)
        else:
            others.append(row)
    return roots + others
