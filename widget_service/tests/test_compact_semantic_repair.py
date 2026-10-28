"""语义布局脚本回归：使用真实处理器校验人工构造的边界用例，不调用模型。"""

import json
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from compact_script_helpers import options
from services.card_validation.compact_validation.diagnostics import DiagnosticCollector
from services.card_validation.compact_validation.semantic.layout.text_width import (
    _collect_text_width_budget_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_script_repair import (
    ScriptRepairBudget,
    repair_static_errors,
    static_candidates,
)
from services.compact_semantic_layout import GEOMETRY_PROPS
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext, QualityIssue
from test_compact_script_extensions import HANDLER


def sample(kind):
    title = ["title", "SingleLineTitle", {"title": "设备", "fontSize": 12}]
    main = ["main", "EmphasisText", {"mainText": "21", "secondaryText": "明天", "fontSize": 18}]
    support = ["support", "SecondaryBody", {"items": [{"value": str(i)} for i in range(6)]}]
    if kind == "columns":
        support[2]["columns"] = 1
        support[2]["items"] = [{"value": str(i), "maxLines": 2} for i in range(6)]
        main[2].pop("secondaryText")
        rows = [
            ["root", "Layout", {"layout": "S-title-content"}, ["title", "body"]],
            title,
            ["body", "Group", {"variant": "peer-pair"}, ["main", "support"]],
            main,
            support,
        ]
    elif kind == "action":
        support[2]["items"] = [{"value": str(i), "maxLines": 2} for i in range(4)]
        rows = [
            ["root", "Layout", {"layout": "S-title-content-action"}, ["title", "body", "action"]],
            title,
            ["body", "Group", {"variant": "hero-support"}, ["main", "support"]],
            main,
            support,
            ["action", "PillButton", {"label": "查看", "onClick": [HANDLER]}],
        ]
    elif kind == "region":
        support[2]["items"] = [{"value": str(i), "maxLines": 2} for i in range(6)]
        rows = [
            ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            ["left", "Region", {"variant": "title-hero-support"}, ["title", "main", "support"]],
            title,
            main,
            support,
            ["right", "Region", {"variant": "center"}, ["other"]],
            ["other", "EmphasisText", {"mainText": "正常"}],
        ]
    else:
        support[2]["items"] = [{"value": str(i), "maxLines": 2} for i in range(6)]
        rows = [
            ["root", "Layout", {"layout": "S-title-dual-content"}, ["title", "main", "support"]],
            title,
            main,
            support,
        ]
    rows.append(["/ui/status", "ready"])
    size = "2x4" if kind == "region" else "2x2"
    context = DslProcessingContext(
        size=size,
        card_spec={"suggestSize": size},
        protocol_profile={},
        colorless_layout=True,
        task_spec={
            "size": size,
            "appVersion": "99.0",
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
            "eventCandidates": [HANDLER],
        },
    )
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), context


def assert_preserved(before, after):
    old_rows = parse_compact_dsl_rows(before, expand_layouts=False)
    new_rows = parse_compact_dsl_rows(after, expand_layouts=False)
    nodes = {}
    for row in new_rows:
        if isinstance(row, ComponentRow):
            nodes[row.component_id] = row
            if row.component_type in {"Layout", "Region", "Group"}:
                assert not GEOMETRY_PROPS.intersection(row.props)
    for row in old_rows:
        if not isinstance(row, ComponentRow):
            continue
        actual = nodes.get(row.component_id)
        assert actual is not None and actual.component_type == row.component_type
        if row.component_type not in {"Layout", "Region", "Group", "SecondaryBody"}:
            assert actual == row
        if row.component_type == "SecondaryBody":
            assert {**actual.props, "columns": 0} == {**row.props, "columns": 0}
    old_data = [row for row in old_rows if not isinstance(row, ComponentRow)]
    new_data = [row for row in new_rows if not isinstance(row, ComponentRow)]
    assert old_data == new_data
    old_ids = [row.component_id for row in old_rows if isinstance(row, ComponentRow)]
    new_ids = []
    for row in new_rows:
        if isinstance(row, ComponentRow) and row.component_id in old_ids:
            new_ids.append(row.component_id)
    assert new_ids == old_ids


@pytest.mark.parametrize("kind", ["columns", "group", "action", "region"])
@pytest.mark.asyncio
async def test_semantic_error_repair_uses_original_processor_and_preserves_content(kind):
    source, context = sample(kind)
    processor = DesignCompactProcessor()
    initial = processor.process(source, context)
    assert initial.errors, kind

    async def evaluate(candidate):
        return processor.process(candidate, context)

    budget = ScriptRepairBudget(12)
    final = await repair_static_errors(
        initial,
        settings=options(enable_compact_script_repair=True),
        evaluate=evaluate,
        budget=budget,
        context=context,
    )
    assert not final.errors, [issue.message for issue in final.errors]
    assert final.standard_dsl
    assert 0 < budget.candidates_used <= 12
    assert_preserved(initial.source_dsl, final.source_dsl)
    if kind == "region":
        assert '"right","Region",{"variant":"center"},["other"]' in final.source_dsl


