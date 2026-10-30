"""移除外层背板后，图片处理不得复活其样式归属。"""

from copy import deepcopy

import pytest

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.layout_surface_policy import (
    apply_layout_surface,
    configure_layout_surface,
)
from services.template_generation.engine.cardplan.models import SourceSpan
from services.template_generation.engine.cardplan.parser import ParsedCall
from services.template_generation.engine.cardplan.photo_theme import (
    STYLE_MARKER,
    SURFACE_MARKER,
    collect_photo_style_context,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.theme_photo_processing import apply_content_palette

_HERO_IDS = (
    "BatteryOverviewStatusSummaryHero@1",
    "BatteryOverviewStatusLevelSummaryHero@1",
    "BatteryOverviewChargingLevelSummaryHero@1",
    "BatteryOverviewChargingDiagnosticsHero@1",
    "BatteryOverviewTemperatureRingHero@1",
    "BluetoothDeviceOverviewEarbudPairHero@1",
)


def _layout(layout_id: str, hero: str) -> tuple[Nested2Node, Nested2Node]:
    span = SourceSpan(start=0, end=1)
    names = (
        "CountdownOverviewTargetDetailFull@1", hero, "PillAction@1",
    )
    calls = tuple(ParsedCall("template", name, ({},), (), span) for name in names)
    call = ParsedCall("template", layout_id + "@1", ({},), calls, span)
    config = configure_layout_surface(call, Nested2Node(layout_id, ({},), ()))
    # 子树自带背板，用于确认只移除布局外层，不删除内部与按钮的主题归属。
    child = Nested2Node("Column", ({"backgroundColor": "#FFFFFFFF",
                                    STYLE_MARKER: {"backgroundColor": "@theme:panel/1"},
                                    SURFACE_MARKER: True},), ())
    blueprint = get_cardplan_registry().require_template(layout_id + "@1").variants[0].root
    original = _instantiate_blueprint(
        blueprint, {}, theme_values={"supportContentStyle.backgroundColor": "#FFFFFFFF",
                                     "supportContentStyle.borderRadius": 16},
        spread_children=(child, child, child),
    )
    before = deepcopy(original)
    configuration = config.values[0] if config.values else {}
    configured = apply_layout_surface(original, layout_id, configuration)
    assert original == before
    return original, configured


@pytest.mark.parametrize("hero", _HERO_IDS)
@pytest.mark.parametrize(("layout", "index"), [
    ("WideFullHeroActionLayout", 1), ("WideHeroActionFullLayout", 0),
])
def test_exempt_panel_stays_absent_after_photo_processing(hero, layout, index):
    original, result = _layout(layout, hero)
    before = deepcopy(original)
    other = 1 - index
    assert result.children[other] == original.children[other]
    assert result.children[index].children == original.children[index].children
    shell = Nested2Node("Stack", ({},), (result,))
    context = collect_photo_style_context(shell)
    panel_id = f"root_1_{index}"
    assert panel_id not in context.surfaces
    assert "backgroundColor" not in context.roles.get(panel_id, {})
    # 业务内部和按钮仍有背板，避免以删除所有主题信息掩盖问题。
    assert len(context.surfaces) >= 3
    options = dict(result.children[index].values[0])
    node = {"id": panel_id, "component": "Column", "styles": options}
    apply_content_palette([node], {}, "#33FFFFFF", surface_style={"backdropBlur": {"radius": 20}},
                          legacy_panels=[], ownership=context)
    assert "backgroundColor" not in options
    assert "backdropBlur" not in options
    assert "borderRadius" not in options
    assert "padding" not in options
    assert options.get("itemMargin") == (6 if "Diagnostics" in hero else 8)
    assert original == before


@pytest.mark.parametrize("layout", ["WideFullHeroActionLayout", "WideHeroActionFullLayout"])
def test_regular_hero_retains_rounded_outer_panel(layout):
    original, result = _layout(layout, "HeartRateOverviewHero@1")
    assert result == original
    index = 1 if layout == "WideFullHeroActionLayout" else 0
    context = collect_photo_style_context(Nested2Node("Stack", ({},), (result,)))
    assert f"root_1_{index}" in context.surfaces
    assert result.children[index].values[0].get("borderRadius") == 16


def test_removing_surface_preserves_other_theme_roles_and_source():
    layout = "WideFullHeroActionLayout"
    hero = "BatteryOverviewTemperatureRingHero@1"
    original, _ = _layout(layout, hero)
    options = original.children[1].values[0]
    roles = options.get(STYLE_MARKER)
    assert isinstance(roles, dict)
    roles["fontColor"] = "@theme:secondary/1"
    options["fontColor"] = "#CCFFFFFF"
    before = deepcopy(original)
    result = apply_layout_surface(original, layout, {"_heroPanelSurfaceExempt": hero})
    context = collect_photo_style_context(Nested2Node("Stack", ({},), (result,)))
    assert context.roles.get("root_1_1") == {"fontColor": "@theme:secondary/1"}
    assert "root_1_1" not in context.surfaces
    assert original == before
