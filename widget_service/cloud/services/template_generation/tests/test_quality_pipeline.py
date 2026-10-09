"""确保目录内的美学校验器接入公共卡片校验流程。"""

from __future__ import annotations

import json
from typing import Any

from services.card_validation import validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.diagnostics import Diagnostic, Reporter
from services.card_validation.quality.density_validator import DensityValidator
from services.validator import ArtifactValidator


def _genui(*, template_root: bool = False, font_size: int = 13) -> str:
    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["template_root" if template_root else "title_text"],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
    ]
    if template_root:
        components.append(
            {
                "id": "template_root",
                "component": "Column",
                "children": ["title_text"],
                "styles": {"width": "matchParent", "height": "matchParent"},
            }
        )
    components.append(
        {
            "id": "title_text",
            "component": "Text",
            "content": "天气",
            "styles": {"fontSize": font_size, "fontColor": "#FF000000"},
        }
    )
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "quality_pipeline_test",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "quality_pipeline_test",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "quality_pipeline_test",
                "path": "/",
                "value": {},
            },
        },
    ]
    return "\n".join(json.dumps(message) for message in messages)


def test_public_validation_runs_quality_directory_validators() -> None:
    reporter = validate_card(dsl_text=_genui())

    assert reporter.has_code("TYPE.FONT_SIZE_STEP")


def test_template_root_still_skips_the_whole_quality_stage() -> None:
    reporter = validate_card(dsl_text=_genui(template_root=True))

    assert not any(item.stage == "quality" for item in reporter.diagnostics)


def test_current_focus_font_sizes_are_accepted() -> None:
    for font_size in (24, 30, 38):
        reporter = validate_card(dsl_text=_genui(font_size=font_size))

        assert not any(
            item.code == "TYPE.FONT_SIZE_STEP" and item.actual == font_size
            for item in reporter.diagnostics
        )


def _density_context(*, extra_hero: bool = False) -> ValidationContext:
    children = ["focus_row"]
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": children + (["hero"] if extra_hero else []),
        },
        {
            "id": "focus_row",
            "component": "Row",
            "children": ["left", "right"],
            "itemMargin": 8,
            "styles": {"width": 136},
        },
        {
            "id": "left",
            "component": "Text",
            "content": "12",
            "styles": {
                "width": 64,
                "fontSize": 30,
                "fontWeight": 700,
                "textAlign": "center",
            },
        },
        {
            "id": "right",
            "component": "Text",
            "content": "34",
            "styles": {
                "width": 64,
                "fontSize": 30,
                "fontWeight": 700,
                "textAlign": "center",
            },
        },
    ]
    if extra_hero:
        components.append(
            {
                "id": "hero",
                "component": "Text",
                "content": "56",
                "styles": {"fontSize": 30, "fontWeight": 700},
            }
        )
    by_id = {component["id"]: component for component in components}
    return ValidationContext(
        cardspec={"suggestSize": "2x2"},
        components=components,
        components_by_id=by_id,
        root_id="root",
        root_component=by_id["root"],
    )


def test_density_allows_a_legal_parallel_focus_group() -> None:
    reporter = Reporter()

    DensityValidator().validate(_density_context(), None, reporter)

    assert not reporter.has_code("DENSITY.NUMBERS")


def test_density_counts_an_extra_hero_outside_parallel_focus_group() -> None:
    reporter = Reporter()

    DensityValidator().validate(_density_context(extra_hero=True), None, reporter)

    assert reporter.has_code("DENSITY.NUMBERS")


def test_quality_errors_are_observations_at_artifact_boundary() -> None:
    diagnostic = Diagnostic(
        severity="error",
        code="SHAPE.CARD_ROOT_RADIUS",
        stage="quality",
        file_kind="genui",
        message="仅用于观测的美学问题。",
    )
    validator = ArtifactValidator()

    blocking, contexts = validator._normalize_diagnostics(
        [diagnostic],
        "error",
        blocking_only=True,
    )
    observations, _ = validator._normalize_diagnostics(
        [diagnostic],
        "error",
        quality_only=True,
    )

    assert blocking == []
    assert contexts == []
    assert len(observations) == 1
