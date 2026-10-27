"""按受信子模板身份处理组合布局的外层底板例外。"""

from __future__ import annotations

import re
from typing import Any

from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

from .calendar_weather_presentation import is_calendar_condition_focus
from .parser import ParsedCall

_HERO_PANEL_INDEX_BY_LAYOUT = {
    "WideFullHeroActionLayout": 1,
    "WideHeroActionFullLayout": 0,
}
_SURFACE_EXCEPTION_KEY = "_heroPanelSurfaceExempt"
_FOCUS_LAYOUT_ID = "WideTwoFocusLayout"
_CALENDAR_CONDITION_SURFACE_KEY = "_calendarConditionFocusSurface"
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
    if root.component_type == _FOCUS_LAYOUT_ID:
        return _configure_calendar_condition_surface(call, root)
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
    if layout_id == _FOCUS_LAYOUT_ID:
        return _apply_calendar_condition_surface(root, configuration)
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
    options["itemMargin"] = action_gap
    children = list(root.children)
    children[panel_index] = Nested2Node(panel.component_type, (options,), panel.children)
    return Nested2Node(root.component_type, root.values, tuple(children))


def _configure_calendar_condition_surface(call: ParsedCall, root: Nested2Node) -> Nested2Node:
    options = dict(root.values[0]) if root.values else {}
    options.pop(_CALENDAR_CONDITION_SURFACE_KEY, None)
    if is_calendar_condition_focus(root, call):
        options[_CALENDAR_CONDITION_SURFACE_KEY] = True
    return Nested2Node(root.component_type, (options,) if options else (), root.children)


def _apply_calendar_condition_surface(
    root: Nested2Node, configuration: dict[str, Any]
) -> Nested2Node:
    if configuration.get(_CALENDAR_CONDITION_SURFACE_KEY) is not True:
        return root
    if root.component_type != "Row" or len(root.children) != 2:
        return root
    children = []
    for panel in root.children:
        if panel.component_type != "Column" or len(panel.values) != 1:
            return root
        if not isinstance(panel.values[0], dict):
            return root
        options = dict(panel.values[0])
        color = options.get("backgroundColor")
        if not isinstance(color, str):
            return root
        matched = re.fullmatch(r"#(?:[0-9a-fA-F]{2})?([0-9a-fA-F]{6})", color)
        if matched is None:
            return root
        # 参考底板约 10% 透明度；RGB 仍来自当前主题，不写死某个主题颜色。
        options.update(backgroundColor="#19" + matched.group(1), borderRadius=12)
        children.append(Nested2Node(panel.component_type, (options,), panel.children))
    options = dict(root.values[0]) if root.values else {}
    options["itemMargin"] = 12
    return Nested2Node(root.component_type, (options,), tuple(children))
