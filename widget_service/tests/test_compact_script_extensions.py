"""两个新增开关必须对应真实静态 error，并完整复检；无需图片或浏览器。"""

import json
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from compact_script_helpers import example, options
from config.config import get_settings
from services.compact_script_repair import ScriptRepairBudget, repair_static_errors
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext

HANDLER = {"call": "clickToDeeplink", "args": {"intentName": "Weather", "uri": "hww://weather"}}


def sample(kind, *, handlers=None, parent_height=60, inner_height=None):
    rows = [json.loads(line) for line in example("会议").splitlines()]
    extra = []
    for row in rows:
        if row[0] == "row":
            row[2].pop("height", None)
            if parent_height is not None:
                row[2]["height"] = parent_height
        if row[0] != "left":
            continue
        if kind == "duplicate-click":
            row[2]["onClick"] = deepcopy(handlers if handlers is not None else [HANDLER, HANDLER])
        else:
            row[3] = ["inner"]
            extra.append(["inner", "Column", {"height": "matchParent"}, ["value"]])
    if inner_height is not None:
        extra[0][3] = ["fixed"]
        extra.append(["fixed", "Column", {"height": inner_height}, ["value"]])
    rows.extend(extra)
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    context = DslProcessingContext(
        size="2x4",
        protocol_profile={},
        card_spec={},
        task_spec={
            "size": "2x4",
            "appVersion": "11.7.7.300",
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
            "eventCandidates": [HANDLER],
        },
    )
    return source, context


@pytest.mark.parametrize(
    "kind,code,switch",
    [
        ("duplicate-click", "COMPACT_CLICK_HANDLER_COUNT", "enable_compact_duplicate_click_repair"),
        (
            "height-closure",
            "COMPACT_LAYOUT_HEIGHT_UNRESOLVED",
            "enable_compact_height_closure_repair",
        ),
    ],
)
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.asyncio
async def test_new_switches_fix_real_errors_independently(kind, code, switch, enabled):
    source, context = sample(kind)
    processor = DesignCompactProcessor()
    original = processor.process(source, context)
    codes = []
    for error in original.errors:
        for diagnostic in error.prompt_context.get("compactDiagnostics", []):
            codes.append(diagnostic.get("code"))
    assert code in codes

    async def check(candidate):
        return processor.process(candidate, context)

    evaluate = AsyncMock(side_effect=check)
    flags = {
        "enable_compact_duplicate_click_repair": False,
        "enable_compact_height_closure_repair": False,
        switch: enabled,
    }
    budget = ScriptRepairBudget(12)
    final = await repair_static_errors(
        original,
        settings=options(**flags),
        evaluate=evaluate,
        budget=budget,
        context=context,
    )
    if enabled:
        assert not final.errors
        assert budget.candidates_used == 1
        values = {}
        for line in final.source_dsl.splitlines():
            row = json.loads(line)
            values[row[0]] = row
        if kind == "duplicate-click":
            assert values.get("left")[2].get("onClick") == [HANDLER]
        else:
            assert values.get("left")[2].get("height") == "matchParent"
            assert values.get("inner")[2].get("height") == "matchParent"
    else:
        assert final is original
        evaluate.assert_not_called()


@pytest.mark.parametrize(
    "handlers",
    [
        [],
        [HANDLER, {"call": "other", "args": {}}],
        [{"call": "same", "args": {"value": 1}}, {"call": "same", "args": {"value": True}}],
        [{"call": "same"}, {"call": "same"}],
    ],
)
@pytest.mark.asyncio
async def test_click_rule_does_not_invent_or_choose_actions(handlers):
    source, context = sample("duplicate-click", handlers=handlers)
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    evaluate = AsyncMock()
    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert final is original
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_height_rule_skips_unknown_parent_height():
    source, context = sample("height-closure", parent_height=None)
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    evaluate = AsyncMock()
    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert final is original
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_height_closure_does_not_hide_new_overflow():
    source, context = sample("height-closure", inner_height=80)
    processor = DesignCompactProcessor()
    original = processor.process(source, context)

    async def check(candidate):
        return processor.process(candidate, context)

    evaluate = AsyncMock(side_effect=check)
    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert final is original
    assert evaluate.call_count == 1


def test_new_switches_are_exposed_with_matching_defaults():
    from pathlib import Path

    from debug_tools.batch_testing.managed_config import GENERATION_OPTIONS, field_types

    settings = get_settings()
    fields = field_types(Path(__file__).parents[1])
    for name in (
        "enable_compact_duplicate_click_repair",
        "enable_compact_height_closure_repair",
        "enable_compact_semantic_layout_repair",
    ):
        assert getattr(settings, name) is True
        assert fields.get(name) == "bool"
        assert name in GENERATION_OPTIONS


@pytest.mark.parametrize("value", [True, 1.5, -1, 33])
def test_invalid_candidate_limits_are_rejected(value):
    from config.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, compact_script_max_candidates=value)
