"""按受信子模板身份处理组合布局的外层底板例外。"""

from __future__ import annotations

from typing import Any

from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

from .parser import ParsedCall
from .photo_theme import STYLE_MARKER, SURFACE_MARKER

_HERO_PANEL_INDEX_BY_LAYOUT = {
    "WideFullHeroActionLayout": 1,
    "WideHeroActionFullLayout": 0,
}
_SURFACE_EXCEPTION_KEY = "_heroPanelSurfaceExempt"
# 值为去掉布局底板后与 36vp 按钮的间距；兼顾自带底板与需要完整槽位空间的模板。
_HERO_PANEL_SURFACE_EXCEPTIONS = {
    "BatteryOverviewStatusSummaryHero@1": 8,
    "BatteryOverviewStatusLevelSummaryHero@1": 8,
    "BatteryOverviewChargingLevelSummaryHero@1": 8,
    "BatteryOverviewChargingDiagnosticsHero@1": 6,
    "BatteryOverviewTemperatureRingHero@1": 8,
    "BluetoothDeviceOverviewEarbudPairHero@1": 8,
}


def configure_layout_surface(call: ParsedCall, root: Nested2Node) -> Nested2Node:
    """Only actual direct templates can authorize internal surface flags."""
    if root.component_type not in _HERO_PANEL_INDEX_BY_LAYOUT:
        return root
    options = dict(root.values[0]) if root.values else {}
    options.pop(_SURFACE_EXCEPTION_KEY, None)
    if len(call.children) == 3:
        hero = call.children[1]
        if hero.kind == "template" and hero.name in _HERO_PANEL_SURFACE_EXCEPTIONS:
            options[_SURFACE_EXCEPTION_KEY] = hero.name
    return Nested2Node(root.component_type, (options,) if options else (), root.children)


def apply_layout_surface(
    root: Nested2Node, layout_id: str, configuration: dict[str, Any]
) -> Nested2Node:
    """Change only authorized layout-owned surfaces; preserve business trees."""
    panel_index = _HERO_PANEL_INDEX_BY_LAYOUT.get(layout_id)
    if panel_index is None:
        return root
    hero_template_id = configuration.get(_SURFACE_EXCEPTION_KEY)
    if not isinstance(hero_template_id, str):
        return root
    action_gap = _HERO_PANEL_SURFACE_EXCEPTIONS.get(hero_template_id)
    if action_gap is None:
        return root
    if root.component_type != "Row" or len(root.children) != 2:
        raise TerselConversionError(f"{layout_id} surface structure changed.")
    panel = root.children[panel_index]
    if panel.component_type != "Column" or len(panel.children) != 2:
        raise TerselConversionError(f"{layout_id} Hero panel structure changed.")
    if len(panel.values) != 1 or not isinstance(panel.values[0], dict):
        raise TerselConversionError(f"{layout_id} Hero panel styles are missing.")
    options = dict(panel.values[0])
    for key in ("backgroundColor", "borderRadius", "padding"):
        options.pop(key, None)
    options.pop(SURFACE_MARKER, None)
    style_roles = options.get(STYLE_MARKER)
    if isinstance(style_roles, dict):
        remaining_roles = dict(style_roles)
        remaining_roles.pop("backgroundColor", None)
        if remaining_roles:
            options[STYLE_MARKER] = remaining_roles
        else:
            options.pop(STYLE_MARKER, None)
    options["itemMargin"] = action_gap
    children = list(root.children)
    children[panel_index] = Nested2Node(panel.component_type, (options,), panel.children)
    return Nested2Node(root.component_type, root.values, tuple(children))
