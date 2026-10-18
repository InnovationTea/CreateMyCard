"""耳机 Hero 左右耳电量去重及可选内容回归。"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.provider_bundle import load_provider_bundle

_EARPHONE_ROOT = (
    Path(__file__).resolve().parents[1] / "resources/source/providers/earphone"
)


@pytest.mark.parametrize(
    ("has_left", "has_right"),
    [(False, False), (True, False), (False, True), (True, True)],
)
@pytest.mark.parametrize(
    ("left_icon", "right_icon"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_hero_renders_earbud_pair_only_once(
    has_left: bool,
    has_right: bool,
    left_icon: bool,
    right_icon: bool,
) -> None:
    bundle = load_provider_bundle(_EARPHONE_ROOT)
    definition = next(
        item for item in bundle.templates if item.wire_id == "BluetoothDeviceOverviewHero@1"
    )
    bindings = {
        "connected": "${data.earphone.isConnected}",
        "name": "${data.earphone.earphoneName}",
    }
    if has_left:
        bindings["left"] = "${data.earphone.leftBatteryLevel}"
    if has_right:
        bindings["right"] = "${data.earphone.rightBatteryLevel}"
    params: dict[str, str] = {}
    if left_icon:
        params["leftEarIcon"] = "resources/base/media/l_circle_fill.svg"
    if right_icon:
        params["rightEarIcon"] = "resources/base/media/r_circle_fill.svg"
    root = _instantiate_blueprint(
        definition.variants[0].root,
        params,
        bindings=bindings,
        theme_values={"primaryColor": "#FFFFFFFF", "supportContentColor": "#99FFFFFF"},
    )
    source = _serialize_node(root)
    has_pair = has_left and has_right
    expected_pairs = int(has_pair)
    assert source.count("leftBatteryLevel") == expected_pairs
    assert source.count("rightBatteryLevel") == expected_pairs
    assert source.count('"左"') == int(has_pair and not left_icon)
    assert source.count('"右"') == int(has_pair and not right_icon)
    assert source.count("l_circle_fill.svg") == int(has_pair and left_icon)
    assert source.count("r_circle_fill.svg") == int(has_pair and right_icon)
    assert source.count("earphoneName") == 1
    assert source.count("isConnected") == 1
    assert source.count("耳机播控") == int(not has_pair)
