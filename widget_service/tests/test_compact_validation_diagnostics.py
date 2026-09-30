"""验证 Compact 新诊断的兼容分组、定位、建议回退和模型边界。"""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from services.card_validation import compact_dsl_validator
from services.card_validation.compact_validation import repair_guidance
from services.card_validation.compact_validation.context import (
    ComponentRows,
    ValidationContext,
    component_graph,
)
from services.card_validation.compact_validation.diagnostics import (
    MISSING,
    CompactDiagnostic,
    CompactDslValidationError,
    DiagnosticCollector,
    emit_error,
)
from services.card_validation.compact_validation.model_feedback import compact_issue_for_model
from services.card_validation.compact_validation.repair_guidance import (
    RepairGuidanceContext,
    load_default_hints,
    resolve_fix_hint,
    validate_builders,
)
from services.card_validation.compact_validation.source_locations import SourceLocations
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    QualityIssue,
)
from services.prompt_builder import PromptBuilder


def _diagnostic(**changes: Any) -> CompactDiagnostic:
    item = CompactDiagnostic(
        code="COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        validation_class="semantic",
        category="layout",
        message="最小高度 142vp，超过可用高度 126vp。",
        legacy_message="old error, including original advice",
        actual={"minimumRequiredHeight": 142},
        expected={"maximumHeight": 126, "constraint": "不能依靠裁剪消除负预算"},
        component_id="content",
    )
    return replace(item, **changes)


def _payload(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stage": "validation",
        "code": "COMPACT_DSL_VALIDATION_FAILED",
        "message": "old error, including original advice",
        "compactDiagnostics": diagnostics,
    }


def test_exception_old_constructor_and_identity() -> None:
    assert compact_dsl_validator.CompactDslValidationError is CompactDslValidationError
    error = CompactDslValidationError(["b", "a", "b"])
    assert isinstance(error, ValueError)
    assert error.errors == ("b", "a")
    assert error.diagnostics == ()
    assert error.args == ("Compact DSL validation failed:\n- b\n- a",)
    assert all(group.prompt_context() == {} for group in error.groups)


def test_ordered_mixed_groups_never_zip_diagnostics_and_errors() -> None:
    first = _diagnostic(component_id="first")
    second = _diagnostic(component_id="second")
    mixed = _diagnostic(legacy_message="mixed")
    error = CompactDslValidationError.from_records([first, second, "plain", mixed, "mixed"])
    assert error.errors == (first.legacy_message, "plain", "mixed")
    assert error.diagnostics == (first, second, mixed)
    contexts = [group.prompt_context() for group in error.groups]
    complete = contexts[0].get("compactDiagnostics")
    assert isinstance(complete, list)
    assert [item.get("componentId") for item in complete] == ["first", "second"]
    assert contexts[1:] == [{}, {}]
    result = DesignCompactProcessor._validation_failure("source", error.errors, groups=error.groups)
    assert len(result.errors) == len(error.errors)
    assert tuple(issue.message for issue in result.errors) == error.errors


def test_collector_keeps_original_emission_sequence() -> None:
    diagnostic = _diagnostic()
    collector = DiagnosticCollector()
    collector.append("first")
    emit_error(collector, diagnostic)
    collector.append(diagnostic.legacy_message)
    assert collector == ["first", diagnostic.legacy_message, diagnostic.legacy_message]
    assert collector.records == ["first", diagnostic, diagnostic.legacy_message]
    legacy: list[str] = []
    emit_error(legacy, diagnostic)
    assert legacy == [diagnostic.legacy_message]


@pytest.mark.parametrize("value", [None, False, 0, "", [], {}])
def test_model_formatter_keeps_falsy_facts_without_mutation(value: Any) -> None:
    payload = _payload([_diagnostic(actual=value, component_id=None).to_payload()])
    before = deepcopy(payload)
    result = compact_issue_for_model(payload)
    message = result.get("message")
    assert isinstance(message, str)
    assert "实际值（来源：本轮校验文本）：" + json.dumps(value, ensure_ascii=False) in message
    assert "不能依靠裁剪消除负预算" in message
    assert "位置：" not in message
    assert "修改建议：" not in message
    assert "old error" not in message
    assert "compactDiagnostics" not in result
    assert payload == before


def test_model_formatter_keeps_all_related_diagnostics() -> None:
    payload = _payload(
        [
            _diagnostic(component_id="left").to_payload(),
            _diagnostic(component_id="right", expected={"maximumHeight": 30}).to_payload(),
        ]
    )
    result = compact_issue_for_model(payload)
    message = result.get("message")
    assert isinstance(message, str)
    assert "关联问题 1" in message and "关联问题 2" in message
    assert message.index("组件 left") < message.index("组件 right")
    assert '"maximumHeight":30' in message


