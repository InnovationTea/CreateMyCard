"""覆盖 PR489/492 新规则与分类校验、结构化修复反馈的交界。"""

import json
from copy import deepcopy

import pytest

from config.config import get_settings
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation import api
from services.card_validation.compact_validation.constants import _VISUAL_RECIPE_MARKER_PREFIX
from services.card_validation.compact_validation.semantic.display import (
    _paired_recipe_label_context,
)
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_pipeline import DesignCompactProcessor
from services.prompt_builder import PromptBuilder


def _source(component: str, props: dict) -> str:
    rows = [["root", "Column", {}, ["value"]], ["value", component, props]]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _error(source: str, **kwargs: object) -> CompactDslValidationError:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            source,
            task_spec={"size": "2x2", "dataModelSchema": {"data": {}}},
            card_spec={},
            **kwargs,
        )
    return captured.value


def test_compound_duration_is_checked_before_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("多段时长选型失败后不得继续展开组件")

    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden)
    error = _error(_source("EmphasizedData", {"value": "7小时1分"}))
    assert len(error.errors) == 1
    assert "compound duration '7小时1分'" in error.errors[0]
    assert "EmphasisText.mainText" in error.errors[0]
    assert error.diagnostics == ()


def test_text_block_reads_its_paired_label_without_using_other_items() -> None:
    def part(identifier: str, kind: str, children: tuple = (), **props: object) -> ComponentRow:
        return ComponentRow(
            identifier,
            "Text" if kind in {"label", "value"} else "Column",
            {"_visualRecipe": f"{_VISUAL_RECIPE_MARKER_PREFIX}TextBlock.{kind}", **props},
            children,
        )

    rows = [
        part("item", "item", ("label_slot", "value_slot")),
        part("label_slot", "labelSlot", ("label",)),
        part("label", "label", content="睡眠时长"),
        part("value_slot", "valueSlot", ("value",)),
        part("value", "value", content="7小时1分"),
        part("other", "item", ("other_slot",)),
        part("other_slot", "labelSlot", ("other_label",)),
        part("other_label", "label", content="电量"),
    ]
    parents = {}
    for row in rows:
        for child in row.children:
            parents[child] = row.component_id
    by_id = {row.component_id: row for row in rows}
    value = by_id.get("value")
    assert value is not None
    assert _paired_recipe_label_context(value, parents, by_id) == "睡眠时长"


@pytest.mark.parametrize("max_lines", [1, 2])
def test_text_width_checks_complete_copy_and_respects_multiline(max_lines: int) -> None:
    source = _source(
        "Text",
        {"content": "完整标签不能截断", "width": 32, "fontSize": 14, "maxLines": max_lines},
    )
    if max_lines == 1:
        error = _error(source)
        assert any("text width overflow" in message for message in error.errors)
        assert "完整标签不能截断" in str(error)
    else:
        result = validate_compact_dsl(
            source, task_spec={"size": "2x2", "dataModelSchema": {"data": {}}}, card_spec={}
        )
        assert result.warnings == ()


def test_width_errors_survive_alongside_structured_height_errors() -> None:
    source = _source(
        "Text",
        {"content": "完整标签不能截断", "width": 32, "height": 200, "fontSize": 14},
    )
    error = _error(source)
    assert any(item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW" for item in error.diagnostics)
    assert any("text width overflow" in message for message in error.errors)
    issues = DesignCompactProcessor._validation_failure(source, error.errors, groups=error.groups)
    prompt = PromptBuilder().build_repair(
        [{"role": "system", "content": "合同"}, {"role": "user", "content": "{}"}],
        source,
        [item.to_prompt_payload() for item in issues.errors],
    )
    content = prompt[1].get("content")
    assert isinstance(content, str)
    assert "COMPACT_LAYOUT_HEIGHT_OVERFLOW" in content
    assert "text width overflow" in content
    assert "compactDiagnostics" not in content


def test_structured_height_feedback_keeps_repair_scope_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "enable_design_compact_runtime_prompt_context", False)
    source = _source("EmphasisText", {"mainText": "完整信息", "height": 200})
    error = _error(source)
    issues = DesignCompactProcessor._validation_failure(source, error.errors, groups=error.groups)
    payloads = [item.to_prompt_payload() for item in issues.errors]
    before = deepcopy(payloads)
    tracker = CompactRepairStrategyTracker()
    first = tracker.next_directive(source, payloads)
    second = tracker.next_directive(source, payloads)
    assert first.category == "layout_capacity"
    assert first.scope == "sublayout"
    assert second.scope == "full_dsl"
    strategy = second.to_prompt_payload()
    prompt = PromptBuilder().build_repair(
        [{"role": "system", "content": "合同"}, {"role": "user", "content": "{}"}],
        source,
        payloads,
        dsl_format="design-compact-dsl",
        repair_strategy=strategy,
    )
    content = prompt[-1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("repairStrategy") == strategy
    assert "禁止沿用其旧拓扑" in payload.get("instruction", "")
    assert "COMPACT_LAYOUT_HEIGHT_OVERFLOW" in content
    assert payloads == before
