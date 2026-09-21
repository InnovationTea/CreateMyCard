from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.card_validation import ValidationOptions, validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.diagnostics import Reporter
from services.card_validation.quality.spacing_validator import SpacingValidator
from services.card_validation.rule_registry import RuleRegistry
from services.card_validation.source_parser import SourceParser

RULES_DIR = Path(__file__).resolve().parents[1] / "cloud" / "data" / "validator_rules"


def _context(components: list[dict[str, Any]]) -> ValidationContext:
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "spacing-test"}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "spacing-test",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "spacing-test",
                "path": "/",
                "value": {},
            },
        },
    ]
    reporter = Reporter()
    context = SourceParser().parse(
        "\n".join(json.dumps(message) for message in messages),
        '{"suggestSize":"2x2"}',
        reporter,
    )
    assert not reporter.diagnostics
    return context


def test_spacing_validator_reports_safe_margin_without_scale_rule() -> None:
    context = _context(
        [
            {
                "id": "root",
                "component": "Column",
                "children": ["item"],
                "styles": {"padding": 5},
            },
            {
                "id": "item",
                "component": "Row",
                "children": [],
                "itemMargin": 5,
            },
        ]
    )
    reporter = Reporter()
    SpacingValidator().validate(context, RuleRegistry(RULES_DIR), reporter)

    assert {item.code for item in reporter.diagnostics} == {"SPACING.SAFE_MARGIN"}


def test_spacing_validator_checks_button_horizontal_padding() -> None:
    context = _context(
        [
            {
                "id": "root",
                "component": "Column",
                "children": ["button"],
                "styles": {"padding": 12},
            },
            {
                "id": "button",
                "component": "Button",
                "children": [],
                "styles": {"padding": {"left": 4, "right": 7}},
            },
        ]
    )
    reporter = Reporter()
    SpacingValidator().validate(context, RuleRegistry(RULES_DIR), reporter)

    assert reporter.has_code("SPACING.BUTTON_CONTENT_PADDING")


def test_pipeline_runs_spacing_validator() -> None:
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "spacing-test"}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "spacing-test",
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": [],
                        "styles": {"padding": 0},
                    }
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "spacing-test",
                "path": "/",
                "value": {},
            },
        },
    ]
    reporter = validate_card(
        dsl_text="\n".join(json.dumps(message) for message in messages),
        options=ValidationOptions(max_errors=50),
    )

    assert reporter.has_code("SPACING.SAFE_MARGIN")
