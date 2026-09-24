"""耳机按钮背景统一，隔离共享主题中的手机电量。

全部 GetEarphoneInfo 模板在普通 / 融球主题下的动作背景解析矩阵，以及混合
业务时回退主题默认背景的契约，已固化为场景金样（Layer C）：
``earphone__action_background_matrix``。构建函数内置规则断言（普通主题的
``#3364BB5C``、布局覆盖 ``#1952991F``、融球 ``#33FFFFFF``），快照冻结每个
模板最终解析的背景色；规则或主题漂移会直接导致构建失败或快照 diff。
引擎或模板改动后按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
本文件没有剩余测试函数——场景由 golden 工作流的发现导入并注册。
"""

from typing import Any

from services.template_generation.engine.cardplan.compiler import _provider_layout_action_background
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.test_support.golden_scenarios import scenario

_THEMES: tuple[tuple[str, bool], ...] = (("plain", False), ("fusion", True))


def _earphone_action_backgrounds(fusion: bool) -> dict[str, Any]:
    registry = get_cardplan_registry(fusion)
    theme_id = "fusion-battery-teal" if fusion else "audio-product-neutral-violet"
    theme = registry.require_theme(theme_id)
    assert theme.action_style is not None
    backgrounds: dict[str, str] = {}
    records = sorted(
        registry.template_variant_search_records, key=lambda record: record.template_id,
    )
    for record in records:
        if record.capability_id != "GetEarphoneInfo":
            continue
        contract = HybridBodyContract.model_construct(
            theme_profile_id=theme_id,
            allowed_template_ids=(record.template_id,),
            allowed_business_component_ids=("BluetoothDeviceOverview",),
        )
        expected = "#33FFFFFF" if fusion else "#3364BB5C"
        definition = registry.templates.get(record.template_id)
        assert definition is not None
        if not fusion and definition.layout_action_style is not None:
            expected = "#1952991F"
        background = _provider_layout_action_background(
            contract, registry, foreground=theme.action_style.content_color,
            default=theme.action_style.background_color,
        )
        assert background == expected, record.template_id
        backgrounds[record.template_id] = background
    assert backgrounds
    return backgrounds


def _mixed_business_fusion_background() -> str:
    registry = get_cardplan_registry(True)
    contract = HybridBodyContract.model_construct(
        theme_profile_id="fusion-battery-teal",
        allowed_template_ids=("BluetoothDeviceOverviewHero@1", "BatteryOverviewHero@1"),
        allowed_business_component_ids=("BluetoothDeviceOverview", "BatteryOverview"),
    )
    return str(_provider_layout_action_background(
        contract, registry, foreground="#FFCCFFF6", default="#33FFFFFF",
    ))


@scenario("earphone__action_background_matrix")
def _build_action_background_matrix() -> dict[str, Any]:
    payload: dict[str, Any] = {
        theme_slug: _earphone_action_backgrounds(fusion) for theme_slug, fusion in _THEMES
    }
    payload["mixed_business_fusion"] = _mixed_business_fusion_background()
    return payload
