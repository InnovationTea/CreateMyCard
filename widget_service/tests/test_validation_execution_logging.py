# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from types import SimpleNamespace

import pytest

from services import generation_pipeline as pipeline
from services import validator as validator_module
from services.card_validation.compact_validation.diagnostics import (
    CompactDslValidationError,
    CompactDslValidationResult,
)
from services.card_validation.diagnostics import Diagnostic
from services.validation_execution import ValidationExecutionContext
from services.validator import ArtifactValidator


class _CapturedLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


def _execution_context() -> ValidationExecutionContext:
    return ValidationExecutionContext(
        operation="generateWidgetCardCompactDsl",
        generation_mode="create",
        phase="repair",
        attempt=2,
        purpose="delivery_candidate",
    )


def test_validation_execution_context_marks_candidate_without_losing_attempt() -> None:
    context = _execution_context().with_purpose(
        "recomposition_candidate",
        candidate_index=3,
    )

    assert context.phase == "repair"
    assert context.attempt == 2
    assert context.purpose == "recomposition_candidate"
    assert context.candidate_index == 3
    assert context.log_fields() == (
        "operation=generateWidgetCardCompactDsl generation_mode=create "
        "phase=repair attempt=2 purpose=recomposition_candidate candidate_index=3"
    )


@pytest.fixture
def compact_pipeline(monkeypatch):
    captured = _CapturedLogger()
    monkeypatch.setattr(pipeline, "logger", captured)
    monkeypatch.setattr(pipeline, "trace_step", lambda *_args, **_kwargs: None)
    for name in ("repair_compact_dsl_safe_structure", "repair_compact_dsl_binding_paths"):
        monkeypatch.setattr(pipeline, name, lambda source, **_kwargs: source)
    monkeypatch.setattr(
        pipeline, "expand_compact_semantic_layout", lambda source, **_kwargs: (source, {}),
    )
    monkeypatch.setattr(
        pipeline.A2UIProtocolRegistry, "read_design_protocol_profile", lambda *_args: {},
    )
    monkeypatch.setattr(
        pipeline, "evaluate_compact_plan_coverage",
        lambda *_args, **_kwargs: SimpleNamespace(errors=(), warnings=(), duplicate_facts=()),
    )
    monkeypatch.setattr(pipeline, "compact_plan_omitted_facts", lambda *_args: ())
    monkeypatch.setattr(pipeline, "bounded_component_capacity_contexts", lambda *_args: ())
    monkeypatch.setattr(pipeline, "convert_compact_dsl_to_a2ui", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(pipeline, "repair_repeated_display_units", lambda source, *_args: source)
    context = pipeline.DslProcessingContext(
        size="2x4", task_spec={"appVersion": "test"}, card_spec={}, protocol_profile={},
        validation_execution_context=_execution_context(),
    )
    return captured, context


def test_compact_validation_logs_execution_identity(monkeypatch, compact_pipeline) -> None:
    captured, context = compact_pipeline
    monkeypatch.setattr(
        pipeline, "validate_compact_dsl",
        lambda *_args, **_kwargs: CompactDslValidationResult(("layout warning",)),
    )
    result = pipeline.DesignCompactProcessor()._process("compact-source", context)

    assert result.errors == ()
    assert len(captured.warning_messages) == 1
    assert "layout warning" in captured.warning_messages[0]
    assert captured.error_messages == []
    assert len(captured.info_messages) == 2
    assert "validation_started" in captured.info_messages[0]
    assert "phase=repair attempt=2 purpose=delivery_candidate" in captured.info_messages[0]
    assert "validation_completed" in captured.info_messages[1]
    assert "warning_count=1" in captured.info_messages[1]


@pytest.mark.parametrize("layout", [False, True])
def test_artifact_context_is_per_call_and_layout_scope_is_preserved(monkeypatch, layout):
    captured = _CapturedLogger()
    observed_layouts = []

    def check_phase(_source, *, layout):
        observed_layouts.append(layout)
        return []

    monkeypatch.setattr(validator_module, "logger", captured)
    monkeypatch.setattr(validator_module, "theme_phase_errors", check_phase)
    monkeypatch.setattr(
        validator_module, "validate_card", lambda **_kwargs: SimpleNamespace(diagnostics=[]),
    )
    artifact = SimpleNamespace(
        genui="",
        meta=SimpleNamespace(capabilityRegistryVersion="test-registry"),
        model_dump=lambda **_kwargs: {},
    )
    validator = ArtifactValidator(asset_src_url_mapping={})
    validate = validator.validate_layout if layout else validator.validate
    first = _execution_context()
    second = first.with_purpose("theme_fallback")
    for context in (first, second):
        assert validate(artifact, {"id": "test-profile"}, execution_context=context) == []
    assert validate(artifact, {"id": "test-profile"}) == []

    expected = (first, second, ValidationExecutionContext())
    assert len(captured.info_messages) == 6
    for index, context in enumerate(expected):
        assert context.log_fields() in captured.info_messages[index * 2]
        assert context.log_fields() in captured.info_messages[index * 2 + 1]
    assert observed_layouts == [layout, layout, layout]
    assert validator_module.in_layout_phase() is False


def test_compact_failure_logs_error_and_preserves_issues(monkeypatch, compact_pipeline) -> None:
    captured, context = compact_pipeline

    def fail_validation(*_args, **_kwargs):
        raise CompactDslValidationError(["candidate rejected"])

    monkeypatch.setattr(pipeline, "validate_compact_dsl", fail_validation)
    result = pipeline.DesignCompactProcessor()._process("compact-source", context)

    assert len(result.errors) == 1
    assert result.errors[0].message == "candidate rejected"
    assert captured.warning_messages == []
    assert len(captured.error_messages) == 1
    assert len(captured.info_messages) == 1
    assert "validation_failed" in captured.error_messages[0]
    assert "error_count=1" in captured.error_messages[0]
    assert _execution_context().log_fields() in captured.error_messages[0]


@pytest.mark.parametrize("stage", ["validation", "outer_recomposition"])
def test_compact_program_exception_is_logged_and_propagated(monkeypatch, compact_pipeline, stage):
    from dataclasses import replace

    captured, context = compact_pipeline
    failure = RuntimeError("unexpected program failure")

    def crash(*_args, **_kwargs):
        raise failure

    if stage == "outer_recomposition":
        context = replace(context, size="2x2")
        monkeypatch.setattr(pipeline, "recompose_small_card", crash)
    else:
        monkeypatch.setattr(pipeline, "validate_compact_dsl", crash)
    with pytest.raises(RuntimeError) as caught:
        pipeline.DesignCompactProcessor()._process("source", context)
    assert caught.value is failure
    assert len(captured.error_messages) == 1
    assert f"{stage}_crashed" in captured.error_messages[0]
    assert "Traceback" in captured.error_messages[0]


@pytest.mark.parametrize("accepted", [True, False])
def test_search_logs_one_summary_and_keeps_final_validation(
    monkeypatch, compact_pipeline, accepted,
):
    from dataclasses import replace

    from services import compact_outer_recomposition as search

    captured, context = compact_pipeline
    context = replace(context, size="2x2", validation_execution_context=None)
    metrics = []
    calls = []
    monkeypatch.setattr(pipeline, "report_ops_metrics", lambda **kwargs: metrics.append(kwargs))

    def validate(source, **kwargs):
        assert "execution_context" not in kwargs
        calls.append(source)
        if source.startswith("candidate"):
            if not accepted or source == "candidate-1":
                raise CompactDslValidationError(["rejected"])
        return CompactDslValidationResult(())

    def recompose(source, **kwargs):
        assert "validation_execution_context" not in kwargs
        return search._search_recomposition_candidates(
            source, iter(("candidate-1", "candidate-2")),
            reasons=("height_capacity",), validation_context={},
            compact_plan=None, task_spec={},
        )

    monkeypatch.setattr(search, "validate_compact_dsl", validate)
    monkeypatch.setattr(search, "compact_plan_coverage_errors", lambda *_args: ())
    monkeypatch.setattr(pipeline, "validate_compact_dsl", validate)
    monkeypatch.setattr(pipeline, "recompose_small_card", recompose)
    result = pipeline.DesignCompactProcessor()._process("original", context)
    assert result.errors == ()
    assert calls == ["candidate-1", "candidate-2", "candidate-2" if accepted else "original"]
    assert len(captured.info_messages) == 3
    assert "outer_recomposition_completed" in captured.info_messages[0]
    assert f"applied={accepted} candidate_count=2" in captured.info_messages[0]
    assert ValidationExecutionContext().log_fields() in captured.info_messages[0]
    assert captured.error_messages == []
    assert captured.warning_messages == []
    assert metrics == []


def test_artifact_validation_logs_execution_identity(monkeypatch) -> None:
    captured = _CapturedLogger()
    diagnostic = Diagnostic(
        severity="warning",
        code="TEST_WARNING",
        stage="quality",
        file_kind="dsl",
        message="layout warning",
    )
    reporter = SimpleNamespace(diagnostics=[diagnostic])
    artifact = SimpleNamespace(
        genui="",
        meta=SimpleNamespace(capabilityRegistryVersion="test-registry"),
        model_dump=lambda **_kwargs: {},
    )
    monkeypatch.setattr(validator_module, "logger", captured)
    monkeypatch.setattr(validator_module, "theme_phase_errors", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(validator_module, "validate_card", lambda **_kwargs: reporter)

    validator = ArtifactValidator()
    errors = validator.validate(
        artifact,
        {"id": "test-profile"},
        execution_context=_execution_context(),
    )

    assert errors == []
    assert captured.warning_messages == []
    assert captured.error_messages == []
    assert len(captured.info_messages) == 2
    assert "artifact_validation_started" in captured.info_messages[0]
    assert "phase=repair attempt=2 purpose=delivery_candidate" in captured.info_messages[0]
    assert "artifact_validation_completed" in captured.info_messages[1]
    assert "warning_count=1" in captured.info_messages[1]