@pytest.mark.parametrize("diagnostics", [[], [None], [{}], [{"severity": "warning"}]])
def test_bad_diagnostics_fall_back_to_old_message(diagnostics: list[Any]) -> None:
    payload = _payload(diagnostics)
    before = deepcopy(payload)
    result = compact_issue_for_model(payload)
    assert result.get("message") == payload.get("message")
    assert "compactDiagnostics" not in result
    assert payload == before


def test_missing_hard_constraints_fall_back_instead_of_sending_incomplete_feedback() -> None:
    diagnostic = _diagnostic().to_payload()
    diagnostic.pop("expected")
    payload = _payload([diagnostic])
    before = deepcopy(payload)
    result = compact_issue_for_model(payload)
    assert result.get("message") == payload.get("message")
    assert "compactDiagnostics" not in result
    assert payload == before


def test_other_quality_issues_and_old_records_remain_unchanged() -> None:
    old = QualityIssue(stage="validation", code="COMPACT_DSL_VALIDATION_FAILED", message="old")
    assert compact_issue_for_model(old.to_prompt_payload()) == old.to_prompt_payload()
    other = {"stage": "validation", "code": "ARTIFACT_VALIDATION_FAILED", "expected": {}}
    assert compact_issue_for_model(other) == other


@pytest.mark.parametrize("builder_result", [None, "special hint", "", 12])
def test_hint_resolution_and_invalid_return_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, builder_result: Any
) -> None:
    path = tmp_path / "hints.json"
    path.write_text('{"COMPACT_LAYOUT_HEIGHT_OVERFLOW":"default hint"}', encoding="utf-8")
    monkeypatch.setattr(repair_guidance, "DEFAULT_HINT_PATH", path)
    seen: list[RepairGuidanceContext | None] = []

    def builder(item: CompactDiagnostic, context: RepairGuidanceContext | None) -> Any:
        seen.append(context)
        assert item.actual == {"minimumRequiredHeight": 142}
        return builder_result

    monkeypatch.setattr(repair_guidance, "HINT_BUILDERS", ((_diagnostic().code, builder),))
    context = RepairGuidanceContext(mode="edit", constraints={"preserveFont": None})
    result = resolve_fix_hint(_diagnostic(), context)
    assert result == ("special hint" if builder_result == "special hint" else "default hint")
    assert seen == [context]
    assert context.constraints.get("preserveFont") is None


def test_hint_failures_do_not_mutate_facts_or_hide_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    diagnostic = _diagnostic()
    monkeypatch.setattr(repair_guidance, "DEFAULT_HINT_PATH", tmp_path / "missing.json")

    def builder(item: CompactDiagnostic, context: RepairGuidanceContext | None) -> str:
        item.actual.clear()
        raise RuntimeError("test failure")

    monkeypatch.setattr(repair_guidance, "HINT_BUILDERS", ((diagnostic.code, builder),))
    assert resolve_fix_hint(diagnostic) is None
    assert diagnostic.actual == {"minimumRequiredHeight": 142}
    assert deepcopy(_diagnostic(actual=MISSING)).actual is MISSING


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (None, "default hint"),
        (RepairGuidanceContext(mode="create"), "create hint"),
        (RepairGuidanceContext(mode="edit"), "default hint"),
        (RepairGuidanceContext(mode="edit", constraints={"preserveLayout": True}), "edit hint"),
        (RepairGuidanceContext(mode="edit", constraints={"preserveLayout": False}), "change hint"),
    ],
)
def test_hint_builder_distinguishes_known_conditions_from_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    context: RepairGuidanceContext | None,
    expected: str,
) -> None:
    path = tmp_path / "hints.json"
    path.write_text('{"COMPACT_LAYOUT_HEIGHT_OVERFLOW":"default hint"}', encoding="utf-8")
    monkeypatch.setattr(repair_guidance, "DEFAULT_HINT_PATH", path)

    def builder(item: CompactDiagnostic, conditions: RepairGuidanceContext | None) -> str | None:
        hint: str | None = None
        assert item.actual == {"minimumRequiredHeight": 142}
        if conditions is not None:
            preserve = conditions.constraints.get("preserveLayout")
            if conditions.mode == "create":
                hint = "create hint"
            elif conditions.mode == "edit" and preserve is True:
                hint = "edit hint"
            elif conditions.mode == "edit" and preserve is False:
                hint = "change hint"
        return hint

    monkeypatch.setattr(repair_guidance, "HINT_BUILDERS", ((_diagnostic().code, builder),))
    assert resolve_fix_hint(_diagnostic(), context) == expected


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        '{"UNKNOWN":"hint"}',
        '{"COMPACT_LAYOUT_HEIGHT_OVERFLOW":""}',
        '{"COMPACT_LAYOUT_HEIGHT_OVERFLOW":3}',
        '{"COMPACT_LAYOUT_HEIGHT_OVERFLOW":"a","COMPACT_LAYOUT_HEIGHT_OVERFLOW":"b"}',
    ],
)
def test_invalid_hint_configuration_is_rejected(tmp_path: Path, text: str) -> None:
    path = tmp_path / "hints.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_default_hints(path)


