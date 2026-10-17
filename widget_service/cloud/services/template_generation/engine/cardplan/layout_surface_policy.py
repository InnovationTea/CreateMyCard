"""按受信子模板身份处理组合布局的外层底板例外。"""

from __future__ import annotations

from typing import Any

from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

from .parser import ParsedCall

_LAYOUT_ID = "WideFullHeroActionLayout"
_SURFACE_EXCEPTION_KEY = "_rightPanelSurfaceExempt"
# 值为去掉布局底板后与 36vp 按钮的间距，保留业务面板原始内容高度。
_RIGHT_PANEL_SURFACE_EXCEPTIONS = {
    "BatteryOverviewStatusSummaryHero@1": 8,
    "BatteryOverviewStatusLevelSummaryHero@1": 8,
    "BatteryOverviewChargingLevelSummaryHero@1": 8,
    "BatteryOverviewChargingDiagnosticsHero@1": 6,
}


def configure_layout_surface(call: ParsedCall, root: Nested2Node) -> Nested2Node:
    """Only the actual direct Hero template can authorize the internal flag."""
    if root.component_type != _LAYOUT_ID:
        return root
    options = dict(root.values[0]) if root.values else {}
    options.pop(_SURFACE_EXCEPTION_KEY, None)
    if len(call.children) == 3:
        hero = call.children[1]
        if hero.kind == "template" and hero.name in _RIGHT_PANEL_SURFACE_EXCEPTIONS:
            options[_SURFACE_EXCEPTION_KEY] = hero.name
    return Nested2Node(root.component_type, (options,) if options else (), root.children)


def apply_layout_surface(
    root: Nested2Node, layout_id: str, configuration: dict[str, Any]
) -> Nested2Node:
    """Remove only the layout-owned surface; preserve the Hero and action trees."""
    if layout_id != _LAYOUT_ID:
        return root
    hero_template_id = configuration.get(_SURFACE_EXCEPTION_KEY)
    if not isinstance(hero_template_id, str):
        return root
    action_gap = _RIGHT_PANEL_SURFACE_EXCEPTIONS.get(hero_template_id)
    if action_gap is None:
        return root
    if root.component_type != "Row" or len(root.children) != 2:
        raise TerselConversionError("WideFullHeroActionLayout surface structure changed.")
    left, right = root.children
    if right.component_type != "Column" or len(right.children) != 2:
        raise TerselConversionError("WideFullHeroActionLayout right panel structure changed.")
    if len(right.values) != 1 or not isinstance(right.values[0], dict):
        raise TerselConversionError("WideFullHeroActionLayout right panel styles are missing.")
    options = dict(right.values[0])
    for key in ("backgroundColor", "borderRadius", "padding"):
        options.pop(key, None)
    options["itemMargin"] = action_gap
    right = Nested2Node(right.component_type, (options,), right.children)
    return Nested2Node(root.component_type, root.values, (left, right))
