# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import pytest

from services.card_validation.effective_capability_validator import (
    EffectiveCapabilityValidator,
)


def _action(call: str, intent_name: str, **params: object) -> dict[str, object]:
    return {
        "call": call,
        "args": {
            "intentName": intent_name,
            "params": params,
        },
    }


@pytest.mark.parametrize(
    ("call", "intent_name", "fixed_params"),
    [
        ("clickToApi", "SetMobileData", {}),
        (
            "clickToIntent",
            "SetSettingSwitch",
            {"appBundleName": "com.huawei.hmos.settings", "itemName": "WIFI"},
        ),
        ("clickToIntent", "SetLocationSettingSwicth", {}),
        ("clickToIntent", "SetScreenUseTimeManageSwitch", {}),
        ("clickToIntent", "SetMicSettingSwicth", {}),
    ],
)
def test_effective_event_allows_legacy_switch_flag_for_toggle_action(
    call: str,
    intent_name: str,
    fixed_params: dict[str, object],
) -> None:
    validator = EffectiveCapabilityValidator()
    actual = _action(call, intent_name, **fixed_params, switchFlag=0)
    allowed = _action(call, intent_name, **fixed_params)

    assert validator._event_allowed(actual["call"], actual["args"], [allowed])


def test_effective_event_compatibility_is_symmetric() -> None:
    validator = EffectiveCapabilityValidator()
    actual = _action("clickToApi", "SetMobileData")
    allowed = _action("clickToApi", "SetMobileData", switchFlag=1)

    assert validator._event_allowed(actual["call"], actual["args"], [allowed])


@pytest.mark.parametrize("switch_flag", [-1, 2, True, "0"])
def test_effective_event_rejects_invalid_legacy_switch_flag(switch_flag: object) -> None:
    validator = EffectiveCapabilityValidator()
    actual = _action("clickToApi", "SetMobileData", switchFlag=switch_flag)
    allowed = _action("clickToApi", "SetMobileData")

    assert not validator._event_allowed(actual["call"], actual["args"], [allowed])


def test_effective_event_does_not_relax_non_toggle_action() -> None:
    validator = EffectiveCapabilityValidator()
    actual = _action("clickToApi", "CallPhone", phoneNumber="10086", switchFlag=0)
    allowed = _action("clickToApi", "CallPhone", phoneNumber="10086")

    assert not validator._event_allowed(actual["call"], actual["args"], [allowed])


def test_effective_event_keeps_fixed_toggle_parameters_strict() -> None:
    validator = EffectiveCapabilityValidator()
    actual = _action(
        "clickToIntent",
        "SetSettingSwitch",
        appBundleName="com.huawei.hmos.settings",
        itemName="WIFI",
        switchFlag=0,
    )
    allowed = _action(
        "clickToIntent",
        "SetSettingSwitch",
        appBundleName="com.huawei.hmos.settings",
        itemName="BLUETOOTH",
    )

    assert not validator._event_allowed(actual["call"], actual["args"], [allowed])
