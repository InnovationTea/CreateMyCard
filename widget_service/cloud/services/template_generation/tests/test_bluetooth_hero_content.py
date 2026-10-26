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
        params["leftEarIcon"] = "resources/base/media/icon_left.svg"
    if right_icon:
        params["rightEarIcon"] = "resources/base/media/icon_right.svg"
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
    # 当前左右耳图标成对采用，任一缺失时两侧均使用 L/R 圆形兜底。
    use_icons = left_icon and right_icon
    assert source.count('"L"') == int(has_pair and not use_icons)
    assert source.count('"R"') == int(has_pair and not use_icons)
    assert source.count("icon_left.svg") == int(has_pair and use_icons)
    assert source.count("icon_right.svg") == int(has_pair and use_icons)
    assert source.count("earphoneName") == 1
    # 连接状态可在标题/说明等多个表达式中复用；左右耳读数仍须各出现一次。
    assert "isConnected" in source
    assert source.count("耳机播控") == int(not has_pair)
