from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator, is_wrapped_expression, static_expression_value, walk_json


class AssetValidator(BaseValidator):
    stage = "hard"
    name = "asset"

    def validate(self, context, rules, reporter) -> None:
        forbidden = [re.compile(pattern, re.I) for pattern in rules.asset.get("forbiddenPatterns", [])]
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            component_type = component.get("component")
            if component_type == "Image":
                self._check_asset_value(
                    component.get("src"),
                    f"/updateComponents/componentsById/{component_id}/src",
                    forbidden,
                    context,
                    rules,
                    reporter,
                    required=True,
                )
            styles = component.get("styles", {})
            if isinstance(styles, dict) and "backgroundImage" in styles:
                self._check_asset_value(
                    styles.get("backgroundImage"),
                    f"/updateComponents/componentsById/{component_id}/styles/backgroundImage",
                    forbidden,
                    context,
                    rules,
                    reporter,
                    required=False,
                )

    def _check_asset_value(self, value: Any, pointer: str, forbidden, context, rules, reporter, required: bool) -> None:
        if not isinstance(value, str):
            if required:
                reporter.add("error", "ASSET_PATH_NOT_DECLARED", "hard", "genui", line=2, json_pointer=pointer, actual=value, message="资源路径必须是字符串或完整表达式。")
            return
        if is_wrapped_expression(value):
            resolved = static_expression_value(value, context.data_model)
            if isinstance(resolved, str):
                self._check_static_path(resolved, pointer, forbidden, context, rules, reporter)
            else:
                reporter.add(
                    "warning",
                    "ASSET_PATH_NOT_DECLARED",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=value,
                    message="表达式形式的资源路径无法在初始 DataModel 中解析为静态路径。",
                    fix_hint="确保该表达式运行时只返回素材库 allowlist 中的资源路径。",
                )
            return
        self._check_static_path(value, pointer, forbidden, context, rules, reporter)

    def _check_static_path(self, path: str, pointer: str, forbidden, context, rules, reporter) -> None:
        for pattern in forbidden:
            if pattern.search(path):
                reporter.add(
                    "error",
                    "ASSET_REMOTE_URL_FORBIDDEN",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=path,
                    message="资源路径禁止网络 URL、data:image 和 base64。",
                    fix_hint="使用素材库声明的本地 resources/base/media/*.svg 或 *.png。",
                )
                return
        # In effective-capability mode the asset allowlist is the filtered
        # effective asset set, checked later by EffectiveCapabilityValidator.
        # Keep static allowlist behavior unchanged for legacy CLI usage.
        if getattr(context, "use_effective_capabilities", False):
            return
        if path not in rules.asset_allowlist:
            reporter.add(
                "error",
                "ASSET_PATH_NOT_DECLARED",
                "hard",
                "genui",
                line=2,
                json_pointer=pointer,
                actual=path,
            )


def collect_asset_paths(value: Any) -> list[str]:
    result = []
    for _, child in walk_json(value):
        if isinstance(child, str) and child.startswith("resources/"):
            result.append(child)
    return result
