"""整卡动作合同、展开证据定位、量化进展和 EventCard 角色修复回归。"""

import json
from dataclasses import replace

import pytest
from compact_script_helpers import options
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_script_repair import (
    ScriptRepairBudget,
    _error_facts,
    _improved,
    repair_static_errors,
)
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessingResult,
    QualityIssue,
)


def findings(*amounts):
    issues = []
    for identifier, overflow in amounts:
        diagnostic = {
            "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
            "componentId": "root",
            "evidenceComponentId": identifier,
            "actual": {"overflow": overflow},
        }
        issues.append(
            QualityIssue(
                "validation",
                "COMPACT",
                "超限",
                prompt_context={
                    "compactDiagnostics": [diagnostic],
                },
            )
        )
    return DslProcessingResult("source", issues=tuple(issues))


@pytest.mark.parametrize(
    "before,after,accepted",
    [
        ([("a", 26)], [("a", 8)], True),
        ([("a", 26)], [("a", 26)], False),
        ([("a", 26)], [("a", 27)], False),
        ([("a", 26)], [("a", None)], False),
        ([("a", 26)], [("b", 8)], False),
        ([("a", 26), ("b", 8)], [("a", 8), ("b", 9)], False),
        ([("a", 26), ("b", 8)], [("a", 26)], True),
        ([("a", 26), ("b", 8)], [("a", 8), ("b", 8)], True),
        ([("a", 26), ("a", 8)], [("a", 20), ("a", 8)], True),
        ([("a", 26), ("a", 8)], [("a", 30), ("a", 8)], False),
    ],
)
def test_candidate_progress_requires_known_improvement_and_no_regression(before, after, accepted):
    assert _improved(findings(*before), findings(*after)) is accepted


def test_source_mapping_keeps_independent_failures_and_new_warning_is_rejected():
    before = findings(("body", 26), ("primary", 8))
    assert len(_error_facts(before)) == 2
    after = findings(("body", 8), ("primary", 8))
    warning = QualityIssue("validation", "NEW_WARNING", "新警告", "warning")
    assert not _improved(before, replace(after, issues=(*after.issues, warning)))


def event_sample(count):
    items = [{"title": "会议", "time": str(i)} for i in range(count)]
    rows = [
        [
            "root",
            "Layout",
            {"layout": "W-top-bottom", "variant": "continuous"},
            ["title", "primary", "details"],
        ],
        ["title", "SingleLineTitle", {"title": "行程"}],
        ["primary", "EmphasisText", {"mainText": "明日"}],
        ["details", "EventCard", {"items": items, "density": "compact"}],
        ["/ui/status", "ready"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    context = DslProcessingContext(
        size="2x4",
        card_spec={},
        protocol_profile={},
        colorless_layout=True,
        task_spec={
            "size": "2x4",
            "appVersion": "99.0",
            "eventCandidates": [],
            "assetCandidates": [],
            "dataModelSchema": {"data": {}},
        },
    )
    return source, context


@pytest.mark.parametrize("count,passes", [(2, True), (10, False)])
@pytest.mark.asyncio
async def test_event_role_repair_preserves_all_items_and_refuses_excess_capacity(count, passes):
    source, context = event_sample(count)
    processor = DesignCompactProcessor()
    original = processor.process(source, context)
    if count == 2:
        assert not original.errors
        evaluate = pytest.fail
        final = await repair_static_errors(
            original,
            settings=options(),
            evaluate=evaluate,
            budget=ScriptRepairBudget(12),
            context=context,
        )
        assert final is original
        return
    assert original.errors

    async def evaluate(candidate):
        return processor.process(candidate, context)

    budget = ScriptRepairBudget(12)
    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=budget,
        context=context,
    )
    assert bool(final.errors) != passes
    assert budget.candidates_used > 0
    if not passes:
        assert final is original
        return
    old_nodes = parse_compact_dsl_rows(original.source_dsl, expand_layouts=False)
    new_nodes = parse_compact_dsl_rows(final.source_dsl, expand_layouts=False)
    for row in old_nodes:
        if not isinstance(row, ComponentRow) or row.component_id != "root":
            assert row in new_nodes


def test_geometry_diagnostics_keep_measured_identity_after_mapping_to_source():
    from test_compact_semantic_repair import sample

    source, context = sample("columns")
    result = DesignCompactProcessor().process(source, context)
    identities = set()
    for issue in result.errors:
        for diagnostic in issue.prompt_context.get("compactDiagnostics", []):
            if diagnostic.get("componentId") == "root":
                assert diagnostic.get("evidenceComponentId")
                identities.add(diagnostic.get("evidenceComponentId"))
    assert len(identities) >= 2
