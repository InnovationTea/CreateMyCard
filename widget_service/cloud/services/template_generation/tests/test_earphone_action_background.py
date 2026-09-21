"""耳机按钮背景统一，隔离共享主题中的手机电量。"""

import pytest

from services.template_generation.engine.cardplan.compiler import _provider_layout_action_background
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.registry import get_cardplan_registry


@pytest.mark.parametrize("fusion", [False, True])
def test_all_single_earphone_templates_use_twenty_percent_white(fusion: bool) -> None:
    registry = get_cardplan_registry(fusion)
    theme_id = "fusion-battery-teal" if fusion else "audio-product-neutral-violet"
    theme = registry.require_theme(theme_id)
    assert theme.action_style is not None
    checked = 0
    for record in registry.template_variant_search_records:
        if record.capability_id != "GetEarphoneInfo":
            continue
        contract = HybridBodyContract.model_construct(
            theme_profile_id=theme_id,
            allowed_template_ids=(record.template_id,),
            allowed_business_component_ids=("BluetoothDeviceOverview",),
        )
        background = _provider_layout_action_background(
            contract, registry, foreground=theme.action_style.content_color,
            default=theme.action_style.background_color,
        )
        assert background == "#33FFFFFF", record.template_id
        checked += 1
    assert checked > 0


def test_mixed_business_keeps_theme_background() -> None:
    registry = get_cardplan_registry(True)
    contract = HybridBodyContract.model_construct(
        theme_profile_id="fusion-battery-teal",
        allowed_template_ids=("BluetoothDeviceOverviewHero@1", "BatteryOverviewHero@1"),
        allowed_business_component_ids=("BluetoothDeviceOverview", "BatteryOverview"),
    )
    background = _provider_layout_action_background(
        contract, registry, foreground="#FFCCFFF6", default="#33FFFFFF",
    )
    assert background == "#33FFFFFF"
