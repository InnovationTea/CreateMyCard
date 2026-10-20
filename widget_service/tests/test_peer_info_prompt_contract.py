"""同级短信息的选型描述归属及加载回归，不把文案断言当作模型遵循率。"""

import hashlib
from pathlib import Path

import pytest

from services.compact_prompt_loader import assemble_prompts

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
FEWSHOT_HASHES = {
    "2x2.md": "c1d476b3454820450f8d3ca341d5301446e831a6fab2ce578455b3130e2cc7d5",
    "2x4.md": "8599f95498cc516249882701c749b1ef0ab335adb3ef1a92f43e3b7843e4b812",
}


def source_text(name: str) -> str:
    return (SOURCE / name).read_text(encoding="utf-8")


def test_pair_selection_belongs_to_combination_contract() -> None:
    text = source_text("combinations/common.md")
    assert "恰好两组同级短信息" in text
    assert "同一对象下两个不同口径的指标" in text
    assert "标签或单位说明不算需要另补一个动态字段" in text
    assert "动作无法承载" in text
    assert "专用表达" in text


def test_one_block_exclusion_does_not_exclude_two_instances() -> None:
    text = source_text("components/common.md")
    assert "本限制针对单个实例" in text
    assert "每块分别表达一个指标" in text


def test_small_layout_keeps_peer_info_titleless() -> None:
    text = source_text("layouts/2x2.md")
    assert "S-title-dual-content | [title, primary, support] | 仅普通主辅" in text
    assert "双 InfoBlock 不使用本布局" in text
    assert "不得增加公共\nSingleLineTitle" in text
    assert '"layout":"S-title-dual-content","variant":"stacked-info"' not in text


def test_titleless_pair_does_not_require_different_business_objects() -> None:
    text = source_text("layouts/2x2.md")
    assert "已成立双信息块且无需共同标题" in text
    assert "不能将单一主值及其紧密辅助拆成两块" in text
    small_components = source_text("components/2x2.md")
    assert "是否成立双信息块遵守组合合同" in small_components
    assert "两个同级 InfoBlock 必须放入无标题的 S-dual-info" in small_components
    assert "“不要标题”不等于删除这些必要标签" in small_components
    assert "同一对象的多个属性不是双对象" not in small_components


def test_plan_maps_selected_combination_without_repeating_trigger_table() -> None:
    text = source_text("plan.md")
    assert "双信息块组合的事实首选 InfoBlock" in text
    assert "layoutHints 首选无独立标题的 S-dual-info" in text
    assert "不把数值字段逐项默认推荐为 EmphasizedData" in text
    assert "恰好两组同级短信息" not in text


def test_repair_preserves_pair_relationship_without_freezing_component_type() -> None:
    text = source_text("repair.md")
    assert "同级组合换型时成组保持同规格" in text
    assert "组件类型不是硬约束" in text
    assert "改为无标题 S-dual-info" in text


def test_complete_fewshots_do_not_pair_info_blocks_with_title() -> None:
    text = source_text("fewshots/2x2.md")
    assert '"layout":"S-title-dual-content","variant":"stacked-info"' not in text
    assert '"layout":"S-dual-info"' in text
    assert "本例不使用图标、标题或动作" in text


def test_static_explanation_placement_precedes_component_replacement() -> None:
    component = source_text("components/common.md")
    assert "`secondaryText` 仅作静态说明时" in component
    assert "辅助行已有动态事实时不能覆盖它" in component
    repair = source_text("repair.md")
    assert "先按组件合同恢复读数与静态说明的分工" in repair
    assert "不得覆盖动态辅助值" in repair


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fewshots_remain_byte_identical(size: str) -> None:
    expected = FEWSHOT_HASHES.get(f"{size}.md")
    assert expected is not None
    actual = hashlib.sha256((SOURCE / "fewshots" / f"{size}.md").read_bytes()).hexdigest()
    assert actual == expected


def test_pair_selection_is_loaded_into_create_and_not_duplicated_in_plan_contract() -> None:
    prompts = assemble_prompts(SOURCE)
    create = prompts.get("create")
    plan = prompts.get("plan")
    assert isinstance(create, str)
    assert isinstance(plan, str)
    assert create.count("恰好两组同级短信息") == 1
    assert "恰好两组同级短信息" not in plan
