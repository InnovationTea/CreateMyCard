"""固定强调主文本采用一致压力与既有修复，保留全部原文和显示规格。"""

import copy
import json
from dataclasses import replace

import pytest

from config.config import get_settings
from services.card_validation.compact_validation.semantic.layout.text_width import (
    _collect_text_width_budget_errors,
)
from services.compact_composition_planner import _text_width
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext

_HANDLER = {"call": "clickToDeeplink", "args": {"intentName": "Settings", "uri": "status"}}


def _source(rows):
    return "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)


def _case():
    rows = [
        ["root", "Layout", {"layout": "S-title-primary-secondary-action"},
         ["title", "primary", "support", "action"]],
        ["title", "SingleLineTitle", {"title": "设备状态", "fontSize": 12}],
        ["primary", "EmphasisText", {"mainText": "设备健康度 92%", "fontSize": 18}],
        ["support", "SecondaryBody", {"columns": 1, "fontSize": 12, "items": [
            {"label": "循环次数 ", "value": "218 次"},
            {"label": "建议充电区间 ", "value": "20%-80%"},
        ]}],
        ["action", "PillButton", {"label": "查看设置", "onClick": [copy.deepcopy(_HANDLER)]}],
        ["/state/ready", True],
    ]
    task = {
        "size": "2x2", "appVersion": "99.0", "userQuery": "显示设备状态并打开设置",
        "dataModelSchema": {"data": {}},
        "eventCandidates": [{"id": "event.settings", **copy.deepcopy(_HANDLER)}],
        "assetCandidates": [],
    }
    facts = []
    for text in ("设备健康度 92%", "循环次数 218 次", "建议充电区间 20%-80%"):
        facts.append({"text": text, "requirement": text, "priority": "must"})
    facts.append({"actionId": "event.settings", "requirement": "打开设置", "priority": "must"})
    context = DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"}, task_spec=task,
        protocol_profile={}, event_candidates=task.get("eventCandidates", []),
        compact_plan={"info_required": facts}, colorless_layout=True,
        plan_information_coverage_as_warning=True,
    )
    return rows, context


@pytest.fixture(autouse=True)
def _offline_metrics(monkeypatch):
    monkeypatch.setattr("services.generation_pipeline.report_ops_metrics", lambda **_: None)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)


def _issue(component="primary_main", kind="text width overflow"):
    return {"code": "COMPACT_DSL_VALIDATION_FAILED", "stage": "validation",
            "message": f"component {component}: {kind}; original font 18 exceeds its area."}


def _measure(text, width, *, marker=None, overflow="clip"):
    props = {"content": text, "fontSize": 18, "maxLines": 1, "width": width,
             "textOverflow": overflow}
    if marker:
        props["_visualRecipe"] = marker
    components = [ComponentRow("root", "Column", {"width": width}, ("text",)),
                  ComponentRow("text", "Text", props)]
    errors, warnings = [], []
    _collect_text_width_budget_errors(
        components, {"size": "2x2"}, {"suggestSize": "2x2"}, errors, None,
        warnings=warnings,
    )
    return errors, warnings


def test_complete_width_uses_same_pressure_as_composition_planner():
    text = "设备健康度 92%"
    pressure = _text_width(text, 18)
    assert pressure == 134
    errors, _ = _measure(text, 126)
    assert len(errors) == 1
    assert "134vp" in errors[0]
    assert text in errors[0]
    assert _measure(text, pressure)[0] == []


def test_existing_chinese_fitting_text_is_unchanged():
    assert _measure("设备健康度", 126) == ([], [])


def test_static_ellipsis_contract_keeps_its_own_measurement_and_warning():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        errors, warnings = _measure(
            "设备健康度 92%", 126, marker="static-content-v1:TextList.primaryText",
            overflow="ellipsis",
        )
    assert errors == []
    assert len(warnings) == 1
    assert "ellipsis" in warnings[0]


def test_real_processor_reports_original_text_and_uses_existing_parent_repair():
    rows, context = _case()
    source = _source(rows)
    result = DesignCompactProcessor().process(source, context)
    issues = [issue.to_prompt_payload() for issue in result.errors]
    assert len(issues) == 1
    assert "134vp" in issues[0].get("message", "")
    assert result.source_dsl == source
    tracker = CompactRepairStrategyTracker(max_repair_attempts=5)
    directive = tracker.next_directive(
        source, issues, compact_plan=context.compact_plan, task_spec=context.task_spec,
    )
    assert directive.scope == "parent_layout"
    assert directive.repair_strategy == "parent_layout_recompose"
    assert "18fp" in directive.instruction
    assert "保留所有字符、空格" in directive.instruction
    assert "S-title-content-action" in directive.instruction
    assert "CircleButton" not in directive.instruction
    assert not directive.capacity_fits
    assert directive.optional_drop is None