@pytest.mark.parametrize("mode", ["off", "master-off", "zero-budget", "no-context"])
@pytest.mark.asyncio
async def test_semantic_switch_budget_and_context_skip_candidates(mode):
    source, context = sample("columns")
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    evaluate = AsyncMock()
    final = await repair_static_errors(
        original,
        settings=options(
            enable_compact_semantic_layout_repair=mode != "off",
            enable_compact_script_repair=mode != "master-off",
        ),
        evaluate=evaluate,
        budget=ScriptRepairBudget(0 if mode == "zero-budget" else 12),
        context=None if mode == "no-context" else context,
    )
    assert final is original
    evaluate.assert_not_called()


@pytest.mark.parametrize("severity", ["error", "warning"])
@pytest.mark.asyncio
async def test_semantic_candidate_with_new_issue_is_not_adopted(severity):
    source, context = sample("columns")
    original = DesignCompactProcessor().process(source, context)
    invalid = replace(original, issues=(QualityIssue("validation", "NEW", "新问题", severity),))
    evaluate = AsyncMock(return_value=invalid)
    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert final is original
    evaluate.assert_called()


def test_source_located_diagnostics_do_not_edit_unrelated_branch():
    source, context = sample("region")
    initial = DesignCompactProcessor().process(source, context)
    diagnostic = {
        "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        "componentId": "left",
        "evidenceComponentId": "__generated",
        "actual": {"overflow": 8},
    }
    original = replace(
        initial,
        issues=(
            QualityIssue(
                "validation", "COMPACT", "超限", prompt_context={"compactDiagnostics": [diagnostic]}
            ),
        ),
    )
    candidates = list(static_candidates(original, options(), context=context))
    assert candidates
    for rule, candidate in candidates:
        assert rule == "semantic-layout"
        assert_preserved(original.source_dsl, candidate)
        assert '"right","Region",{"variant":"center"},["other"]' in candidate


