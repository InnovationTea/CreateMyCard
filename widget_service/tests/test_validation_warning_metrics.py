# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from types import SimpleNamespace

from services import validation_metrics
from services.card_validation.diagnostics import Diagnostic
from services.validation_execution import ValidationExecutionContext
from services.validation_metrics import ValidationWarning, report_validation_warnings
from utils.ops_metrics import VALIDATION_ERROR_MESSAGE


def _context(**changes: object) -> ValidationExecutionContext:
    values = {
        "operation": "generateWidgetCardCompactDsl",
        "generation_mode": "create",
        "phase": "repair",
        "attempt": 2,
        "purpose": "delivery_candidate",
        "report_metrics": True,
    }
    values.update(changes)
    return ValidationExecutionContext(**values)


def _enable_reporting(monkeypatch, received: list[dict[str, str]]) -> None:
    settings = SimpleNamespace(enable_validation_warning_metrics=True)
    monkeypatch.setattr(validation_metrics, "get_settings", lambda: settings)
    monkeypatch.setattr(
        validation_metrics,
        "report_ops_metrics",
        lambda body: received.append(body),
    )


def test_formal_validation_reports_each_distinct_warning_with_identity(monkeypatch) -> None:
    received: list[dict[str, str]] = []
    _enable_reporting(monkeypatch, received)
    warning = ValidationWarning(
        source="compact_dsl",
        code="COMPACT_DSL_VALIDATION_WARNING",
        message="COMPACT_LAYOUT_HEIGHT_OVERFLOW: root exceeds height budget.",
    )

    report_validation_warnings((warning, warning), _context())

    assert received == [
        {
            VALIDATION_ERROR_MESSAGE: (
                "[warning] [operation=generateWidgetCardCompactDsl] "
                "[generation_mode=create] [phase=repair] [attempt=2] "
                "[source=compact_dsl] [purpose=delivery_candidate] "
                "COMPACT_DSL_VALIDATION_WARNING: "
                "COMPACT_LAYOUT_HEIGHT_OVERFLOW: root exceeds height budget."
            )
        }
    ]


def test_different_attempts_are_reported_separately(monkeypatch) -> None:
    received: list[dict[str, str]] = []
    _enable_reporting(monkeypatch, received)
    warning = ValidationWarning("compact_dsl", "TEST_WARNING", "same warning")

    report_validation_warnings((warning,), _context(phase="initial", attempt=1))
    report_validation_warnings((warning,), _context(phase="repair", attempt=2))

    messages = [body.get(VALIDATION_ERROR_MESSAGE, "") for body in received]
    assert len(messages) == 2
    assert "[phase=initial] [attempt=1]" in messages[0]
    assert "[phase=repair] [attempt=2]" in messages[1]


def test_probe_standalone_and_disabled_reporting_are_excluded(monkeypatch) -> None:
    received: list[dict[str, str]] = []
    _enable_reporting(monkeypatch, received)
    warning = ValidationWarning("compact_dsl", "TEST_WARNING", "warning")

    report_validation_warnings(
        (warning,),
        _context(purpose="recomposition_candidate"),
    )
    report_validation_warnings(
        (warning,),
        _context(purpose="standalone", report_metrics=False),
    )
    monkeypatch.setattr(
        validation_metrics,
        "get_settings",
        lambda: SimpleNamespace(enable_validation_warning_metrics=False),
    )
    report_validation_warnings((warning,), _context())

    assert received == []


def test_artifact_warning_keeps_code_message_and_location_without_raw_values() -> None:
    diagnostic = Diagnostic(
        severity="warning",
        code="VISUAL.CONTRAST",
        stage="quality",
        file_kind="genui",
        line=2,
        json_pointer="/updateComponents/componentsById/title/styles/fontColor",
        message="文本与背景对比度不足",
        actual={"raw": "do-not-report"},
        expected={"raw": "do-not-report"},
        fix_hint="do not include the full object",
    )

    warning = ValidationWarning.from_artifact_diagnostic(diagnostic)

    assert warning == ValidationWarning(
        source="a2ui_artifact",
        code="VISUAL.CONTRAST",
        message="文本与背景对比度不足",
        location=(
            "genui:2 "
            "/updateComponents/componentsById/title/styles/fontColor"
        ),
    )
