"""Template-generation feature gate tests."""

from __future__ import annotations

from typing import Any

import pytest

from config.config import get_settings
from services.template_generation.feature_gates import (
    FUSION_BALL_MIN_PRD_VERSION_CONFIG,
    fusion_ball_enabled,
)


@pytest.mark.parametrize(
    ("app_version", "expected"),
    [
        ("11.7.5.205", False),
        ("11.7.5.206", True),
        ("11.7.5.207", True),
        ("", False),
        (None, False),
        ("invalid", False),
        ("CreateMyCard/11.7.5.206", False),
    ],
)
def test_fusion_ball_gate_compares_task_spec_app_version(
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
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: 11},
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "invalid"},
    ],
)
def test_fusion_ball_gate_fails_closed_for_invalid_config(
    monkeypatch: pytest.MonkeyPatch,
    config: dict[str, Any],
) -> None:
    monkeypatch.setattr(get_settings(), "CONFIG", config)

    assert fusion_ball_enabled("11.7.5.206") is False