def test_shipping_hint_configuration_and_registration() -> None:
    assert load_default_hints(repair_guidance.DEFAULT_HINT_PATH)
    assert validate_builders(repair_guidance.HINT_BUILDERS) == {}

    def builder(diagnostic: CompactDiagnostic, context: RepairGuidanceContext | None) -> None:
        return None

    with pytest.raises(ValueError, match="Duplicate"):
        validate_builders(((_diagnostic().code, builder), (_diagnostic().code, builder)))


def test_component_graph_preserves_duplicates_and_parent_views() -> None:
    first = ComponentRow("first", "Column", {}, ("value", "value"))
    last = ComponentRow("last", "Column", {}, ("value",))
    value = ComponentRow("value", "Text", {"content": "first value"})
    duplicate = ComponentRow("value", "Text", {"content": "last value"})
    rows = ComponentRows([first, last, value, duplicate])
    graph = component_graph(rows)
    assert graph.records == (first, last, value, duplicate)
    assert graph.by_id.get("value") is duplicate
    assert graph.first_parent.get("value") is first
    assert graph.last_parent.get("value") is last
    assert graph.all_parents.get("value") == [first, first, last]
    assert component_graph(rows) is graph


def _locations(original: str, props: dict[str, Any]) -> SourceLocations:
    context = ValidationContext(
        original_source=original,
        validation_source="validation source",
        components=ComponentRows([ComponentRow("content", "Text", props)]),
        data_rows=[DataRow("/value", 0)],
        task_spec={},
        card_spec={},
    )
    return SourceLocations(context)


def test_source_mapping_uses_original_lines_and_real_property_values() -> None:
    original = '\n```genui\n["content","Text",{"content":{"path":"/old"}}]\n```'
    diagnostic = _diagnostic(property_path="/content/path")
    location = _locations(original, {"content": {"path": "/old"}}).locate(diagnostic)
    assert location.source_line == 3
    assert location.property_path == "/content/path"
    replaced = _locations(original, {"content": {"path": "/new"}}).locate(diagnostic)
    assert replaced.component_id == "content"
    assert replaced.source_line == 3
    assert replaced.property_path is None


@pytest.mark.parametrize(
    "source",
    [
        '["content","Text",{}]\n["content","Text",{}]',
        '["different","Text",{}]',
        '["content","Text",{}]\ninvalid json',
    ],
)
def test_unreliable_source_mapping_omits_location(source: str) -> None:
    result = _locations(source, {}).locate(_diagnostic())
    assert result.component_id is None
    assert result.source_line is None


def test_data_row_mapping_does_not_reuse_removed_or_rewritten_line() -> None:
    diagnostic = _diagnostic(component_id=None, data_path="/value")
    assert _locations('\n["/value",0]', {}).locate(diagnostic).source_line == 2
    assert _locations('["/value",1]', {}).locate(diagnostic).source_line is None
    assert _locations('["/old",0]', {}).locate(diagnostic).source_line is None


def test_processor_and_prompt_preserve_original_source_and_internal_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import generation_pipeline

    root = '["root","Column",{"height":"matchParent"},["text"]]'
    text = '["text","Text",{"content":"body","fontSize":12,"height":200}]'
    original = "\n```genui\n" + root + "\n" + text + "\n```"
    validation = root + "\n" + text
    monkeypatch.setattr(
        generation_pipeline, "repair_compact_dsl_binding_paths", lambda *a, **k: validation
    )
    context = DslProcessingContext(
        size="2x2",
        card_spec={"suggestSize": "2x2"},
        task_spec={"size": "2x2", "dataModelSchema": {}},
        protocol_profile={},
    )
    result = DesignCompactProcessor().process(original, context)
    assert result.errors
    quality_errors = [item.to_prompt_payload() for item in result.errors]
    before = deepcopy(quality_errors)
    height = next(item for item in quality_errors if item.get("compactDiagnostics"))
    diagnostics = height.get("compactDiagnostics")
    assert isinstance(diagnostics, list)
    assert diagnostics[0].get("sourceLine") == 3
    initial = [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    messages = PromptBuilder().build_repair(initial, original, quality_errors)
    content = messages[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("invalidSourceDsl") == original
    errors = payload.get("qualityErrors")
    assert isinstance(errors, list)
    assert len(errors) == len(result.errors)
    assert all("compactDiagnostics" not in item for item in errors)
    assert any("COMPACT_LAYOUT_HEIGHT_OVERFLOW" in item.get("message", "") for item in errors)
    assert quality_errors == before
    assert [item.to_prompt_payload() for item in result.errors] == before
