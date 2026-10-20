"""阶段边界检查：布局只接受角色，交付不允许残留内部角色。"""

from __future__ import annotations

import json

from services.theme_style_roles import COLOR_FIELDS, is_role


def theme_phase_errors(source: str, *, layout: bool) -> list[str]:
    try:
        records = [json.loads(line) for line in source.splitlines() if line.strip()]
    except (TypeError, ValueError):
        return []  # JSON 协议错误由既有解析器报告。
    errors = []
    for record in records:
        if not isinstance(record, dict):
            continue
        update = record.get("updateComponents")
        if not isinstance(update, dict):
            continue
        nodes = update.get("components")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            styles = node.get("styles", {})
            if not isinstance(styles, dict):
                continue
            for key, value in styles.items():
                location = f"{node.get('id')}.{key}"
                if layout and key in COLOR_FIELDS and not is_role(value):
                    errors.append(f"THEME.LAYOUT_COLOR: {location} must be an internal role")
                if layout and key in {"linearGradient", "backgroundImage"}:
                    errors.append(f"THEME.EARLY_BACKGROUND: {location} is not a layout property")
                if not layout and isinstance(value, str) and value.startswith("@theme:"):
                    errors.append(f"THEME.UNRESOLVED_ROLE: {location} cannot be delivered")
    return errors
