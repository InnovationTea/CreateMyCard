"""验证静态 error 的脚本入口不依赖 Web，且只接受完整复检取得的进展。"""

import json
import subprocess
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from compact_script_helpers import example, options, process
from services import compact_script_repair as scripts
from services.compact_script_repair import ScriptRepairBudget
from services.generation_pipeline import DslProcessingResult, QualityIssue


def broken_height(*, both=False):
    rows = [json.loads(line) for line in example("会议").splitlines()]
    extra = []
    for row in rows:
        if row[0] == "left" or (both and row[0] == "right"):
            child = row[3][0]
            nested = row[0] + "_inner"
            row[2]["height"] = 20
            row[3] = [nested]
            extra.append([nested, "Column", {"height": 40}, [child]])
    rows.extend(extra)
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.asyncio
async def test_static_height_error_is_fixed_without_renderer(monkeypatch):
    initial = process(broken_height())
    assert initial.errors
    renderer = AsyncMock(side_effect=AssertionError("静态修复不得调用浏览器"))
    monkeypatch.setattr(subprocess, "Popen", renderer)
    budget = ScriptRepairBudget(12)
    evaluate = AsyncMock(side_effect=process)
    result = await scripts.repair_static_errors(
        initial,
        settings=options(enable_compact_script_repair=True),
        evaluate=evaluate,
        budget=budget,
    )
    assert not result.errors
    assert result.source_dsl != initial.source_dsl
    assert budget.candidates_used == 1
    renderer.assert_not_called()
    assert '"mainText":"会议"' in result.source_dsl


@pytest.mark.parametrize("warning", [False, True])
@pytest.mark.asyncio
async def test_pass_and_warning_never_modify_source(warning):
    original = process(example("会议"))
    if warning:
        original = replace(
            original, issues=(QualityIssue("validation", "RISK", "风险", "warning"),)
        )
    evaluate = AsyncMock()
    result = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
    )
    assert result is original
    evaluate.assert_not_called()


@pytest.mark.parametrize("enabled,candidates", [(False, 12), (True, 0)])
@pytest.mark.asyncio
async def test_switch_and_zero_budget_skip_static_candidates(enabled, candidates):
    original = process(broken_height())
    evaluate = AsyncMock()
    final = await scripts.repair_static_errors(
        original,
        settings=options(enable_compact_script_repair=enabled),
        evaluate=evaluate,
        budget=ScriptRepairBudget(candidates),
    )
    assert final is original
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_partial_progress_keeps_latest_source_and_remaining_errors():
    original = process(broken_height(both=True))
    assert len(original.errors) == 2
    budget = ScriptRepairBudget(1)
    result = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=AsyncMock(side_effect=process),
        budget=budget,
    )
    assert len(result.errors) == 1
    assert result.source_dsl != original.source_dsl
    assert (
        result.errors[0].prompt_context.get("compactDiagnostics")[0].get("componentId") == "right"
    )


@pytest.mark.asyncio
async def test_rejected_candidate_does_not_replace_original():
    original = process(broken_height())
    invalid = DslProcessingResult("不应采用", issues=(QualityIssue("validation", "NEW", "新错误"),))
    result = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=AsyncMock(return_value=invalid),
        budget=ScriptRepairBudget(12),
    )
    assert result is original


@pytest.mark.asyncio
async def test_unhandled_error_goes_back_to_model_without_fake_changes():
    original = DslProcessingResult(
        "invalid", issues=(QualityIssue("conversion", "UNKNOWN", "错误"),)
    )
    evaluate = AsyncMock()
    result = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
    )
    assert result is original
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_upstream_width_warning_does_not_trigger_script_repair():
    from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
    from test_compact_horizontal_budget import _TASK, _source

    context = DslProcessingContext(size="2x4", task_spec=_TASK, card_spec={}, protocol_profile={})
    processor = DesignCompactProcessor()
    original = processor.process(_source(), context)
    assert not original.errors and original.issues

    async def evaluate(source):
        return processor.process(source, context)

    evaluate = AsyncMock(side_effect=evaluate)
    final = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
    )
    assert final is original
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_hard_width_error_uses_sibling_rule_without_new_warning():
    from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
    from test_compact_horizontal_budget import _TASK, _source

    context = DslProcessingContext(size="2x4", task_spec=_TASK, card_spec={}, protocol_profile={})
    processor = DesignCompactProcessor()
    original = processor.process(_source(weight=0.5), context)
    assert original.errors

    async def evaluate(source):
        return processor.process(source, context)

    final = await scripts.repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert not final.issues
    assert final.source_dsl.count('"ProgressCircle"') == 3
