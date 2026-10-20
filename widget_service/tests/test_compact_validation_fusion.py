"""覆盖 Fusion 流程与结构化反馈交界处的回归。"""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from config.config import get_settings
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation import api
from services.card_validation.compact_validation.context import ComponentRows, ValidationContext
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    DiagnosticCollector,
)
from services.card_validation.compact_validation.model_feedback import compact_issue_for_model
from services.card_validation.compact_validation.repair_guidance import resolve_fix_hint
from services.card_validation.compact_validation.semantic.display import (
    _collect_progress_readout_object_errors,
)
from services.card_validation.compact_validation.source_locations import SourceLocations
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_layout_runtime import CompactLayoutRuntimeError
from services.compact_plan import CompactPlanCoverageResult
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.prompt_builder import PromptBuilder

INVALID = "\n".join(['["root","Column",{},["value"]]', '["value","Text",{"content":"body"}]'])
TALL = "\n".join(
    [
        '["root","Column",{"height":"matchParent"},["value"]]',
        '["value","EmphasisText",{"mainText":"body","height":200}]',
    ]
)
TASK = {"size": "2x2", "appVersion": "11.7.5.208", "dataModelSchema": {"data": {}}}


def _errors(source: str, **kwargs: object) -> CompactDslValidationError:
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(source, task_spec=TASK, card_spec={"suggestSize": "2x2"}, **kwargs)
    return captured.value


def test_two_by_four_height_over_126_is_blocking_error() -> None:
    items = [
        {
            "title": "澳大利亚网球公开赛",
            "time": "1月11日-31日",
            "location": "墨尔本公园硬地赛场",
        },
        {
            "title": "法国网球公开赛",
            "time": "5月24日-6月7日",
            "location": "巴黎罗兰·加洛斯红土场地",
        },
        {
            "title": "温布尔登网球锦标赛",
            "time": "日期待官方公布",
            "location": "伦敦全英俱乐部草地赛场",
        },
        {
            "title": "美国网球公开赛",
            "time": "日期待官方公布",
            "location": "纽约法拉盛草地公园硬地赛场",
        },
    ]
    rows = (
        [
            "root",
            "Column",
            {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
                "itemMargin": 6,
            },
            ["title", "body"],
        ],
        ["title", "SingleLineTitle", {"title": "2027网球大满贯", "fontSize": 12}],
        [
            "body",
            "Column",
            {
                "width": "matchParent",
                "itemMargin": 8,
                "alignItems": "start",
                "justifyContent": "start",
                "layoutWeight": 1,
            },
            ["events"],
        ],
        ["events", "EventCard", {"items": items, "density": "compact"}],
        ["/state/ready", True],
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    context = DslProcessingContext(
        size="2x4",
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        task_spec={
            "size": "2x4",
            "appVersion": "11.7.5.208",
            "dataModelSchema": {"state": {"ready": {"type": "boolean"}}},
        },
        protocol_profile={"version": "v0.9"},
    )

    result = DesignCompactProcessor().process(source, context)

    assert not result.standard_dsl
    assert result.errors
    diagnostics = []
    for issue in result.errors:
        issue_diagnostics = issue.prompt_context.get("compactDiagnostics", [])
        assert isinstance(issue_diagnostics, list)
        diagnostics.extend(issue_diagnostics)
    height_diagnostics = [
        item for item in diagnostics if item.get("code") == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
    ]
    assert len(height_diagnostics) == 2
    assert {item.get("componentId") for item in height_diagnostics} == {"root", "body"}
    assert all(item.get("severity") == "error" for item in height_diagnostics)


def test_model_whitelist_precedes_layout_and_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("模型组件白名单失败后不应继续匹配布局或展开")

    monkeypatch.setattr(api, "match_compact_layout", forbidden)
    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden)
    error = _errors(INVALID, enforce_model_component_types=True, layout_scope="unknown")
    assert len(error.errors) == 1
    diagnostic = error.diagnostics[0]
    assert diagnostic.code == "COMPACT_MODEL_COMPONENT_FORBIDDEN"
    assert diagnostic.source_line == 2
    assert diagnostic.actual == "Text"


def test_layout_legacy_is_kept_after_structured_height_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = "Alternatives: complete first variant; complete second variant"

    def mismatch(*_args: object, **_kwargs: object) -> None:
        raise CompactLayoutRuntimeError(detail)

    monkeypatch.setattr(api, "match_compact_layout", mismatch)
    error = _errors(TALL, layout_scope="any")
    assert error.errors[-1] == detail
    assert error.groups[-1].has_legacy_record
    assert error.groups[-1].prompt_context() == {}
    assert any(item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW" for item in error.diagnostics)


def test_binding_failure_preserves_layout_order_and_stops_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mismatch(*_args: object, **_kwargs: object) -> None:
        raise CompactLayoutRuntimeError("Alternatives: all candidates")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("绑定合同失败后不应展开")

    monkeypatch.setattr(api, "match_compact_layout", mismatch)
    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden)
    source = '["title","EmphasizedData",{"unit":{"path":"/data/number"},"value":1}]'
    task = {"size": "2x2", "dataModelSchema": {"data": {"number": {"type": "number"}}}}
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(source, task_spec=task, card_spec={}, layout_scope="any")
    assert captured.value.errors[0] == "Alternatives: all candidates"
    assert "schema type number" in captured.value.errors[1]
    assert captured.value.diagnostics == ()


