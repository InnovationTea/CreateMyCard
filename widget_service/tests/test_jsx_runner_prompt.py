"""验证 JSX Runner 的信息层级提示词。"""

from services.multi_step_generation.jsx_runner.prompt import (
    build_plan_context,
    build_plan_prompt,
)


def test_plan_prompt_prefers_core_with_secondary_body_over_table_text() -> None:
    prompt = build_plan_prompt()

    assert "完整单焦点" in prompt
    assert "提示 DataDisplay" in prompt
    assert "地点、备注、另一指标等独立补充" in prompt
    assert "其余带标签短字段统一提示同一个 SecondaryBody" in prompt
    assert "分区内不存在可识别核心信息时，才提示 TableText" in prompt
    assert "字段数量多、可写成标签和值或空间紧张都不是选用依据" in prompt


def test_plan_context_reinforces_core_with_secondary_body_over_table_text() -> None:
    context = build_plan_context({"info_required": []})

    assert "先区分完整单焦点、核心加独立补充和无核心清单" in context
    assert "2x2 无动作的完整单焦点使用 DataDisplay" in context
    assert "其余带标签短字段统一放入同一个 SecondaryBody" in context
    assert "分区内不存在可识别核心信息时，才允许 TableText" in context
    assert "字段数量多、可写成标签和值或空间紧张都不是选用依据" in context
