# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from types import SimpleNamespace

import pytest

from services import validator as validator_module
from services.card_validation.compact_validation import api as compact_validation_api
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


def test_compact_validation_logs_execution_identity(monkeypatch) -> None:
    captured = _CapturedLogger()
    monkeypatch.setattr(compact_validation_api, "logger", captured)
    monkeypatch.setattr(
        compact_validation_api,
        "_validate_compact_dsl",
        lambda *_args, **_kwargs: CompactDslValidationResult(("layout warning",)),
    )

    result = compact_validation_api.validate_compact_dsl(
        "compact-source",
        task_spec={},
        card_spec={},
        execution_context=_execution_context(),
    )

    assert result.warnings == ("layout warning",)
    assert captured.warning_messages == []
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


def test_compact_probe_failure_is_identified_without_warning_log(monkeypatch) -> None:
    captured = _CapturedLogger()
    monkeypatch.setattr(compact_validation_api, "logger", captured)

    def fail_validation(*_args, **_kwargs):
        raise CompactDslValidationError(["candidate rejected"])

    monkeypatch.setattr(compact_validation_api, "_validate_compact_dsl", fail_validation)
    context = _execution_context().with_purpose(
        "recomposition_candidate",
        candidate_index=4,
    )

    with pytest.raises(CompactDslValidationError, match="candidate rejected"):
        compact_validation_api.validate_compact_dsl(
            "compact-source",
            task_spec={},
            card_spec={},
            execution_context=context,
        )

    assert captured.warning_messages == []
    assert captured.error_messages == []
    assert len(captured.info_messages) == 2
    assert "validation_failed" in captured.info_messages[1]
    assert "purpose=recomposition_candidate candidate_index=4" in captured.info_messages[1]


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
