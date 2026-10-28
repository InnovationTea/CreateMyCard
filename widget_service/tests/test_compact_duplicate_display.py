# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""重复绑定候选的无损边界和完整处理链路回归。"""

import copy
import json
import socket
from dataclasses import replace

import pytest

from config.config import get_settings
from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
from services.compact_duplicate_display import (
    duplicate_display_candidates,
    duplicate_display_feedback,
)
from services.compact_plan import evaluate_compact_plan_coverage
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessingResult,
    QualityIssue,
)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("duplicate display tests must not access network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr("services.generation_pipeline.report_ops_metrics", lambda **_: None)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)


def _source(rows):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _case():
    rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "center"}, ["primary"]],
        ["primary", "EmphasisText", {
            "mainText": {"path": "/data/temperatureText"},
            "secondaryText": {"path": "/data/condition"}, "fontSize": 18,
        }],
        ["right", "Region", {"variant": "center"}, ["condition"]],
        ["condition", "EmphasisText", {
            "mainText": {"path": "/data/condition"}, "fontSize": 18,
        }],
        ["/data/temperatureText", "22℃"], ["/data/condition", "多云"],
    ]
    plan = {"info_required": [
        {"dataId": "/data/temperatureText", "requirement": "温度", "priority": "must"},
        {"dataId": "/data/condition", "requirement": "天气", "priority": "must"},
    ]}
    task = {
        "size": "2x4", "appVersion": "99.0", "dataModelSchema": {"data": {
            "temperatureText": {"type": "string", "sampleValue": "22℃"},
            "condition": {"type": "string", "sampleValue": "多云"},
        }},
    }
    context = DslProcessingContext(
        size="2x4", card_spec={"suggestSize": "2x4"}, task_spec=task,
        protocol_profile={}, compact_plan=plan, colorless_layout=True,
    )
    return rows, context


def _duplicates(source, context):
    result = evaluate_compact_plan_coverage(source, context.compact_plan, context.task_spec)
    return result.duplicate_facts


def test_full_processor_rechecks_and_only_removes_optional_duplicate(monkeypatch):
    rows, context = _case()
    source = _source(rows)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors
    assert result.standard_dsl
    before = parse_compact_dsl_rows(original.source_dsl, expand_layouts=False)
    expected = []
    for row in before:
        if getattr(row, "component_id", None) == "primary":
            props = dict(row.props)
            props.pop("secondaryText")
            row = replace(row, props=props)
        expected.append(row)
    after = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    assert after == tuple(expected)
    again = DesignCompactProcessor().process(result.source_dsl, context)
    assert again.source_dsl == result.source_dsl
    assert again.standard_dsl == result.standard_dsl


def test_successful_source_never_enters_duplicate_recovery(monkeypatch):
    rows, context = _case()
    rows[2][2].pop("secondaryText")

    def forbidden(*_args, **_kwargs):
        pytest.fail("successful source must not produce duplicate candidates")

    monkeypatch.setattr("services.generation_pipeline.duplicate_display_candidates", forbidden)
    assert not DesignCompactProcessor().process(_source(rows), context).errors


@pytest.mark.parametrize("value", [
    "{{ ${/data/condition} }}",
    "{{ '天气 ' + ${/data/condition} }}",
    {"path": "/data/condition", "fallback": "未知"},
])
def test_expression_or_extended_binding_is_not_modified(value):
    rows, context = _case()
    duplicates = _duplicates(_source(rows), context)
    rows[2][2]["secondaryText"] = value
    source = _source(rows)
    assert duplicates
    assert duplicate_display_candidates(source, duplicates) == ()


def test_equal_sample_values_at_different_paths_are_not_duplicates():
    rows, context = _case()
    rows[2][2].pop("secondaryText")
    rows[-2][1] = "多云"
    source = _source(rows)
    assert _duplicates(source, context) == ()
    assert duplicate_display_candidates(source, ()) == ()


def _item_case(component="SecondaryBody", labels=("天气", "天气")):
    rows, context = _case()
    rows[2][2].pop("secondaryText")
    rows[4] = ["condition", component, {"items": [
        {"label": labels[0], "value": {"path": "/data/condition"}},
        {"label": labels[1], "value": {"path": "/data/condition"}},
    ], "fontSize": 12}]
    return rows, context


def test_identical_items_keep_one_full_label_binding_and_order():
    rows, context = _item_case()
    source = _source(rows)
    candidates = duplicate_display_candidates(source, _duplicates(source, context))
    assert candidates
    for candidate in candidates:
        expected = copy.deepcopy(rows)
        expected[4][2]["items"].pop()
        assert parse_compact_dsl_rows(candidate.source_dsl, expand_layouts=False) == (
            parse_compact_dsl_rows(_source(expected), expand_layouts=False)
        )


