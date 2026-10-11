"""验证 Design Compact Repair 提示词保留通用、语义优先的修复流程。"""

import json

from services.prompt_builder import REPAIR_SYSTEM_PROMPT, PromptBuilder


def test_repair_system_prompt_requires_root_cause_and_regression_checks() -> None:
    assert "先恢复语义事实" in REPAIR_SYSTEM_PROMPT
    assert "再定位共同根因" in REPAIR_SYSTEM_PROMPT
    assert "按值形态选择结构" in REPAIR_SYSTEM_PROMPT
    assert "重算受影响子树" in REPAIR_SYSTEM_PROMPT
    assert "最后整体回归" in REPAIR_SYSTEM_PROMPT
    assert "TaskSpec 是值语义的唯一依据" in REPAIR_SYSTEM_PROMPT
    assert "已经包含单位的" in REPAIR_SYSTEM_PROMPT
    assert "不得追加或拆出单位" in REPAIR_SYSTEM_PROMPT


def test_build_repair_reinforces_semantic_and_related_structure_checks() -> None:
    initial_prompt = [
        {"role": "system", "content": "create constraints"},
        {"role": "user", "content": '{"size":"2x2"}'},
    ]
    quality_errors = [
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": "invalid display structure",
        }
    ]

    messages = PromptBuilder().build_repair(
        initial_prompt,
        "invalid source",
        quality_errors,
        dsl_format="compact-dsl",
        repair_strategy={
            "category": "layout_capacity",
            "scope": "parent_layout",
            "repairStrategy": "structural",
            "retryTarget": "dsl_recompose",
            "instruction": "重新选择父布局变体。",
        },
    )

    assert messages[0]["content"].startswith("create constraints")
    assert REPAIR_SYSTEM_PROMPT in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    instruction = payload["instruction"]
    assert "字段类型与展示语义" in instruction
    assert "共同根因" in instruction
    assert "父容器" in instruction
    assert "重复单位" in instruction
    assert payload["qualityErrors"] == quality_errors
    assert payload["repairStrategy"]["scope"] == "parent_layout"
    assert payload["repairStrategy"]["retryTarget"] == "dsl_recompose"
    assert "本轮修复路由：重新选择父布局变体。" in instruction
