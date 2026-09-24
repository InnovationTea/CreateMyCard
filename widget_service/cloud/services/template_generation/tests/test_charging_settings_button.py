"""Keep charging-pair settings buttons text-only without changing other cards."""

import pytest

from services.template_generation.engine.cardplan.compiler import (
    _normalize_charging_settings_button,
)


@pytest.mark.parametrize(
    "action_id",
    ["event.open.settings.bluetooth", "event.open.settings.battery"],
)
def test_charging_pair_removes_only_optional_button_icon(action_id):
    params = {"actionId": action_id, "label": "Settings", "icon": "asset.icon"}
    roots = {"GetEarphoneInfo": ("/earphone",), "GetPhoneBatteryInfo": ("/battery",)}
    actual = _normalize_charging_settings_button("PillAction@1", params, roots, "2x4")
    assert actual == {"actionId": action_id, "label": "Settings"}
    assert params.get("icon") == "asset.icon"


def test_other_business_keeps_optional_icon():
    params = {"actionId": "event.open.settings.bluetooth", "icon": "asset.icon"}
    roots = {"GetEarphoneInfo": ("/earphone",)}
    assert _normalize_charging_settings_button("PillAction@1", params, roots, "2x4") == params
