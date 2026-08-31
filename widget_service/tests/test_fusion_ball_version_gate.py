"""PR #176 review follow-up tests for request and fusion-ball version handling."""

from __future__ import annotations

import inspect
import json
from typing import Any

import pytest
from pydantic import ValidationError

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.fusion_ball_expander import (
    FUSION_BALL_MIN_PRD_VERSION_CONFIG,
    fusion_ball_enabled,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.task_spec_builder import TaskSpecBuilder

_DEFAULT_APP_VERSION = "11.7.5.208"


def _fusion_source() -> str:
    rows = [
        [
            "root",
            "Column",
            {
                "width": 160,
                "height": 160,
                "padding": 12,
                "borderRadius": 20,
                "clip": True,
                "design": "fusion-ball-schedule-cool",
            },
            ["title"],
        ],
        ["title", "Text", {"content": "今日安排", "fontColor": "#FFFFFFFF"}],
    ]
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    )


def _component_ids(dsl: str) -> set[str]:
    update = json.loads(dsl.splitlines()[1])["updateComponents"]
    return {component["id"] for component in update["components"]}


@pytest.mark.parametrize(
    ("app_version", "expected"),
    [
        ("11.7.5.205", False),
        ("11.7.5.206", True),
        (_DEFAULT_APP_VERSION, True),
        ("", False),
        (None, False),
        ("invalid", False),
    ],
)
def test_fusion_ball_gate_uses_configured_minimum(
    monkeypatch: pytest.MonkeyPatch,
    app_version: Any,
    expected: bool,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )

    assert fusion_ball_enabled(app_version) is expected


@pytest.mark.parametrize(
    "config",
    [
        {},
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: ""},
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: None},
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "invalid"},
    ],
)
def test_fusion_ball_gate_fails_closed_for_invalid_config(
    monkeypatch: pytest.MonkeyPatch,
    config: dict[str, Any],
) -> None:
    monkeypatch.setattr(get_settings(), "CONFIG", config)

    assert fusion_ball_enabled(_DEFAULT_APP_VERSION) is False


def test_converter_reads_app_version_from_protocol_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    source = _fusion_source()
    disabled = convert_compact_dsl_to_a2ui(
        source,
        size="2x2",
        protocol_profile={"version": "v0.9", "appVersion": "11.7.5.205"},
    )
    enabled = convert_compact_dsl_to_a2ui(
        source,
        size="2x2",
        protocol_profile={"version": "v0.9", "appVersion": "11.7.5.206"},
    )

    assert "fusionBallBackground" not in _component_ids(disabled)
    assert "fusionBallBackground" in _component_ids(enabled)
    assert "app_version" not in inspect.signature(convert_compact_dsl_to_a2ui).parameters


def test_design_processor_copies_task_spec_app_version_into_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    results: dict[str, str] = {}
    for app_version in ("11.7.5.205", "11.7.5.206"):
        task_spec = TaskSpec(
            userQuery="日程卡片",
            size="2x2",
            appVersion=app_version,
            dataModelSchema={"data": {}},
        )
        context = DslProcessingContext(
            size="2x2",
            card_spec={
                "title": "今日日程",
                "description": "展示今天的安排",
                "suggestSize": "2x2",
                "dataBindings": [],
            },
            task_spec=task_spec.model_dump(mode="json"),
            protocol_profile={"version": "v0.9"},
            design_profile_id="design-compact-dsl",
        )

        result = processor.process(_fusion_source(), context)

        assert not result.errors
        results[app_version] = result.standard_dsl

    assert "fusionBallBackground" not in results["11.7.5.205"]
    assert "fusionBallBackground" in results["11.7.5.206"]


def test_task_spec_defaults_to_reviewed_app_version() -> None:
    task_spec = TaskSpec(
        userQuery="日程卡片",
        size="2x2",
        dataModelSchema={"data": {}},
    )

    assert task_spec.appVersion == _DEFAULT_APP_VERSION


@pytest.mark.parametrize("app_version", ["", "invalid"])
def test_task_spec_rejects_invalid_app_version(app_version: str) -> None:
    with pytest.raises(ValidationError):
        TaskSpec(
            userQuery="日程卡片",
            size="2x2",
            appVersion=app_version,
            dataModelSchema={"data": {}},
        )


def test_task_spec_builder_preserves_valid_app_version() -> None:
    app_version = "11.7.5.208+review.1"

    task_spec = TaskSpecBuilder().build(
        user_query="日程卡片",
        size="2x2",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
        app_version=app_version,
    )

    assert task_spec.appVersion == app_version
