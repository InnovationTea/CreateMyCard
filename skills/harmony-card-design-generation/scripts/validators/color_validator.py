from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator, HEX_RE, is_wrapped_expression


class ColorValidator(BaseValidator):
    stage = "quality"
    name = "color"

    COLOR_FIELDS = {
        "backgroundColor",
        "borderColor",
        "fontColor",
        "color",
        "selectedColor",
        "fillColor",
        "strokeColor",
    }

    def validate(self, context, rules, reporter) -> None:
        token_re = re.compile(rules.color.get("tokenNamePattern", r"^(brand|font_|icon_|background_|comp_|multi_color_)"))
        color_values: list[str] = []
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            styles = component.get("styles", {})
            if not isinstance(styles, dict):
                continue
            for key, value in styles.items():
                if key in self.COLOR_FIELDS:
                    self._check_color(value, f"/updateComponents/componentsById/{component_id}/styles/{key}", token_re, rules, reporter)
                    if isinstance(value, str) and HEX_RE.fullmatch(value):
                        color_values.append(value.lower())
                if key == "linearGradient":
                    self._check_gradient(value, f"/updateComponents/componentsById/{component_id}/styles/linearGradient", token_re, rules, reporter, color_values)
        unknown = [value for value in set(color_values) if value not in rules.allowed_color_hex]
        for value in sorted(unknown):
            reporter.add(
                "warning",
                "COLOR_SOURCE_UNKNOWN",
                "quality",
                "genui",
                line=2,
                actual=value,
                message="颜色 hex 未能回溯到 token、多彩色或已声明场景拓展色。",
                fix_hint="优先使用 color-token-values.md 中映射后的 hex，或在 color.json 声明场景拓展色。",
            )

    def _check_color(self, value: Any, pointer: str, token_re, rules, reporter) -> None:
        if not isinstance(value, str):
            return
        if is_wrapped_expression(value):
            return
        if token_re.search(value):
            reporter.add(
                "error",
                "COLOR_TOKEN_NAME_OUTPUT",
                "quality",
                "genui",
                line=2,
                json_pointer=pointer,
                actual=value,
                message="DSL 颜色字段不能直接输出 token 名称。",
                fix_hint="把 token 映射为最终 #RRGGBB 或 #AARRGGBB hex。",
            )
            return
        if not HEX_RE.fullmatch(value):
            reporter.add(
                "error",
                "COLOR_FORMAT_INVALID",
                "quality",
                "genui",
                line=2,
                json_pointer=pointer,
                actual=value,
                expected="#RRGGBB 或 #AARRGGBB",
                message="颜色值格式非法。",
            )

    def _check_gradient(self, value: Any, pointer: str, token_re, rules, reporter, color_values: list[str]) -> None:
        if not isinstance(value, dict):
            reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=pointer, actual=value, message="linearGradient 必须是 object。")
            return
        if "direction" not in value:
            reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=pointer + "/direction", message="linearGradient.direction 是必填字段。")
        stops = value.get("colors")
        if not isinstance(stops, list) or not stops:
            reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=pointer + "/colors", actual=stops, message="linearGradient.colors 必须是非空 stop 数组。")
            return
        for index, stop in enumerate(stops):
            if not (isinstance(stop, list) and len(stop) == 2):
                reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=f"{pointer}/colors/{index}", actual=stop, message="每个 gradient stop 必须是 [color, offset]。")
                continue
            color, offset = stop
            self._check_color(color, f"{pointer}/colors/{index}/0", token_re, rules, reporter)
            if isinstance(color, str) and HEX_RE.fullmatch(color):
                color_values.append(color.lower())
            if not isinstance(offset, (int, float)) or not 0 <= offset <= 1:
                reporter.add("error", "STYLE_GRADIENT_INVALID", "quality", "genui", line=2, json_pointer=f"{pointer}/colors/{index}/1", actual=offset, message="gradient stop offset 必须是 0 到 1 的数字。")