@pytest.mark.parametrize("component,labels", [
    ("TableText", ("天气", "天气")),
    ("SecondaryBody", ("早晨天气", "当前天气")),
])
def test_minimum_count_or_distinct_labels_are_not_erased(component, labels):
    rows, context = _item_case(component, labels)
    source = _source(rows)
    assert duplicate_display_candidates(source, _duplicates(source, context)) == ()


def test_required_main_values_are_not_cleared_and_feedback_explains_slots():
    rows, context = _case()
    rows[2][2]["mainText"] = {"path": "/data/condition"}
    rows[2][2].pop("secondaryText")
    source = _source(rows)
    duplicates = _duplicates(source, context)
    assert duplicate_display_candidates(source, duplicates) == ()
    feedback = duplicate_display_feedback(duplicates)
    assert len(feedback) == 1
    assert len(feedback[0].get("requiredDisplayPositions", [])) == 2
    assert "不能清空属性" in feedback[0].get("ownershipInstruction", "")
    assert "造新事实" in feedback[0].get("ownershipInstruction", "")
    assert "ownershipInstruction" not in duplicates[0]


def test_graph_occurrence_and_action_nodes_do_not_allow_local_removal():
    rows, context = _case()
    source = _source(rows)
    duplicates = _duplicates(source, context)
    forged = copy.deepcopy(duplicates)
    forged[0]["occurrences"][1]["componentType"] = "ProgressCircle"
    assert duplicate_display_candidates(source, forged) == ()
    rows[2][2]["onClick"] = [{"call": "open", "args": {"id": "unchanged"}}]
    assert duplicate_display_candidates(_source(rows), duplicates) == ()


@pytest.mark.parametrize("failure", ["validation", "unexpected_geometry"])
def test_failed_or_unrelated_candidate_change_preserves_original(monkeypatch, failure):
    rows, context = _case()
    source = _source(rows)
    duplicates = _duplicates(source, context)
    issue = QualityIssue(
        "validation", "COMPACT_PLAN_COVERAGE_FAILED", "duplicate",
        prompt_context={"duplicateFacts": list(duplicates)},
    )
    original = DslProcessingResult(source, issues=(issue,))
    processor = DesignCompactProcessor()
    calls = []

    def checked(candidate, _context):
        calls.append(candidate)
        if failure == "validation":
            return DslProcessingResult(candidate, issues=(
                QualityIssue("validation", "COMPACT_DSL_VALIDATION_FAILED", "still invalid"),
            ))
        return DslProcessingResult(
            candidate.replace('"fontSize": 18', '"fontSize": 12'), standard_dsl="not adopted",
        )

    monkeypatch.setattr(processor, "_process", checked)
    result = processor._repair_duplicate_display(original, context)
    assert result is original
    assert 1 <= len(calls) <= 8


def test_duplicate_candidates_have_fixed_upper_bound():
    rows, context = _case()
    rows[4][2] = {
        "mainText": {"path": "/data/extraText"},
        "secondaryText": {"path": "/data/condition"},
    }
    source = _source(rows)
    candidates = duplicate_display_candidates(source, _duplicates(source, context))
    assert 1 <= len(candidates) <= 8


@pytest.mark.parametrize("other_label", [
    "早晨天气", {"path": "/data/anotherCity/name"},
])
def test_unknown_or_different_object_context_is_not_deduplicated(other_label):
    rows, context = _case()
    duplicates = _duplicates(_source(rows), context)
    rows[2][2]["mainText"] = other_label
    assert duplicate_display_candidates(_source(rows), duplicates) == ()


def test_existing_action_parameters_are_preserved_by_full_processing():
    rows, context = _case()
    handler = {"call": "clickToDeeplink", "args": {"uri": "hww://weather"}}
    rows[3] = ["right", "Region", {"variant": "title-content-action"},
               ["title", "condition", "action"]]
    rows.extend([
        ["title", "SingleLineTitle", {"title": "天气"}],
        ["action", "PillButton", {"label": "查看天气", "onClick": [handler]}],
    ])
    plan = copy.deepcopy(context.compact_plan)
    assert isinstance(plan, dict)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "event.weather", "priority": "must", "requirement": "查看天气"})
    task = copy.deepcopy(context.task_spec)
    task["eventCandidates"] = [{"id": "event.weather", **handler}]
    context = replace(context, compact_plan=plan, task_spec=task)
    result = DesignCompactProcessor().process(_source(rows), context)
    assert not result.errors
    assert result.standard_dsl
    compiled = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    action = next(row for row in compiled if getattr(row, "component_id", None) == "action")
    assert action.props.get("onClick") == [handler]
    assert action.props.get("label") == "查看天气"