@pytest.mark.parametrize("generated_id", ["value", "value_generated"])
def test_expanded_nodes_never_claim_source_properties(generated_id: str) -> None:
    original = ComponentRows([ComponentRow("value", "EmphasisText", {"mainText": "body"})])
    expanded = ComponentRows([ComponentRow(generated_id, "Text", {"content": "body"})])
    context = ValidationContext(
        original_source='["value","EmphasisText",{"mainText":"body"}]',
        validation_source="same input",
        components=expanded,
        original_components=original,
        data_rows=[],
        task_spec=TASK,
        card_spec={},
    )
    diagnostic = CompactDiagnostic(
        code="COMPACT_DISPLAY_RAW_BOOLEAN",
        validation_class="semantic",
        category="display",
        message="展开节点错误",
        legacy_message="old message",
        expected={"boolean": False},
        actual=False,
        component_id=generated_id,
        property_path="/content",
    )
    located = SourceLocations(context).locate(diagnostic)
    assert located.component_id is None
    assert located.source_line is None
    assert located.property_path is None
    assert located.evidence_source == "expanded"
    payload = {
        "stage": "validation",
        "code": "COMPACT_DSL_VALIDATION_FAILED",
        "message": "old",
        "compactDiagnostics": [located.to_payload()],
    }
    before = deepcopy(payload)
    formatted = compact_issue_for_model(payload)
    assert "高阶组件展开结果" in formatted.get("message", "")
    assert payload == before


@pytest.mark.parametrize("with_hint", [False, True])
def test_height_feedback_preserves_occupancy_and_fixed_design_constraints(with_hint: bool) -> None:
    error = _errors(TALL)
    diagnostic = next(
        item for item in error.diagnostics if item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
    )
    assert "Occupancy:" in diagnostic.legacy_message
    assert "Occupancy:" in diagnostic.message
    assert diagnostic.expected.get("preserveFixedDesignSizes") is True
    assert diagnostic.expected.get("preserveRequiredTextAndActions") is True
    assert "Regroup facts" not in diagnostic.message
    assert "Regroup facts" in diagnostic.legacy_message
    assert diagnostic.actual.get("occupancy")
    hint = resolve_fix_hint(diagnostic)
    assert hint is not None and "固定设计高度" in hint
    assert "调整子组件高度" not in hint
    feedback = compact_issue_for_model({
        "stage": "validation",
        "code": "COMPACT_DSL_VALIDATION_FAILED",
        "message": diagnostic.legacy_message,
        "compactDiagnostics": [
            replace(diagnostic, fix_hint=hint if with_hint else None).to_payload(),
        ],
    })
    message = feedback.get("message")
    assert isinstance(message, str)
    assert "不能依靠权重、裁剪、flex shrink 或分布式对齐" in message
    assert "Occupancy:" in message
    assert ("修改建议：" in message) is with_hint


@pytest.mark.parametrize("with_hint", [False, True])
def test_progress_and_readout_object_error_is_structured(with_hint: bool) -> None:
    components = [
        ComponentRow("root", "Row", {}, ("progress", "readout")),
        ComponentRow("progress", "Progress", {"value": {"path": "/data/battery/value"}}),
        ComponentRow("readout", "Text", {"content": {"path": "/data/weather/value"}}),
    ]
    schema = {
        "data": {
            "battery": {"value": {"type": "number"}},
            "weather": {"value": {"type": "number"}},
        }
    }
    errors = DiagnosticCollector()
    _collect_progress_readout_object_errors(components, {"dataModelSchema": schema}, errors)
    assert len(errors.records) == 1
    diagnostic = errors.records[0]
    assert isinstance(diagnostic, CompactDiagnostic)
    assert diagnostic.code == "COMPACT_DISPLAY_PROGRESS_OBJECT_MISMATCH"
    assert diagnostic.actual.get("progressRoot") == "/data/battery"
    assert diagnostic.expected.get("readoutRoots") == ["/data/weather"]
    assert diagnostic.expected.get("borrowOtherObjectValueAllowed") is False
    assert diagnostic.expected.get("preserveCompleteReadout") is True
    assert "omit its progress" not in diagnostic.message
    assert "omit its progress" in diagnostic.legacy_message
    hint = resolve_fix_hint(diagnostic) if with_hint else None
    assert (hint is not None) is with_hint
    feedback = compact_issue_for_model({
        "stage": "validation",
        "code": "COMPACT_DSL_VALIDATION_FAILED",
        "message": diagnostic.legacy_message,
        "compactDiagnostics": [replace(diagnostic, fix_hint=hint).to_payload()],
    })
    message = feedback.get("message")
    assert isinstance(message, str)
    assert '"borrowOtherObjectValueAllowed":false' in message
    assert '"preserveCompleteReadout":true' in message
    assert ("修改建议：" in message) is with_hint


