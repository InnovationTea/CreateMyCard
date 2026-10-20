"""开关标记等价不扩大动作授权，不改变传入对象或其它参数。"""

import copy

import pytest

from services.event_matching import event_handlers_match


def _handler(flag: object = 0) -> dict:
    return {"call": "clickToIntent", "args": {"intentName": "SetSettingSwitch", "params": {
        "appBundleName": "com.huawei.hmos.settings", "itemName": "wlan", "switchFlag": flag,
    }}}


@pytest.mark.parametrize("expected,actual", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_integer_flags_are_equivalent_without_mutation(expected: int, actual: int) -> None:
    left, right = _handler(actual), _handler(expected)
    original = copy.deepcopy((left, right))
    assert event_handlers_match(left, right)
    assert (left, right) == original


@pytest.mark.parametrize("flag", [None, True, False, "0", "1", 0.0, 1.0, -1, 2])
def test_invalid_flags_are_not_authorized(flag: object) -> None:
    assert not event_handlers_match(_handler(flag), _handler())
    assert not event_handlers_match(_handler(flag), _handler(flag))


@pytest.mark.parametrize("case", ["target", "package", "intent", "call", "extra", "missing"])
def test_other_event_changes_remain_blocking(case: str) -> None:
    actual = _handler(1)
    args = actual.get("args")
    assert isinstance(args, dict)
    params = args.get("params")
    assert isinstance(params, dict)
    if case == "target":
        params["itemName"] = "bluetooth"
    elif case == "package":
        params["appBundleName"] = "other.application"
    elif case == "intent":
        args["intentName"] = "OtherIntent"
    elif case == "call":
        actual["call"] = "otherCall"
    elif case == "extra":
        params["other"] = 1
    else:
        params.pop("appBundleName")
    assert not event_handlers_match(actual, _handler())


def test_non_switch_flags_keep_exact_semantics() -> None:
    expected = {"call": "custom", "args": {"switchFlag": 0}}
    actual = {"call": "custom", "args": {"switchFlag": 1}}
    assert not event_handlers_match(actual, expected)


@pytest.mark.parametrize("name", [
    "event.setWifiMode", "event.setBluetoothMode",
    "event.setNearLinkMode", "event.setPowerSavingMode",
])
@pytest.mark.parametrize("flag", [0, 1])
def test_registered_switch_schema_and_preflight_accept_both_flags(name: str, flag: int) -> None:
    from api.schemas import GenerateWidgetCardRequest
    from services.capability_registry import CapabilityRegistry
    from services.generation_preflight import GenerationPreflight

    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    capability = registry.get_event_capability(name)
    assert capability is not None
    action = capability.actionTemplate.model_dump(mode="json")
    args = action.get("args")
    assert isinstance(args, dict)
    params = args.get("params")
    assert isinstance(params, dict)
    params["switchFlag"] = flag
    request = GenerateWidgetCardRequest(
        uid="switch-test", userQuery="设置开关", size="2x2", title="开关", description="设置开关",
        prdVer="11.7.7.300", device={"romVersion": "7.0"},
        candidateEventCandidates=[{"capabilityId": name, "action": action}],
    )
    result = GenerationPreflight(registry).run(request)
    assert not result.blocking_issues
    assert len(result.effective_events) == 1
