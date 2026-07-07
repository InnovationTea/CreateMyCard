from __future__ import annotations

from typing import Any

from .base import BaseValidator, estimate_text_width, expression_like, is_match_parent, numeric, read_pointer, resolve_dimension, spacing_tuple, static_expression_value


class QualityValidator(BaseValidator):
    stage = "quality"
    name = "quality"

    def validate(self, context, rules, reporter) -> None:
        if not context.dsl_messages:
            return
        penalties = 0
        penalties += self._check_root(context, rules, reporter)
        penalties += self._check_component_styles(context, rules, reporter)
        penalties += self._check_layout_budget(context, rules, reporter)
        penalties += self._check_static_text_fit(context, rules, reporter)
        score = max(0, 100 - penalties - reporter.error_count * 8 - reporter.warning_count * 2)
        context.quality_score = score
        reporter.set_quality(score)

    def _check_root(self, context, rules, reporter) -> int:
        penalties = 0
        root = context.root_component
        size = context.cardspec.get("suggestSize")
        if size not in rules.protocol.get("sizes", {}):
            width = context.create_surface.get("width")
            height = context.create_surface.get("height")
            for candidate, spec in rules.protocol.get("sizes", {}).items():
                if width == spec.get("width") and height == spec.get("height"):
                    size = candidate
                    break
        if not isinstance(root, dict) or size not in rules.protocol.get("sizes", {}):
            return 10
        expected = rules.protocol["sizes"][size]
        styles = root.get("styles", {})
        if not isinstance(styles, dict):
            reporter.add("error", "LAYOUT_ROOT_SIZE_MISSING", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{context.root_id}/styles", message="root.styles 必须是 object。")
            return 20
        root_width = resolve_dimension(styles.get("width"), expected["width"])
        root_height = resolve_dimension(styles.get("height"), expected["height"])
        if root_width != expected["width"] or root_height != expected["height"]:
            penalties += 8
            reporter.add(
                "error",
                "LAYOUT_ROOT_SIZE_MISSING",
                "quality",
                "genui",
                line=2,
                json_pointer=f"/updateComponents/componentsById/{context.root_id}/styles",
                actual={"width": styles.get("width"), "height": styles.get("height")},
                expected={"width": expected["width"], "height": expected["height"], "outerFill": "matchParent"},
                message="root 必须声明与尺寸一致的 width/height；外层可使用 matchParent，校验按基准尺寸解析。",
            )
        if numeric(styles.get("borderRadius")) != expected["borderRadius"] or styles.get("clip") is not True:
            penalties += 5
            reporter.add("error", "LAYOUT_ROOT_SIZE_MISSING", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{context.root_id}/styles", actual={"borderRadius": styles.get("borderRadius"), "clip": styles.get("clip")}, expected={"borderRadius": expected["borderRadius"], "clip": True}, message="root 圆角和 clip 必须与尺寸规范一致。")
        if not self._has_background(root, context, rules, expected):
            penalties += 10
            reporter.add("error", "LAYOUT_ROOT_BACKGROUND_MISSING", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{context.root_id}/styles", message="root 或 root 下真实背景组件必须提供背景样式。", fix_hint="在 root.styles 写 backgroundColor、linearGradient 或 backgroundImage。")
        expected_padding = rules.layout.get("defaultPadding", 12)
        if spacing_tuple(styles.get("padding")) != (expected_padding, expected_padding, expected_padding, expected_padding):
            penalties += 2
            reporter.add("warning", "LAYOUT_SPACING_NOT_ALLOWED", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{context.root_id}/styles/padding", actual=styles.get("padding"), expected=expected_padding, message="root padding 建议使用默认安全区。")
        return penalties

    def _has_background(self, root: dict[str, Any], context, rules, expected: dict[str, Any] | None = None) -> bool:
        styles = root.get("styles", {})
        bg_keys = set(rules.style.get("rootBackgroundStyles", []))
        if isinstance(styles, dict) and bg_keys & set(styles.keys()):
            return True
        children = root.get("children")
        if not isinstance(children, list):
            return False
        expected = expected or {}
        root_width = resolve_dimension(styles.get("width"), expected.get("width"))
        root_height = resolve_dimension(styles.get("height"), expected.get("height"))
        for child_id in children:
            child = context.components_by_id.get(child_id)
            child_styles = child.get("styles", {}) if isinstance(child, dict) else {}
            if not isinstance(child_styles, dict) or not (bg_keys & set(child_styles.keys())):
                continue
            child_width = numeric(child_styles.get("width"))
            child_height = numeric(child_styles.get("height"))
            if (
                root_width is not None
                and root_height is not None
                and child_width is not None
                and child_height is not None
                and child_width >= root_width
                and child_height >= root_height
            ):
                return True
        return False

    def _check_component_styles(self, context, rules, reporter) -> int:
        penalties = 0
        allowed_font_sizes = set(rules.layout.get("allowedFontSizes", []))
        allowed_spacing = set(rules.layout.get("allowedSpacing", []))
        enum_values = rules.style.get("enumValues", {})
        common_styles = set(rules.style.get("commonStyleFields", []))
        component_styles = rules.style.get("componentStyleFields", {})
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            component_type = component.get("component")
            styles = component.get("styles", {})
            if not isinstance(styles, dict):
                continue
            allowed = common_styles | set(component_styles.get(component_type, []))
            extra = sorted(set(styles.keys()) - allowed)
            if extra:
                penalties += 2
                reporter.add("warning", "DSL_FIELD_FORBIDDEN", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles", actual=extra, message="styles 中存在组件目录未声明的字段。")
            for field in ("width", "height"):
                if component_id != context.root_id and is_match_parent(styles.get(field)):
                    penalties += 8
                    reporter.add(
                        "error",
                        "LAYOUT_MATCH_PARENT_SCOPE_INVALID",
                        "quality",
                        "genui",
                        line=2,
                        json_pointer=f"/updateComponents/componentsById/{component_id}/styles/{field}",
                        actual=styles.get(field),
                        expected="仅 createSurface 和 root.styles 的 width/height 可使用 matchParent",
                        message="matchParent 只允许用于外围卡片大小；内部组件必须保持可静态预算的数值宽高。",
                    )
            font_size = numeric(styles.get("fontSize"))
            if font_size is not None and int(font_size) not in allowed_font_sizes:
                penalties += 4
                reporter.add("error", "LAYOUT_FONT_SIZE_NOT_ALLOWED", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles/fontSize", actual=font_size, expected=sorted(allowed_font_sizes), message="fontSize 不在允许字号阶梯中。")
            for field in ("padding", "margin"):
                for item in spacing_tuple(styles.get(field)):
                    if item not in allowed_spacing:
                        penalties += 1
                        reporter.add("warning", "LAYOUT_SPACING_NOT_ALLOWED", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles/{field}", actual=styles.get(field), expected=sorted(allowed_spacing), message="间距值不在允许尺度中。")
                        break
            for field in ("itemMargin", "space"):
                value = numeric(component.get(field))
                if value is not None and value not in allowed_spacing:
                    penalties += 1
                    reporter.add("warning", "LAYOUT_SPACING_NOT_ALLOWED", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/{field}", actual=value, expected=sorted(allowed_spacing), message="间距值不在允许尺度中。")
            self._check_enums(component, styles, enum_values, reporter)
            if component_type == "Image":
                missing = [field for field in rules.style.get("imageRequiredStyles", []) if field not in styles]
                if missing:
                    penalties += 8
                    reporter.add("error", "STYLE_IMAGE_SIZE_MISSING", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles", actual=styles, expected=rules.style.get("imageRequiredStyles", []), message="Image 必须声明 width、height 和 objectFit。")
                elif styles.get("objectFit") != rules.style.get("imageDefaultObjectFit", "contain"):
                    penalties += 1
                    reporter.add("warning", "STYLE_IMAGE_SIZE_MISSING", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles/objectFit", actual=styles.get("objectFit"), expected=rules.style.get("imageDefaultObjectFit", "contain"), message="素材图标建议使用 objectFit: contain。")
            if component_type == "Button":
                min_size = rules.layout.get("minClickableSize", 24)
                width = numeric(styles.get("width"))
                height = numeric(styles.get("height"))
                if width is not None and width < min_size or height is not None and height < min_size:
                    penalties += 8
                    reporter.add("error", "LAYOUT_BUTTON_TOO_SMALL", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles", actual={"width": styles.get("width"), "height": styles.get("height")}, expected=f">= {min_size}", message="Button 可点击视觉尺寸不能小于最小值。")
            if component_type == "Progress" and styles.get("type") in {"ring", "eclipse", "scaleRing"}:
                if numeric(styles.get("width")) != numeric(styles.get("height")):
                    penalties += 4
                    reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles", message="环形 Progress 必须设置相同 width/height。")
        return penalties

    def _check_enums(self, component, styles, enum_values, reporter) -> None:
        component_id = component.get("id", "<unknown>")
        component_type = component.get("component")
        for field, value in list(styles.items()) + [(key, component.get(key)) for key in ("wrap",)]:
            if expression_like(value) or value is None:
                continue
            enum_key = f"{component_type}.{field}"
            allowed = enum_values.get(enum_key) or enum_values.get(field)
            if allowed and value not in allowed:
                reporter.add("error", "DSL_FIELD_FORBIDDEN", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles/{field}", actual=value, expected=allowed, message="枚举值不在允许列表中。")

    def _check_layout_budget(self, context, rules, reporter) -> int:
        penalties = 0
        for component in context.components:
            component_type = component.get("component")
            if component_type not in {"Row", "Column"}:
                continue
            component_id = component.get("id", "<unknown>")
            children = component.get("children")
            styles = component.get("styles", {})
            if not isinstance(children, list) or not isinstance(styles, dict):
                continue
            child_components = [context.components_by_id[child] for child in children if isinstance(child, str) and child in context.components_by_id]
            pad_top, pad_right, pad_bottom, pad_left = spacing_tuple(styles.get("padding"))
            gap = numeric(component.get("itemMargin")) or 0
            if component_type == "Row":
                width = self._component_dimension(component_id, styles, "width", context, rules)
                if width is None:
                    continue
                used, unknown = pad_left + pad_right + gap * max(0, len(child_components) - 1), False
                for child in child_components:
                    child_styles = child.get("styles", {})
                    _, margin_right, _, margin_left = spacing_tuple(child_styles.get("margin") if isinstance(child_styles, dict) else None)
                    child_width = numeric(child_styles.get("width")) if isinstance(child_styles, dict) else None
                    used += margin_left + margin_right
                    if child_width is None:
                        unknown = True
                    else:
                        used += child_width
                if not unknown and used > width:
                    penalties += 8
                    reporter.add("error", "LAYOUT_ROW_OVERFLOW", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}", actual=used, expected=f"<= {width}", message="Row 横向预算超出父容器宽度。")
            if component_type == "Column":
                height = self._component_dimension(component_id, styles, "height", context, rules)
                if height is None:
                    continue
                used, unknown = pad_top + pad_bottom + gap * max(0, len(child_components) - 1), False
                for child in child_components:
                    child_styles = child.get("styles", {})
                    margin_top, _, margin_bottom, _ = spacing_tuple(child_styles.get("margin") if isinstance(child_styles, dict) else None)
                    child_height = numeric(child_styles.get("height")) if isinstance(child_styles, dict) else None
                    used += margin_top + margin_bottom
                    if child_height is None:
                        unknown = True
                    else:
                        used += child_height
                if not unknown and used > height:
                    penalties += 8
                    reporter.add("error", "LAYOUT_COLUMN_OVERFLOW", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}", actual=used, expected=f"<= {height}", message="Column 纵向预算超出父容器高度。")
        return penalties

    def _component_dimension(self, component_id: str, styles: dict[str, Any], field: str, context, rules) -> float | None:
        parent_size = None
        if component_id == context.root_id:
            size = context.cardspec.get("suggestSize")
            expected = rules.protocol.get("sizes", {}).get(size)
            if isinstance(expected, dict):
                parent_size = expected.get(field)
        return resolve_dimension(styles.get(field), parent_size)

    def _check_static_text_fit(self, context, rules, reporter) -> int:
        penalties = 0
        for component in context.components:
            component_type = component.get("component")
            if component_type not in {"Text", "Button"}:
                continue
            component_id = component.get("id", "<unknown>")
            styles = component.get("styles", {})
            if not isinstance(styles, dict):
                continue
            value = component.get("content") if component_type == "Text" else component.get("label")
            text = None
            if isinstance(value, str) and not expression_like(value):
                text = value
            elif isinstance(value, str):
                resolved = static_expression_value(value, context.data_model)
                text = resolved if isinstance(resolved, str) else None
            if not text:
                continue
            width = numeric(styles.get("width"))
            font = numeric(styles.get("fontSize")) or 14
            max_lines = int(numeric(styles.get("maxLines")) or 1)
            if width is not None:
                required = estimate_text_width(text, font)
                if component_type == "Button":
                    required += 16
                if required > width * max_lines:
                    penalties += 4
                    reporter.add("warning", "QUALITY_SCORE_LOW", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}", actual=text, message="静态文本估算可能放不下当前宽度。", fix_hint="增加宽度、改为两行并预留高度，或缩短非受保护文案。")
            if styles.get("textOverflow") in set(rules.layout.get("protectedTextOverflow", [])):
                penalties += 5
                reporter.add("error", "QUALITY_SCORE_LOW", "quality", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/styles/textOverflow", actual=styles.get("textOverflow"), message="受保护文本不应依赖 ellipsis/clip/marquee。")
        return penalties