@pytest.mark.parametrize("component", ["primary_secondary", "other_main", "primary_main_more"])
def test_other_fields_or_prefix_matches_do_not_change_repair_scope(component):
    rows, context = _case()
    directive = CompactRepairStrategyTracker().next_directive(
        _source(rows), [_issue(component)], task_spec=context.task_spec,
    )
    assert directive.scope == "sublayout"
    assert "固定18fp单行主文本" not in directive.instruction


@pytest.mark.parametrize("kind", ["vertical layout requires at least 150vp", "unknown property"])
def test_non_width_error_does_not_gain_the_fixed_text_instruction(kind):
    rows, context = _case()
    directive = CompactRepairStrategyTracker().next_directive(
        _source(rows), [_issue(kind=kind)], task_spec=context.task_spec,
    )
    assert "固定18fp单行主文本" not in directive.instruction


def test_unreachable_emphasis_is_not_treated_as_the_parent_width_problem():
    rows, context = _case()
    rows.append(["unused", "EmphasisText", {"mainText": "设备健康度 92%", "fontSize": 18}])
    directive = CompactRepairStrategyTracker().next_directive(
        _source(rows), [_issue("unused_main")], task_spec=context.task_spec,
    )
    assert directive.scope == "sublayout"


@pytest.mark.parametrize("size,static", [("2x4", False), ("2x2", True)])
def test_static_or_wide_policy_keeps_existing_route(size, static):
    rows, context = _case()
    task = {**context.task_spec, "size": size}
    directive = CompactRepairStrategyTracker(static_content=static).next_directive(
        _source(rows), [_issue()], task_spec=task,
    )
    assert "固定18fp单行主文本" not in directive.instruction
    assert directive.scope == "sublayout"


def test_fixed_width_does_not_increase_retry_budget_or_authorize_drop():
    rows, context = _case()
    tracker = CompactRepairStrategyTracker(max_repair_attempts=1)
    first = tracker.next_directive(_source(rows), [_issue()], task_spec=context.task_spec)
    final = tracker.next_directive(_source(rows), [_issue()], task_spec=context.task_spec)
    assert first.retryable
    assert not final.retryable
    assert final.optional_drop is None
    assert not tracker.allowed_omitted_fact_indexes


def test_same_font_existing_direct_layout_preserves_complete_text_and_action():
    rows, context = _case()
    original = copy.deepcopy(rows)
    rows[0] = ["root", "Layout", {"layout": "S-title-content-action", "variant": "direct-flush"},
               ["title", "content", "action"]]
    rows[2] = ["primary", "Group", {"variant": "label-value"}, ["label", "reading"]]
    rows.extend([
        ["label", "EmphasisText", {"mainText": "设备健康度 ", "fontSize": 18}],
        ["reading", "EmphasisText", {"mainText": "92%", "fontSize": 18}],
        ["content", "Group", {"variant": "supporting-items"}, ["primary", "support"]],
    ])
    assert rows[3:6] == original[3:6]
    assert rows[6][2].get("mainText") + rows[7][2].get("mainText") == original[2][2].get("mainText")
    result = DesignCompactProcessor().process(_source(rows), context)
    assert not result.errors, [issue.message for issue in result.errors]
    assert any("Plan static text is not fully visible" in issue.message for issue in result.issues)
    nodes = []
    for line in result.standard_dsl.splitlines():
        nodes.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    texts = {}
    for node in nodes:
        if node.get("component") == "Text":
            texts[node.get("content")] = node.get("styles", {}).get("fontSize")
    assert texts.get("设备健康度 ") == 18
    assert texts.get("92%") == 18
    assert any(node.get("onClick") == [_HANDLER] for node in nodes)
    assert "建议充电区间 20%-80%" in texts
    assert texts.get("建议充电区间 20%-80%") == 12
    strict = replace(context, plan_information_coverage_as_warning=False)
    strict_result = DesignCompactProcessor().process(_source(rows), strict)
    missing_text = "Plan static text is not fully visible"
    assert any(missing_text in issue.message for issue in strict_result.errors)
    invalid_rows = copy.deepcopy(original)
    invalid_rows[2][2]["maxLines"] = 2
    rejected = DesignCompactProcessor().process(_source(invalid_rows), replace(context))
    assert any("does not allow maxLines" in issue.message for issue in rejected.errors)
