"""PR #176 review follow-up tests for fusion-ball version and palette handling."""

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
    FusionBallPalette,
    fusion_ball_enabled,
    fusion_ball_palette_for_root,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.prompt_builder import PromptBuilder
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


def _components_by_id(dsl: str) -> dict[str, dict[str, Any]]:
    update = json.loads(dsl.splitlines()[1])["updateComponents"]
    return {component["id"]: component for component in update["components"]}


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


@pytest.mark.parametrize("previous_design_token", [None, '["/state/ready",true]'])
def test_design_compact_prompt_appends_fusion_ball_restriction_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    previous_design_token: str | None,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    task_spec = TaskSpec(
        userQuery="生成日程卡片",
        size="2x2",
        appVersion="11.7.5.205",
        dataModelSchema={"data": {}},
    )

    prompt = PromptBuilder().build_design_compact(
        task_spec,
        "design rules",
        previous_design_token=previous_design_token,
    )

    system_prompt = prompt[0]["content"]
    assert system_prompt.startswith("design rules\n\n# 本次请求运行时限制")
    assert "禁止在任何组件中生成 `fusion-ball-*` Design Token" in system_prompt
    assert "root 必须按非融球背景规则生成" in system_prompt


def test_design_compact_prompt_is_unchanged_when_fusion_ball_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    task_spec = TaskSpec(
        userQuery="生成日程卡片",
        size="2x2",
        appVersion="11.7.5.206",
        dataModelSchema={"data": {}},
    )

    prompt = PromptBuilder().build_design_compact(task_spec, "design rules")

    assert prompt[0] == {"role": "system", "content": "design rules"}


def test_non_design_compact_prompt_does_not_append_fusion_ball_restriction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "CONFIG", {})
    task_spec = TaskSpec(
        userQuery="生成日程卡片",
        size="2x2",
        appVersion="11.7.5.205",
        dataModelSchema={"data": {}},
    )

    prompt = PromptBuilder().build_design_token(
        task_spec,
        "other design rules",
        "other-design-token",
    )

    assert prompt[0] == {"role": "system", "content": "other design rules"}


@pytest.mark.parametrize(
    ("design_token", "expected_palette"),
    [
        (
            "fusion-ball-schedule-cool",
            FusionBallPalette("#FF121E59", "#FF2BA2D9", "#FF52CCCC"),
        ),
        (
            "fusion-ball-schedule-warm",
            FusionBallPalette("#FF731D28", "#FFFF5533", "#FFE68A2E"),
        ),
        (
            "fusion-ball-sleep-violet",
            FusionBallPalette("#FF2B2459", "#FF572BD9", "#FFB398D9"),
        ),
        (
            "fusion-ball-sport-orange",
            FusionBallPalette("#FFB33C24", "#FFFF8833", "#FFFAA89E"),
        ),
    ],
)
def test_fusion_ball_design_tokens_use_fixed_palettes(
    monkeypatch: pytest.MonkeyPatch,
    design_token: str,
    expected_palette: FusionBallPalette,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    components = [
        {
            "component_id": "root",
            "component_type": "Column",
            "props": {"design": design_token},
        },
    ]

    palette = fusion_ball_palette_for_root(
        components,
        size="2x2",
        app_version=_DEFAULT_APP_VERSION,
    )

    assert palette == expected_palette


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


def test_converter_expands_fusion_ball_with_relative_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )
    output = convert_compact_dsl_to_a2ui(
        _fusion_source(),
        size="2x2",
        protocol_profile={"version": "v0.9", "appVersion": "11.7.5.206"},
    )
    components = _components_by_id(output)
    expected_dimensions = {
        "fusionBallBackground": ("100%", "100%"),
        "fusionBallLargeSlot": ("112.5%", "27.5%"),
        "fusionBallLarge": ("116.666667%", "477.272727%"),
        "fusionBallMediumSlot": ("50%", "137.5%"),
        "fusionBallMedium": ("200%", "72.727273%"),
        "fusionBallSmallSlot": ("121.875%", "118.75%"),
        "fusionBallSmall": ("51.282051%", "52.631579%"),
        "fusionBallGlassLayer": ("100%", "100%"),
    }

    for component_id, dimensions in expected_dimensions.items():
        styles = components[component_id]["styles"]
        assert (styles["width"], styles["height"]) == dimensions
    assert components["__genui_render_component__root"]["styles"] == {
        "width": "matchParent",
        "height": "matchParent",
        "padding": 12,
        "borderRadius": 20,
        "clip": True,
    }


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
