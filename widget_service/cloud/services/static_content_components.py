"""静态语义组件的受控展开；布局与文字规格统一读取增量合同。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.card_validation.compact_validation.semantic.layout.text_capacity import (
    require_static_text_capacity,
)
from services.generation_content_policy import STATIC_COMPONENTS, current_content_policy
from services.static_text_capacity import (
    component_spec,
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


def validate_static_model_props(component: Any) -> None:
    """在主题注入前验证模型字段，避免把样式错误静默当作Runtime默认值。"""
    allowed = {
        "SingleLineTitle": {"title", "icon"},
        "TextList": {"items"},
        "SingleLineList": {"items"},
        "ComparisonGroup": {"items"},
        "EmphasisText": {"mainText", "secondaryText"},
    }
    fields = allowed.get(component.component_type)
    if fields is None:
        _fail(f"静态内容不支持 {component.component_type}。")
    _fields(component.props, fields, component.component_id)


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

    def emphasis(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"mainText", "secondaryText"}, "EmphasisText")
        main_id, height = self.text("mainText", values.get("mainText"), self.width, "emphasis")
        children = [main_id]
        gap = number(component_spec("EmphasisText"), "gap")
        if "secondaryText" in values:
            secondary_id, secondary_height = self.text(
                "secondaryText", values.get("secondaryText"), self.width,
                "emphasisSecondary", secondary=True,
            )
            children.append(secondary_id)
            height += gap + secondary_height
        self.column(self.component.component_id, children, height, gap)

    def text_list(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"items"}, "TextList")
        items = values.get("items")
        if not isinstance(items, list) or not 2 <= len(items) <= 3:
            _fail("TextList.items 必须为2–3项；含标题时最多2项。")
        spec = component_spec("TextList")
        gap = number(spec, "threeItemGap" if len(items) == 3 else "twoItemGap")
        inner_gap = number(spec, "innerGap")
        children = []
        heights = []
        for index, raw in enumerate(items):
            item = _fields(raw, {"primaryText", "secondaryText", "value"}, "列表项")
            value_width = 0.0
            side_gap = 0.0
            if "value" in item:
                value = item.get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    value = str(value)
                value = static_string(value, f"items[{index}].value")
                value_width = text_width(value, number(self.spec("listValue"), "fontSize"))
                side_gap = number(spec, "sideGap")
            main_width = self.width - value_width - side_gap
            primary, primary_height = self.text(
                f"item{index}_primaryText", item.get("primaryText"), main_width, "listPrimary",
            )
            secondary, secondary_height = self.text(
                f"item{index}_secondaryText", item.get("secondaryText"), main_width,
                "listSecondary", secondary=True,
            )
            main_id = self.identifier(f"item{index}_main")
            main_height = primary_height + inner_gap + secondary_height
            self.column(main_id, [primary, secondary], main_height, inner_gap,
                        extra={"layoutWeight": 1})
            row_children = [main_id]
            if "value" in item:
                value_id, value_height = self.text(
                    f"item{index}_value", value, value_width, "listValue", secondary=True,
                )
                self.rows[-1].props.update(width=value_width, textAlign="end")
                row_children.append(value_id)
                main_height = max(main_height, value_height)
            row_id = self.identifier(f"item{index}")
            self.add(row_id, "Row", {
                "width": "matchParent", "height": main_height, "itemMargin": side_gap,
                "alignItems": "center", "flexShrink": 0,
            }, row_children)
            children.append(row_id)
            heights.append(main_height)
            if index < len(items) - 1:
                divider_id = self.identifier(f"divider{index}")
                thickness = number(spec, "dividerWidth")
                if is_role(self.ink):
                    color = alpha_role(self.ink, number(spec, "dividerAlpha"))
                else:
                    color = "#1F" + self.ink[3:]
                self.add(divider_id, "Divider", {
                    "width": "matchParent", "height": thickness, "strokeWidth": thickness,
                    "flexShrink": 0, "color": color,
                }, [])
                children.append(divider_id)
                heights.append(thickness)
        self.column(self.component.component_id, children,
                    sum(heights) + gap * (len(children) - 1), gap)

    def single_lines(self, props: dict[str, Any]) -> None:
        values = _fields(props, {"items"}, "SingleLineList")
        items = values.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 24:
            _fail("SingleLineList.items 必须为非空条目数组，最多24项并须通过容量校验。")
        spec = component_spec("SingleLineList")
        gap = number(spec, "gap")
        side_gap = number(spec, "sideGap")
        children = []
        heights = []
        for index, raw in enumerate(items):
            item = _fields(raw, {"text", "assist"}, "单行条目")
            text = static_string(item.get("text"), f"items[{index}].text")
            assist = item.get("assist")
            if isinstance(assist, (int, float)) and not isinstance(assist, bool):
                assist = str(assist)
            assist = static_string(assist, f"items[{index}].assist")
            extent = text_width(text, number(self.spec("singleText"), "fontSize"))
            text_id, text_height = self.text(
                f"item{index}_text", text, extent, "singleText", secondary=True,
            )
            self.rows[-1].props["width"] = extent
            assist_id, assist_height = self.text(
                f"item{index}_assist", assist, self.width - extent - side_gap, "singleAssist",
            )
            self.rows[-1].props.update(layoutWeight=1, textAlign="end")
            row_id = self.identifier(f"item{index}")
            height = max(text_height, assist_height)
            self.add(row_id, "Row", {
                "width": "matchParent", "height": height, "itemMargin": side_gap,
                "alignItems": "center", "flexShrink": 0,
            }, [text_id, assist_id])
            children.append(row_id)
            heights.append(height)
        self.column(self.component.component_id, children,
                    sum(heights) + gap * (len(items) - 1), gap)

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



def expand_static_component(
    component: Any, size: str, *, width: float, palette: dict[str, str]
) -> list[Any]:
    if not current_content_policy().is_static:
        _fail("静态内容组件需要服务端请求上下文授权。")
    if component.component_type not in STATIC_COMPONENTS | {
        "SingleLineTitle", "EmphasisText",
    }:
        _fail("静态组件未登记。")
    props = deepcopy(component.props)
    if component.component_type in {"SingleLineTitle", "EmphasisText"}:
        props.pop("fontColor", None)
    for key in ("width", "height", "layoutWeight", "flexShrink"):
        props.pop(key, None)
    builder = _Builder(component, width, palette)
    try:
        if component.component_type == "SingleLineTitle":
            builder.header(props)
        elif component.component_type == "EmphasisText":
            builder.emphasis(props)
        elif component.component_type == "TextList":
            builder.text_list(props)
        elif component.component_type == "SingleLineList":
            builder.single_lines(props)
        elif component.component_type == "ComparisonGroup":
            builder.comparison(props, size)
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