@pytest.mark.asyncio
async def test_valid_semantic_source_is_unchanged():
    source, context = sample("columns")
    rows = [json.loads(line) for line in source.splitlines()]
    for row in rows:
        if row[0] == "support":
            row[2]["columns"] = 2
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    original = DesignCompactProcessor().process(source, context)
    assert not original.errors
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
async def test_vertical_action_repair_finishes_before_trying_horizontal_group():
    rows = [
        [
            "root",
            "Layout",
            {"layout": "S-title-primary-secondary-action"},
            ["title", "main", "support", "action"],
        ],
        [
            "title",
            "SingleLineTitle",
            {"title": "睡眠", "fontSize": 12, "icon": "resources/calendar.svg"},
        ],
        ["main", "EmphasizedData", {"value": "82", "unit": "分", "fontSize": 30}],
        [
            "support",
            "SecondaryBody",
            {
                "columns": 1,
                "fontSize": 12,
                "items": [
                    {"label": "状态 ", "value": "良好"},
                    {"label": "时长 ", "value": "7小时1分"},
                    {"label": "状态 ", "value": "稳定"},
                ],
            },
        ],
        ["action", "PillButton", {"label": "查看", "onClick": [HANDLER]}],
        ["/ui/status", "ready"],
    ]
    _, context = sample("action")
    context = replace(
        context,
        task_spec={
            **context.task_spec,
            "assetCandidates": [{"id": "asset.calendar", "src": "resources/calendar.svg"}],
        },
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    processor = DesignCompactProcessor()
    original = processor.process(source, context)
    assert original.errors
    evaluated = []

    async def evaluate(candidate):
        evaluated.append(candidate)
        return processor.process(candidate, context)

    final = await repair_static_errors(
        original,
        settings=options(),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert not final.errors, [issue.message for issue in final.errors]
    assert_preserved(original.source_dsl, final.source_dsl)
    assert evaluated
    for candidate in evaluated:
        assert '"variant":"peer-pair"' not in candidate
        assert '"columns":2' not in candidate


def test_new_group_id_does_not_replace_an_existing_business_component():
    source, context = sample("group")
    source = source.replace('"main"', '"root_content_group"')
    original = DesignCompactProcessor().process(source, context)
    candidates = list(static_candidates(original, options(), context=context))
    assert candidates
    for _rule, candidate in candidates:
        assert_preserved(original.source_dsl, candidate)
        assert '"root_content_group_1","Group"' in candidate


def test_fixed_info_slots_are_not_moved_into_readonly_groups():
    rows = [
        [
            "root",
            "Layout",
            {"layout": "S-title-dual-content", "variant": "stacked-info"},
            ["title", "first", "second"],
        ],
        [
            "title",
            "SingleLineTitle",
            {"title": "会议", "fontSize": 12, "icon": "resources/base/media/calendar_fill.svg"},
        ],
        [
            "first",
            "InfoBlock",
            {"variant": "stacked", "primaryText": "评审", "secondaryText": "10点"},
        ],
        [
            "second",
            "InfoBlock",
            {"variant": "stacked", "primaryText": "例会", "secondaryText": "14点"},
        ],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    _, context = sample("group")
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    assert list(static_candidates(original, options(), context=context)) == []


def wide_sample(direction):
    title = [
        "title",
        "SingleLineTitle",
        {"title": "行程", "fontSize": 12, "icon": "resources/calendar.svg"},
    ]
    primary = ["main", "EmphasisText", {"mainText": "明日", "fontSize": 18}]
    details = ["details", "SummaryList", {"items": ["项目评审会议安排", "下午出发"]}]
    if direction == "split":
        primary[2]["secondaryText"] = "九点开始"
        details[2]["items"] = ["评审会议", "下午出发"]
        rows = [
            ["root", "Layout", {"layout": "W-top-bottom"}, ["title", "main", "details"]],
            title,
            primary,
            details,
        ]
    else:
        rows = [
            ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
            ["left", "Region", {"variant": "title-content"}, ["title", "main"]],
            title,
            primary,
            ["right", "Region", {"variant": "center"}, ["details"]],
            details,
        ]
    rows.append(["/ui/status", "ready"])
    _, context = sample("region")
    context = replace(
        context,
        task_spec={
            **context.task_spec,
            "assetCandidates": [{"id": "asset.calendar", "src": "resources/calendar.svg"}],
        },
    )
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), context


@pytest.mark.parametrize(
    "direction,layout",
    [
        ("split", "W-split-panels"),
        ("stack", "W-top-bottom"),
    ],
)
@pytest.mark.asyncio
async def test_registered_wide_layout_switch_preserves_business_rows(direction, layout):
    source, context = wide_sample(direction)
    processor = DesignCompactProcessor()
    original = processor.process(source, context)
    if direction == "split":
        assert not original.errors
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
    assert not final.errors, [issue.message for issue in final.errors]
    assert f'"layout":"{layout}"' in final.source_dsl
    old_rows = parse_compact_dsl_rows(original.source_dsl, expand_layouts=False)
    new_rows = parse_compact_dsl_rows(final.source_dsl, expand_layouts=False)
    for row in old_rows:
        if isinstance(row, ComponentRow) and row.component_type in {"Layout", "Region"}:
            continue
        assert row in new_rows
    assert 0 < budget.candidates_used <= 12


@pytest.mark.asyncio
async def test_registered_wide_layout_switch_respects_semantic_switch():
    source, context = wide_sample("stack")
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    evaluate = AsyncMock()
    final = await repair_static_errors(
        original,
        settings=options(enable_compact_semantic_layout_repair=False),
        evaluate=evaluate,
        budget=ScriptRepairBudget(12),
        context=context,
    )
    assert final is original
    evaluate.assert_not_called()


def test_text_width_diagnostic_keeps_legacy_message_and_reports_measured_fact():
    components = [
        ComponentRow(
            "root", "Column", {"width": "matchParent", "height": "matchParent"}, ("area",)
        ),
        ComponentRow("area", "Column", {"width": 60, "height": 126}, ("text",)),
        ComponentRow(
            "text",
            "Text",
            {"content": "完整文字不可删除", "fontSize": 12, "width": "matchParent"},
            (),
        ),
    ]
    legacy = []
    diagnostics = DiagnosticCollector()
    for errors in (legacy, diagnostics):
        _collect_text_width_budget_errors(components, {"size": "2x4"}, {}, errors, None)
    assert legacy == diagnostics and len(legacy) == 1
    assert len(diagnostics.records) == 1
    record = diagnostics.records[0]
    assert record.code == "COMPACT_LAYOUT_WIDTH_OVERFLOW"
    assert record.component_id == "text" and record.property_path == "/content"
    assert record.expected == {"maximumWidth": 60, "preserveFixedContent": True}
    assert record.actual == {
        "minimumRequiredWidth": 96,
        "overflow": 36,
        "text": "完整文字不可删除",
        "fontSize": 12,
    }