def test_plan_and_compact_errors_keep_distinct_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import generation_pipeline

    def coverage(*args: object, **kwargs: object) -> CompactPlanCoverageResult:
        assert kwargs.get("allowed_omitted_fact_indexes") == (0,)
        assert kwargs.get("information_errors_as_warnings") is True
        return CompactPlanCoverageResult(errors=("missing fact",), warnings=("plan warning",))

    monkeypatch.setattr(generation_pipeline, "evaluate_compact_plan_coverage", coverage)
    monkeypatch.setattr(
        generation_pipeline,
        "compact_plan_omitted_facts",
        lambda *args: ({"requirement": "旧事实"},),
    )
    context = DslProcessingContext(
        size="2x2",
        task_spec=TASK,
        card_spec={"suggestSize": "2x2"},
        protocol_profile={},
        compact_plan={"info_required": []},
        allowed_omitted_plan_fact_indexes=(0,),
        plan_information_coverage_as_warning=True,
    )
    result = DesignCompactProcessor().process(INVALID, context)
    assert [item.code for item in result.errors] == [
        "COMPACT_PLAN_COVERAGE_FAILED",
        "COMPACT_DSL_VALIDATION_FAILED",
    ]
    assert result.errors[0].prompt_context == {}
    assert result.errors[1].prompt_context.get("compactDiagnostics")
    warnings = [item for item in result.issues if item.severity == "warning"]
    assert [item.code for item in warnings] == [
        "COMPACT_PLAN_COVERAGE_WARNING", "COMPACT_PLAN_FACT_OMITTED",
    ]
    assert all(item.prompt_context == {} for item in warnings)


def test_duplicate_plan_fact_context_reaches_repair_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import generation_pipeline

    duplicate_fact = {
        "requirement": "最高心率",
        "dataId": "/data/health/max",
        "expectedVisibleCount": 1,
        "actualVisibleCount": 2,
        "occurrences": [],
    }

    def coverage(*args: object, **kwargs: object) -> CompactPlanCoverageResult:
        return CompactPlanCoverageResult(
            errors=("duplicate fact",),
            warnings=(),
            duplicate_facts=(duplicate_fact,),
        )

    monkeypatch.setattr(generation_pipeline, "evaluate_compact_plan_coverage", coverage)
    context = DslProcessingContext(
        size="2x2",
        task_spec=TASK,
        card_spec={"suggestSize": "2x2"},
        protocol_profile={},
        compact_plan={"info_required": []},
    )

    result = DesignCompactProcessor().process(INVALID, context)

    plan_issue = next(
        item for item in result.errors if item.code == "COMPACT_PLAN_COVERAGE_FAILED"
    )
    assert plan_issue.prompt_context == {"duplicateFacts": [duplicate_fact]}


@pytest.mark.parametrize("runtime_context", [False, True])
def test_repair_keeps_history_recovery_and_internal_record(
    monkeypatch: pytest.MonkeyPatch, runtime_context: bool,
) -> None:
    monkeypatch.setattr(
        get_settings(), "enable_design_compact_runtime_prompt_context", runtime_context,
    )
    error = _errors(TALL)
    issues = DesignCompactProcessor._validation_failure(TALL, error.errors, groups=error.groups)
    quality_errors = [item.to_prompt_payload() for item in issues.errors]
    history = [[{"stage": "validation", "code": "old", "message": "Occupancy: old"}]]
    recovery = {"variants": ["full alternative"], "ordinaryFactPacking": ["all facts"]}
    initial = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": json.dumps({"compositionRecovery": recovery})},
        {"role": "user", "content": json.dumps({"qualityErrors": history[0]})},
    ]
    before = deepcopy(quality_errors)
    prompt = PromptBuilder().build_repair(
        initial,
        TALL,
        quality_errors,
        dsl_format="design-compact-dsl",
        previous_failures=history,
    )
    content = prompt[-1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert prompt[:len(initial)] == initial
    assert "previousFailures" not in payload
    if runtime_context:
        assert payload.get("compositionRecovery") == recovery
    else:
        assert "compositionRecovery" not in payload
    assert "originalUserContent" not in payload
    assert "invalidSourceDsl" not in payload
    assert {"role": "assistant", "content": TALL} in prompt
    assert quality_errors == before
    assert "关键占用：" in content
    assert "compactDiagnostics" not in content


def test_only_fusion_repair_prompt_source_exists() -> None:
    profiles = Path(__file__).parents[1] / "cloud/data/protocol_profiles"
    assert not (profiles / "design-compact-dsl/REPAIR_SYSTEM_PROMPT.md").exists()
    repair = (profiles / "design-compact-dsl-fusion/prompt_source/repair.md").read_text(
        encoding="utf-8"
    )
    assert "expanded 位置来自模板展开，不是模型 Props" in repair
    assert "previousFailures" in repair
    assert "compositionRecovery" in repair
