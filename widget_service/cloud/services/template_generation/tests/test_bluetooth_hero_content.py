"""耳机 Hero 左右耳电量去重及可选内容回归。

BluetoothDeviceOverviewHero 蓝图在左右耳电量有无 × 左右耳图标有无的 16 种
组合下序列化后的组件树文本，已固化为一个场景金样（Layer C）：
``bluetooth_hero__pair_content_matrix``（键形如
``battery_{hl}{hr}__icon_{il}{ir}``）。左右耳只渲染一次、缺省文案「左/右」
与图标的互斥、earphoneName / isConnected 各出现一次、成对缺失时回退
「耳机播控」等去重契约都由快照整体冻结。引擎或模板改动后按 golden 工作流
``check --diff`` / ``bless --declared`` 复核。
"""

from pathlib import Path

from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.provider_bundle import load_provider_bundle
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_EARPHONE_ROOT = (
    Path(__file__).resolve().parents[1] / "resources/source/providers/earphone"
)


def _render_bluetooth_hero(
    has_left: bool, has_right: bool, left_icon: bool, right_icon: bool,
) -> str:
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
    return _serialize_node(root)


@scenario("bluetooth_hero__pair_content_matrix")
def _build_pair_content_matrix() -> dict[str, str]:
    payload: dict[str, str] = {}
    for has_left in (False, True):
        for has_right in (False, True):
            for left_icon in (False, True):
                for right_icon in (False, True):
                    key = (
                        f"battery_{int(has_left)}{int(has_right)}"
                        f"__icon_{int(left_icon)}{int(right_icon)}"
                    )
                    payload[key] = _render_bluetooth_hero(
                        has_left, has_right, left_icon, right_icon,
                    )
    return payload


def test_bluetooth_hero_pair_content_matrix() -> None:
    assert_golden_scenario("bluetooth_hero__pair_content_matrix")
