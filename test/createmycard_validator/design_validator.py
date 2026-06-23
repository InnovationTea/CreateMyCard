"""Non-deducting design review rules."""

from __future__ import annotations

try:
    from .common import COLOR_RE, Finding, ValidationContext, warning
    from .rule_check import RuleCheckSpec, run_rule_checks
except ImportError:
    from common import COLOR_RE, Finding, ValidationContext, warning  # type: ignore
    from rule_check import RuleCheckSpec, run_rule_checks  # type: ignore


def is_short_static_text(component: dict) -> bool:
    """Return True for fixed short labels that do not need maxLines noise."""
    content = component.get("content")
    if not isinstance(content, str):
        return False
    return len(content) <= 5 and "{{" not in content and "/" not in content


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    root = next((component for component in ctx.components if component.get("id") == "root"), None)
    if isinstance(root, dict):
        styles = root.get("styles") if isinstance(root.get("styles"), dict) else {}
        width = styles.get("width")
        if width not in ("100%", "matchParent", 160, 320, "160", "320", "160vp", "320vp"):
            findings.append(warning("RULE_DESIGN_001", f"root width is unusual for card output: {width!r}"))
        if not any(key in styles for key in ("padding", "space", "itemMargin")) and "itemMargin" not in root:
            findings.append(warning("RULE_DESIGN_002", "root should explicitly set padding and spacing"))
    else:
        return findings

    missing_max_lines: list[str] = []
    for component in ctx.components:
        cid = component.get("id", "<unknown>")
        if component.get("component") == "Text":
            styles = component.get("styles") if isinstance(component.get("styles"), dict) else {}
            if "maxLines" not in styles and not is_short_static_text(component):
                missing_max_lines.append(str(cid))
        if component.get("component") == "Button":
            styles = component.get("styles") if isinstance(component.get("styles"), dict) else {}
            width = styles.get("width")
            height = styles.get("height")
            if not width or not height:
                findings.append(warning("RULE_DESIGN_006", f"Button '{cid}' should set a minimum tap area"))

        styles = component.get("styles") if isinstance(component.get("styles"), dict) else {}
        for key in ("fontSize", "minFontSize", "maxFontSize"):
            value = styles.get(key)
            if isinstance(value, str) and not value.strip().startswith("{{"):
                findings.append(warning("RULE_DESIGN_004", f"{cid}.styles.{key} should be numeric, got string '{value}'"))
        for key, value in styles.items():
            if key.lower().endswith("color") or key in {"fontColor", "backgroundColor", "borderColor", "color"}:
                if isinstance(value, str) and value.startswith("#") and not COLOR_RE.match(value):
                    findings.append(warning("RULE_DESIGN_005", f"{cid}.styles.{key} is not #RRGGBB or #AARRGGBB: {value}"))

    if missing_max_lines:
        preview = ", ".join(missing_max_lines[:20])
        if len(missing_max_lines) > 20:
            preview += f", ... (+{len(missing_max_lines) - 20} more)"
        findings.append(
            warning(
                "RULE_DESIGN_003",
                f"{len(missing_max_lines)} Text components missing maxLines: {preview}",
            )
        )

    # ========== RULE_DESIGN_008: Row 容器对齐方式检查 ==========
    # 先构建 component_id_map
    component_id_map = {str(c.get("id", "")): c for c in ctx.components if c.get("id")}

    # 递归检查是否包含 Progress 或 Image 组件
    def has_progress_or_image(component_id, visited=None):
        if visited is None:
            visited = set()
        if component_id in visited:
            return False
        visited.add(component_id)
        comp = component_id_map.get(component_id)
        if not comp:
            return False
        if comp.get("component") in ("Progress", "Image"):
            return True
        children = comp.get("children", [])
        if isinstance(children, list):
            for child_id in children:
                if isinstance(child_id, str) and has_progress_or_image(child_id, visited):
                    return True
        return False

    for component in ctx.components:
        cid = component.get("id", "<unknown>")
        if component.get("component") == "Row":
            children = component.get("children", [])
            # 递归检查 Row 下是否包含 Progress 或 Image 组件（可能导致高度不一致）
            has_height_varying_children = False
            if isinstance(children, list):
                for child_id in children:
                    if isinstance(child_id, str) and has_progress_or_image(child_id):
                        has_height_varying_children = True
                        break
            # 包含高度变化组件的 Row 应该设置 alignItems: "center"
            if has_height_varying_children:
                alignItems = component.get("alignItems")
                if not alignItems or alignItems != "center":
                    actual = f"当前值: {alignItems}" if alignItems else "未设置"
                    findings.append(warning(
                        "RULE_DESIGN_008",
                        f"Row '{cid}' 包含 Progress/Image 等高度可变组件，{actual}，建议设置 alignItems: 'center' 确保水平对齐"
                    ))

    return findings
