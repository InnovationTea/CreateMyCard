"""静态语义组件的受控展开；布局与文字规格统一读取增量合同。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
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

_COMPLETE_TEXT_TRIAL: ContextVar[bool] = ContextVar("complete_static_text_trial", default=False)


@contextmanager
def complete_static_text_trial(enabled: bool = True):
    """新增恢复候选须全文容纳；不改变正常组件规格和省略号样式。"""
    token = _COMPLETE_TEXT_TRIAL.set(enabled)
    try:
        yield
    finally:
        _COMPLETE_TEXT_TRIAL.reset(token)


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
        "EmphasisText": {"mainText", "secondaryText", "bottomText"},
    }
    fields = allowed.get(component.component_type)
    if fields is None:
        _fail(f"静态内容不支持 {component.component_type}。")
    _fields(component.props, fields, component.component_id)


def _fields(value: Any, allowed: set[str], location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed:
        _fail(f"{location} 只允许字段 {sorted(allowed)}。")
    return value


def _color_alpha(color: str, opacity: float = 0.6) -> str:
    if is_role(color):
        return alpha_role(color, opacity)
    if len(color) == 9 and color.startswith("#"):
        return f"#{round(opacity * 255):02X}" + color[3:]
    _fail("静态组件缺少合法主题文字色。")
    return color


class _Builder:
    def __init__(
        self, component: Any, width: float, palette: dict[str, str], font_size: int = 12,
        available_height: float | None = None,
    ) -> None:
        self.component = component
        self.font_size = font_size
        self.width = width
        self.available_height = available_height
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
        self,
        suffix: str,
        value: Any,
        width: float,
        style: str,
        *,
        secondary: bool = False,
        overflow: str | None = None,
        max_lines: int | None = None,
    ) -> tuple[str, float]:
        identifier = self.identifier(suffix)
        content = static_string(value, f"{self.component.component_id}.{suffix}")
        spec = self.spec(style)
        text_overflow = overflow or spec.get("textOverflow")
        line_height = number(spec, "lineHeight")
        props = {
            "fontSize": number(spec, "fontSize"),
            "fontWeight": int(number(spec, "fontWeight")),
            "lineHeight": line_height / number(spec, "fontSize"),
            "maxLines": 1,
            "height": line_height,
            "width": "matchParent",
            "flexShrink": 0,
            "wordBreak": "normal",
            "fontColor": self.secondary if secondary else self.ink,
            "_visualRecipe": f"static-content-v1:{self.component.component_type}.{suffix}",
        }
        if text_overflow == "ellipsis":
            line_limit = max_lines or int(number(spec, "maxLines"))
            if _COMPLETE_TEXT_TRIAL.get():
                require_static_text_capacity(
                    content, width, {**spec, "maxLines": line_limit},
                    f"{self.component.component_id}.{suffix}",
                )
            try:
                visible_lines = min(measure_text(content, width, spec).lines, line_limit)
            except ValueError:
                visible_lines = line_limit
            props.update({
                "textOverflow": text_overflow,
                "flexShrink": 1,
                "constraintSize": {"minWidth": 0},
                "maxLines": line_limit,
                "height": line_height * visible_lines,
            })
            self.add(identifier, "Text", {**props, "content": content}, [])
            return identifier, line_height * visible_lines
        capacity = require_static_text_capacity(
            content,
            width,
            spec,
            f"{self.component.component_id}.{suffix}",
        )
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
        values = _fields(props, {"mainText", "secondaryText", "bottomText"}, "EmphasisText")
        main_id, height = self.text("mainText", values.get("mainText"), self.width, "emphasis")
        children = [main_id]
        spec = component_spec("EmphasisText")
        gap = number(spec, "gap")
        supports = []
        for key in ("secondaryText", "bottomText"):
            value = values.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            supports.append((key, static_string(value, f"EmphasisText.{key}")))
        if len(supports) == 2:
            key, value = supports.pop(0)
            secondary_id, secondary_height = self.text(
                key, value, self.width, "emphasisSecondary", secondary=True,
            )
            children.append(secondary_id)
            height += gap + secondary_height
        top_id = self.identifier("top")
        self.column(top_id, children, height, gap)
        body_children = [top_id]
        location = f"mainText上部{height:g}vp"
        if supports:
            key, value = supports.pop()
            bottom_id, bottom_height = self.text(
                key, value, self.width, "emphasisSecondary", secondary=True,
            )
            minimum_gap = number(spec, "minimumSupportGap")
            for row in self.rows:
                if row.component_id == top_id:
                    row.props.pop("height", None)
                    row.props.update(
                        layoutWeight=1, constraintSize={"minHeight": height + minimum_gap},
                        padding={"bottom": minimum_gap},
                    )
            body_children.append(bottom_id)
            location = (
                f"mainText/secondaryText上部{height:g}vp + "
                f"{self.component.component_id}.{key}底部{bottom_height:g}vp + "
                f"间隔{minimum_gap:g}vp"
            )
            height += minimum_gap + bottom_height
        self._fill_body(body_children, height, 0.0, location)

    def _fill_body(self, children: list[str], minimum: float, gap: float, location: str) -> None:
        available = self.available_height
        if available is None:
            _fail(f"COMPACT_STATIC_TEXT_CAPACITY: {location} 缺少可用内容区高度。")
        if minimum > available:
            _fail(
                f"COMPACT_STATIC_TEXT_CAPACITY: {self.component.component_id} {location}"
                f"至少需要{minimum:g}vp，可用{available:g}vp；保持文字与字号，改用合法承载组件。"
            )
        self.column(self.component.component_id, children, minimum, gap, extra={
            "height": "matchParent", "layoutWeight": 1,
            "constraintSize": {"minHeight": minimum},
        })

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
            badge_gap = number(spec, "badgeGap")
            badge_style = self.spec("listBadge")
            badge_width = text_width(str(index + 1), number(badge_style, "fontSize"))
            badge_width += number(spec, "badgePadding") * 2
            main_width = self.width - value_width - side_gap - badge_width - badge_gap
            if main_width <= 0:
                _fail("TextList.value 占满正文宽度，无法为主副文本保留空间。")
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
                        extra={"layoutWeight": 1, "constraintSize": {"minWidth": 0},
                               "flexShrink": 1})
            badge_id, _badge_height = self.text(
                f"item{index}_badge", str(index + 1), badge_width, "listBadge",
            )
            badge_color = _color_alpha(self.ink, number(spec, "badgeAlpha"))
            self.rows[-1].props.update(
                width=badge_width, textAlign="center", backgroundColor=badge_color,
                borderRadius=number(spec, "badgeRadius"),
            )
            text_children = [main_id]
            if "value" in item:
                value_id, value_height = self.text(
                    f"item{index}_value", value, value_width, "listValue", secondary=True,
                )
                self.rows[-1].props.update(width=value_width, textAlign="end")
                text_children.append(value_id)
                main_height = max(main_height, value_height)
            text_id = self.identifier(f"item{index}_text")
            self.add(text_id, "Row", {
                "width": "matchParent", "height": main_height, "layoutWeight": 1,
                "itemMargin": side_gap, "alignItems": "center", "flexShrink": 0,
                "constraintSize": {"minWidth": 0},
            }, text_children)
            row_id = self.identifier(f"item{index}")
            self.add(row_id, "Row", {
                "width": "matchParent", "height": main_height, "itemMargin": badge_gap,
                "alignItems": "center", "flexShrink": 0,
            }, [badge_id, text_id])
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
        if not isinstance(items, list) or not 1 <= len(items) <= 5:
            _fail("SingleLineList.items 必须为1–5项；静态正文最多五条信息，标题不计入。")
        spec = component_spec("SingleLineList")
        gap = number(spec, "gap")
        side_gap = number(spec, "sideGap")
        panels = len(items) <= 3
        padding = number(spec, "panelPadding") if panels else 0.0
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
            assist_width = self.width - extent - side_gap - padding * 2
            if assist_width <= 0:
                _fail(
                    f"COMPACT_STATIC_TEXT_CAPACITY: {self.component.component_id}.item{index}_text "
                    f"占用{extent:g}vp，扣除背板内边距与间距后item{index}_assist无可用宽度；"
                    "保持完整标签和值，换用能分层承载的合法组件。"
                )
            text_id, text_height = self.text(
                f"item{index}_text", text, extent, "singleText", secondary=True,
            )
            self.rows[-1].props["width"] = extent
            assist_id, assist_height = self.text(
                f"item{index}_assist", assist, assist_width,
                "singlePanelAssist" if panels else "singleAssist",
            )
            self.rows[-1].props.update(layoutWeight=1, textAlign="end")
            row_id = self.identifier(f"item{index}")
            height = max(text_height, assist_height)
            styles = {
                "width": "matchParent", "height": height, "itemMargin": side_gap,
                "alignItems": "center", "flexShrink": 0,
            }
            if panels:
                height = number(spec, "panelHeight")
                styles.update(height=height, padding={"left": padding, "right": padding},
                              borderRadius=number(spec, "panelRadius"), backgroundColor=self.panel)
            self.add(row_id, "Row", styles, [text_id, assist_id])
            children.append(row_id)
            heights.append(height)
        minimum = sum(heights) + gap * (len(items) - 1)
        if panels and len(items) == 3:
            self._fill_body(children, minimum, gap, "三项单行背板")
            self.rows[-1].props["justifyContent"] = "spaceBetween"
        else:
            self.column(self.component.component_id, children, minimum, gap)

    def comparison(self, props: dict[str, Any], size: str) -> None:
        values = _fields(props, {"items"}, "ComparisonGroup")
        items = values.get("items")
        spec = component_spec("ComparisonGroup")
        if size != "2x4" or not isinstance(items, list):
            _fail("ComparisonGroup 仅支持 2x4 的静态对象数组。")
        if not number(spec, "minimumItems") <= len(items) <= number(spec, "maximumItems"):
            _fail("ComparisonGroup 仅支持 2x4 的 2–4 个等权对象。")
        four_item_grid = len(items) == 4
        gap_name = "fourItemGap" if four_item_grid else "gap"
        inner_gap_name = "fourItemInnerGap" if four_item_grid else "innerGap"
        gap = number(spec, gap_name)
        padding = number(spec, "padding")
        inner_gap = number(spec, inner_gap_name)
        column_count = 2 if four_item_grid else len(items)
        column_width = (self.width - gap * (column_count - 1)) / column_count
        text_area = column_width - padding * 2
        text_overflow = spec.get("fourItemTextOverflow") if four_item_grid else None
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
                    overflow=text_overflow,
                    max_lines=1 if four_item_grid else None,
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
            if four_item_grid:
                cell_height = number(spec, "fourItemHeight")
                if height > cell_height:
                    _fail(
                        "ComparisonGroup 四项宫格的单格内容超过固定高度；"
                        "请精简每项文字或减少辅助字段。"
                    )
                height = cell_height
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
                    "justifyContent": "center" if four_item_grid else "start",
                },
            )
            children.append(column_id)
            heights.append(height)
        if four_item_grid:
            row_ids = []
            row_height = number(spec, "fourItemHeight")
            for row_index in range(2):
                row_id = self.identifier(f"row{row_index}")
                start = row_index * 2
                self.add(
                    row_id,
                    "Row",
                    {
                        "width": "matchParent",
                        "height": row_height,
                        "itemMargin": gap,
                        "alignItems": "start",
                        "flexShrink": 0,
                    },
                    children[start:start + 2],
                )
                row_ids.append(row_id)
            self.column(
                self.component.component_id,
                row_ids,
                row_height * 2 + gap,
                gap,
            )
            return
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
    component: Any, size: str, *, width: float, palette: dict[str, str],
    available_height: float | None = None,
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
    builder = _Builder(component, width, palette, available_height=available_height)
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
